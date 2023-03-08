# Zer0Bot
Zer0Bot collaboration

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

## RULES
Obviously if you're here you're invited on a pure 'I trust you' basis, but the protection I can enforce on a free repository is limited, so some basics to keep this manageable:

  1. No commits to the main branch, no merges, no pull requests, you **do not touch the main branch** for now.

### Git workflow practices:
   - **Start by making your own new work branch from Zer0BotTest**, it has a working setup with login credentials for the test discord & test google drive memberlist, and pre-configured test settings for those. There is nothing important that you could break here.
   - When you have something finalized, you will need to make a new release branch from your work that is compatible with the latest version of Zer0BotDev. On there you remove test settings / config files and credential files, and finally you merge Zer0BotDev into this release branch & resolve conflicts if there are any (remember to re-add any new stuff you needed to the live settings / config files at this point).
   - Make a pull request for your release branch to Zer0BotDev
   - Make a pull request for your work branch to Zer0BotTest to keep that one updated for the next persons work.
   - We check together how you solved any conflicts, check for bugs/mistakes and make sure your personal / test stuff stays off the dev branch
   - We merge both your pull requests, both your new branches can be deleted at this point.
   - Unless absent only Yathsou merges new Dev versions onto the live main branch.

### Why so strict:
minimises conflicts from working on similar code parts and keeps it easy to start with new work from test branch, but more importantly... 
**If you break the main branch you take down zbot the next time it restarts**, let me be the one to break the main branch, because I have direct access to un-break it.

The discord bot is configured to automatically pull the latest version from main on startup, and can be restarted within discord with the `-zbot restart` command. If I'm away for an extended period of time and you're sure of your work, you can use this to carefully update the main branch. If you break the bot in any way that prevents the restart command you wont be able to undo any mistakes (until we rent a nice shared virtual machine somewhere cheap for $4 a month or so) and the bot will remain broken until I'm back.

Obviously there is some potential for abuse here, again, i'm trusting you to not abuse the potential for entering malicious code onto the main branch and running it on my machine. Let me make it clear that abuse here goes beyond joking around and 'roleplaying games' together, this is software development and server administration responsibility.

## I don't care much for Code Style, but... ;)
- try to keep lines short-ish, press enter key many often much happy, feeling like you need too many ugly indents -> means you could have made a new function / file -> leads to better organised code. And much easier for me to review side by side in comparison editors when I dont have to scroll horizontally to find whats at the end of your line.
- descriptive names please, i_like_dashes but CamelCaseNames is fine too as long as I can figure out what its for.
- comments are good, I forget what I made and go "how the hell did I do this" or "where does that go/come from" **all the time**, doing that for your stuff will be more difficult...
- with how much text is involved with all the stuff zbot has to say, I dont really care how or where you format those as long as it works, use whatever you feel like.

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
