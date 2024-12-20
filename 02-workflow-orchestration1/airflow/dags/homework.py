import os
import logging

from datetime import datetime

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from google.cloud import storage
from airflow.providers.google.cloud.operators.bigquery import BigQueryCreateExternalTableOperator
import pyarrow.csv as pv
import pyarrow.parquet as pq

PROJECT_ID = 'dtc-de-course-439003'
BUCKET = 'dtc-de-course-439003-gcs-bucket'
AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")

def format_to_parquet(src_file, dest_file):
    if not src_file.endswith('.csv'):
        logging.error("Can only accept source files in CSV format, for the moment")
        return
    table = pv.read_csv(src_file)
    pq.write_table(table, dest_file)


def upload_to_gcs(bucket, object_name, local_file):
    storage.blob._MAX_MULTIPART_SIZE = 5 * 1024 * 1024  # 5 MB
    storage.blob._DEFAULT_CHUNKSIZE = 5 * 1024 * 1024  # 5 MB

    client = storage.Client()
    bucket = client.bucket(bucket)

    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_file)


default_args = {
    "owner": "airflow",
    #"start_date": days_ago(1),
    "depends_on_past": False,
    "retries": 1,
}

def download_upload_dag(
    dag,
    url_template,
    local_path_template,
    gcs_path_template
):
    with dag:
        dowload_dataset_task = BashOperator(
            task_id="download_dataset_task",
            bash_command=f"curl -sSL {url_template} > {local_path_template}"
        )
        
        local_to_gcs_task = PythonOperator(
            task_id="local_to_gcs_task",
            python_callable=upload_to_gcs,
            op_kwargs={
                "bucket": BUCKET,
                "object_name": gcs_path_template,
                "local_file": local_path_template,
            },
        )
        
        
        rm_task = BashOperator(
            task_id="rm_task",
            bash_command=f"rm {local_path_template}"
        )
        
        dowload_dataset_task >> local_to_gcs_task >> rm_task
        
def download_parquetize_upload_dag(
    dag,
    url_template,
    local_csv_path_template,
    local_parquet_path_template,
    gcs_path_template
):
    with dag:
        dowload_dataset_task = BashOperator(
            task_id="download_dataset_task",
            bash_command=f"curl -sSL {url_template} > {local_csv_path_template}"
        )
        
        format_to_parquet_task = PythonOperator(
            task_id="format_to_parquet",
            python_callable=format_to_parquet,
            op_kwargs={
                "src_file": local_csv_path_template,
                "dest_file": local_parquet_path_template
            }
        )
        
        local_to_gcs_task = PythonOperator(
            task_id="local_to_gcs_task",
            python_callable=upload_to_gcs,
            op_kwargs={
                "bucket": BUCKET,
                "object_name": gcs_path_template,
                "local_file": local_parquet_path_template,
            },
        )
        
        
        rm_task = BashOperator(
            task_id="rm_task",
            bash_command=f"rm {local_parquet_path_template} {local_csv_path_template}"
        )
        
        dowload_dataset_task >> format_to_parquet_task >> local_to_gcs_task >> rm_task

URL_PREFIX = 'https://d37ci6vzurychx.cloudfront.net/trip-data'

YELLOW_TAXI_URL_TEMPLATE = URL_PREFIX + '/yellow_tripdata_{{ execution_date.strftime(\'%Y-%m\') }}.parquet'
YELLOW_TAXI_OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + '/yellow_tripdata_{{ execution_date.strftime(\'%Y-%m\') }}.parquet'
YELLOW_TAXI_GCS_PATH_TEMPLATE = "raw/yellow_tripdata/{{ execution_date.strftime(\'%Y\') }}/yellow_tripdata_{{ execution_date.strftime(\'%Y-%m\') }}.parquet"

yellow_taxi_data_dag = DAG(
    dag_id="yellow_taxi_data_dag",
    schedule_interval="0 6 2 * *",
    start_date=datetime(2019, 1, 1),
    end_date=datetime(2020, 12, 31),
    default_args=default_args,
    catchup=True,
    max_active_runs=3,
    tags=['dtc-de'],
    )    
        
download_upload_dag(
    yellow_taxi_data_dag,
    url_template=YELLOW_TAXI_URL_TEMPLATE,
    local_path_template=YELLOW_TAXI_OUTPUT_FILE_TEMPLATE,
    gcs_path_template=YELLOW_TAXI_GCS_PATH_TEMPLATE
)

#https://d37ci6vzurychx.cloudfront.net/trip-data/fhv_tripdata_2020-01.parquet

FHV_URL_TEMPLATE = URL_PREFIX + '/fhv_tripdata_{{ execution_date.strftime(\'%Y-%m\') }}.parquet'
FHV_OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + '/fhv_tripdata_{{ execution_date.strftime(\'%Y-%m\') }}.parquet'
FHV_GCS_PATH_TEMPLATE = "raw/fhv_tripdata/{{ execution_date.strftime(\'%Y\') }}/fhv_tripdata_{{ execution_date.strftime(\'%Y-%m\') }}.parquet"

fhv_data_dag = DAG(
    dag_id="fhv_data_dag",
    schedule_interval="0 6 2 * *",
    start_date=datetime(2019, 1, 1),
    end_date=datetime(2020, 12, 31),
    default_args=default_args,
    catchup=True,
    max_active_runs=3,
    tags=['dtc-de'],
    )    
        
download_upload_dag(
    fhv_data_dag,
    url_template=FHV_URL_TEMPLATE,
    local_path_template=FHV_OUTPUT_FILE_TEMPLATE,
    gcs_path_template=FHV_GCS_PATH_TEMPLATE
)

#https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv

ZONE_URL_TEMPLATE = 'https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv'
ZONE_CSV_OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + '/zone_data_{{ execution_date.strftime(\'%Y-%m\') }}.csv'
ZONE_PARQUET_OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + '/zone_data_{{ execution_date.strftime(\'%Y-%m\') }}.parquet'
ZONE_GCS_PATH_TEMPLATE = "raw/zone_data/{{ execution_date.strftime(\'%Y\') }}/zone_data_{{ execution_date.strftime(\'%Y-%m\') }}.parquet"

zone_data_dag = DAG(
    dag_id="zone_data_dag",
    schedule_interval="@daily",
    start_date=days_ago(1),
    default_args=default_args,
    catchup=False,
    max_active_runs=1,
    tags=['dtc-de'],
    )    
        
download_parquetize_upload_dag(
    zone_data_dag,
    url_template=ZONE_URL_TEMPLATE,
    local_csv_path_template=ZONE_CSV_OUTPUT_FILE_TEMPLATE,
    local_parquet_path_template=ZONE_PARQUET_OUTPUT_FILE_TEMPLATE,
    gcs_path_template=ZONE_GCS_PATH_TEMPLATE
)