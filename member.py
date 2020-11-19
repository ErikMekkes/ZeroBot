from math import sqrt, fabs, pow
import utilities
from datetime import datetime
import copy
import ast

# key names for skills and activities, matches ingame api result.
# using some easier lowercase naming for the ones that are used.
score_labels = [
    "overall", "attack", "defence", "strength", "constitution", "ranged", 
    "prayer", "magic", "cooking", "woodcutting", "fletching", "fishing", 
    "firemaking", "crafting", "smithing", "mining", "herblore", "agility", 
    "thieving", "slayer", "farming", "runecrafting", "hunter", 
    "construction", "summoning", "dungeoneering", "divination", "invention", 
    "archaeology", 
    
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
    "discord_roles"
]
# blank skills and activities to ensure one is always present
number_of_skills = 28
blank_skills = {}
for i in range(0, number_of_skills):
    blank_skills[score_labels[i]] = [0,0,0]
blank_activities = {}
for i in range(number_of_skills, len(score_labels)):
    blank_activities[score_labels[i]] = [0,0]
blank_misc = {}
for i in range(0, len(misc_labels)):
    blank_misc[misc_labels[i]] = ""
blank_misc["discord_roles"] = []

_boolstr = {
    True : 'TRUE',
    False : 'FALSE'
}

def _dateToStr(date) :
    """
    Returns string representation of datetime, date can be None.
    Result is either strftime of datetime or "".
    """
    if (date == None) : return ""
    return date.strftime(utilities.dateformat)

def _strToDate(str) :
    """
    Returns date representation of string.
    Result is None if string could not be read as date.
    """
    try:
        return datetime.strptime(str, utilities.dateformat)
    except ValueError :
        return None

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
        self.rank_after_gem = ""
        self.profile_link = ""
        self.leave_date = ""
        self.leave_reason = ""
        self.referral = ""
        self.discord_id = 0
        self.discord_name = ""
        self.old_names = list()
        self.last_active = None
        self.event_points = 0
        self.note1 = ""
        self.note2 = ""
        self.note3 = ""
        self.clan_xp = clan_xp
        self.kills = kills
        # skill xp and activity score dicts, guarantees presence.
        self.skills = copy.deepcopy(blank_skills)
        self.activities = copy.deepcopy(blank_activities)
        self.misc = copy.deepcopy(blank_misc)
        # not stored, based on last active, used for sorting inactives
        self.days_inactive = 0
        # not stored, only set if member originates from a search result to allow editing.
        self.result_type = ""
        self.row = None
        self.sheet = None
        self.on_hiscores = False
    def total_clues(self):
        sum = (
            self.activities["easy_clues"][1]
            + self.activities["medium_clues"][1]
            + self.activities["hard_clues"][1]
            + self.activities["elite_clues"][1]
            + self.activities["master_clues"][1]
        )
        return sum
    def __repr__(self):
        return str(self)
    def __str__(self):
        old_names = ""
        for x in self.old_names:
            old_names += x + ","
        old_names = old_names[:-1]
        skills = "["
        for v in self.skills.values():
            skills += str(v) + ", "
        skills = skills[:-2] + "]"
        activities = "["
        for v in self.activities.values():
            activities += str(v) + ", "
        activities = activities[:-2] + "]"
        misc = ""
        for _, v in self.misc.items():
            # if needed can process v to string first
            # if k == "key": misc += ... continue
            misc += str(v) + "\t"
        misc = misc[:-1]

        user_str = (
            f"{self.name}\t{self.rank}\t{self.discord_rank}\t{self.site_rank}"
            f"\t{self.join_date}\t{_boolstr[self.passed_gem]}"
            f"\t{self.rank_after_gem}\t{self.profile_link}\t{self.leave_date}"
            f"\t{self.leave_reason}\t{self.referral}\t{str(self.discord_id)}"
            f"\t{self.discord_name}\t{old_names}"
            f"\t{_dateToStr(self.last_active)}\t{str(self.event_points)}"
            f"\t{self.note1}\t{self.note2}\t{self.note3}"
            f"\t{str(self.clan_xp)}\t{str(self.kills)}"
            f"\t{skills}"
            f"\t{activities}"
            f"\t{misc}"
        )
        return user_str
    def __eq__(self, other):
        if isinstance(other, str):
            return (self.name.lower() == other.lower())
        if not isinstance(other, Member):
            # don't attempt to compare against unrelated types
            return False
        # Names in RS are unique, case insensitive
        return (self.name.lower() == other.name.lower())
    def loadFromOldName(self, other):
        """
        Load all the old data except the new ingame stats.
        """
        #self.name = name               # skip, same or renamed
        #self.rank = rank               # already updated from RS API
        self.discord_rank = other.discord_rank
        self.site_rank = other.site_rank
        self.join_date = other.join_date
        self.passed_gem = other.passed_gem
        self.rank_after_gem = other.rank_after_gem
        self.profile_link = other.profile_link
        self.leave_date = other.leave_date
        self.leave_reason = other.leave_reason
        self.referral = other.referral
        self.discord_id = other.discord_id
        self.discord_name = other.discord_name
        self.old_names = other.old_names
        self.last_active = other.last_active
        self.event_points = other.event_points
        self.note1 = other.note1
        self.note2 = other.note2
        self.note3 = other.note3
        #self.clan_xp = clan_xp         # already updated
        #self.kills = kills             # already updated
        #self.skills = {}               # already updated
        #self.activities = {}             # already updated
        for k, v in other.misc.items():
            self.misc[k] = v
    def wasActive(self, other):
        # True if made gains in any of the below
        if other.clan_xp > self.clan_xp: return True
        if other.kills > self.kills: return True
        if other.activities["runescore"][1] > self.activities["runescore"][1]: return True
        for k, v in other.skills.items():
            if v[1] > self.skills[k][1]:
                return True
        # dont have to check individual clues, comparing to self, cant lower
        if other.total_clues() > self.total_clues(): return True
        # Did not have gains in any of the above, not active
        return False
    def match(self, other):
        if not isinstance(other, Member):
            # don't attempt to compare against unrelated types
            return -1
        # can't lose clan xp, lower clan xp = not same person
        if other.clan_xp < self.clan_xp: 
            return -1
        # can't lose clan kills, lower clan kills = not same person
        if other.kills < self.kills: 
            return -1
        for k,v in other.skills.items():
            if v[1] < self.skills[k][1]:
                return -1
        # cant lose clue count, fewer clues = different person
        if other.total_clues() < self.total_clues(): return -1
        # same count but different distribution = different person
        if other.activities["easy_clues"][1] < self.activities["easy_clues"][1]: return -1
        if other.activities["medium_clues"][1] < self.activities["medium_clues"][1]: return -1
        if other.activities["hard_clues"][1] < self.activities["hard_clues"][1]: return -1
        if other.activities["elite_clues"][1] < self.activities["elite_clues"][1]: return -1
        if other.activities["master_clues"][1] < self.activities["master_clues"][1]: return -1

        # High end estimate of expected gains over a day
        clanxp_exp = 20000000       # 10M
        runescore_exp = 1000
        totalxp_exp = 20000000      # 10M
        hpxp_exp = 4000000          #  3M
        clanxp_diff = float(other.clan_xp - self.clan_xp) / clanxp_exp
        runescore_diff = fabs(float(other.activities["runescore"][1] - self.activities["runescore"][1])) / runescore_exp
        totalxp_diff = float(other.skills["overall"][1] - self.skills["overall"][1]) / totalxp_exp
        hpxp_diff = float(other.skills["constitution"][1] - self.skills["constitution"][1]) / hpxp_exp

        return (sqrt(
                pow(clanxp_diff,2) +
                pow(runescore_diff,2) +
                pow(totalxp_diff,2) +
                pow(hpxp_diff,2)
                )
        )
    def rankInfo(self):
        discord_rank = self.discord_rank
        if (self.discord_rank == ""):
            discord_rank = "Unknown"
        site_rank = self.site_rank
        if (self.site_rank == ""):
            site_rank = "Unknown"
        message = f"{self.name} - ingame: {self.rank}, discord : {discord_rank}, site: {site_rank}, passed gem: {self.passed_gem}"
        if (self.rank_after_gem != ""):
            message += f", rank after gem: {self.rank_after_gem}"
        message += "\n"
        return message
    def bannedInfo(self):
        """
        Single line string containing info on a banned member.
        """
        name_str = self.name
        max_name_length = 12
        for _ in range (0, max_name_length - len(self.name)):
            name_str += " "
        info_str = f"{name_str} | {self.note1}"
        return info_str
    def inactiveInfo(self):
        """
        Single line string representation of member, simple info only.
        Profile link surrounded by < > escape brackets.
        """
        # add spaces after name for consistent format
        name_str = self.name
        max_name_length = 12
        for _ in range (0, max_name_length - len(self.name)):
            name_str += " "
        # same for rank
        discord_rank_str = self.discord_rank
        max_rank_length = 17
        for _ in range (0, max_rank_length - len(self.discord_rank)):
            discord_rank_str += " "
        # number format for clan xp
        max_clan_xp_length = 10
        clan_xp_prepend = ''
        for _ in range (0, max_clan_xp_length - len(str(self.clan_xp))):
            clan_xp_prepend += " "
        clan_xp_str = clan_xp_prepend + str(self.clan_xp)
        # date
        last_active_str = _dateToStr(self.last_active)
        max_last_active_length = 12
        for _ in range (0, max_last_active_length - len(_dateToStr(self.last_active))):
            last_active_str += " "
        # site link
        profile_link_str = self.profile_link
        max_profile_link_length = 35
        for _ in range (0, max_profile_link_length - len(self.profile_link)):
            profile_link_str += " "
        
        info_str = ''
        info_str += (
            name_str + ' ' + discord_rank_str +
            ' ' + self.join_date +
            ' ' + clan_xp_str +
            ' ' + last_active_str +
            ' ' + profile_link_str +
            ' ' + self.discord_name
        )
        return info_str
    def load_changes(self, memberchanges):
        """
        carefully load changes by deep copy, then also reflect result in dummy
        """
        pass
        #a
        #s
        #d
        #4
        #f
    @staticmethod
    def from_string(member_str):
        """
        Reads a member from a string. Used for reading from memberlist on disk.
        member_str: Single line string with member attributes separated by tabs.

        output: A Member object.
        """
        memb_info = member_str.split('\t')
        memb = Member(memb_info[0], memb_info[1], int_0(memb_info[19]), int_0(memb_info[20]))
        memb.discord_rank = memb_info[2]
        memb.site_rank = memb_info[3]
        memb.join_date = memb_info[4]
        memb.passed_gem = (memb_info[5] == 'TRUE')
        memb.rank_after_gem = memb_info[6]
        memb.profile_link = memb_info[7]
        memb.leave_date = memb_info[8]
        memb.leave_reason = memb_info[9]
        memb.referral = memb_info[10]
        memb.discord_id = int_0(memb_info[11])
        memb.discord_name = memb_info[12]
        # weird case, split empty string = list containing empty string instead of empty list
        if (len(memb_info[13]) == 0) :
            memb.old_names = list()
        else :
            memb.old_names = memb_info[13].split(',')
        memb.last_active = _strToDate(memb_info[14])
        memb.event_points = int_0(memb_info[15])
        memb.note1 = memb_info[16]
        memb.note2 = memb_info[17]
        memb.note3 = memb_info[18]
        for num,x in enumerate(ast.literal_eval(memb_info[21])):
            memb.skills[score_labels[num]] = x
        for num,x in enumerate(ast.literal_eval(memb_info[22])):
            memb.activities[score_labels[number_of_skills + num]] = x
        # remaining entries are stored in misc with matching label.
        for i in range(23, len(memb_info)):
            memb.misc[misc_labels[i-23]] = memb_info[i]
        memb.misc["discord_roles"] = ast.literal_eval(memb.misc["discord_roles"])
        return memb
    def to_string(self):
        """
        Writes a member to a string. Used for writing to memberlist on disk.
        member: Member object.

        output: Single line string with member attributes separated by tabs.
        """
        member_str = str(self)
        return member_str
    def load_sheet_changes(self, other):
        """
        Load all the sheet data.
        Assumes there was a match on name, profile link or discord_id.
        """
        self.name = other.name
        self.rank = other.rank
        self.discord_rank = other.discord_rank
        self.site_rank = other.site_rank
        self.join_date = other.join_date
        self.passed_gem = other.passed_gem
        self.rank_after_gem = other.rank_after_gem
        self.profile_link = other.profile_link
        self.leave_date = other.leave_date
        self.leave_reason = other.leave_reason
        self.referral = other.referral
        self.discord_id = other.discord_id
        self.discord_name = other.discord_name
        self.old_names = other.old_names
        self.last_active = other.last_active
        self.event_points = other.event_points
        self.note1 = other.note1
        self.note2 = other.note2
        self.note3 = other.note3
    @staticmethod
    def from_sheet(memb_info):
        """
        Read a member from a list of attributes that follows the same format
        as the rows on the spreadsheet.
        """
        memb = Member(memb_info[0],memb_info[1],0,0)
        memb.discord_rank = memb_info[2]
        memb.site_rank = memb_info[3]
        memb.join_date = memb_info[4]
        memb.passed_gem = (memb_info[5] == "TRUE")
        memb.rank_after_gem = memb_info[6]
        memb.profile_link = memb_info[7]
        memb.leave_date = memb_info[8]
        memb.leave_reason = memb_info[9]
        memb.referral = memb_info[10]
        memb.discord_id = int_0(memb_info[11])
        memb.discord_name = memb_info[12]
        # prevent empty string case, splitting an empty string gives a list
        # containing empty string instead of the empty list we want.
        if (len(memb_info[13]) == 0) :
            memb.old_names = list()
        else :
            memb.old_names = memb_info[13].split(',')
        memb.last_active = _strToDate(memb_info[14])
        memb.event_points = int_0(memb_info[15])
        memb.note1 = memb_info[16]
        memb.note2 = memb_info[17]
        memb.note3 = memb_info[18]
        return memb
    def to_sheet(self):
        """
        Returns a list of attributes that follows the same format as the rows
        on the spreadsheet. Only attributes that might need an update.
        """
        old_names_str = ''
        for i in range(0,len(self.old_names)):
            if (i == 0):
                old_names_str += self.old_names[i]
            else:
                old_names_str += "," + self.old_names[i]
        
        memb_info = [
            self.name,
            self.rank,
            self.discord_rank,
            self.site_rank,
            self.join_date,
            _boolstr[self.passed_gem],
            self.rank_after_gem,
            self.profile_link,
            self.leave_date,
            self.leave_reason,
            self.referral,
            str(self.discord_id),
            self.discord_name,
            old_names_str,
            _dateToStr(self.last_active),
            str(self.event_points),
            self.note1,
            self.note2,
            self.note3
        ]
        return memb_info
    def name_before(self, other):
        """
        True iff this name comes before the name of other alphabetically. 
        Used for sorting memberlists.
        """
        a = list(self.name.lower())
        b = list(other.name.lower())
        for num, c in enumerate(a):
            if num == len(b):
                # b ran out of chars already and was equal til now = false
                return False
            if c == ' ' :
                # lowest character = false
                return False
            if c == b[num]:
                # if at last char in a, equal or b still has more chars = true
                if num+1 == len(a): return True
                # equal characters = check next
                continue
            return c < b[num]
        return True

def int_0(int_str):
    """
    custom int() function to parse spreadsheet cells and api results.
    returns 0 for empty strings.
    returns 0 for a -1 string or int.
    returns 0 for decimal numbers.
    """
    # if its an actual int return 0 if -1, otherwise return the int
    if isinstance(int_str, int):
        if int_str == -1:
            return 0
        return int_str
    
    # not an int, assuming string
    # filter out empty strings
    if int_str == '':
        return 0
    # filter out decimal number format
    if '.' in int_str:
        return 0
    # finally try to parse as int
    result = int(int_str)
    # if the given number string was -1
    if result == -1:
        return 0
    return result

def validSiteProfile(profile_link):
    # https://zer0pvm.com/members/2790316
    https_base_url = 'https://zer0pvm.com/members/'
    if (https_base_url in profile_link):
        try:
            site_id = int(profile_link[len(https_base_url):len(profile_link)])
            if (len(str(site_id)) == 7):
                return True
            return False
        except ValueError:
            return False
    return False

def validDiscordId(discord_id):
    # discord ids are based on time of disc creation. At least 17 digits.
    if isinstance(discord_id, int):
        if (len(str(discord_id)) >= 17):
            return True
        return False

    # not int, assuming str
    if (len(discord_id) < 17):
        return False
    try:
        int(discord_id)
        return True
    except ValueError:
        return False