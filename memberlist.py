from utilities import read_file, write_file
from member import Member
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
    matches in old names of members. Result is a list that may be empty.
    The id must be either:
     - A valid discord id, integer with 17+ digits (705523860375863427)
     - A valid profile link, string url (https://zer0pvm.com/members/2790316)
     - A valid ingame name, string of 1 to 12 characters, case insensitive
    """
    results = list()
    for memb in memberlist:
        if memb.matches_id(id):
            memb.result_type = "exact"
            results.append(memb)
        elif isinstance(id, str):
            for old_name in memb.old_names:
                if (old_name.lower() == id):
                    memb.result_type = "old name"
                    results.append(memb)
    return results
def memberlist_add(memberlist, member):
    """
    Appends the member element to the memberlist by reference. The member 
    element can still be modified after being added.
    """
    if not isinstance(member, Member):
        text = "Object to append to memberlist is not of Member."
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