from datetime import date
import inspect
import re


def add_log(msg, date=date.today()):
    """
    Add logs to log.txt

    :param msg: message to include in the log
    :type msg: str
    :param date: logging date
    :type date: str
    :param current_dir: name of current .py script
    :type current_dir: directory object

    :rtype: str
    :return: logs in the form of date, current directory, message
    """
    previous_frame = inspect.currentframe().f_back
    (filename, line_number,
     function_name, lines, index) = inspect.getframeinfo(previous_frame)
    short_filename = re.findall("([^\/]+$)", filename)[0]

    with open("./log.txt", "a+") as logfile:
        logfile.write("\n")
        logfile.write(f"{str(date)}/GH Action@{short_filename}: {msg};")
