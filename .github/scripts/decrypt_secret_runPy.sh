#!/bin/sh

# Decrypt the file

mkdir $HOME/secrets

# --batch to prevent interactive command
# --yes to assume "yes" for questions
gpg --quiet --batch --yes --passphrase="$CLIENT_SECRET_PASSPHRASE" \
--output $HOME/secrets/client_secret.json -d client_secret.json.gpg

# Install required dependencies for python script
pip install google-api-python-client
pip install google-auth-oauthlib

# Run upload script
python3 ./src/data/upload_to_gdrive_sys_argv.py $HOME/secrets/client_secret.json