"""
Bot module for all the memberlist modifying functions. Also includes the 
scheduled daily update.

How to safely edit the memberlist:
 - access the instance of this module with bot.get_cog("MemberlistCog")
 - request edit permission to the list with await membcog.lock()
 - make your edits through the list_access dictionary given to you by lock().
   You can use the helper functions in memberlist.py to add, remove or move 
   members between lists in a convenient way. You can also find a member that 
   you can then edit by searching for a member with memberlist_get.
 - once you finished your edits call membcog.unlock()
   Calling unlock() signals that you wont make more changes and that the next
   function can start making its edits, this prevents conflicts. 
   The lock / unlock steps also handle all the synching to the disk and google
   drive spreadsheet for you so there's no need to update those.
   DO NOT keep copies of lists or individual members after unlock or be very 
   certain you do not edit them in any way. It can cause editing conflicts or 
   can desync the lists in memory from the ones on the disk / google drive.
"""
from discord.ext import tasks, commands
import io
import textwrap
import discord
from discord import app_commands
from discord import Interaction
from datetime import datetime, timedelta
from logfile import LogFile
import asyncio
import re
# custom modules
import zerobot_common
import utilities

logfile = LogFile("logs/logfile", prefix = "MemberListCog")

from utilities import _strToDate, send_messages
from sheet_ops import (
    clear_sheets,
    color_spreadsheet,
    load_sheet_changes,
    memberlist_to_sheet,
    warnings_from_sheet
)
from rankchecks import (
    Todos,
    TodosInviteIngame,
    TodosJoinDiscord,
    TodosUpdateRanks,
    update_discord_info
)
from clantrack import get_ingame_memberlist, compare_lists
from searchresult import SearchResult
from memberembed import member_embed
import memberlist
from memberlist import (
    join_date_cond,
    memberlist_sort,
    memberlist_sort_name,
    memberlist_sort_clan_xp,
    memberlist_sort_leave_date,
    memberlist_from_disk,
    memberlist_to_disk,
    memberlist_get,
    memberlist_remove,
    memberlist_move,
    memberlist_get_all,
    memberlist_compare_stats
)
from member import (
    Member,
    valid_discord_id,
    valid_profile_link,
    notify_role_names
)
from exceptions import (
    BannedUserError,
    ExistingUserWarning,
    MemberNotFoundError,
    NotACurrentMemberError,
    StaffMemberError,
    NotADiscordId,
    NotAProfileLink
)

# logfile for clantrack
memberlist_log = LogFile("logs/memberlist")

def parse_discord_id(id):
    """
    Tries to parse id as a valid discord id.
    Raises NotADiscordId if id could not be parsed as discord id.
    """
    if isinstance(id, str):
        try:
            id = int(id)
        except ValueError:
            raise NotADiscordId()
    if valid_discord_id(id):
        return id
    raise NotADiscordId()
def parse_profile_link(id):
    """
    Tries to parse id as a valid profile link.
    Raises NotADiscordId if id could not be parsed as discord id.
    """
    if isinstance(id, str):
        # force https entries
        id = id.replace("http:", "https:")
    if valid_profile_link(id):
        return id
    raise NotAProfileLink()

def _Inactives(days):
    """
    Returns a list of players that have been inactive for more than the 
    specified number of days. List is sorted by lowest clan xp first.
    """
    memberlist = memberlist_from_disk(zerobot_common.current_members_filename)
    today = datetime.utcnow()
    results = list()
    for memb in memberlist:
        if memb.discord_rank in zerobot_common.inactive_exceptions.keys():
            continue
        if memb.name in zerobot_common.inactive_exceptions.keys():
            continue
        if memb.last_active == None:
            days_inactive = today - datetime.strptime(
                "2020-04-14", utilities.dateformat
            )
            memb.last_active = datetime.strptime(
                "2020-04-14", utilities.dateformat
            )
        else:
            days_inactive = today - memb.last_active
        if days_inactive.days >= days:
            memb.days_inactive = days_inactive.days
            results.append(memb)
    
    memberlist_sort_clan_xp(results)
    return results

def _Need_Full_Reqs():
    """
    Returns a list of players that should have the full member rank by now.
    Req introduced: 2021-09-27, time given: 3 months
    """
    req_start_date = _strToDate("2021-09-27")
    req_time_days = 90
    today = datetime.utcnow()
    mlist = memberlist_from_disk(zerobot_common.current_members_filename)
    need_full = []

    for memb in mlist:
        # stored as string
        join_date = _strToDate(memb.join_date)
        # skip if memb joined before new reqs
        if join_date < req_start_date:
            continue
        # skip if memb is not a recruit
        if memb.rank != "Recruit":
            continue
        days_elapsed = (today - join_date).days
        if days_elapsed > req_time_days:
            need_full.append(memb)
    
    # sort results by join date, sort after = less work
    memberlist_sort(need_full, join_date_cond)
    return need_full
    
def need_full_req_formatter(memb):
    leng = 12 - len(memb.name)
    while leng > 0:
        memb.name += " "
        leng -= 1
    return f"{memb.name}  {memb.join_date}  {memb.rank}\n"

async def on_message_hostcounter(message, memblistcog):
    """
    callback function for on message event to checks if message is to host 
    something. Used to track of player host stats.

    This is triggered for any message received, including our own.
    Must keep this efficient, return asap if irrelevant.
    """
    if len(message.role_mentions) == 0:
        return
    if memblistcog.bot.user.id == message.author.id:
        return
    
    list_access = await memblistcog.lock(skip_sheet=True)
    member = memberlist_get(list_access["current_members"], message.author.id)
    if member is None:
        await memblistcog.unlock(skip_sheet=True)
        return

    for role in message.role_mentions:
        if role.name in notify_role_names:
            new_value = member.notify_stats[role.name] + 1
            member.notify_stats[role.name] = new_value
    await memblistcog.unlock(skip_sheet=True)

def split_multiple(content, codeblock=False):
    """
    Tries to fit content in as few strings under 2k length as possible.
    content can be a single string or a list of strings.
    """
    #TODO: list case could fit nicer, append whats possible first
    #TODO: splits are random, could try to respect codeblocks / breaks etc
    messages = []
    # single string case
    if type(content) == str:
        index = 0
        while index < len(content):
            block = content[index:index+1990]
            messages.append(block)
            index += 1990
        if codeblock:
            return list(map(lambda msg: f"```{msg}```", messages))
        return messages
    # list of strings case
    index = 0
    while index < len(content):
        # single message is too large and needs splitting
        if len(content[index]) > 1990:
            messages += split_multiple(content[index])
            index += 1
        else:
            msg = ""
            while (len(msg) + len(content[index])) < 1990:
                msg += content[index]
                index += 1
                if index >= len(content):
                    break 
            messages.append(msg)
    if codeblock:
        return list(map(lambda msg: f"```{msg}```", messages))
    return messages

async def send_multiple(ctx, content, codeblock=False):
    """
    Splits up a list of messages and sends them in batches.
    Ensures a batch of messages doesnt exceed discords 2k character limit.
    Should still add check to split up individual strings if too long.
    """
    messages = split_multiple(content, codeblock)
    for msg in messages:
        await ctx.send(msg)

def add_dupe(list, dupe):
    if dupe is None: return False

    in_list = False
    for m in list:
        if m.entry_id == dupe.entry_id: in_list = True
    if not(in_list):
        list.append(dupe)
        return True
    return False

async def warn_duplicates(self):
    res = ["duplicates in current memberlist:\n"]
    dupes = []
    # straight duplicate check
    for memb in self.current_members:
        for m in self.current_members:
            if memb.entry_id == m.entry_id:
                continue
            if memb.name == m.name and add_dupe(dupes, m):
                res.append(
                    f" name duplicate in current members: {m.name}, "
                    f"entry id {m.entry_id}\n"
                )
    for memb in self.current_members:
        for m in self.current_members:
            if memb.entry_id == m.entry_id:
                continue
            if memb.discord_id == 0:
                continue # no need to check
            if memb.discord_id == m.discord_id and add_dupe(dupes, m):
                res.append(
                    f" discord_id duplicate in current members: {m.discord_id}, "
                    f"entry id {m.entry_id}\n"
                )
    res.append(
        "It is possible to remove memberlist entries with /remove_member.\n"
    )

    # unmarked rejoiner check
    res.append(
        "\nmight have rejoined (different member ids but they look similar):\n"
    )
    for memb in self.current_members:
        for m in self.old_members:
            if memb.id == m.id:
                continue # already marked as known rejoiner
            if memb.name == m.name:
                res.append(
                    f" did current member id {memb.id}, old member id {m.id} "
                    f"rejoin? same name: {m.name}\n"
                )
            if memb.discord_id == 0:
                continue # no need to check
            if memb.discord_id == m.discord_id:
                res.append(
                    f" did current member id {memb.id}, old member id {m.id} "
                    f"rejoin? same discord_id: {m.discord_id}\n"
                )
    res.append(
        "For rejoining members, re-use their member id from the old member "
        "list. Use /edit_member_id to give them the same member id as before. "
        "This lets zbot know they rejoined. (do not remove the old member,"
        "leave the info on the old members list intact)\n"
    )
    
    # got past banlist check
    res.append(
        "\nmight have sneakily gotten past our banlist:\n"
    )
    dupes = []
    for memb in self.current_members:
        # discord_id is on banlist
        dupe = memberlist_get(self.banned_members, memb.discord_id)
        if add_dupe(dupes, dupe):
            res.append(f"shared discord_id {memb.discord_id}, current: {memb.name} bannned: {dupe.name}\n")
        # name is on banlist
        # name is in banlist.member.oldnames
        # member.oldnames on banlist
    
    #TODO: check for entry_id dupes, these should not happen at all.
    #    id dupes are expected from rejoiners, cant check if actual rejoiner.
    #    maybe occasionally run a manual check / separate command to verify.
    #TODO: could check if old members on banlist
    await send_multiple(zerobot_common.bot_channel, res, codeblock=True)


async def daily_update(self):
    """
    The actual daily update process.
     - retrieve ingame data if not provided
     - load any changes on sheet into memory
     - compare memory with ingame
     - handle stay/leave/join/rename in memory
        - for leave, set site retired, remove discord roles
     - load discord info for current membs
     - load site info for current membs
     - write finished versions to backup
     - write finished versions to disk
     - write finished versions to sheet
     - re-color spreadsheet
     - print changes summary
     - print todo lists
    """
    # start posting update warnings on spreadsheet
    await zerobot_common.bot_channel.send(
        "Starting to collect ingame data for update"
    )

    # retrieve the latest ingame data as a new concurrent ask
    ingame_members = await self.bot.loop.run_in_executor(
        None, get_ingame_memberlist, self.highest_id, self.highest_entry_id
    )
    # backup ingame members right away, nice for testing
    date_str = datetime.utcnow().strftime(utilities.dateformat)
    ing_backup_name = (
        "memberlists/current_members/ingame_membs_" + date_str + ".txt"
    )
    memberlist_to_disk(ingame_members, ing_backup_name)
    
    # post update warning on discord
    await zerobot_common.bot_channel.send("Daily update starting")

    #=== try to obtain editing lock, loads sheet changes ===
    await self.lock()
    if zerobot_common.sheet_memberlist_enabled:
        clear_sheets()
    # compare against new ingame data to find joins, leaves, renames
    comp_res = compare_lists(ingame_members, self.current_members)
    # use result to update our list of current members
    self.current_members = (
        comp_res.staying + comp_res.joining + comp_res.renamed
    )
    # get site updates, send list to siteops func that updates it
    update_discord_info(self.current_members)
    self.logfile.log("retrieved discord user changes...")
    if zerobot_common.site_enabled:
        zerobot_common.siteops.update_site_info(self.current_members)
    self.logfile.log("retrieved site user changes...")
    # for leaving members remove discord roles, set site rank to retired
    await process_leaving_members(self, comp_res.leaving)
    self.logfile.log("updated discord accounts of leaving members...")

    # sort updated lists
    memberlist_sort_name(self.current_members)
    memberlist_sort_name(self.old_members)
    memberlist_sort_name(self.banned_members)
    # check memberlists for duplicate discord ids
    await warn_duplicates(self)
    self.logfile.log("checked the memberlists for duplicates...")

    # write updated memberlists to disk as backup
    cur_backup_name = (
        "memberlists/current_members/current_membs_" + date_str + ".txt"
    )
    old_backup_name = (
        "memberlists/old_members/old_membs_" + date_str + ".txt"
    )
    ban_backup_name = (
        "memberlists/banned_members/banned_membs_" + date_str + ".txt"
    )
    memberlist_to_disk(self.current_members, cur_backup_name)
    memberlist_to_disk(self.old_members, old_backup_name)
    memberlist_to_disk(self.banned_members, ban_backup_name)

    #=== release editing lock, writes to sheet and disk ===
    await self.unlock()
    
    #update colors on sheet
    if zerobot_common.sheet_memberlist_enabled:
        color_spreadsheet()

    # post summary of changes
    await zerobot_common.bot_channel.send(comp_res.summary())
    #post todo lists,
    to_invite = TodosInviteIngame(self.current_members)
    await send_multiple(zerobot_common.bot_channel, to_invite)
    to_join_discord = TodosJoinDiscord(self.current_members)
    await send_multiple(zerobot_common.bot_channel, to_join_discord)
    to_update_rank = TodosUpdateRanks(self.current_members)
    await send_multiple(zerobot_common.bot_channel, to_update_rank, codeblock=True)

async def process_leaving_member(self, memb):
    self.logfile.log(
        f" - {memb.name} is leaving, updating discord and site ranks..."
    )
    today_date = datetime.utcnow().strftime(utilities.dateformat)
    # update leave date and reason
    if (memb.leave_date == ""):
        memb.leave_date = today_date
    if (memb.leave_reason == ""):
        memb.leave_reason = "left or inactive kick"
    self.old_members.append(memb)
    rank_index = utilities.rank_index(discord_role_name=memb.discord_rank)
    if rank_index is None:
        await zerobot_common.bot_channel.send(
            f"Unknown rank for leaving member: {memb.name}, skipped for "
            "automatic rank removal. You will have to update their "
            "discord roles and site rank manually."
        )
        return
    if rank_index <= zerobot_common.staff_rank_index:
        await zerobot_common.bot_channel.send(
            f"Can not do automatic deranks for leaving member: "
            f"{memb.name}, bot isn't allowed to change staff ranks. "
            f"You will have to update their discord roles and site "
            f"rank manually."
        )
        return
    # remove discord roles
    await self.removeroles(memb)
    # set site rank to retired member
    if zerobot_common.site_enabled:
        if valid_profile_link(memb.profile_link):
            zerobot_common.siteops.setrank_member(memb, "Retired member")
        else:
            await zerobot_common.bot_channel.send(
                f"Could not remove site rank for {memb.name}, profile link : "
                f"{memb.profile_link}"
            )

async def process_leaving_members(self, leaving_list):
    """
    Process the leaving members, removes their discord roles, sets their
    site rank to retired. 
    """
    leaving_size = len(leaving_list)
    self.logfile.log(f"{leaving_size} leaving members:")
    if (leaving_size > 10):
        await zerobot_common.bot_channel.send(
            f"Safety Check: too many members leaving for automatic site "
            f"rank and discord role removal: {leaving_size}. No discord "
            f"roles or site ranks changed, you will have to update them "
            f"manually."
        )
        return

    for memb in leaving_list:
        await process_leaving_member(self, memb)

def get_highest_ids(self):
    # could switch to highest unused id but thats unnecessary complexity atm
    highest_id = 0
    highest_entry_id = 0
    for memb in self.current_members:
        if memb.id > highest_id:
            highest_id = memb.id
        if memb.entry_id > highest_entry_id:
            highest_entry_id = memb.entry_id
    for memb in self.old_members:
        if memb.id > highest_id:
            highest_id = memb.id
        if memb.entry_id > highest_entry_id:
            highest_entry_id = memb.entry_id
    for memb in self.banned_members:
        if memb.id > highest_id:
            highest_id = memb.id
        if memb.entry_id > highest_entry_id:
            highest_entry_id = memb.entry_id
    self.highest_id = highest_id
    self.highest_entry_id = highest_entry_id

class MemberlistCog(commands.Cog):
    """
    Handles commands related to memberlist changes and starts the daily update.
    """
    def __init__(self, bot):
        self.bot = bot
        self.logfile = LogFile("logs/botlog")
        self.logfile.log(f"MembList cog loaded and ready.")
        self.updating = False
        self.update_msg = ""
        self.confirmed_update = False
        self.ingame_update_result = None

        self.current_members = memberlist_from_disk(
            zerobot_common.current_members_filename
        )
        self.old_members = memberlist_from_disk(
            zerobot_common.old_members_filename
        )
        self.banned_members = memberlist_from_disk(
            zerobot_common.banned_members_filename
        )
        # init highest used member id state
        self.highest_id = 0
        self.highest_entry_id = 0
        get_highest_ids(self)

        self.list_access = {}

        if zerobot_common.daily_mlist_update_enabled:
            bot.daily_callbacks.append((daily_update, [self]))
        bot.on_message_callbacks.append((on_message_hostcounter, [self]))
        bot.daily_callbacks.append(
            (
                self.post_inactives,
                [zerobot_common.bot_channel2]
            )
        )
        bot.daily_callbacks.append(
            (
                self.post_need_full_reqs,
                [zerobot_common.bot_channel2]
            )
        )
    
    async def lock(self, interval=60, message=None, ctx=None, skip_sheet=False):
        """
        Signals that you wish to access and edit the memberlist.
        Returns a list_access dictionary with references to each memberlist.

        Load a copy from disk instead if you do not need to make edits. Use
        memberlist.memberlist_from_disk(filename) for this.

        DO NOT copy / replace references in list_access! Always act on them by
        looking up the key value in the list_access object. GOOD examples :
         - list_access["current_members"].append(new_member).
         - member_foo = memberlist_get(list_access["current_members"], "foo")
           member_foo.note1 = "this guy did well"
        BAD example, copies list reference. The banlist reference copy points
        to the actual banlist even after unlock. If you modify it after unlock
        you may wreck other functions by breaking the single accesss promise.
         - banlist = list_access["banned_members"]
        BAD example, replaces list reference but wont affect the actual list:
         - list_access["banned_members"] = my_new_list

        Acts as an imperfect mutex, locks access to the memberlist to prevent 
        simultanious editing. 'Imperfect' as it's not purely atomic, there 
        could be an interrupt between checking self.updating and locking it 
        as true. Time between lock() and unlock() should be kept to a minimum 
        to prevent waiting time / having to resend commands.

        Retries obtaining the lock at interval times until succesful. Default
        interval between attempts is 60 seconds. No fifo / other scheduling.
        """
        while self.updating:
            if message is not None:
                if ctx is not None:
                    await ctx.send(message)
                else:
                    await zerobot_common.bot_channel.send(message)
            await asyncio.sleep(interval)
        self.updating = True
        if not skip_sheet and zerobot_common.sheet_memberlist_enabled:
            load_sheet_changes(
                self.current_members, zerobot_common.current_members_sheet
            )
            load_sheet_changes(
                self.old_members, zerobot_common.old_members_sheet
            )
            load_sheet_changes(
                self.banned_members, zerobot_common.banned_members_sheet
            )
            await warnings_from_sheet(self)
            # check if highest id states changed on sheet
            get_highest_ids(self)
        self.list_access["current_members"] = self.current_members
        self.list_access["old_members"] = self.old_members
        self.list_access["banned_members"] = self.banned_members
        return self.list_access
    async def unlock(self, skip_sheet = False):
        """
        Signals that you finished accessing and editing the memberlist.
        Writes the current version of the memberlist to drive / sheet.

        Revokes access to the memberlist by clearing the references from the
        dictionary. As long as the function calling lock() did not make copies
        of the references it will no longer be able to edit.

        Acts as an imperfect mutex, unlocks access to the spreadsheet to 
        prevent simultanious editing. 'Imperfect' as it's not purely atomic, 
        there could be an interrupt between checking self.updating and locking 
        it as true. Time between lock() and unlock() should be kept to a 
        minimum to prevent waiting time / having to resend commands.
        """
        self.list_access["current_members"] = None
        self.list_access["old_members"] = None
        self.list_access["banned_members"] = None

        memberlist_to_disk(
            self.current_members, zerobot_common.current_members_filename
        )
        memberlist_to_disk(
            self.old_members, zerobot_common.old_members_filename
        )
        memberlist_to_disk(
            self.banned_members, zerobot_common.banned_members_filename
        )

        if not skip_sheet and zerobot_common.sheet_memberlist_enabled:
            memberlist_to_sheet(
                self.current_members, zerobot_common.current_members_sheet
            )
            memberlist_to_sheet(
                self.old_members, zerobot_common.old_members_sheet
            )
            memberlist_to_sheet(
                self.banned_members, zerobot_common.banned_members_sheet
            )
        
        self.updating = False
    
    @commands.command()
    async def restart(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("restart", ctx.channel.id)
        ): return

        # TODO: create an internal restart that does not rely on the server 
        # restarting the python script. very tricky with scheduled tasks
        await self.bot.close()

    @commands.command()
    async def test(self, ctx, role: discord.Role):
        memberlog = LogFile("applications/log4", prefix = "MemberExport")
        await memberlog.log("\n".join(str(member.name) for member in role.members))
        await ctx.send("\n".join(str(member) for member in role.members))

    @commands.command()
    async def dropcomp(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        await ctx.send("https://forms.gle/GJP9kLSkhEKMhXRz9")
        


    @app_commands.command(
        name = "known_inactive", 
        description = (
            "Let the bot and others know that a member is expected "
            "to be inactive for a number of days"
        )
    )
    @app_commands.check(zerobot_common.is_staff_check)
    async def known_inactive(self, interaction: Interaction, member: discord.Member, days: int):
        """
        Sets a member as known inactive for a number of days.
        Only able to be used by staff members, in any channel.
        """
        # signal to discord that our response might take time
        await interaction.response.defer(ephemeral = False)
        logfile.log(
            f"{interaction.channel.name}:{interaction.user.name}:"
            f"slashcommand:known_inactive"
        )

        memblist = self.bot.get_cog("MemberlistCog")
        if memblist is None:
            await interaction.followup.send("zbot error: memberlist module not found.")
            logfile.log("known_inactive command failed, memberlist module not found")
            return
        
        list_access = await memblist.lock()

        memb = memberlist_get(list_access["current_members"], member.id)
        if memb is None:
            memb = memberlist_get(
                list_access["current_members"], member.display_name
            )
            if memb is None:
                await memblist.unlock()
                await interaction.followup.send(
                    f"No current member found in memberlist for "
                    f" {member.id}:{member.display_name}."
                )
                logfile.log("known_inactive command failed, member not found")
                return
        today_date = datetime.utcnow()
        newdate =  today_date + timedelta(days)
        memb.last_active = newdate

        await memblist.unlock()

        await interaction.followup.send(
            f"I have set the last active date of {memb.name} to {days} days "
            f"from now ({newdate.strftime(utilities.dateformat)}). They "
            f"will not show up on the inactives list until after this date."
        )
        logfile.log(
            f"known_inactive command successful, {memb.name} for {days} "
            f"until {newdate.strftime(utilities.dateformat)}"
        )
    @known_inactive.error
    async def known_inactive_error(self, interaction, error):
        logfile.log(
            f"known_inactive command attempt blocked, "
            f"{interaction.user.display_name} is not a staff member."
        )
        await interaction.response.send_message(
            f"Not Allowed ! Staff Members Only.", ephemeral = False
        )
    
    @app_commands.command(
        name = "remove_memberlist_entry",
        description = "Remove an entry from the memberlists using its unique entry id"
    )
    @app_commands.check(zerobot_common.is_staff_check)
    async def remove_memberlist_entry(self, interaction: Interaction, entry_id: int):
        """
        Removes a member from the memberlist by entry_id.
        Only able to be used by staff members, in any channel.
        """
        # signal to discord that our response might take time
        await interaction.response.defer(ephemeral = False)
        logfile.log(
            f"{interaction.channel.name}:{interaction.user.name}:"
            f"slashcommand:remove_memberlist_entry"
        )

        memblist = self.bot.get_cog("MemberlistCog")
        if memblist is None:
            await interaction.followup.send("zbot error: memberlist module not found.")
            logfile.log(
                "remove_memberlist_entry command failed, "
                "memberlist module not found"
            )
            return
        
        memb = await memblist.remove_entry(entry_id)
        if memb is None:
            await interaction.followup.send(
                f"Could not find {entry_id} on the memberlists"
            )
            logfile.log(
                f"remove_memberlist_entry command attempt failed, "
                f"{entry_id} not found on memberlists"
            )
        else:
            await interaction.followup.send(f"Removed {memb.name} from {memb.sheet}")
            logfile.log(
                f"remove_memberlist_entry command attempt successful, "
                f"Removed {memb.name} from {memb.sheet}."
            )
    @remove_memberlist_entry.error
    async def remove_memberlist_entry_error(self, interaction, error):
        logfile.log(
            f"remove_memberlist_entry command attempt blocked, "
            f"{interaction.user.display_name} is not a staff member."
        )
        await interaction.response.send_message(
            f"Not Allowed ! Staff Members Only.", ephemeral = False
        )
    
    @app_commands.command(
        name = "edit_member_id",
        description = "Set a new member id for a member"
    )
    @app_commands.check(zerobot_common.is_staff_check)
    @app_commands.default_permissions()
    async def edit_member_id(
        self,
        interaction: Interaction,
        old_member_id: int,
        new_member_id: int
    ):
        """
        Sets new_id as the id of all memberlist entries with id = current_id.
        Only able to be used by staff members, in any channel.
        """
        # signal to discord that our response might take time
        await interaction.response.defer(ephemeral = False)
        logfile.log(
            f"{interaction.channel.name}:{interaction.user.name}:"
            f"slashcommand:edit_member_id"
        )

        memblist = self.bot.get_cog("MemberlistCog")
        if memblist is None:
            await interaction.followup.send("zbot error: memberlist module not found.")
            logfile.log("edit_member_id command failed, memberlist module not found")
            return

        edits = await memblist.edit_id(old_member_id, new_member_id)
        if len(edits) == 0:
            await interaction.followup.send(
                f"Could not find {old_member_id} on the memberlists"
            )
            logfile.log(
                f"edit_member_id command attempt failed, "
                f"{old_member_id} not found on memberlists"
            )
        else:
            msg = (
                f"```{new_member_id} has been set as the new id for all "
                f"{len(edits)} entries of {old_member_id}:\n"
            )
            for n in edits:
                msg += f" {n[0]} : {n[1]}, entry {n[2]}\n"
            msg += "```"
            await interaction.followup.send(msg)
            logfile.log(
                f"edit_member_id command attempt successful, {old_member_id} "
                f"replaces {new_member_id} for {len(edits)} entries."
            )
    @edit_member_id.error
    async def edit_member_id_error(self, interaction, error):
        logfile.log(
            f"edit_member_id command attempt blocked, "
            f"{interaction.user.display_name} is not a staff member.")
        await interaction.response.send_message(
            f"Not Allowed ! Staff Members Only.", ephemeral = False
        )
    
    @app_commands.command(
        name = "host_stats",
        description = "Check your hosting stats in clan or add @someone to check theirs."
    )
    async def host_stats(self, interaction: Interaction, member: discord.Member):
        # log command attempt and check if command allowed
        logfile.log(
            f"{interaction.channel.name}:{interaction.user.name}:"
            f"slashcommand:host_stats"
        )
        if zerobot_common.permissions.not_allowed(
            "host_stats", interaction.channel.id
        ):
            await interaction.response.send("Not allowed in this channel.")
            return

        # signal to discord that our response might take time
        await interaction.response.defer()

        if member is None:
            msg = "Your hosting stats "
            member = interaction.user
        else:
            msg = f"Hosting stats of {member.display_name} "
        msg += "according to my information: ```"

        memblist = memberlist_from_disk(zerobot_common.current_members_filename)
        memb = memberlist_get(memblist, member.id)
        skip_listing = [
            "Nex Learner",
            "Raksha Learner",
            "Notify Dungeoneering Party",
        ]
        total = 0
        for type, num in memb.notify_stats.items():
            if type in skip_listing:
                continue
            msg += f"{type} : {num}\n"
            total += num
        events_started = memb.misc["events_started"]
        msg += f"\nevents started with -zbot host : {events_started}\n"
        total += events_started
        msg += f"\ntotal : {total}```\n"
            
        msg += (
            "(zbot only knows how often you used Notify Tags and "
            "the `-zbot host` command in the clan discord) "
        )
        await interaction.followup.send(msg)

    @commands.command()
    async def show_highest_ids(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("show_highest_ids", ctx.channel.id)
        ): return
        get_highest_ids(self)
        await ctx.send(
            f"current highest member id: {self.highest_id}\n"
            f"current highest entry id: {self.highest_entry_id}\n"
        )
    
    @commands.command()
    async def message(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("message", ctx.channel.id)
        ): return
        
        cmd_length = len("-zbot message ")
        # try to send to specific channel if first argument is an id
        if "channel:" in args[0]:
            try:
                chann_id = int(args[0][8:])
                channel = ctx.guild.get_channel(chann_id)
                msg = ctx.message.content[cmd_length+len(args[0])+1:]
                target = channel
            except Exception:
                msg = ctx.message.content[cmd_length:]
                target = ctx
        else:
            msg = ctx.message.content[cmd_length:]
            target = ctx
        
        # try to fill in nitro emojis
        res = ""
        for w in re.split("([^\w:])", msg):
            if len(w) > 2 and w[0] == ":" and w[len(w)-1] == ":":
                e_str = w[1:-1]
                try:
                    # if its a number, try finding emoji by id
                    emoji_id = int(e_str)
                    e = self.bot.get_emoji(emoji_id)
                    # None if not found = good
                    # shows mistake and prevents empty message
                    res += str(e)
                except Exception:
                    # if by number went wrong, try finding first match by name
                    for e in self.bot.emojis:
                        if e.name == e_str:
                            res += str(e)
                            break
                    # None if not found
                    res += "None"
            else:
                res += w
        await target.send(res)

    @commands.command()
    async def reload_data(self, ctx):
        """
        Very simple reload to get sheet changes.

        disk data is only loaded on bot startup, should not edit,
        maybe only when bot is down
        """
        await self.lock()
        await self.unlock()
        await ctx.send("Done")
    
    @commands.command()
    async def updatelist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("updatelist", ctx.channel.id)
        ): return

        # check if confirmed
        if self.confirmed_update:
            await daily_update(self)
            return
        # not confirmed yet, ask for confirm
        await ctx.send(
            "Fully updating the memberlist spreadsheet can take a long time! "
            "(~30 minutes!)\n The spreadsheet can not be edited while the "
            "update is running.\n If you are sure you want to start the "
            "update, type the command again within 30 seconds"
        )
        self.confirmed_update = True
        await asyncio.sleep(30)
        self.confirmed_update = False
    
    async def search_all(self, id):
        """
        Searches the disk version of the 3 memberlists for id.
        Can not be used to edit members. 
        Results may have outdated Discord roles / Site ranks / Ingame stats.
        """
        result = SearchResult()
        current_members = memberlist_from_disk(
            zerobot_common.current_members_filename
        )
        old_members = memberlist_from_disk(
            zerobot_common.old_members_filename
        )
        banned_members = memberlist_from_disk(
            zerobot_common.banned_members_filename
        )
        result.current_results = memberlist_get_all(current_members, id)
        result.old_results = memberlist_get_all(old_members, id)
        result.banned_results = memberlist_get_all(banned_members, id)
        for memb in result.current_results:
            memb.status = "Current Member"
        for memb in result.old_results:
            memb.status = "Retired Member"
        for memb in result.banned_results:
            memb.status = "\uD83D\uDE21 BANNED Member \U0001F621"
        return result

    async def search(self, name, discord_id, profile_link):
        """
        Tries to find any results in the memberlist and groups the results.
        Checks for name, discord id and profile link matches on the current,
        old and banned memberlists. Might include duplicates.
        """
        # find results for name matches (non-empty)
        if name == "" or name is None:
            name_results = SearchResult()
        else:
            name_results = await self.search_all(name)
        # find results for discord id matches (non-empty)
        if discord_id == 0 or discord_id is None:
            id_results = SearchResult()
        else:
            id_results = await self.search_all(discord_id)
        # find results for profile link matches (non-empty)
        if (
            profile_link == "" or 
            profile_link is None or 
            profile_link == "no site"
        ):
            link_results = SearchResult()
        else:
            link_results = await self.search_all(profile_link)
        return name_results + id_results + link_results
    
    @commands.command()
    async def refresh_banlist(self, ctx, *args):
        """
        Refreshes the banlist channel with new messages.
        """
        if zerobot_common.banlist_channel_id is None:
            await ctx.send("Banlist channel isnt set up in settings.json.")
            return
        channel = zerobot_common.guild.get_channel(
            zerobot_common.banlist_channel_id
        )
        await channel.purge()
        # fetch latest from sheet with lock -> unlock
        await self.lock()
        await self.unlock()
        # retrieve up to date, modifyable copy from disk
        mlist = memberlist_from_disk(zerobot_common.banned_members_filename)
        # sort last to leave first
        memberlist_sort_leave_date(mlist, asc=False)
        today = datetime.utcnow().strftime(utilities.dateformat)
        msg = (
            "**=== Zer0 PvM Banlist ===**\n\n"
            "We strongly suggest to NOT invite these people to pvm teams.\n"
            "We may also hold you responsible for any drama caused if you "
            "bring them into anything Zer0 related.\n\n"

            "This list only shows the 25 most recent Zer0 bans.\n"
            "The full Zer0 PvM banlist can be found here: "
            "<http://tiny.cc/Zer0PvMBanList>\n\n"
            f"Last Updated: {today}"
        )
        await channel.send(msg)
        messages = [
            "Name         |    Date    | Ban Reason\n",
            "----------------------------------------\n"
        ]
        for i in range(0, 25):
            memb = mlist[i]
            msg = memb.bannedInfo()
            if len(msg) > 140:
                index = msg.rfind(" ",0, 140)
                part1 = msg[0:index]
                part2 = "                           " + msg[index:len(msg)]
                msg = part1 + "\n" + part2
            messages.append(msg + "\n")
        await send_multiple(channel, messages, codeblock=True)
        msg = (
            "_ _\n"
            "Ban Lists from the other PvM Communities:\n"
            " - Raid FC Banlist  : <http://tiny.cc/raidfcbans>\n"
            " - AoD 7-10 Banlist : <http://tiny.cc/AoD7-10BanList>"
        )
        await channel.send(msg)
    
    @commands.command()
    async def find(self, ctx, *args):
        # alias for findmember, no checks needed here.
        await self.findmember(ctx, *args)

    @commands.command()
    async def findmember(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("findmember", ctx.channel.id)
        ): return

        use_msg = (
            "Needs to be : -zbot findmember id"
            "id: ingame name, discord_id or profile_link>"
        )
        if len(args) == 0:
            await ctx.send("Not enough arguments\n" + use_msg)
            return
        id = " ".join(args).lower()
        try:
            id = parse_discord_id(id)
        except Exception:
            pass
        try:
            id = parse_profile_link(id)
        except Exception:
            pass
        
        results = await self.search_all(id)
        if (len(results.combined_list()) == 0):
            await ctx.send("No results found in search.")
            return
        msg = (
            "Found these results, ingame stats may be outdated, "
            "info for those is from the last daily update:\n"
        )
        if (len(results.combined_list()) > 10):
            msg += (
                "Found more than 10 results, only showing the first 10:\n"
            )

        # get latest information
        update_discord_info(results.combined_list())
        if zerobot_common.site_enabled:
            zerobot_common.siteops.update_site_info(results.combined_list())
        await ctx.send(msg)

        for memb in results.combined_list()[:10]:
            # no role, or did not have / dont know their discord.
            if (
                memb.discord_id == 0 or 
                memb.discord_name == "Left clan discord"
            ):
                memb.discord_rank = ""
            await ctx.send(embed=member_embed(memb))
    
    @commands.command()
    async def checkdupes(self, ctx):
        await warn_duplicates(self)
    
    async def remove_entry(self, entry_id):
        """
        Removes an entry from the memberlists.
        Returns the member entry if found, otherwise None.
        """
        await self.lock()
        for m in self.current_members:
            if m.entry_id == entry_id:
                self.current_members.remove(m)
                await self.unlock()
                m.sheet = "current_members"
                return m
        for m in self.old_members:
            if m.entry_id == entry_id:
                self.old_members.remove(m)
                await self.unlock()
                m.sheet = "old_members"
                return m
        for m in self.banned_members:
            if m.entry_id == entry_id:
                self.banned_members.remove(m)
                await self.unlock()
                m.sheet = "banned_members"
                return m
        return None
    
    async def edit_id(self, current_id, new_id):
        """
        Sets new_id as the id of all memberlist entries with id = current_id.
        """
        await self.lock()
        edits = []
        for m in self.current_members:
            if m.id == current_id:
                m.id = new_id
                edits.append(("current_members", m.name, m.entry_id))
        for m in self.old_members:
            if m.id == current_id:
                m.id = new_id
                edits.append(("old_members", m.name, m.entry_id))
        for m in self.banned_members:
            if m.id == current_id:
                m.id = new_id
                edits.append(("banned_members", m.name, m.entry_id))
        if new_id > self.highest_id:
            self.highest_id = new_id
        await self.unlock()
        return edits
    
    @commands.command()
    async def removemember(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed(
                "removemember", ctx.channel.id
            )
        ): return

        use_msg = (
            "Needs to be : -zbot removemember list_name member_id\n"
            " - list_name: current_members, old_members or banned_members\n"
            " - member_id: name, profile_link or discord_id"
        )
        if len(args) != 2:
            await ctx.send(use_msg)
            return
        list_names = ["current_members", "old_members", "banned_members"]
        if not args[0] in list_names:
            await ctx.send(use_msg)
            return
        id = " ".join(args[1:]).lower()
        try:
            id = parse_discord_id(id)
        except Exception:
            pass
        try:
            id = parse_profile_link(id)
        except Exception:
            pass
        
        list_access = await self.lock()
        memb = memberlist_remove(list_access[args[0]], id)
        await self.unlock()

        if memb is None:
            await ctx.send(f"No member found for {id} in {args[0]}.")
            return
        await ctx.send(f"Removed {memb.name} from {args[0]}.")
    
    @commands.command()
    async def movemember(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("movemember", ctx.channel.id)
        ): return

        use_msg = (
            "Needs to be : -zbot movemember from_list to_list member_id\n"
            " - from_list / to_list: current_members, old_members or "
            "banned_members\n"
            " - member_id: name, profile_link or discord_id"
        )
        if len(args) != 3:
            await ctx.send(use_msg)
            return
        list_names = ["current_members", "old_members", "banned_members"]
        if not args[0] in list_names:
            await ctx.send(use_msg)
            return
        if not args[1] in list_names:
            await ctx.send(use_msg)
            return
        id = " ".join(args[2:]).lower()
        try:
            id = parse_discord_id(id)
        except Exception:
            pass
        try:
            id = parse_profile_link(id)
        except Exception:
            pass
        
        list_access = await self.lock()
        memb = memberlist_move(list_access[args[0]], list_access[args[1]], id)
        await self.unlock()

        if memb is None:
            await ctx.send(f"No member found for {id} in {args[0]}.")
            return
        await ctx.send(f"Moved {memb.name} from {args[0]} to {args[1]}.")
    
    @commands.command()
    async def edit(self, ctx, *args):
        await self.editmember(ctx, *args)
    @commands.command()
    async def editmember(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
            )
        if not(
            zerobot_common.permissions.is_allowed("editmember", ctx.channel.id)
        ): return

        use_msg = (
            "Needs to be : -zbot editmember list_name member_id attribute = "
            "value\n"
            " - list_name: current_members, old_members or banned_members\n"
            " - member_id: a valid name, profile_link or discord_id\n"
            " - attribute: name, profile_link, discord_id\n"
        )

        # check if command uses the correct form
        if len(args) != 5 :
            await ctx.send(use_msg)
            return
        list_names = ["current_members", "old_members", "banned_members"]
        if not args[0] in list_names:
            await ctx.send(use_msg)
            return
        if (args[3] != "="):
            await ctx.send(use_msg)
            return
        # check if attribute to edit is valid. ugly but effective, I want to 
        # do this before I spend time finding the member, without keeping a 
        # separate list of valid attributes, so the goal is to check if a 
        # class instance will be given an attribute when made. afaik there is 
        # no python model that lets me predefine / check the existence of a 
        # class instance's attributes but this works the same.
        attribute = args[2]
        dummy_member = Member("","",0,0)
        try:
            getattr(dummy_member, attribute)
        except AttributeError:
            await ctx.send(
                f"{attribute} is not a valid attribute you can change\n"
                f"{use_msg}"
            )
            return
        
        # check if new value for attribute is valid
        new_value = args[4]
        if (attribute == "discord_id"):
            # allow "0" as explicit exception for unknown discord id
            if (new_value == "0"):
                new_value = 0
            else:
                try:
                    new_value = parse_discord_id(new_value)
                except NotADiscordId:
                    await ctx.send(f"{new_value} is not a valid discord id")
                    return
        if (attribute == "profile_link"):
            # allow "no site" as explicit exception for unknown profile link
            if (new_value.lower() == "no site"):
                new_value = "no site"
            else:
                try:
                    new_value = parse_profile_link(new_value)
                except NotAProfileLink:
                    await ctx.send(f"{new_value} is not a valid profile link")
                    return

        id = (args[1]).lower()
        try:
            id = parse_discord_id(id)
        except Exception:
            pass
        try:
            id = parse_profile_link(id)
        except Exception:
            pass
        
        list_access = await self.lock()
        memb = memberlist_get(list_access[args[0]], id)
        if memb is not None:
            old_value = getattr(memb, attribute)
            setattr(memb, attribute, new_value)
            # also update old names if changing name
            if attribute == "name":
                if new_value in memb.old_names:
                    memb.old_names.remove(new_value)
                if not old_value in memb.old_names:
                    memb.old_names.append(old_value)
            # verify highest id state if changing id
            if attribute == "id":
                if new_value > self.highest_id:
                    self.highest_id = new_value
            if attribute == "entry_id":
                if new_value > self.highest_entry_id:
                    self.highest_entry_id = new_value
        await self.unlock()

        if memb is None:
            await ctx.send(f"No member found for {id} in {args[0]}.")
            return
        await ctx.send(
            f"Edited {attribute} of {memb.name} from "
            f"{old_value} to {new_value}."
        )

    @commands.command()
    async def todos(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("todos", ctx.channel.id)
        ): return

        memberlist = memberlist_from_disk(
            zerobot_common.current_members_filename
        )
        await ctx.send(
            "Gathering latest info, takes a minute, "
            "ingame ranks only update daily and might be outdated"
        )
        result = await self.bot.loop.run_in_executor(
            None, Todos, memberlist, *args
        )
        await send_multiple(ctx, result)
    
    @commands.command()
    async def inactives(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if zerobot_common.permissions.not_allowed("inactives", ctx.channel.id):
            return
        use_msg = (
            "Shows a list of currently inactive members. "
            "\n `zbot inactives <number_of_days> <max_amount>`"
            "\nnumber_of_days : optional, minimum days inactive before being on"
            " the list. default is 30."
            "\nmax_amount : optional, max number of people to show. default is "
            "to show all."
        )
        days = 30
        number = None
        if len(args) > 0:
            try:
                days = int(args[0])
            except ValueError:
                await ctx.send(
                    "number_of_days has to be a number!\n" + use_msg
                )
                return
        if len(args) > 1:
            try:
                number = int(args[1])
            except ValueError:
                await ctx.send("max_amount has to be a number!\n" + use_msg)
                return
        if len(args) > 2:
            await ctx.send(
                f"{len(args)} arguments added, only using first 2\n" + use_msg
            )
        
        await self.post_inactives(ctx, days, number)
        await self.post_need_full_reqs(ctx)
    
    async def post_need_full_reqs(self, ctx):
        """
        Posts a list of members who should have the full member rank by now.
        """
        pre_msg = [(
            "These new members have been in the clan for more than 3 months "
            "and have not shown the full member reqs yet:\n\n"
        )]
        post_msg = (
            "\nThis means they are at risk of being removed for inactivity if "
            "there is not enough clan space for new members.\n"
        )
        need_full = await self.bot.loop.run_in_executor(
            None, _Need_Full_Reqs
        )
        res = (
            pre_msg
            + list(map(need_full_req_formatter, need_full))
            + [post_msg]
        )
        await send_multiple(ctx, res, codeblock=True)
        
    async def post_inactives(self, ctx, days=30, num_of_inactives=None):
        """
        Posts a list of currently inactive members to the specified context.
            - days_inactive: minimum days without activity to show up in list.
            - number_of_inactives: how many to post, sorted by least active.
        """
        # get already sorted list of inactives, keep first n, format as line
        inactvs = await self.bot.loop.run_in_executor(
            None, _Inactives, days
        )
        if num_of_inactives:
            inactvs = inactvs[:num_of_inactives]
        inactvs = list(map(lambda memb: memb.inactiveInfo() + "\n", inactvs))
        #create pre msg and header, squish lines into as few msgs as possible
        pre_msg = [(
            f"These members have been inactive for {days} or more days: \n\n"
        )]
        post_msg = [(
            "\nThis means they are at risk of being removed for inactivity if "
            "there is not enough clan space for new members.\n"
        )]
        header = [(
            "Name         Rank              Join Date  Clan xp    Last "
            "Active  Site Profile Link                   Discord Name   \n"
        )]
        res = (pre_msg + header + inactvs + post_msg)
        # send result in codeblock for looks
        await send_multiple(ctx, res, codeblock=True)
    
    @commands.command()
    async def exceptions(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("exceptions", ctx.channel.id)
        ) : return

        msg = "```Ingame name - Reason\n"
        for k,v in zerobot_common.inactive_exceptions.items():
            msg += (
                f"{k} - {v}\n"
            )
        msg += "```"
        await ctx.send(msg)
    
    @commands.command()
    async def welcome(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("welcome", ctx.channel.id)
        ) : return

        if len(args) == 1 and args[0] == "me":
            await send_messages(
                ctx.author,
                f"application_templates/welcome_messages.json"
            )
        else:
            await send_messages(
                None,
                f"application_templates/welcome_messages.json",
                alt_ctx=ctx.channel
            )

    @commands.command()
    async def banlist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("banlist", ctx.channel.id)
        ) : return

        memberlist = memberlist_from_disk(
            zerobot_common.banned_members_filename
        )

        res = ["Name         | Ban reason\n", "-------------------------\n"]
        for memb in memberlist:
            res.append(memb.bannedInfo() + "\n")
        await send_multiple(ctx, res, codeblock=True)
    
    async def background_check_app(self, ctx, app):
        """
        Runs a background check on the application, matches found are posted
        to the provided context (channel or user).

        Raises BannedUserError when there is matching info on the banlist.
        Raises ExistingUserWarning when matches found outside bans.
        """
        name = app.fields_dict["name"]
        discord_id = app.fields_dict["requester_id"]
        profile_link = app.fields_dict["profile_link"]
        await self.background_check(ctx, name, discord_id, profile_link)

    async def background_check(self, ctx, name, discord_id, profile_link):
        """
        Runs a background check on the user, matches found are posted
        to the provided context (channel or user).

        Raises BannedUserError when there is matching info on the banlist.
        Raises ExistingUserWarning when matches found outside bans.
        """
        search_result = await self.search(
            name, discord_id, profile_link
        )

        # if result in bans, post results and refuse to add
        if (search_result.has_ban()):
            for memb in search_result.banned_results:
                if (
                    memb.discord_id == 0 or 
                    memb.discord_name == "Left clan discord" or 
                    memb.discord_name == "Not in clan discord"
                ):
                    memb.discord_rank = ""
                if (memb.profile_link == "no site"):
                    memb.site_rank = ""
                await ctx.send(embed=member_embed(memb))
            raise BannedUserError("This person is banned.")
        
        # if already known as member some other way, just post results, 
        # warn that they might need a check and continue adding
        if (search_result.has_result()):
            for memb in search_result.combined_list():
                if (
                    memb.discord_id == 0 or 
                    memb.discord_name == "Left clan discord" or 
                    memb.discord_name == "Not in clan discord"
                ):
                    memb.discord_rank = ""
                if (memb.profile_link == "no site"):
                    memb.site_rank = ""
                await ctx.send(embed=member_embed(memb))
            raise ExistingUserWarning("This person was a member before")

    async def add_member_app(self, ctx, app):
        """
        Adds the member from the application to the memberlist.
        """
        name = app.fields_dict["name"]
        discord_id = app.fields_dict["requester_id"]
        profile_link = app.fields_dict["profile_link"]
        await self.add_member(ctx, name, discord_id, profile_link)

    async def add_member(self, ctx, name, discord_id, profile_link):
        """
        Adds a member's information to the memberlist.
        """
        # critical section, editing spreadsheet
        list_access = await self.lock()

        currentDT = datetime.utcnow()
        today_str = currentDT.strftime(utilities.dateformat)
        new_member = Member(name, "needs invite", 0, 0)
        if valid_discord_id(discord_id):
            new_member.discord_rank = "Recruit"
        else:
            new_member.discord_rank = ""
        if valid_profile_link(profile_link):
            new_member.site_rank = "Recruit"
        else:
            new_member.site_rank = ""
        new_member.profile_link = profile_link
        new_member.discord_id = discord_id
        new_member.join_date = today_str
        new_member.last_active = currentDT
        # set member id and increment state
        new_member.id = self.highest_id + 1
        self.highest_id += 1
        new_member.entry_id = self.highest_entry_id + 1
        self.highest_entry_id += 1
        list_access["current_members"].append(new_member)

        # finished with updating, can release lock
        await self.unlock()

    async def removeroles(self, member):
        """
        Removes any ranked roles below staff rank, removes clan member role
        and assigns the guest role afterwards. They keep other roles.
        """
        discord_id = member.discord_id
        if not valid_discord_id(discord_id):
            await zerobot_common.bot_channel.send(
                f"Could not remove roles for {member.name}, "
                f"not a valid discord id: {discord_id}"
            )
            return
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await zerobot_common.bot_channel.send(
                f"Could not remove roles for {member.name}, "
                f"discord id: {discord_id} does not exist or "
                f"is not a member of the Zer0 Discord."
            )
            return
        
        # Remove clan member role and ranked roles below staff
        roles_to_remove = zerobot_common.get_lower_ranks(
            discord_user, zerobot_common.staff_rank_index
        )
        clan_member_role = zerobot_common.guild.get_role(
            zerobot_common.clan_member_role_id
        )
        roles_to_remove.append(clan_member_role)
        await discord_user.remove_roles(*roles_to_remove, reason="left clan")
        # add guest role
        guest_role_id = zerobot_common.guest_role_id
        guest_role = zerobot_common.guild.get_role(guest_role_id)
        await discord_user.add_roles(guest_role, reason="left clan")
        member.discord_rank = "Guest"

    @commands.command()
    async def respond(self, ctx):
        # log command attempt, allowed everwhere
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )

        await ctx.send("Hello nbr <@358480624480419840>!")

        self.logfile.log(
            f"responded with hello in {ctx.channel.name}: {ctx.channel.id} "
        )
    
    @commands.command()
    async def activity(self, ctx, *args):
        """
        Tells you your activity status.
        """
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("activity", ctx.channel.id)
        ) : return

        if len(args) == 0:
            id = ctx.author.id
        else:
            id = " ".join(args).lower()
            try:
                id = parse_discord_id(id)
            except Exception:
                pass
            try:
                id = parse_profile_link(id)
            except Exception:
                pass
        memb = memberlist_get(self.current_members, id)
        if memb is None:
            await ctx.send(f"Could not find {id} on the memberlist!")

        today = datetime.utcnow()
        inactive_date = today - memb.last_active
        inactive_datestr = memb.last_active.strftime(utilities.dateformat)
        days_inactive = inactive_date.days
        max_days = zerobot_common.inactive_days
        inactive = days_inactive > max_days
        if inactive:
            status = (
                f"{memb.name} is on our list of inactive members! "
                "** And risks getting kicked for inactivity!**\n"
            )
            resp = (
                "To be removed from the inactives list: Get skill xp, "
                "wildy kills, runescore, do clues, rename, or ask a staff "
                "member.\n"
            )
        else:
            status = f"{memb.name} is not on our list of inactive members. "
            resp = (
                f"{memb.name} has {max_days - days_inactive} "
                f"days left before we consider them inactive.\n"
                f"If {memb.name} will be away for longer than that and wants "
                f"to avoid inactivity kicks, tell a staff member.\n"
            )

        res = (
            f"{status}"
            f"{memb.name} was last active ingame {days_inactive} days ago on "
            f"{inactive_datestr}.\n{resp}\n"
            f"Anyone inactive for more than {max_days} "
            f"days may be kicked when we need to make space for new members. "
            f"Lower ranks / newer members in clan are first up, so stay "
            f"active or rankup in clan!"
        )
        await ctx.send(res)
    
    @commands.command()
    async def clanstats(self, ctx, *args):
        """
        Shows recent stats of the clan by comparing with old memberlist.
        """
        # log command attempt and check if command allowed
        self.logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if not(
            zerobot_common.permissions.is_allowed("clanstats", ctx.channel.id)
        ) : return

        # check if command has correct number of arguments
        use_msg = (
            "usage: "
            "`-zbot clanstats`"
            "    shows clan stats from last 30 days"
            "`-zbot clanstats <days>`"
            "    days = a number, shows clan stats since <days> ago"
            "`-zbot clanstats <date>`"
            "    date = a date in yyyy-mm-dd format! (example: 2020-12-28)"
            "    shows clan stats since <date>"
            "`-zbot clanstats <date_1> <date_2>`"
            "    date = a date in yyyy-mm-dd format! (example: 2020-12-28)"
            "    shows clan stats since between <date_1> and <date_2>"
        )
        today_date = datetime.utcnow()
        date_1 = None
        date_2 = None
        if len(args) > 2:
            await ctx.send("Too many arguments!\n" + use_msg)
            return
        if len(args) == 0:
            date_1 = datetime.utcnow() - timedelta(days=30)
        if len(args) == 1:
            try:
                # try parse as x days ago
                try:
                    days = int(args[0])
                    date_1 = datetime.utcnow() - timedelta(days=days)
                except ValueError:
                    # try parse as date instead
                    date_1 = datetime.strptime(args[0], utilities.dateformat)
            except ValueError:
                # neither parsed successfully
                await ctx.send(f"Incorrect dateformat: {args[0]}\n" + use_msg)
                return
        if len(args) == 2:
            try:
                # try to parse as date
                date_1 = datetime.strptime(args[0], utilities.dateformat)
                date_2 = datetime.strptime(args[1], utilities.dateformat)
            except ValueError:
                # one of the dates did not parse successfully
                await ctx.send(
                    f"Incorrect dateformat: {args[0]} {args[1]}\n" + use_msg
                )
                return
        date_string_1 = date_1.strftime(utilities.dateformat)
        base_memblist_name = "memberlists/current_members/current_membs_"
        oldlist_filename = base_memblist_name + date_string_1 + ".txt"
        # load disk versions to guarantee safe comparison
        oldlist = memberlist_from_disk(oldlist_filename)
        if len(oldlist) == 0:
            await ctx.send(f"No archived memberlist found for {date_string_1}")
            return
        if len(args) == 2:
            date_string_2 = date_2.strftime(utilities.dateformat)
            newlist_filename = base_memblist_name + date_string_2 + ".txt"
            newlist = memberlist_from_disk(newlist_filename)
            if len(newlist) == 0:
                await ctx.send(
                    f"No archived memberlist found for {date_string_2}"
                )
                return
        else:
            newlist = memberlist_from_disk("memberlists/current_members.txt")
        if len(args) == 2:
            stat_range = f"between {date_string_1} and {date_string_2}"
        else:
            stat_range = f"since {date_string_1}"
        current_size = len(newlist)
        comp_res = memberlist_compare_stats(newlist, oldlist)
        stats = comp_res.staying
        # count non-zer0 discord ids, or count 'clan_member' tags
        clan_member_role = zerobot_common.get_named_role("Clan Member")
        membs_on_discord = len(clan_member_role.members)
        total_on_disc = zerobot_common.guild.member_count

        memberlist.memberlist_sort(stats, memberlist.hosts_cond, asc=False)
        top10hosts = "**Most active hosts:**\n"
        for i in range(0,10):
            total = 0
            for x in stats[i].notify_stats.values():
                total += x
            top10hosts += f"{stats[i].name} : {total}\n"


        memberlist.memberlist_sort(stats, memberlist.clan_xp_cond, asc=False)
        top10xp = "**Most xp gained:**\n"
        for i in range(0,10):
            top10xp += f"{stats[i].name} : {stats[i].clan_xp}\n"
        
        memberlist.memberlist_sort(stats, memberlist.clues_cond, asc=False)
        top10clues = f"**Most clues done {stat_range}:**\n"
        for i in range(0,10):
            top10clues += f"{stats[i].name} : {stats[i].total_clues()}\n"
        
        memberlist.memberlist_sort(stats, memberlist.runescore_cond, asc=False)
        top10runescore = f"**Most runescore gained:**\n"
        for i in range(0,10):
            top10runescore += (
                f"{stats[i].name} : {stats[i].activities['runescore'][1]}\n"
            )
        
        memberlist.memberlist_sort(stats, memberlist.wildykills_cond, asc=False)
        top10pks = f"**Most Wildy PKs:**\n"
        for i in range(0,10):
            top10pks += f"{stats[i].name} : {stats[i].kills}\n"

        #TODO inactives between dates, so can do between and not just since
        days_diff = (today_date - date_1).days
        inactives = _Inactives(days_diff)

        embed = discord.Embed()
        embed.set_author(
            name = f"{zerobot_common.guild.name} stats {stat_range}",
            icon_url = zerobot_common.guild.icon_url)
        embed.description = (
            f"Current clan Members: {current_size}\n"
            f"Clan members on discord: {membs_on_discord}\n"
            f"Total users on discord: {total_on_disc}\n"
            f"{len(comp_res.joining)} members joined {stat_range}\n"
            f"{len(comp_res.leaving)} members left {stat_range}\n"
            f"{len(comp_res.renamed)} members renamed {stat_range}\n"
            f"{len(inactives)} members inactive since {date_string_1}\n"
            f"\n"
            f"{top10hosts}"
            f"\n"
            f"{top10xp}"
            f"\n"
            f"{top10clues}"
            f"\n"
            f"{top10runescore}"
            f"\n"
            f"{top10pks}"
        )
        await ctx.send(embed=embed)
        inactives_str = (
            f"Members that are inactive ingame since {date_string_1}: "
            f"{len(inactives)}\n If you are near the top of this list it is "
            f"very likely that you will get kicked when we need to make space "
            f"for new members:\n"
        )
        inactives_str += (
            "Name         Rank              Join Date  Clan xp    Last "
            "Active  Site Profile Link                   Discord Name   \n"
        )
        for memb in inactives:
            inactives_str += f"{memb.inactiveInfo()}\n"
        
        new_membs = f"{len(comp_res.joining)} members joined {stat_range}:\n"
        for memb in comp_res.joining:
            new_membs += f" {memb.name},"
        new_membs = new_membs[:-1]
        left_membs = f"{len(comp_res.leaving)} members left {stat_range}:\n"
        for memb in comp_res.leaving:
            left_membs += f" {memb.name},"
        renamed_membs = f"{len(comp_res.renamed)} members renamed {stat_range}:"
        for memb in comp_res.renamed:
            renamed_membs += f"\n - {memb.name} = {memb.old_names[0]}"
        
        changed_ranks = []
        for memb in stats:
            if memb.old_rank != memb.new_rank:
                changed_ranks.append(memb)
        changed_ranks_str = (
            f"{len(changed_ranks)} members changed rank {stat_range}:"
        )
        for memb in changed_ranks:
            changed_ranks_str += (
                f"\n - {memb.name}: {memb.old_rank} -> {memb.new_rank}"
            )
        changed_dpm = []
        for memb in stats:
            memb.mage_change = ""
            memb.melee_change = ""
            memb.range_change = ""
            changed = False
            if memb.new_misc["highest_mage"] != memb.old_misc["highest_mage"]:
                if memb.new_misc["highest_mage"] == "":
                    memb.mage_change = (
                        f"Lost {memb.old_misc['highest_mage']}"
                    )
                elif memb.old_misc["highest_mage"] == "":
                    memb.mage_change = (
                        f"Gained {memb.new_misc['highest_mage']}"
                    )
                else:
                    memb.mage_change = (
                        f"{memb.old_misc['highest_mage']} -> "
                        f"{memb.new_misc['highest_mage']}"
                    )
                changed = True
            if memb.new_misc["highest_melee"] != memb.old_misc["highest_melee"]:
                if memb.new_misc["highest_melee"] == "":
                    memb.melee_change = (
                        f"Lost {memb.old_misc['highest_melee']}"
                    )
                elif memb.old_misc["highest_melee"] == "":
                    memb.melee_change = (
                        f"Gained {memb.new_misc['highest_melee']}"
                    )
                else:
                    memb.melee_change = (
                        f"{memb.old_misc['highest_melee']} -> "
                        f"{memb.new_misc['highest_melee']}"
                    )
                changed = True
            if memb.new_misc["highest_range"] != memb.old_misc["highest_range"]:
                if memb.new_misc["highest_range"] == "":
                    memb.range_change = (
                        f"Lost {memb.old_misc['highest_range']}"
                    )
                elif memb.old_misc["highest_range"] == "":
                    memb.range_change = (
                        f"Gained {memb.new_misc['highest_range']}"
                    )
                else:
                    memb.range_change = (
                        f"{memb.old_misc['highest_range']} -> "
                        f"{memb.new_misc['highest_range']}"
                    )
                changed = True
            if changed:
                changed_dpm.append(memb)
        changed_dpm_str = (
            f"{len(changed_dpm)} members changed dpm {stat_range}:"
        )
        for memb in changed_dpm:
            changed_dpm_str += (
                f"\n - {memb.name}: {memb.mage_change}    "
                f"{memb.melee_change}    {memb.range_change}"
            )
        changed_tags = []
        for memb in stats:
            changed = False
            memb.new_tags = []
            for id in memb.new_misc["discord_roles"]:
                if not id in memb.old_misc["discord_roles"]:
                    role = zerobot_common.guild.get_role(id)
                    if role is None:
                        memb.new_tags.append("deleted-role")
                    else:
                        memb.new_tags.append(role.name)
                    changed = True
            memb.lost_tags = []
            for id in memb.old_misc["discord_roles"]:
                if not id in memb.new_misc["discord_roles"]:
                    role = zerobot_common.guild.get_role(id)
                    if role is None:
                        memb.lost_tags.append("deleted-role")
                    else:
                        memb.lost_tags.append(role.name)
                    changed = True
            if changed:
                changed_tags.append(memb)
        changed_tags_str = (
            f"{len(changed_tags)} members changed discord tags {stat_range}:"
        )
        for memb in changed_tags:
            changed_tags_str += f"\n - {memb.name}"
            if len(memb.new_tags) != 0:
                changed_tags_str += (
                    f"\n    New Tags: {','.join(memb.new_tags)}"
                )
            if len(memb.lost_tags) != 0:
                changed_tags_str += (
                    f"\n    Lost Tags: {','.join(memb.lost_tags)}"
                )

        stats_str = (
            f"{new_membs}\n"
            f"\n"
            f"{left_membs}\n"
            f"\n"
            f"{renamed_membs}\n"
            f"\n"
            f"{inactives_str}"
            f"\n"
            f"{changed_ranks_str}\n"
            f"\n"
            f"{changed_dpm_str}\n"
            f"\n"
            f"{changed_tags_str}\n"
        )
        wrapped = stats_str.splitlines()
        for num, l in enumerate(wrapped):
            wrapped[num] = textwrap.fill(l, width=125)
        stats_str = "\n".join(wrapped)
        f = io.StringIO(stats_str)
        disc_file = discord.File(f, "clanstats.txt")
        await ctx.send(content="More clan statistics:", file=disc_file)