# -*- coding: utf-8 -*-
"""Append newly scraped data to existing data stored in Google Drive.

Usage
-----
To be used as part of scheduled Continuous Deployment workflow.
"""

import pandas as pd
import gdown

if __name__ == "__main__":

    ## LOAD
    # Load new data
    NEWDATA_URL = 'https://raw.githubusercontent.com/SarahHannes/tweet-sentiment/dev/new_data_cleaned.csv'
    df_new = pd.read_csv(NEWDATA_URL)

    # Load existing data
    OLDDATA_FILE_ID = '1XiABfco1-NpSwSjl32BAUS_HqPrBFYzD'
    OLDDATA_URL = 'https://drive.google.com/uc?id=' + OLDDATA_FILE_ID
    OLDDATA_OUTPUT = 'data.txt'
    # Download model from google drive
    gdown.download(OLDDATA_URL, OLDDATA_OUTPUT, quiet=False)
    df_old = pd.read_csv('data.txt', sep='\t')

    ## TRANSFORM
    # Merge dataframes & remove duplicates
    df = pd.concat([df_old, df_new]).reset_index(drop=True).drop_duplicates(subset=['username', 'tweet'])

    ## SAVE
    df.to_csv('data.txt', sep='\t', index=False)
