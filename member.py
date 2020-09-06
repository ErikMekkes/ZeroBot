from math import sqrt, fabs, pow
from datetime import datetime

_skilldict = {
    "Overall" : 0
}

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
    return date.strftime("%Y-%m-%d")

def _strToDate(str) :
    """
    Returns date representation of string.
    Result is None if string could not be read as date.
    """
    try:
        return datetime.strptime(str, "%Y-%m-%d")
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
        self.rank_after_gem = ""
        self.passed_gem = False
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
        self.runescore = 0
        # total xp & skill xp
        self.skills = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        self.highest_mage = ""
        self.highest_melee = ""
        self.highest_range = ""
        # not stored on sheet, based on last active, used for sorting inactives
        self.days_inactive = 0
        # not stored on sheet, only set if member originates from a search result to allow editing.
        self.result_type = ""
        self.row = None
        self.sheet = None
    def __str__(self):
        user_str = f"{self.name}\t{self.rank}\t{self.discord_rank}\t{self.site_rank}\t{self.join_date}\t{_boolstr[self.passed_gem]}\t{self.rank_after_gem}"
        user_str += ("\t" + self.profile_link + "\t" + self.leave_date + "\t" + self.leave_reason + "\t" + self.referral + "\t" + str(self.discord_id) + "\t" + self.discord_name + "\t")
        for num,x in enumerate(self.old_names):
            if (num != 0) : user_str += ","
            user_str += x
        user_str += "\t" + _dateToStr(self.last_active) + "\t" + str(self.event_points) + "\t" + self.note1 + "\t" + self.note2 + "\t" + self.note3 + "\t" + str(self.clan_xp) + "\t" + str(self.kills) + "\t" + str(self.runescore)
        for x in self.skills:
            user_str += "\t" + str(x)
        user_str += f"\t{self.highest_mage}\t{self.highest_melee}\t{self.highest_range}"
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
        #self.name = name               # same
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
        #self.runescore = 0             # already updated
        #self.skills = []               # already updated
        self.highest_mage = other.highest_mage
        self.highest_melee = other.highest_melee
        self.highest_range = other.highest_range
    def wasActive(self, other):
        # True if made gains in any of the below
        if other.clan_xp > self.clan_xp : return True
        if other.kills > self.kills : return True
        if other.runescore > self.runescore : return True
        for num,x in enumerate(other.skills):
            if x > self.skills[num] : return True
        # Did not have gains in any of the above, false
        return False
    def match(self, other):
        if not isinstance(other, Member):
            # don't attempt to compare against unrelated types
            return -1
        # can't lose xp, lower xp = not same person
        if other.clan_xp < self.clan_xp : 
            return -1
        for num,x in enumerate(other.skills):
            if x < self.skills[num] : 
                return -1
        # can't lose kills, lower kills = not same person
        if other.kills < self.kills : 
            return -1

        # High end estimate of expected gains over a day
        clanxp_exp = 20000000       # 10M
        runescore_exp = 1000
        totalxp_exp = 20000000      # 10M
        hpxp_exp = 4000000          #  3M
        clanxp_diff = float(other.clan_xp - self.clan_xp) / clanxp_exp
        runescore_diff = fabs(float(other.runescore - self.runescore)) / runescore_exp
        totalxp_diff = float(other.skills[0] - self.skills[0]) / totalxp_exp
        hpxp_diff = float(other.skills[4] - self.skills[4]) / hpxp_exp

        return (sqrt(
                pow(clanxp_diff,2) +
                pow(runescore_diff,2) +
                pow(totalxp_diff,2) +
                pow(hpxp_diff,2)
                )
        )
    def asList(self):
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
            self.note3,
            self.clan_xp,
            self.kills,
            self.runescore
        ]
        for x in self.skills:
            memb_info.append(x)
        memb_info += [
            self.highest_mage,
            self.highest_melee,
            self.highest_range
        ]
        return memb_info
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
    def minimalInfo(self):
        """
        Single line string representation of member, simple info only.
        Profile link surrounded by < > escape brackets.
        """
        clan_xp_str = str(self.clan_xp)
        discord_id_str = str(self.discord_id)
        info_str = self.rankInfo()
        info_str += (
            ', <' + self.profile_link + '>' +
            ', discord_name: ' + self.discord_name +
            ', discord_id: ' + discord_id_str +
            ', joined: ' + self.join_date +
            ', clan xp: ' + clan_xp_str +
            ', last active: ' + _dateToStr(self.last_active)
        )
        return info_str
    def minimalInfoOld(self):
        """
        Single line string representation of member, simple info only.
        Profile link surrounded by < > escape brackets.
        """
        clan_xp_str = str(self.clan_xp)
        discord_id_str = str(self.discord_id)
        info_str = "Old member, last known info: "
        info_str += self.rankInfo()
        info_str += (
            ', <' + self.profile_link + '>' +
            ', discord_name: ' + self.discord_name +
            ', discord_id: ' + discord_id_str +
            ', joined: ' + self.join_date +
            ', left: ' + self.leave_date +
            ', clan xp: ' + clan_xp_str
        )
        return info_str
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



# custom int() function that returns 0 for empty strings
# prevents int parse errors when info is missing
def int_0(int_str):
    # filter out empty strings
    if int_str == '':
        return 0
    # filter out decimal number format
    if '.' in int_str:
        return 0
    else:
        return int(int_str)

def read_member(memb_info):
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
    memb.runescore = int_0(memb_info[21])
    #add skills
    for num in range(0, len(memb.skills)):
        memb.skills[num] = int_0(memb_info[num+22])
    memb.highest_mage = memb_info[51]
    memb.highest_melee = memb_info[52]
    memb.highest_range = memb_info[53]
    return memb

# for sorting memberlist accounting for jagex spaces
def _name_smaller(this, that):
    """
    True iff this comes before that alphabetically.
    """
    a = list(this.lower())
    b = list(that.lower())
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

# for sorting memberlist accounting for jagex spaces
def memblist_sort(mlist):
    if len(mlist) == 0: return
    if len(mlist) == 1: return
    for i in range(1, len(mlist)):
        key = mlist[i]

        j = i-1
        while j >= 0 and _name_smaller(key.name, mlist[j].name):
            mlist[j+1] = mlist[j]
            j -= 1
        mlist[j+1] = key

# for sorting memberlist accounting for jagex spaces
def memblist_sort_days_inactive(mlist):
    if len(mlist) == 0: return
    if len(mlist) == 1: return
    for i in range(1, len(mlist)):
        key = mlist[i]

        j = i-1
        while j >= 0 and key.days_inactive > mlist[j].days_inactive:
            mlist[j+1] = mlist[j]
            j -= 1
        mlist[j+1] = key

# for sorting memberlist accounting for jagex spaces
def memblist_sort_clan_xp(mlist):
    if len(mlist) == 0: return
    if len(mlist) == 1: return
    for i in range(1, len(mlist)):
        key = mlist[i]

        j = i-1
        while j >= 0 and key.clan_xp < mlist[j].clan_xp:
            mlist[j+1] = mlist[j]
            j -= 1
        mlist[j+1] = key

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

# there are a few unique id's that are shorter but valid
# perhaps these are older legacy ones? if more show up need to edit validation.
discord_id_exceptions = [
    "77714252336467968",
    77714252336467968,
    "82996849245425664",
    82996849245425664
]

def validDiscordId(discord_id):
    # 286608712628699138
    # int?
    if discord_id in discord_id_exceptions:
        return True
    
    if isinstance(discord_id, int):
        if (len(str(discord_id)) == 18):
            return True
        return False

    # not int, assuming str
    if (len(discord_id) != 18):
        return False
    try:
        int(discord_id)
        return True
    except ValueError:
        return False