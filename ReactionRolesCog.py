import zerobot_common
from discord.ext import commands
from rankchecks import discord_ranks

class ReactionRolesCog(commands.Cog):
    '''
    Handles giving roles for reactions to certain messages.
    '''
    def __init__(self, bot):
        self.bot = bot
        zerobot_common.reactionlog.log(f'Reactionroles cog loaded and ready.')
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        '''
        This event is triggered for anyone adding a reaction to anything.
        Must keep this efficient, return asap if irrelevant.
        '''
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
        if (role_to_add == None):
            zerobot_common.reactionlog.log(
                f"Could not find role : {role_id} on "
                f"{zerobot_common.guild.name}"
            )
            return
        # specific case for waiting approval role
        if (role_id == zerobot_common.get_named_role('Waiting Approval').id):
            # return if user already has a ranked role. Approval not needed.
            for role in discord_user.roles:
                if (role.name in discord_ranks):
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
        '''
        This event is triggered for anyone removing a reaction from anything.
        Must keep this efficient, return asap if irrelevant.
        '''
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