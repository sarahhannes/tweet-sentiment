Twitter Sentiment Analysis [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/sarahhannes/tweet-sentiment/dev/app2.py)
==============================
[![CD](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/cd.yml/badge.svg)](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/cd.yml)
[![CT](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct.yml/badge.svg)](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct.yml)
[![CT Workflow Rerun](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct_rerun.yml/badge.svg)](https://github.com/SarahHannes/tweet-sentiment/actions/workflows/ct_rerun.yml)

A Python based project for performing sentiment analysis on Twitter data.
- Twitter data is hourly scraped using {twint} package.
- Scheduled model training is performed monthly on MLflow served on a `g1-small` GCP Compute Engine instance.
- Model training artifacts are stored in GCP Cloud Storage.
- Instance schedule is applied on the subscribed Compute Engine instance for cost efficiency.
- Total cost of GCP usage is less than MYR 3.00/ month (approx. USD 0.72/ month).
<br>

Architecture Overview
------------
![flowcharts-pipelines (6)](https://user-images.githubusercontent.com/78901374/145487611-43c9be19-ab46-475a-9f77-770f19ae08e5.png)

Simplified View of Pipelines
------------
![flowcharts-DAG for black background drawio](https://user-images.githubusercontent.com/78901374/157574470-f29bf415-ce8a-4c76-a605-b1e27a28c40d.png)

Dashboard
------------
<i> Click [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/sarahhannes/tweet-sentiment/dev/app2.py) to view dashboard! </i>

![ezgif com-gif-maker (2)](https://user-images.githubusercontent.com/78901374/156597875-cc1ee50d-ab2b-427d-a0b5-9ee707e6c8a9.gif)


Limitations
--------
- Unfortunately, hardly reproducible due to manual pipeline integration & authentication processes.
- Dashboard is not scalable. Currently the twitter handle belonging to twitter accounts of interests were hardcoded in python file served on {Streamlit} for data analysis and visualization.
- No fallbacks on failed scheduled Actions.

Credits
--------
<p><small>Project based on the <a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project template</a>. #cookiecutterdatascience</small></p>
<br><i> Thank you to the developers of twint and all other packages for making this project possible! </i>
