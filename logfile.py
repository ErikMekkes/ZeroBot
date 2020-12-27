from datetime import datetime
import os
import traceback
# uses date and time formats defined in utilities
import utilities

class LogFile:
    """
    Logfile(listbot).
    """
    def __init__(self, filename, parent=None):
        '''
        Sets up a logfile with specified filename. Ensures directory structure
        exists if filename has subfolders. Current date is appended to
        filename with a _ separator when the log is created.

        parent - Optional parent LogFile where anything logged by this 
        LogFile should be logged as well.
        '''
        filename += f'_{datetime.utcnow().strftime(utilities.dateformat)}'
        # ensure directory for file exists if filename specifies subfolders
        dirname = os.path.dirname(filename)
        if (dirname != ''):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        # create file if it does not exist.
        if (not os.path.exists(filename)):
            open(filename, 'w')
        self.filename = filename
        self.parent=parent
    def log(self, text):
        '''
        Appends text to this logfile, with 'datetime : ' prepended to it.
        '''
        if (isinstance(text, list)):
            err_string = ''
            for errstr in text:
                err_string += errstr
            text = err_string
        print(text)
        file = open(self.filename, "a", encoding="utf-8")
        timestamp = datetime.utcnow().strftime(utilities.datetimeformat)
        file.write((timestamp + ' : ' + text + '\n'))
        file.close()
        if self.parent is not None:
            parent.log(text)
    def log_exception(self, error, ctx=None):
        '''
        Logs an exception with its stacktrace.
        '''
        if ctx is not None:
            self.log(
                f"Error in command : {ctx.command} in {ctx.channel.name} by "
                f"{ctx.author.display_name}"
            )
        # write down full error trace in log files on disk.
        self.log(
            traceback.format_exception(
                type(error), error, error.__traceback__
            )
        )
        if self.parent is not None:
            parent.log_exception(error, ctx)