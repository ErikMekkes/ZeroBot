import json
import os
import requests

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