"""
sales_pipeline_dag.py
----------------------
Airflow DAG orchestrating the full ELT + ML pipeline on a daily
schedule, mirroring how this would run in production:

    extract -> load -> dbt build (transform + test) -> ml_forecast -> export_for_bi

Each task shells out to the corresponding script in /src and /ml, so
the orchestration layer stays a thin scheduler on top of code that's
independently runnable and testable (which is exactly how you'd want
to demo/debug it without spinning up the whole Airflow stack).

To run for real: `pip install apache-airflow`, drop this file in your
$AIRFLOW_HOME/dags folder (or docker-compose the official Airflow
image and mount ./airflow/dags), then trigger from the Airflow UI.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="ecommerce_sales_pipeline",
    description="Daily ELT pipeline: extract -> load -> dbt transform/test -> forecast -> BI export",
    default_args=default_args,
    schedule_interval="0 3 * * *",  # 3 AM daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ecommerce", "elt", "dbt", "ml"],
) as dag:

    extract = BashOperator(
        task_id="extract_source_data",
        bash_command="python {{ params.project_dir }}/src/extract.py",
        params={"project_dir": "/opt/airflow/project"},
    )

    load = BashOperator(
        task_id="load_raw_to_warehouse",
        bash_command="python {{ params.project_dir }}/src/load.py --engine duckdb",
        params={"project_dir": "/opt/airflow/project"},
    )

    dbt_build = BashOperator(
        task_id="dbt_build_and_test",
        bash_command=(
            "cd {{ params.project_dir }}/dbt_project && "
            "dbt build --profiles-dir . --target dev"
        ),
        params={"project_dir": "/opt/airflow/project"},
    )

    forecast = BashOperator(
        task_id="run_sales_forecast",
        bash_command="python {{ params.project_dir }}/ml/sales_forecast.py",
        params={"project_dir": "/opt/airflow/project"},
    )

    export_bi = BashOperator(
        task_id="export_for_powerbi",
        bash_command="python {{ params.project_dir }}/src/export_for_powerbi.py",
        params={"project_dir": "/opt/airflow/project"},
    )

    extract >> load >> dbt_build >> forecast >> export_bi
