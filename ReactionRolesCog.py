import zerobot_common
from discord.ext import commands

class ReactionRolesCog(commands.Cog):
    '''
    Handles giving roles for reactions to certain messages.
    '''
    def __init__(self, bot):
        self.bot = bot
        zerobot_common.logfile.log(f'Reactionroles cog loaded and ready.')
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        '''
        This event is triggered for anyone adding a reaction to anything.
        Should try very hard to keep this efficient, return asap if not relevant.
        '''
        # check if message should grant roles, return if not a reaction role message.
        reaction_message = zerobot_common.reaction_messages.get(str(payload.message_id))
        if (reaction_message == None):
            return
        # find role id to give for that reaction to that message, return if no role to give
        role_id = reaction_message.get(str(payload.emoji))
        if (role_id == None):
            return
        # find discord user, return if can not load the discord user to modify roles for
        discord_user = zerobot_common.guild.get_member(payload.user_id)
        if (discord_user == None):
            zerobot_common.reactionlog.log(f'Could not find user : {payload.user_id} on {zerobot_common.guild.name}')
            return
        # return if role to add cant be found
        role_to_add = zerobot_common.guild.get_role(role_id)
        if (role_to_add == None):
            zerobot_common.reactionlog.log(f'Could not find role : {role_id} on {zerobot_common.guild.name}')
            return
        # specific case for waiting approval role
        if (role_id == zerobot_common.discord_roles.get('Waiting Approval')):
            # return if user already has an approved role, dont need to assign waiting approval.
            for role in discord_user.roles:
                if (role.name in zerobot_common.discord_roles):
                    return
            # assign waiting approval role.
            await discord_user.add_roles(role_to_add, reason=f'{payload.user_id} reacted to {payload.message_id} with {payload.emoji}')
            return
        
        await discord_user.add_roles(role_to_add, reason=f'{payload.user_id} reacted to {payload.message_id} with {payload.emoji}')