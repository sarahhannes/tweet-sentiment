import glob
import pandas as pd
import re
import os
from write_log import add_log

new_files = glob.glob("./src/data/*_new.txt")  # find /src/data/*_new.csv

if new_files:  # if there is new file(s)
    print('Got new file(s)!!')

    if len(new_files) > 1:  # if more than one exist
        print('There are multiple new files!')
        print(new_files)
        print(max(new_files))
        latest_new_file = max(new_files)
        df_new = pd.read_csv(latest_new_file,  sep='\t')  # read the latest *_new.csv file
        print('here is the df_new!')
        print(latest_new_file)
        print(df_new)

    else:  # if there is only 1 *_new.csv file
        latest_new_file = new_files[0]
        df_new = pd.read_csv(latest_new_file, sep='\t')

    date_new_list = re.findall("([0-9]+)", latest_new_file)
    date_new_file = '-'.join(date_new_list)  # get date from latest_new_file

    raw_files = glob.glob('./data/raw/*_raw.*')  # find /data/raw/*_raw.*

    if raw_files:  # if raw file(s) exist
        print('YAY found raw file(s)')
        print(raw_files)

        if len(raw_files) > 1:  # if there are more than 1 raw files
            latest_raw_file = max(raw_files)  # get the latest one
            print('there are multiple raw files', latest_raw_file)
            for file in raw_files:
                if file != latest_raw_file:
                    # os.remove(file)  # delete every files except the latest_raw_file #to be uncommented
                    add_log(msg=f"Redundant file deleted {file}")

        else:  # if there is only 1 raw file
            latest_raw_file = raw_files[0]

        date_raw_list = re.findall("([0-9]+)", latest_raw_file)
        date_raw_file = '-'.join(date_raw_list)  # get date from latest_raw_file

        if date_raw_file >= date_new_file:  # if date from latest raw file >= date from latest new file
            add_log(msg="Raw file is already up to date. No action performed")

        else:  # if date from latest raw file < date from latest new file
            if latest_raw_file[-3:] == 'txt':  # if the raw file is txt
                df_raw = pd.read_csv(latest_raw_file, sep="\t")
            else:  # if the raw file is not txt (possibly could only be csv)
                df_raw = pd.read_csv(latest_raw_file)
            print('YAY! we can retrieve df_raw')
            print(latest_raw_file)
            print(df_raw)
            df_merged = pd.concat([df_new, df_raw], ignore_index=True, sort=False)
            df_merged.to_csv(f"./data/raw/{date_new_file}_raw.txt", index=False, sep="\t")  # save file in /data/raw/

            if os.path.exists(latest_raw_file) and os.path.isfile(latest_raw_file):  # check if latest_raw_file exist
                os.remove(latest_raw_file)  # delete old latest_raw_file #to be uncommented
                add_log("Raw file updated. Old raw file deleted")  # update log

    else:  # no raw file found in /data/raw/
        df_new.to_csv(f"./data/raw/{date_new_file}_raw.txt", index=False, sep='\t')  # save df_new as /data/raw/*_raw.txt
        add_log(msg=f"Raw file not found. Copied new file and save as ./data/raw/{date_new_file}_raw.txt")  # update log

    # Move ./src/data/*_new.txt to /data/new/
    df_new.to_csv(f"./data/new/{date_new_file}_new.txt", index=False, sep='\t')
    add_log(msg=f"Copied new file and save as ./data/new/{date_new_file}_new.txt")  # update log

    # Delete /src/data/*_new.txt
    for file in new_files:
        print('delete new file')
        os.remove(file)
        add_log(msg=f"Deleted {file}")

else:  # no new file found in /src/data/
    print('No new file found!!')
    add_log(msg="No new file found. No action performed")

"""
# TODO: test all routes/ all possible scenarios, one by one
    1) Scenario: multiple new files, multiple raw files. raw file is not up to date.
        Expected action: get the latest raw file, get the latest new file, merge, save as {new_date}_raw.txt
        TOCHECK: - check if the total len(df_merge) is correct
    2) Scenario: multiple new file, multiple raw files. raw file is up to date.
        Expected action: nothing performed. update log.
        --success!
    3) Scenario: raw file is in different format (csv, txt)
        Expected action:
        Suggestion: save everything as txt? to standardize everything...??
        --done change all to txt
    4) Scenario: multiple raw files, multiple new files. raw file is up to date. no files in /data/new folder. 
        Expected action: copy new file to /data/new/ and delete new files in src/data. do nothing for raw file.
        --success!!! <3
        
# TODO: uncomment 'tobe-uncommented' lines
# TODO: add, commit, push to origin
# TODO: check why add_log adds log.txt to outer dir. test against scrape.py
"""
