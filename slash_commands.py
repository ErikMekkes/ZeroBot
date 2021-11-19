import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType

from datetime import datetime, timedelta
import zerobot_common
import utilities
from memberlist import memberlist_from_disk, memberlist_get

logfile = None
log_prefix = "slash_commands"

class Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        global logfile
        logfile = zerobot_common.logfile
        logfile.log(f"slash commands module loaded and ready.", log_prefix)
    @cog_ext.cog_slash(
        name = "host_stats",
        description = (
            "Check your hosting stats in clan or add @someone to check theirs."
        ),
        guild_ids = [zerobot_common.clan_server_id],
        default_permission = True,
        options = [
            create_option(
                name = "member",
                description = "@ a clan member if you want to check theirs",
                required = False,
                option_type = 6,
            )
        ],
        permissions = {},
    )
    async def host_stats(
        self, ctx: SlashContext, member: discord.User = None
    ):
        # signal to discord that our response might take time
        await ctx.defer()

        if member is None:
            msg = "Your hosting stats "
            member = ctx.author
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
        await ctx.send(msg)
    
    @cog_ext.cog_slash(
        name = "known_inactive",
        description = (
            "Lets you set a current member as known inactive "
            "for a number of days"
        ),
        guild_ids = [zerobot_common.clan_server_id],
        default_permission = False,
        options = [
            create_option(
                name = "member",
                description = "current member to set as known inactive",
                required = True,
                option_type = 6
            ),
            create_option(
                name = "days",
                description = "number of days the member will be inactive",
                required = True,
                option_type = 4
            )
        ],
        permissions = {
            zerobot_common.clan_server_id: [
                create_permission(
                    zerobot_common.staff_role_id,
                    SlashCommandPermissionType.ROLE,
                    True)
            ]
        }
    )
    async def known_inactive(
        self, ctx: SlashContext, member: discord.User, days: int
    ):
        """
        Sets a member as known inactive for a number of days.
        Allowed for owner/admin/staff member, in any channel.
        """
        # signal to discord that our response might take time
        await ctx.defer()

        memblist = self.bot.get_cog("MemberlistCog")
        if memblist is None:
            await ctx.send("zbot error: memberlist module not found.")
            logfile.log("memberlist module not found")
            return
        
        list_access = await memblist.lock()

        memb = memberlist_get(list_access["current_members"], member.id)
        if memb is None:
            memb = memberlist_get(
                list_access["current_members"], member.display_name
            )
            if memb is None:
                await ctx.send(
                    f"No current member found in memberlist for "
                    f" {member.id}:{member.display_name}."
                )
                await memblist.unlock()
                return
        today_date = datetime.utcnow()
        newdate =  today_date + timedelta(days)
        memb.last_active = newdate

        await memblist.unlock()

        await ctx.send(
            f"I have set the last active date of {memb.name} to {days} days "
            f"from now ({newdate.strftime(utilities.dateformat)}). They "
            f"will not show up on the inactives list until after this date."
        )

def setup(bot):
    bot.add_cog(Slash(bot))