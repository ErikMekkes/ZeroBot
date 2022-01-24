# variables, functions and settings that are shared between zerobot modules
# Go through the steps in here until you see the try to run now instruction.

# MAKE SURE YOU DO NOT SHARE your bot auth_token or drive creds keyfile, anyone
# can use them to modify your drive docs or take over your bot and do anything 
# it has permissions for. if you use git, the credentials folder used for these
# files in settings.json is in the .gitignore for this reason.

"""
Notes for developers:
WARNING: Most things in here should be referenced directly and fully as 
zerobot_common.something. Do not make local copies of them for reference, or 
be EXTREMELY sure they are NEVER reassigned. For example, if you use in a 
different file : _easy_name = zerobot_common.variable, that copy will point 
to the same object initially, but if the one in here is ever reassigned your
copy will not update and will still point to the old value, not the new one! 
similarly, reassigning your copy afterwards : _easy_name = new_value, will 
NOT update zerobot_common._easy_name to new_value

Note on imports and circular dependencies:
This module should not have circular depencies, it should load no matter
which modules have been enabled or disabled.
- utilities and logfile modules are similar safe, self contained imports.

Example of non-breaking circular importing:
site_ops and permissions modules do break the promise, they require references 
to this module. However, they only use references to this module in functions
that are not run at import time!
So while they are linked, they do not cause circular dependencies for imports
and as long as the program ensures that those references have been 
initialised by the time those functions are run (which it does) there is no
problem with imports at program runtime. I currently prefer this over
splitting this file, and it makes sense from an order of operations view. But
I might look into decoupling them a bit more in the future.
"""
# imports for google sheet access
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# zerobot modules
import utilities
from utilities import load_json, rank_index

from logfile import LogFile
# main logfile for the bot
logfile = LogFile("logs/logfile")

from site_ops import SiteOps
from permissions import Permissions

# load bot settings from json file, can change the name here to use different 
# a different settings file, nice for testing.
settings_file = "settings.json"
settings = load_json(settings_file)

# Create a discord application, then make a bot for it. Starting
# point to do that is here: https://discord.com/developers/applications

# Load your authentication token to start the bot with, you should have made 
# your own discord bot. You can find your auth token on the developers page.
# DO NOT SHARE YOUR TOKEN WITH ANYONE, or they can take over your bot.
bot_auth_token_filename = settings.get("bot_auth_token_filename")
auth_file = open(bot_auth_token_filename)
auth_token = auth_file.read()
auth_file.close()

# This loads date and time formats from settings if you want different ones.
# The default settings for this work fine, no changes needed.
_df = settings.get("dateformat", utilities.dateformat)
_tf = settings.get("timeformat", utilities.dateformat)
utilities.dateformat = _df
utilities.timeformat = _tf
utilities.datetimeformat = _df + "_" + _tf

# clan name used to look up clan memberlist on official rs hiscores api
rs_api_clan_name = settings.get("rs_api_clan_name")
# The id of your clan discord server, right click your server -> 'Copy ID'
# if you cant see the copy id option, go to your discord settings, go to app
#     settings, Advanced, and enable 'Developer Mode' to be able to check IDs.
# The bot must also be added to your discord server or it wont see the server!
clan_server_id = settings.get("clan_server_id")
guild = None
# channel where bot can post status and error messages, create one, name it
# 'staff-bot-command' to keep things easy for now. Find its channel id and 
# update it in settings.json, ID can be found with right click on channel.
bot_channel_id = settings.get("bot_channel_id")
bot_channel = None
# regular bot commands channel for all members
bot_channel2_id = settings.get("bot_channel2_id")
bot_channel2 = None

# You can tell the bot where commands are allowed to be used, do this in this 
# file by adding channel names or channel ids to the list of a command.
# by default a lot of them are allowed in the staff-bot channel
permissions_filename = settings.get("permissions_filename")
permissions = Permissions(permissions_filename)

# The main memberlist function, works a bit like runeclan.
# can also be toggled, you dont have to use it, but its the most common one.
memberlist_enabled = settings.get("memberlist_enabled", True)
daily_mlist_update_enabled = settings.get("daily_mlist_update_enabled", True)
daily_update_time = settings.get("daily_update_time")
# Controls if update should skip fetching latest ingame info if a recent copy
# exists locally.
use_cached_ingame_data = settings.get("use_cached_ingame_data", True)

# Check the discord_ranks.json settings file. Make sure that file contains
# your discord ranks in the right order! (highest at the top). You will need
# at least these three roles:
#  - Staff Member
#  - Clan Member
#  - Guest

# Check the match_disc_ingame and parse_discord_rank tables in rankchecks.py !
# They should match your setup for rank names!

# This is needed because the bot needs to know which ranks match up with what.
# You might have more discord ranks or roles that are not used for ranks, and 
# the bot needs to know the rank order.
# THESE ROLES SHOULD HAVE UNIQUE NAMES, or the bot won't know which match up.
json_rank_ids = load_json(settings.get("discord_ranks_filename"))
discord_rank_ids = {}
for k,v in json_rank_ids.items():
    discord_rank_ids[int(k)] = v
# store a copy in utilities as well, these should remain unchanged
utilities.discord_rank_ids = discord_rank_ids

# A few individual ranks/roles for ease of access, make sure these match!
# guest role on discord, for discord users that have not joined clan
#     also automatically given to ex clan members
guest_role_id = settings.get("guest_role_id")
guest_rank_index = rank_index(discord_role_id=guest_role_id)
# clan member discord role given to all clan members
clan_member_role_id = settings.get("clan_member_role_id")
# staff member discord role, higher roles are also considered staff.
# staff members or higher roles are protected from bot changes
staff_role_id = settings.get("staff_role_id")
staff_rank_index = rank_index(discord_role_id=staff_role_id)

# The bot automatically notifies you who is inactive in your clan. It will
# take a while for this to become useful if you just started using the bot.
# But it is nice for clans close to the member limit / to keep people active.
# You can add people that should not be on the inactives list to this file:
inactive_exceptions_filename = settings.get("inactive_exceptions_filename")
inactive_exceptions = load_json(inactive_exceptions_filename)
# How long it should take before someone is considered inactive:
inactive_days = 30

# This is just where the memberlists are kept, be careful with these files.
current_members_filename = settings.get("current_members_filename")
old_members_filename = settings.get("old_members_filename")
banned_members_filename = settings.get("banned_members_filename")



# You should have a working clan memberlist bot by this point :) try it out
#  by running ZeroBot.py. The remaining settings are for other modules.
# Type '-zbot updatelist' in the bot command channel to run the memberlist 
# update right away! Then try the the '-zbot find', '-zbot inactives', and 
# '-zbot activity' commands after the daily update is done.




# ENABLING THIS IS REQUIRED for google drive ZeroBot modules:
# - google drive spreadsheet copy of the memberlist, for editing / backups
# - channel syncing from spreadsheet text, to edit discord messages together.
# - competition spreadsheet, for managing teams and tracking messages
drive_functions_enabled = settings.get("drive_functions_enabled", False)
# You need a service account, which allows the bot to access google drive.
#   Starting point for creating one : https://console.developers.google.com/
#   After you made a service account, create access credentials for it and 
#   copy the keyfile to the credentials folder.
#   the default place for it is credentials/drive_creds_keyfile.json
# DO NOT SHARE YOUR CREDENTIALS, or they can take over your google drive.
if drive_functions_enabled:
    drive_scope = ["https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"]
    # name of your keyfile with google credentials created in the dev console
    drive_creds_keyfile_name = settings.get("drive_creds_keyfile_name")
    drive_creds = ServiceAccountCredentials.from_json_keyfile_name(
        drive_creds_keyfile_name,
        drive_scope
    )
    drive_client = gspread.authorize(drive_creds)

# The settings below let you set up a google drive version of the memberlists.
# Highly recommended for editing and as a backup of the memberlist info.
#      Needs the google drive credentials setup above to work.
# You need a Google Drive spreadsheet that uses the bot's memberlist format,
# make a copy of this example spreadsheet to get the correct format: 
# https://docs.google.com/spreadsheets/d/1IjuFWeiRxcrb2JIKeF7Dywuj6DeMc8Po9Ihj1oPyrh4
#   You do not need to add the first info by hand, the bot will add all your
#   clanmembers automatically with the next daily update it does.
# Be careful with the format ! Do not delete / move / add columns!
#   You can hide columns you dont use (right click column -> hide)
#   You can edit info, but keep the same format! (number stays number etc.)
# Next give the service account access to your spreadsheet by inviting it,
# use the share button on the sheet, then enter your service account's email.
sheet_memberlist_enabled = settings.get("sheet_memberlist_enabled", False)
if sheet_memberlist_enabled:
    # name of the memberlist spreadsheet document
    memberlist_doc_name = settings.get("memberlist_doc_name")
    memberlist_doc = drive_client.open(memberlist_doc_name)

    # spreadsheet tabs that are used in the memberlist document
    current_members_sheet = memberlist_doc.worksheet("Current Members")
    old_members_sheet = memberlist_doc.worksheet("Old Members")
    banned_members_sheet = memberlist_doc.worksheet("Banned Members")
    warnings_sheet  = memberlist_doc.worksheet("Warnings")

# Information for the bot on the layout of drive spreadsheets, if you change
# the sheet layout this needs to be updated too, and the functions used in
# sheet_ops.py to read the sheet. This is why you're careful with the layout.
class SheetParams:
    start_col = "A"
    end_col = "T"
    # number of header rows on the memberlist sheets
    header_rows = 1
    # range for header data
    header_range = f"{start_col}1:{end_col}{header_rows}"
    # header entries for the memberlist sheets
    header_entries = [
            "Name","Ingame Rank","Discord Rank","Site Rank","Join Date","Passed Gem","Site Profile","Leave Date",
            "Leave Reason","Referral","Discord ID","Discord Name","Old Names","Last Active","ID","Entry ID","Warning Points","Note1","Note2","Note3"]
    update_header = [
        "AUTOMATIC", "UPDATE IN", "5 MINUTES", "S T O P", "EDITING!",
        "! - ! - !", "!", "!", "!", "S T O P", "EDITING!", "! - ! - !", "!", "!",
        "!", "!", "!", "S T O P", "EDITING!", "! - ! - !"
    ]
    @staticmethod
    def range_full(list_length=550):
        # range string for header+entire memberlist data
        range_str = (
            f"{SheetParams.start_col}"
            f"{1}:"
            f"{SheetParams.end_col}"
            f"{1+SheetParams.header_rows+list_length+25}"
        )
        return range_str
    @staticmethod
    def range_no_header(sheet=None, list_length=525):
        """
        Constructs a range string that covers the entire sheet except for the header rows.
        """
        if sheet is not None:
            list_length = sheet.row_count
        # 1 indexed range string for entire memberlist data, skipping header rows
        range_str = (
            f"{SheetParams.start_col}"
            f"{1+SheetParams.header_rows}:"
            f"{SheetParams.end_col}"
            f"{1+SheetParams.header_rows+list_length}"
        )
        return range_str

# Other modules you can toggle in settings.json, see example_settings.json
# They have more settings and configs in their own python files. I wont go
# through explaining them all, the code and settings should be straigtforward.
applications_enabled = settings.get("enable_applications", False)
dropcomp_enabled = settings.get("dropcomp_enabled", False)
events_enabled = settings.get("events_enabled", False)
forumthread_enabled = settings.get("forumthread_enabled", False)
forumthread = settings.get("forumthread")
reaction_roles_enabled = settings.get("reaction_roles_enabled", False)
funresponses_enabled = settings.get("funresponses_enabled", False)
channel_manager_enabled = settings.get("channel_manager_enabled", False)
daily_channel_reload_enabled = settings.get(
    "daily_channel_reload_enabled", False
)
daily_reload_channels = settings.get("daily_reload_channels", [])
submissions_enabled = settings.get("submissions_enabled", False)

# channel for killtime or killcount submissions
submissions_channel_id = settings.get("submissions_channel_id")

# banlist channel where the bot can post banlist info.
# for memberlist refresh_banlist command, might add to daily update as well
banlist_channel_id = settings.get("banlist_channel_id")

# specific for applications only
if applications_enabled:
    # role on discord that allows people to start an application
    approval_role_id = settings.get("approval_role_id")
    approval_rank_index = rank_index(discord_role_id=approval_role_id)
    # role given to people when they join the clan (usually matching recruit)
    join_role_id = settings.get("join_role_id")
    join_rank_index = rank_index(discord_role_id=join_role_id)

# Manager for operations to clan site, hosted by shivtr (https://shivtr.com/)
site_enabled = settings.get("site_enabled", False)
if site_enabled:
    site_login_creds_filename = settings.get("site_login_credentials_filename")
    site_login_credentials = load_json(site_login_creds_filename)
    site_base_url = settings.get("site_base_url")
    siteops = SiteOps()

# channel names and their ids, loaded on bot startup from guild.
# only used by permissions.py to look up name -> id
discord_channels = None

# load messages that should give a role for a reaction from disk
if reaction_roles_enabled:
    reaction_messages_filename = settings.get("reaction_messages_filename")
    reaction_messages = load_json(reaction_messages_filename)

# individuals or ranks that dont need dpm knowledge check
gem_exceptions = ["Alexanderke","Skye","Zer0 Legend","Zer0 OG","Veteran Member","Elite Member","PvM Specialists","Supreme PvMer","MasterClass PvMer"]
# minimum rank that needs a dpm knowledge check
gem_req_rank = "Full Member"

enabled_modules = ["ServerWatchCog", "ReaperCrewCog"]
if memberlist_enabled : enabled_modules.append("MemberlistCog")
if reaction_roles_enabled : enabled_modules.append("ReactionRolesCog")
if applications_enabled : enabled_modules.append("ApplicationsCog")
if channel_manager_enabled : enabled_modules.append("ChannelCog")
if events_enabled : enabled_modules.append("EventsCog")
if dropcomp_enabled : enabled_modules.append("DropCompCog")
if forumthread_enabled : enabled_modules.append("ForumThreadCog")
if funresponses_enabled : enabled_modules.append("FunResponsesCog")
if submissions_enabled : enabled_modules.append("SubmissionsCog")

archive_blacklist = [
    755473609342058619, #tag request

    307827188634353665, #announcement
    818941995531632670, #game news
    419347383021862912, #streamers

    307827203171811339, #general
    755485394778194000, #pvm advice
    695403997464494131, #specialist hub
    338076302684848131, #achievments
    434016697687474186, #off-topic
    727562380980125716, #other games
    763208637660266578, #pof borrow / trade

    755487300741234778, # event suggestion
    381062945041285121, # team finding

    775363362787295255, #submissions

    892047321603395654, #achievements tracker
    307827142534889472, #bot commands
    591801230213382145, #price check channel
    815661081208160337, #dank memes bot

    349320454382682118, # warbands
    192316399413231616, #nsfw staff
    699940703748489246, #staff bot
    411673295201501184, #clan issues
    311870323634995201, #leaders

    192299572607844352, #server members
    536539435702157312, #rework discuss
    632273628326789150, #event command
    450518786529951765, #skyenet command
    783206091222810644, #admin logs

    347712635149484042, #music bots
    802687845462573086, #respond to voice
]

# recommended not to touch the functions below

def drive_connect():
    """
    Reconnects to the google drive API if not used recently.
    """
    if (drive_creds.access_token_expired): drive_client.login()

def get_named_channel(channel_name):
    """
    Searches the guild for the channel name, returns the channel if found.
    CAUTION: channel names are NOT unique, this returns the first result if
    there are duplicate names.
    Returns None if no matching channel found.

    Intended to find pre-defined, unique channels by name. Operates on the
    common guild object.
    """
    for chann in guild.channels:
        if (chann.name == channel_name):
            return chann
    return None

def get_named_role(role_name):
    """
    Searches the guild for the role name, returns the role if found. 
    CAUTION: role names are NOT unique, this returns the first result if
    there are duplicate names.
    Returns None if no matching role found.

    Intended to find pre-defined, unique role by name. Operates on the
    common guild object.
    """
    for role in guild.roles:
        if (role.name == role_name):
            return role
    return None

def is_member(discord_user):
    """
    Checks if a discord user is a clan member using the role given to all
    clan members.
    """
    for r in discord_user.roles:
        if r.id == clan_member_role_id:
            return True
    return False
def is_staff_member(discord_user):
    """
    Checks if discord user has the staff member role.
    """
    for r in discord_user.roles:
        if r.id == staff_role_id:
            return True
    return False
def get_rank_id(discord_role_name):
    """
    Look up id for a discord rank name
    """
    names = list(discord_rank_ids.values())
    if discord_role_name in names:
        index = names.index(discord_role_name)
        return list(discord_rank_ids.keys())[index]
    return -1
def highest_role(discord_user):
    """
    Returns the highest role this discord user has. Uses discord_rank_ids to
    determine which rank is highest (first mentioned is highest).
    """
    rank = len(discord_rank_ids)
    highest_role = None
    for role in discord_user.roles:
        index = rank_index(discord_role_id=role.id)
        if index is None:
            continue
        if index < rank:
            rank = index
            highest_role = role
    return highest_role

def get_lower_ranks(discord_user, r_index):
    """
    Returns all ranked roles the user has that are lower than r_index.
    """
    lower_roles = []
    for role in discord_user.roles:
        index = rank_index(discord_role_id=role.id)
        if index is not None and index > r_index:
            lower_roles.append(role)
    return lower_roles