Twitter Sentiment Analysis [_archieved_]
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/sarahhannes/tweet-sentiment/dev/app2.py) 
==============================
[![CD](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/cd.yml/badge.svg)](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/cd.yml)
[![CT](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct.yml/badge.svg)](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct.yml)
[![CT_Workflow_Rerun](https://github.com/SarahHannes/tweet-sentiment/workflows/CT%20Workflow%20Rerun/badge.svg)](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct_rerun.yml)

A Python based project for performing sentiment analysis on Twitter data. Get <a href="https://docs.google.com/viewer?srcid=1Eo0UGMQTx9UBntdb4pg39QOOmJhlUfZJ&pid=explorer&efh=false&a=v&chrome=false">full project paper</a> here.
- Twitter data is hourly scraped using {twint} package.
- Scheduled model training is performed monthly on MLflow served on a `g1-small` GCP Compute Engine instance.
- Model training artifacts are stored in GCP Cloud Storage.
- Instance schedule is applied on the subscribed Compute Engine instance for cost efficiency.
- Total cost of GCP usage is less than MYR 3.00/ month (approx. USD 0.72/ month).

Dashboard
------------
<i> Click [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/sarahhannes/tweet-sentiment/dev/app2.py) to view dashboard! </i>

![ezgif com-gif-maker (2)](https://user-images.githubusercontent.com/78901374/156597875-cc1ee50d-ab2b-427d-a0b5-9ee707e6c8a9.gif)

Simplified View of Pipelines
------------
![flowcharts-DAG for black background drawio](https://user-images.githubusercontent.com/78901374/157574470-f29bf415-ce8a-4c76-a605-b1e27a28c40d.png)

Architecture Overview
------------
![flowcharts-pipelines (6)](https://user-images.githubusercontent.com/78901374/145487611-43c9be19-ab46-475a-9f77-770f19ae08e5.png)

GCP Config
------------
`startup-script` for GCP Compute Engine instance:
```
#! /bin/bash
sudo apt update
sudo apt-get -y install tmux
echo Installing python3-pip
sudo apt install -y python3-pip
export PATH="$HOME/.local/bin:$PATH"
echo Installing mlflow and google_cloud_storage
pip3 install mlflow google-cloud-storage
echo Starting new tmux session
sudo -H -u <USERNAME> tmux new-session -d -s mysession
mlflow server \
--backend-store-uri sqlite:///mlflow.db \
--default-artifact-root <gsutil URI> \
--host localhost
```
Working Example:

```
#! /bin/bash
sudo apt update
sudo apt-get -y install tmux
echo Installing python3-pip
sudo apt install -y python3-pip
export PATH="$HOME/.local/bin:$PATH"
echo Installing mlflow and google_cloud_storage
pip3 install mlflow google-cloud-storage
echo Starting new tmux session
sudo -H -u tweet_sentiment_py tmux new-session -d -s mysession
mlflow server \
--backend-store-uri sqlite:///mlflow.db \
--default-artifact-root gs://mlflow_bucket_001 \
--host localhost
```


Limitations & Roadblocks
--------
- Unfortunately, hardly reproducible due to manual pipeline integration & authentication processes.
- Dashboard is not scalable. Currently the twitter handle belonging to twitter accounts of interests were hardcoded in python file served on {Streamlit} for data analysis and visualization.
- No fallbacks on failed scheduled Actions.
- Roadblock: As of Jan 2022, GitHub Action build may fail due to dependencies installation error. This affects both the scheduled pipelines and dashboard.<a href="https://github.blog/changelog/2022-01-11-github-actions-jobs-running-on-windows-latest-are-now-running-on-windows-server-2022/#:~:text=actions-,GitHub%20Actions%3A%20Jobs%20running%20on%20%60windows%2Dlatest%60%20are,running%20on%20Windows%20Server%202022.&text=Windows%20Server%202022%20became%20generally,2019%20to%20Windows%20Server%202022."> (See Ref)</a>

Credits
--------
<p><small>Project based on the <a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project template</a>. #cookiecutterdatascience</small></p>
<br><i> Thank you to the developers of twint and all other packages for making this project possible! </i>
