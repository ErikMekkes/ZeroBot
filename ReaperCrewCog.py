from discord.ext import commands
import discord
from utilities import read_file
import zerobot_common

logfile = None
log_prefix = "reapercrew"
def log(msg):
    logfile.log(msg, log_prefix)

reaper_msg = read_file("reaper_message.txt")

ticket_tool_name = "Zer0Ticket tool"


async def watch_reaper_ticket(message):
    """
    on_message event handler for opened reaper ticket
    """
    # return asap if not reaper ticket
    if message.author.display_name != ticket_tool_name:
        return
    if not "Reaper" in message.content:
        return
    # try to rename channel to ticket opener name
    channel = message.channel
    content = message.content.splitlines()
    id = int(content[0][8:-1])
    username = zerobot_common.guild.get_member(id).display_name
    await channel.edit(name=username)
    # send extra info
    img_file_bytes = open(f"enable_channel_pings.png", "rb")
    discord_img = discord.File(img_file_bytes)
    await channel.send(reaper_msg, file=discord_img)
    img_file_bytes.close()

class ReaperCrewCog(commands.Cog):
    """
    Adds some extra info to channels from reaper ticket tool
    """
    def __init__(self, bot):
        self.bot = bot
        global logfile
        logfile = zerobot_common.logfile
        log(f"reaper crew module loaded and ready.")

        bot.on_message_callbacks.append((watch_reaper_ticket, []))