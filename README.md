# ZeroBot
ZeroBot is designed specifically for our clan to be able to do member applications and rankups on discord, and to track members namechanges, stats and activity.
It can do a lot more cool stuff like roles assigned by emojis reactions, guides that can be edited through google drive and I'm usually looking to add more fun stuff for things like clan competitions and events.

Because it is so specific to our clan, you would have to make many changes or cut out parts to make this work for you.
Even so, if you're looking to make something similar there should be many usable parts / ideas / examples here.

Everything except for some .json settings / data files is in python, python's libraries for discord and google sheets are excellent and it is fun coding practise.

I do not plan to assist you with installing or adapting this to your use. This is mostly a passion project specifically for Zer0 PvM.
But, if you found a bug, added something cool or think you've cleaned something up or made it more efficient you can let me know by email or by opening a pull request.

As the project is simple python, use any editor you like. The actual setup to run is quite complex though.
I run our live version on a very simple but secure ubuntu server. I did include an example systemd service file with a startup script that can pull a most recent version from git.

## Installation / Workspace Requirements to run the bot
Very simple:
- clone the repository somewhere on your machine
- have python installed on your machine
- setup a new python virtual environment in the repository folder with `python -m venv .zbotvenv`
- move the 2 chat-exporter package folders from the existing .venv folder to your new .zbotenv and delete the now empty .venv
- activate the .zbotenv (`.zbotenv\Scripts\activate.bat` on Windows, `source .zbotenv/bin/activate` on UNIX)
- install the following packages in the now active .zbotenv with python pip (should say (.zbotenv) in front of the command line):
`python -m pip install discord.py beautifulsoup4 google-auth google-auth-oauthlib gspread==5.4.0 gspread-dataframe==3.3.0 gspread-formatting==1.0.6 oauth2client oauthlib requests requests-oauthlib rapidfuzz emoji==1.6.1`

Your editor of choice should now be able to find and activate the .zbotvenv and run `python ZeroBot.py` from there, or you can manually do it.

2022-08-07 note: some of these packages are outdated / have newer versions, but I have not tested or migrated over to them yet.
chat-exporter is copied because I MODIFIED the chat-exporter package to support local downloads, do not update / replace it. TODO: move to own repository, the original author doesnt want local download options in their package for good reasons.

## Setting up to run the bot (or a test setup)
First off, a warning, while the bot cant make any ingame changes, keep in mind that depending on the access rights, it can do very real damage to your linked discord, spreadsheet or site when it is set up wrong or modified. It is highly recommended to make a separate test setup for all of the components below, and to run that test bot first any time you make changes, to prevent mistakes from affecting your real version.

I obviously made it so you cant use our live versions unless I grant you access to them, so you will need:
- your own discord application / bot (https://discord.com/developers/applications), along with its bot auth token
- your own discord server, to which you have added your bot so that it is allowed to connect, with permissions that let the bot access what it needs.
Go through the steps and comments in zerobot_common.py and check the settings.json entries mentioned in there along the way.
Doing that should guide you to a memberlist management bot that has ingame stats like runeclan, by going through these steps:
  - getting the bot in your discord server and configuring your clan name
  - setting up a discord channel for bot commands and responses
  - permissions.json : telling the bot which commands are allowed where
  - enabling the daily memberlist update at a convenient time.
  - setting up discord roles and which ranks they match with, using discord_ranks.json and rankchecks.py
  - setting up the list of inactivite members, and using inactive_exceptions.json

As long as you followed the above when you run zerobot.py it should connect to your discord and start its timer for the daily memberlist update. You can force the first update right away by typing -zbot updatelist in you bot command channel, and then try out commands like, -zbot find, -zbot inactives, and -zbot activity.

There are many other modules you can enable afterwards.
- module to handle applications to join the clan or rankup on discord. Also includes the option to safely archive discord channels (copies all text and images to disk)
- google drive memberlist spreadsheet connection, to show and edit member info easily in one place
- module for a shivtr clan site connection, to manage member ranks there
- module to let the bot get text from a spreadsheet, and post it as discord messages. Very nice for working on discord messages together, like channels with guides or large amounts of info text. 
- module to track when our clan recruitment thread needs a bump.
- module to assign roles when people react with emojis to posts.
- module with some fun examples of random bot chat responses.
- module to let members create and manage discord channels safely for events
- module to upload screenshots from discord channels to a spreadsheet for clan competitions.


## Zer0Bot Code Overview
### Components
At its simplest zbot is just a python program that runs in an endless loop on the server. It is connected to discord, the runescape api, google drive api, the clan site, and locally stored files.

- with discord we use 3 types of bot interactions
  - events: message received, channel created / deleted, connection lost etc.
  - commands: message that starts with the bot's prefix (-zbot) and a name that matches a python @commands function (respond)
  - the newer slash commands: the /something context menu's in discord, look great but these have to be defined separately and are a bit more tricky.
- Currently we only request clan and clan member stats from the runescape api once per day, for the memberlist update.
  - the daily comparison for who stayed / renamed / left / is (in)active is the most complex part, and pretty accurate so far :).
- The google drive api is used for 3 google drive files: memberlists, discord channels, and a competition tracking sheet.
   - The memberlists document is mostly used as a more practical editor, all the member info is primarily kept on local storage. Because of this there is a lot of back and forth to keep the member information synched. We actually have enough raw data that if we were to keep it all on the sheet it would become slow and unresponsive. We also update frequently with the way the bot handles applications and discord stats, so local storage was pretty much required (and very nice now for quick searches with the bot)
   - For the discord channel document, the bot simply finds the right tab and reads info from there, nothing too complicated.
   - competition sheets are also a very simple one way send-a-new-row-to-the-sheet when the bot gets a message kind of deal.
- the clan site connection still exists, the bot is still able to access & update info there, but is no longer actively required for anything.
- in local storage the bot keeps the current memberlists (with a lot of stats) and previous archived ones, settings (mostly .json config files), images and texts for (application) forms, and a lot of images and text files from recording things like applications, competitions and errors/bot status logs.

### Main Files
#### Main entry point: Zer0Bot.py, the server runs this program on startup (after updating from github), and if it ever crashes the server will reload it from github and restart it (up to a limit of repeated failures to prevent us getting timed out of discord for much longer for trying to connect too often).

We could write everything the bot needs to do in here but that would be a horrible mess, Zer0bot.py should not need much editing, and only does the following:
  - set some of the major discord bot settings
  - save some basic information for modules to make use of when it first connects with an on_ready handler
  - load all the bot's functionality modules, in discord's terms these are named cog's.
  - set up a callback system for discord events and the daily update, very practical, you can add functions to these and they will be run when these events happen.
  - check and log any discord connection status updates
  - start the bot by connecting to discord with the bot's login auth_token (we keep the real zbot discord and google access keys out of github to prevent leaks)

#### Second most important file: zerobot_common.py
This file is used for various global configuration settings, variables and other information. The kind of stuff almost every module needs.
  
Because it is used by so many modules there are two very important details further explained in the python comments:
  - generally you should reference information with the full name as zerobot_common.something, don't make copies.
  - zerobot_common can not import other files unless you can guarantee they do not cause circular import / initialisation dependency loops.

#### Cogs (discord modules)
Whenever I'm adding things that could be grouped together, I try to collect them in a module with similar functions / settings to keep things organized. By now there are many modules and many more functions and settings. This is important to keep things findable and fixable, and prevent repeating work already done elsewhere. But also with the goal that by keeping some structure like this, you are more easily able to add new parts, that there is a 'free' space for something new without feeling like you are adding to a giant pile of clutter.

Plenty of examples in the code (some are still poorly organized large files), zerobot_common is one, the utilities.py file is another, and stuff like ApplicationsCog making use of memberlist management functions from MemberlistCog, The lengthy daily udpate process used for the daily update being separated to clantrack.py, grouping things in ChannelCog & EventsCog.
