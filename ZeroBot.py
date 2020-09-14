import zerobot_common
from discord.ext import commands
from MemberlistCog import MemberlistCog
from ApplicationsCog import ApplicationsCog
from ReactionRolesCog import ReactionRolesCog
from GuidesCog import GuidesCog

# set up the basic discord bot object along with some basic settings
bot = commands.Bot(command_prefix='-zbot ', case_insensitive=True, fetch_offline_members=True, guild_subscriptions=True)
# TODO create our own, for now remove the default help command to hide commands that normal users shouldnt see.
bot.remove_command('help')

@bot.event
async def on_ready():
    '''
    Executed once the bot has connected to discord.
    Saves some critical references to discord objects into common memory for modules to use.
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
    # Find applications category in Zer0 server and load into common
    categories = zerobot_common.guild.categories
    for cat in categories:
        if cat.id == zerobot_common.applications_category_id:
            zerobot_common.applications_category = cat
    # store a lookup dictionary for channel names and their ids
    channels = zerobot_common.guild.channels
    chann_dict = {}
    for chann in channels:
        chann_dict[chann.name] = chann.id
    zerobot_common.discord_channels = chann_dict
    # store a lookup dictionary for role names and their ids
    roles = zerobot_common.guild.roles
    role_dict = {}
    for role in roles:
        role_dict[role.name] = role.id
    zerobot_common.discord_roles = role_dict
    
    # start the different command modules of the bot.
    if (bot.get_cog('MemberlistCog') == None):
        bot.add_cog(MemberlistCog(bot))
    if (bot.get_cog('ReactionRolesCog') == None):
        bot.add_cog(ReactionRolesCog(bot))
    if (bot.get_cog('ApplicationsCog') == None):
        bot.add_cog(ApplicationsCog(bot))
    if (bot.get_cog('GuidesCog') == None):
        bot.add_cog(GuidesCog(bot))

# actually start the bot
bot.run(zerobot_common.auth_token)