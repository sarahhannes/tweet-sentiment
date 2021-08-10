import twint
import nest_asyncio
import glob
import pandas as pd
from datetime import date, timedelta
from write_log import add_log

nest_asyncio.apply()


# Get last_update date
try:
    lastupdate_file = glob.glob('./LASTUPDATE.txt')[0]
    col_index = pd.read_csv(lastupdate_file).columns
    last_update = str(col_index.values[0])  # get last_update date as str
except IndexError as e:  # No LASTUPDATE file found, so set last_update as today()-1
    last_update = str(date.today()-timedelta(days=1))
    add_log(msg=f"LASTUPDATE.txt not found. Set start scrape date as {last_update}")

# if last_update == today
if last_update == str(date.today()):
    # update log
    add_log(msg="Scraped data is up to date. No action performed")

else:
    try:  # Scrape, save as csv, update LASTUPDATE, update log
        # Query parameters
        start_date = last_update  # last_update date
        end_date = str(date.today())  # today's date
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
        add_log(msg=f"{e}. Please fix")
