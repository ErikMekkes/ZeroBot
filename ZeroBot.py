"""
Main Zerobot file

Starts up the bot using the discord credentials.
Loads up any modules (Cogs) that have been enabled in settings.json
"""
import zerobot_common
from discord import Intents
from discord.ext import commands
from discord_slash import SlashCommand
from MemberlistCog import MemberlistCog
from ApplicationsCog import ApplicationsCog
from ReactionRolesCog import ReactionRolesCog
from ChannelCog import ChannelCog
from DropCompCog import DropCompCog
from ForumThreadCog import ForumThreadCog
from FunResponsesCog import FunResponsesCog
from EventsCog import EventsCog
from SubmissionsCog import SubmissionsCog
from ServerWatchCog import ServerWatchCog

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
slash = SlashCommand(bot, sync_commands=True)
bot.load_extension("slash_commands")
# remove the default help command to hide commands that shouldnt be seen.
bot.remove_command("help")
# TODO create our own help command instead...

# setup callback structure for event handler.
bot.channel_delete_callbacks = []

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

    # start loading all enabled modules e.g. "MemberlistCog"
    for module_name in zerobot_common.enabled_modules:
        if bot.get_cog(module_name) == None:
            bot.add_cog(globals()[module_name](bot))

@bot.event
async def on_command_error(ctx, error):
    """
    This event executes whenever the bot encounters an unhandled error.
    """
    # send simple message to location the error came from.
    if isinstance(error, commands.errors.CommandNotFound):
        await ctx.send(error)
    else:
        await ctx.send("An error occured.")
    zerobot_common.logfile.log_exception(error)

@bot.event
async def on_guild_channel_delete(channel):
    for callback in bot.channel_delete_callbacks:
        await callback(channel)

# logging connection status for debugging
@bot.event
async def on_disconnect():
    zerobot_common.logfile.log(f"Bot disconnected.")
@bot.event
async def on_connect():
    zerobot_common.logfile.log(f"Bot connected.")
@bot.event
async def on_resumed():
    zerobot_common.logfile.log(f"Bot session resumed.")

# actually start the bot
bot.run(zerobot_common.auth_token)