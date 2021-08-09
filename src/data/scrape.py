import twint
import nest_asyncio
import re
from pyprojroot import here

nest_asyncio.apply()

# print(here("./scrape_keyword.txt"))
# Extract scrape queries

#f = open("scrape_keyword.txt", "r")
#for line in f:
#    if "Start Date" in line:
#        start_date = re.findall(r"\d{4}-\d{2}-\d{2}", line)[0]
#    if "End Date" in line:
#        end_date = re.findall(r"\d{4}-\d{2}-\d{2}", line)[0]
#    if "Hashtag" in line:
#        hashtag = "#" + re.findall(r"[^Hashtag](\w+)", line)[0]
#f.close()

#filename = "data\\new\\new_" + "".join(re.findall(r"\d+", end_date)) + ".csv"

start_date = '2021-05-01'
end_date = '2021-05-02'
hashtag = '#dhl'

# Initialize configuration
scraper = twint.Config()

# Configuration parameters
scraper.Store_csv = True  # stores as csv
# TODO: Save to pandas instead of writing to csv
scraper.Pandas = True



# scraper.Output = filename  # name of the output file
scraper.Lang = "en"
scraper.Since = start_date
scraper.Until = end_date
scraper.Search = hashtag  # query keywords

# Run
twint.run.Search(scraper)
tweets_df = twint.storage.panda.Tweets_df

#print(tweets_df)
print('done scrapping')
# TODO: write last update (end_date). save as LASTUPDATE.txt
tweets_df.to_csv(f'/data/{end_date}_new.csv')
# TODO: create log file and a list of conditions to be logged upon scrapping
# TODO: append scraped data into /data/raw/raw.csv
