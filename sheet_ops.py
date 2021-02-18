import time
from datetime import datetime
import zerobot_common
import utilities
from zerobot_common import SheetParams, discord_ranks
from member import Member, valid_profile_link , valid_discord_id
from memberlist import memberlist_sort_name, memberlist_get
from gspread_formatting import format_cell_range, format_cell_ranges, CellFormat, Color
from rankchecks import ingame_ranks, site_ranks, gem_exceptions

##TODO modify tosheet
def memberlist_to_sheet(memberlist, sheet):
    '''
    Writes specified memberlist to specified google docs sheet.
    Clears the sheet and sorts the memberlist before writing.
    '''
    zerobot_common.drive_connect()
    # clear the spreadsheet
    clear_sheet(sheet)

    # re-sort the memberlist in alphabetical order
    memberlist_sort_name(memberlist)
    # transform member objects back into lists of rows for googledocs
    memb_list_rows = list()
    for memb in memberlist:
        memb_list_rows.append(memb.to_sheet())

    sheet.batch_update([{
        'range' : SheetParams.range_no_header(),
        'values' : memb_list_rows
        }], value_input_option = 'USER_ENTERED')
def memberlist_from_sheet(sheet):
    '''
    Reads a memberlist from the specified google docs sheet.
    '''
    zerobot_common.drive_connect()
    memberlist = list()
    member_matrix = sheet.get_all_values()
    # skip header rows
    for i in range(SheetParams.header_rows, len(member_matrix)):
        memberlist.append(Member.from_sheet(member_matrix[i]))
    return memberlist

def clear_sheet(sheet):
    zerobot_common.drive_connect()
    # empty the sheet
    sheet.clear()
    # restore the header entries
    sheet.batch_update([{
        'range' : SheetParams.header_range,
        'values' : [SheetParams.header_entries]
        }], value_input_option = 'USER_ENTERED')
    # clear background colors for non-header
    white_fmt = CellFormat(backgroundColor=Color(1,1,1))
    format_cell_range(sheet,SheetParams.range_no_header(), white_fmt)
def clear_sheets():
    clear_sheet(zerobot_common.current_members_sheet)
    clear_sheet(zerobot_common.old_members_sheet)
    clear_sheet(zerobot_common.banned_members_sheet)
def start_update_warnings():
    zerobot_common.drive_connect()
    zerobot_common.current_members_sheet.batch_update(
        [{'range' : SheetParams.header_range,
        'values' : [SheetParams.update_header]}],
        value_input_option = 'USER_ENTERED')
    zerobot_common.old_members_sheet.batch_update(
        [{'range' : SheetParams.header_range,
        'values' : [SheetParams.update_header]}],
        value_input_option = 'USER_ENTERED')
    zerobot_common.banned_members_sheet.batch_update(
        [{'range' : SheetParams.header_range,
        'values' : [SheetParams.update_header]}],
        value_input_option = 'USER_ENTERED')
    time.sleep(60)
    zerobot_common.current_members_sheet.update_cell(SheetParams.header_rows,3,'4 MINUTES')
    zerobot_common.old_members_sheet.update_cell(SheetParams.header_rows,3,'4 MINUTES')
    zerobot_common.old_members_sheet.update_cell(SheetParams.header_rows,3,'4 MINUTES')
    time.sleep(60)
    zerobot_common.current_members_sheet.update_cell(SheetParams.header_rows,3,'3 MINUTES')
    zerobot_common.old_members_sheet.update_cell(SheetParams.header_rows,3,'3 MINUTES')
    zerobot_common.banned_members_sheet.update_cell(SheetParams.header_rows,3,'3 MINUTES')
    time.sleep(60)
    zerobot_common.current_members_sheet.update_cell(SheetParams.header_rows,3,'2 MINUTES')
    zerobot_common.old_members_sheet.update_cell(SheetParams.header_rows,3,'2 MINUTES')
    zerobot_common.banned_members_sheet.update_cell(SheetParams.header_rows,3,'2 MINUTES')
    time.sleep(60)
    zerobot_common.current_members_sheet.update_cell(SheetParams.header_rows,3,'1 MINUTE')
    zerobot_common.old_members_sheet.update_cell(SheetParams.header_rows,3,'1 MINUTE')
    zerobot_common.banned_members_sheet.update_cell(SheetParams.header_rows,3,'1 MINUTES')
    time.sleep(60)
def print_update_in_progress_warnings():
    print_update_in_progress_warning(zerobot_common.current_members_sheet)
    print_update_in_progress_warning(zerobot_common.old_members_sheet)
    print_update_in_progress_warning(zerobot_common.banned_members_sheet)
def print_update_in_progress_warning(sheet):
    zerobot_common.drive_connect()
    # insert ongoing update warnings
    warn1 = ['AUTOMATIC','UPDATE','IN PROGRESS']
    warn2 = ['STARTED:', datetime.utcnow().strftime(utilities.timeformat)]
    warn3 = ['Update takes about 30 minutes.']
    warn4 = ['Anything entered on this sheet will']
    warn5 = ['be overwritten after the update']
    warn_list = [warn1, warn2, warn3, warn4, warn5]

    sheet.batch_update(
        [{'range' : SheetParams.range_no_header(),
        'values' : warn_list}],
        value_input_option = 'USER_ENTERED'
    )

def UpdateMember(sheet, row, member):
    """
    Replaces the member details in specified row with details from specified member object
    """
    zerobot_common.drive_connect()
    sheet.update(f'{SheetParams.start_col}{row}:{SheetParams.end_col}{row}', [member.to_sheet()], value_input_option = 'USER_ENTERED')

def DeleteMember(sheet, row):
    """
    Deletes the row from the sheet.
    """
    zerobot_common.drive_connect()
    sheet.delete_row(row)

def InsertMember(sheet, row, member):
    """
    Inserts a member on the sheet.
    """
    zerobot_common.drive_connect()
    sheet.insert_row(member.to_sheet(), row, value_input_option = 'USER_ENTERED')

def load_sheet_changes(memberlist, sheet):
    """
    Loads changes from sheet to memberlist. Only updates matching names.
    Members on the sheet for which no existing name can be found are added.
    Removing members can not be done through the sheet.
    """
    sheet_list = memberlist_from_sheet(sheet)
    for x in sheet_list:
        # try name matching
        member = memberlist_get(memberlist, x.name)
        # try profile link matching if no result yet
        if member is None and valid_profile_link(x.profile_link):
            member = memberlist_get(memberlist, x.profile_link)
        # try discord id matching if no result yet
        if member is None and valid_discord_id(x.discord_id):
            member = memberlist_get(memberlist, x.discord_id)
        # if no existing match found at all, add to memberlist
        if member is None:
            memberlist.append(x)
            continue
        member.load_sheet_changes(x)

def color_spreadsheet():
    '''
    Checks for mismatches from rank and gem columns and updates the background colors accordingly.
    Does not make other changes to spreadsheet, updates colors only.
    '''
    zerobot_common.drive_connect()
    # load the memberlist from google docs
    memberlist = memberlist_from_sheet(zerobot_common.current_members_sheet)

    #### Add colors for missing gems and required rank changes ####
    white_fmt = CellFormat(backgroundColor=Color(1,1,1))
    gray_fmt = CellFormat(backgroundColor=Color(0.8,0.8,0.8))
    orange_fmt = CellFormat(backgroundColor=Color(1, 0.5, 0))
    red_fmt = CellFormat(backgroundColor=Color(1, 0.2, 0))
    green_fmt = CellFormat(backgroundColor=Color(0.25, 0.75, 0.25))

    ingame_rank_ranges = list()
    discord_rank_ranges = list()
    site_rank_ranges = list()
    passed_gem_ranges = list()

    # ingame rank = Col B, clan Rank = Col C, Discord Rank = Col D, Passed Gem = Col F
    row = SheetParams.header_rows + 1
    # check passed gem and rank after gem columns
    for x in memberlist:
        # orange gem column, for push to do gem : no gem, current rank higher than novice
        if not(x.passed_gem) and (
            discord_ranks.get(x.discord_rank, 0) > discord_ranks['Recruit']
            ):
            passed_gem_ranges.append((f'F{row}', orange_fmt))
        row += 1
    row = SheetParams.header_rows + 1
    for x in memberlist:
        # discord rank color
        if (x.passed_gem or (x.discord_rank in gem_exceptions or x.name in gem_exceptions)):
            # check ingame rank for mismatch
            if discord_ranks.get(x.discord_rank, 0) > ingame_ranks.get(x.rank, 0): ingame_rank_ranges.append((f'B{row}', green_fmt))
            if discord_ranks.get(x.discord_rank, 0) < ingame_ranks.get(x.rank, 0): ingame_rank_ranges.append((f'B{row}', orange_fmt))
            # check site rank for mismatch
            if not valid_profile_link(x.profile_link):
                site_rank_ranges.append((f'D{row}', gray_fmt))
            else:
                if discord_ranks.get(x.discord_rank, 0) > site_ranks.get(x.site_rank, 0): site_rank_ranges.append((f'D{row}', green_fmt))
                if discord_ranks.get(x.discord_rank, 0) < site_ranks.get(x.site_rank, 0): site_rank_ranges.append((f'D{row}', orange_fmt))
            # colour discord rank if missing or not auto updating
            if discord_ranks.get(x.discord_rank, 0) == 0:
                # no discord rank = red for missing
                discord_rank_ranges.append((f'C{row}', red_fmt))
            elif not valid_discord_id(x.discord_id):
                # discord rank fine but not autoupdating = grey
                discord_rank_ranges.append((f'C{row}', gray_fmt))
        else:   
            # ingame rank above novice = should get derank
            if ingame_ranks.get(x.rank, 0) > ingame_ranks['Recruit']: ingame_rank_ranges.append((f'B{row}', orange_fmt))
            if not valid_profile_link(x.profile_link):
                site_rank_ranges.append((f'D{row}', gray_fmt))
            else:
                # above novice = should get derank
                if site_ranks.get(x.site_rank, 0) > site_ranks['Recruit']: site_rank_ranges.append((f'D{row}', orange_fmt))
                # below novice = should get rankup
                if site_ranks.get(x.site_rank, 0) < site_ranks['Recruit']: site_rank_ranges.append((f'D{row}', green_fmt))
            # discord rank
            if discord_ranks.get(x.discord_rank, 0) == 0:
                # no discord rank = red for missing
                discord_rank_ranges.append((f'C{row}', red_fmt))
            elif discord_ranks.get(x.discord_rank, 0) > discord_ranks.get('Recruit'):
                # discord rank but too high
                discord_rank_ranges.append((f'C{row}', orange_fmt))
            elif not valid_discord_id(x.discord_id):
                # discord rank fine but not autoupdating = grey
                discord_rank_ranges.append((f'C{row}', gray_fmt))
        row += 1

    # clear all previous formatting
    format_cell_range(zerobot_common.current_members_sheet,'B5:G510', white_fmt)
    # sheets api errors with empty list of changes, only try if a change is needed.
    if (len(ingame_rank_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,ingame_rank_ranges)
    if (len(discord_rank_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,discord_rank_ranges)
    if (len(site_rank_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,site_rank_ranges)
    if (len(passed_gem_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,passed_gem_ranges)