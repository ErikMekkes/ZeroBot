"""
Standalone Module
Enables syncing channels with contents posted on a google spreadsheet. 
Allows multiple people to collaborate on discord posts for channels.

Requires google drive credentials and document access, see zerobot_common.
"""
import zerobot_common
import utilities
import discord
from discord.ext import commands
from logfile import LogFile

logfile = None

if zerobot_common.channel_manager_enabled:
    # load google sheets document that contains the channel info sheets (tabs)
    channels_doc_name = zerobot_common.settings.get("channels_doc_name")
    channels_doc = zerobot_common.drive_client.open(channels_doc_name)
    # load config that describes which channels should be synched with what
    synched_channels_filename = zerobot_common.settings.get(
        "synched_channels_filename"
    )
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

async def daily_channel_reload(channel_cog):
    """
    Callback function for daily update loop.
    """
    # notify that daily channel reloading is starting
    await zerobot_common.bot_channel.send(
        "Starting daily channel reloading..."
    )
    
    for name in zerobot_common.daily_reload_channels:
        await zerobot_common.bot_channel.send(
            f"reloading {name} channel..."
        )
        await channel_cog.reload_channel(name)
    # notify that daily channel reloading has finished.
    await zerobot_common.bot_channel.send(
        "Daily channel reloading finished."
    )

class ChannelCog(commands.Cog):
    """
    Handles synched channels and commands related to synching.
    """
    def __init__(self, bot):
        self.bot = bot
        
        global logfile
        logfile = LogFile(
            "logs/channelslog",
            parent = zerobot_common.logfile,
            parent_prefix = "channelslog"
        )

        if zerobot_common.daily_channel_reload_enabled:
            bot.daily_callbacks.append((daily_channel_reload, [self]))
        
        logfile.log(f"Channels cog loaded and ready.")

    @commands.command()
    async def reloadchannels(self, ctx):
        """
        Reload all the channels the bot knows about.
        """
        # log command attempt and check if command allowed
        logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if zerobot_common.permissions.not_allowed(
            "reloadchannels", ctx.channel.id
        ) : return

        for channel_name in synched_channels:
            await self.reload_channel(channel_name)

    @commands.command()
    async def reloadchannel(self, ctx, channel_name):
        """
        Reload a single channel by name, must match the spreadsheet name.
        The related channel is found by the bot in synched_channels.
        """
        # log command attempt and check if command allowed
        logfile.log(
            f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}"
        )
        if zerobot_common.permissions.not_allowed(
            "reloadchannel", ctx.channel.id
        ) : return

        await self.reload_channel(channel_name)
        await ctx.send(f"Finished reloading {channel_name}.")
    
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
        # create initial posts with text and image if img_url is present
        for post in posts:
            if post.img_url is not None:
                # post has img_url, try to post image.
                found = utilities.download_img(post.img_url, "zbottemp.png")
                #TODO ^ check if found is image, could be some kind of 
                # 'not found' html page, wont crash, just blank tempfile.png
                if found:
                    img_file = open("zbottemp.png", "rb")
                    img = discord.File(img_file)
                    msg = await channel.send(post.text, file=img)
                    post.msg = msg
                    img.close()
                    img_file.close()
                    utilities.delete_file("zbottemp.png")
                    continue
                else:
                    msg = await channel.send(
                        f"{post.row} : {post.img_url} not found\n"
                        f"{post.text}"
                    )
                    post.msg = msg
                    continue
            # no img_url, just send text.
            if post.text is None or post.text == "":
                # no img and missing text (cant send empty message)
                msg = await channel.send(f"{post.row} : no text or img")
                post.msg = msg
                continue
            msg = await channel.send(post.text,allowed_mentions=discord.AllowedMentions(roles=False, users=False, everyone=False))
            post.msg = msg
        
        # loop over all posts to insert reference links
        for post in posts:
            if post.text is None or post.text == "":
                # empty text / just an image -> no need to edit
                continue
            old_text = post.text
            # loop over post numbers
            for i in range(1,len(posts)+1):
                # create a link to post number, 
                # TODO: could create once outside posts loop for efficiency
                referenced_post = find_post(posts, i)
                mention = (
                    f"https://discordapp.com/channels/"
                    f"{zerobot_common.clan_server_id}/{channel_id}/"
                    f"{referenced_post.msg.id}"
                )
                # if post # is referenced, replace it in text with the link.
                post.text = post.text.replace(f"[{i}]", mention)
            # only send text edit request to discord if text actually changed.
            if post.text != old_text:
                await post.msg.edit(content=post.text)