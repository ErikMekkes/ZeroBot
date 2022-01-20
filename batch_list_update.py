# Make sure Member.from_str in here still reads the old version format
# Make sure Member.to_str in here writes the new version format
# then just run and this will try to update all files and folders below
# tries these specific files
files = [
    "memberlists/current_members.txt",
    "memberlists/old_members.txt",
    "memberlists/banned_members.txt"
]
# tries all files in these folders
folders = [
    "memberlists/banned_members/",
    "memberlists/current_members/",
    "memberlists/old_members/"
]

import traceback
from utilities import read_file, write_file, int_0, _strToDate, _dateToStr, bracket_parser, boolstr
from exceptions import NotAMemberList, NotAMember
from member import Warning, NotAWarningError
import copy
import ast
from os import listdir
from os.path import isfile, join

# key names for skills and activities, matches ingame api result.
# using some easier lowercase naming for the ones that are used.
skill_labels = [
    "overall", "attack", "defence", "strength", "constitution", "ranged", 
    "prayer", "magic", "cooking", "woodcutting", "fletching", "fishing", 
    "firemaking", "crafting", "smithing", "mining", "herblore", "agility", 
    "thieving", "slayer", "farming", "runecrafting", "hunter", 
    "construction", "summoning", "dungeoneering", "divination", "invention", 
    "archaeology"
]
activity_labels = [
    "Bounty Hunter", "B.H. Rogues", "Dominion Tower", 
    "The Crucible", "Castle Wars games", "B.A. Attackers", "B.A. Defenders", 
    "B.A. Collectors", "B.A. Healers", "Duel Tournament", 
    "Mobilising Armies", "Conquest", "Fist of Guthix", "GG: Athletics", 
    "GG: Resource Race", "WE2: Armadyl Lifetime Contribution", 
    "WE2: Bandos Lifetime Contribution", "WE2: Armadyl PvP kills", 
    "WE2: Bandos PvP kills", "Heist Guard Level", "Heist Robber Level", 
    "CFP: 5 Game Average", "AF15: Cow Tipping", 
    "AF15: Rats killed after the miniquest", "runescore", 
    "easy_clues", "medium_clues", "hard_clues", "elite_clues", "master_clues"
]
misc_labels = [
    "highest_mage",
    "highest_melee",
    "highest_range",
    "discord_roles",
    "events_started"
]

# these should match the names of the notify roles that should be tracked.
notify_role_names = [
    "AoD Learner",
    "Solak Learner",
    "Vorago Learner",
    "Raids Learner",
    "ROTS Learner",
    "Elite Dungeon Learner",
    "Nex Learner",
    "Raksha Learner",
    "Notify AoD",
    "Notify Solak",
    "Notify Vorago",
    "Notify Raids",
    "Notify ROTS",
    "Notify Elite Dungeon (specify ED1, 2 or 3)",
    "Notify Nex",
    "Notify Raksha",
    "Notify Dungeoneering Party",
    "Notify Kerapac",
    "Notify Croesus"
]

# blank skills and activities to ensure one is always present
blank_skills = {}
for i in range(0, len(skill_labels)):
    blank_skills[skill_labels[i]] = [0,0,0]
blank_activities = {}
for i in range(0, len(activity_labels)):
    blank_activities[activity_labels[i]] = [0,0]
blank_misc = {}
for i in range(0, len(misc_labels)):
    blank_misc[misc_labels[i]] = ""
blank_misc["discord_roles"] = []
blank_notify_stats = {}
for i in range(0, len(notify_role_names)):
    blank_notify_stats[notify_role_names[i]] = 0

class Member:
    """
    Member(name, rank, clan_xp, kills).
    """
    def __init__(self, name, rank, clan_xp, kills):
        self.name = name
        self.rank = rank
        self.discord_rank = ""
        self.site_rank = ""
        self.join_date = ""
        self.passed_gem = False
        self.profile_link = ""
        self.leave_date = ""
        self.leave_reason = ""
        self.referral = ""
        self.discord_id = 0
        self.discord_name = ""
        self.old_names = list()
        self.last_active = None
        self.id = 0
        self.warning_points = 0
        self.warnings = list()
        self.note1 = ""
        self.note2 = ""
        self.note3 = ""
        self.clan_xp = clan_xp
        self.kills = kills
        # skill xp and activity score dicts, guarantees presence.
        self.skills = copy.deepcopy(blank_skills)
        self.activities = copy.deepcopy(blank_activities)
        self.misc = copy.deepcopy(blank_misc)
        self.notify_stats = copy.deepcopy(blank_notify_stats)
        # not stored, based on last active, used for sorting inactives
        self.days_inactive = 0
        # not stored, only set if member originates from a search result to allow editing.
        self.result_type = ""
        self.row = None
        self.sheet = None
        self.on_hiscores = False
    def __str__(self):
        old_names = ""
        for x in self.old_names:
            old_names += x + ","
        old_names = old_names[:-1]
        warnings = "["
        for w in self.warnings:
            warnings += str(w)
        warnings += "]"
        skills = "["
        for v in self.skills.values():
            skills += str(v) + ", "
        skills = skills[:-2] + "]"
        activities = "["
        for v in self.activities.values():
            activities += str(v) + ", "
        activities = activities[:-2] + "]"
        notify_stats = "["
        for v in self.notify_stats.values():
            notify_stats += str(v) + ", "
        notify_stats = notify_stats[:-2] + "]"
        misc = ""
        for _, v in self.misc.items():
            # if needed can process v to string first
            # if k == "key": misc += ... continue
            misc += str(v) + "\t"
        misc = misc[:-1]

        user_str = (
            f"{self.name}\t{self.rank}\t{self.discord_rank}\t{self.site_rank}"
            f"\t{self.join_date}\t{boolstr[self.passed_gem]}"
            f"\t{self.profile_link}\t{self.leave_date}"
            f"\t{self.leave_reason}\t{self.referral}\t{str(self.discord_id)}"
            f"\t{self.discord_name}\t{old_names}"
            f"\t{_dateToStr(self.last_active)}"
            f"\t{str(self.id)}"
            f"\t{str(self.warning_points)}"
            f"\t{warnings}"
            f"\t{self.note1}\t{self.note2}\t{self.note3}"
            f"\t{str(self.clan_xp)}\t{str(self.kills)}"
            f"\t{skills}"
            f"\t{activities}"
            f"\t{notify_stats}"
            f"\t{misc}"
        )
        return user_str
    def to_string(self):
        """
        Writes a member to a string. Used for writing to memberlist on disk.
        member: Member object.

        output: Single line string with member attributes separated by tabs.
        """
        return str(self)
    @staticmethod
    def from_string(member_str):
        """
        Reads a member from a string. Used for reading from memberlist on disk.
        member_str: Single line string with member attributes separated by tabs.
        output: A Member object.
        """
        memb_info = member_str.split("\t")
        memb = Member(
            memb_info[0],
            memb_info[1],
            int_0(memb_info[19]),
            int_0(memb_info[20])
        )
        memb.discord_rank = memb_info[2]
        memb.site_rank = memb_info[3]
        memb.join_date = memb_info[4]
        memb.passed_gem = (memb_info[5] == "TRUE")
        memb.profile_link = memb_info[6]
        memb.leave_date = memb_info[7]
        memb.leave_reason = memb_info[8]
        memb.referral = memb_info[9]
        memb.discord_id = int_0(memb_info[10])
        memb.discord_name = memb_info[11]
        # weird case, split empty string results in a list containing 
        # empty string instead of empty list
        if (len(memb_info[12]) == 0) :
            memb.old_names = list()
        else :
            memb.old_names = memb_info[12].split(',')
        memb.last_active = _strToDate(memb_info[13])
        memb.warning_points = int_0(memb_info[14])
        warnings = bracket_parser(memb_info[15])
        for w in warnings:
            memb.warnings.append(Warning.from_str(w))
        memb.note1 = memb_info[16]
        memb.note2 = memb_info[17]
        memb.note3 = memb_info[18]
        for num,x in enumerate(ast.literal_eval(memb_info[21])):
            memb.skills[skill_labels[num]] = x
        for num,x in enumerate(ast.literal_eval(memb_info[22])):
            memb.activities[activity_labels[num]] = x
        for num,x in enumerate(ast.literal_eval(memb_info[23])):
            memb.notify_stats[notify_role_names[num]] = x
        # load entries into misc per label.
        for i in range(len(misc_labels)):
            memb.misc[misc_labels[i]] = memb_info[i+24]
        # process misc entries further if needed
        memb.misc["discord_roles"] = ast.literal_eval(memb.misc["discord_roles"])
        memb.misc["events_started"] = int_0(memb.misc["events_started"])
        return memb

def memberlist_from_string(memberlist_string):
    # UNMODIFIED
    try:
        result = list()
        memberlist_array = memberlist_string.splitlines()
        for memb_str in memberlist_array:
            result.append(Member.from_string(memb_str))
        return result
    except Exception:
        text = "String to be read as memberlist is not of list[Member]"
        raise NotAMemberList(text)
def memberlist_from_disk(filename):
    # UNMODIFIED
    memberlist_str = read_file(filename)
    return memberlist_from_string(memberlist_str)
def memberlist_to_string(memberlist):
    # UNMODIFIED
    if not isinstance(memberlist, list):
        text = (
            f"Object to be converted to a memberlist string is not of "
            f"list[Member]."
        )
        raise NotAMemberList(text)
    mlist = []
    for memb in memberlist:
        if not isinstance(memb, Member):
            text = (
                f"Object in memberlist to be converted to a member string is "
                f"not of Member."
            )
            raise NotAMember(text)
        mlist.append(memb.to_string())
    return "\n".join(mlist)
def memberlist_to_disk(memberlist, filename):
    # UNMODIFIED
    if not isinstance(memberlist, list):
        text = "Object to be written to disk is not of list[Member]."
        raise NotAMemberList(text)
    return write_file(memberlist_to_string(memberlist), filename)

def batch_update():
    # files
    for filename in files:
        try:
            list = memberlist_from_disk(filename)
            memberlist_to_disk(list, filename)
            print(f"updated {filename}")
        except Exception:
            print(f"unable to update {filename}")
            #print(traceback.format_exc())
    #folders
    for folder in folders:
        onlyfiles = [f for f in listdir(folder) if isfile(join(folder, f))]
        for file in onlyfiles:
            filename = folder+file
            try:
                list = memberlist_from_disk(filename)
                memberlist_to_disk(list, filename)
                print(f"updated {filename}")
            except Exception:
                print(f"unable to update {filename}")

batch_update()
