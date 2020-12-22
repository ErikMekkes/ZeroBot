from datetime import datetime
import os
import traceback
# uses date and time formats defined in utilities
import utilities

class LogFile:
    """
    Logfile(listbot).
    """
    def __init__(self, filename):
        '''
        Sets up a logfile with specified filename. Ensures directory structure
        exists if filename uses a different folder. Current date is appended to
        filename with a _ separator when the log is created.
        '''
        filename += f'_{datetime.utcnow().strftime(utilities.dateformat)}'
        # ensure directory for file exists if not creating in current directory
        dirname = os.path.dirname(filename)
        if (dirname != ''):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        # create file if it does not exist.
        if (not os.path.exists(filename)):
            open(filename, 'w')
        self.filename = filename
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
        self.log(traceback.format_exception(type(error), error, error.__traceback__))