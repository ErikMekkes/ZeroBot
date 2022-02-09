"""
For fetching ingame data from the rs api and comparing the old memberlist with
the new data from the rs api. Basically Runeclan for just our clanmembers, but
with some additional highscore stats like clues and wildy kills.

Is able to very accurately identify new names for people in clan that renamed.
Does so by comparing ingame memberlist changes and individual member stats.
"""
import os
import zerobot_common
import utilities
from utilities import int_0
from logfile import LogFile
from member import Member, skill_labels, activity_labels
from memberlist import CompareResult, memberlist_from_disk
from exceptions import NotAMember, NotAMemberList
# external imports
import requests
from datetime import datetime
import copy

# links to jagex API
_memberlist_base_url = (
    "http://services.runescape.com/"
    + "m=clan-hiscores/members_lite.ws?clanName="
)
_member_base_url = (
    "https://secure.runescape.com/"
    + "m=hiscore/index_lite.ws?player="
)

# logfile for clantrack
clantrack_log = LogFile("logs/clantrack")

def compare_lists(ingame_members, current_members):
    """
    Makes no changes to the lists, just returns an accuracte comparison.
    The comparison result is split in staying, joining, renamed and leaving 
    member lists. All members in them are updated with most recent stats.

    The new memberlist can be constructed as staying + joining + renamed.
    """
    clantrack_log.log(f"Comparing memberlist in memory with ingame one...")
    ingame_membs = copy.deepcopy(ingame_members)
    current_membs = copy.deepcopy(current_members)
    # create lists to compare members
    staying_members = list()
    joining_members = list()
    leaving_members = list()
    renamed_members = list()
    ## PART 1: find possible joining members, load new data if stayed in clan
    # loop through ingame members list, try to find in current members list
    for ingame_memb in ingame_membs:
        existing_member = None
        for cm in current_membs:
            if cm.name.lower() == ingame_memb.name.lower():
                existing_member = cm
        if existing_member is None:
            # not found = new ingame member or someone renamed to this
            ingame_memb.join_date = datetime.utcnow().strftime(
                utilities.dateformat
            )
            ingame_memb.last_active = datetime.utcnow()
            joining_members.append(ingame_memb)
        else:
            # found = just joined today or stayed in clan

            # if the rank was needs invite, they joined the clan ingame today.
            if (existing_member.rank == "needs invite"):
                just_joined = True
            else:
                just_joined = False
            
            # load old data from last memberlist
            ingame_memb.loadFromOldName(existing_member)
            #TODO: if not on hiscores also load ingame stats from old name, loadfromold doesnt.

            # if last active is not set in future...
            if (
                ingame_memb.last_active == None 
                or ingame_memb.last_active < datetime.utcnow()
            ):
                # and they have been active, update last_active to today
                if (existing_member.wasActive(ingame_memb)):
                    ingame_memb.last_active = datetime.utcnow()
            # if they just joined, assign them as joining.
            if (just_joined):
                joining_members.append(ingame_memb)
            else:
                staying_members.append(ingame_memb)
            

    ## PART 2: find possible leaving members
    # loop through current members list, try to find in ingame members list
    for current_memb in current_membs:
        found = False
        for im in ingame_membs:
            if im.name.lower() == current_memb.name.lower(): found = True
        if not(found):
            # member left or renamed to one in joining
            leaving_members.append(current_memb)
        # found = stayed in clan, already handled by PART1 loop.

    ## PART 3: Compare leaving and joining to find renames
    # lower than this is a decent chance of a match
    chance_threshold = 2
    for leave in leaving_members:
        # this is a check on current member data, if there was no ingame data before then
        # there is no information to use to find their new name.
        #TODO: perhaps there might be some limited info to use, 
        #    like (previous) name similarity / rank / comments / clan list stats.
        #TODO: use not(.on_hiscores) after adding it to disk save part of member
        if leave.activities["runescore"][1] == 0:
            # already know nobody stayed in clan with the same name, they wouldnt
            # be in leaving members if there was. No old data = cant find new name.
            clantrack_log.log(
                f"Current member marked as leaving has no stats data : {leave.name}. "
                "Can not compare with new members for renames, removing from clan."
            )
            continue
        # calculate match chances
        best_match = 0
        best_chance = 1000
        non_matches = 0
        for join in joining_members:
            #TODO: use not(.on_hiscores) after making it stored on disk
            if join.activities["runescore"][1] == 0:
                # TODO: this case does have some data from clan list: name, rank, clanxp, kills
                clantrack_log.log(
                    f"Missing data for {join.name}. Can not check if this is"
                    f" new name of {leave.name}, skipping this comparison option."
                )
                non_matches += 1
                continue
            chance = leave.match(join)
            if (chance == -1):
                non_matches += 1
                continue
            if (chance < best_chance):
                best_chance = chance
                best_match = join
            else :
                non_matches += 1
        
        if non_matches == len(joining_members):
            # all joining are ruled out immediately by lower stats or no data,
            # they stay assigned as leaving members.
            clantrack_log.log(
                f"{leave.name} left the clan, no possible match in joiners"
            )
        else:
            msg = (
                f"{leave.name} renamed to {best_match.name} "
                f"with {best_chance} chance?"
            )
            if (best_chance < chance_threshold):
                # good enough rename chance, should have updated stats and 
                # and assigned to renamed.
                clantrack_log.log(f"{msg} -- likely, considering as renamed")
                # if new name was a previous name, remove from old names.
                if best_match.name in leave.old_names:
                    leave.old_names.remove(best_match.name)
                # add previous name to old names
                leave.old_names.append(leave.name)

                # load all the old info into the new name object
                best_match.loadFromOldName(leave)
                # Member was active, they renamed. update last active with 
                # today if it was not set in the future.
                if (
                    best_match.last_active == None 
                    or best_match.last_active < datetime.utcnow()
                ):
                    best_match.last_active = datetime.utcnow()
                
                # Final step, mark as renamed. MUST also be removed from 
                # leaving and joining, is done below, cant do while iterating.
                renamed_members.append(best_match)
            else:
                # not a good enough rename chance, stays assigned as leaving
                clantrack_log.log(f"{msg} -- unlikely, removing from clan")
    
    ## PART 4: sort out renamed and members who still needed invites in lists.
    for memb in renamed_members:
        # renamed = joining, with entry id set from leave so this should work
        joining_members.remove(memb)
        leaving_members.remove(memb)
        continue
        # remove from joining
        for jm in joining_members:
            if jm.name == memb.name:
                joining_members.remove(jm)
                break # otherwise its removal while iterating
        # remove from leaving
        old_name = memb.old_names[len(memb.old_names)-1]
        for lm in leaving_members:
            if lm.name == old_name:
                leaving_members.remove(lm)
                break # otherwise its removal while iterating
    
    # anyone with needs invite rank should be assigned as staying, not leaving
    leaving = leaving_members.copy()
    for memb in leaving:
        if (memb.rank == "needs invite"):
            clantrack_log.log(f"{memb.name} was not invited yet, kept on list.")
            leaving_members.remove(memb)
            staying_members.append(memb)
            continue
    # joining members is already correct by now, no further changes needed

    clantrack_log.log(f"Finished comparing memberlists.")
    return CompareResult(
        staying_members, joining_members, leaving_members, renamed_members
    )

def _get_member_data(member, session=None, attempts=0):
    if not isinstance(member, Member):
        raise NotAMember("Object to fetch ingame data for is not of Member")
    try:
        if session is None:
            req_resp = requests.get(_member_base_url+member.name, timeout=10)
        else:
            req_resp = session.get(_member_base_url+member.name, timeout=10)
    except requests.exceptions.Timeout:
        if attempts > 5:
            clantrack_log.log(f"Failed to get member data : {member.name}")
            return
        return _get_member_data(member, session, attempts=attempts+1)
    except Exception:
        if attempts > 5:
            clantrack_log.log(f"Failed to get member data : {member.name}")
            return
        return _get_member_data(member, session, attempts=attempts+1)

    if (req_resp.status_code == requests.codes["ok"]):
        member_info = req_resp.text.splitlines()
        for i in range(0, len(skill_labels)):
            # skills: [rank,level,xp]
            skills = member_info[i].split(",")
            # re-order to match activities index, and replace -1's with 0
            skill_array = [
                int_0(skills[0]),
                int_0(skills[2]),
                int_0(skills[1])
            ]
            member.skills[skill_labels[i]] = skill_array
        for i in range(0, len(activity_labels)):
            # stat: [rank, score], starts after skills till end of activities
            activivity_arr = member_info[len(skill_labels)+i].split(",")
            activity = [
                int_0(activivity_arr[0]), 
                int_0(activivity_arr[1])
            ]
            member.activities[activity_labels[i]] = activity
        member.on_hiscores = True
    else:
        clantrack_log.log(f"Failed to get member data : {member.name}")

def _get_clanmembers(
    session,
    ingame_members_list,
    highest_id,
    highest_entry_id
):
    clantrack_log.log(f"Starting clan memberlist retrieval...")
    if not isinstance(ingame_members_list, list):
        text = (
            "Object to fetch ingame data for is not of list[Member]."
        )
        raise NotAMemberList(text)
    try:
        memb_list_api_result = session.get(
            _memberlist_base_url+zerobot_common.rs_api_clan_name, timeout=10
        )
    except requests.exceptions.Timeout:
        clantrack_log.log(f"Retrying clan memberlist retrieval...")
        return _get_clanmembers(session, ingame_members_list)

    # got a response, need to check if good response
    if (memb_list_api_result.status_code == requests.codes["ok"]):
        # split per line, remove first junk description line
        members_strings = memb_list_api_result.text.splitlines()
        members_strings.pop(0)

        # go through lines of member info
        for memb_str in members_strings:
            # replace jagex's non breaking spaces (char 160) with 
            # (char 32) normal spaces
            memb_str = memb_str.replace(" "," ")
            memb_info = memb_str.split(",")
            memb = Member(
                memb_info[0], 
                memb_info[1], 
                int_0(memb_info[2]), 
                int_0(memb_info[3])
            )
            memb.id = highest_id
            highest_id += 1
            memb.entry_id = highest_entry_id
            highest_entry_id += 1
            ingame_members_list.append(memb)
        clantrack_log.log(f"Retrieved clan memberlist.")
    else:
        clantrack_log.log("Failed to retrieve clan member list.")

def get_ingame_memberlist(highest_id: int, highest_entry_id: int):
    #TODO: should remain disabled until .on_hiscores is disk saved
    if zerobot_common.use_cached_ingame_data:
        date_str = datetime.utcnow().strftime(utilities.dateformat)
        cached_data_file = (
            "memberlists/current_members/ingame_membs_" + date_str + ".txt"
        )
        if os.path.exists(cached_data_file):
            clantrack_log.log(
                f"Using cached ingame data from {date_str}..."
            )
            return memberlist_from_disk(cached_data_file)
    zerobot_common.drive_connect()
    # start session to try to speed up rs api requests
    session = requests.session()
    ingame_members_list = list()
    _get_clanmembers(session, ingame_members_list, highest_id, highest_entry_id)
    
    # get updated stats for each member
    clantrack_log.log(f"Retrieving individual stats for members in clan...")
    for ingame_memb in ingame_members_list:
        _get_member_data(ingame_memb, session=session)
    clantrack_log.log(f"Finished retrieving individual clan members stats.")
    
    return ingame_members_list