import zerobot_common
from utilities import load_json, dateformat, timeformat
from discord.ext import commands
from logfile import LogFile
from datetime import datetime

# start log for guides module
guideslog_filename = 'logs/guideslog' + datetime.utcnow().strftime(dateformat)
guideslog = LogFile(guideslog_filename)
# load config that describes which channels contain which guides
guidechannels_filename = 'guide_channels.json'
guidechannels = load_json(guidechannels_filename)

class GuidesCog(commands.Cog):
    '''
    Handles guide channels and commands related to guides.
    '''
    def __init__(self, bot):
        self.bot = bot
        for channel in guidechannels:
            guide_name = guidechannels[channel]

    @commands.command()
    async def reloadguides(self, ctx):
