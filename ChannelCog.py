'''
Enables syncing channels with contents posted on a google spreadsheet. 
Allows multiple people to collaborate on discord posts for channels.

Everything related to synching channels from the google drive channels sheet 
is in this module.
'''
import zerobot_common
import utilities
import discord
from discord.ext import commands
from logfile import LogFile

# start log for channels module
channelslog = LogFile('logs/channelslog')
# load google sheets document that contains the actual channel sheets (tabs)
channels_doc_name = zerobot_common.settings.get('channels_doc_name')
channels_doc = zerobot_common.drive_client.open(channels_doc_name)
# load config that describes which channels should be synched with what
synched_channels_filename = zerobot_common.settings.get('synched_channels_filename')
synched_channels = utilities.load_json(synched_channels_filename)

class Post():
    """
    Initially used to store the contents of each post from the sheet. 
    """
    def __init__(self, text, row):
        self.text = text
        self.row = row
        self.msg = None
        self.img_url = None

def find_post(posts, row):
    """
    Find the post with the specified row number if it is in the list of posts.

    Should be equal to index in list of posts due to how its constructed, but 
    might as well check and be sure. Used for referencing.
    """
    for post in posts:
        if post.row == row: return post
    return None

def read_channel_sheet(channel_name):
    """
    Reads all the cells in the first column of the named sheet and returns 
    them as a list of Post objects. Recognizes image upload posts separately.
    The row of each post is stored as well for referencing later.
    """
    zerobot_common.drive_connect()
    sheet = channels_doc.worksheet(channel_name)
    sheet_matrix = sheet.get_all_values()
    posts = []
    num = 1
    for row in sheet_matrix:
        text = row[0]
        post = Post(text, num)
        # if text has a image tag to be posted
        if "[img]" in text and "[/img]" in text:
            # find first [img][\img] tag in text
            url_start = text.index("[img]") + len("[img]")
            url_end = text.index("[/img]")
            # store the url and remove the tagged url from the text
            post.img_url = text[url_start:url_end]
            post.text = (
                text[0:url_start-len("[img]")]
                + text[url_end+len("[/img]"):len(text)]
            )
        posts.append(post)
        num += 1
    return posts

class ChannelCog(commands.Cog):
    """
    Handles synched channels and commands related to synching.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def reloadchannels(self, ctx):
        """
        Reload all the channels the bot knows about.
        """
        for channel_name in synched_channels:
            await self.reload_channel(channel_name)

    @commands.command()
    async def reloadchannel(self, ctx, channel_name):
        """
        Reload a single channel by name, must match the spreadsheet name.
        The related channel is found by the bot in synched_channels.
        """
        await self.reload_channel(channel_name)
    
    async def reload_channel(self, channel_name):
        """
        Actual process for clearing and re-creating posts in a channel.
        - clears channel first
        - sends empty message for each post (so we can reference future ones)
        - edits the text in each post, with reference links to other posts.
        """
        channel_id = synched_channels[channel_name]
        channel = zerobot_common.guild.get_channel(channel_id)
        posts = read_channel_sheet(channel_name)
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
        # loop over all posts to edit references in them
        for post in posts:
            # loop over # of posts, create a link to post #, if [#] is used in
            # the text replace it with the link.
            for i in range(1,len(posts)+1):
                referenced_post = find_post(posts, i)
                mention = (
                    f"https://discordapp.com/channels/"
                    f"{zerobot_common.clan_server_id}/{channel_id}/"
                    f"{referenced_post.msg.id}"
                )
                post.text = post.text.replace(f"[{i}]", mention)
            await post.msg.edit(content=post.text)