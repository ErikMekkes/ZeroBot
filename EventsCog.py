"""
Standalone Module
Allows normal discord members to create and manage channels for events.
"""
from discord.ext import tasks, commands
import zerobot_common
from logfile import LogFile
from datetime import datetime, timedelta
from utilities import load_json, dump_json, _dateToStr, _strToDate, datetimeformat
from memberlist import memberlist_get

logfile = None
events_filename = "clan_events.txt"
# discord category that new event channels should be created under 
# loaded on bot start from guild object using events_category_id.
events_category_id = zerobot_common.settings.get("events_category_id")
events_category = None
int_to_day = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}
class Event():
    """
    Represents an event.
    """
    def __init__(self, channel_id, host_id, date, event_name, event_list=None):
        """
        Create an event object.
        """
        self.channel_id = channel_id
        self.host_id = host_id
        self.date = date
        self.event_name = event_name
        self.event_list = event_list
    def __eq__(self, other):
        if isinstance(other, Event):
            # each application is given its own unique channel
            if (self.channel_id == other.channel_id):
                return True
        return False
    def to_dict(self):
        """
        Transforms this event into a dictionary.
        """
        return {
            "channel_id": self.channel_id,
            "host_id": self.host_id,
            "date": _dateToStr(self.date, df=datetimeformat),
            "event_name": self.event_name
        }
    @staticmethod
    def from_dict(event_dict, event_list = None):
        """
        Transforms an event dictionary back into an Event object.
        """
        return Event(
            event_dict["channel_id"],
            event_dict["host_id"],
            _strToDate(event_dict["date"], df=datetimeformat),
            event_dict["event_name"],
            event_list = event_list
        )

class DateException(Exception):
    pass
class TimeException(Exception):
    pass

def parsedate(daystr, timestr):
    # find today's date starting at 00:00
    now = datetime.utcnow()
    t = datetime.combine(datetime.min, now.time()) - datetime.min
    today = now - t
    day = -1
    daystr = daystr.lower()
    if daystr in "monday":
        day = 0
    elif daystr in "tuesday":
        day = 1
    elif daystr in "wednesday":
        day = 2
    elif daystr in "thursday":
        day = 3
    elif daystr in "friday":
        day = 4
    elif daystr in "saturday":
        day = 5
    elif daystr in "sunday":
        day = 6
    elif daystr in "today":
        day = today.weekday()
    elif daystr in "tomorrow":
        day = today.weekday() + 1
        if day == 7:
            day = 0
    else:
        raise DateException(f"Unable to convert {daystr} to date.")
    # todays day number
    d = today.weekday()
    # number of days ahead
    days_ahead = day - d
    if days_ahead < 0:
        days_ahead += 7
    date = today + timedelta(days=days_ahead)
    
    timestr = timestr.lower()
    timeformat1 = "%H%M"
    timeformat2 = "%Hh%M"
    timeformat3 = "%H:%M"
    time = None
    try:
        time = datetime.strptime(timestr[:len(timeformat1)], timeformat1)
    except ValueError:
        pass
    if time is None:
        try:
            time = datetime.strptime(timestr[:len(timeformat2)], timeformat2)
        except ValueError:
            pass
    if time is None:
        try:
            time = datetime.strptime(timestr[:len(timeformat3)], timeformat3)
        except ValueError:
            pass
    if time is None:
        raise TimeException(f"Unable to convert {timestr} to time.")
    date = datetime.combine(date, time.time())
    return date

class EventList:
    """
    List of events.
    """
    def __init__(self, events_filename):
        """
        Creates an EventList.
        """
        self.events_filename = events_filename
        self.load()
    def load(self):
        """
        Load the state of events from disk.
        """
        events_dict = load_json(self.events_filename)
        try:
            events_dict = events_dict["events"]
        except KeyError:
            self.events = []
            self.dump()
            return

        self.events = []
        # events file is a dictionary {events: [event_1, ..., event_n]}.
        # each event is a dictionary as event.to_dict()
        for e in events_dict:
            self.events.append(Event.from_dict(e, event_list = self))
    def dump(self):
        """
        Writes the state of events to disk.
        """
        dict_list = []
        for e in self.events:
            dict_list.append(e.to_dict())
        dump_json({"events": dict_list}, self.events_filename)
    def append(self, event):
        """
        Appends the event to the event list and syncs with file on disk.
        """
        self.events.append(event)
        event.applist = self
        self.dump()

async def setup_event_channel(ctx, channel):
    """
    Sets up the remaining permissions for an event channel.
    Allows editing channel name, description, slow mode, nsf, channel delete
    Allows pinning and deleting messages.
    """
    await channel.set_permissions(
        ctx.author,
        manage_channels = True,
        manage_messages = True
    )

def channel_position(date):
    """
    Finds the channel position this date should have.
    """
    pos = 0
    # loop through channels in category (= ordered by position).
    for c in events_category.channels:
        # check if channel matches the dateformat
        try:
            day = c.name[0:3]
            time = c.name[4:9]
            c_date = parsedate(day, time)
            # if date is before, need to place new one after
            if c_date <= date:
                pos = c.position + 1
            else:
                # stop once we passed a channel with a later date.
                # assuming channels are already ordered by date
                break
        except Exception:
            # skip over event channels without date.
            pos = c.position + 1
    return pos

class EventsCog(commands.Cog):
    """
    Handles all the commands for applications.
    """
    def __init__(self, bot):
        """
        Starts the module that manages events and event commands.
        """
        self.bot = bot
        global logfile
        logfile = LogFile(
            "logs/eventslog",
            parent = zerobot_common.logfile,
            parent_prefix = "eventslog"
        )
        logfile.log(f"Events cog loaded and ready.")

        # Find events category in Zer0 server and store it
        categories = zerobot_common.guild.categories
        for cat in categories:
            if cat.id == events_category_id:
                global events_category
                events_category = cat
        # Load events from disk
        self.events = EventList(events_filename)
    
    @commands.command()
    async def event(self, ctx, *args):
        """
        Start a new event and open a channel for it.
        """
        logfile.log(f"{ctx.channel.name}:{ctx.author.name}:{ctx.message.content}")
        if not(zerobot_common.permissions.is_allowed("event", ctx.channel.id)) : return
        if not zerobot_common.is_member(ctx.author):
            await ctx.send(f"You have to be a clan member to start events.")
            return

        use_str = (
            "Use: `-zbot event <day> <time> name of event`\n"
            "day: mon, tue, wed, fri, sat, sun, today\n"
            "time: 1300, 13:00, 13h00 formats all work\n"
            "example: `-zbot event mon 2200 raids learner`"
        )

        # return if wrong format
        if (len(args) < 3):
            await ctx.send(f"enter a day, time, and event name.\n{use_str}")
            return

        try:
            date = parsedate(args[0], args[1])
        except Exception as e:
            await ctx.send(f"{str(e)}\n{use_str}")
            return
        day = int_to_day[date.weekday()]
        time = date.strftime("%Hh%M")
        event_date = f"{day}-{time}-"
        event_name = "-".join(args[2:len(args)]).lower()
        channel_name = event_date + event_name
        position = channel_position(date)
        # might be equal to next channel's position so
        # move the other channels down to prepare for inserting a new one
        for c in events_category.channels:
            if c.position >= position:
                await c.edit(position = c.position + 1)
        # actually start making the channel
        channel = await events_category.create_text_channel(
            channel_name,
            position=position,
            reason="zbot host event"
        )
        await setup_event_channel(ctx, channel)
        await ctx.send(
            f"I have created the {channel.mention} event channel for you. "
            f"You are able to edit its name and delete it after the event. "
            f"You can also pin and delete messages in this channel."
        )
        # track event, not used for anything yet, for future use
        event = Event(channel.id, ctx.author.id, date, event_name)
        self.events.append(event)

        # track amount of events hosted per person
        membcog = self.bot.get_cog("MemberlistCog")
        list_access = await membcog.lock(skip_sheet=True)
        
        memb_id = ctx.author.id
        member = memberlist_get(list_access["current_members"], memb_id)
        if member is not None:
            new_value = member.misc["events_started"] + 1
            member.misc["events_started"] = new_value

        await membcog.unlock(skip_sheet=True)
    
    @commands.command()
    async def _c_list(self, ctx, *args):
        if ctx.author.id != 311838457687441418: return
        msg = "```\nchannel_name : position\n"
        for c in events_category.channels:
            msg += f"{c.name} : {c.position}\n"
        msg += "```"
        await ctx.send(msg)

    @commands.command()
    async def _c_move(self, ctx, *args):
        if ctx.author.id != 311838457687441418: return
        c = zerobot_common.guild.get_channel(int(args[0]))
        c_orig = c.position
        await c.edit(position = int(args[1]))
        await ctx.send(f"moved {c.name} from index {c_orig} to {c.position}")