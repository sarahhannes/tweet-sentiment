import twint
import nest_asyncio
import glob
import pandas as pd
import datetime
import os

nest_asyncio.apply()


def add_log(msg, date=datetime.date.today(), current_dir=os.path.basename(__file__)):
    """
    append to log.txt
    """
    with open("./log.txt", "a+") as logfile:
        logfile.write(f"{str(date)}/GH Action@{current_dir}: {msg}")


# Get last_update date
lastupdate_file = glob.glob('./src/data/LASTUPDATE.txt')[0]
col_index = pd.read_csv(lastupdate_file).columns
last_update = str(col_index.values[0])  # get last_update date as str
print('here', last_update)

# if last_update == today
if last_update == str(datetime.date.today()):
    # update log
    add_log(msg="Scraped data is up to date. No action performed.")

else:
    try:  # Scrape, save as csv, update LASTUPDATE, update log
        # Query parameters
        start_date = last_update  # last_update date
        end_date = str(datetime.date.today())  # today's date
        hashtag = '#dhl'

        # Initialize configuration
        scraper = twint.Config()

        # Configure parameters
        scraper.Pandas = True  # save as pandas object
        scraper.Lang = "en"
        scraper.Since = start_date
        scraper.Until = end_date
        scraper.Search = hashtag  # query keywords

        # Run
        twint.run.Search(scraper)

        # Save into csv
        tweets_df = twint.storage.panda.Tweets_df
        tweets_df.to_csv(f'{end_date}_new.csv', index=False)

        # Update LASTUPDATE file
        text_file = open("./LASTUPDATE.txt", "w")  # override file if exist & write file if not exist
        write_text = text_file.write(end_date)
        text_file.close()

        # Update log
        add_log(msg=f"Scraped and saved data as {end_date}_new.csv")

    except FileNotFoundError as e:
        add_log(msg=f"{e}.Please fix")
