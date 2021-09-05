"""
Scrape twitter hourly for keyword specified in `hashtag`
"""

# Import libraries
from datetime import datetime, timedelta
import twint
import nest_asyncio
nest_asyncio.apply()

# Scrape
now = datetime.utcnow()
before = now - timedelta(minutes=60)

# Initialize configuration
d = twint.Config()
d.Lang = 'en'

d.Since = before.strftime('%Y-%m-%d %H:%M:%S')
d.Until = now.strftime('%Y-%m-%d %H:%M:%S')

d.Search = "#dhl"  # what to query

# Run
twint.run.Search(d)

# Save into csv
df = twint.storage.panda.Tweets_df

# Write to file (if file not found, otherwise, append)
df.to_csv("raw_data.txt", sep="\t", mode='a', header=False,  index=False)
