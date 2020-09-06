class Application:
    def __init__(self, channel_id, requester_id, type='guest', voters=None, votes_required=1, status='open', site_profile='no site', applist=None):
        '''
        An application, identifiable by a discord channel id.
        May or may not be part of an application list that is synced to disk.
        Other attributes are stored in a dictionary.
        '''
        if (voters is None):
            voters = []
        self.channel_id = str(channel_id)
        self.fields_dict = {
            'requester_id': requester_id,
            'type': type,
            'voters': voters,
            'votes_required': votes_required,
            'status': status,
            'site_profile': site_profile
        }
        self.applist = applist
    def __eq__(self, other):
        if isinstance(other, Application):
            # each application is given its own unique channel
            if (self.channel_id == other.channel_id):
                return True
        return False
    def set_status(self, status):
        '''
        Sets the status of this app.
        If app is part of an applist it will sync it with the applist on disk.
        new_status: open, closed, rejected or accepted.
        '''
        self.fields_dict['status'] = status
        if (self.applist != None):
            self.applist.dump()
    def set_site(self, site_profile):
        '''
        Sets the site profile of this app.
        If app is part of an applist it will sync it with the applist on disk.
        '''
        self.fields_dict['site_profile'] = site_profile
        if (self.applist != None):
            self.applist.dump()
    def add_vote(self, voter_id):
        '''
        Adds voter_id's vote to this app if voter_id has not voted on it already
        If app is part of an applist it will sync it with the applist on disk.
        Returns True if vote added, return False if voter_id already voted.
        '''
        if (not voter_id in self.fields_dict['voters']):
            self.fields_dict['voters'].append(voter_id)
            if (self.applist != None):
                self.applist.dump()
            return True
        return False
    @staticmethod
    def from_dict(channel_id, fields_dict, applist=None):
        '''
        Transforms a ("channel_id": fields_dict) pair back into an Application object.
        '''
        return Application(
            channel_id,
            fields_dict['requester_id'],
            fields_dict['type'],
            fields_dict['voters'],
            fields_dict['votes_required'],
            fields_dict['status'],
            fields_dict['site_profile'],
            applist
        )