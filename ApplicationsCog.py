"""
Standalone Module, but very complex setup.
This module lets you configure a channel that people can request applications
in. The bot creates a new channel for each application under a preset category.
The applicant will be given access to post in that channel by the bot.
Use the category settings in discord to set the permissions for the others who 
may need access to react to applications, the new channels created by the bot 
will take over those settings from the category to give them access.

Idea of this file is simple, provide commands (guest, join, rankup) to start
apps in the app request channel and commands (accept, reject, archive, cancel)
to manage applications in each newly created application channel. Each type of
app that can be started has its own accept_type function, that tells the bot
what to do to accept them.

On its own, this module will just manage their discord ranks. If you have the
memberlist or siteops modules enabled it will also update their status there.

Config required for this module:
 - check discord ranks setup in zerobot_common
 - check these settings in settings.json:
   - clan_server_id
   - applications_category_id
   - app_requests_channel_id
   - default_bot_channel_id
   - discord rank ids for ranks
   - check if site / memberlist module enabled, and their settings if so
 - check the setup below for this module
"""
from discord.ext import commands
import discord
import chat_exporter

import zerobot_common
import utilities

from utilities import message_ctx, rank_index
from logfile import LogFile
from permissions import Permissions
from application import Application
from applications import Applications
from exceptions import BannedUserError, ExistingUserWarning
from rankchecks import rank_parser, discord_rank_parser, disallowed_rankups
from memberlist import memberlist_get
from member import valid_profile_link

# number of votes required for accepting applications
votes_for_guest = 1
votes_for_join = 3
votes_for_rankup = 2

# The remaining ones below are automated, you shouldnt have to change anything
# there. But you can edit permissions / applications .json files by hand if
# something went wrong that cant be fixed with a command.

# logfile for applications
app_log = LogFile("logs/applications")
# load permissions for use of commands in application channels from disk
permissions_filename = "applications/application_permissions.json"
permissions = Permissions(permissions_filename)
app_log.log("application permissions system loaded and ready.")
# load applications status from disk
applications_filename = "applications/applications.json"
applications = Applications(applications_filename)

# channel that allows application commands and gets cleared typing after them.
app_req_channel_id = zerobot_common.settings.get("app_requests_channel_id")
# discord category that new application channels should be created under
# loaded on bot start from guild object using app_category_id.

staff_app_category_id = zerobot_common.settings.get("staffapplications_category_id")
staff_app_category = None

app_category_id = zerobot_common.settings.get("applications_category_id") 
app_category = None

# message for non members who try to rankup instead of join
join_before_rankup_message = (
    "You have to join the clan first before you can rank up :) \n"
    "Use `-zbot join` to join the clan, or `-zbot guest` to register as a guest for now."
)
app_not_found_msg = "Could not find a related application for this channel."
channel_creation_message = (
    "I have a created a channel for your application on the Zer0 Discord "
    "server, please go to : "
)

async def set_applicant_permissions(ctx, channel):
    """
    Allows the applicant to use the channel.
    """
    await channel.set_permissions(
        ctx.author,
        view_channel=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_external_emojis=True,
        add_reactions=True
    )

async def setup_app_channel(ctx, channel, app_type):
    """
    Set up an application channel. Sets the required permissions and starts it
    off with a generic message and any messages defined for the app.
    """
    # set up permissions for applicant to be able to use channel.
    await set_applicant_permissions(ctx, channel)
    # set up permissions for bot commands in channel
    permissions.allow("archive", channel.id)
    permissions.allow("accept", channel.id)
    permissions.allow("reject", channel.id)
    permissions.allow("cancel", channel.id)
    permissions.allow("sitelink", channel.id)
    # start the app channel with a basic message
    msg = (f"Hello {ctx.author.mention}! "
        + utilities.read_file("application_templates/app_base_message"))
    await channel.send(msg)
    # send all the messages belonging to the channel type
    await utilities.send_messages(
        channel,
        f"application_templates/{app_type}_messages.json"
    )

async def setup_staff_app_channel(ctx, channel):
    """
    - hides channel from non-staff
    - disallows typing for staff until opened for comments
    """
    # set up permissions for applicant to be able to use channel.
    await set_applicant_permissions(ctx, channel)
    # remove channel permissions for @everyone
    await channel.set_permissions(
        zerobot_common.guild.default_role,
        view_channel=False
    )
    # make sure staff can still see the channel
    await channel.set_permissions(
        zerobot_common.guild.get_role(zerobot_common.staff_role_id),
        view_channel=True
    )
    # start the app channel with a basic message
    msg = (
        f"Hello {ctx.author.mention}! Please ask / answer questions "
        f"about your application here."
    )
    await channel.send(msg)
    # send all the messages belonging to the channel type
    await utilities.send_messages(
        channel,
        "application_templates/staff_member_messages.json"
    )
    permissions.allow("archive", channel.id)

async def on_guild_channel_delete(channel):
    """
    This event is triggered for every channel deletion.
    If the channel that got deleted was an open application, close it.
    """
    app = applications.get_app(channel.id)
    if app == None:
        # not an app channel
        return
    if app.fields_dict.get("status") != "open":
        # already accepted or closed
        return
    # is still open app channel, close it
    app.set_status("closed")
    # clear app permissions for channel
    permissions.disallow("archive", channel.id)
    permissions.disallow("accept", channel.id)
    permissions.disallow("cancel", channel.id)
    permissions.disallow("reject", channel.id)
    permissions.disallow("sitelink", channel.id)
    # notify applicant of closing channel
    app_type = app.fields_dict["type"]
    discord_user = zerobot_common.guild.get_member(app.fields_dict["requester_id"])
    await message_ctx(discord_user, f"Your application for {app_type} has been closed. Reason: The channel was removed.")

class ApplicationsCog(commands.Cog):
    """
    Handles all the commands for applications.
    """
    def __init__(self, bot):
        self.bot = bot
        app_log.log("Applications cog loaded and ready.")

        # Find applications category in Zer0 server and store it
        categories = zerobot_common.guild.categories
        for cat in categories:
            if cat.id == app_category_id:
                global app_category
                app_category = cat
        for cat2 in categories:
            if cat.id == staff_app_category_id:
                global staff_app_category
                staff_app_category = cat2
        bot.channel_delete_callbacks.append(on_guild_channel_delete)

    @commands.command()
    async def rankup(self, ctx, *args):
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(ctx.channel.id == app_req_channel_id): return

        # return if not joined yet
        if not zerobot_common.is_member(ctx.author):
            await ctx.send(join_before_rankup_message)
            return
        # return if wrong format
        if (len(args) < 1):
            await ctx.send(f"Use: `-zbot rankup <rank>`")
            return
        # return if already has an open app
        open_app = applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await message_ctx(ctx.author, f"You already have an open application at <#{open_app.channel_id}>", alt_ctx=ctx)
            return
        # parse name, validity checked later with possible rankups
        rank_name = "_".join(args).lower()
        rank_name = rank_parser.get(rank_name, rank_name)
        discord_rank_name = discord_rank_parser.get(rank_name, rank_name)

        # create a copy of discord ranks
        possible_rankups = {}
        discord_ranks_copy = zerobot_common.discord_rank_ids.copy()
        # remove ranks that can not be applied for
        for r_id, r_name in discord_ranks_copy.items():
            if r_name not in disallowed_rankups:
                possible_rankups[r_id] = r_name
        current_rank = rank_index(discord_user=ctx.author)
        lower_rank_ids = list(zerobot_common.discord_rank_ids.keys())[current_rank:]
        # remove ranks that are equal to or lower than the users current rank
        for r_id in lower_rank_ids:
            try:
                possible_rankups.pop(r_id)
            except KeyError as e:
                app_log.log_exception(e, ctx)
                pass
        # reverse to list most likely rankup first
        possible_rankups = list(possible_rankups.values())
        possible_rankups.reverse()
        # return if rank is not a possible rankup for this discord user
        if (not discord_rank_name in possible_rankups):
            msg = f"You can not apply for {discord_rank_name}, the ranks you can apply for are:"
            for r_name in possible_rankups:
                msg += f" {r_name},"
            msg = msg[:-1]
            await ctx.send(msg)
            return
        
        # actually start making the application
        #channel = await zerobot_common.guild.create_text_channel(
        #    f"{rank_name}-{ctx.author.display_name}",
        #    category=app_category,
        #    reason="rankup"
        #)

        # staff apps are handled differently.
        if rank_name == "staff_member":
            # makes the staff application channels under the staff_app_category id(only staff applications)
            channel = await zerobot_common.guild.create_text_channel(
                f"{rank_name}-{ctx.author.display_name}",
                category=staff_app_category,
                reason="rankup"
            )
            await setup_staff_app_channel(ctx, channel)
        else:
            # makes the normal application channels under the app_category id(all applications)
            channel = await zerobot_common.guild.create_text_channel(
                f"{rank_name}-{ctx.author.display_name}",
                category=app_category,
                reason="rankup"
            )
            await setup_app_channel(ctx, channel, rank_name)
            # register the application and update copy on disk
            # TODO track rank id instead of name (or both, but use id)
            rankup_app = Application(
                channel.id,
                ctx.author.id,
                type = "rankup",
                rank = discord_rank_name,
                votes_required = votes_for_rankup
            )
            applications.append(rankup_app)
        # tell applicant the app is created with link
        await message_ctx(ctx.author, channel_creation_message + channel.mention)
        # clean the app requests channel for new requests
        await self.clean_app_requests(ctx)


    @commands.command()
    async def join(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(ctx.channel.id == app_req_channel_id) : return

        # return if already has an open app
        open_app = applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await message_ctx(ctx.author, f"You already have an open application at <#{open_app.channel_id}>", alt_ctx=ctx)
            return

        # actually start making the application
        channel = await zerobot_common.guild.create_text_channel(
            f"join-{ctx.author.display_name}",
            category=app_category,
            reason="joining"
        )
        await setup_app_channel(ctx, channel, "join")
        await message_ctx(ctx.author, channel_creation_message + channel.mention)
        # register the application and update copy on disk
        join_app = Application(
            channel.id,
            ctx.author.id,
            type="join",
            votes_required=votes_for_join
        )
        applications.append(join_app)
        # clean the app requests channel for new requests
        await self.clean_app_requests(ctx)

        name = ctx.author.display_name
        join_app.fields_dict["name"] = name

        # check if banned or returning member and post extra info.
        if zerobot_common.memberlist_enabled:
            memblist = self.bot.get_cog("MemberlistCog")
            # do background check
            try:
                await memblist.background_check_app(zerobot_common.bot_channel, join_app)
                # passed, post confirm of no issues in bot channel
                msg = (
                    f"Join app opened for {ctx.author.display_name}: "
                    "They are not on the banlist and I do not recognize them "
                    "as an ex-clanmember.")
                await zerobot_common.bot_channel.send(msg)
            except BannedUserError:
                # on banlist, post error in app and full info in bot channel
                await channel.send(f"_ _\n⛔ There is a problem with this app, please check the staff bot channel. ⛔\n_ _")
                await zerobot_common.bot_channel.send(
                    f"Join app opened for {ctx.author.display_name}. "
                    f"Can not accept a ⛔ Banned Member ⛔. \n"
                    f"They need to appeal their ban status first through <@&308529829672910848> "
                    f"and need to be removed from the banlist by them first.\n"
                    f"Remove their ban with: `-zbot removemember banned_members id`\n"
                    f"  id: ingame name, discord_id or profile_link\n"
                    f"you can retry accepting the app after Clan Issues resolved the ban."
                )
                return
            except ExistingUserWarning:
                # possible previous member, might need full memb reqs
                # post full member reqs in app and member info in bot channel
                await channel.send(
                    f"\n\n☝ {name} may have been a previous member, I have posted similar results in the staff bot channel ☝\n"
                )
                await zerobot_common.bot_channel.send(
                    f"☝ Join app opened for {ctx.author.display_name} ☝: "
                    f"They are not on the banlist, but I found similar member results above for them on the spreadsheet, you may want to check those. "
                )
        else:
            await zerobot_common.bot_channel.send(
                f"Join app opened for {ctx.author.display_name}: "
                f"Failed to check memberlist, could not check if they were a "
                f"previous member or if they are on the banlist."
            )
    
    async def clean_app_requests(self, ctx):
        """
        Purges all messages from the app_requests channel and reposts the instructions.
        """
        # IMPORTANT check if in app_requests, if in a different channel do nothing!
        if not(ctx.channel.id == app_req_channel_id) : return

        # clear all previous messages from the channel
        await ctx.channel.purge()

        # send all the messages belonging to the channel type
        await utilities.send_messages(
            ctx.channel, "application_templates/app_requests_messages.json"
        )
    
    @commands.command()
    async def guest(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(ctx.channel.id == app_req_channel_id) : return

        open_app = applications.has_open_app(ctx.author.id)
        if (open_app != None):
            await message_ctx(ctx.author, f"You already have an open application at <#{open_app.channel_id}>", alt_ctx=ctx)
            return
        
        channel = await zerobot_common.guild.create_text_channel(
            f"guest-{ctx.author.display_name}",
            category=app_category,
            reason="guesting"
        )
        await setup_app_channel(ctx, channel, "guest")
        await message_ctx(ctx.author, channel_creation_message + channel.mention)

        # register the application and update copy on disk
        guest_app = Application(channel.id, ctx.author.id)
        applications.append(guest_app)
        await self.clean_app_requests(ctx)

        name = ctx.author.display_name
        guest_app.fields_dict["name"] = name
        # check if banned or returning member and post extra info.
        if zerobot_common.memberlist_enabled:
            memblist = self.bot.get_cog("MemberlistCog")
            # do background check
            try:
                await memblist.background_check_app(zerobot_common.bot_channel, guest_app)
                # passed, post confirm of no issues in bot channel
                msg = (
                    f"Guest app opened for {ctx.author.display_name}: "
                    "They are not on the banlist and I do not recognize them "
                    "as an ex-clanmember.")
                await zerobot_common.bot_channel.send(msg)
            except BannedUserError:
                # on banlist, post error in app and full info in bot channel
                await channel.send(f"_ _\n⛔ There is a problem with this app, please check the staff bot channel. ⛔\n_ _")
                await zerobot_common.bot_channel.send(
                    f"Guest app opened for {ctx.author.display_name}. "
                    f"Can not accept a ⛔ Banned Member ⛔. \n"
                    f"They need to appeal their ban status first through <@&308529829672910848> "
                    f"and need to be removed from the banlist by them first.\n"
                    f"Remove their ban with: `-zbot removemember banned_members id`\n"
                    f"  id: ingame name, discord_id or profile_link\n"
                    f"you can retry accepting the app after Clan Issues resolved the ban."
                )
                return
            except ExistingUserWarning:
                # possible previous member, just post their info
                await channel.send(
                    f"_ _\nYou may have been a previous member. I tried to post info that could help in the staff bot channel.\n"
                )
                await zerobot_common.bot_channel.send(
                    f"Guest app opened for {ctx.author.display_name}: "
                    f"They are not on the banlist, but I found previous member results above for them on the spreadsheet, you may want to check / remove those. "
                )
        else:
            await zerobot_common.bot_channel.send(
                f"Guest app opened for {ctx.author.display_name}: "
                f"Failed to check memberlist, could not check if they were a "
                f"previous member or if they are on the banlist."
            )
    
    @commands.command()
    async def archive(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(
            permissions.is_allowed("archive", ctx.channel.id) or 
            zerobot_common.permissions.is_allowed("archive", ctx.channel.id) or
            (
                zerobot_common.is_staff_member(ctx.author) and
                ctx.channel.id not in zerobot_common.archive_blacklist
            )
        ):
            await ctx.send("Not allowed in this channel!")
            return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send("I will copy all the posts to the archive, but will not delete the channel.")
        elif (app.fields_dict["status"] == "open"):
            await ctx.send(
                "This application has not been accepted or rejected yet! "
                "Use `-zbot accept` or `-zbot reject`"
            )
            return
        
        filedir = f"applications/{ctx.channel.id}-{ctx.channel.name}/"
        await chat_exporter.local_export(ctx.channel, zerobot_common.guild, None, "UTC", filedir)

        if (app == None):
            await ctx.send("Finished archiving all the posts!")
            # clear permissions for channel (archive once)
            permissions.disallow("archive", ctx.channel.id)
            zerobot_common.permissions.disallow("archive", ctx.channel.id)
        else:
            await ctx.channel.delete(reason="archived")
            # clear permissions for application
            permissions.disallow("archive", ctx.channel.id)
            permissions.disallow("accept", ctx.channel.id)
            permissions.disallow("cancel", ctx.channel.id)
            permissions.disallow("reject", ctx.channel.id)
            permissions.disallow("sitelink", ctx.channel.id)
    
    @commands.command()
    async def sitelink(self, ctx, profile_link):
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(permissions.is_allowed("sitelink", ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send(app_not_found_msg)
            return
        app.set_site(profile_link)
        await ctx.send("Updated their site account link.")
    
    @commands.command()
    async def accept(self, ctx):
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(permissions.is_allowed("accept", ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send(app_not_found_msg)
            return
        
        if (app.fields_dict["requester_id"] == ctx.author.id):
            await ctx.send(f"You can not accept your own application!")
            return
        status = app.fields_dict["status"]
        if (status != "open"):
            await ctx.send(
                f"This application is already {status}. If you want to make "
                f"a change you will have to edit the member manually."
            )
            return
        
        num_votes = len(app.fields_dict["voters"])
        votes_required = app.fields_dict["votes_required"]
        if (app.add_vote(ctx.author.id)):
            num_votes += 1
            await ctx.send(
                f"Added your vote to accept this application, the application"
                f" now has {num_votes} of the {votes_required} required votes"
            )
        else:
            await ctx.send(
                f"You have already voted to accept this application, the "
                f"application has {num_votes} of the {votes_required} "
                f"required votes"
            )
        
        if (num_votes >= votes_required):
            app.set_status("accepted")
            app_type = app.fields_dict["type"]
            accept_func = f"accept_{app_type}"
            new_name = f"{ctx.channel.name}-accepted"
            # run accept func, it can fail which resets the app to open
            await getattr(self, accept_func)(ctx, app)
            # only update channel name if accept func was successful.
            if app.fields_dict["status"] == "accepted":
                await ctx.channel.edit(name=new_name)
            return
    
    async def accept_guest(self, ctx, app):
        """
        Accept guest application = give guest role, remove applicant role.
        Assumes they are new, and do not need check / removal of other roles.
        """
        discord_id = app.fields_dict["requester_id"]
        discord_user = zerobot_common.guild.get_member(discord_id)
        name = discord_user.display_name
        app.fields_dict["name"] = name

        # do background check
        if zerobot_common.memberlist_enabled:
            memblist = self.bot.get_cog("MemberlistCog")
            try:
                await memblist.background_check_app(zerobot_common.bot_channel, app)
                await zerobot_common.bot_channel.send(
                    f"Accepted {name} as guest."
                )
            except BannedUserError:
                # banned, report unable to accept
                await ctx.send(f"_ _\n⛔ There is a problem with this app, please check the staff bot channel. ⛔\n_ _")
                app.set_status("open")
                zerobot_common.bot_channel.send(
                    f"Can not accept {name} as guest. ⛔ Banned Member ⛔."
                    f"They need to appeal their ban status first through <@&308529829672910848> "
                    f"and need to be removed from the banlist by them first.\n"
                    f"Remove their ban with: `-zbot removemember banned_members id`\n"
                    f"  id: ingame name, discord_id or profile_link\n"
                    f"you can retry accepting the app after Clan Issues resolved the ban."
                )
                return
            except ExistingUserWarning:
                await zerobot_common.bot_channel.send(
                    f"Accepted {name} as guest: "
                    f"They are not on the banlist, but I found previous member results above for them on the memberlist, you may want to check / remove those."
                )
        else:
            await zerobot_common.bot_channel.send(
                f"Accepted {name} as guest, but failed to check memberlist, "
                f"could not check if they were a previous member or if they are on the banlist."
            )

        # add guest role
        guest_id = zerobot_common.guest_role_id
        guest_role = zerobot_common.guild.get_role(guest_id)
        await discord_user.add_roles(guest_role, reason="accepted guest")
        # remove lower roles
        roles_to_remove = zerobot_common.get_lower_ranks(discord_user, zerobot_common.guest_rank_index)
        await discord_user.remove_roles(*roles_to_remove, reason="accepted guest")

        await message_ctx(
            discord_user, 
            f"Your application for Guest in the Zer0 discord was accepted :)"
        )
        await ctx.send(
            f"Application for Guest accepted :). \n You can continue to talk "
            f"in this channel until it is archived."
        )
    
    async def accept_join(self, ctx, app):
        """
        Accept join application = give new member role, remove applicant role.
        + if enabled, instruct memberlist module to add the member.
        """
        # update name with latest discord name right before adding to list
        discord_id = app.fields_dict["requester_id"]
        discord_user = zerobot_common.guild.get_member(discord_id)
        name = discord_user.display_name
        app.fields_dict["name"] = name

        message = f""

        if zerobot_common.memberlist_enabled:
            memblist = self.bot.get_cog("MemberlistCog")
            # do background check
            try:
                await memblist.background_check_app(zerobot_common.bot_channel, app)
                await zerobot_common.bot_channel.send(
                    f"Accepted {name}. They are not on the banlist and I do not recognize them "
                    "as an ex-clanmember"
                )
            except BannedUserError:
                await ctx.send(f"_ _\n⛔ There is a problem with this app, please check the staff bot channel. ⛔\n_ _")
                app.set_status("open")
                zerobot_common.bot_channel.send(
                    f"Can not accept {name} joining. ⛔ Banned Member ⛔. "
                    f"They need to appeal their ban status first through <@&308529829672910848> "
                    f"and need to be removed from the banlist by them first.\n"
                    f"Remove their ban with: `-zbot removemember banned_members id`\n"
                    f"  id: ingame name, discord_id or profile_link\n"
                    f"you can retry accepting the app after Clan Issues resolved the ban."
                )
                return
            except ExistingUserWarning:
                await zerobot_common.bot_channel.send(
                    f"Accepted {name}. They are not on the banlist, but I still found previous member results above for them on the spreadsheet, you may want to check / remove those. "
                )
            # add member to memberlist
            await memblist.add_member_app(zerobot_common.bot_channel, app)
            message += f"I have added them to the memberlist spreadsheet. "
            # post 10 least active people that were not active in last 30 days
            await memblist.post_inactives(zerobot_common.bot_channel, 30, 15)
            await memblist.post_need_full_reqs(zerobot_common.bot_channel)
        else:
            await zerobot_common.bot_channel.send(
                f"Accepted {name}. But failed to check memberlist, could not check if they were a previous member or if they are on the banlist."
            )

        # add generic clan member role
        clan_member_role = zerobot_common.guild.get_role(zerobot_common.clan_member_role_id)
        await discord_user.add_roles(clan_member_role, reason="accepted member")
        # add joined rank role
        join_role = zerobot_common.guild.get_role(zerobot_common.join_role_id)
        await discord_user.add_roles(join_role, reason="accepted member")
        # remove lower ranked roles
        roles_to_remove = zerobot_common.get_lower_ranks(discord_user, zerobot_common.join_rank_index)
        await discord_user.remove_roles(*roles_to_remove, reason="accepted member")
        message += (
            f" I have given them the {join_role.name} rank on discord and "
            f"removed their previous lower rank(s)."
        )
        
        # if the site link was set in the app try updating it already
        profile_link = app.fields_dict["profile_link"]
        if zerobot_common.site_enabled and profile_link != "no site":
            if valid_profile_link(profile_link):
                zerobot_common.siteops.setrank(profile_link, join_role.name)
            else:
                txt = (
                    f"invalid site profile set while accepting app: "
                    f"{profile_link}, can not set site rank."
                )
                app_log.log(txt)
                await zerobot_common.bot_channel.send(txt)

        # send welcome messages
        await send_accepted_messages(discord_user, ctx)

        message += (
            f" I have also sent them info on notify tags, dpm tags, and links to "
            f"all the useful pvm info / discords. \n\nYou still need to "
            f"invite them ingame. I have asked them to look for an invite."
        )
        await zerobot_common.bot_channel.send(message)
    
    async def accept_rankup(self, ctx, app):
        """
        Accept rankup application = Remove member's old role, give new role.
        + if enabled, instruct memberlist module to change the member's rank.
        """
        discord_id = app.fields_dict["requester_id"]
        discord_user = zerobot_common.guild.get_member(discord_id)
        # check against editing staff
        if zerobot_common.is_staff_member(discord_user):
            await ctx.send(
                f"Trying to edit a Staff Member, "
                f"bot is not allowed to edit Staff Members"
            )
            return
        new_rank_name = app.fields_dict["rank"]
        new_rank_id = zerobot_common.get_rank_id(new_rank_name)
        new_rank_index = rank_index(discord_role_id=new_rank_id)
        # lower staff rank index = higher rank
        if new_rank_index <= zerobot_common.staff_rank_index:
            await ctx.send(
                f"Trying to give someone a Staff Rank, "
                f"bot is not allowed to edit Staff Members"
            )
            return
        # add new rank role
        new_rank_role = zerobot_common.guild.get_role(new_rank_id)
        await discord_user.add_roles(new_rank_role, reason="member rankup")
        # remove lower ranks
        roles_to_remove = zerobot_common.get_lower_ranks(discord_user, new_rank_index)
        await discord_user.remove_roles(*roles_to_remove, reason="accepted guest")

        await message_ctx(discord_user, f"Your application for {new_rank_name} was accepted :)")
        await ctx.send(f"Rankup application to {new_rank_name} accepted :)\n You can continue to talk in this channel until it is archived.")

        # if the site link was set in the app try updating it already
        profile_link = app.fields_dict["profile_link"]
        if zerobot_common.site_enabled and profile_link != "no site":
            if valid_profile_link(profile_link):
                zerobot_common.siteops.setrank(profile_link, new_rank_name)
            else:
                txt = (
                    f"invalid site profile set while accepting rankup: "
                    f"{profile_link}, can not set site rank."
                )
                app_log.log(txt)
                await zerobot_common.bot_channel.send(txt)

        # try to update rank on memberlist and site if not done yet
        if zerobot_common.memberlist_enabled:
            memblist = self.bot.get_cog("MemberlistCog")
            lists = await memblist.lock()
            member = memberlist_get(lists["current_members"], discord_id)
            if member is not None:
                member.discord_rank = new_rank_name
                # update to the more recent profile link if set through app
                if profile_link != "no site":
                    member.profile_link = profile_link
                # try to update site if not already updated
                elif zerobot_common.site_enabled:
                    if valid_profile_link(member.profile_link):
                        zerobot_common.siteops.setrank_member(
                            member, new_rank_name
                        )
                    else:
                        txt = (
                            f"invalid site profile set while accepting "
                            f"rankup: {profile_link}, can not set site rank."
                        )
                        app_log.log(txt)
                        await zerobot_common.bot_channel.send(txt)
            else:
                await ctx.send(
                    f"{discord_id} not found on current memberlist. "
                    f"Could not edit rank on memberlist or find their "
                    f"profile link to update their site rank.")
            await memblist.unlock()
    
    @commands.command()
    async def reject(self, ctx, *args):
        """
        Rejects an application, can be used by anyone who can type in the channel except the applicant.
        """
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(permissions.is_allowed("reject", ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send(app_not_found_msg)
            return
        if (app.fields_dict["requester_id"] == ctx.author.id):
            await ctx.send(f"You cant reject your own application!")
            return
        status = app.fields_dict["status"]
        if (status != "open"):
            await ctx.send(
                f"This application is already {status}. If you want to make "
                f"a change you will have to edit the member manually."
            )
            return

        reason = ""
        if (len(args) > 0):
            reason = "Reason: " + " ".join(args)
        app.set_status("rejected")
        app_type = app.fields_dict["type"]
        discord_user = zerobot_common.guild.get_member(app.fields_dict["requester_id"])
        await message_ctx(discord_user, f"Your application for {app_type} has been rejected. {reason}")
        await ctx.send(f"Your application for {app_type} has been rejected. {reason}\n You can continue to talk in this channel until it is archived.")

    @commands.command()
    async def cancel(self, ctx, *args):
        """
        Cancels an application, can be used by anyone who can type in the channel.
        Sets app status to close and archives the channel.
        """
        # log command attempt and check if command allowed
        app_log.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(permissions.is_allowed("cancel", ctx.channel.id)) : return

        app = applications.get_app(ctx.channel.id)
        if (app == None):
            await ctx.send(app_not_found_msg)
            return

        reason = ""
        if (len(args) > 0):
            reason = "Reason: " + " ".join(args)
        
        app.set_status("closed")
        app_type = app.fields_dict["type"]
        discord_user = zerobot_common.guild.get_member(app.fields_dict["requester_id"])
        await message_ctx(discord_user, f"Your application for {app_type} has been closed. {reason}")
        await self.archive(ctx)
    
async def send_accepted_messages(discord_user, ctx):
    # send acception message in app channel
    await ctx.send(
        f"Application to join accepted, ready for an ingame invite? :)\n"
        f"You can continue to talk in this channel until it is archived.\n\n"
        f"**Reminder: Our clan is almost always at the ingame member limit! This means we need to make space for new members like you regularly!**\n"
        f"To avoid being kicked and having to re-apply, log in occasionally and do something ingame, or notify us if you plan on going inactive for more than a few weeks."
    )
    # send customizable welcome messages
    await utilities.send_messages(
        discord_user,
        f"application_templates/welcome_messages.json",
        alt_ctx=ctx
    )
    await zerobot_common.bot_channel.send(
        f"I have pmed {discord_user.display_name} on discord that their app "
        f"has been accepted and have sent them the welcome messages."
    )