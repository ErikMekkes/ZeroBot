"""
Standalone Module
Makes the bot respond with funny replies when a trigger phrase is typed in 
a discord channel the bot can access.

Can be enabled or disables with "funresponses_enabled" in the settings.json 
config file.
"""

from discord.ext import tasks, commands
import random
import zerobot_common
from memberlist import memberlist_from_disk
memers = [
    "A urora",
    "Wuhanian Bat",
    "Super Fr00b",
    "Zero Errors",
    "Yathsou",
    "Duker J",
    "African Herb",
    "Sanshine",
    "zbot!",
    "Pepelicious!",
    "Ectarax!",
    "Phagowocyte"
]
def nbr(channel):
    if zerobot_common.memberlist_enabled:
        mlist = memberlist_from_disk(zerobot_common.current_members_filename)
    name = random.choice(mlist).name
    val = random.random()
    if val <= 0.2:
        return "No! YOU are nbr!"
    if val <= 0.3:
        return "Raids when?"
    if val <= 0.7:
        choice = random.choice(memers + [name])
        return f"{choice} is nbr!"
    if val <= 0.8:
        return "Ade ade"
    if val <= 0.9:
        return "No comedy auras!"
    if val <= 1:
        return f"Proooooooo!"
def ade(channel):
    val = random.random()
    if val <= 0.1:
        return "Raids when?"
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
    if val <= 0.1:
        return f"{name} Raids when?"
    if val <= 0.2:
        return f"{name} pet when?"
    if val <= 0.4:
        return f"{name} specialist when?"
    if val <= 0.5:
        return f"{name} rankup when?"
    if val <= 0.65:
        return f"{name} gem done when?"
    if val <= 0.8:
        return f"{name} tags done when?"
    if val <= 0.9:
        return f"{name} in top clan highscores when?"
    if val <= 0.1:
        return f"{name} pvm world record yet?"
def will(channel):
    val = random.random()
    if val <= 0.1:
        if zerobot_common.memberlist_enabled:
            mlist = memberlist_from_disk(zerobot_common.current_members_filename)
        name = random.choice(mlist).name
        return f"Ask {random.choice(memers + [name])}!"
    if val <= 0.15:
        return f"Maybe next year."
    if val <= 0.2:
        return f"Neverrrrr!"
    if val <= 0.55:
        return f"No."
    if val <= 65:
        return f"Of course!"
    if val <= 1:
        return f"Yes!"
def when(channel):
    val = random.random()
    if val <= 0.1:
        if zerobot_common.memberlist_enabled:
            mlist = memberlist_from_disk(zerobot_common.current_members_filename)
        name = random.choice(mlist).name
        return f"Ask {random.choice(memers + [name])}!"
    if val <= 0.2:
        return f"Neverrrrr!"
    if val <= 0.3:
        return f"Maybe next year."
    if val <= 0.4:
        return f"When you're ready."
    if val <= 0.5:
        return f"Soon (tm)."
    if val <= 0.75:
        return f"This Week!"
    if val <= 0.95:
        return f"Today!"
    if val <= 1:
        return f"Now!"
def retaliate(channel, name):
    val = random.random()
    if val <= 0.1:
        return f"I will remember this {name}"
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
    val = random.random()
    if val <= 0.1:
        return f"zbot!"
    if val <= 0.7:
        return random.choice(memers)
    if val <= 1:
        return f"{name}!"

async def on_message_funresponse(message, funresponsecog):
    """
    This event is triggered for any message received, including our own.
    Must keep this efficient, return asap if irrelevant.
    """
    if funresponsecog.bot.user.id == message.author.id:
        return
    name = message.author.display_name
    text = message.content.lower()
    channel = message.channel
    if "zbot" in text:
        if " ade" in text or "ade " in text:
            await channel.send(ade(message.channel))
            return
        if " nbr" in text:
            await channel.send(nbr(message.channel))
            return
        if " who" in text:
            await channel.send(who(funresponsecog,channel))
            return
        if " when" in text:
            await channel.send(when(message.channel))
            return
        if " will" in text or "should" in text:
            await channel.send(will(message.channel))
            return
        if " you" in text:
            await channel.send(retaliate(channel, name))
            return
        if (
            " are " in text or 
            " is " in text
        ):
            await channel.send(ask(channel, name))
            return

class FunResponsesCog(commands.Cog):
    """
    Activates random fun responses to messages.
    """
    def __init__(self, bot):
        self.bot = bot
        bot.on_message_callbacks.append((on_message_funresponse, [self]))