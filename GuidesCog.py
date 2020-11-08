'''
Enables syncing guide channels with contents posted on a google spreadsheet. Allows multiple
people to collaborate on discord posts for guides.

This module uses some components from other zerobot common for convenience, but everything
related to this google drive guide syncing functionality is in here, except for:
- guideslog_filename in settings.json
- adding the cog module in zerobot.py
'''
import zerobot_common
import utilities
import discord
from discord.ext import commands
from logfile import LogFile
from datetime import datetime

# start log for guides module
guideslog = LogFile('logs/guideslog')
# load document that contains the actual guides
guides_doc_name = zerobot_common.settings.get('guides_doc_name')
guides_doc = zerobot_common.drive_client.open(guides_doc_name)
# load config that describes which channels should which guides
guidechannels_filename = zerobot_common.settings.get('guidechannels_filename')
guidechannels = utilities.load_json(guidechannels_filename)

class Post():
    def __init__(self, text, row):
        self.text = text
        self.row = row
        self.msg = None
        self.img_url = None

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
        text = row[0]
        post = Post(text, num)
        # if text has a image tag to be posted
        if "[img]" in text and "[\\img]" in text:
            # find first [img][\img] tag in text
            url_start = text.index("[img]") + len("[img]")
            url_end = text.index("[\\img]")
            # store the url and remove the tagged url from the text
            post.img_url = text[url_start:url_end]
            post.text = (
                text[0:url_start-len("[img]")]
                + text[url_end+len("[\img]"):len(text)]
            )
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
            # is an image post, only post image.
            if post.img_url is not None:
                #TODO post and delete img
                found = utilities.download_img(post.img_url, "zbottemp.png")
                if found:
                    img_file = open("zbottemp.png", 'rb')
                    img = discord.File(img_file)
                    msg = await channel.send(post.row, file=img)
                    post.msg = msg
                    img.close()
                    img_file.close()
                    utilities.delete_file("zbottemp.png")
                    continue
            msg = await channel.send(post.row)
            post.msg = msg
        # edit text to include references
        for post in posts:
            # was an image post, no text to edit.
            # loop over # of posts, for each #, replace [#] in text with <mention>
            for i in range(1,len(posts)+1):
                referenced_post = find_post(posts, i)
                mention = f'https://discordapp.com/channels/{zerobot_common.clan_server_id}/{channel_id}/{referenced_post.msg.id}'
                post.text = post.text.replace(f'[{i}]', mention)
            await post.msg.edit(content=post.text)


        
        
