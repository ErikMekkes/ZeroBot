import zerobot_common
from discord.ext import commands
from discord import File
from pathlib import Path
from application import Application

class ApplicationsCog(commands.Cog):
    '''
    Handles all the commands for applications.
    '''
    def __init__(self, bot):
        self.bot = bot
        zerobot_common.logfile.log(f'Applications cog loaded and ready.')

    @commands.command()
    async def join(self, ctx):
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(ctx.channel.id == zerobot_common.app_requests_channel_id) : return

        open_app = zerobot_common.applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await ctx.author.send(f'You already have an open application at <#{open_app.channel_id}>')
            zerobot_common.applications_log.log(f'already has an open application at <#{open_app.channel_id}>')
            return

        name = f'join-{ctx.author.name}'
        channel = await zerobot_common.guild.create_text_channel(name, category=zerobot_common.applications_category, reason='joining')
        await ctx.author.send(f'I have a created a channel for your application on the Zer0 Discord server, please go to : {channel.mention}')
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
        zerobot_common.permissions.allow('archive', channel.id)
        zerobot_common.permissions.allow('accept', channel.id)
        zerobot_common.permissions.allow('reject', channel.id)
        zerobot_common.permissions.allow('cancel', channel.id)
        zerobot_common.permissions.allow('sitelink', channel.id)
        # register the application and update copy on disk
        join_app = Application(channel.id, ctx.author.id, type='join', votes_required=3)
        zerobot_common.applications.append(join_app)

        app_base_message = f'Hello {ctx.author.mention}! ' + open('app_base_message').read()
        await channel.send(app_base_message)
        with open('minreqs.png', 'rb') as f:
            picture = File(f)
            await channel.send('Thank you for your interest in Joining Zer0 PvM!\n \n To join Zer0 PvM you will need to meet the follow entry requirements:', file=picture)
        join_request_message = open('join_request_message').read()
        await channel.send(join_request_message)

        await self.clean_app_requests(ctx)
    
    async def clean_app_requests(self, ctx):
        '''
        Purges all messages from the app_requests channel and reposts the instructions.
        '''
        # IMPORTANT check if in app_requests, if in a different channel do nothing!
        if not(ctx.channel.id == zerobot_common.app_requests_channel_id) : return

        await ctx.channel.purge()
        with open('minreqs.png', 'rb') as f:
            picture = File(f)
            await ctx.channel.send('**To join Zer0 you will need the following entry requirements:** (not required for guest access)', file=picture)
            await ctx.channel.send('**Entry Reqs minimum perks:** (not required for guest access)\n - Weapon Perks: precise 6, equilibrium 4, or better combinations.\n - Armor Perks: biting 3, crackling 4, impatient 4, relentless 5, (enhanced) devoted 4, or better combinations.')
        app_requests_message = open('app_requests_message').read()
        await ctx.channel.send(app_requests_message)

    
    @commands.command()
    async def guest(self, ctx):
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(ctx.channel.id == zerobot_common.app_requests_channel_id) : return

        open_app = zerobot_common.applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await ctx.send(f'You already have an open application at <#{open_app.channel_id}>')
            return

        name = f'guest-{ctx.author.name}'
        channel = await zerobot_common.guild.create_text_channel(name, category=zerobot_common.applications_category, reason='guesting')
        await ctx.author.send(f'I have a created a channel for your application on the Zer0 Discord server, please go to : {channel.mention}')
        await channel.set_permissions(ctx.author, read_messages=True, send_messages=True, read_message_history=True)
        zerobot_common.permissions.allow('archive', channel.id)
        zerobot_common.permissions.allow('accept', channel.id)
        zerobot_common.permissions.allow('cancel', channel.id)
        zerobot_common.permissions.allow('reject', channel.id)
        # register the application and update copy on disk
        guest_app = Application(channel.id, ctx.author.id)
        zerobot_common.applications.append(guest_app)

        app_base_message = f'Hello {ctx.author.mention}! ' + open('app_base_message').read()
        await channel.send(app_base_message)
        guest_request_message = open('guest_request_message').read()
        await channel.send(guest_request_message)

        await self.clean_app_requests(ctx)
    
    @commands.command()
    async def archive(self, ctx):
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('archive', ctx.channel.id)) : return

        app = zerobot_common.applications.get_app(ctx.channel.id)
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
        zerobot_common.permissions.disallow('archive', ctx.channel.id)
        zerobot_common.permissions.disallow('accept', ctx.channel.id)
        zerobot_common.permissions.disallow('cancel', ctx.channel.id)
        zerobot_common.permissions.disallow('reject', ctx.channel.id)
        zerobot_common.permissions.disallow('sitelink', ctx.channel.id)
    
    @commands.command()
    async def sitelink(self, ctx, site_profile):
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('sitelink', ctx.channel.id)) : return

        app = zerobot_common.applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return
        app.set_site(site_profile)
        ctx.send('Stored site link for rankups, remember to accept their app on the clan website!')
    
    @commands.command()
    async def accept(self, ctx):
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('accept', ctx.channel.id)) : return

        app = zerobot_common.applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return
        
        if (app.fields_dict['requester_id'] == ctx.author.id):
            await ctx.send(f'You cant accept your own application!')
            return
        
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
        discord_user = zerobot_common.guild.get_member(app.fields_dict['requester_id'])

        # add guest role
        new_role = zerobot_common.guild.get_role(zerobot_common.discord_roles.get('Guest'))
        await discord_user.add_roles(new_role, reason="accepted guest application")
        # remove waiting approval role
        approval_role = zerobot_common.guild.get_role(zerobot_common.discord_roles.get('Waiting Approval'))
        await discord_user.remove_roles(approval_role, reason='Adding member')

        await discord_user.send(f'Your application for Guest in the Zer0 discord was accepted :)')
        await ctx.send(f'Application for Guest accepted :). \n You can continue to talk in this channel until it is archived.')
    
    async def accept_join(self, ctx, app):
        '''
        Accept join application = addmember from normal zerobot.
        '''
        memblist = self.bot.get_cog('MembList')
        if (memblist == None):
            zerobot_common.applications_log.log(f'Failed to retrieve memberlist cog for addmember call')
            return
        discord_id = app.fields_dict['requester_id']
        discord_user = zerobot_common.guild.get_member(discord_id)
        name = discord_user.name
        site_profile = app.fields_dict['site_profile']
        await ctx.send(f'Application to join accepted, ready for an ingame invite? :)\n You can continue to talk in this channel until it is archived.')
        # act like accept comes from staff bot command, response goes there too
        staff_bot_channel = zerobot_common.guild.get_channel(zerobot_common.default_bot_channel_id)
        ctx.channel = staff_bot_channel
        await memblist.addmember(ctx, name, 'Novice', discord_id, site_profile)

    
    @commands.command()
    async def reject(self, ctx, *args):
        '''
        Rejects an application, can be used by anyone who can type in the channel except the applicant.
        '''
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('reject', ctx.channel.id)) : return

        app = zerobot_common.applications.get_app(ctx.channel.id)
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
        discord_user = zerobot_common.guild.get_member(app.fields_dict['requester_id'])
        await discord_user.send(f'Your application for {app_type} has been closed. {reason}')
        await ctx.send(f'Your application for {app_type} has been rejected. \n You can continue to talk in this channel until it is archived.')

    @commands.command()
    async def cancel(self, ctx, *args):
        '''
        Cancels an application, can be used by anyone who can type in the channel.
        Sets app status to close and archives the channel.
        '''
        # log command attempt and check if command allowed
        zerobot_common.applications_log.log(f'{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}')
        if not(zerobot_common.permissions.is_allowed('cancel', ctx.channel.id)) : return

        app = zerobot_common.applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send('Could not find related application for this channel.')
            return

        reason = ''
        if (len(args) > 0):
            reason = 'Reason: ' + ' '.join(args)
        
        app.set_status('closed')
        app_type = app.fields_dict['type']
        discord_user = zerobot_common.guild.get_member(app.fields_dict['requester_id'])
        await discord_user.send(f'Your application for {app_type} has been closed. {reason}')
        await self.archive(ctx)


    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        '''
        This event is triggered for every channel deletion.
        If the channel that got deleted was an open application, close it.
        '''
        app = zerobot_common.applications.get_app(channel.id)
        if (app == None):
            # not an app channel
            return
        if (app.fields_dict.get('status') != 'open'):
            # already accepted or closed
            return
        # is still open app channel, close it
        app.set_status('closed')
        # clear permissions for channel
        zerobot_common.permissions.disallow('archive', channel.id)
        zerobot_common.permissions.disallow('accept', channel.id)
        zerobot_common.permissions.disallow('cancel', channel.id)
        zerobot_common.permissions.disallow('reject', channel.id)
        zerobot_common.permissions.disallow('sitelink', channel.id)
        # notify applicant of closing channel
        app_type = app.fields_dict['type']
        discord_user = zerobot_common.guild.get_member(app.fields_dict['requester_id'])
        await discord_user.send(f'Your application for {app_type} has been closed. Reason: The channel was removed.')
