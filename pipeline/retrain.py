# -*- coding: utf-8 -*-

"""Retrains and updates exisiting sentiment analysis model.

High-Level Overview
-----
1. Load data
2. Polarity classification using TextBlob and VaderSentiment as class label
3. Class label consolidation
4. Resample data (SMOTE oversampling approach)
5. Train model
6. Pickle model
7. Update model.pickle in Google Drive

Usage
-----
To be used as part of scheduled Continuous Improvement workflow.

"""

import os
import pickle
import re

from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import BernoulliNB
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from imblearn.over_sampling import SMOTE
from textblob import TextBlob
from textblob.sentiments import NaiveBayesAnalyzer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from nltk.stem import WordNetLemmatizer
import nltk
import gspread
import pandas as pd
import numpy as np

from app import load_data_gdrive, load_google_worksheet
from text_preprocessing import remove_link_lemma

nltk.download('wordnet')
wnl = WordNetLemmatizer()


def load_google_worksheet_from_info(private_key_id, private_key, client_id, sheet_url):
    """
    This function directly:
        - Obtains credentials from Github secrets
        - Builds credentials object to connect with Googlesheet containing collected user input via streamlit app
        - Accesses the Googlesheet
        - Loads all data from the Googlesheet into pandas
    
    See app.build_connection() for more info.
    
    Parameters
    ----------
    private_key_id : str
        Required credential to access Google Drive. Stored in Github secrets.
    private_key : str
        Required credential to access Google Drive. Stored in Github secrets.
    client_id : str
        Required credential to access Google Drive. Stored in Github secrets.
    sheet_url : str
        Link to Google sheet. Stored in Github secrets.

    Returns
    -------
    pandas.core.frame.DataFrame
        Dataframe containing all rows from google worksheet returned by app.load_google_worksheet().

    """
    info = {
      'type': "service_account",
      'project_id': "quixotic-card-325716",
      'private_key_id': private_key_id,
      'private_key': private_key,
      'client_email': "tweet-sentiment@quixotic-card-325716.iam.gserviceaccount.com",
      'client_id': client_id,
      'auth_uri': "https://accounts.google.com/o/oauth2/auth",
      'token_uri': "https://oauth2.googleapis.com/token",
      'auth_provider_x509_cert_url': "https://www.googleapis.com/oauth2/v1/certs",
      'client_x509_cert_url': "https://www.googleapis.com/robot/v1/metadata/x509/tweet-sentiment%40quixotic-card-325716.iam.gserviceaccount.com"
      }
    
    # Create credential object
    credentials = service_account.Credentials.from_service_account_info(info)
    scoped_credentials = credentials.with_scopes(
        ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive'])
  
    # Initialize gspread Client instance
    gc = gspread.Client(auth=scoped_credentials)
    gc.session = AuthorizedSession(scoped_credentials)
  
    # Get Googlesheet url from stored github secrets
    sheet_url = sheet_url
  
    # Access the Googlesheet via shared link
    sheet = gc.open_by_url(sheet_url)
  
    # Return dataframe containing data in 1st worksheet of the accessed Googlesheet
    return load_google_worksheet(sheet.get_worksheet(0))


if __name__ == "__main__":

    private_key_id = os.environ['GSA_PRIVATE_KEY_ID']
    private_key = os.environ['GSA_PRIVATE_KEY']
    client_id = os.environ['GSA_CLIENT_ID']
    sheet_url = os.environ["GSA_PRIVATE_GSHEETS_URL"]
    
    # 1: Load data
    # File ID for Tweet data stored in Google Drive
    data_file_id = '1XiABfco1-NpSwSjl32BAUS_HqPrBFYzD'
    # Load all scraped data
    df = load_data_gdrive(data_file_id)[['tweet']]
    # Load data from user-validation google sheet (collected from streamlit app)
    df_googlesheet = load_google_worksheet_from_info(private_key_id, private_key, client_id, sheet_url)
    
    # 2: Preprocess google sheet
    # 2a: Remove duplicates
    df_googlesheet = df_googlesheet.drop_duplicates(subset=['tweet', 'polarity'])
    
    # 2b: Amend polarity column (0 = negative, 1 = positive)
    # If original predicted polarity is positive, change it to 0 (negative)
    df_googlesheet['user_validated'] = df_googlesheet['polarity'].apply(lambda x: 0 if x == 'positive' else 1)
    
    # 2c: Keep only required columns
    df_googlesheet_final = df_googlesheet[['tweet', 'user_validated']]
    
    # 3: Classification using TextBlob
    # 3a: Get polarity score using TextBlob sentiment
    df['textblob_polarity'] = df['tweet'].apply(lambda x: TextBlob(x).sentiment.polarity)
    
    # 3b: Extract polarity from scores
    """
      negative sentiment: (polarity score < 0) and (polarity score >= -1)
      positive sentiment: (polarity score >= 0) and (polarity score <= 1)
    """
    # Create a list of polarity conditions
    textblob_conditions = [
        (df['textblob_polarity'] < 0) & (df['textblob_polarity'][0] >= -1),
        (df['textblob_polarity'] == 0),
        (df['textblob_polarity'][0] >= 0) & (df['textblob_polarity'][0] <= 1)
        ]
    
    # Create a list of values to assign to each polarity conditions (0 = negative, -1 = neutral, 1 = positive)
    textblob_values = [0, -1, 1]
    
    # 3c: Create a new column in the original df and use np.select to assign values to it using the lists as arguments
    df['textblob'] = np.select(textblob_conditions, textblob_values)
    
    # 4: Classification using VaderSetiment
    # 4a: Initialize Vader sentiment
    vader = SentimentIntensityAnalyzer()
    
    # 4b: Get polarity scores using VaderSentiment
    df['vader_polarity'] = df['tweet'].apply(lambda x: vader.polarity_scores(x)['compound'])
    
    # 4c: Extract polarity from scores
    """
      negative sentiment: compound score <= -0.05
      neutral sentiment: (compound score > -0.05) and (compound score < 0.05)
      positive sentiment: compound score >= 0.05
    """
    # Create a list of polarity conditions
    vader_conditions = [
        (df['vader_polarity'] <= -0.05),
        (df['vader_polarity'] > -0.05) & (df['vader_polarity'] < 0.05),
        (df['vader_polarity'] >= 0.05)
        ]
    
    # Create a list of values to assign to each polarity conditions (0 = negative, -1 = neutral, 1 = positive)
    vader_values = [0, -1, 1]
    
    # 4d: Create a new column in the original df and use np.select to assign values to it using the lists as arguments
    df['vader'] = np.select(vader_conditions, vader_values)
    
    # 5: Class label consolidation
    # 5a: Keep only required cols & remove rows where vader and textblob gives different polarity
    df2 = df[df['vader']==df['textblob']][['tweet', 'textblob', 'vader']]
    
    # 5b: Remove rows with neutral polarity
    df2 = df2[df2['vader']!=-1]
    
    # 5c: Add data from googlesheet
    df_final = pd.concat([df2, df_googlesheet_final])
    
    # 5d: Consolidate polarity column
    # If value from textblob col is null, get value from user_validated, otherwise get value from textblob col
    df_final['polarity'] = np.where(pd.isna(df_final['textblob']), df_final['user_validated'], df_final['textblob'])
    
    # 5e: Keep only required columns
    df_final = df_final[['tweet', 'polarity']]
    
    # 6: Resample data
    # 6a: Select X and Y variable (Since both vader and textblob now have the same polarity, either one is choosen as Y variable)
    X = df_final['tweet']
    y = df_final['polarity']
    
    # 6b: Vectorize using bigram tfidf
    tfidf = TfidfVectorizer(lowercase=False,ngram_range=(2,2), preprocessor = remove_link_lemma)
    
    # 6c: Fit and transform
    Xtfidf = tfidf.fit_transform(X)
    
    # 6d: Create artificial datapoints for minority class label using smote
    smote = SMOTE(random_state=1, k_neighbors=1)
    X_smote, y_smote = smote.fit_resample(Xtfidf, y)
    
    # 7: Split Train and Test set
    X_train, X_test, y_train, y_test = train_test_split(X_smote, y_smote, test_size=0.2, random_state=1)
    
    # 8: Retrain model
    # 8a: Create new pipeline using new BernoulliNB() model
    model_retrained_new = Pipeline([('nb', BernoulliNB()) # build model
                       ])
    
    # Retrain and get accuracy
    model_retrained_new.fit(X_train, y_train)
    model_retrained_new.score(X_test, y_test)
    
    # 9: Update model pickle
    pipe_final = Pipeline([
              ('vectorizer', tfidf),
              ('nb', model_retrained_new.steps[0][1]) # save the fitted model from previous pipe
                       ])
    
    # 10: Save built model
    path = './'
    pickle_save = open(path + 'model.pickle', 'wb')
    pickle.dump(pipe_final, pickle_save)
    pickle_save.close()
