import json
import os
import requests
import discord
from datetime import datetime

dateformat = '%Y-%m-%d'
timeformat = '%H.%M.%S'
datetimeformat = '%Y-%m-%d_%H.%M.%S'

discord_rank_ids = {}

def read_file(filename, type=None):
    """
    A safe wrapper for reading a file from disk as string.
    Creates parent directories and empty file if filepath does not exist.

    Returns file contents as string.
    """
    # ensure directory for file exists if not creating in current directory
    dirname = os.path.dirname(filename)
    if (dirname != ''):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    # if file does not exist create it.
    if (not os.path.exists(filename)):
        file = open(filename, 'w', encoding="utf-8")
        if type == "json":
            file.write('{}')
        file.close()
    file = open(filename, 'r', encoding="utf-8")
    result = file.read()
    file.close()
    return result
def write_file(object, filename):
    """
    A safe wrapper for writing an object to disk.
    Creates parent directories for filename if they do not exist.

    Writes str() representation of object to file.
    """
    # ensure directory for file exists if not creating in current directory
    dirname = os.path.dirname(filename)
    if (dirname != ''):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    file = open(filename, 'w', encoding="utf-8")
    file.write(str(object))
    file.close()
def delete_file(filename):
    """
    A safe wrapper for deleting a file from disk.
    Does nothing if the file doest not exist.
    """
    if not os.path.exists(filename):
        return
    os.remove(filename)

def load_json(filename):
    '''
    Wrapper function to load json from filename. Creates file and loads a blank json dictionary if it does not exist.
    Used for all config files. Startup may still fail if file is missing certain required settings.
    '''
    return json.loads(read_file(filename, type="json"))

def dump_json(dictionary, filename):
    '''
    Wrapper function to dump dictionary to json file. Creates parent directories for file if they do not exist.
    '''
    return write_file(json.dumps(dictionary, indent=4), filename)

def download_img(img_url, filename):
    #TODO assumes file opening / writing succeeds
    file = open(filename, 'wb')
    try:
        response = requests.get(img_url, stream=True)
    except Exception:
        file.close()
        return False
    
    if not response.ok:
        file.close()
        return False
    
    for block in response.iter_content(1024):
        if not block:
            break
        file.write(block)
    file.close()
    return True

async def message_ctx(ctx, message, file=None, alt_ctx=None):
    """
    Tries to send message to ctx. Allows specifying an alternative context to
    send the message to if not able to message primary ctx. Useful for 
    messsaging users as they are able to disable direct messaging.
    """
    if ctx is None:
        if alt_ctx is not None:
            await alt_ctx.send(content=message, file=file)
        return
    try:
        await ctx.send(content=message, file=file)
    except discord.errors.Forbidden:
        if alt_ctx is not None:
            await alt_ctx.send(content=message, file=file)
    except discord.ext.commands.CommandInvokeError:
        if alt_ctx is not None:
            await alt_ctx.send(content=message, file=file)
async def send_messages(ctx, config_filename, alt_ctx=None):
    """
    Send messages specified in .json config file to the ctx.
    It is possible to specify an alt_ctx to try to send messages to if ctx 
    does not allow sending messages (users can block direct messages).
    """
    # load the messages that need to be sent for this app.
    msgs = load_json(config_filename)
    # loop over messages, send as text or image depending on extension.
    for _, v in msgs.items():
        split_ext = os.path.splitext(v)
        if len(split_ext) == 2:
            if split_ext[1] == ".txt":
                message = open(f"application_templates/{v}").read()
                await message_ctx(ctx, message, alt_ctx=alt_ctx)
            if split_ext[1] == ".png":
                img_file = open(f"application_templates/{v}", "rb")
                img = discord.File(img_file)
                await message_ctx(ctx, "", file=img, alt_ctx=alt_ctx)

def int_0(int_str):
    """
    custom int() function to parse spreadsheet cells and api results.
    returns 0 for empty strings.
    returns 0 for a -1 string or int.
    returns 0 for decimal numbers.
    """
    # if its an actual int return 0 if -1, otherwise return the int
    if isinstance(int_str, int):
        if int_str == -1:
            return 0
        return int_str
    
    # not an int, assuming string
    # filter out empty strings
    if int_str == '':
        return 0
    # filter out decimal number format
    if '.' in int_str:
        return 0
    # finally try to parse as int
    result = int(int_str)
    # if the given number string was -1
    if result == -1:
        return 0
    return result
def _dateToStr(date, df=None) :
    """
    Returns string representation of datetime, date can be None.
    Result is either strftime of datetime or "".
    """
    if (date == None) : return ""
    if df is not None:
        return date.strftime(df)
    return date.strftime(dateformat)

def _strToDate(str, df=None) :
    """
    Returns date representation of string.
    Result is None if string could not be read as date.
    """
    try:
        if df is not None:
            return datetime.strptime(str, df)
        return datetime.strptime(str, dateformat)
    except ValueError :
        return None
boolstr = {
    True : 'TRUE',
    False : 'FALSE'
}

def bracket_parser(txt):
    """
    Parses a nested set of brackets without delimiters into nested list.
    ex: {{{a}{b}}{c}{{d}}} -> [[a,b],c,[d]]
    """
    if txt == "[]": return []
    depth = 0
    count = 0
    firstopen = len(txt)
    lastclose = 0
    for i,x in enumerate(txt): 
        if x == '[':
            count += 1
            if i < firstopen:
                firstopen = i+1
            if count > depth:
                depth = count
        if x == ']':
            count -= 1
            if count == 0:
                lastclose = i
                break
    if count != 0:
        raise ValueError()
    if depth == 0:
        return txt
    if depth == 1:
        res = []
        count = 0
        for i,x in enumerate(txt): 
            if x == '[':
                count += 1
                open = i+1
            if x == ']':
                count -= 1
                close = i
            if count == 0:
                res += [(txt[open:close])]
        return [res]
    res = bracket_parser(txt[firstopen:lastclose])
    textrem = txt[lastclose+1:len(txt)]
    if len(textrem) != 0:
        return res + bracket_parser(textrem)
    return res

def rank_index(*args, discord_user=None, discord_role_id=None, discord_role_name=None):
    """
    Returns the rank index for this role. Uses discord_rank_ids to
    determine which rank is highest (first mentioned is highest).
    """
    num_args = -2
    for k in locals().values():
        if k is not None:
            num_args += 1
    if num_args != 1:
        raise Exception("Unknown argument type passed to role_rank().")
    # rank name based
    if discord_role_name is not None:
        names = list(discord_rank_ids.values())
        if discord_role_name in names:
            return names.index(discord_role_name)
        return None
    # discord user based
    if discord_user is not None:
        highest_rank = len(discord_rank_ids)
        for role in discord_user.roles:
            rank = rank_index(discord_role_id=role.id)
            if rank is not None and rank < highest_rank:
                highest_rank = rank
        if highest_rank == len(discord_rank_ids):
            return None
        return highest_rank
    # rank id based
    if discord_role_id is not None:
        ids = list(discord_rank_ids.keys())
        if discord_role_id in ids:
            return ids.index(discord_role_id)
        return None