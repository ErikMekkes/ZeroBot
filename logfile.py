from datetime import datetime
import os

class LogFile:
    """
    Logfile(listbot).
    """
    def __init__(self, filename, dateformat, timeformat):
        # ensure directory for file exists if not creating in current directory
        dirname = os.path.dirname(filename)
        if (dirname != ''):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        # create file if it does not exist.
        if (not os.path.exists(filename)):
            open(filename, 'w')
        self.filename = filename
        self.dateformat = dateformat
        self.timeformat = timeformat
        self.datetimeformat = f"{dateformat} {timeformat}"
    def log(self, text):
        if (isinstance(text, list)):
            err_string = ''
            for errstr in text:
                err_string += errstr
            text = err_string
        print(text)
        file = open(self.filename, "a", encoding="utf-8")
        file.write((datetime.utcnow().strftime(self.datetimeformat) + ' : ' + text + '\n'))
        file.close()