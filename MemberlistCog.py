"""
Bot module for all the memberlist modifying functions. Also includes the 
scheduled daily update.

How to safely edit the memberlist:
 - access the instance of this module with bot.get_cog('MemberlistCog')
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
import discord
import time
from datetime import datetime, timedelta
from logfile import LogFile
import asyncio
# custom modules
import zerobot_common
import utilities

from utilities import send_messages
from sheet_ops import start_update_warnings, clear_sheets, print_update_in_progress_warnings, color_spreadsheet, load_sheet_changes, memberlist_to_sheet, warnings_from_sheet
from rankchecks import Todos, TodosInviteIngame, TodosJoinDiscord, TodosUpdateRanks, update_discord_info, parse_discord_rank
from clantrack import get_ingame_memberlist, compare_lists
from searchresult import SearchResult
from memberembed import member_embed
import memberlist
from memberlist import memberlist_sort_name, memberlist_sort_clan_xp, memberlist_sort_leave_date, memberlist_from_disk, memberlist_to_disk, memberlist_get, memberlist_remove, memberlist_move, memberlist_get_all, memberlist_compare_stats
from member import Member, valid_discord_id, valid_profile_link, notify_role_names
from exceptions import BannedUserError, ExistingUserWarning, MemberNotFoundError, NotACurrentMemberError, StaffMemberError, NotADiscordId, NotAProfileLink

# logfile for clantrack
memberlist_log = LogFile('logs/memberlist')

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
        if (memb.name in zerobot_common.inactive_exceptions.keys()):
            continue
        if (memb.last_active == None):
            days_inactive = today - datetime.strptime("2020-04-14", utilities.dateformat)
            memb.last_active = datetime.strptime("2020-04-14", utilities.dateformat)
        else:
            days_inactive = today - memb.last_active
        if (days_inactive.days >= days):
            memb.days_inactive = days_inactive.days
            results.append(memb)
    
    memberlist_sort_clan_xp(results)
    return results
    
async def send_multiple(ctx, str_list, codeblock=False):
    """
    Splits up a list of messages and sends them in batches.
    Right now just does it in a dumb way, 20 strings at a time without checking length.
    """
    for i in range(0, len(str_list), 20):
        message = ""
        if (codeblock):
            message += "```"
        for index in range(i, i+20):
            if (index == len(str_list)): break
            message += str_list[index]
        if (codeblock):
            message += "```"
        await ctx.send(message)


@tasks.loop(hours=23, reconnect=False)
async def daily_update_scheduler(self):
    """
    Schedules the daily updates at the time specified in settings.
    """
    # wait remaining time until update after 23h task loop wakes up
    update_time_str = zerobot_common.settings.get("daily_update_time")
    update_time = datetime.strptime(update_time_str, utilities.timeformat)
    wait_time = update_time - datetime.utcnow()
    memberlist_log.log(f'auto_upd in {wait_time.seconds/3600}h')
    # async sleep to be able to do other stuff until update time
    await asyncio.sleep(wait_time.seconds)
    await daily_update(self)

async def warn_duplicates(self):
    dupes = ["duplicates in memberlists:\n"]
    for memb in self.current_members:
        dupe = memberlist_get(self.old_members, memb.discord_id)
        if dupe is not None:
            dupes.append(f"current: {memb.name} old: {dupe.name}\n")
        dupe = memberlist_get(self.banned_members, memb.discord_id)
        if dupe is not None:
            dupes.append(f"current: {memb.name} bannned: {dupe.name}\n")
    for memb in self.old_members:
        dupe = memberlist_get(self.current_members, memb.discord_id)
        if dupe is not None:
            dupes.append(f"old: {memb.name} current: {dupe.name}\n")
        dupe = memberlist_get(self.banned_members, memb.discord_id)
        if dupe is not None:
            dupes.append(f"old: {memb.name} bannned: {dupe.name}\n")
    for memb in self.banned_members:
        dupe = memberlist_get(self.current_members, memb.discord_id)
        if dupe is not None:
            dupes.append(f"banned: {memb.name} current: {dupe.name}\n")
        dupe = memberlist_get(self.old_members, memb.discord_id)
        if dupe is not None:
            dupes.append(f"banned: {memb.name} old: {dupe.name}\n")
    if len(dupes) == 1:
        dupes.append("No duplicates found.")
    await send_multiple(zerobot_common.bot_channel, dupes, codeblock=True)


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
    await zerobot_common.bot_channel.send("Starting to collect ingame data for update")

    # retrieve the latest ingame data as a new concurrent ask
    ingame_members = await self.bot.loop.run_in_executor(
        None, get_ingame_memberlist
    )
    # backup ingame members right away, nice for testing
    date_str = datetime.utcnow().strftime(utilities.dateformat)
    ing_backup_name = "memberlists/current_members/ingame_membs_" + date_str + ".txt"
    memberlist_to_disk(ingame_members, ing_backup_name)
    
    # start posting update warnings on spreadsheet
    await zerobot_common.bot_channel.send("Daily update starting in 5 minutes")
    if zerobot_common.sheet_memberlist_enabled:
        await self.bot.loop.run_in_executor(None, start_update_warnings)

    #=== try to obtain editing lock, loads sheet changes ===
    await self.lock()
    if zerobot_common.sheet_memberlist_enabled:
        clear_sheets()
        print_update_in_progress_warnings()
    # compare against new ingame data to find joins, leaves, renames
    comp_res = compare_lists(ingame_members, self.current_members)
    # use result to update our list of current members
    self.current_members = comp_res.staying + comp_res.joining + comp_res.renamed
    # get site updates, send list to siteops func that updates it
    update_discord_info(self.current_members)
    self.logfile.log("retrieved discord user changes...")
    if zerobot_common.site_enabled:
        zerobot_common.siteops.update_site_info(self.current_members)
    self.logfile.log("retrieved site user changes...")
    # for leaving members remove discord roles, set site rank to retired
    await process_leaving(self, comp_res.leaving)
    self.logfile.log("updated discord accounts of leaving members...")

    # sort updated lists
    memberlist_sort_name(self.current_members)
    memberlist_sort_name(self.old_members)
    memberlist_sort_name(self.banned_members)
    # check memberlists for duplicate discord ids
    await warn_duplicates(self)
    self.logfile.log("checked the memberlists for duplicates...")

    # write updated memberlists to disk as backup
    cur_backup_name = "memberlists/current_members/current_membs_" + date_str + ".txt"
    old_backup_name = "memberlists/old_members/old_membs_" + date_str + ".txt"
    ban_backup_name = "memberlists/banned_members/banned_membs_" + date_str + ".txt"
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
    await send_multiple(zerobot_common.bot_channel, to_update_rank)
    
async def process_leaving(self, leaving_list):
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
    
    today_date = datetime.utcnow().strftime(utilities.dateformat)
    for memb in leaving_list:
        self.logfile.log(f" - {memb.name} is leaving, updating discord and site ranks...")
        rank_index = utilities.rank_index(discord_role_name=memb.discord_rank)
        if rank_index is None:
            await zerobot_common.bot_channel.send(
                f"Unknown rank for leaving member: {memb.name}, skipped for "
                "automatic rank removal. You will have to update their "
                "discord roles and site rank manually."
            )
            continue
        if rank_index <= zerobot_common.staff_rank_index:
            await zerobot_common.bot_channel.send(
                f"Can not do automatic deranks for leaving member: "
                f"{memb.name}, bot isn't allowed to change staff ranks. "
                f"You will have to update their discord roles and site "
                f"rank manually."
            )
            continue
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
        # update leave date and reason
        if (memb.leave_date == ""):
            memb.leave_date = today_date
        if (memb.leave_reason == ""):
            memb.leave_reason = "left or inactive kick"
        self.old_members.append(memb)

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

        self.current_members = memberlist_from_disk(zerobot_common.current_members_filename)
        self.old_members = memberlist_from_disk(zerobot_common.old_members_filename)
        self.banned_members = memberlist_from_disk(zerobot_common.banned_members_filename)

        self.list_access = {}

        # start daily update loop
        if zerobot_common.daily_memberlist_update_enabled:
            try:
                daily_update_scheduler.start(self)
            except RuntimeError:
                # loop already running, happens when reconnecting.
                pass
    
    async def lock(self, interval=60, message=None, ctx=None):
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

        Acts as an imperfect mutex, locks access to the memberlist to prevent simultanious editing.
        'Imperfect' as it's not purely atomic, there could be an interrupt between checking self.updating and locking it as true.
        Time between lock() and unlock() should be kept to a minimum to prevent waiting time / having to resend commands.

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
        if zerobot_common.sheet_memberlist_enabled:
            load_sheet_changes(self.current_members, zerobot_common.current_members_sheet)
            load_sheet_changes(self.old_members, zerobot_common.old_members_sheet)
            load_sheet_changes(self.banned_members, zerobot_common.banned_members_sheet)
            await warnings_from_sheet(self)
        self.list_access['current_members'] = self.current_members
        self.list_access['old_members'] = self.old_members
        self.list_access['banned_members'] = self.banned_members
        return self.list_access
    async def unlock(self):
        """
        Signals that you finished accessing and editing the memberlist.
        Writes the current version of the memberlist to drive / sheet.

        Revokes access to the memberlist by clearing the references from the
        dictionary. As long as the function calling lock() did not make copies
        of the references it will no longer be able to edit.

        Acts as an imperfect mutex, unlocks access to the spreadsheet to prevent simultanious editing.
        'Imperfect' as it's not purely atomic, there could be an interrupt between checking self.updating and locking it as true.
        Time between lock() and unlock() should be kept to a minimum to prevent waiting time / having to resend commands.
        """
        self.list_access['current_members'] = None
        self.list_access['old_members'] = None
        self.list_access['banned_members'] = None
        memberlist_to_disk(self.current_members, zerobot_common.current_members_filename)
        memberlist_to_disk(self.old_members, zerobot_common.old_members_filename)
        memberlist_to_disk(self.banned_members, zerobot_common.banned_members_filename)
        if zerobot_common.sheet_memberlist_enabled:
            memberlist_to_sheet(self.current_members, zerobot_common.current_members_sheet)
            memberlist_to_sheet(self.old_members, zerobot_common.old_members_sheet)
            memberlist_to_sheet(self.banned_members, zerobot_common.banned_members_sheet)
        self.updating = False
    
    @commands.command()
    async def restart(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('restart', ctx.channel.id)) : return

        # TODO: create an internal restart that does not rely on the server restarting the python script. very tricky with scheduled tasks
        await self.bot.logout()
    
    @commands.command()
    async def updatelist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('updatelist', ctx.channel.id)) : return

        # check if confirmed
        if self.confirmed_update:
            await daily_update(self)
            return
        # not confirmed yet, ask for confirm
        await ctx.send((
            'Fully updating the memberlist spreadsheet takes a long time! (~30 minutes!)\n' +
            'The spreadsheet can not be edited while the full update is running.\n' +
            'If you are sure you want to start the full update, type the command again within 30 seconds'
        ))
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
        current_members = memberlist_from_disk(zerobot_common.current_members_filename)
        old_members = memberlist_from_disk(zerobot_common.old_members_filename)
        banned_members = memberlist_from_disk(zerobot_common.banned_members_filename)
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
        if profile_link == "" or profile_link is None or profile_link == "no site":
            link_results = SearchResult()
        else:
            link_results = await self.search_all(profile_link)
        return name_results + id_results + link_results
    
    @commands.command()
    async def refresh_banlist(self, ctx, *args):
        """
        Refreshes the banlist channel with new messages.
        """
        channel = zerobot_common.guild.get_channel(zerobot_common.banlist_channel_id)
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
            "We strongly suggest to NOT invite these people to your pvm teams.\n"
            "We may hold you responsible for any drama caused if you bring them into anything Zer0 related.\n\n"

            "This list only shows the 25 most recent Zer0 bans.\n"
            "The full Zer0 PvM banlist can be found here: <http://tiny.cc/Zer0PvMBanList>\n\n"
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
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('findmember', ctx.channel.id)) : return

        use_msg = (
            "Needs to be : -zbot findmember id"
            "id: ingame name, discord_id or profile_link>"
        )
        if len(args) == 0:
            await ctx.send("No enough arguments\n" + use_msg)
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
        if (len(results.combined_list()) >= 4):
            await ctx.send("Too many results found in search.")
            return

        # get latest information
        update_discord_info(results.combined_list())
        zerobot_common.siteops.update_site_info(results.combined_list())
        await ctx.send(
            "Found these results, Ingame stats may be outdated, "
            "info for those is from the last daily update:"
        )
        for memb in results.combined_list():
            if (memb.discord_id == 0 or memb.discord_name == "Left clan discord"):
                # no role, or did not have / dont know their discord.
                memb.discord_rank = ""
            await ctx.send(embed=member_embed(memb))
    
    @commands.command()
    async def checkdupes(self, ctx):
        await warn_duplicates(self)
    
    @commands.command()
    async def removemember(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('removemember', ctx.channel.id)) : return

        use_msg = (
            'Needs to be : -zbot removemember list_name member_id\n'
            ' - list_name: current_members, old_members or banned_members\n'
            ' - member_id: name, profile_link or discord_id'
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
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('movemember', ctx.channel.id)) : return

        use_msg = (
            'Needs to be : -zbot movemember from_list to_list member_id\n'
            ' - from_list / to_list: current_members, old_members or banned_members\n'
            ' - member_id: name, profile_link or discord_id'
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
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('editmember', ctx.channel.id)) : return

        use_msg = (
            'Needs to be : -zbot editmember list_name member_id attribute = value\n'
            ' - list_name: current_members, old_members or banned_members'
            ' - member_id: a valid name, profile_link or discord_id'
            ' - attribute: name, profile_link, discord_id'
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
        await self.unlock()

        if memb is None:
            await ctx.send(f"No member found for {id} in {args[0]}.")
            return
        await ctx.send(f"Edited {attribute} of {memb.name} from {old_value} to {new_value}.")

    @commands.command()
    async def todos(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('todos', ctx.channel.id)) : return

        memberlist = memberlist_from_disk(zerobot_common.current_members_filename)
        await ctx.send("Gathering latest info, takes a minute, ingame ranks only update daily and might be outdated")
        result = await self.bot.loop.run_in_executor(None, Todos, memberlist, *args)
        await send_multiple(ctx, result)
    
    @commands.command()
    async def inactives(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('inactives', ctx.channel.id)) : return

        if len(args) != 1:
            await ctx.send(('Needs to be : -zbot inactives <number of days>'))
            return
        try:
            days = int(args[0])
        except ValueError:
            await ctx.send(('Days argument has to be a number!\n Needs to be : -zbot inactives <number of days>'))
            return
        result = await self.bot.loop.run_in_executor(None, _Inactives, days)
        await ctx.send('Inactive for ' + str(days) + ' or more days: \n')
        for i in range(0, len(result),10):
            if (i == 0):
                message = '```\nName         Rank              Join Date  Clan xp    Last Active  Site Profile Link                   Discord Name   \n'
            else:
                message = '```\n'
            for memb in range(i,i+10):
                if (memb >= len(result)) : break
                message += result[memb].inactiveInfo() + '\n'
            message += '```'
            await ctx.send(message)
    
    @commands.command()
    async def exceptions(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(zerobot_common.permissions.is_allowed("exceptions", ctx.channel.id)) : return

        msg = "```Ingame name - Reason\n"
        for k,v in zerobot_common.inactive_exceptions.items():
            msg += (
                f"{k} - {v}\n"
            )
        msg += "```"
        await ctx.send(msg)
    
    async def get_discord_user(self, member):
        # check format of member's id
        discord_id = member.discord_id
        if not valid_discord_id(discord_id):
            return None
        # can still be None if id is valid but no member of discord (anymore).
        return zerobot_common.guild.get_member(discord_id)
    
    @commands.command()
    async def add(self, ctx, *args):
        # alias for addmember, no checks needed here.
        await self.addmember(ctx, *args)
    
    @commands.command()
    async def welcome(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(zerobot_common.permissions.is_allowed("welcome", ctx.channel.id)) : return

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
        self.logfile.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(zerobot_common.permissions.is_allowed("banlist", ctx.channel.id)) : return

        memberlist = memberlist_from_disk(zerobot_common.banned_members_filename)

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
        discord_id = app.fields_dict['requester_id']
        profile_link = app.fields_dict['profile_link']
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
                if (memb.discord_id == 0 or memb.discord_name == "Left clan discord" or memb.discord_name == "Not in clan discord"):
                    memb.discord_rank = ""
                if (memb.profile_link == "no site"):
                    memb.site_rank = ""
                await ctx.send(embed=member_embed(memb))
            raise BannedUserError("This person is banned.")
        
        # if already known as member some other way, just post results, warn that they might need a check and continue adding
        if (search_result.has_result()):
            for memb in search_result.combined_list():
                if (memb.discord_id == 0 or memb.discord_name == "Left clan discord" or memb.discord_name == "Not in clan discord"):
                    memb.discord_rank = ""
                if (memb.profile_link == "no site"):
                    memb.site_rank = ""
                await ctx.send(embed=member_embed(memb))
            raise ExistingUserWarning("This person was a member before")
    
    async def post_inactives(self, ctx, days_inactive, number_of_inactives):
        """
        Posts a list of currently inactive members to the specified context.
         - days_inactive: minimum days without activity to show up in list.
         - number_of_inactives: size of list to post, ordered by least active.
        """
        message = "\nSuggested inactives to kick if you need to make room:\n"
        message += "```Name         Rank              Join Date  Clan xp    Last Active  Site Profile Link                   Discord Name   \n"
        inactives = await self.bot.loop.run_in_executor(None, _Inactives, days_inactive)
        for i in range(0, number_of_inactives):
            if (i >= len(inactives)) : break
            message += inactives[i].inactiveInfo() + "\n"
        message += "```"

        await ctx.send(message)
    
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
        list_access["current_members"].append(new_member)

        # finished with updating, can release lock
        await self.unlock()

    @commands.command()
    async def addmember(self, ctx, *args):
        """
        Discord bot command to add a member (name, discord id, profile link)
        """
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('addmember', ctx.channel.id)) : return

        # check if command has correct number of arguments
        if len(args) < 4 :
            await ctx.send(('Needs to be: `-zbot addmember <name> <clan rank> <discord id> <profile link>`\n example: `-zbot addmember Zezima "Full Member" 123456789012345678 https://zer0pvm.com/members/1234567`'))
            return
        if (len(args) > 4):
            await ctx.send(('Too many! use \"\" around things with spaces : `-zbot addmember <name> <clan rank> <discord id> <profile link>`'))
            return
        
        # check if command arguments are valid
        name = args[0]
        rank = args[1].lower()
        rank = parse_discord_rank.get(rank, rank)
        discord_id = args[2]
        profile_link = args[3].replace("http:", "https:")
        # should be a valid rank, no staff rank changes allowed
        rank_index = utilities.rank_index(discord_role_name=rank)
        if rank_index is None:
            await ctx.send(f"Could not add, {rank} is not a correct rank\ncheck for spaces, use \"\" around something with a space in it")
            return
        if rank_index <= zerobot_common.staff_rank_index:
            await ctx.send(f"Could not add, can't give {rank} to {name}, bot currently isn't allowed to change staff ranks")
            return
        # should be an 18 length number, or "0" as explicit 'doesnt use discord' case
        if (discord_id == "0"):
            discord_id = 0
        else:
            try:
                discord_id = parse_discord_id(discord_id)
            except NotADiscordId:
                await ctx.send(f"Could not add, {discord_id} is not a valid discord id\ncheck if the discord id is correct, example: 12345678901234567. Use `0` if they really can't join discord.")
                return
        #should be a valid profile link, or "no site" as explicit 'doesnt use site' case
        if (profile_link.lower() == "no site"):
            profile_link = "no site"
        else:
            try:
                profile_link = parse_profile_link(profile_link)
            except NotAProfileLink:
                await ctx.send(f"Could not add, {profile_link} is not a correct profile link\ncheck if the profile link is correct, example: https://zer0pvm.com/members/1234567. Use `no site` if they really can't make a site account.")
                return
        discord_user = zerobot_common.guild.get_member(discord_id)
        
        # do background check
        try:
            self.background_check(ctx, name, discord_id, profile_link)
        except BannedUserError:
            await ctx.send(f"You can not add a \uD83D\uDE21 Banned Member \U0001F621, clear their banlist status first.")
            return
        except ExistingUserWarning:
            await ctx.send(f"Adding, but found previous member results above searching for name, discord id, and profile link matches for {name} (might show duplicates). You might want to check / remove them from the sheet")
        # add member to memberlist
        await self.add_member(ctx, name, discord_id, profile_link)
        # update rank on site, not needed if no site.
        if (profile_link.lower() != "no site"):
            zerobot_common.siteops.setrank(profile_link, 'Recruit')
        
        message = ''
        if (discord_user != None):
            message += f"Can't find discord user {discord_id}, I can't rank them on discord. I also can't send them the welcome messages."
        else:
            # note: I'm using the name of the actual user and roles removed in the report, not the ones i expect to be removed.
            # This is to make any unexpected results / possible mistakes visible.
            message += f"Discord User: {discord_user.name}, "
            # remove waiting approval role if present
            approval_role = zerobot_common.get_named_role('Waiting Approval')
            await discord_user.remove_roles(approval_role, reason='Adding member')
            message += f'Removed {approval_role.name} role, '
            # remove guest role if present
            guest_role = zerobot_common.get_named_role('Guest')
            await discord_user.remove_roles(guest_role, reason='Adding member')
            message += f'Removed {guest_role.name} role, '
            # add recruit role
            recruit_role = zerobot_common.get_named_role('Recruit')
            await discord_user.add_roles(recruit_role, reason='Adding member')
            message += f'Added {recruit_role.name} role on discord. '

            # send welcome messages
            await send_messages(
                discord_user,
                f"application_templates/welcome_messages.json"
            )
            message += f"\nI have pmed {name} on discord to ask for an invite, sign up for notify tags, and informed them of dps tags. \n"

        message += (
            f"Ranked {name} to Recruit on the website. Also added {name} to "
            f"the memberlist spreadsheet. \n\nYou still need to invite them "
            f"ingame. Check if their gear is augmented."
        )
        await ctx.send(message)
        await self.post_inactives(ctx, 30, 6)
    
    async def changerank(self, member, new_rank):
        discord_id = member.discord_id
        if not valid_discord_id(discord_id):
            await zerobot_common.bot_channel.send(f"Could not change discord rank of {member.name}, not a valid discord id: {discord_id}")
            return
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await zerobot_common.bot_channel.send(f"Could not change discord rank of {member.name}, discord id: {discord_id} does not exist or is not a member of the Zer0 Discord.")
            return
        
        old_rank = member.discord_rank
        old_role = None
        message = f"{discord_user.mention}: "
        for role in discord_user.roles:
            # found waiting approval role, remove
            if role.name == "Waiting Approval":
                await discord_user.remove_roles(role, reason="Adding member")
                message += f"Removed Waiting Approval role. "
            # found guest role, remove
            if role.name == "Guest":
                await discord_user.remove_roles(role, reason="Adding member")
                message += f"Removed Guest role. "
            # found old role, remove
            if role.name == old_rank:
                await discord_user.remove_roles(role, reason="Adding member")
                message += f"Removed old rank: {old_rank} on discord. "
                old_role = role
        # old role still None = did not have old role
        if (old_role == None) :
            message += f"Did not have old rank: {old_rank} on discord. "
        
        # add new role
        new_role = zerobot_common.get_named_role(new_rank)
        await discord_user.add_roles(new_role, reason="rank change command")
        message += f"Added {new_role.name} role on discord. "
        await zerobot_common.bot_channel.send(message)
        member.discord_rank = new_rank
    
    async def kickmember(self, member):
        discord_id = member.discord_id
        if not valid_discord_id(discord_id):
            await zerobot_common.bot_channel.send(f"Could not kick {member.name}, not a valid discord id: {discord_id}")
            return
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await zerobot_common.bot_channel.send(f"Could not kick {member.name}, discord id: {discord_id} does not exist or is not a member of the Zer0 Discord.")
            return
        
        await discord_user.kick(reason = "kick")
        member.discord_rank = ""

    async def removeroles(self, member):
        """
        Removes any ranked roles below staff rank, removes clan member role
        and assigns the guest role afterwards. They keep other roles.
        """
        discord_id = member.discord_id
        if not valid_discord_id(discord_id):
            await zerobot_common.bot_channel.send(f"Could not remove roles for {member.name}, not a valid discord id: {discord_id}")
            return
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await zerobot_common.bot_channel.send(f"Could not remove roles for {member.name}, discord id: {discord_id} does not exist or is not a member of the Zer0 Discord.")
            return
        
        # Remove clan member role and ranked roles below staff
        roles_to_remove = zerobot_common.get_lower_ranks(discord_user, zerobot_common.staff_rank_index)
        clan_member_role = zerobot_common.guild.get_role(zerobot_common.clan_member_role_id)
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
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')

        await ctx.send('Hello!')
        self.logfile.log(f'responded with hello in {ctx.channel.name}: {ctx.channel.id} ')
    
    @commands.command()
    async def active(self, ctx, *args):
        """
        Tells you your activity status.
        """
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('active', ctx.channel.id)) : return

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
        inactive = days_inactive > zerobot_common.inactive_days
        if inactive:
            status = (
                "You are on our list of inactive members. "
                "**! You risk getting kicked !**\n"
            )
            resp = (
                "To be removed from the inactives list: Do any of the skills "
                "or activities (wildy kills, runescore, etc.) on the "
                "highscores or ask a staff member.\n"
            )
        else:
            status = "You are not on our list of inactive members. "
            resp = (
                f"You have {zerobot_common.inactive_days - days_inactive} "
                f"days left before you're considered inactive.\n"
                f"If you think you will be gone for longer than that and you "
                f"want to avoid inactivity kicks, tell a staff member.\n"
            )

        res = (
            f"{status}"
            f"You were last active ingame {days_inactive} days ago on "
            f"{inactive_datestr}.\n{resp}\n"
            f"Anyone inactive for more than {zerobot_common.inactive_days} "
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
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('clanstats', ctx.channel.id)) : return

        # check if command has correct number of arguments
        use_msg = (
            "usage: `-zbot clanstats <date>`"
            " date = optional date that bot should compare with."
            "        this can either be a number for x days ago,"
            "        or a date in yyyy-mm-dd format! (example: 2020-12-28)"
            "        default is 30 days ago if not specified."
        )

        if len(args) > 1:
            await ctx.send("Too many arguments!\n" + use_msg)
            return
        if len(args) == 0:
            date = datetime.utcnow() - timedelta(days=30)
        if len(args) == 1:
            try:
                # try parse as x days ago
                try:
                    days = int(args[0])
                    date = datetime.utcnow() - timedelta(days=days)
                except ValueError:
                    # try parse as date instead
                    date = datetime.strptime(args[0], utilities.dateformat)
            except ValueError:
                # neither parsed successfully
                await ctx.send(f"Incorrect dateformat: {args[0]}\n" + use_msg)
                return
        date_string = date.strftime(utilities.dateformat)
        base_memblist_name = "memberlists/current_members/current_membs_"
        oldlist_filename = base_memblist_name + date_string + ".txt"
        # load disk versions to guarantee safe comparison
        oldlist = memberlist_from_disk(oldlist_filename)
        if len(oldlist) == 0:
            await ctx.send(f"No archived memberlist found for {date_string}")
            return
        newlist = memberlist_from_disk("memberlists/current_members.txt")
        current_size = len(newlist)
        stats = memberlist_compare_stats(newlist, oldlist)
        stayed = len(stats)
        new_membs = current_size - stayed
        # count non-zer0 discord ids, or count 'clan_member' tags
        clan_member_role = zerobot_common.get_named_role("Clan Member")
        membs_on_discord = len(clan_member_role.members)
        total_on_disc = zerobot_common.guild.member_count

        memberlist.memberlist_sort(stats, memberlist.hosts_cond, asc=False)
        top5hosts = "Most active hosts:\n"
        for i in range(0,5):
            total = 0
            for x in stats[i].notify_stats.values():
                total += x
            top5hosts += f"{stats[i].name} : {total}\n"


        memberlist.memberlist_sort(stats, memberlist.clan_xp_cond, asc=False)
        top5xp = "Most xp gained:\n"
        for i in range(0,5):
            top5xp += f"{stats[i].name} : {stats[i].clan_xp}\n"
        

        embed = discord.Embed()
        embed.set_author(
            name = f"{zerobot_common.guild.name} stats since {date_string}",
            icon_url = zerobot_common.guild.icon_url)
        embed.description = (
            f"Current Members: {current_size}\n"
            f"New members since {date_string}: {new_membs}\n"
            f"Clan members on discord: {membs_on_discord}\n"
            f"Total users on discord: {total_on_disc}\n"
            f"\n"
            f"{top5hosts}\n"
            f"\n"
            f"{top5xp}"
        )
        await ctx.send(embed=embed)

        inactives = _Inactives(30)
        top5inactive = (
            f"Members that are inactive ingame: {len(inactives)}\n"
            "First ten, if you are on this list it is very likely that you will get "
            "kicked when we need to make space for new members:\n"
        )
        top5inactive += (
            "```Name         Rank              Join Date  Clan xp    Last "
            "Active  Site Profile Link                   Discord Name   \n"
        )
        for i in range(0,10):
            top5inactive += f"{inactives[i].inactiveInfo()}\n"
        top5inactive += "```"
        await ctx.send(top5inactive)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        This event is triggered for any message received, including our own.
        Must keep this efficient, return asap if irrelevant.
        '''
        if len(message.role_mentions) == 0 or self.bot.user.id == message.author.id:
            return
        
        for role in message.role_mentions:
            if role.name in notify_role_names:
                # find and edit member notify stat in memory
                # can ignore sheet since it doesnt include these stats.
                # disk version is updated with the next major memberlist edit.
                # read/write to disk for each of these is too costly.
                memb_id = message.author.id
                member = memberlist_get(self.current_members, memb_id)
                if member is None:
                    return
                new_value = member.notify_stats[role.name] + 1
                member.notify_stats[role.name] = new_value