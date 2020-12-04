"""
For fetching ingame data from the api and comparing the old memberlist with
the new data from the api.
"""
import zerobot_common
import utilities
from logfile import LogFile
from member import Member, int_0, number_of_skills, score_labels
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
        try:
            index = current_membs.index(ingame_memb)
        except ValueError:
            # not found = new ingame member or someone renamed to this
            ingame_memb.join_date = datetime.utcnow().strftime(
                utilities.dateformat
            )
            ingame_memb.last_active = datetime.utcnow()
            joining_members.append(ingame_memb)
        else:
            # found = just joined today or stayed in clan
            existing_member = current_membs[index]
            # if the rank was needs invite, they joined the clan ingame today.
            if (existing_member.rank == "needs invite"):
                just_joined = True
            else:
                just_joined = False
            
            # load old data from last memberlist
            ingame_memb.loadFromOldName(existing_member)

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
        try:
            index = ingame_membs.index(current_memb)
        except ValueError:
            # not found = member left or renamed to one in joining
            leaving_members.append(current_memb)
        # found = stayed in clan, already markes as staying with new data.

    ## PART 3: Compare leaving and joining to find renames
    # lower than this is a decent chance of a match
    chance_threshold = 2
    for leave in leaving_members:
        #TODO: check if no runescore = no data found? nothing else to use?
        if leave.activities["runescore"][1] == 0:
            # already know nobody stayed in clan with same name, they wouldnt
            # be in leaving members if there was. no data to compare, so they
            # stay assigned to leaving members.
            clantrack_log.log(
                f"Missing data for leaving member : {leave.name}. "
                "Can not check for renames, assigned as leaving member."
            )
            continue
        # calculate match chances
        best_match = 0
        best_chance = 1000
        non_matches = 0
        for join in joining_members:
            #TODO: again check if no runescore = no data?
            if join.activities["runescore"][1] == 0:
                clantrack_log.log(
                    f"Missing data for {join.name}. Can not check if this is"
                    f" new name of {leave.name}, skipping this comparison"
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
        # renamed should be taken out of joining and leaving
        joining_members.remove(memb)
        old_name = memb.old_names[len(memb.old_names)-1]
        leaving_members.remove(old_name)
    # anyone with needs invite rank should be assigned as staying, not leaving
    leaving = leaving_members.copy()
    for memb in leaving:
        if (memb.rank == "needs invite"):
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
        for i in range(0, number_of_skills):
            # skills: [rank,level,xp]
            skills = member_info[i].split(",")
            # re-order to match activities index, and replace -1's with 0
            skill_array = [
                int_0(skills[0]),
                int_0(skills[2]),
                int_0(skills[1])
            ]
            member.skills[score_labels[i]] = skill_array
        for i in range(number_of_skills, len(member_info)):
            # stat: [rank, score]
            activivity_arr = member_info[i].split(",")
            activity = [
                int_0(activivity_arr[0]), 
                int_0(activivity_arr[1])
            ]
            member.activities[score_labels[i]] = activity
        member.on_hiscores = True
    else:
        clantrack_log.log(f"Failed to get member data : {member.name}")

def _get_clanmembers(session, ingame_members_list):
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
            ingame_members_list.append(
                Member(
                    memb_info[0], 
                    memb_info[1], 
                    int_0(memb_info[2]), 
                    int_0(memb_info[3]))
            )
        clantrack_log.log(f"Retrieved clan memberlist.")
    else:
        clantrack_log.log("Failed to retrieve clan member list.")

def get_ingame_memberlist():
    zerobot_common.drive_connect()
    # start session to try to speed up rs api requests
    session = requests.session()
    ingame_members_list = list()
    _get_clanmembers(session, ingame_members_list)
    
    # get updated stats for each member
    clantrack_log.log(f"Retrieving individual stats for members in clan...")
    for ingame_memb in ingame_members_list:
        _get_member_data(ingame_memb, session=session)
    clantrack_log.log(f"Finished retrieving individual clan members stats.")
    
    return ingame_members_list