#!/bin/sh

# Decrypt the file

mkdir $HOME/secrets

# --batch to prevent interactive command
# --yes to assume "yes" for questions
gpg --quiet --batch --yes --passphrase="$CLIENT_SECRET_PASSPHRASE" \
--output $HOME/secrets/client_secret.json -d client_secret.json.gpg
