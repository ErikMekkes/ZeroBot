# variables, functions and settings that are shared between zerobot modules

# MAKE SURE YOU DO NOT SHARE your bot auth_token or drive creds keyfile, anyone
# can use them to modify your drive docs or take over your bot and do anything 
# it has permissions for. if you use git, the credentials folder used for these
# files in settings.json is in the .gitignore.

# WARNING: Everything in here should be referenced directly and fully as 
# zerobot_common.something. Do not make local copies of them for reference, or 
# be EXTREMELY sure they are NEVER reassigned. For example, if you use in a 
# different file : _easy_name = zerobot_common.variable, that copy will point 
# to the same object initially, but if the one in here is ever reassigned your
# copy will not update and will still point to the old value, not the new one! 
# similarly, reassigning your copy afterwards : _easy_name = new_value, will 
# NOT update zerobot_common.discord_roles_filename

# Note on imports and circular dependencies:
# This module should not have circular depencies, it should be self contained 
# and decoupled from other files as much as possible.
# - utilities, logfile, applications modules are safe, self contained imports.
#
# site_ops and permissions modules break this promise, they require references 
# to this module. However, they only use references to this module in functions
# that are not run at import time.
# So while they are linked, they do not cause circular dependencies for imports
# and as long as the program ensures that those references have been 
# initialised by the time those functions are run (which it does) there is no
# problem with imports at program runtime. I currently prefer this over
# splitting this file, and it makes sense from an order of operations view. But
# I might look into decoupling them a bit more in the future.

import json
import os
from datetime import datetime
# imports for google sheet access
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# zerobot modules
import utilities
from utilities import load_json, dump_json
from logfile import LogFile
from site_ops import SiteOps
from permissions import Permissions

# load bot settings from json file
settings_file = 'settings.json'
settings = load_json(settings_file)

# load authentication token for starting bot, you should have made your own 
# discord bot. Create a discord application, then make a bot for it. Starting
# point to do that is here: https://discord.com/developers/applications
bot_auth_token_filename = settings.get('bot_auth_token_filename')
auth_file = open(bot_auth_token_filename)
auth_token = auth_file.read()
auth_file.close()

# Google Drive credentials and client to interact with the Google Drive API
# You should have a service account, with credentials to login to it.
# Starting point for creating one : https://console.developers.google.com/
# You should also have given your service account access to your drive sheet:
# Invite it using the share button on the doc, use the service account's email.
drive_scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']
drive_creds_keyfile_name = settings.get('drive_creds_keyfile_name')
drive_creds = ServiceAccountCredentials.from_json_keyfile_name(
    drive_creds_keyfile_name,
    drive_scope
)
drive_client = gspread.authorize(drive_creds)
drive_doc_name = settings.get('drive_doc_name')
drive_doc = drive_client.open(drive_doc_name)

# spreadsheet tabs that are used
current_members_sheet = drive_doc.worksheet('Current Members')
old_members_sheet = drive_doc.worksheet('Old Members')
banned_members_sheet = drive_doc.worksheet('Banned Members')
recent_changes_sheet = drive_doc.worksheet('Recent Changes')

def drive_connect():
    '''
    Reconnects to the google drive API if not used recently.
    '''
    if (drive_creds.access_token_expired): drive_client.login()

# if set, use date and time formats from settings 
dateformat = settings.get('dateformat', utilities.dateformat)
timeformat = settings.get('timeformat', utilities.dateformat)
utilities.dateformat = dateformat
utilities.timeformat = timeformat
utilities.datetimeformat = dateformat + ' ' + timeformat

# Manager for operations to clan site, hosted by shivtr (https://shivtr.com/)
site_login_creds_filename = settings.get('site_login_credentials_filename')
site_login_credentials = load_json(site_login_creds_filename)
site_base_url = settings.get('site_base_url')
siteops = SiteOps()
# disable site? (site rank functions will always have 'full member' as result)
site_disabled = settings.get('site_disabled')

# name used to look up members_lite clan memberlist file on official rs api
rs_api_clan_name = settings.get('rs_api_clan_name')
# guild = the clan discord 'server' object, loaded on bot start using it's id.
clan_server_id = settings.get('clan_server_id')
guild = None

# channel names and their ids, loaded on bot startup from guild.
discord_channels = None
# role names and their ids, loaded on bot startup from guild.
discord_roles = None

# default channel where bot can post status and error messages
default_bot_channel_id = settings.get('default_bot_channel_id')

# logfiles
logfile = LogFile('logs/logfile')
reactionlog = LogFile('logs/reactionroles')

# load known messages that should give a role for a reaction from disk
reaction_messages_filename = settings.get('reaction_messages_filename')
reaction_messages = load_json(reaction_messages_filename)

# load permissions for use of commands in channels from disk
permissions_filename = settings.get('permissions_filename')
permissions = Permissions(permissions_filename)

# people that wont be shown on the inactives list
inactive_exceptions_filename = settings.get('inactive_exceptions_filename')
json_dictionary = load_json(inactive_exceptions_filename)
inactive_exceptions = json_dictionary.get('inactive_exceptions')

# Discord roles and their ranks, because you might have discord roles that are
# not used for ranks, and because the bot needs to know the rank order.
# If you want the bot to be able to check if members have the right ranks, you
# need to give matching ingame / discord / site ranks the same number.
# THESE ROLES SHOULD HAVE UNIQUE NAMES, or the bot won't know which to assign.
# Required for:
#  - ApplicationsCog : tells it which roles are ranks to give and their order
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
    'Guest' : 1,
    'Waiting Approval' : 0
}