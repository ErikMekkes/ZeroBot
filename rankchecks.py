import zerobot_common
from zerobot_common import gem_exceptions, gem_req_rank
from member import valid_discord_id, valid_profile_link

match_disc_ingame = {
    "Leaders" : ["Owner","Deputy Owner","Overseer"],
    "Clan Issues" : ["Coordinator"],
    "PvM Coordinator" : ["Coordinator"],
	"Staff Member" : ["Organiser"],
	"MasterClass PvMer" : ["Admin"],
	"Supreme PvMer" : ["General"],
	"PvM Specialists" : ["Captain"],
	"Elite Member" : ["Captain"],
	"Veteran Member" : ["Lieutenant"],
	"Advanced Member" : ["Sergeant"],
	"Full Member" : ["Corporal"],
	"Recruit" : ["Recruit"],
    'Clan Friends/Allies' : [],
    "Guest" : [],
    "Waiting Approval" : []
}
# adding "" = not having a site account is allowed as match
match_disc_site = {
    "Leaders" : ["Leader","Co-Leader"],
    "Clan Issues" : ["Clan Issues"],
    "PvM Coordinator" : ["Clan-Coordinator"],
	"Staff Member" : ["Staff Member"],
	"MasterClass PvMer" : ["","MasterClass PvMer"],
	"Supreme PvMer" : ["","Supreme PvMer"],
	"PvM Specialists" : ["","PvM Specialists"],
	"Elite Member" : ["","Elite Member"],
	"Veteran Member" : ["","Veteran Member"],
	"Advanced Member" : ["","Advanced Member"],
	"Full Member" : ["","Full Member"],
	"Recruit" : ["","Recruit"],
    'Clan Friends/Allies' : ["","Registered Guest","Retired member"],
    "Guest" : ["","Registered Guest","Retired member"],
    "Waiting Approval" : [""]
}

# used to find a member's highest dps tag
dps_tags = {
    '170k Mage DPM (No longer obtainable)' : 1,
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
        # skip if discord id invalid
        if not valid_discord_id(memb.discord_id): continue
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
                memb.misc["highest_mage"] = "Extreme DPS"
                memb.misc["highest_melee"] = "Extreme DPS"
                memb.misc["highest_range"] = "Extreme DPS"
                break
            else :
                if "Mage" in r.name:
                    current_tag = dps_tags.get(memb.misc["highest_mage"], 0)
                    if dps_tags.get(r.name, 0) > current_tag:
                        memb.misc["highest_mage"] = r.name
                if "Melee" in r.name:
                    current_tag = dps_tags.get(memb.misc["highest_melee"], 0)
                    if dps_tags.get(r.name, 0) > current_tag:
                        memb.misc["highest_melee"] = r.name
                if "Range" in r.name:
                    current_tag = dps_tags.get(memb.misc["highest_range"], 0)
                    if dps_tags.get(r.name, 0) > current_tag:
                        memb.misc["highest_range"] = r.name

        # update highest discord rank
        rank = -1
        for r in usr.roles:
            try:
                rank_numb = list(match_disc_ingame.keys()).index(r.name)
            except ValueError:
                # this role is not a known rank
                continue
            if rank_numb < rank:
                rank = rank_numb
                memb.discord_rank = r.name
        # store all current discord role ids.
        discord_roles = []
        for r in usr.roles:
            discord_roles.append(r.id)
        memb.misc["discord_roles"] = discord_roles

def TodosJoinDiscord(memberlist):
    response = list()
    for memb in memberlist:
        # no discord id, and never manually entered name
        if not valid_discord_id(memb.discord_id):
            response.append(f"{memb.name}\n")
    response = [f"**Need to join discord or need a discord id update on sheet:** {len(response)}\n"] + response
    return response
def TodosUpdateRanks(memberlist):
    _need_rank_update = list()
    for memb in memberlist:
        # find minimum rank for gem, can set as -1 for no gem req
        gem_req_disc_rank = list(match_disc_ingame.keys()).index(gem_req_rank)
        try:
            discord_rank = list(match_disc_ingame.keys()).index(memb.discord_rank)
        except ValueError:
            # cant find their rank in the list -> needs a rank.
            _need_rank_update.append(memb)
            continue
        # no gem, gem req for their rank, rank or name not in gem exceptions.
        if not memb.passed_gem and discord_rank <= gem_req_disc_rank:
            if not(memb.discord_rank in gem_exceptions or memb.name in gem_exceptions):
                _need_rank_update.append(memb)
                continue
        # site rank does not match discord rank
        if not memb.site_rank in match_disc_site[memb.discord_rank]:
            _need_rank_update.append(memb)
            continue
        # ingame rank does not match discord rank
        if not memb.rank in match_disc_ingame[memb.discord_rank]:
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

def Todos(_memberlist, *args):
    """
    Finds tasks by looking at inconsistencies in the memberlist.
    Assumes the memberlist is up to date with latest info.
    """
    _no_discord = list()
    _no_site = list()
    _no_gem = list()
    for memb in _memberlist:
        # no valid site profile
        if not valid_profile_link(memb.profile_link):
            _no_site.append(memb)
        # no valid discord id, or no longer on discord
        if not valid_discord_id(memb.discord_id) or memb.discord_name == "Left clan discord":
            _no_discord.append(memb)
        # not passed gem, and listed to get rankup with gem = need gem
        if not memb.passed_gem:
            _no_gem.append(memb)
    response = list()
    if (len(args) != 1):
        response.append("**To do lists:**\n")
        response += TodosJoinDiscord(_memberlist)
        response += TodosInviteIngame(_memberlist)
        response += TodosUpdateRanks(_memberlist)
        message = f"\n- not on discord: {len(_no_discord)}\n"
        message += f"- not on clan site: {len(_no_site)}\n"
        message += f"- no gem : {len(_no_gem)}\n"
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
                response.append(f"{memb.name}\n")
            return response
        response.append("\n\nNeeds to `-zbot todos ` plus one of : `nodiscord`, `nosite`, `nogem`")
        return response