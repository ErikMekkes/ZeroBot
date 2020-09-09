import zerobot_common
from discord.ext import tasks, commands
import traceback
from sheet_ops import UpdateMember, DeleteMember, InsertMember, read_member_sheet, SheetParams
from rankchecks import RefreshList, Todos, TodosInviteIngame, TodosJoinDiscord, TodosUpdateRanks, update_discord_info, discord_ranks, parse_discord_rank
from clantrack import UpdateList
from searchresult import SearchResult
from memberembed import member_embed
import time
from datetime import datetime
from logfile import LogFile
import asyncio
from member import Member, read_member, memblist_sort_clan_xp, validDiscordId, validSiteProfile

def _AddMember(name, profile_link, discord_id):
    zerobot_common.drive_connect()

    currentDT = datetime.utcnow()
    today_str = currentDT.strftime('%Y-%m-%d')
    new_member = Member(name, 'needs invite', 0, 0)
    new_member.rank_after_gem = ''
    new_member.discord_rank = 'Recruit'
    new_member.site_rank = "Recruit"
    new_member.profile_link = profile_link
    new_member.discord_id = discord_id
    new_member.join_date = today_str
    new_member.last_active = currentDT
    zerobot_common.current_members_sheet.insert_row(new_member.asList(),6,value_input_option = 'USER_ENTERED')

def _FindMembers(query, query_type):
    """
    Searches for given query on all memberlists, results are given as a searchresult object.

    Query type - one of : name, profile_link, discord_id
    """
    result = SearchResult()
    zerobot_common.drive_connect()
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
    zerobot_common.drive_connect()
    memberlist = read_member_sheet(sheet)
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
    zerobot_common.drive_connect()

    results = list()

    # retrieve memberlist from google docs
    curr_memb_matrix = zerobot_common.current_members_sheet.get_all_values()
    today = datetime.utcnow()
    # skip header rows
    for i in range(SheetParams.header_rows, len(curr_memb_matrix)):
        memb = read_member(curr_memb_matrix[i])
        if (memb.name in zerobot_common.inactive_exceptions):
            continue
        if (memb.last_active == None):
            days_inactive = today - datetime.strptime("2020-04-14", zerobot_common.dateformat)
            memb.last_active = datetime.strptime("2020-04-14", zerobot_common.dateformat)
        else:
            days_inactive = today - memb.last_active
        if (days_inactive.days >= days):
            memb.days_inactive = days_inactive.days
            results.append(memb)
    
    memblist_sort_clan_xp(results)
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

        # direct reference to known channels TODO, move to common?
        self.bot_channel = zerobot_common.guild.get_channel(zerobot_common.default_bot_channel_id)

        # start auto update loop if not started yet (could already be running if reconnecting)
        # these look sketchy because the auto_updater is set up using the task annotation.
        if(self.auto_updater.get_task() == None):   # pylint: disable=no-member
            self.auto_updater.start()               # pylint: disable=no-member

    @tasks.loop(hours=23, reconnect=False)
    async def auto_updater(self):
        """
        Updates the memberlist every day at noon.
        """
        update_time = 12
        now = datetime.utcnow()
        secs_til_time = update_time*3600 - now.hour*3600 - now.minute*60 - now.second
        if (secs_til_time < 0):
            secs_til_time += 24*3600
        self.logfile.log(f'auto_upd in {secs_til_time/3600}h')
        # do other stuff until this update time
        await asyncio.sleep(secs_til_time)

        # keep waiting one minute until safe to update
        while (self.updating):
            self.logfile.log('auto_upd waiting for updating to be false')
            await asyncio.sleep(60)
        
        # start update
        self.updating = True
        currentDT = datetime.utcnow()
        self.update_msg = ('Memberlist update still in progress, started at ' + currentDT.strftime("%H:%M:%S") + ', takes ~30 minutes, try again later!')
        await self.bot_channel.send('Updating the memberlist! (~30 minutes!)')
        update_res = await self.bot.loop.run_in_executor(None, UpdateList)
        # update site ranks
        zerobot_common.siteops.update_sheet_site_ranks()
        # Update colors on current members sheet
        RefreshList()
        leaving_size = len(update_res.leaving)
        if (leaving_size > 10):
            await self.bot_channel.send(f"Safety Check: too many members leaving for automatic deranks: {leaving_size}, no discord roles removed or site ranks changed. You will have to update them manually")
        else:
            # for leaving members, remove all discord roles, set site rank to retired, sheet info is already updated
            for memb in update_res.leaving:
                if (discord_ranks.get(memb.discord_rank, 0) > 7):
                    await self.bot_channel.send(f"Can not do automatic derank for leaving member: {memb.name}, bot isn't allowed to change staff ranks. You will have to update this manually.")
                    continue
                await self.removeroles(memb)
                zerobot_common.siteops.setrank(memb.profile_link, "Retired member")
        await self.bot_channel.send(update_res.summary())
        self.updating = False

        # print todos
        memberlist = read_member_sheet(zerobot_common.current_members_sheet)
        to_invite = TodosInviteIngame(memberlist)
        await send_multiple(self.bot_channel, to_invite)
        to_join_discord = TodosJoinDiscord(memberlist)
        await send_multiple(self.bot_channel, to_join_discord)
        to_update_rank = TodosUpdateRanks(memberlist)
        await send_multiple(self.bot_channel, to_update_rank)
    
    @commands.command()
    async def restart(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('restart', ctx.channel.id)) : return

        # TODO: create an internal restart that does not rely on the server restarting the python script. tricky with scheduled tasks
        await self.bot.logout()


    @commands.command()
    async def todos(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('todos', ctx.channel.id)) : return

        if self.updating:
            await ctx.send(self.update_msg)
            return
        await ctx.send("Gathering latest info, takes a minute, ingame ranks only update daily and might be outdated")
        result = await self.bot.loop.run_in_executor(None, Todos, *args)
        await send_multiple(ctx, result)

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
        zerobot_common.siteops.updateSiteRanks(results.combined_list())

        if (len(results.combined_list()) == 0):
            await ctx.send('No results found in search.')
        for memb in results.combined_list():
            if (memb.discord_id == 0 or memb.discord_name == "Left clan discord" or memb.discord_name == "Not in clan discord"):
                memb.discord_rank = ""
            if (memb.profile_link == "no site"):
                memb.site_rank = ""
            await ctx.send(embed=member_embed(memb))
    
    @commands.command()
    async def inactives(self, ctx, *args):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('inactives', ctx.channel.id)) : return

        if self.updating :
            await ctx.send(self.update_msg)
            return
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
        if (discord_ranks.get(rank, -1) > 7):
            await ctx.send(f"can't give {rank} to {name}, bot currently isn't allowed to change staff ranks")
            return

        # critical section, editing spreadsheet
        if not(await self.lock(ctx, f"Rank change of {name}, should take ~1 second")): return
        # could make this run concurrently, but it should be fast anyway.
        result = _FindMembers(name, "name")
        if (not(result.has_exact())):
            await ctx.send(f"{name} not found.\nMaybe they renamed, try searching with `-zbot findmember {name}`")
            await self.unlock()
            return
        member = result.get_exact()
        # old rank too high
        old_rank = member.discord_rank
        if (discord_ranks.get(old_rank, -1) > 7):
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
                await discord_user.send(welcome_message)
                welcome_message = open('welcome_message2.txt').read()
                await discord_user.send(welcome_message)
                welcome_message = open('welcome_message3.txt').read()
                await discord_user.send(welcome_message)
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
    async def find(self, ctx, *args):
        # alias for findmember, no checks needed here.
        await self.findmember(ctx, *args)
    
    @commands.command()
    async def welcome_message(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('welcome_message', ctx.channel.id)) : return
        
        name = ctx.author.name
        welcome_message = f"Hello {name}! " + open('welcome_message1.txt').read()
        await ctx.send(welcome_message)
        welcome_message = open('welcome_message2.txt').read()
        await ctx.send(welcome_message)

    @commands.command()
    async def banlist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('banlist', ctx.channel.id)) : return

        zerobot_common.drive_connect()
        memberlist = read_member_sheet(zerobot_common.banned_members_sheet)

        res = ["Name         | Ban reason\n", "-------------------------\n"]
        for memb in memberlist:
            res.append(memb.bannedInfo() + "\n")
        await send_multiple(ctx, res, codeblock=True)


    @commands.command()
    async def addmember(self, ctx, *args):
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
        if (discord_ranks.get(rank, 0) > 7):
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
        
        # check against current/old/blacklisted members
        name_results = _FindMembers(name, 'name')
        if (discord_id == 0):
            # prevent empty / no discord matches
            id_results = SearchResult()
        else:
            id_results = _FindMembers(discord_id, 'discord_id')
        if (profile_link == 'no site'):
            # prevent empty / no site matches
            link_results = SearchResult()
        else:
            link_results = _FindMembers(profile_link, 'profile_link')
        # combine results, could replace with override of + operator for searchresult class
        search_result = SearchResult()
        search_result.current_results = name_results.current_results + id_results.current_results + link_results.current_results
        search_result.old_results = name_results.old_results + id_results.old_results + link_results.old_results
        search_result.banned_results = name_results.banned_results + id_results.banned_results + link_results.banned_results

        # if result in bans, post results and refuse to add
        if (search_result.has_ban()):
            for memb in search_result.banned_results:
                if (memb.discord_id == 0 or memb.discord_name == "Left clan discord" or memb.discord_name == "Not in clan discord"):
                    memb.discord_rank = ""
                if (memb.profile_link == "no site"):
                    memb.site_rank = ""
                await ctx.send(embed=member_embed(memb))
            await ctx.send(f"You can not add a \uD83D\uDE21 Banned Member \U0001F621, clear their banlist status first.")
            return
        
        # if already known as member some other way, just post results, warn that they might need a check and continue adding
        if (search_result.has_result()):
            for memb in search_result.combined_list():
                if (memb.discord_id == 0 or memb.discord_name == "Left clan discord" or memb.discord_name == "Not in clan discord"):
                    memb.discord_rank = ""
                if (memb.profile_link == "no site"):
                    memb.site_rank = ""
                await ctx.send(embed=member_embed(memb))
            await ctx.send(f"Adding, but found previous member results above searching for name, discord id, and profile link matches for {name} (might show duplicates). You might want to check / remove them from the sheet")
        
        # first actual edits start if update lock check passes, add command has passed the checks and should not fail from now on.
        
        # critical section, editing spreadsheet
        if not(await self.lock(ctx, f"Adding new member {name}, should take ~1 second")): return
        # runs concurrently, other commands that dont require spreadsheet can execute.
        await self.bot.loop.run_in_executor(None, _AddMember, name, profile_link, discord_id)
        # finished with updating, can release lock
        await self.unlock()
        
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
            approval_role = zerobot_common.guild.get_role(zerobot_common.discord_roles.get('Waiting Approval'))
            await discord_user.remove_roles(approval_role, reason='Adding member')
            message += f'Removed {approval_role.name} role, '
            # remove guest role if present
            guest_role = zerobot_common.guild.get_role(zerobot_common.discord_roles.get('Guest'))
            await discord_user.remove_roles(guest_role, reason='Adding member')
            message += f'Removed {guest_role.name} role, '
            # add recruit role
            recruit_role = zerobot_common.guild.get_role(zerobot_common.discord_roles.get('Recruit'))
            await discord_user.add_roles(recruit_role, reason='Adding member')
            message += f'Added {recruit_role.name} role on discord. '

            # send welcome message on discord
            welcome_message = f"Hello {name}, Welcome to Zer0 PvM, your application has been accepted!\n\n" + open('welcome_message1.txt').read()
            await discord_user.send(welcome_message)
            welcome_message = open('welcome_message2.txt').read()
            await discord_user.send(welcome_message)
            welcome_message = open('welcome_message3.txt').read()
            await discord_user.send(welcome_message)
            message += f"\nI have pmed {name} on discord to ask for an invite, sign up for notify tags, and informed them of dps tags. \n"

        message += f"Ranked {name} to Recruit on the website. "
        message += f"Also added {name} to the memberlist spreadsheet."
        message += f"\n\nYou still need to invite them ingame (check if their gear is augmented)."

        message += f"\nSuggested inactives to kick if you need to make room:\n"
        message += '```Name         Rank              Join Date  Clan xp    Last Active  Site Profile Link                   Discord Name   \n'
        inactives = await self.bot.loop.run_in_executor(None, _Inactives, 30)
        for i in range(0, 5):
            if (i >= len(inactives)) : break
            message += inactives[i].inactiveInfo() + '\n'
        message += f"```"

        await ctx.send(message)
    
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
        if not(await self.lock(ctx, f"Updating user info of {name}, should take ~1 second")): return
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
        zerobot_common.siteops.updateSiteRanks([member])
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
        new_role = zerobot_common.guild.get_role(zerobot_common.discord_roles.get(new_rank))
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

    async def lock(self, ctx, message):
        """
        Acts as an imperfect mutex, locks access to the spreadsheet to prevent simultanious editing.
        'Imperfect' as it's not purely atomic, there could be an interrupt between checking self.updating and locking it as true.
        Time between lock() and unlock() should be kept to a minimum to prevent waiting time / having to resend commands.

        True if allowed to edit, false if not allowed. Sends previous 'message' to 'ctx' when False.
        """
        # TODO would be cleaner to not have the message part here, make this awaitable, have it retry until succesful / use some kind of queue for locks
        if self.updating :
            await ctx.send(self.update_msg)
            return False
        self.updating = True
        currentDT = datetime.utcnow()
        lock_time = currentDT.strftime(zerobot_common.timeformat)
        self.update_msg = f"Waiting for spreadsheet access started at {lock_time} to finish: " + message
        return True
    async def unlock(self):
        """
        Acts as an imperfect mutex, unlocks access to the spreadsheet to prevent simultanious editing.
        'Imperfect' as it's not purely atomic, there could be an interrupt between checking self.updating and locking it as true.
        Time between lock() and unlock() should be kept to a minimum to prevent waiting time / having to resend commands.
        """
        self.updating = False
        self.update_msg = ""

    @commands.command()
    async def respond(self, ctx):
        # log command attempt, allowed everwhere
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')

        await ctx.send('Hello!')
        self.logfile.log(f'responded with hello in {ctx.channel.name}: {ctx.channel.id} ')
    
    @commands.command()
    async def refreshlist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('refreshlist', ctx.channel.id)) : return

        # critical section, editing spreadsheet
        if not(await self.lock(ctx, f'Memberlist refresh, should take ~10 seconds')): return
        # run this concurrently, so that other commands that dont require spreadsheet can still execute in the meantime.
        await self.bot.loop.run_in_executor(None, RefreshList)
        # finished with updating, can release lock
        await self.unlock()

        await ctx.send('Refreshed discord ranks & tags on the spreadsheet, and re-colored and sorted it for you :)')
    
    @commands.command()
    async def updatelist(self, ctx):
        # log command attempt and check if command allowed
        self.logfile.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('updatelist', ctx.channel.id)) : return

        # check if confirmed
        if self.confirmed_update:
            # critical section, editing spreadsheet
            if not(await self.lock(ctx, f'Memberlist update, should take ~30 minutes')):
                # cant edit yet, reset and exit.
                self.confirmed_update = False
                return
            await ctx.send('Updating the memberlist! (takes ~30 minutes!)')
            # run this concurrently, so that other commands that dont require spreadsheet can still execute in the meantime.
            update_res = await self.bot.loop.run_in_executor(None, UpdateList)
            # update site ranks
            zerobot_common.siteops.update_sheet_site_ranks()
            # Update colors on current members sheet
            RefreshList()

            leaving_size = len(update_res.leaving)
            if (leaving_size > 10):
                await self.bot_channel.send(f"Safety Check: too many members leaving for automatic deranks: {leaving_size}, no discord roles removed or site ranks changed. You will have to update them manually")
            else:
                # for leaving members, remove all discord roles, set site rank to retired sheet info is already updated
                for memb in update_res.leaving:
                    if (discord_ranks.get(memb.discord_rank, 0) > 7):
                        await ctx.send(f"Can not do automatic derank for leaving member: {memb.name}, bot isn't allowed to change staff ranks. You will have to update this person manually.")
                        continue
                    await self.removeroles(memb)
                    zerobot_common.siteops.setrank(memb.profile_link, "Retired member")
            await ctx.send(update_res.summary())
            await self.unlock()
            self.confirmed_update = False
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