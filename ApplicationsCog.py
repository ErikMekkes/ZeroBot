'''
This module lets you configure a channel that people can request applications
in. The bot creates a channel for each new application. The applicant will be
given access to post in that channel by the bot. Use the category permissions
in discord to give other people the permissions they need, they will be taken
over for each new application channel.

Idea of this file is simple, there's commands (guest, join, rankup) to start an
app in the app request channel, and commands (accept, reject, archive, cancel)
to manage applications in each newly created application channel. Each type of
app that can be started has it's own accept_type function, that tells the bot
what to do to accept them.

Config required for this module:
 - add cog to zerobot.py
 - check these settings in settings.json:
   - clan_server_id
   - applications_category_id
   - app_requests_channel_id
   - default_bot_channel_id
 - check discord_ranks table in zerobot_common
 - check the setup below for this module
'''
import zerobot_common
from discord.ext import commands
from discord import File
from pathlib import Path
from logfile import LogFile
from permissions import Permissions
from application import Application
from applications import Applications
import traceback

# logfile for applications
app_log = LogFile('logs/applications')
# load permissions for use of commands in application channels from disk
permissions_filename = 'application_permissions.json'
permissions = Permissions(permissions_filename)
# load applications status from disk
applications_filename = 'applications/applications.json'
applications = Applications(applications_filename)

# discord clan server object (guild) to use, loaded at bot start using the
# clan_server_id in settings.json.
guild = None
# channel that allows application commands and gets cleared typing after them.
app_req_channel_id = zerobot_common.settings.get('app_requests_channel_id')
# discord category that new application channels should be created under 
# loaded on bot start from guild object using app_category_id.
app_category_id = zerobot_common.settings.get('applications_category_id')
app_category = None


# number of votes required for accepting applications
votes_for_guest = 1
votes_for_join = 3
votes_for_rankup = 2

# rank required to be able to start an application (can be None).
# useful as a whitelist for apps, or if they need to do something else first.
can_apply_role = 'Waiting Approval'
can_apply_rank = zerobot_common.discord_ranks.get(can_apply_role)
# response message sent to people who can not apply but tried to (can be None)
cant_apply_message = (
    'Please check our <#748523828291960892> channel before ' +
    'starting an application :).'
)

# rank given for guest applications
guest_role = 'Guest'
guest_rank = zerobot_common.discord_ranks.get(guest_role)
# rank given to joining members
join_role = 'Recruit'
join_rank = zerobot_common.discord_ranks.get(join_role)
# message for non members who try to rankup instead of join
join_before_rankup_message = (
    'You have to join the clan first before you can rank up :) Use ' +
    '`-zbot join` to join the clan'
)


# I do not like adding these... but our names are a bit inconsistent. And
# people also get annoyed at the 'I meant that why didnt it get it' thing.
# plus I need usable rank names for app channels and files...

# what people type down -> what rankup they mean, in a format that works for
# files and channel names.
rank_parser = {
	'leaders' : 'leader',
	'staff_members' : 'staff_member',
	'staff' : 'staff_member',
	'masterclass_pvmers' : 'masterclass_pvmer',
	'masterclass' : 'masterclass_pvmer',
	'supreme_pvmers' : 'supreme_pvmer',
	'supreme' : 'supreme_pvmer',
	'pvm_specialists' : 'pvm_specialist',
	'specialist' : 'pvm_specialist',
	'veteran_members' : 'veteran_member',
	'veterans' : 'veteran_member',
	'veteran' : 'veteran_member',
	'advanced_members' : 'advanced_member',
	'advanced' : 'advanced_member',
	'full_members' : 'full_member',
	'full' : 'full_member',
	'novice' : 'recruit',
    'guest' : 'Guest',
    'waiting' : 'waiting_approval',
    'approval' : 'waiting_approval'
}
# clear rankup name format -> what actual discord ranks belong to them.
discord_rank_parser = {
	'leader' : 'Leaders',
	'staff_member' : 'Staff Member',
	'masterclass_pvmer' : 'MasterClass PvMer',
	'supreme_pvmer' : 'Supreme PvMer',
	'pvm_specialist' : 'PvM Specialists',
	'veteran_member' : 'Veteran Member',
	'advanced_member' : 'Advanced Member',
	'full_member' : 'Full Member',
	'recruit' : 'Recruit',
    'guest' : 'Guest',
    'waiting_approval' : 'Waiting Approval'
}

# discord ranks they can't apply for, for safety (like admin or special ones)
disallowed_rankups = [
    'Leaders'
]

def highest_discord_rank(discord_user):
    '''
    Returns a discord user's highest rank, using the discord_ranks table.
    Returns None if not ranked.
    '''
    rank = -1
    for role in discord_user.roles:
        role_rank  = zerobot_common.discord_ranks.get(role.name,-1)
        if (role_rank > rank):
            rank = role_rank
    return rank

    
async def setup_app_channel(ctx, channel, app_type):
    '''
    Set up an application channel. Sets the required permissions and starts it
    off with a generic message, an app related message+img, and instructions.
    '''
    # set up permissions for applicant to be able to use channel.
    await channel.set_permissions(
        ctx.author,
        read_messages=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_external_emojis=True,
        add_reactions=True
    )
    # set up permissions for bot commands in channel
    permissions.allow('archive', channel.id)
    permissions.allow('accept', channel.id)
    permissions.allow('reject', channel.id)
    permissions.allow('cancel', channel.id)
    # set up the channel with the basic message
    msg = f'Hello {ctx.author.mention}! ' + open('app_base_message').read()
    await channel.send(msg)
    # try to find and send message, image, and instructions for app.
    try:
        app_message = open(f'{app_type}_app_text').read()
        img_file = open(f'{app_type}_image.png', 'rb')
        app_img = File(img_file)
        await channel.send(app_message, file=app_img)
        instructions = open(f'{app_type}_instructions').read()
        await channel.send(instructions)
    except FileNotFoundError:
        pass

class ApplicationsCog(commands.Cog):
    '''
    Handles all the commands for applications.
    '''
    def __init__(self, bot):
        self.bot = bot
        app_log.log(f'Applications cog loaded and ready.')
        # check that bot is connected to the right clan discord and store it.
        global guild
        guild = bot.get_guild(zerobot_common.clan_server_id)
        if (guild == None):
            app_log.log(f'not connected to the clan server id set in settings.json: {zerobot_common.clan_server_id}')
            self.bot.logout()

        # Find applications category in Zer0 server and store it
        categories = guild.categories
        for cat in categories:
            if cat.id == app_category_id:
                global app_category
                app_category = cat
    
    @commands.command()
    async def rankup(self, ctx, *args):
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(ctx.channel.id == app_req_channel_id): return

        # return if not joined yet
        current_rank = highest_discord_rank(ctx.author)
        if (current_rank < join_rank):
            await ctx.send(join_before_rankup_message)
            return
        # return if wrong format
        if (len(args) < 1):
            await ctx.send(f'Use: `-zbot rankup <rank>`')
            return
        # return if already has an open app
        open_app = applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await ctx.send(f'You already have an open application at <#{open_app.channel_id}>')
            return
        
        rank_name = '_'.join(args).lower()
        rank_name = rank_parser.get(rank_name, rank_name)
        discord_rank_name = discord_rank_parser.get(rank_name, rank_name)
        rank = zerobot_common.discord_ranks.get(discord_rank_name, -1)

        # create a copy of discord ranks
        possible_rankups = zerobot_common.discord_ranks.copy()
        # remove ranks that can not be applied for
        for r_name in disallowed_rankups:
            possible_rankups.pop(r_name)
        # remove ranks that are equal to or lower than the users current rank
        for r_name, rank in zerobot_common.discord_ranks.items():
            if rank <= current_rank:
                possible_rankups.pop(r_name)
        # reverse to list most likely rankup first
        possible_rankups = list(possible_rankups.keys())
        possible_rankups.reverse()
        # return if rank is not a possible rankup for this discord user
        if (not discord_rank_name in possible_rankups):
            msg = f'You can not apply for {discord_rank_name}, the ranks you can apply for are:'
            for r_name in possible_rankups:
                msg += f' {r_name},'
            msg = msg[:-1]
            await ctx.send(msg)
            return
        
        # actually start making the application
        channel = await guild.create_text_channel(
            f'{rank_name}-{ctx.author.display_name}',
            category=app_category,
            reason='joining'
        )
        await setup_app_channel(ctx, channel, rank_name)
        await ctx.author.send(f'I have a created a channel for your application on the Zer0 Discord server, please go to : {channel.mention}')
        # register the application and update copy on disk
        join_app = Application(
            channel.id,
            ctx.author.id,
            type = 'rankup',
            rank = rank_name,
            votes_required=votes_for_rankup
        )
        applications.append(join_app)
        # clean the app requests channel for new requests
        await self.clean_app_requests(ctx)


    @commands.command()
    async def join(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(ctx.channel.id == app_req_channel_id) : return

        # return if already has an open app
        open_app = applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await ctx.send(f'You already have an open application at <#{open_app.channel_id}>')
            app_log.log(f'already has an open application at <#{open_app.channel_id}>')
            return

        # actually start making the application
        channel = await guild.create_text_channel(
            f'join-{ctx.author.display_name}',
            category=app_category,
            reason='joining'
        )
        await setup_app_channel(ctx, channel, 'join')
        await ctx.author.send(f'I have a created a channel for your application on the Zer0 Discord server, please go to : {channel.mention}')
        permissions.allow('sitelink', channel.id)
        # register the application and update copy on disk
        join_app = Application(
            channel.id,
            ctx.author.id,
            type='join',
            votes_required=votes_for_join
        )
        applications.append(join_app)
        # clean the app requests channel for new requests
        await self.clean_app_requests(ctx)
    
    async def clean_app_requests(self, ctx):
        '''
        Purges all messages from the app_requests channel and reposts the instructions.
        '''
        # IMPORTANT check if in app_requests, if in a different channel do nothing!
        if not(ctx.channel.id == app_req_channel_id) : return

        await ctx.channel.purge()
        with open('join_image.png', 'rb') as f:
            picture = File(f)
            await ctx.channel.send('**To join Zer0 you will need the following entry requirements:** (not required for guest access)', file=picture)
            await ctx.channel.send('**Entry Reqs minimum perks:** (not required for guest access)\n - Weapon Perks: precise 6, equilibrium 4, or better combinations.\n - Armor Perks: biting 3, crackling 4, impatient 4, relentless 5, (enhanced) devoted 4, or better combinations.')
        app_requests_message = open('app_requests_message').read()
        await ctx.channel.send(app_requests_message)

    
    @commands.command()
    async def guest(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(ctx.channel.id == app_req_channel_id) : return

        open_app = applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await ctx.send(f'You already have an open application at <#{open_app.channel_id}>')
            return

        name = f'guest-{ctx.author.display_name}'
        channel = await guild.create_text_channel(name, category=app_category, reason='guesting')
        await ctx.author.send(f'I have a created a channel for your application on the Zer0 Discord server, please go to : {channel.mention}')
        await channel.set_permissions(ctx.author, read_messages=True, send_messages=True, read_message_history=True)
        permissions.allow('archive', channel.id)
        permissions.allow('accept', channel.id)
        permissions.allow('cancel', channel.id)
        permissions.allow('reject', channel.id)
        # register the application and update copy on disk
        guest_app = Application(channel.id, ctx.author.id)
        applications.append(guest_app)

        app_base_message = f'Hello {ctx.author.mention}! ' + open('app_base_message').read()
        await channel.send(app_base_message)
        guest_request_message = open('guest_request_message').read()
        await channel.send(guest_request_message)

        await self.clean_app_requests(ctx)
    
    @commands.command()
    async def archive(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(permissions.is_allowed('archive', ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return
        if (app.fields_dict['status'] == 'open'):
            await ctx.send('This application has not been accepted or rejected yet! use `-zbot accept` or `-zbot reject`')
            return

        filedir = f'applications/{ctx.channel.id}-{ctx.channel.name}/'
        Path(filedir).mkdir(parents=True, exist_ok=True)
        messages = []
        async for msg in ctx.channel.history():
            message = ''
            time = msg.created_at.strftime("%Y-%m-%d_%H.%M.%S")
            message +=f'{time}:{msg.author}:{msg.content}'
            for attach in msg.attachments:
                message += f'\n - {attach.filename} - {attach.url}'
                filename = f'{filedir}{time}_{attach.filename}'
                await attach.save(filename)
            # handle embeds too
            #for emb in message.embeds:
            messages.append(message)
        messages_file = open(filedir + 'messages','w', encoding="utf-8")
        for msg in reversed(messages):
            messages_file.write(msg + '\n')
        messages_file.close()
        await ctx.channel.delete(reason='archived')
        # clear permissions for channel
        permissions.disallow('archive', ctx.channel.id)
        permissions.disallow('accept', ctx.channel.id)
        permissions.disallow('cancel', ctx.channel.id)
        permissions.disallow('reject', ctx.channel.id)
        permissions.disallow('sitelink', ctx.channel.id)
    
    @commands.command()
    async def sitelink(self, ctx, site_profile):
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(permissions.is_allowed('sitelink', ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return
        app.set_site(site_profile)
        ctx.send('Stored site link for rankups, remember to accept their app on the clan website!')
    
    @commands.command()
    async def accept(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(permissions.is_allowed('accept', ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return
        
        if (app.fields_dict['requester_id'] == ctx.author.id):
            await ctx.send(f'You cant accept your own application!')
            return
        
        print(app.fields_dict['voters'])
        num_votes = len(app.fields_dict['voters'])
        votes_required = app.fields_dict['votes_required']
        if (app.add_vote(ctx.author.id)):
            num_votes += 1
            await ctx.send(f'Added your vote to accept this application, the application now has {num_votes} of the {votes_required} required votes')
        else:
            await ctx.send(f'You have already voted to accept this application, the application has {num_votes} of the {votes_required} required votes')
        
        if (num_votes >= votes_required):
            app.set_status('accepted')
            app_type = app.fields_dict['type']
            accept_func = f'accept_{app_type}'
            new_name = f'{ctx.channel.name}-accepted'
            await ctx.channel.edit(name=new_name)
            await getattr(self, accept_func)(ctx, app)
            return
    
    async def accept_guest(self, ctx, app):
        '''
        Accept guest application = give guest role on discord.
        Assumes they are new, and do not need check / removal of other roles.
        '''
        discord_user = guild.get_member(app.fields_dict['requester_id'])

        # add guest role
        new_role = guild.get_role(zerobot_common.discord_roles.get(guest_role))
        await discord_user.add_roles(new_role, reason="accepted guest application")
        # remove waiting approval role
        approval_role = guild.get_role(zerobot_common.discord_roles.get(can_apply_role))
        await discord_user.remove_roles(approval_role, reason='Adding member')

        await discord_user.send(f'Your application for Guest in the Zer0 discord was accepted :)')
        await ctx.send(f'Application for Guest accepted :). \n You can continue to talk in this channel until it is archived.')
    
    async def accept_join(self, ctx, app):
        '''
        Accept join application = addmember from normal zerobot.
        '''
        memblist = self.bot.get_cog('MemberlistCog')
        if (memblist == None):
            app_log.log(f'Failed to retrieve memberlist cog for addmember call')
            return
        discord_id = app.fields_dict['requester_id']
        discord_user = guild.get_member(discord_id)
        name = discord_user.display_name
        site_profile = app.fields_dict['site_profile']
        await ctx.send(f'Application to join accepted, ready for an ingame invite? :)\n You can continue to talk in this channel until it is archived.')
        # act like accept comes from staff bot command, response goes there too
        staff_bot_channel = guild.get_channel(zerobot_common.default_bot_channel_id)
        ctx.channel = staff_bot_channel
        await memblist.addmember(ctx, name, join_role, discord_id, site_profile)
    
    async def accept_rankup(self, ctx, app):
        #asdf
        memblist = self.bot.get_cog('MemberlistCog')
        if (memblist == None):
            app_log.log(f'Failed to retrieve memberlist cog for setrank call')
            return
        discord_id = app.fields_dict['requester_id']
        discord_user = guild.get_member(discord_id)
        name = discord_user.display_name
        rank = app.fields_dict['rank']
        await ctx.send(f'Rankup application to {rank} accepted :)\n You can continue to talk in this channel until it is archived.')
        # act like accept comes from staff bot command, response goes there too
        staff_bot_channel = guild.get_channel(zerobot_common.default_bot_channel_id)
        ctx.channel = staff_bot_channel
        await memblist.setrank(ctx, name, rank)

    
    @commands.command()
    async def reject(self, ctx, *args):
        '''
        Rejects an application, can be used by anyone who can type in the channel except the applicant.
        '''
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(permissions.is_allowed('reject', ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return
        if (app.fields_dict['requester_id'] == ctx.author.id):
            await ctx.send(f'You cant reject your own application!')
            return

        reason = ''
        if (len(args) > 0):
            reason = 'Reason: ' + ' '.join(args)
        app.set_status('rejected')
        app_type = app.fields_dict['type']
        discord_user = guild.get_member(app.fields_dict['requester_id'])
        await discord_user.send(f'Your application for {app_type} has been closed. {reason}')
        await ctx.send(f'Your application for {app_type} has been rejected. \n You can continue to talk in this channel until it is archived.')

    @commands.command()
    async def cancel(self, ctx, *args):
        '''
        Cancels an application, can be used by anyone who can type in the channel.
        Sets app status to close and archives the channel.
        '''
        # log command attempt and check if command allowed
        app_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(permissions.is_allowed('cancel', ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return

        reason = ''
        if (len(args) > 0):
            reason = 'Reason: ' + ' '.join(args)
        
        app.set_status('closed')
        app_type = app.fields_dict['type']
        discord_user = guild.get_member(app.fields_dict['requester_id'])
        await discord_user.send(f'Your application for {app_type} has been closed. {reason}')
        await self.archive(ctx)


    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        '''
        This event is triggered for every channel deletion.
        If the channel that got deleted was an open application, close it.
        '''
        app = applications.get_app(channel.id)
        if (app == None):
            # not an app channel
            return
        if (app.fields_dict.get('status') != 'open'):
            # already accepted or closed
            return
        # is still open app channel, close it
        app.set_status('closed')
        # clear permissions for channel
        permissions.disallow('archive', channel.id)
        permissions.disallow('accept', channel.id)
        permissions.disallow('cancel', channel.id)
        permissions.disallow('reject', channel.id)
        permissions.disallow('sitelink', channel.id)
        # notify applicant of closing channel
        app_type = app.fields_dict['type']
        discord_user = guild.get_member(app.fields_dict['requester_id'])
        await discord_user.send(f'Your application for {app_type} has been closed. Reason: The channel was removed.')
