from discord.ext import commands
import zerobot_common
import utilities
from logfile import LogFile

# start log for guides module
guideslog = LogFile("logs/dropcomplog")
# load google sheets document that contains the actual guide sheets (tabs)
dropcomp_doc_name = zerobot_common.settings.get("dropcomp_doc_name")
dropcomp_doc = zerobot_common.drive_client.open(dropcomp_doc_name)
# load config that describes which channels should contain which guides
teamchannels_filename = zerobot_common.settings.get("teamchannels_filename")
teamchannels = utilities.load_json(teamchannels_filename)

class DropCompCog(commands.Cog):
    """
    Commands to help with drop comp.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def dropcomp(self, ctx, *args):
        """
        Submit a drop for the drop comp. Only works in team channel
        """
        channel_id = ctx.channel.id
        team_number = teamchannels.get(str(channel_id), None)
        if team_number is None:
            # not a drop comp team channel
            return
    
        use_str = (
            "Usage: -zbot dropcomp <image_link>\n"
            " image_link: link to the image that shows your drop, imgur, gyazo etc.\n"
            " if you post the image directly to discord it is not needed to add a link. you can just type `-zbot dropcomp` as comment for the image."
        )
        if len(args) > 1:
            # 0 or more than 2 arguments, bad use.
            await ctx.send("You added more than 1 option! Try again.\n" + use_str)
            return
        drop_name = args[0]
        
        img_url = None
        if len(ctx.message.attachments) > 1:
            await ctx.send("Please only post one image per command. Try again.")
        if len(ctx.message.attachments) == 1:
            img_url = ctx.message.attachments[0].url
        if len(args) == 1:
            if img_url is None:
                await ctx.send("You did not attach an image! Try again.\n" + use_str)
                return
        if len(args) == 2:
            # get image url from args.
            img_url = args[1]
        add_drop_to_sheet(team_number, ctx.message.id, ctx.author.id, ctx.author.display_name, img_url, drop_name)
        await ctx.message.add_reaction("👍")

def add_drop_to_sheet(team_number, msg_id, author_id, author_name, img_url, drop_name):
    zerobot_common.drive_connect()
    sheet = dropcomp_doc.worksheet("Drop Log")
    top_row = 2
    values = [
        str(team_number),
        str(msg_id),
        str(author_id),
        author_name,
        img_url,
        drop_name
    ]
    sheet.insert_row(values, top_row, value_input_option = 'USER_ENTERED')