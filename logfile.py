"""
Supports logging operations, including error traces and reporting to other
logs to combine reports from multiple logfiles.
"""
from datetime import datetime
import os
import traceback
# uses date and time formats defined in utilities
import utilities

class LogFile:
    """
    Logfile (ZeroBot implementation).
    """
    def __init__(self, filename, parent=None, parent_prefix=""):
        """
        Sets up a logfile with specified filename. Ensures directory structure
        exists if filename has subfolders. Current date is appended to
        filename with a _ separator when the log is created.

        parent - Optional parent LogFile where anything logged by this 
        LogFile should be logged as well.
        parent_prefix - sets a prefix for text logged to parent.
        """
        filename += f"_{datetime.utcnow().strftime(utilities.dateformat)}"
        # ensure directory for file exists if filename specifies subfolders
        dirname = os.path.dirname(filename)
        if (dirname != ""):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        # create file if it does not exist.
        if (not os.path.exists(filename)):
            open(filename, "w")
        self.filename = filename
        self.parent = parent
        self.parent_prefix = parent_prefix
    def log(self, text, prefix=""):
        """
        Appends text to this logfile, with "datetime : " prepended to it.
        """
        if prefix != "":
            text = f"{prefix} : {text}"
        if (isinstance(text, list)):
            err_string = ""
            for errstr in text:
                err_string += errstr
            text = err_string
        print(text)
        file = open(self.filename, "a", encoding="utf-8")
        timestamp = datetime.utcnow().strftime(utilities.datetimeformat)
        file.write((timestamp + " : " + text + "\n"))
        file.close()
        if self.parent is not None:
            self.parent.log(text, self.parent_prefix + prefix)
    def log_exception(self, error, ctx=None, prefix=""):
        """
        Logs an exception with its stacktrace.
        """
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
            self.parent.log_exception(
                error, ctx, prefix=self.parent_prefix
            )