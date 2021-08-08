import re
import pandas as pd

import nest_asyncio
import twint

nest_asyncio.apply()

# Extract scrape queries
f = open("./src/data/scrape_keyword.txt", "r")
for line in f:
    if "Start Date" in line:
        start_date = re.findall(r"\d{4}-\d{2}-\d{2}", line)[0]
    if "End Date" in line:
        end_date = re.findall(r"\d{4}-\d{2}-\d{2}", line)[0]
    if "Hashtag" in line:
        hashtag = "#"+re.findall(r"[^Hashtag](\w+)", line)[0]
f.close()

filename = "/data/new/"+end_date+"_new.csv"

# Initialize configuration
scraper = twint.Config()

# Configuration parameters
scraper.Store_csv = True  # stores as csv
scraper.Output = filename  # name of the output file
scraper.Lang = "en"
scraper.Since = start_date
scraper.Until = end_date
scraper.Search = hashtag  # query keywords

# Run
twint.run.Search(scraper)

# TODO: write last update (end_date). save as LASTUPDATE.txt

# TODO: create log file and a list of conditions to be logged upon scrapping
# TODO: append scraped data into /data/raw/raw.csv 