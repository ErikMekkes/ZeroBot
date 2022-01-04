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
	"Zer0 Legend" : ["Lieutenant"],
	"Zer0 OG" : ["Lieutenant"],
	"Veteran Member" : ["Lieutenant"],
	"Advanced Member" : ["Sergeant"],
	"Full Member" : ["Corporal"],
	"Recruit" : ["Recruit"],
    "Clan Friends/Allies" : [],
    "Guest" : [],
    "Waiting Approval" : []
}

# This table is used to convert user typed ranks to intended discord rank
# when someone types `-zbot rankup veteran` for example
parse_discord_rank = {
    "owner" : "Leaders",
    "deputy leader" : "Leaders",
    "co-leader" : "Leaders",
    "clan-coordinator" : "Clan-Coordinator",
    "clan issues" : "Clan Issues",
    "citadel co" : "Citadel Co",
    "media co" : "Media Co",
    "staff member" : "Staff Member",
    "masterclass pvmer" : "MasterClass PvMer",
    "supreme pvmer" : "Supreme PvMer",
    "pvm specialist" : "PvM Specialists",
	"zer0 legend" : "Zer0 Legend",
	"legend" : "Zer0 Legend",
	"zer0 og" : "Zer0 OG",
	"og" : "Zer0 OG",
    "elite member" : "Elite Member",
    "veteran member" : "Veteran Member",
    "advanced member" : "Advanced Member",
    "full member" : "Full Member",
    "novice" : "Recruit",
    "registered guest" : "Registered Guest",
    "retired member" : "Retired member",
    "kicked member" : "Kicked Member",
    # name variations -> discord rank
    "novice member" : "Recruit",
    "recruit" : "Recruit",
    "advanced" : "Advanced Member",
    "veteran" : "Veteran Member",
    "elite" : "Elite Member",
    "specialist" : "PvM Specialists",
    "pvm specialists" : "PvM Specialists",
    "guest" : "Guest",
    "retired" : "Retired member",
    "kicked" : "Kicked Member",
    "full" : "Full Member",
    "leader" : "Leaders",
    "staff_member" : "Staff Member",
    "masterclass_pvmer" : "MasterClass PvMer",
    "supreme_pvmer" : "Supreme PvMer",
    "pvm_specialist" : "PvM Specialists",
    "veteran_member" : "Veteran Member",
    "advanced_member" : "Advanced Member",
    "full_member" : "Full Member",
    "waiting_approval" : "Waiting Approval"
}

# rank matching if shivtr site is connected.
# adding "" = not having a site account is allowed as match
match_disc_site = {
    "Leaders" : ["","Leader","Co-Leader"],
    "Clan Issues" : ["","Clan Issues"],
    "PvM Coordinator" : ["","Clan-Coordinator"],
	"Staff Member" : ["","Staff Member"],
	"MasterClass PvMer" : ["","MasterClass PvMer"],
	"Supreme PvMer" : ["","Supreme PvMer"],
	"PvM Specialists" : ["","PvM Specialists"],
	"Elite Member" : ["","Elite Member"],
	"Zer0 Legend" : ["","Veteran Member"],
	"Zer0 OG" : ["","Veteran Member"],
	"Veteran Member" : ["","Veteran Member"],
	"Advanced Member" : ["","Advanced Member"],
	"Full Member" : ["","Full Member"],
	"Recruit" : ["","Recruit"],
    "Clan Friends/Allies" : ["","Registered Guest","Retired member"],
    "Guest" : ["","Registered Guest","Retired member"],
    "Waiting Approval" : [""]
}

# dpm tags, lowest at top (highest rank = highest index in dict)
# names are unused, just to distinguish here and perhaps for future use
mage_dpm_tags = {
    590922060193071118: "Initiate Mage DPM",
    590923162410024980: "Adept Mage DPM",
    590923449162006553: "Master Mage DPM",
    590924385452556309: "Extreme Mage DPM"
}
melee_dpm_tags = {
    590922131366477824: "Initiate Melee DPM",
    590923236603199509: "Adept Melee DPM",
    590923501930545181: "Master Melee DPM",
    590924439604953139: "Extreme Melee DPM"
}
range_dpm_tags = {
    590921829204623381: "Initiate Range DPM",
    590923065622528000: "Adept Range DPM",
    590923403377246208: "Master Range DPM",
    590924088852217856: "Extreme Range DPM"
}
extreme_dps_discord_id = 668543463322812451

boss_tags = {
    674321943247192075,
    674321787886239779,
    674322127125479429,
    808332092823961641,
    674321305495142452,
    674321662669488128,
    674321502082170881,
    538377429891153920,
    538377295799386122,
    538377787803697162,
    538377081097289730,
    796009482613162014,
    796009708275236904,
    796009893249286195,
    786653923174907935,
    538377910533226536,
    538377553753407488,
    893774649035468810,
    893774207337521182,
    620706392352751627,
    620706827855986698,
    634848100900405248,
    786653717029847060,
    474659531847237662,
    761563102697095168,
    761563422457593876,
    761562722520268810,
    761563345370873877,
    796009428561166376,
    796009634867052564,
    796009809367269416,
    761564324777951272,
    761564190120476682,
    893774431120412673,
    893774921015111690,
    786653656438931486,
    761563185026826270,
    761562491892400138,
    761563005778526218,
    761562895669788692,
    761563271677214730,
    761563508289962024,
    796009326095368202,
    796009582744698940,
    796009760926203944,
    761564244901888000,
    761564152468078632,
    893774487294734336,
    893774925976977430,
}

def update_discord_info(_memberlist):
    """
    Checks discord roles and dpm tags for each member in the memberlist and updates them to the highest rank.
    """
    # loop through memberlist
    for memb in _memberlist :
        # skip if discord id invalid
        if not valid_discord_id(memb.discord_id): continue
        usr = zerobot_common.guild.get_member(memb.discord_id)
        # skip if usr not found, keep old rank & discord id, set name as left discord to indicate
        # "Not in clan discord" = exception for old people who never joined / people who cant join
        if (usr == None):
            memb.discord_name = "Left clan discord"
            continue

        # update discord name
        memb.discord_name = usr.name

        # update dpm tags
        memb.passed_gem = False
        highest_mage = -1
        highest_melee = -1
        highest_range = -1
        memb.misc["highest_mage"] = ""
        memb.misc["highest_melee"] = ""
        memb.misc["highest_range"] = ""
        for r in usr.roles:
            if r.id == extreme_dps_discord_id:
                memb.misc["highest_mage"] = r.name
                memb.misc["highest_melee"] = r.name
                memb.misc["highest_range"] = r.name
                memb.passed_gem = True
                break
            if r.id in mage_dpm_tags:
                memb.passed_gem = True
                index = list(mage_dpm_tags.keys()).index(r.id)
                if index > highest_mage:
                    memb.misc["highest_mage"] = r.name
                    highest_mage = index
            if r.id in melee_dpm_tags:
                memb.passed_gem = True
                index = list(melee_dpm_tags.keys()).index(r.id)
                if index > highest_melee:
                    memb.misc["highest_melee"] = r.name
                    highest_melee = index
            if r.id in range_dpm_tags:
                memb.passed_gem = True
                index = list(range_dpm_tags.keys()).index(r.id)
                if index > highest_range:
                    memb.misc["highest_range"] = r.name
                    highest_range = index

        # update highest discord rank
        highest_role = zerobot_common.highest_role(usr)
        if highest_role is not None:
            memb.discord_rank = highest_role.name
        # previous rank info kept if new rank unknown?

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