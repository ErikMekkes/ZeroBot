import json
from application import Application
from utilities import load_json, dump_json

class Applications:
    '''
    Manager for applications that has its state synced with a file on disk.
    '''
    def __init__(self, applications_filename):
        self.applications_filename = applications_filename
        self.load()
    def load(self):
        '''
        Load the state of applications from disk.
        '''
        apps = load_json(self.applications_filename)

        self.applist = []
        # apps dictionary contains ("channel_id": fields_dict) pairs, channel_id are keys.
        # value associated with channel_id key = dictionary containing the other 5 fields
        for channel_id in apps:
            fields_dict = apps[channel_id]
            self.applist.append(Application.from_dict(channel_id, fields_dict, self))
    def dump(self):
        '''
        Writes the status of applications to disk.
        '''
        app_dict = {}
        for app in self.applist:
            app_dict[app.channel_id] = app.fields_dict
        dump_json(app_dict, self.applications_filename)
    def append(self, app):
        '''
        Appends the app to the applist and syncs with file on disk.
        '''
        self.applist.append(app)
        app.applist = self
        self.dump()
    def has_open_app(self, user_id):
        '''
        Returns the users first / oldest application if they have one.
        Returns None otherwise, can be used as a 'get oldest open app for user'.
        '''
        for app in self.applist:
            fields_dict = app.fields_dict
            if (fields_dict['requester_id'] == user_id and fields_dict['status'] == 'open'):
                return app
        return None
    def get_app(self, channel_id):
        '''
        Searches the list of applications for the application that uses the specified channel.
        Returns the application if found, returns None otherwise. 
        channel_id is a key, which gets stored and loaded as string, so this uses string comparison.
        '''
        channel_id = str(channel_id)
        for app in self.applist:
            if (app.channel_id == channel_id):
                return app
        return None