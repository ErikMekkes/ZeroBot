from discord.ext import tasks, commands
import random
import zerobot_common
from memberlist import memberlist_from_disk

def nbr(channel):
    val = random.random()
    if val <= 0.4:
        return "No! YOU are nbr!"
    if val <= 0.7:
        choice = random.choice(["A urora","Wuhanian Bat","Super Fr00b","Zero Errors","Yathsou"])
        return f"{choice} is nbr!"
    if val <= 0.8:
        return "Ade ade"
    if val <= 0.9:
        return "No comedy auras!"
    if val <= 1:
        return f"Proooooooo!"
def ade(channel):
    val = random.random()
    if val <= 0.3:
        return "Ade ade"
    if val <= 0.45:
        return f"nbr"
    if val <= 0.6:
        return f"nbr nb"
    if val <= 0.8:
        return "Ade ade nbr"
    if val <= 0.9:
        return "Ade nbr nb"
    if val <= 1:
        return f"Proooooooo!"
def ask(channel, name):
    val = random.random()
    if val <= 0.3:
        return f"{name} specialist when?"
    if val <= 0.6:
        return f"{name} rankup when?"
    if val <= 0.8:
        return f"{name} gem done when?"
    if val <= 1:
        return f"{name} tags done when?"
def retaliate(channel, name):
    val = random.random()
    if val <= 0.3:
        return f"I like you {name}"
    if val <= 0.6:
        return f"{name} I see you!"
    if val <= 0.8:
        return f"{name} Time for a mute?"
    if val <= 1:
        return f"{name} I will ban you!"
def who(self, channel):
    if zerobot_common.memberlist_enabled:
        mlist = memberlist_from_disk(zerobot_common.current_members_filename)
    name = random.choice(mlist).name
    val = random.choice(["zbot!","zbot!","zbot!","Yathsou!","A urora!","Wuhanian Bat!","Super Fr00b!","Zero Errors!","Ectarax!", f"{name}!"])
    return val


class FunResponsesCog(commands.Cog):
    """
    Handles all the commands for applications.
    """
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        This event is triggered for any message received, including our own.
        Must keep this efficient, return asap if irrelevant.
        '''
        if self.bot.user.id == message.author.id:
            return
        name = message.author.display_name
        channel = message.channel
        if "zbot" in message.content:
            if "ade" in message.content:
                await channel.send(ade(message.channel))
                return
            if "nbr" in message.content:
                await channel.send(nbr(message.channel))
                return
            if " who" in message.content:
                await channel.send(who(self,channel))
                return
            if " you" in message.content:
                await channel.send(retaliate(channel, name))
                return
            if (
                " are " in message.content or 
                " is " in message.content
            ):
                await channel.send(ask(channel, name))
                return