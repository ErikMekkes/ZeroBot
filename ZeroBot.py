"""
Main Zerobot file

Starts up the bot using the discord credentials.
Loads up any modules (Cogs) that have been enabled in settings.json
"""
import zerobot_common
from discord import Intents
from discord.ext import tasks, commands
from discord_slash import SlashCommand
from datetime import datetime
from utilities import timeformat
import asyncio
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
from ReaperCrewCog import ReaperCrewCog

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

# callback structure for channel delete event handler.
# just takes functions, no args available other than channel from event.
bot.channel_delete_callbacks = []
bot.on_message_callbacks = []

# callback structure for daily functions, can be used by other modules 
# to run functions at the daily update time specified in settings
# takes (func, arglist) pairs, arglist = [arg1, ... , argn]
bot.daily_callbacks = []

@tasks.loop(hours=23, reconnect=False)
async def daily_update_scheduler():
    """
    Schedules the daily updates at the time specified in settings.
    """
    # wait remaining time until update after 23h task loop wakes up
    update_time_str = zerobot_common.daily_update_time
    update_time = datetime.strptime(update_time_str, timeformat)
    wait_time = update_time - datetime.utcnow()
    zerobot_common.logfile.log(f"daily update in {wait_time.seconds/3600}h")
    # async sleep to be able to do other stuff until update time
    await asyncio.sleep(wait_time.seconds)

    for func, args in bot.daily_callbacks:
        await func(*args)

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

    # make sure daily update loop is running
    try:
        daily_update_scheduler.start()
    except RuntimeError:
        # loop already running, happens when reconnecting.
        pass

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
@bot.event
async def on_message(message):
    for callback, args in bot.on_message_callbacks:
        await(callback(message, *args))
    await bot.process_commands(message)

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