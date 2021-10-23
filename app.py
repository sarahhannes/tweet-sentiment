from datetime import datetime as dt
from datetime import date, timedelta
import datetime
import os
import re

from tzlocal import get_localzone
from bokeh.models import ColumnDataSource, CustomJS
from bokeh.models import DataTable, TableColumn, HTMLTemplateFormatter, DateFormatter
from googleapiclient.discovery import build
from google.oauth2 import service_account
from gspread_pandas import Spread, Client
from streamlit_bokeh_events import streamlit_bokeh_events
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
    
    # Unpack year, weeknum and day from selected date
    cw_year, cw_weeknum, cw_day = selected_week.isocalendar()

    # Slice df based on selected date and polarity, then save as new df
    positive_df = df.loc[(df['week'] == cw_weeknum) & (df['year'] == cw_year) & (df['polarity'] == 'positive')].copy()
    negative_df = df.loc[(df['week'] == cw_weeknum) & (df['year'] == cw_year) & (df['polarity'] == 'negative')].copy()
    
    # If either one is empty, get the most recent data
    if len(positive_df) == 0:
        top2_weeknum = df['week'].unique()[-2]
        max_year = max(df['year'])

        # slice to get the most recent week -1, year
        positive_df = df.loc[
            (df['week'] == top2_weeknum) & (df['year'] == max_year) & (df['polarity'] == 'positive')].copy()

    if len(negative_df) == 0:
        top2_weeknum = df['week'].unique()[-2]
        max_year = max(df['year'])
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
    Slice to obtain only data for selected_week and update value in session_state

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
    if choice != 'Data':
        st.session_state['datatable'] = get_datatable(cust_tweets, selected_week)
    else:
        weekstart = get_weekstart(selected_week)
        st.session_state['datatable'] = get_datatable(cust_tweets, weekstart)


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


def plot_graph(df, x, y, chart_type, agg_type):
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
        'Week': 'week:O',
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


def main():

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
            choice = st.selectbox("Navigate to:", ["Home", "Trends", "Data"])
            # Create date input for filtering
            selected_week = st.date_input(
                "Select KPI for week:", dt.today(),
                help='Default to current business week')
            # Create form submit button
            
            sidebar_submit = st.form_submit_button('Go!',
                                       on_click=update_datatable, # Updates datatable on click
                                       args=(cust_tweets, selected_week, choice)) # Arguments for update_datatable function

            st.write('')
            st.write('')
            st.write('')
            # Display last update information
            st.write(get_modified_time(data_file_id, drive_service, server_tz, local_tz))
            
            # If form is submitted
            if sidebar_submit:
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

        # Form to get user input
        with st.form("trend_form"):
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
            trend_form_submitted = st.form_submit_button("Submit")
        
        # If 'Select All' is selected, get all column names
        if 'Select All' in user_input_y:
            user_input_y = ['Total Customer Mentions', 'Total DHL Tweets', 'Likes', 'Negative Mentions', 'Positive Mentions', 'Replies', 'Retweets']

        # If user selected a From date filter
        if user_input_date_from != min_date:
            filtered_agg_df = filtered_agg_df.loc[(filtered_agg_df['date'] >= user_input_date_from)]

        # If user selected a To date filter
        if user_input_date_to != max_date:
            filtered_agg_df = filtered_agg_df.loc[(filtered_agg_df['date'] <= user_input_date_to)]

        # Exception catching: if user_input_date_from > than user_input_date_to
        if user_input_date_from > user_input_date_to:
            st.warning(
                "The To date must be greater than the From date. Please reselect appropriate dates and click submit.")

        # Exception catching: if data is not available
        if len(filtered_agg_df) == 0:
            st.warning('Data is not available for selected dates. Please reselect appropriate dates and click submit.')

        # If form is submitted, plot graph
        if trend_form_submitted:
            plot = plot_graph(filtered_agg_df.drop(columns=['date']), user_input_x, user_input_y, user_input_chart_type, user_input_agg_type)
            st.write(plot)

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
    
if __name__ == '__main__':
    main()
