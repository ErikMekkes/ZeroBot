# variables, functions and settings that are shared between zerobot modules

# MAKE SURE YOU DO NOT SHARE your bot auth_token or drive creds keyfile, anyone can use them to 
# modify your drive docs or take over your bot and do anything it has permissions for.
# if you use git, the credentials folder used for these files in settings.json is in the .gitignore.

# WARNING: Everything in here should be referenced directly and fully as zerobot_common.something
# Do not make local copies of them for reference, or be EXTREMELY sure they are NEVER reassigned.
# if in a different file you do, for example : _easy_name = zerobot_common.discord_roles_filename
# that copy will point to the same object initially, but if the one in here is ever reassigned your
# copy will not update and will still point to the old value, not the new one! similarly, reassigning
# your copy afterwards : _easy_name = new value will NOT update zerobot_common.discord_roles_filename

# Note on circular dependencies:
# This file imports the init constructors from Applications, SiteOps, Permissions.
# But those files also require certain imports from this file.
# This works as long as the program start is not in either of these and imports zerobot_common.
# I prefer this over splitting this file, it also makes sense from an order of operations view,
# the references required should all be established by the time the constructors are called.

import json
import os
from datetime import datetime
# imports for google sheet access
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# zerobot modules
from logfile import LogFile
from applications import Applications
from site_ops import SiteOps
from permissions import Permissions

def load_json(filename):
    '''
    Wrapper function to load json from filename. Creates file and loads a blank json dictionary if it does not exist.
    Used for all config files. Startup may still fail if file is missing certain required settings.
    '''
    # ensure directory for file exists if not creating in current directory
    dirname = os.path.dirname(filename)
    if (dirname != ''):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    # if file does not exist create and return as empty dictionary.
    if (not os.path.exists(filename)):
        file = open(filename, 'w')
        file.write('{}')
        file.close()
        return {}
    file = open(filename, 'r')
    result = json.loads(file.read())
    file.close()
    return result

def dump_json(dictionary, filename):
    '''
    Wrapper function to dump dictionary to json file. Creates parent directories for file if they do not exist.
    '''
    # ensure directory for file exists if not creating in current directory
    dirname = os.path.dirname(filename)
    if (dirname != ''):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    file = open(filename, 'w')
    file.write(json.dumps(dictionary, indent=4))
    file.close()


# load bot settings from json file
settings_file = 'settings.json'
settings = load_json(settings_file)

# load authentication token for starting bot, you should have made your own for your new discord bot.
# starting point to create a discord application (bot) : https://discord.com/developers/applications
bot_auth_token_filename = settings.get('bot_auth_token_filename')
auth_file = open(bot_auth_token_filename)
auth_token = auth_file.read()
auth_file.close()

# Google Drive credentials and client to interact with the Google Drive API
# you should have created service account credentials to access your google sheets document.
# starting point to create google web credentials : https://console.developers.google.com/
drive_scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']
drive_creds_keyfile_name = settings.get('drive_creds_keyfile_name')
drive_creds = ServiceAccountCredentials.from_json_keyfile_name(drive_creds_keyfile_name, drive_scope)
drive_client = gspread.authorize(drive_creds)
drive_doc_name = settings.get('drive_doc_name')
drive_doc = drive_client.open(drive_doc_name)

# spreadsheet tabs that are used
current_members_sheet = drive_doc.worksheet("Current Members")
old_members_sheet = drive_doc.worksheet("Old Members")
banned_members_sheet = drive_doc.worksheet("Banned Members")
recent_changes_sheet = drive_doc.worksheet("Recent Changes")

def drive_connect():
    '''
    Reconnects to the google drive API if not used recently.
    '''
    if (drive_creds.access_token_expired): drive_client.login()

# date and time formats
dateformat = settings.get('dateformat')
timeformat = settings.get('timeformat')

# Manager for operations to a clan website, hosted by shivtr (https://shivtr.com/)
site_login_credentials_filename = settings.get('site_login_credentials_filename')
site_login_credentials = load_json(site_login_credentials_filename)
site_base_url = settings.get('site_base_url')
siteops = SiteOps(dateformat, timeformat)
# disable site component? (site rank functions will always have 'full member' as result)
site_disabled = settings.get('site_disabled')

# name used to look up members_lite clan memberlist file on official rs api
rs_api_clan_name = settings.get('rs_api_clan_name')
# guild = the clan discord 'server' object, loaded on bot startup using it's id.
clan_server_id = settings.get('clan_server_id')
guild = None

# category that new application channels should be added under, loaded on bot startup from guild.
applications_category_id = settings.get('applications_category_id')
# channel that allows application commands, this channel also gets cleared automatically
app_requests_channel_id = settings.get('app_requests_channel_id')
applications_category = None

# channel names and their ids, loaded on bot startup from guild.
discord_channels = None
# role names and their ids, loaded on bot startup from guild.
discord_roles = None

# default channel where bot can post status and error messages
default_bot_channel_id = settings.get('default_bot_channel_id')

# logfiles
logfile = LogFile("logs/logfile_" + datetime.utcnow().strftime(dateformat), dateformat, timeformat)
reactionlog = LogFile("logs/reactionroles_" + datetime.utcnow().strftime(dateformat), dateformat, timeformat)
applications_log = LogFile("logs/applications_" + datetime.utcnow().strftime(dateformat), dateformat, timeformat)

# load known messages that should give a role for a reaction from disk
reaction_messages_filename = settings.get('reaction_messages_filename')
reaction_messages = load_json(reaction_messages_filename)

# load applications status from disk
applications_filename = settings.get('applications_filename')
applications = Applications(applications_filename)

# load permissions for use of commands in channels from disk
permissions_filename = settings.get('permissions_filename')
permissions = Permissions(permissions_filename)

# people that wont be shown on the inactives list
inactive_exceptions_filename = settings.get('inactive_exceptions_filename')
inactive_exceptions = load_json(inactive_exceptions_filename).get('inactive_exceptions')