from discord.ext import commands
import zerobot_common

logfile = None
log_prefix = "serverwatch"

    
async def on_guild_channel_delete(channel):
    """
    This event is triggered for every channel deletion.
    logs / reports the deletion and creates an archived copy of the channel.
    """
    logfile.log(f"{channel.name} channel {channel.id} deleted", log_prefix)

class ServerWatchCog(commands.Cog):
    """
    Watches the discord server and reports / logs mod actions.
    """
    def __init__(self, bot):
        """
        Starts the module that manages events and event commands.
        """
        self.bot = bot
        global logfile
        logfile = zerobot_common.logfile
        logfile.log(f"server watch module loaded and ready.", log_prefix)

        bot.channel_delete_callbacks.append(on_guild_channel_delete)