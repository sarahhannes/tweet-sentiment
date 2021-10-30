# -*- coding: utf-8 -*-
"""Train and track model on MLFlow.

Usage
-----
To be used as part of scheduled Continuous Training workflow.
"""

import os
import pickle
import re
import json
from datetime import datetime as dt
from datetime import date, timedelta
import datetime

from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_validate
from sklearn.model_selection import ParameterSampler
from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import BernoulliNB
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import matthews_corrcoef
from sklearn.metrics import make_scorer
from imblearn.over_sampling import SMOTE
from textblob import TextBlob
from textblob.sentiments import NaiveBayesAnalyzer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from nltk.stem import WordNetLemmatizer
from google.oauth2 import service_account
from google.api_core.client_options import ClientOptions
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
import mlflow
import mlflow.sklearn
import nltk
import pandas as pd
import numpy as np
import gspread
import gdown
import requests
import google.cloud.storage

from app import load_data_gdrive, load_google_worksheet
from text_preprocessing import remove_link_lemma


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


def load_data(private_key_id, private_key, client_id, sheet_url):
    """
    Load data stored in Google Drive and user input data stored in Googlesheet

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
    df : pandas.core.frame.DataFrame
        Dataframe containing all scraped and previously cleaned data.
    df_googlesheet : pandas.core.frame.DataFrame
        Dataframe containing all rows from google worksheet returned by app.load_google_worksheet().

    """
    # Load data
    data_file_id = '1XiABfco1-NpSwSjl32BAUS_HqPrBFYzD'  # File ID for Tweet data stored in Google Drive
    # Load all scraped data
    df = load_data_gdrive(data_file_id)[['tweet']]
    # Load data from user-validation google sheet (collected from streamlit app)
    df_googlesheet = load_google_worksheet_from_info(private_key_id, private_key, client_id, sheet_url)
    # Remove duplicates
    df_googlesheet = df_googlesheet.drop_duplicates(subset=['tweet', 'polarity'])
    return df, df_googlesheet


def preprocess_data(df, df_googlesheet):
    """
    Preprocess data prior to training by performing:
        - Classification using TextBlob and VaderSentiment to obtain class label
        - Class label consolidation
        - Removing 'neutral' polarity
        - Removing unused columns

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Dataframe containing all scraped and previously cleaned data.
    df_googlesheet : pandas.core.frame.DataFrame
        Dataframe containing all rows from google worksheet returned by app.load_google_worksheet().

    Returns
    -------
    df_final : pandas.core.frame.DataFrame
        Preprocessed data.

    """
    # Amend polarity column (0 = negative, 1 = positive)
    # If original predicted polarity is positive, change it to 0 (negative)
    df_googlesheet['user_validated'] = df_googlesheet['polarity'].apply(lambda x: 0 if x == 'positive' else 1)

    # Keep only required columns
    df_googlesheet_final = df_googlesheet[['tweet', 'user_validated']]

    ## Classification using TextBlob sentiment
    # Get polarity score using TextBlob sentiment
    df['textblob_polarity'] = df['tweet'].apply(lambda x: TextBlob(x).sentiment.polarity)

    # Extract polarity from scores
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

    # Create a new column in the original df and use np.select to assign values to it using the lists as arguments
    df['textblob'] = np.select(textblob_conditions, textblob_values)

    ## Classification using Vader sentiment
    # Initialize Vader sentiment
    vader = SentimentIntensityAnalyzer()

    # Get polarity scores using VaderSentiment
    df['vader_polarity'] = df['tweet'].apply(lambda x: vader.polarity_scores(x)['compound'])

    # Extract polarity from scores
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

    # Create a new column in the original df and use np.select to assign values to it using the lists as arguments
    df['vader'] = np.select(vader_conditions, vader_values)

    ## Class label consolidation
    # Keep only required cols & remove rows where vader and textblob gives different polarity
    df2 = df[df['vader'] == df['textblob']][['tweet', 'textblob', 'vader']]

    # Remove rows with neutral polarity
    df2 = df2[df2['vader'] != -1]

    # Add data from googlesheet
    df_final = pd.concat([df2, df_googlesheet_final])

    # Consolidate polarity column
    # If value from textblob col is null, get value from user_validated, otherwise get value from textblob col
    df_final['polarity'] = np.where(pd.isna(df_final['textblob']), df_final['user_validated'], df_final['textblob'])

    # Keep only required columns
    df_final = df_final[['tweet', 'polarity']]

    return df_final


def resample_data(k_neighbors):
    """
    Resamples data using SMOTE and split resampled data into training and testing sets.

    Parameters
    ----------
    k_neighbors : int
        Value to set for SMOTE() k_neigbors parameters.

    Returns
    -------
    X_train : scipy.sparse.csr.csr_matrix
        Split array containing training set.
    X_test : scipy.sparse.csr.csr_matrix
        Split array containing test set.
    y_train : pandas.core.series.Series
        Split array containing class label of training set.
    y_test : pandas.core.series.Series
        Split array containing class label of testing set.
    tfidf : sklearn.feature_extraction.text.TfidfVectorizer
        Initialized vectorizer with custom preprocessor.

    """
    # Select X and Y variable
    # (Since both vader and textblob now have the same polarity, either one is choosen as Y variable)
    X = df_final['tweet']
    y = df_final['polarity']

    # Vectorize using bigram tfidf
    tfidf = TfidfVectorizer(lowercase=False, ngram_range=(2, 2), preprocessor=remove_link_lemma)

    # Fit and transform
    Xtfidf = tfidf.fit_transform(X)

    # Create artificial datapoints for minority class label using smote
    smote = SMOTE(random_state=1, k_neighbors=k_neighbors)
    X_smote, y_smote = smote.fit_resample(Xtfidf, y)

    # Split Train and Test set
    X_train, X_test, y_train, y_test = train_test_split(X_smote, y_smote, test_size=0.2, random_state=1)

    return X_train, X_test, y_train, y_test, tfidf


if __name__ == '__main__':

    # Get secrets from env
    private_key_id = os.environ['GSA_PRIVATE_KEY_ID']
    private_key = os.environ['GSA_PRIVATE_KEY'].replace('\\n', '\n')
    client_id = os.environ['GSA_CLIENT_ID']
    sheet_url = os.environ["GSA_PRIVATE_GSHEETS_URL"]

    # Set mlflow tracking config
    experiment_name = "SentimentAnalysis"
    tracking_uri = os.environ.get('MLFLOW_TRACKING_URI')

    # Set experiment name
    mlflow.set_experiment(experiment_name)
    experiment = mlflow.get_experiment_by_name(experiment_name)

    # Set path to log
    mlflow.set_tracking_uri(tracking_uri)

    # Set metrics
    metric = {'matthews_corrcoef': make_scorer(matthews_corrcoef),
              'accuracy': 'accuracy',
              'f1': 'f1',
              'precision': 'precision',
              'recall': 'recall',
              'neg_log_loss': 'neg_log_loss'}

    # Set hyperparams and params
    hyperparams = {'k_neighbors': range(1, 21),  # SMOTE
                   'alpha': range(0, 3)}

    params = {'cv_folds': 5,
              'n_iter': 6}

    param_list = list(ParameterSampler(hyperparams, n_iter=params['n_iter'], random_state=0))

    # Load data
    df, df_googlesheet = load_data(private_key_id, private_key, client_id, sheet_url)
    # Preprocess data
    df_final = preprocess_data(df, df_googlesheet)

    for run in range(params['n_iter']):
        run_hyperparams = param_list[run]

        with mlflow.start_run(experiment_id=experiment.experiment_id):

            # Resample data
            X_train, X_test, y_train, y_test, tfidf = resample_data(run_hyperparams['k_neighbors'])

            # Build pipeline
            model = Pipeline([('nb', BernoulliNB(alpha=run_hyperparams['alpha']))])

            # Train and score
            model.fit(X_train, y_train)
            model.score(X_test, y_test)

            # Assemble final pipe
            pipe_final = Pipeline([('vectorizer', tfidf),
                                   ('nb', model.steps[0][1])])

            # Perform cross validation
            scores = cross_validate(model, X_train, y_train, scoring=metric)

            metrics_dict = {}
            for m in metric:
                metrics_dict[m] = np.mean(scores['test_' + m])

            # Log model parameters
            mlflow.log_params(run_hyperparams)

            # Log model metrics
            mlflow.log_metrics(metrics_dict)

            # Log model and create version
            mlflow.sklearn.log_model(
                sk_model=pipe_final,
                artifact_path="model",
                registered_model_name="SentimentAnalysisClassifier")
