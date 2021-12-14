from datetime import datetime as dt
from datetime import date, timedelta
import datetime
import os
import re

from altair import datum
from bokeh.models import ColumnDataSource, CustomJS
from bokeh.models import DataTable, TableColumn, HTMLTemplateFormatter, DateFormatter
from googleapiclient.discovery import build
from google.oauth2 import service_account
from gspread_pandas import Spread, Client
from streamlit_bokeh_events import streamlit_bokeh_events
from tzlocal import get_localzone
from wordcloud import WordCloud
import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
import streamlit as st
import gdown
import gspread


st.set_page_config(page_title='Twitter Watcher', layout='wide', page_icon='📮')


def get_weekstart(selected_date=dt.today()):
    """
    Returns Monday of the selected_date week

    Parameters
    ----------
    selected_date : datetime.date, optional
        Any date/ day of the week. The default is dt.today().

    Returns
    -------
    datetime.date
        Date of the Monday of week of selected_date.

    """
    return selected_date - timedelta(days=selected_date.weekday())


def load_data_gdrive(data_file_id):
    """
    Load data from Google Drive

    Parameters
    ----------
    data_file_id : str
        Unique file ID corresponding to stored Tweet data in Google Drive.

    Returns
    -------
    pandas.core.frame.DataFrame
        Cleaned pandas dataframe returned from clean_df() function.

    """
    data_url = 'https://drive.google.com/uc?id=' + data_file_id
    data_output = 'data.txt'
    
    # Download data from google drive
    gdown.download(data_url, data_output, quiet=True)
    
    df = pd.read_csv(data_output, sep='\t')
    return clean_df(df)


def clean_df(df):
    """
    Clean and pre-process dataframe by:
        - Transforming columns to appropriate format
        - Derive additional columns such as day_of_week from date

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Raw dataframe.

    Returns
    -------
    df : pandas.core.frame.DataFrame
        Preprocessed dataframe.

    """
    # Transform date column to pandas._libs.tslibs.timestamps.Timestamp format
    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')
    # Transform time column to datetime.time format
    df['time'] = pd.to_datetime(df['time'], format='%H:%M:%S').dt.time
    # Double check for NaT - if NaT, convert to 00:00:00
    for x in df['time'][pd.Series(df['time']).isna()].index:
        df.at[x, 'time'] = datetime.time(0,0,0)

    # Combine columns to get datetime
    df['datetime'] = df.apply(lambda row: datetime.datetime.combine(row['date'], row['time']), axis=1)
    # Get year
    df['year'] = df['date'].apply(lambda x: x.year)
    # Get month
    df['month'] = df['date'].apply(lambda x: x.month_name())
    # Get week number
    df['week'] = df['date'].dt.isocalendar().week
    # Get day of the week
    df['day_of_week'] = df['date'].apply(lambda x: x.day_name())
    # Get hour in 24h format
    df['hour'] = df['time'].apply(lambda x: x.hour)
    # Transform polarity column
    df['polarity'] = df['polarity'].apply(lambda x: 'positive' if x == 1 else 'negative')
    return df


def get_dhl_acc(df):
    """
    Extract list of Twitter account associated with DHL

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Tweets data.

    Returns
    -------
    dhl_acc : list
        List of Twitter account usernames associated with DHL.

    """
    dhl_acc = list(set(df['username'].str.extract('(.*DHL.*)', re.IGNORECASE)[0]))
    dhl_acc.remove(np.nan)
    return dhl_acc


def get_dhl_tweet(df, dhl_acc):
    """
    Get Tweets by DHL associated accounts

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Tweets data.
    dhl_acc : list
        List of Twitter account usernames associated with DHL.

    Returns
    -------
    pandas.core.frame.DataFrame
        Filtered dataframe containing only Tweets by DHL associated accounts.

    """
    return df[df['username'].isin(dhl_acc)].reset_index(drop=True)


def get_cust_tweet(df, dhl_acc):
    """
    Get Tweets by Twitter users

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Tweets data.
    dhl_acc : list
        List of Twitter account usernames associated with DHL.

    Returns
    -------
    pandas.core.frame.DataFrame
        Filtered dataframe by removing Tweets by DHL associated accounts.

    """
    return df[~df['username'].isin(dhl_acc)].reset_index(drop=True)


@st.cache(persist=True)
def hashtags_polarity(df, selected_week):
    """
    Get hashtags associated with Negative polarity and Positive polarity

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Dataframe containing only customer Tweets.
    selected_week : datetime.date
        Date provided by user input.

    Returns
    -------
    positive_words : str
        Words from Positive Tweets hashtags.
    negative_words : str
        Words from Negative Tweets hashtags.

    """
    # Sort df by datetime in descending order
    df.sort_values(by=['datetime'], ascending=False).reset_index(drop=True)

    # Unpack year, weeknum and day from selected date
    cw_year, cw_weeknum, cw_day = selected_week.isocalendar()

    # Slice df based on selected date and polarity, then save as new df
    positive_df = df.loc[(df['week'] == cw_weeknum) & (df['year'] == cw_year) & (df['polarity'] == 'positive')].copy()
    negative_df = df.loc[(df['week'] == cw_weeknum) & (df['year'] == cw_year) & (df['polarity'] == 'negative')].copy()

    # If either one is empty, get the most recent data
    if len(positive_df) == 0:
        # Get the second top week number
        top2_weeknum = df['week'].unique()[1]
        max_year = max(df['year'])

        # slice to get the most recent week -1, year
        positive_df = df.loc[
            (df['week'] == top2_weeknum) & (df['year'] == max_year) & (df['polarity'] == 'positive')].copy()

    if len(negative_df) == 0:
        # Get the second top week number
        top2_weeknum = df['week'].unique()[1]
        max_year = max(df['year'])

        # slice to get the most recent week -1, year
        negative_df = df.loc[
            (df['week'] == top2_weeknum) & (df['year'] == max_year) & (df['polarity'] == 'negative')].copy()

    # Combine hashtags into list of words
    positive_list = positive_df['hashtags'].apply(
        lambda x: "".join(x).replace("'", "").replace("[", "").replace("]", "").replace(",", "").split())
    negative_list = negative_df['hashtags'].apply(
        lambda x: "".join(x).replace("'", "").replace("[", "").replace("]", "").replace(",", "").split())

    # Join words
    positive_words = (' ').join([item for sublist in positive_list for item in sublist])
    negative_words = (' ').join([item for sublist in negative_list for item in sublist])

    # Placeholder to ensure no 0 len string
    positive_words += ' DHL'
    negative_words += ' DHL'
    return positive_words, negative_words


@st.cache(persist=True)
def get_kpi(weekly_data, selected_week):
    """
    Returns KPI value and delta for all 6 KPIs. If data is not available for
    selected_week, returns KPIs for the latest week available

    Parameters
    ----------
    weekly_data : pandas.core.frame.DataFrame
        Pivoted dataframe with sum aggregation for week, year index.
    selected_week : datetime.date
        Selected date from user input.

    Returns
    -------
    kpi_dict : dict
        Dictionary containing kpi_name: (current week's value, delta) for all 6 KPIs.
    warning : str
        String storing warning to display, if any.

    """
    
    # Reset index to perform transformation
    weekly_data2 = weekly_data.reset_index()
    
    # Change from str type -> int to enable slicing later
    weekly_data2['year'] = weekly_data2['year'].apply(lambda x: int(x[:-2]))
    weekly_data2['week'] = weekly_data2['week'].apply(lambda x: int(x))
    
    # Set back index to week, year
    weekly_data2 = weekly_data2.set_index(['week', 'year'])
    
    # Initialize empty dict to store KPI with format -> kpi_name: (current week value, delta)
    kpi_dict = {}

    try:
        current_week = selected_week
        previous_week = selected_week - timedelta(days=7)
        
        # Unpack year, weeknum and day from selected week and previous week
        cw_year, cw_weeknum, cw_day = current_week.isocalendar()
        pw_year, pw_weeknum, pw_day = previous_week.isocalendar()
        
        # For each KPI, get its current value and previous value, then save in kpi_dict
        for key, column_name in [('Positive Mentions', 'polarity_positive_mentions'),
                                 ('Negative Mentions', 'polarity_negative_mentions'),
                                 ('Retweets', 'retweets'),
                                 ('Replies', 'replies'),
                                 ('Likes', 'likes'),
                                 ('DHL Tweets', 'count_dhl_tweets')]:
            current_value = int(weekly_data2.at[(cw_weeknum, cw_year), column_name])
            prev_value = int(weekly_data2.at[(pw_weeknum, pw_year), column_name])
            kpi_dict[key] = (current_value, current_value - prev_value)

        warning = ""

    # If data does not exist, get the most recent KPI
    except KeyError as e:
        warning = f'Data is not available for week, year {e}. Showing the most recent KPI'
        weekly_data2 = weekly_data2.sort_index()  # sort index ascendingly
        (cw_weeknum, cw_year), (pw_weeknum, pw_year) = weekly_data2.index.take([-1, -2])  # get the 2 latest weeknum, year available

        for key, column_name in [('Positive Mentions', 'polarity_positive_mentions'),
                                 ('Negative Mentions', 'polarity_negative_mentions'),
                                 ('Retweets', 'retweets'),
                                 ('Replies', 'replies'),
                                 ('Likes', 'likes'),
                                 ('DHL Tweets', 'count_dhl_tweets')]:
            current_value = int(weekly_data2.at[(cw_weeknum, cw_year), column_name])
            prev_value = int(weekly_data2.at[(pw_weeknum, pw_year), column_name])
            kpi_dict[key] = (current_value, current_value - prev_value)

    return kpi_dict, warning


def get_datatable(df, selected_week):
    """
    Slice to obtain only data for selected_week

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Dataframe containing data to be sliced.
    selected_week : datetime.date
        Date from user input.

    Returns
    -------
    pandas.core.frame.DataFrame
        Sliced dataframe sorted in descenging order by datetime column.

    """
    week_start = selected_week
    week_end = selected_week + timedelta(days=7)

    # Sort df by datetime in descending order
    df = df.sort_values(by=['datetime'], ascending=False).reset_index(drop=True)

    # A workaround to ensure that time is always rendered in correct format
    df['time'] = df['time'].apply(lambda x: str(x))

    # Slice df to get only data for selected week
    filtered_df = df[
        (df['date'] >= np.datetime64(week_start)) & (df['date'] <= np.datetime64(week_end))].copy().reset_index()

    # Exception catching: If sliced df is empty, get the latest week available
    if len(filtered_df) == 0:
        week_end = max(df['date'])
        week_start = week_end - timedelta(days=7)

        filtered_df = df[
            (df['date'] >= np.datetime64(week_start)) & (df['date'] <= np.datetime64(week_end))].copy().reset_index()

    return filtered_df[['datetime', 'date', 'time', 'polarity', 'tweet', 'link']].sort_values(by=['datetime'], ascending=False).reset_index(drop=True)


def update_datatable(cust_tweets, selected_week, choice):
    """
    Slice to obtain only data for selected_week and update value in session_state.
    If `choice` of page navigation is Data, update st.session_state['datatable'] with 7 days latest data;
    Else, update session_state object with data on `selected_week` only.

    Parameters
    ----------
    cust_tweets : pandas.core.frame.DataFrame
        Dataframe containing data to be sliced.
    selected_week : datetime.date
        Date from user input.
    choice : str
        Name of page user wish to navigate to.

    Returns
    -------
    None.

    """
    if choice == 'Data':
        weekstart = selected_week - timedelta(days=7)
        st.session_state['datatable'] = get_datatable(cust_tweets, weekstart)
    else:
        st.session_state['datatable'] = get_datatable(cust_tweets, selected_week)


def load_google_worksheet(worksheet):
    """
    Get all rows from connected google worksheet

    Parameters
    ----------
    worksheet : gspread.models.Worksheet
        Loaded worksheet which contains user input.

    Returns
    -------
    pandas.core.frame.DataFrame
        Dataframe containing all rows from google worksheet.

    """
    
    return pd.DataFrame(worksheet.get_all_records())


def update_google_worksheet(worksheet, df):
    """
    Update new user input from df to connected worksheet

    Parameters
    ----------
    worksheet : gspread.models.Worksheet
        Connected worksheet which contains user input.
    df : pandas.core.frame.DataFrame
        Dataframe to write to worksheet.

    Returns
    -------
    None.

    """
    # Get column names
    column_name = df.columns.values.tolist()
    # Get value to append to worksheet
    row_value = df.values.tolist()
    # Update worksheet
    worksheet.update([column_name] + row_value)


def build_connection():
    """
    Initialize credentials object and drive_service object to interact with
    Google Drive API.

    ref: https://google-auth.readthedocs.io/en/master/_modules/google/oauth2/service_account.html#Credentials.from_service_account_info
    Info argument in credentials object is a .toml file stored in streamlit.io.
    Note that credentials object is initialized in a similar fashion to retrain.load_google_worksheet_from_info().
    However, one stark differences is that the info argument here is structured in .toml file (saved in streamlit.io);
    while the latter's info argument is a constructed dict object with some of its values saved in Github secrets.
    This is because github secrets does not allow storage of any structured file format, therefore the workaround.

    Since app.py will be run entirely from streamlit.io, there is no need to store the .toml file in Github secrets.

    Returns
    -------
    credentials : google.oauth2.service_account.Credentials
        Credentials object for Google service account built using credentials
        obtained from GCP > IAM & Admin > Service Accounts > KEYS.
    drive_service : googleapiclient.discovery.Resource
        Initialized Resource to interact with Google Drive API.
        Ref: https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.discovery-module.html

    """
    # Create a connection object
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    drive_service = build('drive', 'v3', credentials=credentials)
    
    return credentials, drive_service


def get_modified_time(file_id, drive_service, server_tz, local_tz):
    """
    Get latest modified time from file stored in Google Drive folder

    Parameters
    ----------
    file_id : str
        Unique ID of file stored in Google Drive.
    drive_service : googleapiclient.discovery.Resource
        Initialized Resource to interact with Google Drive API.
    server_tz : pytz.tzfile.Etc/UTC
        timezone information for server location.
    local_tz : str
        Region for user timezone eg "Asia/Kuala_Lumpur".

    Returns
    -------
    str
        Description of last modified time.

    """
    metadata = drive_service.files().get(fileId=file_id, fields='modifiedTime').execute()
    mtime = pd.to_datetime(metadata['modifiedTime'], format="%Y-%m-%d %H:%M").tz_convert(server_tz).tz_convert(local_tz)
    return f'Last Updated at {mtime.year}-{mtime.month}-{mtime.day} {mtime.hour}:{mtime.minute}'


def connect_googlesheet(googlesheet_name, credentials):
    """
    Connect to existing Google Sheet

    Parameters
    ----------
    googlesheet_name : str
        Name of Private Google Sheet accessible by created Google service account.
    credentials : google.oauth2.service_account.Credentials
        Credentials object for Google service account built using credentials
        obtained from GCP > IAM & Admin > Service Accounts > KEYS.

    Returns
    -------
    worksheet : gspread.models.Worksheet
        Connected Google worksheet.
    spread : gspread_pandas.spread.Spread
        Connected Google Spreadsheet.

    """
    # Get google sheet url from secrets
    sheet_url = st.secrets["private_gsheets_url"]

    # Initialize a Client instance and authorize to access spreadsheets via Google Sheets API (via OAuth2 credentials)
    # ref: https://docs.gspread.org/en/latest/api.html#gspread.authorize
    gc = gspread.authorize(credentials)

    # Open the google sheet
    sh = gc.open_by_url(sheet_url)

    # Open the worksheet
    worksheet = sh.worksheet(title=googlesheet_name)
    
    # Create an instance of Client class to comunicate with Google API
    # ref: https://gspread-pandas.readthedocs.io/en/latest/gspread_pandas.html#gspread_pandas.client.Client
    client = Client(creds=credentials)

    # Create an instance of Spread class to interact with Google spreadsheet using Pandas
    # ref: https://gspread-pandas.readthedocs.io/en/latest/gspread_pandas.html#gspread_pandas.spread.Spread
    spread = Spread(spread=sheet_url, client=client)
    return worksheet, spread


def update_googlesheet_gspread_pandas(spread, googlesheet_name, df):
    """
    Updates data in connected Google Spreadsheet

    Parameters
    ----------
    spread : gspread_pandas.spread.Spread
        Connected Google Spreadsheet.
    googlesheet_name : str
        Name of Google Worksheet.
    df : pandas.core.frame.DataFrame
        Dataframe to update to Google Worksheet.

    Returns
    -------
    None.

    """
    col = ['datetime', 'tweet', 'polarity', 'user_input_timestamp']
    spread.df_to_sheet(df[col], sheet=googlesheet_name, index=False)


def polarity_formatter(my_col):
    """
    Format polarity column to highlight row based on polarity.
    Rows for negative polarity is highlighted in red, and rows for positive
    polarity is highlighted in green

    Parameters
    ----------
    my_col : pandas.core.series.Series
        Column to be formatted.

    Returns
    -------
    bokeh.models.widgets.tables.HTMLTemplateFormatter
        HTML Template Formatter with user-defined template.

    """
    template = """
        <div style="background:<%= 
            (function colorfromint(){
                if(result_col == 'positive')
                {return('#84ddb4')}
                else if (result_col == 'negative')
                    {return('#e74d3c')}
                }()) %>; 
            color: white"> 
            <p style="text-align:center;">
            <%= value %></p>
        </div>
    """.replace('result_col', my_col)
    return HTMLTemplateFormatter(template=template)


@st.cache
def convert_df(df):
    """
    Convert pandas dataframe into csv file for user to download

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Dataframe to converted to csv to.

    Returns
    -------
    NoneType
        Function to convert pandas dataframe to csv file.

    """
    return df.to_csv().encode('utf-8')


def get_agg_data(cust_tweets, dhl_tweets):
    """
    Aggregate Tweets data into multiindexed dataframe (datatime, week, year).
    Aggregation function used is summation.

    Parameters
    ----------
    cust_tweets : pandas.core.frame.DataFrame
        Dataframe containing Tweets from customers.
    dhl_tweets : pandas.core.frame.DataFrame
        Dataframe containing Tweets from DHL associated accounts.

    Returns
    -------
    pandas.core.frame.DataFrame
        Pivoted multiindexed pandas dataframe aggregated using summation.

    """
    # Get polarity data from cust_tweets
    # Get one-hot encoded columns for 'polarity'
    sum_polarity = pd.concat([pd.get_dummies(cust_tweets[['datetime', 'year', 'polarity']]), cust_tweets[['week']]], axis=1).add_suffix('_mentions')
    
    # Add count for each tweets
    sum_polarity['count_cust_tweets'] = 1
    
    # Ensure that columns exist
    if 'polarity_positive_mentions' not in sum_polarity.columns:
        sum_polarity['polarity_positive_mentions'] = sum_polarity['polarity_negative_mentions'].apply(lambda x: 0 if x==1 else np.nan)
    if 'polarity_negative_mentions' not in sum_polarity.columns:
        sum_polarity['polarity_negative_mentions'] = sum_polarity['polarity_positive_mentions'].apply(lambda x: 0 if x==1 else np.nan)
    
    # Get engagement data from dhl_tweets
    # Slice dataframe to get only engagement details
    sum_engagement = dhl_tweets[['datetime', 'week', 'year', 'replies', 'retweets', 'likes']].copy()
    # Add count for each tweets
    sum_engagement['count_dhl_tweets'] = 1
    
    # Append both dfs
    sum_df = sum_engagement.append(sum_polarity, sort=False)
    # if value is na, copy 'week_mentions'
    sum_df['week'] = sum_df.apply(lambda row: np.where(pd.isna(row['week']), row['week_mentions'], row['week']), axis=1)
    # if value is na, copy 'year_mentions'
    sum_df['year'] = sum_df.apply(lambda row: np.where(pd.isna(row['year']), row['year_mentions'], row['year']), axis=1)
    sum_df['datetime'] = sum_df.apply(lambda row: np.where(pd.isna(row['datetime']), row['datetime_mentions'], row['datetime']), axis=1)
    # reset index and drop original
    sum_df = sum_df.reset_index(drop=True)
    # change unhashable np.array of dtype=object to dtype=np.int
    sum_df['datetime'] = sum_df['datetime'].apply(lambda x: x.astype(str))
    sum_df['week'] = sum_df['week'].apply(lambda x: x.astype(str))
    sum_df['year'] = sum_df['year'].apply(lambda x: x.astype(str))

    return pd.pivot_table(sum_df, values=['replies', 'retweets', 'likes', 'count_dhl_tweets', 'polarity_negative_mentions', 'polarity_positive_mentions', 'count_cust_tweets'], index=['datetime', 'week', 'year'], aggfunc=np.sum, fill_value=0)


def plot_custom_graph(df, x, y, chart_type, agg_type):
    """
    Plot altair chart from user input

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Pivoted (datetime, week, year) multiindexed dataframe using sum aggregation function.
    x : str
        X axis name from user input.
    y : list
        List of column names from user input.
    chart_type : str
        Name of chart type from user input.
    agg_type : str
        String depicting data aggregation type from user input.

    Returns
    -------
    altair.vegalite.v4.api.Chart
        Rendered chart.

    """
    width = 800
    
    x_dict = {
        'Hours of the day': 'hours(datetime):T',
        'Day of the week': 'day(datetime):O',
        'Day of the month': 'date(datetime):O',
        'Week': 'week:Q',
        'Date': 'monthdate(datetime):O',
        'Month': 'month(datetime):O',
        'Quarter': 'quarter(datetime):O',
        'Year': 'year(datetime):O'
    }
    
    agg_type_dict = {
        'Total number of Tweets': 'sum(value):Q',
        'Average number of Tweets': 'average(value):Q',
        'Min number of Tweets': 'min(value):Q',
        'Max number of Tweets': 'max(value):Q'
    }

    if chart_type == 'Scatter':
        return alt.Chart(
            data = df,
            width = width
        ).transform_fold(
            y
        ).mark_circle().encode(
            alt.X(x_dict[x], title=x),
            alt.Y(agg_type_dict[agg_type], title='value'),
            color='key:N',
            tooltip = [alt.Tooltip(x_dict[x]), alt.Tooltip('key:N'), alt.Tooltip(agg_type_dict[agg_type])]
        ).configure_mark(
            strokeWidth=10
        ).interactive()
    
    elif chart_type == 'Line':
        return alt.Chart(
            data = df,
            width = width
        ).transform_fold(
            y
        ).mark_line().encode(
            alt.X(x_dict[x], title=x),
            alt.Y(agg_type_dict[agg_type]),
            color='key:N',
            tooltip = [alt.Tooltip(x_dict[x]), alt.Tooltip('key:N'), alt.Tooltip(agg_type_dict[agg_type])]
        ).configure_mark(
            strokeWidth=3
        ).interactive()
    
    elif chart_type == 'Area':
        return alt.Chart(
            data = df,
            width = width
        ).transform_fold(
            y
        ).mark_area().encode(
            alt.X(x_dict[x], title=x),
            alt.Y(agg_type_dict[agg_type]),
            color='key:N',
            tooltip = [alt.Tooltip(x_dict[x]), alt.Tooltip('key:N'), alt.Tooltip(agg_type_dict[agg_type])]
        ).configure_mark(
            strokeWidth=10
        ).interactive()
    
    elif chart_type == 'Bar':
        return alt.Chart(
            data = df,
            width = width
        ).transform_fold(
            y
        ).mark_bar().encode(
            alt.X(x_dict[x], title=x),
            alt.Y(agg_type_dict[agg_type]),
            color='key:N',
            tooltip = [alt.Tooltip(x_dict[x]), alt.Tooltip('key:N'), alt.Tooltip(agg_type_dict[agg_type])]
        ).configure_mark(
            strokeWidth=10
        ).interactive()
    
    elif chart_type == 'Heatmap':
        return alt.Chart(df).transform_fold(y).mark_rect().encode(
            alt.X('hours(datetime):O', title='Hours of the day'),
            alt.Y('day(datetime):O', title='Day'),
            alt.Row('key:O', title=''),
            color=agg_type_dict[agg_type],
            tooltip = [alt.Tooltip('hours(datetime):O'),
                       alt.Tooltip('day(datetime):O'),
                       alt.Tooltip('key:N'),
                       alt.Tooltip(agg_type_dict[agg_type])]
        ).properties(
            width=610,
            height=150
        )

def agg_by_period(agg_df, groupby_var):
    """
    Aggregate numerical data by `groupby_var`. Calculate percentage and percentage change for all KPI categories.

    Parameters
    ----------
    agg_df : pandas.core.frame.DataFrame
        Dataframe returned by `get_agg_data(cust_tweets, dhl_tweets)`.
    groupby_var : str
        Variable to aggregate the data by. One of ['year', 'quarter', 'month', 'week', 'day'].

    Returns
    -------
    agg_df_period : pandas.core.frame.DataFrame
        Dataframe containing numerical data agggreagated by `groupby_var`, within columns [`groupby_var`, 'variable', 'value', 'sum', 'percentage', 'pct_change'].

    """
    # Transform datetime column to datetime format
    agg_df['datetime'] = pd.to_datetime(agg_df['datetime'])
    
    # Get respective time period from datetime column
    if groupby_var == 'quarter':
        agg_df['quarter'] = agg_df['datetime'].apply(lambda x: x.quarter)
    elif groupby_var == 'month':
        agg_df['month'] = agg_df['datetime'].apply(lambda x: x.month)
    elif groupby_var == 'day':
        agg_df['day'] = agg_df['datetime'].apply(lambda x: x.day)
        
    # Aggregate by `groupby_var` by summation
    agg_df_period = agg_df.melt(id_vars=groupby_var, value_vars=['Total Customer Mentions', 'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions', 'Replies', 'Retweets']).groupby([groupby_var, 'variable'])['value'].sum().reset_index()
    
    # Get totals, save in a new dataframe and set index to KPI categories
    sum_df = agg_df_period.groupby(['variable'])['value'].sum().reset_index()
    sum_df = sum_df.set_index('variable')
    
    # Add column for totals for each respectives KPI categories
    agg_df_period['sum'] = agg_df_period.apply(lambda row: sum_df.at[row['variable'], 'value'], axis=1)
    
    # Calculate percentage and percentage change
    agg_df_period['percentage'] = agg_df_period.apply(lambda row: row['value']/row['sum']*100, axis=1)
    agg_df_period['pct_change'] = agg_df_period.groupby(['variable'])['value'].pct_change(fill_method='ffill')*100
    return agg_df_period


def get_summary_df(cust_tweets, dhl_tweets, groupby_user_input):
    """
    Create summary dataframe by aggregating `cust_tweets` and `dhl_tweets` based on `groupby_user_input`

    Parameters
    ----------
    cust_tweets : pandas.core.frame.DataFrame
        Dataframe returned by `get_cust_tweet(df, dhl_acc)`.
    dhl_tweets : pandas.core.frame.DataFrame
        Dataframe returned by `get_dhl_tweet(df, dhl_acc)`.
    groupby_user_input : str
        Variable to aggregate the data by, based on user input. One of ['Year', 'Quarter', 'Month', 'Week', 'Day'].

    Returns
    -------
    grouped_summary_merged : pandas.core.frame.DataFrame
        Merged dataframe containing data aggregated by `groupby_user_input`, within columns [`groupby_user_input`, 'variable', 'value', 'sum', 'percentage', 'pct_change', 'Tweet'].

    """

    agg_df = get_agg_data(cust_tweets, dhl_tweets).reset_index()
    groupby_var = groupby_user_input.lower()
    y_colname = {'count_cust_tweets': 'Total Customer Mentions',
                'count_dhl_tweets': 'Total DHL Tweets',
                'likes': 'Likes',
                'polarity_negative_mentions': 'Negative Mentions',
                'polarity_positive_mentions': 'Positive Mentions',
                'replies': 'Replies',
                'retweets': 'Retweets'}

    agg_df = agg_df.rename(columns=y_colname)
    agg_df_period = agg_by_period(agg_df, groupby_var)

    # Get day and quarter value
    if groupby_var == 'day':
        dhl_tweets[f'{groupby_var}'] = dhl_tweets['date'].apply(lambda x: x.day)
        cust_tweets[f'{groupby_var}'] = cust_tweets['date'].apply(lambda x: x.day)
    elif groupby_var == 'quarter':
        dhl_tweets[f'{groupby_var}'] = dhl_tweets['date'].apply(lambda x: x.quarter)
        cust_tweets[f'{groupby_var}'] = cust_tweets['date'].apply(lambda x: x.quarter)
    elif groupby_var == 'month':
        dhl_tweets[f'{groupby_var}'] = dhl_tweets['date'].apply(lambda x: x.month)
        cust_tweets[f'{groupby_var}'] = cust_tweets['date'].apply(lambda x: x.month)

    # Get top tweets for all variables
    grouped_top_replies = dhl_tweets[[f'{groupby_var}', 'tweet', 'replies']].sort_values(by=[f'{groupby_var}'], ascending=True).sort_values(by=['replies'], ascending=False).groupby([f'{groupby_var}']).head(1)
    grouped_top_likes = dhl_tweets[[f'{groupby_var}', 'tweet', 'likes']].sort_values(by=[f'{groupby_var}'], ascending=True).sort_values(by=['likes'], ascending=False).groupby([f'{groupby_var}']).head(1)
    grouped_top_retweets = dhl_tweets[[f'{groupby_var}', 'tweet', 'retweets']].sort_values(by=[f'{groupby_var}'], ascending=True).sort_values(by=['retweets'], ascending=False).groupby([f'{groupby_var}']).head(1)

    # Concat tweets for all variables
    grouped_top_dhl = pd.concat([grouped_top_replies, grouped_top_likes, grouped_top_retweets]).reset_index()

    # Identify variable type (one of replies, likes, retweets)
    grouped_top_dhl['Variable'] = np.where(grouped_top_dhl['replies'].notnull(), 'Replies',
             np.where(grouped_top_dhl['likes'].notnull(), 'Likes',
                     np.where(grouped_top_dhl['retweets'].notnull(), 'Retweets', '')))

    # Group cust_tweets by groupby_var
    grouped_top_cust = cust_tweets.groupby([f'{groupby_var}', 'polarity']).max()[['tweet']].reset_index()
    
    # Replace polarity with Mentions
    grouped_top_cust['Variable'] = grouped_top_cust['polarity'].apply(lambda x: 'Negative Mentions' if x == 'negative' else 'Positive Mentions')

    # Concat both grouped dhl_tweets and cust_tweets to create summary df
    grouped_summary_df = pd.concat([grouped_top_cust[[f'{groupby_var}', 'tweet', 'Variable']], grouped_top_dhl[[f'{groupby_var}', 'tweet', 'Variable']]]).rename(columns={'tweet':'Tweet'}).reset_index(drop=True)

    # Rename columns
    grouped_summary_df = grouped_summary_df.rename(columns={'Variable': 'variable'})

    # Ensure all are in numeric types
    if groupby_var == 'week':
        agg_df_period['week'] = pd.to_numeric(agg_df_period['week'])
        grouped_summary_df['week'] = pd.to_numeric(grouped_summary_df['week'])
    elif groupby_var == 'year':
        agg_df_period['year'] = pd.to_numeric(agg_df_period['year'])
        grouped_summary_df['year'] = pd.to_numeric(grouped_summary_df['year'])
    elif groupby_var == 'month':
        agg_df_period['month'] = pd.to_numeric(agg_df_period['month'])
        grouped_summary_df['month'] = pd.to_numeric(grouped_summary_df['month'])

    # Merge agg_df_period with grouped_summary_df
    grouped_summary_merged = agg_df_period.merge(grouped_summary_df, left_on=[f'{groupby_var}', 'variable'], right_on=[f'{groupby_var}', 'variable'], how='left')

    # Replace np.nan in Tweets with empty string
    grouped_summary_merged['Tweet'] = grouped_summary_merged['Tweet'].replace(np.nan, '')

    period_colname = {'year': 'Year',
                      'quarter': 'Quarter',
                      'month': 'Month',
                      'week': 'Week',
                      'day': 'Day'}
    # Rename columns
    grouped_summary_merged = grouped_summary_merged.rename(columns=period_colname)
    return grouped_summary_merged

def plot_pct_graph(graph_type, groupby_user_input, summary_df, kpi_color_pal):
    """
    Plot percentage or percentage change graph according to user input
    
    Parameters
    ----------
    graph_type : str
        Graph to plot based on user input.One of ['Percentage over time', 'Percentage change over time'].
    groupby_user_input : str
        Variable to aggregate the data by, based on user input. One of ['Year', 'Quarter', 'Month', 'Week', 'Day'].
    summary_df : pandas.core.frame.DataFrame
        Dataframe containing data aggregated by `groupby_user_input`, within columns [`groupby_user_input`, 'variable', 'value', 'sum', 'percentage', 'pct_change', 'Tweet'].
    kpi_color_pal : str
        Name of Altair color scheme, chosen for KPI color code.
    Returns
    -------
    altair.vegalite.v4.api.VConcatChart
        Vertically concatenated altair chart with graph on top layer and text table on bottom layer.
    """
    if graph_type == 'Percentage over time':
        field_var = 'percentage'
        field_var_title = 'Percentage'
    else:
        field_var = 'pct_change'
        field_var_title = 'Percentage Change'
    
    if groupby_user_input in ['Week', 'Day']:
        axis_type = 'Q'
    else:
        axis_type = 'O'

    if groupby_user_input in ['Year', 'Quarter', 'Month']:
        # Mouseover selection. Reduces opacity on non-selected items on chart
        highlight = alt.selection(type='single', on='mouseover', fields=[groupby_user_input], nearest=True)
        bars = alt.Chart(summary_df).mark_bar().encode(
                    x=alt.X(f'{groupby_user_input}:{axis_type}', axis=alt.Axis(format='1')),
                    y=alt.Y(f'{field_var}:Q', title=field_var_title),
                    column=alt.Column('variable:N', title='KPI'),
                    color=alt.Color('variable:N', legend=None, scale=alt.Scale(scheme=kpi_color_pal)),
                    opacity=alt.condition(highlight, alt.value(1), alt.value(0.2))
                ).properties(
                    title={
      "text": [f'KPI {field_var_title} across {groupby_user_input}'], 
      "subtitle": ["Plot represent all historical data.", f"Hover over bars to view the corresponding KPI {field_var_title} and representative tweets for each week in the Data Table below.",
                   ""],
      "color": "black",
      "subtitleColor": "gray"
    },
                    width=90,
                    height=100
                ).add_selection(highlight).transform_filter(alt.datum.Month > 0) # added in transform filter

        p = bars

    else:
        # Drag selection. Reduces opacity on non-selected items on chart
        highlight = alt.selection(type='interval')
        
        line = alt.Chart(summary_df).mark_line().encode(
            x=alt.X(f'{groupby_user_input}:{axis_type}', axis=alt.Axis(format='1', grid=False)),
            y=alt.Y(f'{field_var}:Q', title=field_var_title),
            color=alt.Color('variable:N', legend=None, scale=alt.Scale(scheme=kpi_color_pal)),
            opacity=alt.condition(highlight, alt.value(1), alt.value(0.2))
            ).properties(
                 title={
      "text": [f'KPI {field_var_title} across {groupby_user_input}'], 
      "subtitle": ["Plot represent all historical data.", "Drag mouse for selection. Data table below shows the corresponding tweets for selected points.",
                   ""],
      "color": "black",
      "subtitleColor": "gray"
    },
                width=780,
                height=150
                ).add_selection(highlight)

        point = alt.Chart(summary_df).mark_circle().encode(
            x=alt.X(f'{groupby_user_input}:{axis_type}', axis=alt.Axis(format='1')),
            y=f'{field_var}:Q',
            color=alt.Color('variable:N', legend=None, scale=alt.Scale(scheme=kpi_color_pal)),
            opacity=alt.condition(highlight, alt.value(1), alt.value(0.2))
        ).transform_filter(highlight)

        p = line+point

    ranked_text = alt.Chart(summary_df).mark_text(align='left', baseline='middle', limit=400).encode(
        y=alt.Y('row_number:O',axis=None)
        ).transform_window(
            row_number='row_number()'
            ).transform_filter(
                highlight
                ).transform_window(
                    rank='rank(row_number)'
                    ).transform_filter(alt.datum.rank<10).properties(height=160)

    # Columns of text table
    grouping = ranked_text.encode(text=f'{groupby_user_input}:Q').properties(title={"text": [''], "subtitle": [f'{str(groupby_user_input)}']})
    var = ranked_text.encode(text='variable:N').properties(title={"text": [''], "subtitle": ['KPI']})
    annos = ranked_text.encode(text=alt.Text('label_annos:N')).transform_calculate(label_annos=f'format(datum.{field_var},".1f") + " %"').properties(title={"text": [''], "subtitle": [field_var_title]})
    tweet = ranked_text.encode(text='Tweet:N').properties(title={"text": [''], "subtitle": ['Tweet']})
    
    # Horizontally concat columns to make up text table
    text = alt.hconcat(grouping, var, annos, tweet)

    # Build chart
    return alt.vconcat(
        p, text
        ).resolve_legend(
            color="independent"
            ).configure_view(
                strokeWidth=0).configure_title(
    fontSize=20,
    anchor='start',
    color='gray')

def get_annos(filtered_agg_df, user_input_x, user_input_y, user_input_agg_type, local_tz, server_tz):
    """
    Return annotations accompanying custom charts

    Parameters
    ----------
    filtered_agg_df : pandas.core.frame.DataFrame
        Filtered agg_df obtained from get_agg_df().
    user_input_x : str
        Variable to group the data by, based on user input. One of ['Hours of the day', 'Day of the week', 'Day of the month', 'Week', 'Date', 'Month', 'Quarter', 'Year'].
    user_input_y : str
        Variable for KPI, based on user input. One of ['Select All', 'Total Customer Mentions', 'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions', 'Replies', 'Retweets'].
    user_input_agg_type : str
        Variable to aggregate the data by, based on user input. One of ['Total number of Tweets', 'Average number of Tweets', 'Min number of Tweets', 'Max number of Tweets'].
    local_tz : str
        Region for user timezone eg "Asia/Kuala_Lumpur".
    server_tz : pytz.tzfile.Etc/UTC
        timezone information for server location.

    Returns
    -------
    list
        List containing 2 str describing top aggregated `Negative Mentions` and `Positive Mentions`.

    """
    # Only construct annotations when user select ['Select All'] for user_input_y
    if user_input_y == ['Total Customer Mentions', 'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions', 'Replies', 'Retweets']:
        filtered_agg_df['datetime'] = filtered_agg_df['datetime'].apply(lambda x: pd.to_datetime(x).tz_convert(local_tz))
        
        # Make a new column to later group the data by, based on user input
        if user_input_x == 'Hours of the day':
            filtered_agg_df['x'] = filtered_agg_df['datetime'].apply(lambda x: x.hour)
            annos_period = 'hour'
        elif user_input_x == 'Day of the week':
            filtered_agg_df['x'] = filtered_agg_df['datetime'].apply(lambda x: x.strftime('%A'))
            annos_period = ''
        elif user_input_x == 'Day of the month':
            filtered_agg_df['x'] = filtered_agg_df['datetime'].apply(lambda x: x.day)
            annos_period = 'day of the month'
        elif user_input_x == 'Month':
            filtered_agg_df['x'] = filtered_agg_df['datetime'].apply(lambda x: x.month)
            annos_period = ''
        elif user_input_x == 'Quarter':
            filtered_agg_df['x'] = filtered_agg_df['datetime'].apply(lambda x: x.quarter)
            annos_period = 'Q'
        elif user_input_x == 'Week':
            filtered_agg_df = filtered_agg_df.rename(columns = {'week': 'x'})
            annos_period = 'week'
        elif user_input_x == 'Year':
            filtered_agg_df = filtered_agg_df.rename(columns = {'year': 'x'})
            annos_period = 'year'
        elif user_input_x == 'Date':
            filtered_agg_df = filtered_agg_df.rename(columns = {'date': 'x'})
            annos_period = ''

        # Group and aggregate values based on user input
        if user_input_agg_type == 'Total number of Tweets':
            annos_df = filtered_agg_df.groupby(['x']).sum()
            annos_agg = 'Highest total'
        elif user_input_agg_type == 'Average number of Tweets':
            annos_df = filtered_agg_df.groupby(['x']).mean()
            annos_agg = 'Highest average'
        elif user_input_agg_type == 'Min number of Tweets':
            annos_df = filtered_agg_df.groupby(['x']).min()
            annos_agg = 'Min'
        elif user_input_agg_type == 'Max number of Tweets':
            annos_df = filtered_agg_df.groupby(['x']).max()
            annos_agg = 'Max'

        # Convert from wide to long format
        annos_df_melt = pd.melt(annos_df.reset_index(), id_vars=['x'])
        annos = []
        # Filter to top 1st value for every variable
        if user_input_agg_type in ['Total number of Tweets', 'Average number of Tweets']:
            annos_df_head = annos_df_melt.sort_values(['variable','value'],ascending=False).groupby('variable').head(1).set_index('variable').copy()
            # Append annotations for `Negative Mentions` and `Positive Mentions` in list
            for i in ['Negative Mentions', 'Positive Mentions']:
                if user_input_x == 'Hours of the day':
                    annos.append(f"{annos_agg} {i} on {annos_period} {str(annos_df_head.at[i, 'x']).zfill(2)}:00")
                elif user_input_x == 'Day of the month':
                    n = annos_df_head.at[i, 'x']
                    # Courtesy to Evandrix. ref: https://stackoverflow.com/a/36977549/14656169
                    suf = lambda n: "%d%s"%(n,{1:"st",2:"nd",3:"rd"}.get(n if n<20 else n%10,"th"))
                    annos.append(f"{annos_agg} {i} on {suf(n)} {annos_period}")
                elif user_input_x == 'Month':
                    n = datetime.date(1900, annos_df_head.at[i, 'x'], 1)
                    annos.append(f"{annos_agg} {i} on {annos_period} {n.strftime('%B')}")
                elif user_input_x == 'Year':
                    n = re.sub('\..*$', '', annos_df_head.at[i, 'x'])
                    annos.append(f"{annos_agg} {i} on {annos_period} {n}")
                elif user_input_x == 'Quarter':
                    annos.append(f"{annos_agg} {i} on {annos_period}{annos_df_head.at[i, 'x']}")
                else:
                    annos.append(f"{annos_agg} {i} on {annos_period} {annos_df_head.at[i, 'x']}")
        return annos
    else:
        return ''

def plot_global_trend2(all_df, kpi_color_pal):
    brush = alt.selection_single(encodings=['x'])

    # Main chart
    p = alt.Chart(all_df).mark_bar().encode(
        x=alt.X('week:O', axis=alt.Axis(tickSize=0, grid=False, labelExpr="datum.value % 1 ? null : datum.label")),
        y=alt.Y('value:Q', title = 'Total Tweets'),
        color=alt.condition(brush, 'variable:N', alt.value('lightblue'), scale=alt.Scale(scheme=kpi_color_pal), title='KPI'),
        tooltip=[alt.Tooltip(field='week', title='Week', type='ordinal'),
            alt.Tooltip(field='variable', title='KPI', type='ordinal'),
            alt.Tooltip(field='value', title='Total Tweets', type='quantitative')]
        ).properties(
            title={
    "text": ["Global Weekly Trend"], 
    "subtitle": ["Click on bar to view the corresponding trending tweets keywords for the selected week.",
                ""],
    "color": "black",
    "subtitleColor": "gray"
    },width=600, height=250
            ).add_selection(brush)

    # .transform_window(rank='rank()',sort=[alt.SortField('count', order='descending')])
    # Bottom bar charts (tweets keywords)
    pos_bar = alt.Chart(all_df).mark_bar().encode(
                x=alt.X('percentage:Q'),
                y=alt.Y('keywords:O', title='', sort=alt.EncodingSortField(field="count", op="sum", order='descending'), axis=alt.Axis(tickSize=0)),
                color=alt.value('lightgray'),
                opacity=alt.value(0.5)
                ).properties(
                    title='Trending Positive Keywords', width=300, height=100
                    ).transform_filter(brush).transform_filter((alt.datum.percentage >= 15) | (alt.datum.rank <= 10))

    neg_bar = alt.Chart(all_df).transform_window(
        rank='rank()', sort=[alt.SortField('count', order='descending')]
        ).transform_filter((alt.datum.percentage >= 15) | (alt.datum.rank <= 10) # Filter
            ).mark_bar().encode(
                x=alt.X('percentage:Q'),
                y=alt.Y('keywords:O', title='', sort=alt.EncodingSortField(field="count", op="sum", order='descending'), axis=alt.Axis(tickSize=0)),
                color=alt.value('lightgray'),
                opacity=alt.value(0.5)
                ).properties(
                    title='Trending Negative Keywords', width=300, height=100
                    ).transform_filter(alt.datum.week == brush.value)

    # Return concatenated charts
    return alt.vconcat(p, alt.hconcat(pos_bar,neg_bar)
                    ).resolve_legend(color="independent"
                                        ).configure_view(strokeWidth=0).configure_title(
    fontSize=20,
    anchor='start',
    color='gray'
    )
def plot_global_trend(df_list, kpi_color_pal):
    """
    Returns altair charts

    Parameters
    ----------
    df_list : list
        List containing 3 dataframe object used to produce plot.
        `df_list[0]` should contain df obtained by `get_agg_data(filtered_cust, filtered_dhl).reset_index()` -> melted by id='week'.
        `df_list[1]` should contain concatenated df obtained from `get_keyword_freq(tpos_keyword, weeknum, 'positive')` for all required weeknum.
        `df_list[2]` should contain concatenated df obtained from `get_keyword_freq(tpos_keyword, weeknum, 'negative')` for all required weeknum.
    kpi_color_pal : str
        Name of Altair color scheme, chosen for KPI color code.

    Returns
    -------
    altair.vegalite.v4.api.VConcatChart
        Vertically concatenated altair chart with barchart showing 8 weeks trend on top layer and trending positive and negative keywords barchat on bottom layer.

    """
    
    # Unpacking args
    recent_week_agg_df_melted = df_list[0]
    pos_df = df_list[1]
    neg_df = df_list[2]
    

    st.write('inside plot_global_trend')
    st.write('recent_week_agg_df_melted', recent_week_agg_df_melted)
    st.write('pos_df', pos_df)
    st.write('neg_df', neg_df)

    # Initialize selection
    # brush = alt.selection_single(fields=['week'])
    brush = alt.selection_single(encodings=['x'])

    # Main chart
    p = alt.Chart(recent_week_agg_df_melted).mark_bar().encode(
        x=alt.X('week:O', title='Week', axis=alt.Axis(tickSize=0, grid=False, labelExpr="datum.value % 1 ? null : datum.label")),
        y=alt.Y('value:Q', title = 'Total Tweets'),
        color=alt.condition(brush, 'variable:N', alt.value('lightblue'), scale=alt.Scale(scheme=kpi_color_pal), title='KPI'),
        tooltip=[alt.Tooltip(field='week', title='Week', type='ordinal'),
            alt.Tooltip(field='variable', title='KPI', type='ordinal'),
            alt.Tooltip(field='value', title='Total Tweets', type='quantitative')]
        ).properties(
             title={
      "text": ["Global Weekly Trend"], 
      "subtitle": ["Click on bar to view the corresponding trending tweets keywords for the selected week.",
                   ""],
      "color": "black",
      "subtitleColor": "gray"
    },width=600, height=250
            ).add_selection(brush)

    # Bottom bar charts (tweets keywords)
    pos_bar = alt.Chart(pos_df).transform_window(
        rank='rank()',sort=[alt.SortField('count', order='descending')]
        ).transform_filter(
            (alt.datum.percentage >= 15) | (alt.datum.rank <= 10)
            ).mark_bar().encode(
                x=alt.X('percentage:Q'),
                y=alt.Y('keywords:O', title='', sort=alt.EncodingSortField(field="count", op="sum", order='descending'), axis=alt.Axis(tickSize=0)),
                color=alt.value('lightgray'),
                opacity=alt.value(0.5)
                ).properties(
                    title='Trending Positive Keywords', width=300, height=100
                    ).transform_filter(brush)
    
    neg_bar = alt.Chart(neg_df).transform_window(
        rank='rank()', sort=[alt.SortField('count', order='descending')]
        ).transform_filter(
            (alt.datum.percentage >= 15) | (alt.datum.rank <= 10) # Filter
            ).mark_bar().encode(
                x=alt.X('percentage:Q'),
                y=alt.Y('keywords:O', title='', sort=alt.EncodingSortField(field="count", op="sum", order='descending'), axis=alt.Axis(tickSize=0)),
                color=alt.value('lightgray'),
                opacity=alt.value(0.5)
                ).properties(
                    title='Trending Negative Keywords', width=300, height=100
                    ).transform_filter(brush)
    
    # Return concatenated charts
    return alt.vconcat(p, alt.hconcat(pos_bar,neg_bar)
                       ).resolve_legend(color="independent"
                                        ).configure_view(strokeWidth=0).configure_title(
    fontSize=20,
    anchor='start',
    color='gray'
)

def get_keyword_freq(keywords_str, weeknum, polarity):
    """
    Return top 5 tweets keywords by frequency and percentage for specified `weeknum` and `polarity`

    Parameters
    ----------
    keywords_str : str
        Joined string containing tweets keywords. Obtained from `keywords_polarity_week(filtered_cust, weeknum)`.
    weeknum : int
        Week number.
    polarity : str
        Tweet's polarity.

    Returns
    -------
    pandas.core.frame.DataFrame
        Dataframe containing keywords and its frequency counts in columns ['week', 'keywords', 'polarity', 'count', 'percentage'].

    """
    # Split keywords into unique token list
    str_list = keywords_str.lower().split()

    # If list is not empty
    if len(str_list) != 0:
        # Create new df with keywords column
        keyword_df = pd.DataFrame({'week': weeknum, 'keywords': str_list, 'polarity': polarity})
        # Get count for each token
        keyword_df['count'] = keyword_df['keywords'].apply(lambda x: str_list.count(x))
        # Remove duplicates
        keyword_df = keyword_df.drop_duplicates()
        # Drop rows if it is any of the element in the list
        keyword_df = keyword_df.drop(keyword_df[keyword_df['keywords'].isin(['when', 'more', 'you', 'your', 'today', 'with', 'the', 'just', 'unknown', 'dhl', 'dhlexpress', 'this', 'that', 'from', 'have', 'where', 'what', 'why', 'how', 'time', 'will', 'i', 'is', 'am', 'who', 'they', 'been', 'their', 'well', 'since', 'many'])].index).reset_index(drop=True)
        # Drop keywords shorter than 2 char
        keyword_df = keyword_df[keyword_df['keywords'].str.len() > 3]
        # Drop rows if it is numerical
        keyword_df = keyword_df.drop(keyword_df[keyword_df['keywords'].str.isdigit()].index).reset_index(drop=True)
        # Drop rows if it contains digit
        keyword_df = keyword_df.drop(keyword_df[keyword_df['keywords'].str.match('.*\d.*')].index).reset_index(drop=True)
        # Sort by count
        keyword_df = keyword_df.sort_values(by='count', ascending=False).reset_index(drop=True)
        # Get only top 10 unique words
        keyword_df = keyword_df[:10]
        total = keyword_df['count'].sum()
        # Get percentage
        keyword_df['percentage'] = keyword_df['count'].apply(lambda x: round(x/total*100))
    else:
        return pd.DataFrame({'week': weeknum,'keywords': [np.nan], 'polarity':polarity, 'count':[0]})
    # Return only top 5
    return keyword_df[:5]

def keywords_polarity_week(df, cw_weeknum):
    """
    Concatenate all tweets from `df` into a string by `cw_weeknum` and `polarity` .

    Parameters
    ----------
    df : pandas.core.frame.DataFrame
        Dataframe containing tweets to extract from.
    cw_weeknum : int
        week number.

    Returns
    -------
    positive_words : str
        Joined string from all positive tweets.
    negative_words : str
        Joined string from all negative tweets.

    """
    
    # Slice df based on selected date and polarity, then save as new df
    positive_df = df.loc[(df['week'] == cw_weeknum) & (df['polarity'] == 'positive')].copy()
    negative_df = df.loc[(df['week'] == cw_weeknum) & (df['polarity'] == 'negative')].copy()
    
    # Clean up
    positive_list = positive_df['tweet'].apply(lambda x: "".join(x).replace("'", "").replace("[", "").replace("]", "").replace(",", "").split())
    negative_list = negative_df['tweet'].apply(lambda x: "".join(x).replace("'", "").replace("[", "").replace("]", "").replace(",", "").split())
    
    # Join words
    positive_words = (' ').join([item for sublist in positive_list for item in sublist])
    negative_words = (' ').join([item for sublist in negative_list for item in sublist])
        
    return positive_words, negative_words


def lowercase(text):
    return text.lower()

def remove_extraspace(text):
    return re.sub("\s\s+", " ", text)

def remove_numbers_punctuation(text):
    return re.sub('[^a-zA-Z]', " ", text)

def remove_hashtag(text):
    pattern = re.compile('#.*', re.IGNORECASE)
    return ' '.join([word for word in text.split(' ') if pattern.search(word)==None])

def remove_twitterhandle(text):
    pattern = re.compile('@.*', re.IGNORECASE)
    return ' '.join([word for word in text.split(' ') if pattern.search(word)==None])

def remove_link(text):
    pattern = re.compile('htt.*', re.IGNORECASE)
    return ' '.join([word for word in text.split(' ') if pattern.search(word)==None])

def complete_preprocess2(text):
    """
    Performs preprocessing:
        Lowercase, lemmatizes, remove stopword, remove extraspace, remove numbers and punctuations, remove hashtags, remove twitter handle, remove links

    Parameters
    ----------
    text : str
        String to preprocess.

    Returns
    -------
    str
        Preprocessed string.

    """
    return lowercase(remove_extraspace(remove_numbers_punctuation(remove_hashtag(remove_twitterhandle(remove_link(text))))))


def get_regional_summary_df(regional_acc_list, cust_tweets, dhl_tweets):
    """
    Create summary df for ['year-month', 'year-week'] sum aggregation, which essentially is nearly the same output as get_summary_df() with an additional column for 'regional_acc'.
    Generated by joining extracted '@dhlexpress*' from cust_tweets and 'username' column in dhl_tweets.

    Parameters
    ----------
    regional_acc_list : list
        List containing official DHL Twitter username to group summary by.
    cust_tweets : pandas.core.frame.DataFrame
        Dataframe returned by `get_cust_tweet(df, dhl_acc)`.
    dhl_tweets : pandas.core.frame.DataFrame
        Dataframe returned by `get_dhl_tweet(df, dhl_acc)`.

    Returns
    -------
    grouped_summary_df : pandas.core.frame.DataFrame
        Dataframe containing aggregated data with sample representative Tweets in columns 'regional_acc', 'year-month',
        'variable', 'value', 'Year', 'sum', 'percentage', 'pct_change', 'Tweet', 'period', 'year-week'].
    agg_df : pandas.core.frame.DataFrame
        Dataframe containing aggregated data in columns ['datetime', 'week', 'year', 'Total Customer Mentions',
       'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions',
       'Replies', 'Retweets', 'regional_acc', 'year-week', 'year-month',
       'hour', 'weekday'].

    """
    acc_df_list = []
    for acc in regional_acc_list:
        df = get_agg_data(cust_tweets[cust_tweets['mention'].str.contains(acc)].reset_index(drop=True),
                 dhl_tweets[dhl_tweets['username']==acc].reset_index(drop=True))
        df['regional_acc'] = acc
        df = df.reset_index()
        acc_df_list.append(df)
    
    y_colname = {'count_cust_tweets': 'Total Customer Mentions',
                'count_dhl_tweets': 'Total DHL Tweets',
                'likes': 'Likes',
                'polarity_negative_mentions': 'Negative Mentions',
                'polarity_positive_mentions': 'Positive Mentions',
                'replies': 'Replies',
                'retweets': 'Retweets'}
    
    agg_df = pd.concat(acc_df_list).reset_index(drop=True)
    agg_df = agg_df.rename(columns=y_colname)
    
    agg_df['datetime'] = pd.to_datetime(agg_df['datetime'])
    agg_df['year-week'] = agg_df.apply(lambda row: row['year'][:4]+'-'+row['week'].zfill(2), axis=1)
    agg_df['year-month'] = agg_df['datetime'].apply(lambda x: str(x)[:7])
    
    
    grouped_summary_df_list = []
    for groupby_var in ['year-month', 'year-week']:
    
        # Aggregate by `groupby_var` by summation
        agg_df_period = agg_df.melt(id_vars=['regional_acc', groupby_var], value_vars=['Total Customer Mentions', 'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions', 'Replies', 'Retweets']).groupby(['regional_acc', groupby_var, 'variable'])['value'].sum().reset_index()
    
        # Extract year from year-month
        agg_df_period['year'] = agg_df_period[groupby_var].apply(lambda x: x[:4])
    
        # Get total for year and variable for each regional_acc
        sum_df = agg_df_period.groupby(['regional_acc', 'year', 'variable'])['value'].sum().reset_index()
        sum_df = sum_df.set_index(['regional_acc', 'year', 'variable'])
    
        # Retrieve total for year and variable by regional_acc
        agg_df_period['sum'] = agg_df_period.apply(lambda row: sum_df.query(f'regional_acc == "{row["regional_acc"]}" and year=="{row["year"]}" and variable == "{row["variable"]}"').value[0], axis=1)
    
        # Calculate percentage and percentage change
        agg_df_period['percentage'] = agg_df_period.apply(lambda row: 0 if row['value'] == 0 or row['sum'] == 0 else row['value']/row['sum']*100, axis=1)
        agg_df_period['pct_change'] = agg_df_period.groupby(['regional_acc', 'year', 'variable'])['value'].pct_change(fill_method='ffill')*100
    

        dhl_tweets['year-week'] = dhl_tweets.apply(lambda row: str(row['year'])+'-'+str(row['week']).zfill(2), axis=1)
        dhl_tweets['year-month'] = dhl_tweets['date'].apply(lambda x: str(x)[:7])
    
        grouped_top_dhl_list = []
    
        # Get top tweets for all variables
        grouped_top_replies = dhl_tweets[['username', f'{groupby_var}', 'tweet', 'replies']].sort_values(by=[f'{groupby_var}'], ascending=True).sort_values(by=['replies'], ascending=False).groupby(['username', f'{groupby_var}']).head(1)
        grouped_top_likes = dhl_tweets[['username', f'{groupby_var}', 'tweet', 'likes']].sort_values(by=[f'{groupby_var}'], ascending=True).sort_values(by=['likes'], ascending=False).groupby(['username', f'{groupby_var}']).head(1)
        grouped_top_retweets = dhl_tweets[['username', f'{groupby_var}', 'tweet', 'retweets']].sort_values(by=[f'{groupby_var}'], ascending=True).sort_values(by=['retweets'], ascending=False).groupby(['username', f'{groupby_var}']).head(1)
    
        # Append to list
        grouped_top_dhl_list.append([grouped_top_replies, grouped_top_likes, grouped_top_retweets])
        # Concat dfs in the list
        grouped_top_dhl = pd.concat(grouped_top_dhl_list[0]).reset_index(drop=True)
        # Drop rows if there is not at least 1 NaNs in the subset columns
        grouped_top_dhl = grouped_top_dhl.dropna(subset=['replies', 'likes', 'retweets'], thresh=1)
    
        # Identify variable type (one of replies, likes, retweets)
        grouped_top_dhl['variable'] = np.where(grouped_top_dhl['replies'].notnull(), 'Replies',
                 np.where(grouped_top_dhl['likes'].notnull(), 'Likes',
                         np.where(grouped_top_dhl['retweets'].notnull(), 'Retweets', '')))

        cust_tweets['year-week'] = cust_tweets.apply(lambda row: str(row['year'])+'-'+str(row['week']).zfill(2), axis=1)
        cust_tweets['year-month'] = cust_tweets['date'].apply(lambda x: str(x)[:7])
    
        # Group cust_tweets by groupby_var
        grouped_top_cust = cust_tweets.groupby(['mention', f'{groupby_var}', 'polarity']).max()[['tweet']].reset_index()
    
        # Replace polarity with Mentions
        grouped_top_cust['variable'] = grouped_top_cust['polarity'].apply(lambda x: 'Negative Mentions' if x == 'negative' else 'Positive Mentions')
    
        # Rename cols into regional_acc before concatenating dfs
        grouped_top_cust = grouped_top_cust.rename(columns={'mention': 'regional_acc'})
        grouped_top_dhl = grouped_top_dhl.rename(columns={'username': 'regional_acc'})
        grouped_summary_df = pd.concat([grouped_top_cust[['regional_acc', f'{groupby_var}', 'tweet', 'variable']], grouped_top_dhl[['regional_acc', f'{groupby_var}', 'tweet', 'variable']]]).rename(columns={'tweet':'Tweet'}).reset_index(drop=True)
    
        # Outer join agg_df_period with grouped_summary_df
        grouped_summary_merged = agg_df_period.merge(grouped_summary_df, left_on=['regional_acc', f'{groupby_var}', 'variable'], right_on=['regional_acc', f'{groupby_var}', 'variable'], how='outer').drop_duplicates().reset_index(drop=True)
    
        # Replace np.nan in Tweets with empty string
        grouped_summary_merged['Tweet'] = grouped_summary_merged['Tweet'].replace(np.nan, '')
    
        period_colname = {'year': 'Year',
                      'quarter': 'Quarter',
                      'month': 'Month',
                      'week': 'Week',
                      'day': 'Day',
                     'date': 'Date'}
        # Rename columns
        grouped_summary_merged = grouped_summary_merged.rename(columns=period_colname)
        grouped_summary_merged['period'] = groupby_var
        grouped_summary_df_list.append(grouped_summary_merged)
        
    # Concat all summary_dfs
    grouped_summary_df = pd.concat(grouped_summary_df_list).reset_index(drop=True)
    # Replace np.nans
    grouped_summary_df = grouped_summary_df.replace(np.nan, 0)
    # Clean up Year col
    grouped_summary_df['Year'] = grouped_summary_df.apply(lambda row: str(row['year-week'])[:4] if row['Year'] == 0.0 else row['Year'], axis=1)
    return grouped_summary_df, agg_df

def plot_regional_rw(prev_4_weeks_df, kpi_color_pal):
    """
    Plot recent week regional graph

    Parameters
    ----------
    prev_4_weeks_df : pandas.core.frame.DataFrame
        Filtered grouped_summary_df obtained from get_regional_summary_df().
    kpi_color_pal : str
        Name of Altair color scheme, chosen for KPI color code.

    Returns
    -------
    altair.vegalite.v4.api.Chart.

    """
    highlight = alt.selection_single(fields=['variable'], bind='legend')

    return alt.Chart(prev_4_weeks_df[['regional_acc', 'variable', 'week', 'value']]).transform_aggregate(
        count='sum(value)',
        groupby=['regional_acc', 'variable', 'week']
    ).transform_joinaggregate(
        total='sum(count)',
        groupby=['regional_acc', 'week']
    ).transform_calculate(
        frac=alt.datum.count / alt.datum.total
    ).mark_bar().encode(
        x = alt.X('regional_acc:N', title='', sort='-y', axis=alt.Axis(labelAngle=360, tickSize=0)),
        y = alt.Y('count:Q', title="Percentage", stack='normalize', axis=alt.Axis(format="%")),
        color = alt.Color('variable:N', title='KPI',  scale=alt.Scale(scheme=kpi_color_pal)),
        row = alt.Row('week:O', sort='descending', header=alt.Header(labelOrient='top')),
        tooltip = [alt.Tooltip('variable:N', title='KPI'),
                   alt.Tooltip('frac:Q', title='Percentage', format='.0%'),
                  alt.Tooltip('regional_acc:N', title='Regional account')],
        opacity = alt.condition(highlight, alt.value(1), alt.value(0.2))
    ).configure_mark(
        strokeWidth=10
    ).add_selection(
    highlight
    ).properties(
    title = {
      "text": ["Recent Weekly Trend across Regions and KPIs"], 
      "subtitle": ["Highlight KPI by clicking on legend."],
      "color": "black",
      "subtitleColor": "gray"}, width=550, height=80
    ).configure_header(titleOrient='top').configure_title(
    fontSize=20,
    anchor='start',
    color='gray'
)

def plot_regional_yw(wk_recent_regional_agg_df, regional_acc_color_pal):
    """
    PLot Year Week graph across KPI and Regional account.

    Parameters
    ----------
    wk_recent_regional_agg_df : pandas.core.frame.DataFrame
        Filtered grouped_summary_df obtained from get_regional_summary_df().
    regional_acc_color_pal : str
        Name of Altair color scheme, chosen for regional account color code.

    Returns
    -------
    altair.vegalite.v4.api.Chart.

    """

    # Initialize dropdown filter
    kpi_var = wk_recent_regional_agg_df["variable"].unique()
    kpi_dropdown = alt.binding_select(options=kpi_var)
    kpi_selection = alt.selection_single(
        fields=["variable"],
        bind=kpi_dropdown,
        name="KPI")
    
    # Initialize selection by legend
    selection = alt.selection_multi(fields=['regional_acc'], bind='legend')
    
    return alt.Chart(wk_recent_regional_agg_df).transform_calculate(
        label_percentage=f'format({alt.datum.percentage},".1f") + " %"'
        ).mark_bar(binSpacing=0, width=10).encode(
            x = alt.X('week:O', axis=alt.Axis(domain=False, tickSize=0), title='Week'),
            y = alt.Y('percentage:Q', stack=None, title="Percentage"),
            color = alt.Color('regional_acc:N', title='Regional account', scale=alt.Scale(scheme=regional_acc_color_pal)),
            row = alt.Row('Year:O', sort='descending', header=alt.Header(labelOrient='top')),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.01)),
            tooltip=[alt.Tooltip(field='week', title='week', type='ordinal'),
                     alt.Tooltip(field='label_percentage', title='Percentage', type='nominal'),
                     alt.Tooltip(field='value', title='value', type='quantitative'),
                     alt.Tooltip(field='sum', title='sum', type='quantitative'),
                     alt.Tooltip(field='Tweet', title='Tweet', type='nominal')]
            ).properties(
                title={
                    "text": ["Weekly Trend across Years and Regions"], 
                    "subtitle": ["Highlight by selecting multiple regions from legend using Shift key.",
                                 "Filter by selecting KPI from dropdown menu. Hover for tooltip."],
                    "color": "black",
                    "subtitleColor": "gray"}, width=620, height=50
                ).configure_title(
                    fontSize=20, anchor='start', color='gray'
                    ).configure_header(titleOrient='top').add_selection(kpi_selection).transform_filter(kpi_selection).add_selection(selection)

def plot_regional_heatmap(filtered_agg_df):
    """
    Plot heatmap graph showing density of Negative Mentions from customer by Hour of Day and Regional account.

    Parameters
    ----------
    filtered_agg_df : pandas.core.frame.DataFrame
        Filtered agg_df obtained from  get_agg_df().

    Returns
    -------
    altair.vegalite.v4.api.Chart.

    """
    return alt.Chart(filtered_agg_df).transform_density(
        'hour', groupby=['regional_acc'], as_=['Hour', 'Density'], extent=[0,24]
        ).mark_bar(binSpacing=2).encode(
            x = alt.X("Hour:Q", title='Hour of Day', scale=alt.Scale(domain=[0, 24]), bin=alt.Bin(maxbins=24)),
            y = alt.Y('Density:Q', title='Density'),
            row = alt.Row('regional_acc:N',  header=alt.Header(labelOrient='top'), title=''),
            color = alt.Color('Density:Q',  scale=alt.Scale(scheme='lightgreyred')),
            tooltip = [alt.Tooltip('Density:Q', title='Density', format="0.2f"),
                       alt.Tooltip('Hour:O', title='Hour of Day', format="1.0f")],
            ).properties(
                title={
                    "text": ["Overall Density plot on Negative Mentions across Regions"], 
                    "subtitle": ["Plot represent all historial data points. Hours with mostly dense (Density = 0.5) Negative Mentions are in red."],
                    "color": "black",
                    "subtitleColor": "gray"}, width=600, height=50
                ).configure_title(fontSize=20, anchor='start', color='gray')

def plot_regional_ym(yr_recent_regional_agg_df, regional_acc_color_pal):
    """
    Plot Year Month graph across KPI and Regional account.

    Parameters
    ----------
    yr_recent_regional_agg_df : pandas.core.frame.DataFrame
        Filtered dataframe obtained from get_regional_summary_df().
    regional_acc_color_pal : str
        Name of Altair color scheme, chosen for regional account color code.

    Returns
    -------
    altair.vegalite.v4.api.Chart.

    """
    # Initialize dropdown filter for KPI variables
    kpi_var = yr_recent_regional_agg_df["variable"].unique()
    kpi_dropdown = alt.binding_select(options=kpi_var)
    kpi_selection = alt.selection_single(
        fields=["variable"],
        bind=kpi_dropdown,
        name="KPI",
    )
    
    # Initialize multiple selection for legend
    selection = alt.selection_multi(fields=['regional_acc'], bind='legend')
    
    return alt.Chart(yr_recent_regional_agg_df).transform_calculate(
        label_percentage=f'format({alt.datum.percentage},".1f") + " %"'
        ).mark_bar(binSpacing=0).encode(
            x = alt.X('yearmonth(year-month):T', axis=alt.Axis(domain=False, format='%Y-%B', tickSize=0), title='Year-Month'),
            y = alt.Y('percentage:Q', stack=None, title='Percentage'),
            color=alt.Color('regional_acc:N', title='Regional account', scale=alt.Scale(scheme=regional_acc_color_pal)),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.01)),
            tooltip=[alt.Tooltip(field='year-month', title='Year-Month', type='temporal'),
                     alt.Tooltip(field='variable', title='KPI', type='nominal'),
                     alt.Tooltip(field='label_percentage', title='Percentage', type='ordinal'),
                     alt.Tooltip(field='Tweet', title='Representative Tweet', type='nominal')]
            ).properties(
                title={
                    "text": ["Yearly Trend across Regions and KPIs"], 
                    "subtitle": ["No distinct seasonal pattern observed across all KPIs and Regions",
                                 "Highlight by selecting multiple regions from legend using Shift key. Filter by selecting KPI from dropdown menu. Hover for tooltip."],
                    "color": "black",
                    "subtitleColor": "gray"}, width=750, height=350
                ).add_selection(kpi_selection).transform_filter(kpi_selection).add_selection(selection).transform_timeunit(month='month(Date)').configure_title(fontSize=20, anchor='start', color='gray')


def main():

    # Set common color palette
    regional_acc_color_pal = 'set2'
    kpi_color_pal = 'accent'

    # Set timezones
    # get_localzone() will get the timezone of streamlit.io server which runs the app
    # Therefore, as a workaround, the local timezone is hardcoded
    server_tz = get_localzone()
    local_tz = 'Asia/Kuala_Lumpur'

    # Build credential object and connection to google drive
    credentials, drive_service = build_connection()
    # File ID for Tweet data stored in Google Drive
    data_file_id = '1XiABfco1-NpSwSjl32BAUS_HqPrBFYzD'
    
    # FOR RENDERING ALL PLOTS & DATATABLES
    # Load tweet data from google drive
    df = load_data_gdrive(data_file_id)
    # Slice and get DHL accounts details from loaded df
    dhl_acc = get_dhl_acc(df)
    # Slice loaded df to get tweets from DHL accounts
    dhl_tweets = get_dhl_tweet(df, dhl_acc)
    # Slice loaded df to get tweets from customers
    cust_tweets = get_cust_tweet(df, dhl_acc)
    # Sort customer tweets by datetime in descending order
    cust_tweets = cust_tweets.sort_values(by=['datetime'], ascending=False).reset_index(drop=True)
    # Remove tweets from a known bot accounts
    cust_tweets = cust_tweets[~cust_tweets['username'].isin(['TrendMicroHome', 'centralspotter'])].reset_index(drop=True)
    
    # FOR READING & CAPTURING USER INPUT
    # Connect to googlesheet to read & update user input
    googlesheet_name = 'user-validation'
    worksheet, spread = connect_googlesheet(googlesheet_name, credentials)
    # Load data from googlesheet
    df_googlesheet = load_google_worksheet(worksheet)
    
    # Initialize datatable in session state, if doesn't exist
    # to enable updates upon user input on date filtering
    if 'datatable' not in st.session_state:
        st.session_state['datatable'] = get_datatable(cust_tweets, get_weekstart())

    # Create form to receive user input for filtering
    with st.form('sidebar_form'):
        # Display form in sidebar
        with st.sidebar:
            st.title('Dashboard')
            
            # Create dropdown menu for navigation (page-like output)
            choice = st.selectbox("Navigate to:", ["Home", "Global Trend", "Regional Trend", "Data"])
            # Create date input for filtering
            selected_week = st.date_input(
                "Select KPI for week:", dt.today(),
                help='Default to current business week')
            # Create form submit button
            
            sidebar_submit = st.form_submit_button('Go!')

            st.write('')
            st.write('')
            st.write('')
            # Display last update information
            st.write(get_modified_time(data_file_id, drive_service, server_tz, local_tz))
            
            # If form is submitted
            if sidebar_submit:
                # Update datatable with user selected input
                update_datatable(cust_tweets, selected_week, choice)
                # Save value from session state object into variable
                datatable = st.session_state['datatable']   

    
    if choice == 'Home':
        
        # Get value from session state object
        datatable = st.session_state['datatable']
        
        st.subheader(f'Week {selected_week.isocalendar()[1]} KPIs')

        # Get aggregated data
        agg_data_kpi = get_agg_data(cust_tweets, dhl_tweets)
        # Additional transformation 1: Remove 'datetime' column from index
        agg_data_kpi = agg_data_kpi.reset_index(level='datetime', drop=True)
        # Additional transformation 2: Pivot df using sum as aggregate function
        agg_data_pivot = pd.pivot_table(agg_data_kpi, values=['replies', 'retweets', 'likes', 'count_dhl_tweets', 'polarity_negative_mentions', 'polarity_positive_mentions', 'count_cust_tweets'], index=['week', 'year'], aggfunc=np.sum, fill_value=0)
        
        # Get KPI data
        kpi_dict, warning = get_kpi(agg_data_pivot, selected_week)

        # Display appropriate message if any
        if warning != "":
            st.warning(warning)

        # Initialize columns and display KPIs in each columns
        col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns(6)
        col_h1.metric(label="Positive Mentions", value=str(kpi_dict['Positive Mentions'][0]),
                    delta=str(kpi_dict['Positive Mentions'][1]), delta_color='normal')
        col_h2.metric(label="Negative Mentions", value=str(kpi_dict['Negative Mentions'][0]),
                    delta=str(kpi_dict['Negative Mentions'][1]), delta_color='inverse')
        col_h3.metric(label="DHL Tweets", value=str(kpi_dict['DHL Tweets'][0]),
                      delta=str(kpi_dict['DHL Tweets'][1]), delta_color='normal')
        col_h4.metric(label="Retweets", value=str(kpi_dict['Retweets'][0]),
                      delta=str(kpi_dict['Retweets'][1]), delta_color='normal')
        col_h5.metric(label="Replies", value=str(kpi_dict['Replies'][0]),
                      delta=str(kpi_dict['Replies'][1]), delta_color='normal')
        col_h6.metric(label="Likes", value=str(kpi_dict['Likes'][0]),
                      delta=str(kpi_dict['Likes'][1]), delta_color='normal')

        # Get positive and negative string for wordclouds
        pos, neg = hashtags_polarity(cust_tweets, selected_week)
        
        # Initialize columns
        col_h7, col_h8 = st.columns(2)
        
        # Create subplots
        fig, ax = plt.subplots()
        # Create positive wordclouds
        positive_wordcloud = WordCloud(
            max_words=10000, margin=10, random_state=0,
            background_color='white',
            width=1800,
            height=800, collocations=False
        ).generate_from_text(pos).recolor(color_func=lambda *args, **kwargs: (135, 220, 183)) # rgb for green color is specified in recolor function
        plt.imshow(positive_wordcloud)
        plt.axis("off")
        # Display wordcloud
        col_h7.pyplot(fig)
        
        # Create subplots
        fig, ax = plt.subplots()
        # Create negative wordcloud
        negative_wordcloud = WordCloud(
            max_words=10000, margin=10, random_state=0,
            background_color='white',
            width=1800,
            height=800, collocations=False
        ).generate(neg).recolor(color_func=lambda *args, **kwargs: (231, 77, 60)) # rgb for red color is specified in recolor function
        plt.imshow(negative_wordcloud)
        plt.axis("off")
        # Display wordcloud
        col_h8.pyplot(fig)

        # Create form to receive user input from bokeh datatable
        with st.form("home_form"):
            # Datatable title
            st.write('Top 10 Recent Tweets')
            
            # Initialize Bokeh ColumnDataSource object from sliced pandas dataframe
            # ref: https://docs.bokeh.org/en/latest/docs/user_guide/data.html#using-a-pandas-dataframe
            cds = ColumnDataSource(datatable.head(10))
            
            # Initialize Bokeh table column widget
            # ref: https://docs.bokeh.org/en/latest/docs/reference/models/widgets/tables.html?#bokeh.models.TableColumn
            columns = [
                TableColumn(field='datetime', title='Date', formatter=DateFormatter(), width=80),
                TableColumn(field='polarity', title='Polarity', formatter=polarity_formatter('polarity'), width=60),
                TableColumn(field='tweet', title='Tweet',
                            formatter=HTMLTemplateFormatter(
                                template='<textarea readonly style="width:100%; height:500%; overflow-wrap: break-word; border-style: none; border-color: Transparent; overflow: auto; background: transparent;" "element.style.height = (25+element.scrollHeight)+"px";"> <%= value %> </textarea>')),
                TableColumn(field="link", title='Reply @ Twitter', formatter=HTMLTemplateFormatter(
                    template='<p style="text-align:center;"> <a href="<%= value %>"target="_blank">💬</p>'), width=90)
            ]
    
            # Define events
            cds.selected.js_on_change(
                "indices",
                CustomJS(
                    args=dict(source=cds),
                    code="""
                    document.dispatchEvent(
                    new CustomEvent("INDEX_SELECT", {detail: {data: source.selected.indices}})
                    )
                    """
                )
            )
            
            # Create DataTable plot
            p = DataTable(source=cds, columns=columns, css_classes=["my_table"], row_height=100, editable=False,
                          reorderable=True,
                          scroll_to_selection=True,
                          sortable=True,
                          selectable="checkbox", aspect_ratio='auto', width=735)
            
            # Get event dict containing data from user input on rendered bokeh_plot
            # ref: https://github.com/ash2shukla/streamlit-bokeh-events/blob/master/streamlit_bokeh_events/__init__.py#L21
            result = streamlit_bokeh_events(bokeh_plot=p, events="INDEX_SELECT", key="datetime", refresh_on_update=False,
                                            debounce_time=0, override_height=430)
            
            # Create form submit button
            home_form_submitted = st.form_submit_button("Send Feedback", help='Tweet polarity is predicted using Sentiment Analysis Model. Help improve polarity accuracy by ☑ checkbox and click Send Feedback to flag any incorrect prediction')

        # If form is submitted and checkbox(es) selected
        if result and home_form_submitted:
            if result.get("INDEX_SELECT"):
                # If result is not empty list (Exception catching for when user select and then unselect any checkboxes)
                if result.get("INDEX_SELECT")["data"] != []:
                    # Get data using row index
                    df_user_input = datatable.iloc[result.get("INDEX_SELECT")["data"]]
                    # Add a column for timestamp during user input
                    df_user_input['user_input_timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # Append new user input to exisiting df from googlesheet
                    new_df = df_googlesheet.append(df_user_input, ignore_index=True)
                    # Remove duplicates
                    new_df = new_df.drop_duplicates(subset=['datetime','tweet','polarity'])
                    # Update googlesheet (ie overwriting new_df in place of the exisiting data in googlesheet)
                    update_googlesheet_gspread_pandas(spread, googlesheet_name, new_df)
                    # Display appropriate message
                    st.success('Feedback recorded. Thank you for your feedback.')
                else:
                    # Display appropriate message
                    st.warning('No data selected. Please ☑ checkbox for any incorrect polarity prediction and click Send Feedback.')
        
        # If form is submitted but no checkbox selected, display appropriate message
        if home_form_submitted and not result:
            st.warning('No data selected. Please ☑ checkbox for any incorrect polarity prediction and click Send Feedback.')


    if choice == 'Trends':
        
        # X axis options
        x = ['Hours of the day',
             'Day of the week',
             'Day of the month',
             'Week',
             'Date',
             'Month',
             'Quarter',
             'Year']
        
        # Y axis options
        y = ['Select All',
             'Total Customer Mentions',
             'Total DHL Tweets',
             'Likes',
             'Negative Mentions',
             'Positive Mentions',
             'Replies',
             'Retweets']
        
        # Y axis options and its corresponding column names
        y_colname = {'count_cust_tweets': 'Total Customer Mentions',
                    'count_dhl_tweets': 'Total DHL Tweets',
                    'likes': 'Likes',
                    'polarity_negative_mentions': 'Negative Mentions',
                    'polarity_positive_mentions': 'Positive Mentions',
                    'replies': 'Replies',
                    'retweets': 'Retweets'}
                
        # Chart options
        chart_type = ['Area',
                      'Bar',
                      'Heatmap',
                      'Line',
                      'Scatter']
        
        # Aggregation type options
        agg_type = ['Total number of Tweets',
                    'Average number of Tweets',
                    'Min number of Tweets',
                    'Max number of Tweets']
        
        # Reset index for further transformation
        agg_df = get_agg_data(cust_tweets, dhl_tweets).reset_index()
        # Rename columns
        agg_df = agg_df.rename(columns=y_colname)
        # Get only data up to selected_week
        filtered_agg_df = agg_df.loc[(agg_df['datetime'] <= f'{selected_week.year}-{selected_week.month}-{selected_week.day} 23:59:59')].copy()
        # Change timezone (timezone for scraped data is user's local timezone)
        # Ref: https://github.com/twintproject/twint/issues/234
        # So to make it correct again, first localize the timezone naive col into local tz
        # and then convert it into the server tz for correct plot display
        filtered_agg_df['datetime'] = filtered_agg_df['datetime'].apply(lambda x: pd.to_datetime(x).tz_localize(local_tz).tz_convert(server_tz))
        # Get date column
        filtered_agg_df['date'] = filtered_agg_df['datetime'].apply(lambda x: pd.to_datetime(x).date())

        # Get max date from scraped data
        df_max_date = max(df['datetime'])
        max_date = datetime.date(df_max_date.year, df_max_date.month, df_max_date.day)
        # Get the date of Monday of max_date
        min_date = get_weekstart(max_date)
        
        with st.form('trend_form1'):
            col_t3, col_t4 = st.columns([2,1])
            trend_form1_selection = col_t3.selectbox('Select Trend:',
                     ('Percentage over time', 'Percentage change over time'))
            trend_form1_groupby = col_t4.selectbox('Aggregate by:',
                                                   ('Year', 'Quarter', 'Month', 'Week', 'Day'))
            trend_form1_submitted = st.form_submit_button("Submit")
            
        if trend_form1_submitted:
            summary_df = get_summary_df(cust_tweets, dhl_tweets, trend_form1_groupby)
            plot1 = plot_pct_graph(trend_form1_selection, trend_form1_groupby, summary_df)
            st.write(plot1)
            
            
        with st.expander('Create Custom Charts'):
            # Form to get user input
            with st.form("trend_form2"):
                # Initialize columns
                col_t1, col_t2 = st.columns([1,2])
                # Get user input for date filter
                user_input_date_from = col_t1.date_input("Filter from date:", min_date)
                user_input_date_to = col_t2.date_input("Filter to date:", max_date)
                # Get user input for X axis
                user_input_x = col_t1.selectbox("Choose X axis:", x)
                # Get user input for Y axis
                user_input_y = col_t2.multiselect("Choose Y axis:", y, default=['Select All'],
                                                help='Multiple selection is allowed')
                # Get user input for chart type
                user_input_chart_type = col_t1.selectbox("Choose Chart type:", chart_type,
                                                       help='Heatmap chart will default to (hours, day of the week) regardless of selected X axis')
                # Get user input for agg type
                user_input_agg_type = col_t2.selectbox("Choose aggregation type:", agg_type)
                # Initialize form submit button
                trend_form2_submitted = st.form_submit_button("Submit")
        
        # If 'Select All' is selected, get all column names
        if 'Select All' in user_input_y:
            user_input_y = ['Total Customer Mentions', 'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions', 'Replies', 'Retweets']

        # If user selected a From date filter
        if user_input_date_from != min_date:
            filtered_agg_df = filtered_agg_df.loc[(filtered_agg_df['date'] >= user_input_date_from)]
        else:
            filtered_agg_df = filtered_agg_df.loc[(filtered_agg_df['date'] >= min_date)]

        # If user selected a To date filter
        if user_input_date_to != max_date:
            filtered_agg_df = filtered_agg_df.loc[(filtered_agg_df['date'] <= user_input_date_to)]
        else:
            filtered_agg_df = filtered_agg_df.loc[(filtered_agg_df['date'] <= max_date)]

        # Exception catching: if user_input_date_from > than user_input_date_to
        if user_input_date_from > user_input_date_to:
            st.warning(
                "The To date must be greater than the From date. Please reselect appropriate dates and click submit.")

        # Exception catching: if data is not available
        if len(filtered_agg_df) == 0:
            st.warning('Data is not available for selected dates. Please reselect appropriate dates and click submit.')

        # If form is submitted, plot graph
        if trend_form2_submitted:
            # Display plot title
            st.markdown("""
                        <style>
                        .big-font {
                            font-size:18px;
                        }
                        </style>
                        """, unsafe_allow_html=True)
            plot_title = f"Distribution of {user_input_agg_type} by KPI and {user_input_x} ({user_input_date_from} ~ {user_input_date_to})"
            st.markdown(f'<p style="font-weight:bold" class="big-font">{plot_title}</p>', unsafe_allow_html=True)
            # Construct plot
            plot2 = plot_custom_graph(filtered_agg_df.drop(columns=['date']), user_input_x, user_input_y, user_input_chart_type, user_input_agg_type)
            # Display plot annotations (if any)
            annos = get_annos(filtered_agg_df, user_input_x, user_input_y, user_input_agg_type, local_tz, server_tz)
            if annos != '':
                for a in annos:
                    st.write(a)
            # Display plot
            st.write(plot2)


    if choice == 'Data':
        
        # Get value from session state object
        datatable = st.session_state['datatable']
        
        # Initialize columns
        col_d1, col_d2, col_d3 = st.columns([1.5,1,1])
        # Empty column
        col_d1.empty()
        # Create download button for current view
        col_d2.download_button(label="Download CSV current view",
                           data=convert_df(datatable[['datetime', 'date', 'time', 'polarity', 'tweet', 'link']]),
                           file_name='data.csv', mime='text/csv')
        # Create download button for all data
        col_d3.download_button(label="Download CSV all data",
                           data=convert_df(cust_tweets[['datetime', 'date', 'time', 'polarity', 'tweet', 'link']]),
                           file_name='data.csv', mime='text/csv')
        
        # Create form to receive user input from bokeh datatable
        with st.form("data_form"):
            
            # Datatable title
            st.write('All Recent Tweets')
            
            # Initialize Bokeh ColumnDataSource object from sliced pandas dataframe
            cds_full = ColumnDataSource(datatable)
            
            # Initialize Bokeh table column widget
            columns_full = [
                TableColumn(field='datetime', title='Date', formatter=DateFormatter(), width=60),
                TableColumn(field='polarity', title='Polarity', formatter=polarity_formatter('polarity'), width=60),
                TableColumn(field='tweet', title='Tweet',
                            formatter=HTMLTemplateFormatter(
                                template='<textarea readonly style="width:100%; height:430%; overflow-wrap: break-word; overflow:hidden; border-style: none; border-color: Transparent; overflow: auto; background: transparent;" "element.style.height = (25+element.scrollHeight)+"px";"> <%= value %> </textarea>')),
                TableColumn(field="link", title='Reply @ Twitter', formatter=HTMLTemplateFormatter(
                    template='<p style="text-align:center;"> <a href="<%= value %>"target="_blank">💬</p>'), width=85)
            ]
            
            # Define events
            cds_full.selected.js_on_change(
                "indices",
                CustomJS(
                    args=dict(source=cds_full),
                    code="""
                    document.dispatchEvent(
                    new CustomEvent("INDEX_SELECT", {detail: {data: source.selected.indices}})
                    )
                    """
                )
            )
            
            # Create DataTable plot
            p_full = DataTable(source=cds_full, columns=columns_full, css_classes=["my_table"], row_height=150,
                               editable=False,
                               reorderable=True,
                               scroll_to_selection=True,
                               sortable=True,
                               selectable="checkbox", aspect_ratio='auto', width=735)
            
            # Get event dict containing data from user input on rendered bokeh_plot
            result_full = streamlit_bokeh_events(bokeh_plot=p_full, events="INDEX_SELECT", key="datetime",
                                                 refresh_on_update=False, debounce_time=0, override_height=420)
    
            # Create form submit button
            data_form_submitted = st.form_submit_button("Send Feedback", help='Tweet polarity is predicted using Sentiment Analysis Model. Help improve polarity accuracy by ☑ checkbox and click Send Feedback to flag any incorrect prediction')
            
        # If form is submitted and checkbox(es) selected
        if result_full and data_form_submitted:
            if result_full.get("INDEX_SELECT"):
                # If result is not empty list (Exception catching for when user select and then unselect any checkboxes)
                if result_full.get("INDEX_SELECT")["data"] != []:
                    # Get data using row index
                    df_user_input = datatable.iloc[result_full.get("INDEX_SELECT")["data"]]
                    # Add a column for timestamp during user input
                    df_user_input['user_input_timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # Append new user input to exisiting df from googlesheet
                    new_df = df_googlesheet.append(df_user_input, ignore_index=True)
                    # Remove duplicates
                    new_df = new_df.drop_duplicates(subset=['datetime','tweet','polarity'])
                    # Update googlesheet (ie overwriting new_df in place of the exisiting data in googlesheet)
                    update_googlesheet_gspread_pandas(spread, googlesheet_name, new_df)
                    # Display appropriate message
                    st.success('Feedback recorded. Thank you for your feedback.')
                else:
                    # Display appropriate message
                    st.warning('No data selected. Please ☑ checkbox for any incorrect polarity prediction and click Send Feedback.')
        
        # If form is submitted but no checkbox selected, display appropriate message
        if data_form_submitted and not result_full:
            st.warning('No data selected. Please ☑ checkbox for any incorrect polarity prediction and click Send Feedback.')
    
    
    if choice == 'Global Trend':
        
        global_ct = cust_tweets.copy()
        # Perform simple preprocessing on tweet col
        global_ct['tweet'] = global_ct['tweet'].apply(lambda x: complete_preprocess2(x))
        
         # Get the most recent 5-week's prior date
        oldest_week = pd.to_datetime(selected_week-timedelta(weeks=8))
        filtered_cust = global_ct[global_ct['date']>=oldest_week]
        filtered_dhl = dhl_tweets[dhl_tweets['date']>=oldest_week]
        
        # Get top tweets keywords for all weeks in filtered_cust
        top5wk_df_pos = []
        top5wk_df_neg = []
        for weeknum in filtered_cust['week'].unique():
            tpos_keyword, tneg_keyword = keywords_polarity_week(filtered_cust, weeknum)
            top5wk_df_pos.append(get_keyword_freq(tpos_keyword, weeknum, 'positive'))
            top5wk_df_neg.append(get_keyword_freq(tneg_keyword, weeknum, 'negative'))
        
        top5week_pos = pd.concat(top5wk_df_pos)
        top5week_neg = pd.concat(top5wk_df_neg)
        recent_week_agg_df = get_agg_data(filtered_cust, filtered_dhl).reset_index()
        
        y_colname = {'count_cust_tweets': 'Total Customer Mentions',
                            'count_dhl_tweets': 'Total DHL Tweets',
                            'likes': 'Likes',
                            'polarity_negative_mentions': 'Negative Mentions',
                            'polarity_positive_mentions': 'Positive Mentions',
                            'replies': 'Replies',
                            'retweets': 'Retweets'}

        y = ['Total Customer Mentions',
                    'Total DHL Tweets',
                    'Likes',
                    'Negative Mentions',
                    'Positive Mentions',
                    'Replies',
                    'Retweets']
        
        recent_week_agg_df = recent_week_agg_df.rename(columns=y_colname)
        recent_week_agg_df_melted = recent_week_agg_df.melt(id_vars='week', value_vars=y).groupby(['week', 'variable'])['value'].sum().reset_index()
        
        polarity_df = pd.concat([top5week_neg, top5week_pos])
        all_df = pd.concat([polarity_df, recent_week_agg_df_melted]).reset_index(drop=True)
        all_df['week'] = all_df['week'].apply(lambda x: int(x))
        pos_df = all_df[all_df['polarity']=='positive'].sort_values(by=['count'], ascending=False).reset_index(drop=True)
        neg_df = all_df[all_df['polarity']=='negative'].sort_values(by=['count'], ascending=False).reset_index(drop=True)
        
        st.write('recent_week_agg_df_melted', recent_week_agg_df_melted)
        st.write('pos_df', pos_df)
        st.write('neg_df', neg_df)
        
        # global_plot1 = plot_global_trend([recent_week_agg_df_melted, pos_df, neg_df], kpi_color_pal)
        global_plot1 = plot_global_trend2(all_df, kpi_color_pal)
        st.write(global_plot1)
        st.write('---')
        
        # Prepare df for plot2 and plot3
        summary_df_list = []
        for var in ['Month', 'Week']:
            summary_df_list.append(get_summary_df(cust_tweets, dhl_tweets, var))
        
        summary_df = pd.concat(summary_df_list).reset_index(drop=True)
        summary_df = summary_df.replace(np.nan, 0)
        
        plot2_selection = 'Percentage change over time'
        plot2_period = 'Month'
        global_plot2 = plot_pct_graph(plot2_selection, plot2_period, summary_df, kpi_color_pal)
        st.write(global_plot2)
        st.write("---")
        
        plot3_selection = 'Percentage over time'
        plot3_period = 'Week'
        global_plot3 = plot_pct_graph(plot3_selection, plot3_period, summary_df[summary_df['Week']>0].reset_index(drop=True), kpi_color_pal)
        st.write(global_plot3)
        

    if choice == 'Regional Trend':

        regional_ct = cust_tweets.copy()
        regional_dt = dhl_tweets.copy()

        # Extract mention from cust tweets
        regional_ct['mention'] = regional_ct['tweet'].str.extract('(@dhlexpress[^\s\W]+)', re.IGNORECASE)
        regional_ct['mention'] = regional_ct['mention'].replace(np.nan, '')
        # Lowercasing mentioned username
        regional_ct['mention'] = regional_ct['mention'].apply(lambda x: x.lower())
        # Removing '@'
        regional_ct['mention'] = regional_ct['mention'].apply(lambda x: x.replace('@', '').strip())
        # Lowercasing username on dhl_tweets
        regional_dt['username'] = regional_dt['username'].apply(lambda x: x.lower())
        
        # Define regional username
        regional_acc_list = ['dhlexpressuk', 'dhlexpressfr', 'dhlexpressitaly', 'dhlexpressmy', 'dhlexpressindia']
        grouped_summary_df, agg_df = get_regional_summary_df(regional_acc_list, regional_ct, regional_dt)
        wk_recent_regional_agg_df = grouped_summary_df[(grouped_summary_df['regional_acc'].isin(regional_acc_list)) & (grouped_summary_df['period']=='year-week') ].reset_index(drop=True)
        wk_recent_regional_agg_df['week'] = wk_recent_regional_agg_df['year-week'].apply(lambda x: int(x[-2:]))
        
        prev_4_weeks = selected_week - timedelta(weeks=3)
        prev_4_weeks_year, prev_4_weeks_weeknum, *_ = prev_4_weeks.isocalendar()
        selected_week_year, selected_week_weeknum, *_ = selected_week.isocalendar()
        prev_4_weeks_df = wk_recent_regional_agg_df[(wk_recent_regional_agg_df['year-week']>=str(prev_4_weeks_year)+'-'+str(prev_4_weeks_weeknum)) & (wk_recent_regional_agg_df['year-week']<=str(selected_week_year)+'-'+str(selected_week_weeknum))]
        regional_plot1 = plot_regional_rw(prev_4_weeks_df, kpi_color_pal)
        st.write(regional_plot1)
        st.write('---')
        
        yr_recent_regional_agg_df = grouped_summary_df[(grouped_summary_df['regional_acc'].isin(regional_acc_list)) & (grouped_summary_df['period']=='year-month')].reset_index(drop=True)
        regional_plot2 = plot_regional_ym(yr_recent_regional_agg_df, regional_acc_color_pal)
        st.write(regional_plot2)
        st.write('---')
        
        regional_plot3 = plot_regional_yw(wk_recent_regional_agg_df, regional_acc_color_pal)
        st.write(regional_plot3)
        st.write('---')
        
        agg_df['hour'] = agg_df['datetime'].apply(lambda x: x.hour)
        filtered_agg_df = agg_df.melt(id_vars=['hour', 'regional_acc'], value_vars=['Negative Mentions']).groupby(['hour', 'regional_acc']).sum().reset_index()
        regional_plot4 = plot_regional_heatmap(filtered_agg_df)
        st.write(regional_plot4)


if __name__ == '__main__':
    main()