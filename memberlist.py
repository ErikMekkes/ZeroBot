from utilities import read_file, write_file
from member import Member
from exceptions import NotAMember, NotAMemberList

def memberlist_get(memberlist, id, match_type="name"):
    """
    Finds member in the memberlist that can be identified by id
    Assumes unique ids, returns first result only, Default match is by name.
     - match_type: name (default), profile_link, discord_id (integer)
    """
    for memb in memberlist:
        if getattr(memb, match_type) == id:
            return memb
    return None
def memberlist_to_disk(memberlist, filename):
    """
    Writes a memberlist to disk.
    memberlist: A list of Member objects.
    filename: A filename string.

    output: None, file now contains members as lines separated by newline 
    (\n) characters with attributes separated by tabs.
    """
    if not isinstance(memberlist, list):
        text = "Object to be written to disk is not of list[Member]."
        raise NotAMemberList(text)
    return write_file(memberlist_to_string(memberlist), filename)
def memberlist_from_disk(filename):
    """
    Reads a memberlist from disk.
    filename: A filename string pointing to a memberlist file containing 
    members as lines separated by newline (\n) characters with attributes 
    separated by tabs.

    output: A list of Member objects.
    """
    memberlist_str = read_file(filename)
    return memberlist_from_string(memberlist_str)
def memberlist_from_string(memberlist_string):
    """
    Reads a memberlist from a string. Used for reading memberlist from disk.
    memberlist_string: A string containing members as lines separated by
    newline (\n) characters with attributes separated by tabs.

    output: A list of Member objects.
    """
    try:
        result = list()
        memberlist_array = memberlist_string.splitlines()
        for memb_str in memberlist_array:
            result.append(Member.from_string(memb_str))
        return result
    except Exception:
        text = "String to be read as memberlist is not of list[Member]"
        raise NotAMemberList(text)
def memberlist_to_string(memberlist):
    """
    Writes a memberlist to a string. Used for writing memberlist to disk.
    memberlist: A list of Member objects.

    output: A string containing members as lines separated by newline (\n) 
    characters with attributes separated by tabs.
    """
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
    return '\n'.join(mlist)


# for sorting memberlist accounting for jagex spaces
def memberlist_sort_name(mlist):
    if len(mlist) == 0: return
    if len(mlist) == 1: return
    for i in range(1, len(mlist)):
        key = mlist[i]

        j = i-1
        while j >= 0 and key.name_before(mlist[j]):
            mlist[j+1] = mlist[j]
            j -= 1
        mlist[j+1] = key

# for sorting memberlist accounting for jagex spaces
def memberlist_sort_days_inactive(mlist):
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
def memberlist_sort_clan_xp(mlist):
    if len(mlist) == 0: return
    if len(mlist) == 1: return
    for i in range(1, len(mlist)):
        key = mlist[i]

        j = i-1
        while j >= 0 and key.clan_xp < mlist[j].clan_xp:
            mlist[j+1] = mlist[j]
            j -= 1
        mlist[j+1] = key

##### No longer needed #######

def memberlist_append(memberlist, member):
    "Adds member object to the memberlist"
    if not isinstance(member, Member):
        text = "Object to append to memberlist is not of Member"
        raise NotAMember(text)
    if not isinstance(memberlist, list):
        text = "Object to be appended to is not of list[Member]."
        raise NotAMemberList(text)
    memberlist.append(member)

class Memberlist(object):
    """
    Memberlist representation. Provides operations for:
    - reading / writing to disk
    - reading / writing to sheet
    - adding / removing / editing members
    """
    def __init__(self):
        self.list = []
    def __contains__(self, key):
        return key in self.list
    def __iter__(self):
        return self.list.__iter__()
    def __len__(self):
        return len(self.list)
    def get(self,member,alt=None):
        for x in self.list:
            if x == member:
                return x
        if alt is not None:
            return alt
        return None
    @staticmethod
    def from_disk(filename):
        return memberlist_from_disk(filename)
    def to_disk(self, filename):
        return memberlist_to_disk(self, filename)
    @staticmethod
    def from_string(memberlist_string):
        return memberlist_from_string(memberlist_string)
    def to_string(self):
        return memberlist_to_string(self)