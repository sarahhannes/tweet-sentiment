from googleapiclient.http import MediaFileUpload
# from Google import Create_Service

import pickle
import os
import sys
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request

def Create_Service(client_secret_file, api_name, api_version, *scopes):
    print(client_secret_file, api_name, api_version, scopes, sep='-')
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = [scope for scope in scopes[0]]
    print(SCOPES)

    cred = None
    working_dir = os.getcwd()
    token_dir = 'token files'

    pickle_file = f'token_{API_SERVICE_NAME}_{API_VERSION}.pickle'
    # print(pickle_file)

    ### Check if token dir exists first, if not, create the folder
    if not os.path.exists(os.path.join(working_dir, token_dir)):
        os.mkdir(os.path.join(working_dir, token_dir))

    if os.path.exists(os.path.join(working_dir, token_dir, pickle_file)):
        with open(os.path.join(working_dir, token_dir, pickle_file), 'rb') as token:
            cred = pickle.load(token)

    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            cred = flow.run_local_server()

        with open(os.path.join(working_dir, token_dir, pickle_file), 'wb') as token:
            pickle.dump(cred, token)

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=cred)
        print(API_SERVICE_NAME, 'service created successfully')
        return service
    except Exception as e:
        print(e)
        print(f'Failed to create service instance for {API_SERVICE_NAME}')
        os.remove(os.path.join(working_dir, token_dir, pickle_file))
        return None


def convert_to_RFC_datetime(year=1900, month=1, day=1, hour=0, minute=0):
    dt = datetime.datetime(year, month, day, hour, minute, 0).isoformat() + 'Z'
    return dt


CLIENT_SECRET_FILE = sys.argv[0]

with open(CLIENT_SECRET_FILE, 'rb') as file:
    print('Input file not empty:', b"installed" in file.read(30))
    print('Found client_id in input file:', b"client_id" in file.read(100))


API_NAME = 'drive'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/drive']

service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

# Upload a file
# file_metadata = {
#     'name': 'data.txt',
#     'parents': ['1mHLT3xNo0II-ajpGIMe1FrQasH0iWi9P']
# }
#
# media_content = MediaFileUpload('data.txt', mimetype='text/plain')
#
# file = service.files().create(
#     body=file_metadata,
#
#     media_body=media_content
# ).execute()

# Replace Existing File on Google Drive
# data.txt file id
file_id = '1XiABfco1-NpSwSjl32BAUS_HqPrBFYzD'

media_content = MediaFileUpload('file1.txt', mimetype='text/plain')

service.files().update(
    fileId=file_id,
    media_body=media_content
).execute()
