"""
Bot module for all the memberlist modifying functions. Also includes the 
scheduled daily update.
"""
from discord.ext import tasks, commands
import discord
import traceback
import time
from datetime import datetime
from logfile import LogFile
import asyncio
# custom modules
import zerobot_common
import utilities
from sheet_ops import UpdateMember, DeleteMember, InsertMember, SheetParams, start_update_warnings, clear_sheets, print_update_in_progress_warnings, load_sheet_changes, memberlist_to_sheet, color_spreadsheet, memberlist_from_sheet
from rankchecks import Todos, TodosInviteIngame, TodosJoinDiscord, TodosUpdateRanks, update_discord_info, discord_ranks, parse_discord_rank, site_ranks
from clantrack import get_ingame_memberlist, compare_lists
from searchresult import SearchResult
from memberembed import member_embed
from memberlist import memberlist_sort_name, memberlist_sort_clan_xp, memberlist_from_disk, memberlist_to_disk, memberlist_get
from member import Member, validDiscordId, validSiteProfile
from exceptions import BannedUserError, ExistingUserWarning, MemberNotFoundError, NotACurrentMemberError, StaffMemberError

# logfile for clantrack
memberlist_log = LogFile('logs/memberlist')

async def message_user(user, message, alt_ctx=None):
    """
    Tries to send message to user, send it to alternative contect if not
    allowed to message the user directly. (it's possible for discord users
    to disable direct messaging)
    """
    if user is None:
        if alt_ctx is not None:
            await alt_ctx.send(message)
        return
    try:
        await user.send(message)
    except discord.errors.Forbidden:
        if alt_ctx is not None:
            await alt_ctx.send(message)
    except discord.ext.commands.CommandInvokeError:
        if alt_ctx is not None:
            await alt_ctx.send(message)

def _FindMembers(query, query_type):
    """
    Searches for given query on all memberlists, results are given as a searchresult object.

    Query type - one of : name, profile_link, discord_id
    """
    result = SearchResult()
    result.current_results = _FindMember(query, query_type, zerobot_common.current_members_sheet)
    result.old_results = _FindMember(query, query_type, zerobot_common.old_members_sheet)
    result.banned_results = _FindMember(query, query_type, zerobot_common.banned_members_sheet)
    return result
def _FindMember(query, query_type, sheet):
    """
    Runs search for given query in memberlist. Query can be a name, discord id or site profile link.
    Result is a list, first list item is the exact match, or None if no exact match found.
    Remainder of the list are results that are similar to the original query.
    """
    memberlist = memberlist_from_sheet(sheet)
    results = list()

    # name search can have multiple results, is handled slightly differently
    if (query_type == 'name'):
        for num, memb in enumerate(memberlist):
            # save sheet and row in search result to be able to edit later.
            memb.sheet = sheet
            memb.row = num + SheetParams.header_rows + 1
            # if exact match, add as first result
            if (memb == query):
                memb.result_type = "exact"
                results.append(memb)
            # also try old names as additional results
            # if exact match in list of old names, add as possible result, not unique = continue loop
            for old_name in memb.old_names:
                if (old_name.lower() == query):
                    memb.result_type = "old name"
                    results.append(memb)
            # could try to find partial match in current name
            # could try to find partial match in old names
        return results

    # discord id or site profile link can only have one unique match
    for num,memb in enumerate(memberlist):
        # if exact match in attribute, replace exact match result, is unique = end loop
        if (getattr(memb,query_type) == query):
            memb.result_type = "exact"
            memb.sheet = sheet
            memb.row = num + SheetParams.header_rows + 1
            results.append(memb)
            break
    return results

def _Inactives(days):
    """
    Returns a list of players that have been inactive for more than the 
    specified number of days. List is sorted by lowest clan xp first.
    """
    memberlist = memberlist_from_disk(zerobot_common.current_members_filename)
    today = datetime.utcnow()
    results = list()
    for memb in memberlist:
        if (memb.name in zerobot_common.inactive_exceptions):
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
    await self.bot_channel.send("Starting to collect ingame data for update")

    # retrieve the latest ingame data as a new concurrent ask
    ingame_members = await self.bot.loop.run_in_executor(
        None, get_ingame_memberlist
    )
    # backup ingame members right away, nice for testing
    date_str = datetime.utcnow().strftime(utilities.dateformat)
    ing_backup_name = "memberlists/current_members/ingame_membs_" + date_str
    memberlist_to_disk(ingame_members, ing_backup_name)
    
    # start posting update warnings on spreadsheet
    await self.bot_channel.send("Daily update starting in 5 minutes")
    await self.bot.loop.run_in_executor(None, start_update_warnings)

    #=== try to obtain editing lock, loads sheet changes ===
    await self.lock()
    clear_sheets()
    print_update_in_progress_warnings()
    # compare against new ingame data to find joins, leaves, renames
    comp_res = compare_lists(ingame_members, self.current_members)
    # use result to update our list of current members
    self.current_members = comp_res.staying + comp_res.joining + comp_res.renamed
    # get site updates, send list to siteops func that updates it
    update_discord_info(self.current_members)
    zerobot_common.siteops.update_site_info(self.current_members)
    # for leaving members remove discord roles, set site rank to retired
    await process_leaving(self, comp_res.leaving)

    # sort updated lists
    memberlist_sort_name(self.current_members)
    memberlist_sort_name(self.old_members)
    memberlist_sort_name(self.banned_members)

    # write updated memberlists to disk as backup
    cur_backup_name = "memberlists/current_members/current_membs_" + date_str
    old_backup_name = "memberlists/old_members/old_membs_" + date_str
    ban_backup_name = "memberlists/banned_members/banned_membs_" + date_str
    memberlist_to_disk(self.current_members, cur_backup_name)
    memberlist_to_disk(self.old_members, old_backup_name)
    memberlist_to_disk(self.banned_members, ban_backup_name)

    #=== release editing lock, writes to sheet and disk ===
    await self.unlock()
    
    #update colors on sheet
    color_spreadsheet()

    # post summary of changes
    await self.bot_channel.send(comp_res.summary())
    #post todo lists,
    to_invite = TodosInviteIngame(self.current_members)
    await send_multiple(self.bot_channel, to_invite)
    to_join_discord = TodosJoinDiscord(self.current_members)
    await send_multiple(self.bot_channel, to_join_discord)
    to_update_rank = TodosUpdateRanks(self.current_members)
    await send_multiple(self.bot_channel, to_update_rank)
    
async def process_leaving(self, leaving_list):
    """
    Process the leaving members, removes their discord roles, sets their
    site rank to retired. 
    """
    leaving_size = len(leaving_list)
    if (leaving_size > 10):
        await self.bot_channel.send(
            f"Safety Check: too many members leaving for automatic site "
            f"rank and discord role removal: {leaving_size}. No discord "
            f"roles or site ranks changed, you will have to update them "
            f"manually."
        )
        return
    
    for memb in leaving_list:
        if (discord_ranks.get(memb.discord_rank, 0) > 7):
            await self.bot_channel.send(
                f"Can not do automatic deranks for leaving member: "
                f"{memb.name}, bot isn't allowed to change staff ranks. "
                f"You will have to update their discord roles and site "
                f"rank manually."
            )
            continue
        # remove discord roles
        await self.removeroles(memb)
        # set site rank to retired member
        zerobot_common.siteops.setrank_member(memb, "Retired member")
        # update leave date and reason
        if (memb.leave_date == ""):
            today_date = datetime.utcnow()
            memb.leave_date = today_date.strftime(utilities.dateformat)
        if (memb.leave_reason == ""):
            memb.leave_reason = "left or inactive kick"
        self.old_members.append(memb)
    
async def send_welcome_messages(user, ctx=None):
    """
    Sends the welcome messages to user privately. If user is a name string or 
    a discord user that does not allow direct messaging without being friends
    this will try to send the messages to ctx if it is not None.
    """
    if isinstance(user, str):
        name = user
        user = None
    else:
        name = user.display_name
    # send welcome message on discord
    welcome_message = (
        f"Hello {name}, Welcome to Zer0 PvM, your "
        f"application has been accepted!\n\n"
    ) + open('welcome_message1.txt').read()
    await message_user(user, welcome_message, ctx)
    welcome_message = open('welcome_message2.txt').read()
    await message_user(user, welcome_message, ctx)
    welcome_message = open('welcome_message3.txt').read()
    await message_user(user, welcome_message, ctx)
    welcome_message = open('welcome_message4.txt').read()
    await message_user(user, welcome_message, ctx)

class MemberlistCog(commands.Cog):
    '''
    Handles commands related to memberlist changes and starts the daily update.
    '''
    def __init__(self, bot):
        self.bot = bot
        self.logfile = LogFile("logs/botlog")
        self.logfile.log(f'MembList cog loaded and ready.')
        self.updating = False
        self.update_msg = ""
        self.confirmed_update = False
        self.ingame_update_result = None

        self.current_members = memberlist_from_disk(zerobot_common.current_members_filename)
        self.old_members = memberlist_from_disk(zerobot_common.old_members_filename)
        self.banned_members = memberlist_from_disk(zerobot_common.banned_members_filename)

        self.list_access = {}

        # direct reference to known channels TODO, move to common?
        self.bot_channel = zerobot_common.guild.get_channel(zerobot_common.default_bot_channel_id)

        # start daily update loop
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
                    await self.bot_channel.send(message)
            await asyncio.sleep(interval)
        self.updating = True
        load_sheet_changes(self.current_members, zerobot_common.current_members_sheet)
        load_sheet_changes(self.old_members, zerobot_common.old_members_sheet)
        load_sheet_changes(self.banned_members, zerobot_common.banned_members_sheet)
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
    
    @commands.command()
    async def find(self, ctx, *args):
        # alias for findmember, no checks needed here.
        await self.findmember(ctx, *args)

    @commands.command()
    async def findmember(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('findmember', ctx.channel.id)) : return

        if self.updating :
            await ctx.send(self.update_msg)
            return
        if len(args) != 1:
            await ctx.send(('Needs to be : -zbot findmember <name OR discord_id OR profile_link>'))
            return
        
        # check kind of search, sanitize input
        query = args[0]
        query_type = None
        if (query.find("://") != -1):
            query_type = 'profile_link'
        else:
            try:
                if int(query) < 100000000000000000 : raise ValueError('not a discord id')
                query_type = 'discord_id'
                query = int(query)
            except ValueError:
                query_type = 'name'
                query = query.lower()
        
        # run search
        results = await self.bot.loop.run_in_executor(None, _FindMembers, query, query_type)
        
        # get most up to date info for members in results, no ingame data for now (slow/impractical)
        update_discord_info(results.combined_list())
        zerobot_common.siteops.update_site_info(results.combined_list())

        if (len(results.combined_list()) == 0):
            await ctx.send('No results found in search.')
        for memb in results.combined_list():
            if (memb.discord_id == 0 or memb.discord_name == "Left clan discord" or memb.discord_name == "Not in clan discord"):
                memb.discord_rank = ""
            if (memb.profile_link == "no site"):
                memb.site_rank = ""
            await ctx.send(embed=member_embed(memb))

    async def full_search(self, name, discord_id, profile_link):
        """
        Tries to find any results in the memberlist and groups the results.
        Checks for name, discord id and profile link matches on the current,
        old and banned memberlists. Might include duplicates.
        """
        await self.lock()
        # find results for name matches (non-empty)
        if name == "" or name is None:
            name_results = SearchResult()
        else:
            name_results = _FindMembers(name, 'name')
        # find results for discord id matches (non-empty)
        if discord_id == 0 or discord_id is None:
            id_results = SearchResult()
        else:
            id_results = _FindMembers(discord_id, 'discord_id')
        # find results for profile link matches (non-empty)
        if profile_link == "" or profile_link is None or profile_link == "no site":
            link_results = SearchResult()
        else:
            link_results = _FindMembers(profile_link, 'profile_link')
        await self.unlock()
        return name_results + id_results + link_results

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
    
    async def set_rank(self, name, discord_rank):
        """
        Sets a current member's rank on the memberlist to the specified rank.

        Raises StaffMemberError if trying to make staff rank changes.
        Raises NotACurrentMemberError if member found but not in clan.
        Raises MemberNotFoundError if no member could be found for given name.
        """
        # find the right person and checks to not make staff changes
        if discord_ranks.get(discord_rank, 0) > 8:
            raise StaffMemberError(
                f"Trying to make {name} a staff member, bot is not allowed to"
                f"make staff member changes."
            )
        
        list_access = await self.lock()

        member = memberlist_get(list_access["current_members"], name)
        if member is None:
            await self.unlock()
            raise MemberNotFoundError(f"{name} not found on current memberlist.")
        if discord_ranks.get(member.discord_rank,0) > 8:
            await self.unlock()
            raise StaffMemberError(
                f"{name} is a staff member, bot is not allowed to"
                f"make staff member changes."
            )
        
        # update discord rank on memberlist.
        member.discord_rank = discord_rank
        await self.unlock()
        # update site rank if site module enabled TODO move to separate module
        if zerobot_common.site_enabled:
            zerobot_common.siteops.setrank_member(member, discord_rank)
    
    @commands.command()
    async def setrank(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('setrank', ctx.channel.id)) : return

        name = args[0]
        rank = args[1].lower()
        rank = parse_discord_rank.get(rank, rank)

        if len(args) != 2:
            await ctx.send("Should be `-zbot setrank <name> <rank>`\ncheck for spaces, use \"\" around something with a space in it")
            return
        if (discord_ranks.get(rank, -1) == -1):
            await ctx.send(f"{rank} is not a correct rank\ncheck for spaces, use \"\" around something with a space in it")
            return
        # new rank too high
        if (discord_ranks.get(rank, -1) > 8):
            await ctx.send(f"can't give {rank} to {name}, bot currently isn't allowed to change staff ranks")
            return

        # critical section, editing spreadsheet
        await self.lock()
        # could make this run concurrently, but it should be fast anyway.
        result = _FindMembers(name, "name")
        if (not(result.has_exact())):
            await ctx.send(f"{name} not found.\nMaybe they renamed, try searching with `-zbot findmember {name}`")
            await self.unlock()
            return
        member = result.get_exact()
        # old rank too high
        old_rank = member.discord_rank
        if (discord_ranks.get(old_rank, -1) > 8):
            await ctx.send(f"{name}'s old rank is {old_rank}, bot currently isn't allowed to change staff ranks")
            await self.unlock()
            return
        
        message = ""

        # trying to change rank of someone on banlist = stop, needs manual clearance.
        if (member.sheet == zerobot_common.banned_members_sheet):
            await ctx.send(f"You can not change the rank of a \uD83D\uDE21 Banned Member \U0001F621 ({member.name}), clear their banlist status first.")
            await self.unlock()
            return

        # comes from old members sheet = rejoining, send welcome and info messages
        if (member.sheet == zerobot_common.old_members_sheet):
            discord_user = await self.get_discord_user(member)
            if (discord_user == None):
                message += f"Can't pm {name} on discord. You should tell them to sign up for notify tags, to use them for their pvm in #ranks-chat, tell them about dps gems and what to work on. "
            else:
                welcome_message = f"Hello {name}, Welcome back to Zer0!\n\n" + open('welcome_message1.txt').read()
                await message_user(discord_user, welcome_message)
                welcome_message = open('welcome_message2.txt').read()
                await message_user(discord_user, welcome_message)
                welcome_message = open('welcome_message3.txt').read()
                await message_user(discord_user, welcome_message)
                message += f"I have pmed {name} on discord to ask for an invite, sign up for notify tags, and informed them of dps tags. "

        # TODO: check site / discord functions further to see if the actual update was successful if given valid input?

        # discord role update
        if (rank == "Retired member"):
            await self.removeroles(member)
        elif (rank == "Kicked Member"):
            await self.kickmember(member)
        else:
            await self.changerank(member, rank)

        # TODO: make siteops functions post messages related to site rank changes?

        # site rank update
        if (validSiteProfile(member.profile_link)):
            zerobot_common.siteops.setrank_member(member, rank)
            message += f"Ranked {name} to {rank} on website. "
        else:
            message += f"Could not do site rank change, {name}'s site profile link is invalid: {member.profile_link}\n"
        
        # update sheet, delete from sheet found on -> insert on sheet should be on works for all inputs
        if (rank == "Retired member"):
            new_sheet = zerobot_common.old_members_sheet
        elif (rank == "Kicked member"):
            new_sheet = zerobot_common.banned_members_sheet
        else:
            new_sheet = zerobot_common.current_members_sheet
            # updated rank, rank after gem no longer relevant.
            member.rank_after_gem = ""
        DeleteMember(member.sheet, member.row)
        InsertMember(new_sheet, member.row, member)
        await self.unlock()
        
        message += f"Changed {name}'s rank to {rank} on the spreadsheet.\n You still need to change their ingame rank."

        await ctx.send(message)
    
    async def get_discord_user(self, member):
        # check format of member's id
        discord_id = member.discord_id
        if (not(validDiscordId(discord_id))):
            return None
        # safe to parse int
        discord_id = int(discord_id)
        # can still be None if id is valid but doesnt exist or not a member of discord.
        return zerobot_common.guild.get_member(discord_id)
    
    @commands.command()
    async def add(self, ctx, *args):
        # alias for addmember, no checks needed here.
        await self.addmember(ctx, *args)
    
    @commands.command()
    async def welcome(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('welcome', ctx.channel.id)) : return

        if len(args) == 1 and args[0] == "me":
            await send_welcome_messages(ctx.author, None)
        else:
            await send_welcome_messages(ctx.author.name, ctx.channel)

    @commands.command()
    async def banlist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('banlist', ctx.channel.id)) : return

        memberlist = memberlist_from_disk(zerobot_common.banned_members_filename)

        res = ["Name         | Ban reason\n", "-------------------------\n"]
        for memb in memberlist:
            res.append(memb.bannedInfo() + "\n")
        await send_multiple(ctx, res, codeblock=True)
    
    async def background_check_app(self, ctx, app):
        name = app.fields_dict["name"]
        discord_id = app.fields_dict['requester_id']
        profile_link = app.fields_dict['profile_link']
        await self.background_check(ctx, name, discord_id, profile_link)

    async def background_check(self, ctx, name, discord_id, profile_link):
        """
        Runs a background check on the application, matches found are posted
        to the provided context (channel or user).

        Raises BannedUserError when there is matching info on the banlist.
        Raises ExistingUserWarning when matches found outside bans.
        """
        search_result = await self.full_search(
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
        if validDiscordId(discord_id):
            new_member.discord_rank = "Recruit"
        else:
            new_member.discord_rank = ""
        if validSiteProfile(profile_link):
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
        Discord bot command to add a member (name, discord id, site link)
        """
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('addmember', ctx.channel.id)) : return

        # check if command has correct number of arguments
        if len(args) < 4 :
            await ctx.send(('Needs to be: `-zbot addmember <name> <clan rank> <discord id> <site profile link>`\n example: `-zbot addmember Zezima "Full Member" 123456789012345678 https://zer0pvm.com/members/1234567`'))
            return
        if (len(args) > 4):
            await ctx.send(('Too many! use \"\" around things with spaces : `-zbot addmember <name> <clan rank> <discord id> <site profile link>`'))
            return
        
        # check if command arguments are valid
        name = args[0]
        rank = args[1].lower()
        rank = parse_discord_rank.get(rank, rank)
        discord_id = args[2]
        profile_link = args[3].replace("http:", "https:")
        # should be a valid rank, no staff rank changes allowed
        if (discord_ranks.get(rank, 0) == 0):
            await ctx.send(f"Could not add, {rank} is not a correct rank\ncheck for spaces, use \"\" around something with a space in it")
            return
        if (discord_ranks.get(rank, 0) > 8):
            await ctx.send(f"Could not add, can't give {rank} to {name}, bot currently isn't allowed to change staff ranks")
            return
        # should be an 18 length number, or "0" as explicit 'doesnt have discord' case
        if (discord_id == '0'):
            discord_id = 0
        elif (not(validDiscordId(discord_id))):
            await ctx.send(f"Could not add, {discord_id} is not a valid discord id\ncheck their id again, should be 18 numbers example: 123456789012345678)")
            return
        else:
            # safe to parse int-
            discord_id = int(discord_id)
            discord_user = zerobot_common.guild.get_member(discord_id)
            if (discord_user == None):
                await ctx.send(f"Could not add, {discord_id} does not exist or is not a member of the Zer0 Discord id\ncheck their id again, should be 18 numbers example: 123456789012345678). Use `0` if they really can't join discord.")
                return
        #should be a valid site profile link, or "no site" as explicit 'doesnt have site' case
        if (profile_link.lower() != "no site"):
            if (not(validSiteProfile(profile_link))):
                await ctx.send(f"Could not add, {profile_link} is not a correct profile link\ncheck if the site link and number are correct, example: https://zer0pvm.com/members/1234567). Use `no site` if they really can't make a site account.")
                return
        
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
        if (discord_id == 0):
            message += f"You used 0 for discord id, use only if they can't join discord. I can't rank them on discord. I also can't send them a welcome message."
            message += f" You have to tell them to sign up for notify tags and to use them for their pvm in #ranks-chat, and tell them about dps gems. "
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

            await send_welcome_messages(discord_user)
            message += f"\nI have pmed {name} on discord to ask for an invite, sign up for notify tags, and informed them of dps tags. \n"

        message += (
            f"Ranked {name} to Recruit on the website. Also added {name} to "
            f"the memberlist spreadsheet. \n\nYou still need to invite them "
            f"ingame. Check if their gear is augmented."
        )
        await ctx.send(message)
        await self.post_inactives(ctx, 30, 6)
    
    @commands.command()
    async def edit(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('edit', ctx.channel.id)) : return

        # check if command has correct number of arguments
        if len(args) < 4 :
            await ctx.send(('Not enough! Needs to be: `-zbot edit <name> <attribute> = <value>`\n example: `-zbot edit Zezima discord_id = 123456789012345678`\npossible attributes: `discord_id`, `profile_link`'))
            return
        if (len(args) > 4):
            await ctx.send(('Too many! Needs to be: `-zbot edit <name> <attribute> = <value>`\n use \"\" around things with spaces: `-zbot edit "Ze zima" discord_id = 123456789012345678`\npossible attributes: `discord_id`, `profile_link`'))
            return
        # check if command uses the form a = b
        if (args[2] != "="):
            await ctx.send(('To edit a member use: `-zbot edit <name> <attribute> = <value>`\n example: `-zbot edit Zezima discord_id = 123456789012345678`\npossible attributes: `discord_id`, `profile_link`'))
            return
        # check if attribute to edit is valid
        # ugly but effective, I want to do this before I spend time finding the member, without keeping a separate list of valid attributes, 
        # so the goal is to check if a class instance will be given an attribute when made.
        # afaik there's no python model that lets me predefine / check the existence of a class instance's attributes.
        attribute = args[1]
        dummy_member = Member("","",0,0)
        try:
            getattr(dummy_member, attribute)
        except AttributeError:
            await ctx.send(('Not an existing attribute, possible attributes: `discord_id`, `profile_link`'))
            return

        # check if value for attribute is valid
        if (attribute == "discord_id"):
            new_value = args[3]
            # should be an 18 length number, or "0" as explicit 'doesnt have discord' case
            if (new_value == "0"):
                new_value = 0
            elif (not(validDiscordId(new_value))):
                await ctx.send(f"{new_value} is not a valid discord_id\ncheck their id again, should be 18 numbers example: 123456789012345678)")
                return
            else:
                # safe to parse int
                new_value = int(new_value)
        if (attribute == "profile_link"):
            new_value = args[3].replace("http:", "https:")
            #should be a valid site profile link, or "no site" as explicit 'doesnt have site' case
            if (new_value.lower() == "no site"):
                new_value = "no site"
            elif (not(validSiteProfile(new_value))):
                await ctx.send(f"{new_value} is not a valid profile_link. Check if the address and number are correct, example: https://zer0pvm.com/members/1234567")
                return
        else:
            new_value = args[3]

        name = args[0]

        # critical section, editing spreadsheet
        await self.lock()
        results = _FindMembers(name, "name")
        # member not found, cant edit
        if (not(results.has_exact())):
            await ctx.send(f"{name} not found as current member.\nMaybe they renamed, try searching with `-zbot findmember {name}`")
            await self.unlock()
            return
        member = results.get_exact()
        
        # store old value for update message
        old_value = getattr(member, attribute)
        # update member with new value
        setattr(member, attribute, new_value)

        # get most up to date info of member for sheet update
        update_discord_info([member])
        zerobot_common.siteops.update_site_info([member])
        # update sheet with new info
        UpdateMember(member.sheet, member.row, member)
        await self.unlock()

        message = f"Edited `{name}`, changed {attribute} from ` {old_value}` to ` {new_value}`"
        await ctx.send(message)
    
    async def changerank(self, member, new_rank):
        discord_id = member.discord_id
        if (not(validDiscordId(discord_id))):
            await self.bot_channel.send(f"Could not change discord rank of {member.name}, not a valid discord id: {discord_id}")
            return
        
        # safe to parse int
        discord_id = int(discord_id)
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await self.bot_channel.send(f"Could not change discord rank of {member.name}, discord id: {discord_id} does not exist or is not a member of the Zer0 Discord.")
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
        await self.bot_channel.send(message)
        member.discord_rank = new_rank
    
    async def kickmember(self, member):
        discord_id = member.discord_id
        if (not(validDiscordId(discord_id))):
            await self.bot_channel.send(f"Could not kick {member.name}, not a valid discord id: {discord_id}")
            return
        
        # safe to parse int
        discord_id = int(discord_id)
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await self.bot_channel.send(f"Could not kick {member.name}, discord id: {discord_id} does not exist or is not a member of the Zer0 Discord.")
            return
        
        await discord_user.kick(reason = "kick")
        member.discord_rank = ""

    async def removeroles(self, member):
        discord_id = member.discord_id
        if (not(validDiscordId(discord_id))):
            await self.bot_channel.send(f"Could not remove roles for {member.name}, not a valid discord id: {discord_id}")
            return
        
        # safe to parse int
        discord_id = int(discord_id)
        discord_user = zerobot_common.guild.get_member(discord_id)
        if (discord_user == None):
            await self.bot_channel.send(f"Could not remove roles for {member.name}, discord id: {discord_id} does not exist or is not a member of the Zer0 Discord.")
            return
        
        await discord_user.edit(roles=[], reason="remove roles")
        member.discord_rank = ""

    @commands.command()
    async def respond(self, ctx):
        # log command attempt, allowed everwhere
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')

        await ctx.send('Hello!')
        self.logfile.log(f'responded with hello in {ctx.channel.name}: {ctx.channel.id} ')
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        '''
        This event executes whenever a command encounters an error that isn't handled.
        '''
        # send simple message to location the error came from.
        await ctx.send('An error occured.')
        # write down full error trace in log files on disk.
        self.logfile.log(f'Error in command : {ctx.command}')
        self.logfile.log(traceback.format_exception(type(error), error, error.__traceback__))