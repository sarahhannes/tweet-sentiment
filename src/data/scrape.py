import twint
import nest_asyncio

nest_asyncio.apply()

start_date = '2021-05-01'
end_date = '2021-05-02'
hashtag = '#dhl'

# Initialize configuration
scraper = twint.Config()

# Configuration parameters
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


# Write last update (end_date). save as LASTUPDATE.txt
text_file = open("./LASTUPDATE.txt", "w") # overide file if exist & write file if not exist
write_text = text_file.write(end_date)
text_file.close()

# TODO: create log file and a list of conditions to be logged upon scrapping

