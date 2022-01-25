import time
from datetime import datetime
import zerobot_common
import utilities
from zerobot_common import SheetParams, gem_exceptions
from member import Member, valid_profile_link , valid_discord_id, Warning
from memberlist import memberlist_sort_name, memberlist_get
from rankchecks import match_disc_ingame, match_disc_site
from gspread_formatting import format_cell_range, format_cell_ranges, CellFormat, Color

def memberlist_to_sheet(memberlist, sheet):
    """
    Writes specified memberlist to specified google docs sheet.
    Clears the sheet and sorts the memberlist before writing.
    """
    zerobot_common.drive_connect()
    # clear the spreadsheet
    clear_sheet(sheet, clear_bg_colors=True)

    # sort the memberlist to ensure alphabetical order
    memberlist_sort_name(memberlist)
    # transform member objects into list of rows for googledocs
    memb_list_rows = list()
    for memb in memberlist:
        memb_list_rows.append(memb.to_sheet())

    # enter memberlist data on sheet, skipping header rows
    sheet.batch_update([{
        "range" : SheetParams.range_no_header(list_length=len(memb_list_rows)),
        "values" : memb_list_rows
        }], value_input_option = "USER_ENTERED")
def memberlist_from_sheet(sheet):
    """
    Reads a memberlist from the specified google docs sheet.
    """
    zerobot_common.drive_connect()
    memberlist = list()
    member_matrix = sheet.get_all_values()
    # skip header rows
    for i in range(SheetParams.header_rows, len(member_matrix)):
        memberlist.append(Member.from_sheet(member_matrix[i]))
    return memberlist

def clear_sheet(sheet, clear_bg_colors=False):
    """
    Empties a memberlist sheet, restores header row entries afterwards.
    Optionally clears formatting as well, excluding header rows.
    """
    zerobot_common.drive_connect()
    # empty the sheet
    sheet.clear()
    # restore the header entries
    sheet.batch_update([{
        "range" : SheetParams.header_range,
        "values" : [SheetParams.header_entries]
        }], value_input_option = "USER_ENTERED")
    if clear_bg_colors:
        # clear background colors for non-header
        white_fmt = CellFormat(backgroundColor=Color(1,1,1))
        format_cell_range(sheet,SheetParams.range_no_header(sheet=sheet), white_fmt)
def clear_sheets():
    """
    Empties all 3 memberlist sheets, including formatting, except for header rows.
    """
    clear_sheet(zerobot_common.current_members_sheet, clear_bg_colors=True)
    clear_sheet(zerobot_common.old_members_sheet, clear_bg_colors=True)
    clear_sheet(zerobot_common.banned_members_sheet, clear_bg_colors=True)

def UpdateMember(sheet, row, member):
    """
    Replaces the member details in specified row with details from specified member object
    """
    zerobot_common.drive_connect()
    sheet.update(f"{SheetParams.start_col}{row}:{SheetParams.end_col}{row}", [member.to_sheet()], value_input_option = "USER_ENTERED")

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
    sheet.insert_row(member.to_sheet(), row, value_input_option = "USER_ENTERED")

def load_sheet_changes(memberlist, sheet):
    """
    Loads changes from sheet to memberlist. Only updates matching names.
    Members on the sheet for which no existing name can be found are added.
    Removing members can not be done through the sheet.
    """
    sheet_list = memberlist_from_sheet(sheet)
    for x in sheet_list:
        # for existing members there should be an entry with matching id
        member = memberlist_get(memberlist, x.entry_id, type="entry_id")
        if member is None:
            # no existing match found, add to memberlist
            memberlist.append(x)
        else:
            # match found, load sheet data
            member.load_sheet_changes(x)

async def warnings_from_sheet(self):
    """
    Checks the warnings on the sheet and adds them to the correct member.
    """
    today = datetime.utcnow()
    zerobot_common.drive_connect()
    warnings_matrix = zerobot_common.warnings_sheet.get_all_values()
    for i in range(1,len(warnings_matrix)):
        warning = Warning.from_sheet_format(warnings_matrix[i])
        # try to find member by discord id
        memb = memberlist_get(self.current_members, warning.discord_id)
        if memb is None:
            memb = memberlist_get(self.old_members, warning.discord_id)
        if memb is None:
            memb = memberlist_get(self.banned_members, warning.discord_id)
        # try to find member by name if still not found
        if memb is None:
            memb = memberlist_get(self.current_members, warning.name)
        if memb is None:
            memb = memberlist_get(self.old_members, warning.name)
        if memb is None:
            memb = memberlist_get(self.banned_members, warning.name)
        # If still None at this point -> warn missed
        if memb is None:
            await zerobot_common.bot_channel.send(
                f"Unable to find player for warning: {warning.to_str()}"
            )
            continue
        # store warning in member
        memb.warnings.append(warning)
    # update total warning points
    for memb in self.current_members:
        points = 0
        for warning in memb.warnings:
            if warning.expiry_date is None:
                points += warning.points
                continue
            if today <= warning.expiry_date:
                points += warning.points
        memb.warning_points = points

def color_spreadsheet():
    """
    Checks for mismatches from rank and gem columns and updates the background colors accordingly.
    Does not make other changes to spreadsheet, updates colors only.
    """
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

    # ingame rank = Col B, Discord Rank = Col C, Site Rank = Col D, Passed Gem = Col F
    row = SheetParams.header_rows + 1
    for x in memberlist:
        discord_rank_index = utilities.rank_index(discord_role_name=x.discord_rank)
        # colour gem column
        if not(x.passed_gem) and discord_rank_index is not None:
            if discord_rank_index < zerobot_common.join_rank_index:
                # push to do gems : no gem, current rank higher than novice
                passed_gem_ranges.append((f"F{row}", orange_fmt))
        # colour discord rank if missing or not auto updating
        if discord_rank_index is None:
            # no discord rank = red for missing
            discord_rank_ranges.append((f"C{row}", red_fmt))
        elif not valid_discord_id(x.discord_id):
            # discord rank fine but not autoupdating = grey
            discord_rank_ranges.append((f"C{row}", gray_fmt))
        else:
            if not (x.passed_gem or (x.discord_rank in gem_exceptions or x.name in gem_exceptions)):
                if discord_rank_index < zerobot_common.join_rank_index:
                    # discord rank higher than recruit and no gem
                    discord_rank_ranges.append((f"C{row}", orange_fmt))
            # check ingame rank for mismatch with discord
            if not x.rank in match_disc_ingame[x.discord_rank] : ingame_rank_ranges.append((f"B{row}", orange_fmt))
            # if no site link, color gray = not autoupdating
            if not valid_profile_link(x.profile_link):
                site_rank_ranges.append((f"D{row}", gray_fmt))
            else:
                # check site rank for mismatch with discord
                if not x.site_rank in match_disc_site[x.discord_rank] : site_rank_ranges.append((f"D{row}", orange_fmt))
        row += 1

    # clear all previous formatting
    format_cell_range(zerobot_common.current_members_sheet,"B5:G510", white_fmt)
    # sheets api errors with empty list of changes, only try if a change is needed.
    if (len(ingame_rank_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,ingame_rank_ranges)
    if (len(discord_rank_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,discord_rank_ranges)
    if (len(site_rank_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,site_rank_ranges)
    if (len(passed_gem_ranges) > 0):
        format_cell_ranges(zerobot_common.current_members_sheet,passed_gem_ranges)