import zerobot_common
import discord
import traceback
from discord import Intents
from discord.ext import commands
from MemberlistCog import MemberlistCog
from ApplicationsCog import ApplicationsCog
from ReactionRolesCog import ReactionRolesCog
from GuidesCog import GuidesCog
from DropCompCog import DropCompCog
from ForumThreadCog import ForumThreadCog
from FunResponsesCog import FunResponsesCog
from EventsCog import EventsCog

intents = Intents.default()
intents.members = True
intents.messages = True

# set up the basic discord bot object along with some basic settings
bot = commands.Bot(
    command_prefix = "-zbot ",
    intents = intents,
    case_insensitive = True,
    fetch_offline_members = True,
    guild_subscriptions = True
)
# remove the default help command to hide commands that shouldnt be seen.
bot.remove_command("help")
# TODO create our own help command instead...

@bot.event
async def on_ready():
    """
    Executed once the bot has connected to discord.
    Saves some critical references into common memory for modules to use.
    Then loads the cog modules that define what the bot does.
    """
    # list servers that bot connected to
    for g in bot.guilds:
        zerobot_common.logfile.log(f"connected to {g.name} : {g.id}")
    
    # Find clan server in list of servers the bot is in and load into common
    zerobot_common.guild = bot.get_guild(zerobot_common.clan_server_id)
    if (zerobot_common.guild == None):
        zerobot_common.logfile.log(
            f"not connected to clan server id in settings: "
            f"{zerobot_common.clan_server_id}"
        )
        return
    # Find default bot channel and load into common
    zerobot_common.bot_channel = zerobot_common.guild.get_channel(
        zerobot_common.bot_channel_id
    )
    # store a lookup dictionary for channel names and ids
    channels = zerobot_common.guild.channels
    chann_dict = {}
    for chann in channels:
        chann_dict[chann.name] = chann.id
    zerobot_common.discord_channels = chann_dict
    
    # start the different command modules of the bot.
    if bot.get_cog("MemberlistCog") == None:
        bot.add_cog(MemberlistCog(bot))
    if bot.get_cog("ReactionRolesCog") == None:
        bot.add_cog(ReactionRolesCog(bot))
    if bot.get_cog("ApplicationsCog") == None:
        if zerobot_common.applications_enabled:
            bot.add_cog(ApplicationsCog(bot))
    if bot.get_cog("GuidesCog") == None:
        bot.add_cog(GuidesCog(bot))
    if bot.get_cog("EventsCog") == None:
        if zerobot_common.events_enabled:
            bot.add_cog(EventsCog(bot))
    if bot.get_cog("DropCompCog") == None:
        if zerobot_common.dropcomp_enabled:
            bot.add_cog(DropCompCog(bot))
    if bot.get_cog("ForumThreadCog") == None:
        if zerobot_common.forumthread_enabled:
            bot.add_cog(ForumThreadCog(bot))
    if bot.get_cog("FunResponsesCog") == None:
        if zerobot_common.funresponses_enabled:
            bot.add_cog(FunResponsesCog(bot))

@bot.event
async def on_command_error(ctx, error):
    """
    This event executes whenever the bot encounters an unhandled error.
    """
    # send simple message to location the error came from.
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send(error)
    else:
        await ctx.send("An error occured.")
    # write down full error trace in log files on disk.
    zerobot_common.logfile.log(f"Error in command : {ctx.command}")
    zerobot_common.logfile.log(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

# actually start the bot
bot.run(zerobot_common.auth_token)