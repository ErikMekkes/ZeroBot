import utilities
from utilities import read_file, write_file
from member import Member
from datetime import datetime
from exceptions import NotAMember, NotAMemberList
import copy

def memberlist_get(
    memberlist,
    id
):
    """
    Find a member in a memberlist that can be identified by the id.
    The id must be either:
     - A valid discord id, integer with 17+ digits (705523860375863427)
     - A valid profile link, string url (https://zer0pvm.com/members/2790316)
     - A valid ingame name, string of 1 to 12 characters, case insensitive
    
    Assumes unique ids, returns the first match found. None if no match found.
    """
    for memb in memberlist:
        if memb.matches_id(id):
            return memb
    return None
def memberlist_get_all(
    memberlist,
    id
):
    """
    Find members in a memberlist that can be identified by the id. Includes
    partial name matches and matches in old names of members. 
    Result is a list that may be empty or very large if partial name is vague.
    The id must be either:
     - A valid discord id, integer with 17+ digits (705523860375863427)
     - A valid profile link, string url (https://zer0pvm.com/members/2790316)
     - A valid ingame name, string of 1 to 12 characters, case insensitive
    """
    results = list()
    for memb in memberlist:
        if memb.matches_id(id):
            memb.result_type = "exactname"
            results.append(memb)
        # include partial name matches
        elif str(id).lower() in memb.name.lower():
            memb.result_type = "partialname"
            results.append(memb)
        else:
            for old_name in memb.old_names:
                if (old_name.lower() == id):
                    memb.result_type = "oldname"
                    results.append(memb)
    return results
def memberlist_add(memberlist, member):
    """
    Appends the member element to the memberlist by reference. The member 
    element can still be modified after being added.
    """
    if not isinstance(member, Member):
        text = f"Object to append to memberlist is not of Member: {str(member)}"
        raise NotAMember(text)
    memberlist.append(member)
def memberlist_remove(memberlist, member):
    """
    Find a member in a memberlist and remove it from the memberlist. Does 
    nothing if not found. Returns the member that was removed.
    - member: Can be an actual member object or an id that identifies one.

    If member is not of type Member it is treated as id, searches memberlist
    for member with matching id using memberlist_get and removes that member.
    """
    if not isinstance(member, Member):
        member = memberlist_get(memberlist, member)
    if member is not None:
        memberlist.remove(member)
    return member
def memberlist_move(from_list, to_list, member):
    """
    Moves a member from one memberlist to another. Does nothing if not found.
    - member: Can be an actual member object or an id that identifies one.

    Returns the member element moved between lists by reference, The member 
    element can still be modified after being moved.
    """
    member = memberlist_remove(from_list, member)
    memberlist_add(to_list, member)
    return member
def memberlist_to_disk(memberlist, filename):
    """
    Writes a memberlist to disk.
    memberlist: A list of Member objects.
    filename: A filename string.

    output: None, file now contains members as lines separated by newline 
    (\n) characters with attributes separated by tabs.
    """
    if not isinstance(memberlist, list):
        text = f"Object to be written to disk is not of list[Member]."
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
            try:
                result.append(Member.from_string(memb_str))
            except Exception as ex:
                text = f"String to be read as member is not a Member: {memb_str}"
                raise NotAMember(text)
        return result
    except Exception as ex:
        text = f"String to be read as memberlist is not of list[Member]. {ex}"
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
                f"not of Member: {str(memb)}"
            )
            raise NotAMember(text)
        mlist.append(memb.to_string())
    return "\n".join(mlist)


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
def memberlist_sort_clan_xp(mlist,asc=True):
    memberlist_sort(mlist, clan_xp_cond, asc=asc)
# for sorting memberlist accounting for jagex spaces
def memberlist_sort_leave_date(mlist, asc=True):
    memberlist_sort(mlist, leave_date_cond, asc=asc)

# for sorting memberlist accounting for jagex spaces
def memberlist_sort(mlist, sort_cond, asc=True):
    if len(mlist) == 0: return
    if len(mlist) == 1: return
    for i in range(1, len(mlist)):
        key = mlist[i]

        j = i-1
        while j >= 0 and sort_cond(key, mlist[j], asc):
            mlist[j+1] = mlist[j]
            j -= 1
        mlist[j+1] = key

def clan_xp_cond(memb_1, memb_2, asc=True):
    if memb_1.clan_xp < memb_2.clan_xp:
        return asc
    return not asc

def hosts_cond(memb1, memb2, asc=True):
    hosts1 = 0
    for x in memb1.notify_stats.values():
        hosts1 += x
    hosts2 = 0
    for x in memb2.notify_stats.values():
        hosts2 += x
    if hosts1 < hosts2:
        return asc
    return not asc
def leave_date_cond(memb_1, memb_2, asc=True):
    if memb_1.leave_date < memb_2.leave_date:
        return asc
    return not asc
def runescore_cond(memb_1, memb_2, asc=True):
    if memb_1.activities["runescore"][1] < memb_2.activities["runescore"][1]:
        return asc
    return not asc
def wildykills_cond(memb_1, memb_2, asc=True):
    if memb_1.kills < memb_2.kills:
        return asc
    return not asc
def clues_cond(memb_1, memb_2, asc=True):
    if memb_1.total_clues() < memb_2.total_clues():
        return asc
    return not asc

class CompareResult():
    """
    CompareResult(staying, joining, leaving, renamed).
    """
    def __init__(self, staying, joining, leaving, renamed):
        self.staying = staying
        self.joining = joining
        self.leaving = leaving
        self.renamed = renamed
    def summary_rows(self):
        """
        Gives a spreadsheet rows representation of memberlist changes
        """
        summary = list()
        summary.append([(
            "Memberlist changes from automatic update on "
            + datetime.utcnow().strftime(utilities.dateformat)
        )])
        summary.append(["\nRenamed Clan Members:"])
        for memb in self.renamed:
            old_name = memb.old_names[len(memb.old_names)-1]
            summary.append([f"{old_name} -> {memb.name}"])
        summary.append(["\nLeft Clan:"])
        for memb in self.leaving:
            summary.append([memb.name])
        summary.append(["\nJoined Clan:"])
        for memb in self.joining:
            summary.append([memb.name])
        summary.append(["- - - - - - - - - - - - - - - - - - - - - - - - -"])

        return summary
    def summary(self):
        """
        Gives a text representation of memberlist changes
        """
        rows = self.summary_rows()
        summary = ""
        for line in rows:
            summary += (line[0] + "\n")
        return summary

def memberlist_compare_stats(newlist, oldlist):
    """
    Returns the difference in stats for each member in both lists.
    """
    staying_members = []
    joining_members = []
    leaving_members = copy.deepcopy(oldlist)
    renamed_members = []
    # first pass to identify who stayed, joined and renamed
    for memb in newlist:
        # try finding by discord id, most likely
        old_memb = memberlist_get(oldlist, memb.discord_id)
        # try site link
        if old_memb is None:
            old_memb = memberlist_get(oldlist, memb.profile_link)
        # try same ingame name
        if old_memb is None:
            old_memb = memberlist_get(oldlist, memb.name)
        # try old names if still not found
        if old_memb is None:
            for old_name in memb.old_names:
                old_memb = memberlist_get(oldlist, old_name)
                if old_memb is not None: break
        
        # not found = mark as new member
        if old_memb is None:
            joining_members.append(memb)
            continue
        # not none = found = mark as stayed and add comparison result
        staying_members.append(memb.compare_stats(old_memb))
        # different name = mark as renamed
        if old_memb.name != memb.name:
            memb.old_names = [old_memb.name]
            renamed_members.append(memb)
        # remove from leaving
        leaving_members.remove(old_memb)
        
    return CompareResult(
        staying_members, joining_members, leaving_members, renamed_members
    )
