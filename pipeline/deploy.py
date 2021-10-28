# -*- coding: utf-8 -*-
"""Push models to Production & Staging.

Usage
-----
To be used as part of scheduled Continuous Training workflow.
"""

import os
import mlflow.sklearn
import mlflow.pyfunc
import mlflow


if __name__ == '__main__':

    # Set mlflow tracking config
    experiment_name = "SentimentAnalysis"
    tracking_uri = 'http://34.66.179.103:80'
    registered_model_name = "SentimentAnalysisClassifier"

    # Set experiment name
    mlflow.set_experiment(experiment_name)
    experiment = mlflow.get_experiment_by_name(experiment_name)

    # Set path to log
    mlflow.set_tracking_uri(tracking_uri)

    # Get runs info
    df_runs = mlflow.search_runs(order_by=['metrics.accuracy DESC'], max_results=100)

    # Save all registed model in dict
    model_dict = {}
    client = mlflow.tracking.MlflowClient()
    for mv in client.search_model_versions(f"name='{registered_model_name}'"):
        model_dict[dict(mv)['run_id']] = dict(mv)

    # Get run_id for Best model and Second best model
    model1_run_id = df_runs.at[0, 'run_id']
    model2_run_id = df_runs.at[1, 'run_id']

    # Get version from run_id
    model1_version = model_dict[model1_run_id]['version']
    model2_version = model_dict[model2_run_id]['version']

    # Push Best model to Production
    client.transition_model_version_stage(
        name=registered_model_name,
        version=int(model1_version),
        stage="Production")

    # Push Second best model to Staging
    client.transition_model_version_stage(
        name=registered_model_name,
        version=int(model2_version),
        stage="Staging")

    # Explicitly unstage every other versions
    unstage_versions = []
    for run_id in df_runs['run_id']:
        if run_id not in [model1_run_id, model2_run_id]:
            unstage_versions.append(model_dict[run_id]['version'])

    for version in unstage_versions:
        client.transition_model_version_stage(
            name=registered_model_name,
            version=int(version),
            stage="None")
