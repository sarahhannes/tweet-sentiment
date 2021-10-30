# -*- coding: utf-8 -*-
"""Load model staged as `Production` on MLFlow."""

import os
import mlflow.sklearn
import mlflow.pyfunc
import mlflow


def get_model():
    """
    Returns model

    Returns
    -------
    model : mlflow.pyfunc.PyFuncModel
        Registered `SentimentAnalysisClassifier` model in Production stage.

    """

    experiment_name = "SentimentAnalysis"
    tracking_uri = os.environ.get('MLFLOW_TRACKING_URI')
    registered_model_name = "SentimentAnalysisClassifier"
    stage = 'Production'

    # Set experiment name
    mlflow.set_experiment(experiment_name)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    # Set path to log
    mlflow.set_tracking_uri(tracking_uri)

    model = mlflow.pyfunc.load_model(model_uri=f"models:/{registered_model_name}/{stage}")
    return model
