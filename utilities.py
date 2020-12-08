import json
import os
import requests
import discord

dateformat = '%Y-%m-%d'
timeformat = '%H.%M.%S'
datetimeformat = '%Y-%m-%d_%H.%M.%S'

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