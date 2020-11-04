'''
Almost entirely self contained, need to work out:
- code that calls updatelist (timer and command)    make new cog for tracking?
- zerobot_common.rs_api_clan_name       only used here but ok as setting, move retrieve here
- zerobot_common.logfile                make one here? in cog? both should work its append?
- zerobot_common.drive_connect()        not bad, maybe utility but needs drive stuff?
- zerobot_common.current_members_sheet  ok common use
- zerobot_common.old_members_sheet      ok common use
- zerobot_common.recent_changes_sheet   ok common use
'''
import zerobot_common
import requests
# for date strings
import time
import os
from datetime import datetime
# to store data as member objects
from member import Member, read_member, int_0
from gspread_formatting import format_cell_range, CellFormat, Color
from sheet_ops import SheetParams, read_member_sheet, write_member_sheet

# links to jagex API
_memberlist_base_url = 'http://services.runescape.com/m=clan-hiscores/members_lite.ws?clanName='
_member_base_url = 'https://secure.runescape.com/m=hiscore/index_lite.ws?player='

class UpdateResult():
    """
    UpdateResult(joining, leaving, renamed).
    """
    def __init__(self, joining, leaving, renamed):
        self.joining = joining
        self.leaving = leaving
        self.renamed = renamed
    def summary_rows(self):
        """
        Gives a spreadsheet rows representation of memberlist changes
        """
        summary = list()
        summary.append(["Memberlist changes from automatic update on " + datetime.utcnow().strftime("%Y-%m-%d")])
        summary.append(["\nRenamed Clan Members:"])
        for memb in self.renamed:
            old_name = memb.old_names[len(memb.old_names)-1]
            summary.append([f'{old_name} -> {memb.name}'])
        summary.append(["\nLeft Clan:"])
        for memb in self.leaving:
            summary.append([memb.name])
        summary.append(["\nJoined Clan:"])
        for memb in self.joining:
            summary.append([memb.name])
        summary.append(["- - - - - - - - - - - - - - - - - - - - - - - - - - -"])

        return summary
    def summary(self):
        """
        Gives a text representation of memberlist changes
        """
        rows = self.summary_rows()
        summary = ''
        for line in rows:
            summary += (line[0] + '\n')
        return summary


# Update member skills and runescore from RS API
def _updateUserData(memb, session):
    if not isinstance(memb, Member): return False
    try:
        memb_req_res = session.get(_member_base_url+memb.name, timeout=10)
    except requests.exceptions.Timeout:
        return _updateUserData(memb, session)

    if (memb_req_res.status_code == requests.codes['ok']):
        #TODO process result into proper array rather than use splits?
        #TODO create function in member to update from api result
        memb_info = memb_req_res.text.splitlines()

        # name, rank, clan_xp, kills, already updated by clan data
        # first 28 are skills, 3 columns : rank, lvl, xp
        for num, x in enumerate(memb_info) :
            if num > 28 : break
            memb.skills[num] = int_0(x.split(',')[2])

        # runescore = 53, 2 columns : rank, score
        memb.runescore = int_0(memb_info[53].split(',')[1])
        # clues = next 5 after runescore
        memb.easy_clues = int_0(memb_info[54].split(',')[1])
        memb.medium_clues = int_0(memb_info[55].split(',')[1])
        memb.hard_clues = int_0(memb_info[56].split(',')[1])
        memb.elite_clues = int_0(memb_info[57].split(',')[1])
        memb.master_clues = int_0(memb_info[58].split(',')[1])
        memb.total_clues = (
            memb.easy_clues
            + memb.medium_clues
            + memb.hard_clues
            + memb.elite_clues
            + memb.master_clues
        )
        return True
    else:
        zerobot_common.logfile.log(f"Failed to get member data : {memb.name}")
        return False

# function to retrieve todays member list from RS API
def _getMemberlistUpdate(session, ingame_members_list):
    try:
        memb_list_api_result = session.get(_memberlist_base_url+zerobot_common.rs_api_clan_name, timeout=10)
    except requests.exceptions.Timeout:
        zerobot_common.logfile.log(f'Retrying clan memberlist retrieval...')
        time.sleep(30)
        return _getMemberlistUpdate(session, ingame_members_list)

    # got a response, need to check if good response
    if (memb_list_api_result.status_code == requests.codes['ok']):
        # split per line, remove first junk description line
        members_strings = memb_list_api_result.text.splitlines()
        members_strings.pop(0)

        # go through lines of member info
        for memb_str in members_strings:
            # replace jagex's non breaking spaces (char 160) with normal ones (char 32)
            memb_str = memb_str.replace(' ',' ')
            memb_info = memb_str.split(',')
            ingame_members_list.append(Member(memb_info[0], memb_info[1], int_0(memb_info[2]), int_0(memb_info[3])))
    else:
        # exit if failed to retrieve new data
        zerobot_common.logfile.log("Failed to retrieve clan member list.")
        exit()

def _startUpdateWarnings(current_members_sheet, old_members_sheet):
    update_warning = [[
            "AUTOMATIC","UPDATE IN","5 MINUTES","S T O P","EDITING!","! - ! - !","","",
            "","","S T O P","EDITING!","! - ! - !","","","S T O P",
            "EDITING!","! - ! - !","","","","","","","S T O P","EDITING!","! - ! - !","","","","","","S T O P","EDITING!","! - ! - !","","","","","","","","","S T O P","EDITING!","! - ! - !"]]
    current_members_sheet.batch_update([{'range' : 'A4:' + SheetParams.end_col + '4','values' : update_warning}], value_input_option = 'USER_ENTERED')
    old_members_sheet.batch_update([{'range' : 'A4:' + SheetParams.end_col + '4','values' : update_warning}], value_input_option = 'USER_ENTERED')
    time.sleep(60)
    current_members_sheet.update_cell(4,3,'4 MINUTES')
    old_members_sheet.update_cell(4,3,'4 MINUTES')
    time.sleep(60)
    current_members_sheet.update_cell(4,3,'3 MINUTES')
    old_members_sheet.update_cell(4,3,'3 MINUTES')
    time.sleep(60)
    current_members_sheet.update_cell(4,3,'2 MINUTES')
    old_members_sheet.update_cell(4,3,'2 MINUTES')
    time.sleep(60)
    current_members_sheet.update_cell(4,3,'1 MINUTE')
    old_members_sheet.update_cell(4,3,'1 MINUTE')
    time.sleep(60)

def _printUpdateInProgressWarnings(current_members_sheet, old_members_sheet):
    # empty the current members sheet
    current_members_sheet.clear()
    # clear old colors, list order will change, so need clear even if no color update
    white_fmt = CellFormat(backgroundColor=Color(1,1,1))
    format_cell_range(current_members_sheet,'B5:G510',white_fmt)
    # reset header rows and insert ongoing update warnings for current members sheet
    row1 = [
        "Current clan members and their stats are updated here automatically. Update sorts the list and takes care of joins/leaves/renames.",
        "","","","","","","","Hover here for background Color Explanation","",""]
    row2 = [
        "Blue titled rows = can update by hand. Other rows are auto-updated daily (= overwritten)",
        "","","","","","","","","",""]
    row3 = [
        "You should use the discord bot commands to add (re)joining members. You can try to do it by hand but you'll probably miss things or do unnecessary work",
        "","","","","","","","","","",""]
    warn1 = ['AUTOMATIC','UPDATE','IN PROGRESS']
    warn2 = ['STARTED:', datetime.utcnow().strftime("%H:%M:%S")]
    warn3 = ['Update takes about 30 minutes.']
    warn4 = ['Anything entered on this sheet will']
    warn5 = ['be overwritten after the update']
    current_members_sheet.batch_update([{'range' : 'A1:' + SheetParams.end_col + '9','values' : [row1, row2, row3, SheetParams.header_entries_currmembs,warn1,warn2,warn3,warn4,warn5]}], value_input_option = 'USER_ENTERED')

    # empty the old members sheet
    old_members_sheet.clear()
    # reset header rows and insert ongoing update warnings for old members sheet
    row1 = [
        "People who retired from clan are moved here, either by friendly leave or as inactive kick, meaning they can reapply to join.",
        "","","","","","","","","",""]
    row2 = [
        "People are no longer tracked after leaving clan, but their info is kept here. Name, ranks, notes, etc. will be from the day they left unless you update them by hand.",
        "","","","","","","","","",""]
    row3 = [
        "If you want to track someone's namechanges after they leave the clan you need to add them ingame (friend, ignore or clan banlist",
        "","","","","","","","","",""]
    old_members_sheet.batch_update([{'range' : 'A1:' + SheetParams.end_col + '9','values' : [row1, row2, row3, SheetParams.header_entries_oldmembs,warn1,warn2,warn3,warn4,warn5]}], value_input_option = 'USER_ENTERED')

def _compareMembers(session, current_members_list, ingame_members_list, joining_members, leaving_members, renamed_members):
    # loop through ingame members list, try to find in current members list
    for ingame_memb in ingame_members_list:
        on_hiscores = _updateUserData(ingame_memb, session)
        try:
            index = current_members_list.index(ingame_memb)
        except ValueError:
            # not found = new ingame member or someone renamed to this

            # check if new ingame member on hiscores
            if not(on_hiscores):
                # shouldnt really be possible for a new ingame member to not be on hiscores, log if it happens
                zerobot_common.logfile.log(f'\n-!-\n thing A you worried about happened\n-!-\n')
            
            ingame_memb.join_date = datetime.utcnow().strftime("%Y-%m-%d")
            ingame_memb.last_active = datetime.utcnow()
            joining_members.append(ingame_memb)
        else:
            ##-------------------------------------------------------------------------##
            ##------------ IMPORTANT UPDATE PART : MEMBER STAYED IN CLAN --------------##
            ##-------------------------------------------------------------------------##
            # found = existing member
            existing_member = current_members_list[index]

            # needs invite as rank = they were added to sheet, but still needed an invite.
            # means they just joined, add to joining members later so they show up daily update summary
            if (existing_member.rank == "needs invite"):
                just_joined = True
            else:
                just_joined = False

            # dropped from hiscores = keep old last active, and stats
            if not(on_hiscores):
                # but subtract 1 from their clan xp, to make them show up as active as soon as they do anything
                existing_member.clan_xp = (existing_member.clan_xp - 1)
                continue

            # check if member was active, if so update last active date, need to do before skills update
            # if last active not set in future, update with today
            if (existing_member.last_active == None or existing_member.last_active < datetime.utcnow()):
                if (existing_member.wasActive(ingame_memb)):
                    existing_member.last_active = datetime.utcnow()
            # update member in current list with new ingame data
            existing_member.rank = ingame_memb.rank
            existing_member.clan_xp = ingame_memb.clan_xp
            existing_member.kills = ingame_memb.kills
            existing_member.runescore = ingame_memb.runescore
            existing_member.skills = ingame_memb.skills
            existing_member.easy_clues = ingame_memb.easy_clues
            existing_member.medium_clues = ingame_memb.medium_clues
            existing_member.hard_clues = ingame_memb.hard_clues
            existing_member.elite_clues = ingame_memb.elite_clues
            existing_member.master_clues = ingame_memb.master_clues
            existing_member.total_clues = ingame_memb.total_clues
            
            if (just_joined):
                current_members_list.remove(existing_member)
                joining_members.append(existing_member)


    # loop through current members list, try to find in ingame members list
    for current_memb in current_members_list:
        try:
            index = ingame_members_list.index(current_memb)
        except ValueError:
            # not found = member left or renamed to one in joining
            leaving_members.append(current_memb)
        # found = still in clan, already updated with new stats.

    # lower than this is a decent chance of a match
    chance_threshold = 2

    for leave in leaving_members:
        #TODO: this check could be a bit more robust instead of on runescore alone, 
        if leave.runescore == 0:
            # check if player with same name in joining = stayed but didnt have data before / data was accidentally removed.
            for join in joining_members:
                if leave == join: 
                    #TODO: this part may be completely redundant, if name stayed the same they won't be put in leaving members?
                    ##-------------------------------------------------------------------------------------##
                    ##------ IMPORTANT UPDATE PART : MEMBER STAYED IN CLAN BUT HAD NO DATA BEFORE ---------##
                    ##-------------------------------------------------------------------------------------##
                    zerobot_common.logfile.log(f'\n-!-\n thing B you worried about happened\n-!-\n')
                    join.loadFromOldName(leave)
                    # Member was active, or skills would not have updated.
                    # if last active not set in future, update with today
                    if (join.last_active == None or join.last_active < datetime.utcnow()):
                        join.last_active = datetime.utcnow()
            # already know nobody stayed in clan with same name
            # no data to compare, leave member in to remove and continue with next.
            zerobot_common.logfile.log(f"Missing data for leaving member : {leave.name}. Can not check for renames")
            continue
        # calculate match chances
        best_match = 0
        best_chance = 1000
        non_matches = 0
        for join in joining_members:
            if join.runescore == 0:
                zerobot_common.logfile.log(f'Missing data for {join.name}. Can not check if this is new name of {leave.name}, skipping comparison')
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
            # if all joining are ruled out immediately by lower stats, skip straight to removal
            zerobot_common.logfile.log(f'{leave.name} left the clan, no possible match in joiners')
        else:
            zerobot_common.logfile.log(f'{leave.name} rename to {best_match.name} with {best_chance} chance?')
            if (best_chance < chance_threshold):
                zerobot_common.logfile.log(f'--likely, considering as renamed')
                # == Update old names ==
                # see if new name was used before
                try:
                    leave.old_names.index(best_match.name)
                except ValueError:
                    # not used before, add current to list of prev names
                    leave.old_names.append(leave.name)
                else:
                    # used before, remove from list of pre
                    leave.old_names.remove(best_match.name)
                    leave.old_names.append(leave.name)
                ##----------------------------------------------------------------------------##
                ##-------- IMPORTANT UPDATE PART : MEMBER STAYED IN CLAN BUT RENAMED ---------##
                ##----------------------------------------------------------------------------##
                best_match.loadFromOldName(leave)
                # Member was active, they renamed. if last active not set in future, update with today
                if (best_match.last_active == None or best_match.last_active < datetime.utcnow()):
                    best_match.last_active = datetime.utcnow()
                
                # Final step, mark as renamed
                renamed_members.append(best_match)
            else:
                zerobot_common.logfile.log(f'--unlikely, removing from clan')

def _updateLists(current_members_list, old_members_list, joining_members, leaving_members, renamed_members):
    # sort out renamed and members who still needed invites in leaving/joining/renamed lists.
    for memb in renamed_members:
        # renamed = should not be in joining or leaving
        joining_members.remove(memb)
        old_name = memb.old_names[len(memb.old_names)-1]
        leaving_members.remove(old_name)
    leaving = leaving_members.copy()
    for memb in leaving:
        # needs invite rank in leavers = still needs invite, not joined yet, should not be in leaving.
        if (memb.rank == "needs invite"):
            leaving_members.remove(memb)
            continue
    # joining members is already correct by now, no changes needed, also see compare members function on how
    # members who were already added to sheet (with 'needs invite' as rank) are handled.

    update_res = UpdateResult(joining_members, leaving_members, renamed_members)
    
    # could move this processing elsewhere now, update res is accurate
    for memb in update_res.renamed:
        old_name = memb.old_names[len(memb.old_names)-1]
        current_members_list.remove(old_name)
        current_members_list.append(memb)
    for memb in update_res.leaving:
        if (memb.leave_date == ""):
            memb.leave_date = datetime.utcnow().strftime("%Y-%m-%d")
        if (memb.leave_reason == ""):
            memb.leave_reason = "left or inactive kick"
        memb.site_rank = "Retired member"
        memb.discord_rank = ""
        current_members_list.remove(memb)
        old_members_list.append(memb)
    for memb in update_res.joining:
        current_members_list.append(memb)
    
    return update_res

def _printRecentChanges(recent_changes_sheet, update_res):
    summary = update_res.summary_rows()
    print(update_res.summary())
    for i in range(len(summary)-1,-1,-1):
        recent_changes_sheet.insert_row(summary[i],1,value_input_option = 'USER_ENTERED')

def _writeMemberlistCopyToDisk(memberlist, filename):
    '''
    Writes a copy of the memberlist to the specified file, overwriting it if it existed already.
    '''
    # ensure directory for file exists if not creating in current directory
    dirname = os.path.dirname(filename)
    if (dirname != ''):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    # write a copy with todays date to disk as backup
    memberlist_file = open(filename, "w", encoding="utf-8")
    for x in memberlist:
        memberlist_file.write(str(x) + '\n')
    memberlist_file.close()

def UpdateList():
    '''
    Goes through the entire memberlist.
    - Compares it with ingame clan memberlist, adds people who joined, removes people who left.
    - Updates every member's ingame stats, discord rank status and site rank status.
    - returns a changelog and stores a local copy of the updated list for backups / future comparison.

    The spreadsheets / memberlists are cleared during this process and overwritten afterwards, changes inbetween are lost.
    '''
    zerobot_common.logfile.log("Starting clantrack update")
    zerobot_common.drive_connect()

    # Safe to load these from common for easier reference, Very certain they won't be reassigned in either place.
    current_members_sheet = zerobot_common.current_members_sheet
    old_members_sheet = zerobot_common.old_members_sheet

    # 5 minute heads up for editors to stop working on the sheet before update
    _startUpdateWarnings(current_members_sheet, old_members_sheet)
    # retrieve must recent current and previous members from spreadsheet
    current_members_list = read_member_sheet(current_members_sheet)
    old_members_list = read_member_sheet(old_members_sheet)
    # Clear the spreadsheets and write down update in progress notification on them.
    _printUpdateInProgressWarnings(current_members_sheet, old_members_sheet)
    
    # start session to try to speed up rs api requests
    session = requests.session()
    # retrieve todays member list from RS API
    ingame_members_list = list()
    _getMemberlistUpdate(session, ingame_members_list)

    # create lists to compare members and compare current members with ingame members
    joining_members = list()
    leaving_members = list()
    renamed_members = list()
    _compareMembers(session, current_members_list, ingame_members_list, joining_members, leaving_members, renamed_members)
    # update the member lists with the results from comparing members
    update_res = _updateLists(current_members_list, old_members_list, joining_members, leaving_members, renamed_members)

    # previous actions can take a while, make sure google drive connection is active and write changes
    zerobot_common.drive_connect()
    # write the summary of changes to the recent changes sheet
    _printRecentChanges(zerobot_common.recent_changes_sheet, update_res)
    write_member_sheet(current_members_list, current_members_sheet)
    write_member_sheet(old_members_list, old_members_sheet)

    zerobot_common.logfile.log("Writing backup copy to disk...")
    # create local copies of the memberlists
    _writeMemberlistCopyToDisk(current_members_list, ("backup_memberlists/current_members/current_membs_" + datetime.utcnow().strftime("%Y-%m-%d")))
    _writeMemberlistCopyToDisk(old_members_list, ("backup_memberlists/old_members/old_membs_" + datetime.utcnow().strftime("%Y-%m-%d")))

    zerobot_common.logfile.log("clantrack update done")
    return update_res