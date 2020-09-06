# ZeroBot
ZeroBot is designed specifically for our clan to be able to do member applications and rankups on discord, and to track members namechanges, stats and activity.
I'm looking to add more cool stuff like highscores, guides that can be edited through google drive, competitions etc.

Because it is so specific to our clan, you might have to make many changes or cut out parts to make it work for you.
Even so, if you're looking to make something similar there should be many usable parts / ideas here.
I'll try to make the master branch a cleaner more generic clan utility bot, but it's not a current priority.

Everything except some .json settings / data files is in python, python's libraries for discord and google sheets are excellent and its fun coding practise.

The only requirement to run it is a python environment with gspread, gspread_formatting, oauth2client and discord.py installed. The setup is complex though.
I run our live version on a very simple but secure ubuntu server. I included an example systemd service file with a startup script that can pull a most recent version from git.

== Suggested simple workspace setup: Windows, VSCode ==
First steps:
- install git and set up your git credentials
- clone the ZeroBot git repository somewhere
- install python for windows
- install visual studio code
- install the python extension for VS Code

- Set up Visual Studio Code:
Open Visual Studio Code
Open the ZeroBot git folder (becomes workspace folder)
Verify that VSCode can use the python interpreter (bottom left next to current git branch)

Create a new virtual environment with this command in VSCode terminal (bottom center tab): python -m venv .venv
Activate the virtual environment for your terminal: .\.venv\Scripts\activate
check pip is up to date for your virtual environment: python -m pip install --upgrade pip
install the required python modules into your virtual environment: python -m pip install gspread gspread_formatting oauth2client discord.py


== To run the bot (or a test setup) ==
The bot cant make any ingame changes, but keep in mind that depending on the access rights, it can do very real damage to your linked discord, spreadsheet or site when it is set up wrong or modified. It is highly recommended to make a separate test setup for all of the components below, and to run that test bot any time you make changes, to prevent mistakes from affecting your real version.

I obviously made it so you cant use our live versions unless I grant you access to them, so you will need:
- your own discord application / bot (https://discord.com/developers/applications), along with its bot auth token
- your own discord server to which your bot is allowed to connect, with permissions that let the bot access what it needs.
- a setup of roles / categories / channels in your discord that matches the references for them in the bot's .json config files
  - permissions.json : tell the bot which commands are allowed where (can use channel name or id)
  - (*) ranks.json : tell the bot which ingame / discord / site ranks match a rank (default is same names), lets you set alternative names here
  - (*) site_ranks.json : tell the bot what site id belongs to each site rank name. 
  - reaction_messages.json : tell the bot what role (id) to give for each response to a messages
  - inactive_exceptions.json : you can enter names here that should not appear on the bots inactive player list
  - channel_ids.json : is autogenerated, no need to edit, used by bot to link channel names to ids
  - discord_roles.json : is autogenerated, no need to edit, used by bot to link role names to ids
- your own memberlist google spreadsheet, with matching tabs / column setup (unless you modify the code for it).
- your own google service account (https://console.developers.google.com/), with access to your google spreadsheet, and its service credentials keyfile.
- once you have the above they can be set in settings.json. (make a 2nd settings.json for a test setup)
  - use your own files for: 
  - use your own clan & google drive name
  - (*) use your own clan site url

(*) Unless you have a similar clan site (shivtr), You wont need to modify any site references. You should keep the site_disabled = true in settings.json.
This disables site account management, to enable it you need to provide login credentials for an admin account on the site so the bot is be able to make rank changes.

As long as you followed the above and have the right references set up, when you run zerobot.py it should connect to your discord.
It should start its timer for the daily update to your spreadsheet and you should be able to use all its commands and features.

Contributions are very appreciated, if you added something cool or think you've cleaned something up or made it more efficient, make a pull request!
Start a branch from GenericDev for contributions to the generic bot on master, or from ZeroBotTest for contributions to the Zer0 PvM specific bot on ZeroBotLive.