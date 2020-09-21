import zerobot_common
from sheet_ops import read_member_sheet, write_member_sheet, SheetParams
from member import validDiscordId, validSiteProfile
# imports for google sheet access
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import format_cell_range, format_cell_ranges, CellFormat, Color
from logfile import LogFile
from datetime import datetime
# discord bot api
import discord
import traceback

gem_exceptions = ["Erwin","Alexanderke","Veteran Member","PvM Specialists"]

# used to find a member's highest dps tag
dps_tags = {
    '170k Mage DPM' : 1,
    '170k Range DPM' : 1,
    '170k Melee DPM' : 1,
    '180k Mage DPM' : 2,
    '180k Range DPM' : 2,
    '180k Melee DPM' : 2,
    '200k Mage DPM' : 3,
    '200k Range DPM' : 3,
    '200k Melee DPM' : 3,
    'Extreme Mage' : 4,
    'Extreme Range' : 4,
    'Extreme Melee' : 4,
    'Extreme DPS' : 5
}

# the rank tables below are used to find a users highest rank
# they are also used to check if ranks match, a matching rank has an equal value.
# example: Staff Member on discord, Coordinator ingame, Clan-Coordinator on the site are matching ranks.
discord_ranks = {
    'Leaders' : 10,
    'Staff Member' : 9,
    'MasterClass PvMer' : 8,
    'Supreme PvMer' : 7,
    'PvM Specialists' : 6,
    'Veteran Member' : 5,
    'Advanced Member' : 4,
    'Full Member' : 3,
    'Recruit' : 2,
    'Clan Friends/Allies' : 1,
    'Guest' : 1,
    'Waiting Approval' : 0
}
ingame_ranks = {
    'Owner' : 10,
    'Deputy Owner' : 10,
    'Overseer' : 10,
    'Coordinator' : 9,
    'Organiser' : 9,
    'Admin' : 8,
    'General' : 7,
    'Captain' : 6,
    'Lieutenant' : 5,
    'Sergeant' : 4,
    'Corporal' : 3,
    'Recruit' : 2
}
site_ranks = {
    'Leader' : 10,
    'Co-Leader' : 10,
    'Clan-Coordinator' : 9,
    'Clan Issues' : 9,
    'Citadel Co' : 9,
    'Media Co' : 9,
    'Staff Member' : 9,
    'MasterClass PvMer' : 8,
    'Supreme PvMer' : 7,
    'PvM Specialists' : 6,
    'Veteran Member' : 5,
    'Advanced Member' : 4,
    'Full Member' : 3,
    'Recruit' : 2,
    'Registered Guest' : 1,
    'Retired member' : 1,
    'Kicked Member' : 0
}

# This table is used to convert user typed ranks to intended discord rank
# when someone types `-zbot setrank specialist` for example
parse_discord_rank = {
    # correct name -> discord rank
    'owner' : 'Leaders',
    'deputy leader' : 'Leaders',
    'co-leader' : 'Leaders',
    'clan-coordinator' : 'Clan-Coordinator',
    'clan issues' : 'Clan Issues',
    'citadel co' : 'Citadel Co',
    'media co' : 'Media Co',
    'staff member' : 'Staff Member',
    'masterclass pvmer' : 'MasterClass PvMer',
    'supreme pvmer' : 'Supreme PvMer',
    'pvm specialist' : 'PvM Specialists',
    'elite member' : 'Elite Member',
    'veteran member' : 'Veteran Member',
    'advanced member' : 'Advanced Member',
    'full member' : 'Full Member',
    'novice' : 'Recruit',
    'registered guest' : 'Registered Guest',
    'retired member' : 'Retired member',
    'kicked member' : 'Kicked Member',
    # name variations -> discord rank
    'novice member' : 'Recruit',
    'recruit' : 'Recruit',
    'advanced' : 'Advanced Member',
    'veteran' : 'Veteran Member',
    'elite' : 'Elite Member',
    'specialist' : 'PvM Specialists',
    'pvm specialists' : 'PvM Specialists',
    'guest' : 'Guest',
    'retired' : 'Retired member',
    'kicked' : 'Kicked Member',
    'full' : 'Full Member',
    'leader' : 'Leaders',
    'staff_member' : 'Staff Member',
    'masterclass_pvmer' : 'MasterClass PvMer',
    'supreme_pvmer' : 'Supreme PvMer',
    'pvm_specialist' : 'PvM Specialists',
    'veteran_member' : 'Veteran Member',
    'advanced_member' : 'Advanced Member',
    'full_member' : 'Full Member',
    'waiting_approval' : 'Waiting Approval'
}


def update_discord_info(_memberlist):
    '''
    Checks discord roles and dpm tags for each member in the memberlist and updates them to the highest rank.
    '''
    # loop through memberlist
    for memb in _memberlist :
        # skip if discord id unknown
        if memb.discord_id == 0: continue
        usr = zerobot_common.guild.get_member(memb.discord_id)
        # skip if usr not found, keep old rank & discord id, set name as left discord to indicate
        # 'Not in clan discord' = exception for old people who never joined / people who cant join
        if (usr == None):
            memb.discord_name = 'Left clan discord'
            continue

        # update discord name
        memb.discord_name = usr.name

        # update passed gem
        memb.passed_gem = False
        for r in usr.roles:
            if r.name in dps_tags :
                memb.passed_gem = True
                break

        # update highest gems
        for r in usr.roles:
            if "Extreme DPS" == r.name:
                memb.highest_mage = "Extreme DPS"
                memb.highest_melee = "Extreme DPS"
                memb.highest_range = "Extreme DPS"
                break
            else :
                if "Mage" in r.name:
                    if dps_tags.get(r.name, 0) > dps_tags.get(memb.highest_mage, 0):
                        memb.highest_mage = r.name
                if "Melee" in r.name:
                    if dps_tags.get(r.name, 0) > dps_tags.get(memb.highest_melee, 0):
                        memb.highest_melee = r.name
                if "Range" in r.name:
                    if dps_tags.get(r.name, 0) > dps_tags.get(memb.highest_range, 0):
                        memb.highest_range = r.name

        # update discord rank
        rank = 0
        for r in usr.roles:
            rank_numb = discord_ranks.get(r.name,-1)
            if  rank_numb >= rank:
                rank = rank_numb
                memb.discord_rank = r.name

def update_sheet_discord_info():
    '''
    Checks discord roles and dpm tags for each member on the memberlist spreadsheet and updates them to the highest rank.
    '''
    # load the memberlist from google docs, load updated discord roles per member
    zerobot_common.drive_connect()
    memberlist = read_member_sheet(zerobot_common.current_members_sheet)
    update_discord_info(memberlist)

    # update new discord roles of members on the google doc, update colors on google doc
    write_member_sheet(memberlist, zerobot_common.current_members_sheet)

def _updateColors():
    '''
    Checks for mismatches from rank and gem columns and updates the background colors accordingly.
    Does not make other changes to spreadsheet, updates colors only.
    '''
    # load the memberlist from google docs, load updated discord roles per member
    zerobot_common.drive_connect()
    memberlist = read_member_sheet(zerobot_common.current_members_sheet)

    zerobot_common.logfile.log(f"Updating Colors on Spreadsheet")
    _sheet = zerobot_common.current_members_sheet
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
    rank_after_gem_ranges = list()

    # ingame rank = Col B, clan Rank = Col C, Discord Rank = Col D, Passed Gem = Col F
    row = SheetParams.header_rows + 1
    for x in memberlist:
        # orange gem column, for push to do gem : no gem, current rank or rank after gem higher than novice
        if not(x.passed_gem) and (
            discord_ranks.get(x.discord_rank, 0) > discord_ranks['Recruit'] or
            discord_ranks.get(x.rank_after_gem, 0) > discord_ranks.get('Recruit')
            ):
            passed_gem_ranges.append((f'F{row}', orange_fmt))
        # green gem column / rank after gem column, for rankup : passed gem, rank after gem higher than current rank
        if x.passed_gem and (discord_ranks.get(x.rank_after_gem, 0) > discord_ranks.get(x.discord_rank, 0)):
            passed_gem_ranges.append((f'F{row}', green_fmt))
            rank_after_gem_ranges.append((f'G{row}', green_fmt))
        # discord rank color
        if (x.passed_gem or (x.discord_rank in gem_exceptions or x.name in gem_exceptions)):
            # check ingame rank for mismatch
            if discord_ranks.get(x.discord_rank, 0) > ingame_ranks.get(x.rank, 0): ingame_rank_ranges.append((f'B{row}', green_fmt))
            if discord_ranks.get(x.discord_rank, 0) < ingame_ranks.get(x.rank, 0): ingame_rank_ranges.append((f'B{row}', orange_fmt))
            # check site rank for mismatch
            if not(validSiteProfile(x.profile_link)):
                site_rank_ranges.append((f'D{row}', gray_fmt))
            else:
                if discord_ranks.get(x.discord_rank, 0) > site_ranks.get(x.site_rank, 0): site_rank_ranges.append((f'D{row}', green_fmt))
                if discord_ranks.get(x.discord_rank, 0) < site_ranks.get(x.site_rank, 0): site_rank_ranges.append((f'D{row}', orange_fmt))
            # colour discord rank if missing or not auto updating
            if discord_ranks.get(x.discord_rank, 0) == 0:
                # no discord rank = red for missing
                discord_rank_ranges.append((f'C{row}', red_fmt))
            elif x.discord_id == 0:
                # discord rank fine but not autoupdating = grey
                discord_rank_ranges.append((f'C{row}', gray_fmt))
        else:   
            # ingame rank above novice = should get derank
            if ingame_ranks.get(x.rank, 0) > ingame_ranks['Recruit']: ingame_rank_ranges.append((f'B{row}', orange_fmt))
            if not(validSiteProfile(x.profile_link)):
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
            elif x.discord_id == 0:
                # discord rank fine but not autoupdating = grey
                discord_rank_ranges.append((f'C{row}', gray_fmt))
        row += 1

    format_cell_range(_sheet,'B5:G510', white_fmt)
    # sheets api errors with empty list of changes, only try if a change is needed.
    if (len(ingame_rank_ranges) > 0):
        format_cell_ranges(_sheet,ingame_rank_ranges)
    if (len(discord_rank_ranges) > 0):
        format_cell_ranges(_sheet,discord_rank_ranges)
    if (len(site_rank_ranges) > 0):
        format_cell_ranges(_sheet,site_rank_ranges)
    if (len(passed_gem_ranges) > 0):
        format_cell_ranges(_sheet,passed_gem_ranges)
    if (len(rank_after_gem_ranges) > 0):
        format_cell_ranges(_sheet,rank_after_gem_ranges)
    zerobot_common.logfile.log(f"Finished updating colors on Spreadsheet")

def TodosJoinDiscord(memberlist):
    response = list()
    for memb in memberlist:
        # no discord id, and never manually entered name
        if (memb.discord_id == 0 and memb.discord_name == ""):
            response.append(f"{memb.name}\n")
    response = [f"**Need to join discord or need a discord id update on sheet:** {len(response)}\n"] + response
    return response
def TodosUpdateRanks(memberlist):
    _need_rank_update = list()
    for memb in memberlist:
        site_rank_name = memb.site_rank
        site_rank = site_ranks.get(site_rank_name, None)
        discord_rank_name = memb.discord_rank
        discord_rank = discord_ranks.get(discord_rank_name, 0)
        ingame_rank_name = memb.rank
        ingame_rank = ingame_ranks.get(ingame_rank_name, 0)
        passed_gem = memb.passed_gem
        rank_after_gem_name = memb.rank_after_gem
        rank_after_gem = discord_ranks.get(rank_after_gem_name, 0)
        discord_recruit_rank = discord_ranks['Recruit']
        # passed gem, and listed to get rankup with gem = need rank update
        if passed_gem and (rank_after_gem > discord_rank):
            _need_rank_update.append(memb)
            continue
        # no gem, rank higher than recruit, rank or name not in gem exceptions.
        if not passed_gem and discord_rank > discord_recruit_rank:
            if not(discord_rank_name in gem_exceptions or memb.name in gem_exceptions):
                _need_rank_update.append(memb)
                continue
        # has a site rank and it's different from discord rank
        if site_rank is not None:
            if site_rank is not discord_rank:
                _need_rank_update.append(memb)
                continue
        # different ingame and discord rank
        if ingame_rank is not discord_rank:
            _need_rank_update.append(memb)
            continue
    # build up response
    response = list()
    for memb in _need_rank_update:
        response.append(memb.rankInfo())
    response = [f"**Need a rank update:** {len(response)}\n"] + response
    return response
def TodosInviteIngame(memberlist):
    response = list()
    for memb in memberlist:
        # no discord id, and never manually entered name
        if (memb.rank == "needs invite"):
            response.append(f"{memb.name}\n")
    response = [f"**Need to be invited ingame:** {len(response)}\n"] + response
    return response

def Todos(*args):
    zerobot_common.drive_connect()
    _memberlist = read_member_sheet(zerobot_common.current_members_sheet)
    update_discord_info(_memberlist)
    zerobot_common.siteops.updateSiteRanks(_memberlist)
    _no_discord = list()
    _no_site = list()
    _no_gem = list()
    for memb in _memberlist:
        # no valid site profile
        if not(validSiteProfile(memb.profile_link)):
            _no_site.append(memb)
        # no valid discord id, or no longer on discord
        if not(validDiscordId(memb.discord_id)) or memb.discord_name == "Left discord":
            _no_discord.append(memb)
        # not passed gem, and listed to get rankup with gem = need gem
        if not(memb.passed_gem) and (discord_ranks.get(memb.rank_after_gem, 0) > discord_ranks.get('Recruit')):
            _no_gem.append(memb)
    response = list()
    if (len(args) != 1):
        response.append("**To do lists:**\n")
        response += TodosJoinDiscord(_memberlist)
        response += TodosInviteIngame(_memberlist)
        response += TodosUpdateRanks(_memberlist)
        message = f"\n- not on discord: {len(_no_discord)}\n"
        message += f"- not on clan site: {len(_no_site)}\n"
        message += f"- need gem for rankup: {len(_no_gem)}\n"
        message += f"\nYou can add one of these after `-zbot todos ` to get more details: `nodiscord`, `nosite`, `nogem`"
        response.append(message)
        return response
    if (len(args) == 1):
        if (args[0] == "nodiscord"):
            response.append("\n\nThese are not on the clan discord:\n")
            for memb in _no_discord:
                response.append(f"{memb.name}\n")
            return response
        if (args[0] == "nosite"):
            response.append("\n\nThese are not on the clan website:\n")
            for memb in _no_site:
                response.append(f"{memb.name}\n")
            return response
        if (args[0] == "nogem"):
            response.append("\n\nThese still need to pass a gem:\n")
            for memb in _no_gem:
                response.append(f"{memb.name} for {memb.rank_after_gem}\n")
            return response
        response.append("\n\nNeeds to `-zbot todos ` plus one of : `nodiscord`, `nosite`, `nogem`")
        return response


# start discord bot to update spreadsheet colors
def RefreshList():
    """
    Updates the current memberlist spreedsheet with the latest discord info.
    Also rechecks for mismatched ranks / missing dpm tags and colours those.
    """
    update_sheet_discord_info()
    _updateColors()