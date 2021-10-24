# -*- coding: utf-8 -*-
"""Update file to Google Drive.

Usage
-----
To be used as part of scheduled Continuous Deployment workflow.
"""

import json
import os

from apiclient import errors
from apiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import google_auth_oauthlib
import requests


def update_file(filename):
    try:
        print('Updating file in progress...')
        if filename == 'data.txt':
            file_id = '1XiABfco1-NpSwSjl32BAUS_HqPrBFYzD'
            mimetype = 'text/plain'

        elif filename == 'model.pickle':
            file_id = '1ydeM6Tiamck5sF8oMDThZIRb0xQu7Nqd'
            mimetype = 'application/octet-stream'

        file_metadata = {'name': filename}

        media = MediaFileUpload(filename, mimetype=mimetype)
        file = drive_service.files().update(body=file_metadata,
                                            fileId=file_id,
                                            media_body=media,
                                            addParents='1mHLT3xNo0II-ajpGIMe1FrQasH0iWi9P').execute()

        print(f'File update executed for {filename}')
        print('File ID: %s' % file.get('id'))

    except errors.HttpError as error:
        print('An error occurred: %s' % error)
        return None


def get_access_token(client_id, client_secret, refresh_token, access_token):
    print('Getting access token...')
    r = requests.post(
        'https://www.googleapis.com/oauth2/v4/token',
        headers={'content-type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }
    )

    # If the obtained access token is not the current ones in used, then save it as the access token
    if json.loads(r.text)['access_token'] != access_token:
        print('New access token obtained')
        access_token = json.loads(r.text)['access_token']
        print('New access token is saved')

    # Since we are using refresh token, it should always gives 200 response code (hopefully)
    if r.status_code != 200:
        print('Status code:', r.status_code)
        print('Refresh token expired.')
        print('Please get a new one at https://console.cloud.google.com/ and update GitHub Action secrets.')
    return access_token


if __name__ == '__main__':
    account_email = 'tweet.sentiment.py@gmail.com'
    app_name = 'tweet-sentiment'
    token_uri = 'https://oauth2.googleapis.com/token'
    authorized_redirect_uri = 'https://developers.google.com/oauthplayground'

    client_id = os.environ['GOOGLEDRIVE_CLIENT_ID']
    client_secret = os.environ['GOOGLEDRIVE_CLIENT_SECRET']
    refresh_token = os.environ['GOOGLEDRIVE_REFRESH_TOKEN']
    access_token = os.environ['GOOGLEDRIVE_ACCESS_TOKEN']
    filename = os.environ['UPDATE_FILENAME']

    # Get access token
    access_token = get_access_token(client_id, client_secret, refresh_token, access_token)

    # Set authorization parameters
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config=
        {"web": {"client_id": client_id,
                 "project_id": "quixotic-card-325716",
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": token_uri,
                 "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                 "client_secret": client_secret,
                 "redirect_uris": [authorized_redirect_uri]}},
        scopes=['https://www.googleapis.com/auth/drive'])

    # Get credential from access token & refresh token
    cred = Credentials(token=access_token,
                       refresh_token=refresh_token,
                       client_id=client_id,
                       client_secret=client_secret,
                       token_uri=token_uri)

    # Create service
    with build('drive', 'v3', credentials=cred) as drive_service:
        # Call API
        update_file(filename)
