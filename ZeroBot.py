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

intents = Intents.default()
intents.members = True

# set up the basic discord bot object along with some basic settings
bot = commands.Bot(command_prefix='-zbot ', intents=intents, case_insensitive=True, fetch_offline_members=True, guild_subscriptions=True)
# TODO create our own, for now remove the default help command to hide commands that normal users shouldnt see.
bot.remove_command('help')

@bot.event
async def on_ready():
    '''
    Executed once the bot has connected to discord.
    Saves some critical references into common memory for modules to use.
    Then loads the cog modules that define what the bot does.
    '''
    # list servers that bot connected to
    for g in bot.guilds:
        zerobot_common.logfile.log(f'connected to {g.name} : {g.id}')
    
    # Find Zer0 server in list of servers bot is connected to and load into common
    zerobot_common.guild = bot.get_guild(zerobot_common.clan_server_id)
    if (zerobot_common.guild == None):
        zerobot_common.logfile.log(f'not connected to clan server id in settings: {zerobot_common.clan_server_id}')
        return
    # store a lookup dictionary for channel names and their ids
    channels = zerobot_common.guild.channels
    chann_dict = {}
    for chann in channels:
        chann_dict[chann.name] = chann.id
    zerobot_common.discord_channels = chann_dict
    
    # start the different command modules of the bot.
    if (bot.get_cog('MemberlistCog') == None):
        bot.add_cog(MemberlistCog(bot))
    if (bot.get_cog('ReactionRolesCog') == None):
        bot.add_cog(ReactionRolesCog(bot))
    if (zerobot_common.enable_applications):
        if (bot.get_cog('ApplicationsCog') == None):
            bot.add_cog(ApplicationsCog(bot))
    if (bot.get_cog('GuidesCog') == None):
        bot.add_cog(GuidesCog(bot))
    bot.add_cog(DropCompCog(bot))

@bot.event
async def on_command_error(ctx, error):
    '''
    This event executes whenever a command encounters an error that isn't handled.
    '''
    # send simple message to location the error came from.
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send(error)
    else:
        await ctx.send('An error occured.')
    # write down full error trace in log files on disk.
    zerobot_common.logfile.log(f'Error in command : {ctx.command}')
    zerobot_common.logfile.log(traceback.format_exception(type(error), error, error.__traceback__))

# actually start the bot
bot.run(zerobot_common.auth_token)