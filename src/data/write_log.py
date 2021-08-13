from datetime import datetime
import inspect
import re


def add_log(msg):
    """
    Add logs to log.txt

    :param msg: message to include in the log
    :type msg: str
    :param date: logging date
    :type date: str

    :rtype: str
    :return: logs in the form of date, current directory, message
    """
    previous_frame = inspect.currentframe().f_back
    (filename, line_number,
     function_name, lines, index) = inspect.getframeinfo(previous_frame)
    short_filename = re.findall("([^\/]+$)", filename)[0]

    date_now = datetime.now()
    dt_str = date_now.strftime("%Y-%m-%d %H:%M:%S")
    with open("./src/data/log.txt", "a+") as logfile:
        logfile.write("\n")
        logfile.write(f"{str(dt_str)}@{short_filename}: {msg};")
