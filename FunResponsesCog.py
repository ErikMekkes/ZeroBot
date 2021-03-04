from discord.ext import tasks, commands
import random
import zerobot_common

async def nbr(channel):
    val = random.random()
    if val <= 0.4:
        await channel.send("No! YOU are nbr!")
        return
    if val <= 0.7:
        choice = random.choice(["A urora","Wuhanian Bat","Super Fr00b","Zero Errors","Yathsou"])
        await channel.send(f"{choice} is nbr!")
        return
    if val <= 0.8:
        await channel.send("Ade ade")
        return
    if val <= 0.9:
        await channel.send("No comedy auras!")
        return
    await channel.send(f"Proooooooo!")
async def ade(channel):
    val = random.random()
    if val <= 0.4:
        await channel.send("Ade ade")
        return
    if val <= 0.7:
        await channel.send(f"nbr")
        return
    if val <= 0.8:
        await channel.send("Ade ade nbr")
        return
    if val <= 0.9:
        await channel.send("Ade nbr nb")
        return
    await channel.send(f"Proooooooo!")


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
        if "zbot" in message.content:
            if "ade" in message.content:
                await nbr(message.channel)
            if "nbr" in message.content:
                await ade(message.channel)