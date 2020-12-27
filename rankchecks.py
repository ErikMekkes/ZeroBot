import zerobot_common
from member import valid_discord_id, valid_profile_link

gem_exceptions = ["Alexanderke","Veteran Member","Elite Member","PvM Specialists"]

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
    'Elite Member' : 6,
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
        rank = 0
        for r in usr.roles:
            rank_numb = zerobot_common.discord_ranks.get(r.name,-1)
            if  rank_numb >= rank:
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
        discord_rank = zerobot_common.discord_ranks.get(discord_rank_name, 0)
        ingame_rank_name = memb.rank
        ingame_rank = ingame_ranks.get(ingame_rank_name, 0)
        passed_gem = memb.passed_gem
        discord_recruit_rank = zerobot_common.discord_ranks['Recruit']
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
        if not valid_discord_id(memb.discord_id) or memb.discord_name == "Left discord":
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