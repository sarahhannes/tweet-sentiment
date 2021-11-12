# -*- coding: utf-8 -*-
"""Clean and predict sentiment polarity of scraped Twitter data.

Usage
-----
To be used as part of scheduled Continuous Deployment workflow.
"""

from io import BytesIO
import os
import pickle
import re
import requests

from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import BernoulliNB
import sklearn
from nltk.stem import WordNetLemmatizer
import nltk
import fasttext  # Package for Pre-trained Language Detection Model
import gdown  # Package to download files form google drive
import pandas as pd
import mlflow.sklearn
import mlflow.pyfunc
import mlflow

from text_preprocessing import remove_link_lemma


nltk.download('wordnet')
wnl = WordNetLemmatizer()

def get_stats(tweet):
    """
    input: string
    Extracts and returns Replies, Retweets, Likes from scraped tweet.
    Also returns tweet text stripped of redundant characters.
    output: Pandas series
    """
    pattern = "\|.([0-9]+).*([0-9]+).*([0-9]+).*$"
    tweet_split = re.split(pattern, tweet)
    tweet_cleaned = tweet_split[0].strip()
    try:
        replies = int(tweet_split[1])
        retweets = int(tweet_split[2])
        likes = int(tweet_split[3])
    except (TypeError, IndexError) as e:  # No tweet stats included in scraped tweet
        replies = 0
        retweets = 0
        likes = 0
    return [tweet_cleaned, replies, retweets, likes]


def get_hashtags(tweet):
    """
    input: string
    Get list of cleaned hashtags (removed punctuations) for each tweets.
    output: list
    """
    return list(set([re.sub(r'[^0-9a-zA-Z]', '', tweet) for tweet in tweet.split() if tweet.startswith("#")]))


if __name__ == "__main__":

    ### LOAD ###
    ## Load scraped data (using width delimiter)
    NEWDATA_URL = 'https://raw.githubusercontent.com/SarahHannes/tweet-sentiment/dev/new_data_appended.txt'
    widths = [20, 10, 10, 6, 500]
    df = pd.read_fwf(NEWDATA_URL, header=None, widths=widths, encoding="utf8")

    ## Load sentiment analysis model
    MODEL_FILEID = '1ydeM6Tiamck5sF8oMDThZIRb0xQu7Nqd'
    MODEL_URL = 'https://drive.google.com/uc?id=' + MODEL_FILEID
    MODEL_OUTPUT = 'model.pickle'
    # Download model from google drive
    gdown.download(MODEL_URL, MODEL_OUTPUT, quiet=False)
    # Load model to session
    infile = open(MODEL_OUTPUT, 'rb')
    model = pickle.load(infile)
    infile.close()

    ## Load fastText pre-trained language detection model
    FASTTEXT_FILE_ID = '12JgI89VS7Pkn2akgAs7ZsPFni5HtLvxs'
    FASTTEXT_URL = 'https://drive.google.com/uc?id=' + FASTTEXT_FILE_ID
    FASTTEXT_OUTPUT = 'lid.176.ftz'
    # Download model from google drive
    gdown.download(FASTTEXT_URL, FASTTEXT_OUTPUT, quiet=False)
    # Load model to session
    fmodel = fasttext.load_model(FASTTEXT_OUTPUT)

    ### CLEAN ###
    # 1: Rename columns
    df = df.rename(columns={0: 'tweet_id', 1: 'date', 2: 'time', 3: 'timezone', 4: 'tweet'})

    # 2: Extract username
    df['username'] = df['tweet'].apply(lambda x: re.match('\<(.*?)\>', x).group()[1:-1])

    # 3: Removed <username> from tweets
    df['tweet_cleaned'] = df['tweet'].apply(lambda x: re.sub(re.match('\<(.*?)\>', x).group(), '', x))

    # 4: Remove unused columns
    df = df.drop(columns=['timezone', 'tweet'])

    # 5: Get tweet language
    df['language'] = df['tweet_cleaned'].apply(lambda x: fmodel.predict(x)[0][0][-2:])

    # 6: Remove duplicated rows (keep last row because of the more updated stats = likes, retweet, replies)
    df = df.drop_duplicates(subset=['tweet_id', 'username'], keep='last')

    # 7: Remove non English tweets
    df = df.drop(df[df['language'] != 'en'].index)

    # 8: Get tweet links
    df['link'] = df.apply(lambda row: f'https://twitter.com/{row["username"]}/status/{row["tweet_id"]}', axis=1)

    # 9: Get stats
    df[['tweet', 'replies', 'retweets', 'likes']] = df['tweet_cleaned'].apply(lambda x: get_stats(x)).to_list()

    # 10: Get hashtags
    df['hashtags'] = df['tweet'].apply(lambda x: get_hashtags(x))

    # 11: Get tweet polarity
    df['polarity'] = model.predict(df['tweet'])

    # 12: Remove redundant columns and reset index
    df = df.drop(columns=['tweet_cleaned', 'language']).reset_index(drop=True)

    # 13: Convert to correct date & time object
    df['date'] = df['date'].apply(lambda x: pd.to_datetime(x).date())
    df['time'] = df['time'].apply(lambda x: pd.to_datetime(x).time())

    df.to_csv('new_data_cleaned.csv', index=False)
