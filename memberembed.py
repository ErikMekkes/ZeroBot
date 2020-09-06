import zerobot_common
import discord

def member_embed(member):
    """
    Returns a nice looking discord embed object representation of the given member. Embedded objects have set fields
    that support markup, so they can be used to create a nicely formatted page.
    """
    # check which sheet member was found on -> format into string
    status = ""
    rank_prefix = ""
    if (member.sheet == zerobot_common.current_members_sheet):
        status = "- Current Member"
    if (member.sheet == zerobot_common.old_members_sheet):
        status = "- Retired Member"
        rank_prefix = "Old "
    if (member.sheet == zerobot_common.banned_members_sheet):
        status = "- \uD83D\uDE21 BANNED Member \U0001F621"
    # check if member has old names, if it has any -> format into string
    if (len(member.old_names) == 0):
        old_names = "**Old Names :** None\n"
    else:
        old_names = "**Old Names :** "
        for name in member.old_names:
            old_names += f"{name},"
        # remove trailing comma, add newline
        old_names = old_names[:-1]
        old_names += "\n"
    # lazy code to check if notes empty, if not empty -> format into string
    if (member.note1 == ""):
        note1 = ""
    else:
        note1 = f"**Note 1 :** {member.note1}\n"
    if (member.note2 == ""):
        note2 = ""
    else:
        note2 = f"**Note 2 :** {member.note2}\n"
    if (member.note3 == ""):
        note3 = ""
    else:
        note3 = f"**Note 3 :** {member.note3}\n"
    
    if (member.passed_gem):
        gem_str = f"{member.highest_mage.replace(' DPM', '')}\u2002{member.highest_melee.replace(' DPM', '')}\u2002{member.highest_range.replace(' DPM', '')}"
    else:
        gem_str = "None"
    if (member.rank_after_gem != ""):
        gem_rank_str = f"**Rank after gem :** {member.rank_after_gem}"
    else:
        gem_rank_str = ""
    # consistent length clan xp format
    numb_str = str(member.clan_xp)
    dotted_xp = ""
    j = 0
    for i in range (len(numb_str)-1,-1,-1):
        if (j > 0 and j % 3 == 0): dotted_xp = '.' + dotted_xp
        j += 1
        dotted_xp = numb_str[i] + dotted_xp
    max_clan_xp_length = 13
    clan_xp_suffix = '\u2002'
    for _ in range (0, max_clan_xp_length - len(dotted_xp)):
        clan_xp_suffix += "\u2002"
    clan_xp_str = dotted_xp + clan_xp_suffix
    # consistent length ingame rank format
    ingame_rank_str = member.rank
    max_rank_length = 17
    for _ in range (0, max_rank_length - len(member.rank)):
        ingame_rank_str += "\u2002"
    # consistent length discord rank format
    discord_rank_str = member.discord_rank
    max_rank_length = 17
    for _ in range (0, max_rank_length - len(member.discord_rank)):
        discord_rank_str += "\u2002"
    if (member.leave_reason == ""):
        leave_str = ""
    else:
        leave_str = f"**Leave Reason :** {member.leave_reason}"

    
    discord_user = zerobot_common.guild.get_member(member.discord_id)
    if (discord_user != None):
        mention = discord_user.mention
        avatar_url = discord_user.avatar_url
    else:
        mention = member.discord_name
        avatar_url = discord.embeds.EmptyEmbed
    
    if (member.last_active != None):
        last_active_str = member.last_active.strftime('%Y-%m-%d')
    else:
        last_active_str = "Unknown"

    embed = discord.Embed()
    embed.set_author(name = f"{member.name} {status}", icon_url = avatar_url)
    
    embed.description = (
        f"**Discord :** {mention}\u2001({member.discord_id})\n"
        f"**Site Profile :** {member.profile_link}\n"

        f"**Join Date :** {member.join_date}\u2001\u2001"
        f"**Last Active :** {last_active_str}\u2001\u2001"
        f"**Event Points :** {member.event_points}\n"

        f"**Clan xp :** {clan_xp_str}\u2001\u2002"
        f"**dps tags :** {gem_str}\n"

        f"**{rank_prefix}Ingame Rank :** {ingame_rank_str}\u2001\u2005"
        f"**Site Rank :** {member.site_rank}\n"
        f"**Discord Rank :** {discord_rank_str}\u2001\u2001"
        f"{gem_rank_str}\n"
        f"{old_names}"
        f"{leave_str}"
        f"{note1}"
        f"{note2}"
        f"{note3}"
    )

    return embed