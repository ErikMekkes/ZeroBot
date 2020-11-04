from member import read_member, memblist_sort

class SheetParams:
    start_col = 'A'
    end_col = 'BH'

    # number of header rows on the memberlist spreadsheets
    header_rows = 4
    # header entries for the current members spreadsheet
    header_entries_currmembs = [
            "Name","Ingame Rank","Discord Rank","Site Rank","Join Date","Passed Gem","Rank After Gem","Site Profile","Leave Date",
            "Leave Reason","Referral","Discord ID","Discord Name","Old Names","Last Active","Event Points","Note1","Note2","Note3","Clan XP","Kills","Runescore",
            "Total XP","Attack XP","Defence XP","Strength XP","Constitution XP","Ranged XP","Prayer XP","Magic XP","Cooking XP","Woodcutting XP","Fletching XP","Fishing XP","Firemaking XP","Crafting XP","Smithing XP","Mining XP","Herblore XP","Agility XP","Thieving XP","Slayer XP","Farming XP","Runecrafting XP","Hunter XP","Construction XP","Summoning XP","Dungeoneering XP","Divination XP","Invention XP","Archaeology XP","Highest Mage","Highest Melee","Highest Range","Total Clues","Easy Clues","Medium Clues","Hard Clues","Elite Clues","Master Clues"]
    # header entries for the old members spreadsheet
    header_entries_oldmembs = [
            "Name","Old Ingame Rank","Old Discord Rank","Site Rank","Join Date","Passed Gem","Rank After Gem","Site Profile","Leave Date",
            "Leave Reason","Referral","Discord ID","Discord Name","Old Names","Last Active","Event Points","Note1","Note2","Note3","Clan XP","Kills","Runescore",
            "Total XP","Attack XP","Defence XP","Strength XP","Constitution XP","Ranged XP","Prayer XP","Magic XP","Cooking XP","Woodcutting XP","Fletching XP","Fishing XP","Firemaking XP","Crafting XP","Smithing XP","Mining XP","Herblore XP","Agility XP","Thieving XP","Slayer XP","Farming XP","Runecrafting XP","Hunter XP","Construction XP","Summoning XP","Dungeoneering XP","Divination XP","Invention XP","Archaeology XP","Highest Mage","Highest Melee","Highest Range","Total Clues","Easy Clues","Medium Clues","Hard Clues","Elite Clues","Master Clues"]

def UpdateMember(sheet, row, member):
    """
    Replaces the member details in specified row with details from specified member object
    """
    sheet.update(f'{SheetParams.start_col}{row}:{SheetParams.end_col}{row}', [member.asList()])

def DeleteMember(sheet, row):
    """
    Deletes the row from the sheet.
    """
    sheet.delete_row(row)
def InsertMember(sheet, row, member):
    sheet.insert_row(member.asList(), row, value_input_option = 'USER_ENTERED')

def read_member_sheet(_sheet):
    '''
    Reads a memberlist from the specified google docs sheet.
    '''
    _memberlist = list()
    # retrieve memberlist from google docs
    member_matrix = _sheet.get_all_values()
    # skip header rows
    for i in range(SheetParams.header_rows, len(member_matrix)):
        _memberlist.append(read_member(member_matrix[i]))
    return _memberlist

def write_member_sheet(_memberlist, _sheet):
    '''
    Writes specified memberlist to specified google docs sheet.
    '''
    ##### Update the current members sheet #####
    # re-sort the memberlist in alphabetical order
    memblist_sort(_memberlist)
    # transform member objects back into lists of rows for googledocs
    memb_list_rows = list()
    for x in _memberlist:
        memb_list_rows.append(x.asList())

    # +11 at the end is just extra room for error?
    range_str = f"{SheetParams.start_col}{SheetParams.header_rows+1}:{SheetParams.end_col}{SheetParams.header_rows+len(memb_list_rows)+11}"

    _sheet.batch_update([{
        'range' : range_str,
        'values' : memb_list_rows
        }], value_input_option = 'USER_ENTERED')