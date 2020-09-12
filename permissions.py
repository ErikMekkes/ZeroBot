import json
import zerobot_common
from utilities import load_json, dump_json

class Permissions:
    '''
    Manager for permissions that has its state synced with a file on disk.
    '''
    def __init__(self, permissions_filename):
        '''
        Sets up a new manager for permissions, loads initial state of permissions from disk.
        This allows the bot to reload the state of permissions when losing connection / restarting.
        '''
        self.permissions_filename = permissions_filename
        self.load()
    def load(self):
        '''
        Load the state of permissions from file on disk
        '''
        self.permissions = load_json(self.permissions_filename)
    def dump(self):
        '''
        Write the current state of permissions to file on disk
        '''
        dump_json(self.permissions, self.permissions_filename)
    def allow(self, command, channel):
        '''
        Allow a command to be used in the specified channel. New state of permissions is written to disk afterwards.
        command : name of a command
        channel : id number of channel, or the name of a known channel in channel_ids
        '''
        channel_id = self.lookup_channel(channel)
        
        if command in self.permissions:
            self.permissions.get(command).append(channel_id)
        else:
            self.permissions[command] = [channel_id]
        # write latest copy to disk
        self.dump()
    def disallow(self, command, channel):
        '''
        Ensure a command is not allowed in a certain channel. New state of permissions is written to disk afterwards.
        command : name of a command
        channel : id number of channel, or the name of a known channel in channel_ids
        '''
        channel_id = self.lookup_channel(channel)

        if (command in self.permissions):
            # inefficient but no removal while iterating
            for chann in list(self.permissions.get(command)):
                chann_id = self.lookup_channel(chann)
                if (channel_id == chann_id):
                    # using original ambiguous int/string to remove
                    self.permissions.get(command).remove(chann)
        # write latest copy to disk
        self.dump()
    def is_allowed(self, command, channel):
        '''
        Checks if the command is allowed in the specified channel.
        command : name of a command
        channel : id number of channel, or the name of a known channel in channel_ids

        True iff command is in permissions AND channel_id is in the list of allowed channels linked with that command.
        '''
        channel_id = self.lookup_channel(channel)
        
        if command in self.permissions:
            channels = self.permissions.get(command)
            for chann in channels:
                try:
                    chann_id = self.lookup_channel(chann)
                except TypeError:
                    zerobot_common.logfile.log(f'permissions config warning: {command} allowed in {chann} but {chann} cant be found.')
                    continue
                if (channel_id == chann_id):
                    return True
        return False
    def lookup_channel(self, channel):
        '''
        Looks up channel in channel_ids if channel is a string, if channel is a number it just returns it.
        Throws TypeError if channel is a string but can't be found as known (channel:id) pair.
        channel : id number of a channel, or a name present in channel_ids
        '''
        try:
            channel_id = int(channel)
        except ValueError:
            channel_id = zerobot_common.discord_channels.get(channel)
            if (channel_id == None):
                raise TypeError(f'channel: {channel} - is not a known channel name')
        return channel_id