"""
Main Zerobot file

Starts up the bot using the discord credentials.
Loads up any modules (Cogs) that have been enabled in settings.json
"""
import zerobot_common
import discord
from discord import Intents
from discord.ext import tasks, commands
from discord import app_commands
from discord import Interaction
from datetime import datetime
from utilities import timeformat
import asyncio
# required, might appear unused in editor as they are added based on settings. 
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

class Zer0Bot(commands.Bot):
    def __init__(self):

        # newer discord req, need to signal what extra data we intend to access
        intents = Intents.default()
        intents.members = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix = "-zbot ",
            intents = intents,
            case_insensitive = True,
            fetch_offline_members = True,
            guild_subscriptions = True
        )

        self.initial_startup = True

        # callback structures for discord events and daily task scheduler.
        # you can add (func, arglist) pairs, arglist = [arg1, ... , argn] to be called
        # when the event / daily update happens, very practical.
        # see __init__ of MemberlistCog for some callback function examples

        # this is a workaround for discord.py only allowing one event handler function 
        # per events, it's nice for modularity to be able to use multiple.

        # try to be EFFICIENT in your callback functions, the bot has to run EVERY
        # callback function once each time that type of event that occurs...
        self.channel_delete_callbacks = []
        self.on_message_callbacks = []
        self.daily_callbacks = []

        # remove the default help command to hide commands that shouldnt be seen.
        self.remove_command("help")
            # TODO create our own help commands instead...
    
    async def on_ready(self):
        """
        Executed once the bot has connected to discord.
        Saves some critical references into common memory for modules to use.
        Then loads the cog modules that define what the bot does.
        """
        await self.wait_until_ready()

        # list servers that bot connected to
        for g in self.guilds:
            zerobot_common.logfile.log(f"connected to {g.name} : {g.id}")
        
        # Find clan server in list of servers the bot is in and load into common
        zerobot_common.guild = self.get_guild(zerobot_common.clan_server_id)
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
        zerobot_common.bot_channel2 = zerobot_common.guild.get_channel(
            zerobot_common.bot_channel2_id
        )
        # store a lookup dictionary for channel names and ids
        channels = zerobot_common.guild.channels
        chann_dict = {}
        for chann in channels:
            chann_dict[chann.name] = chann.id
        zerobot_common.discord_channels = chann_dict

        # start loading all enabled modules e.g. "MemberlistCog"
        for module_name in zerobot_common.enabled_modules:
            if self.get_cog(module_name) == None:
                await self.add_cog(globals()[module_name](bot), guild = zerobot_common.guild)


        if self.initial_startup:
            # sync our changes to slash commands
            await self.tree.sync(guild = discord.Object(id=zerobot_common.clan_server_id))

            # just a simple message in the main channel indicating bot is online.
            await zerobot_common.bot_channel.send("Zbot is awake and ready to overtake the world! <:king:784092626903236678>")
        
            self.initial_startup = False

        # make sure daily update loop is running
        try:
            daily_update_scheduler.start()
        except Exception as e:
            # log failures - usually because it is already running
            zerobot_common.logfile.log("Error starting daily scheduler")
            zerobot_common.logfile.log_exception(e)

bot = Zer0Bot()
tree = bot.tree

"""
It is possible to define text commands here using this syntax, but it is better
to add them to one of the cog modules instead (or making a new module)
"""
#@bot.command()
#async def test1(ctx, *args):
    #await ctx.send("Hello")

"""
Slash commands can also be used here, but again recommend to add them to a 
separate module to prevent cluttering in this file:
"""
#@tree.command(guild = discord.Object(id=zerobot_common.clan_server_id), name = 'test', description='testing')
#async def slash2(interaction: Interaction):
    #await interaction.response.send_message(f"I am working!", ephemeral = False)


# using annotation from the discord tasks extension to set up a loop
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