import twint
import nest_asyncio
nest_asyncio.apply()


start_date = "2021-05-01" # YYYY-MM-DD format
end_date = "2021-05-31" # YYYY-MM-DD format

# Initialize configuration
scraper = twint.Config()

# Configuration paramaters
scraper.Store_csv = True # stores as csv
scraper.Output = f'until{end_date}.csv' # name of the output file
scraper.Lang = 'en'

scraper.Since = start_date
scraper.Until = end_date
# TODO: extract query text from external file for easy application?
scraper.Search = '#dhl' # what to query

# Run
twint.run.Search(scraper)