import json
import os

dateformat = '%Y-%m-%d'
timeformat = '%H:%M:%S'
datetimeformat = '%Y-%m-%d %H:%M:%S'

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