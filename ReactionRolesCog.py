"""
Standalone Module

Lets you configure messages such that responding with emojis to them gives
the person who reacted a certain role for that emoji.
"""
import io
import discord
from discord.ext import commands
from logfile import LogFile
import zerobot_common
from utilities import rank_index

logfile = None

class ReactionRolesCog(commands.Cog):
    """
    Handles giving roles for reactions to certain messages.
    """
    def __init__(self, bot):
        self.bot = bot
        global logfile
        logfile = LogFile(
            "logs/reactionroles",
            parent = zerobot_common.logfile,
            parent_prefix = "reactionroles"
        )
        logfile.log(f"Reactionroles cog loaded and ready.")
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """
        This event is triggered for anyone adding a reaction to anything.
        Must keep this efficient, return asap if irrelevant.
        """
        # check if its a reaction role message, return if not.
        msg_id = str(payload.message_id)
        reaction_message = zerobot_common.reaction_messages.get(msg_id)
        if (reaction_message == None):
            return
        # find role id to remove for this removed reaction, return if unknown.
        role_id = reaction_message.get(payload.emoji.name)
        if (role_id == None):
            return
        # find discord user, return if dont know who to edit
        discord_user = zerobot_common.guild.get_member(payload.user_id)
        if (discord_user == None):
            zerobot_common.reactionlog.log(
                f"Could not find user : {payload.user_id} on "
                f"{zerobot_common.guild.name}"
            )
            return
        # find actual discord role to remove, return if cant be found.
        role_to_add = zerobot_common.guild.get_role(role_id)
        if role_to_add == None:
            zerobot_common.reactionlog.log(
                f"Could not find role : {role_id} on "
                f"{zerobot_common.guild.name}"
            )
            return
        # specific case for waiting approval role
        if role_id == zerobot_common.approval_role_id:
            # return if user already has a ranked role. Approval not needed.
            index = rank_index(discord_user=discord_user)
            if index is not None:
                return
            # assign waiting approval role.
            await discord_user.add_roles(
                role_to_add,
                reason = (
                    f"{payload.user_id} reacted to {payload.message_id} "
                    f"with {payload.emoji}"
                )
            )
            return
        
        # try to add role.
        await discord_user.add_roles(
            role_to_add,
            reason = (
                f"{payload.user_id} reacted to {payload.message_id} "
                f"with {payload.emoji}"
            )
        )
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """
        This event is triggered for anyone removing a reaction from anything.
        Must keep this efficient, return asap if irrelevant.
        """
        # check if its a reaction role message, return if not.
        msg_id = str(payload.message_id)
        reaction_message = zerobot_common.reaction_messages.get(msg_id)
        if (reaction_message == None):
            return
        # find role id to remove for this removed reaction, return if unknown.
        role_id = reaction_message.get(payload.emoji.name)
        if (role_id == None):
            return
        # find discord user, return if dont know who to edit
        discord_user = zerobot_common.guild.get_member(payload.user_id)
        if (discord_user == None):
            zerobot_common.reactionlog.log(
                f"Could not find user : {payload.user_id} on "
                f"{zerobot_common.guild.name}"
            )
            return
        # find actual discord role to remove, return if cant be found.
        role_to_remove = zerobot_common.guild.get_role(role_id)
        if (role_to_remove == None):
            zerobot_common.reactionlog.log(
                f"Could not find role : {role_id} on "
                f"{zerobot_common.guild.name}"
            )
            return
        
        # try to remove role.
        await discord_user.remove_roles(
            role_to_remove,
            reason = (
                f"{payload.user_id} removed {payload.emoji.name} reaction"
                f" from {payload.message_id}"
            )
        )
    
    @commands.command()
    async def get_emoji_id(self, ctx, *args):
        use_str = (
            "Usage: -zbot get_emoji_id emoji_name"
        )
        if len(args) != 1:
            await ctx.send(use_str)
        for e in self.bot.emojis:
            if e.name == args[0]:
                await ctx.send(f"{e.name} {e.id} {e}")
    
    @commands.command()
    async def react(self, ctx, *args):
        use_str = (
            "Usage: -zbot react channel_id:message_id emoji_name\n"
            " must be used in the same channel as the message."
        )
        if len(args) != 2:
            await ctx.send(use_str)
        
        msg_id = None
        chann_id = None
        try:
            msg_id = int(args[0])
        except ValueError:
            try:
                loc = args[0].split(':')
                chann_id = int(loc[0])
                msg_id = int(loc[1])
            except Exception:
                await ctx.send("invalid channel:message_id combo.\n\n" + use_str)
                return
        try:
            if chann_id is not None:
                channel = zerobot_common.guild.get_channel(chann_id)
            else:
                channel = ctx.channel
            msg = await channel.fetch_message(msg_id)
        except Exception:
            await ctx.send(f"unable to find message: {msg_id} not found.")
        
        #add the emoji
        try:
            emoji_id = int(args[1])
            await msg.add_reaction(self.bot.get_emoji(emoji_id))
        except Exception:
            await msg.add_reaction(args[1])
    
    @commands.command()
    async def listreactions(self, ctx, *args):
        use_str = (
            "Usage: -zbot listreactions message_id\n"
            " message_id: discord id of message that you need a list of people who reacted of.\n"
            " gives you a textfile with names and discord ids per reaction.\n"
            " must be used in the same channel as the message."
        )

        if len(args) != 1:
            await ctx.send("You did not specify a message id number" + use_str)
            return
        
        try:
            msg_id = int(args[0])
        except ValueError:
            await ctx.send("The option you added is not a message id number.\n" + use_str)
            return
        try:
            msg = await ctx.channel.fetch_message(msg_id)
        except Exception:
            await ctx.send(f"unable to find message: {msg_id} not found.")
        
        reactions_str = ""
        for reaction in msg.reactions:
            for user in await reaction.users().flatten():
                reactions_str += f"{user.id}\t{user.display_name}\t{reaction.emoji}\n"
        f = io.StringIO(reactions_str)
        disc_file = discord.File(f, "reactions.txt")
        await ctx.send(content="", file=disc_file)