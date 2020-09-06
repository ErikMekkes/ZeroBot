from datetime import datetime

class LogFile:
    """
    Logfile(listbot).
    """
    def __init__(self, filename, dateformat, timeformat):
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