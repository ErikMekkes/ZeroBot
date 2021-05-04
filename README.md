# ZeroBot
ZeroBot is designed specifically for our clan to be able to do member applications and rankups on discord, and to track members namechanges, stats and activity.
It can do a lot more cool stuff like roles assigned by emojis reactions, guides that can be edited through google drive and I'm usually looking to add more fun stuff for things like clan competitions and events.

Because it is so specific to our clan, you would have to make many changes or cut out parts to make this work for you.
Even so, if you're looking to make something similar there should be many usable parts / ideas / examples here.
I'll try to make the master branch a cleaner more generic clan utility bot, but it's not a current priority.

Everything except for some .json settings / data files is in python, python's libraries for discord and google sheets are excellent and its fun coding practise.

As the project is simple python, use any editor you like. The actual setup is very complex though.
To run it you only need a python environment with these dependencies installed:
gspread, gspread_formatting, oauth2client, beautifulsoup4 and discord.py installed.
I run our live version on a very simple but secure ubuntu server. I included an example systemd service file with a startup script that can pull a most recent version from git.

## Suggested simple workspace setup guide for Windows, using VSCode

First steps:
- install git and set up your git credentials
- clone the ZeroBot git repository somewhere
- install python for windows
- install visual studio code
- install the python extension for VS Code

Set up Visual Studio Code:
- Open Visual Studio Code
- Open the ZeroBot git folder (becomes workspace folder)
- Verify that VSCode can use the python interpreter (bottom left next to current git branch)

- Create a new virtual environment with this command in VSCode terminal (bottom center tab): python -m venv .venv
- Activate the virtual environment for your terminal: .\.venv\Scripts\activate
- check pip is up to date for your virtual environment: python -m pip install --upgrade pip
- install the required python modules into your virtual environment: python -m pip install gspread gspread_formatting oauth2client beautifulsoup4 discord.py


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

I do not make plan to assist you with installing or adapting this to your use. As I've said, this is mostly a passion project specifically for Zer0 PvM.
But, if you found a bug, added something cool or think you've cleaned something up or made it more efficient you can let me know by opening a pull request.