'''
Enables syncing guide channels with contents posted on a google spreadsheet. Allows multiple
people to collaborate on discord posts for guides.

This module uses some components from other zerobot common for convenience, but everything
related to this google drive guide syncing functionality is in here, except for:
- guideslog_filename in settings.json
- adding the cog module in zerobot.py
'''
import zerobot_common
from discord.ext import commands
from logfile import LogFile
from datetime import datetime
from utilities import load_json

# start log for guides module
guides_doc = zerobot_common.drive_client.open('Discord Guides')
guideslog = LogFile('logs/guideslog')
# load config that describes which channels contain which guides
guidechannels_filename = zerobot_common.settings.get('guidechannels_filename')
guidechannels = load_json(guidechannels_filename)

class Post():
    def __init__(self, text, row, msg=None):
        self.text = text
        self.row = row
        self.msg = msg

def find_post(posts, row):
    for post in posts:
        if post.row == row: return post
    return None

def read_guides_sheet(sheetname):
    zerobot_common.drive_connect()
    sheet = guides_doc.worksheet(sheetname)
    sheet_matrix = sheet.get_all_values()
    posts = []
    num = 1
    for row in sheet_matrix:
        post = Post(row[0], num)
        posts.append(post)
        num += 1
    return posts

class GuidesCog(commands.Cog):
    '''
    Handles guide channels and commands related to guides.
    '''
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def reloadguides(self, ctx):
        for guide_name in guidechannels:
            self.reload_guide(guide_name)

    @commands.command()
    async def reloadguide(self, ctx, guide_name):
        await self.reload_guide(guide_name)
    
    async def reload_guide(self, guide_name):
        channel_id = guidechannels[guide_name]
        channel = zerobot_common.guild.get_channel(channel_id)
        posts = read_guides_sheet(guide_name)
        await channel.purge()
        # create empty posts
        for post in posts:
            msg = await channel.send(post.row)
            post.msg = msg
        # edit text to include references
        for post in posts:
            # loop over # of posts, for each #, replace [#] in text with <mention>
            for i in range(1,len(posts)+1):
                referenced_post = find_post(posts, i)
                mention = f'https://discordapp.com/channels/{zerobot_common.clan_server_id}/{channel_id}/{referenced_post.msg.id}'
                post.text = post.text.replace(f'[{i}]', mention)
            await post.msg.edit(content=post.text)


        
        
