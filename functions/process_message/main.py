import json
import time
import base64
from pathlib import Path
from google.cloud import bigquery
from google.cloud import error_reporting

error_client = error_reporting.Client()
client = bigquery.Client()

project_id = "environment-data"
dataset_id = "farm_one"


def process_message(message, context):
    print(f"Function triggered by messageId {context.event_id} published at {context.timestamp}")

    try:
        device_id = message["attributes"]["device_id"]
        device_type = message["attributes"]["device_type"]
        data = json.loads(base64.b64decode(message["data"]).decode("utf-8"))

        # Construct table name and path
        table_name = f"{device_id}_{device_type}"
        table_path = f"{project_id}.{dataset_id}.{table_name}"

        # Create table if does not exist
        start_time = time.time()
        tables = client.list_tables(dataset_id)
        table_names = [table.table_id for table in tables]
        print("=====================--- %s seconds ---" % (time.time() - start_time))
        if table_name not in table_names:
            dataset_ref = bigquery.DatasetReference(client.project, dataset_id)
            table_ref = dataset_ref.table(table_name)

            # Retrieve database schema for provided device_type
            schema_path = f"schemas/{device_type}.json"
            if Path(schema_path).exists():
                schema = client.schema_from_json(schema_path)
            else:
                raise Exception(f"No schema found for {device_type}")

            table = bigquery.Table(table_ref, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field="timestamp"
            )
            try:
                table = client.create_table(table)
            except Exception as e:
                print(e)

        if isinstance(data, list):
            data_expanded = [{"timestamp": row["ts"], "temperature": row["t"], "humidity": row["h"]} for row in data]
        else:
            data_expanded = [{"timestamp": data["ts"], "temperature": data["t"], "humidity": data["h"]}]

        for d_exp in data_expanded:
            print("=============", d_exp["temperature"])
        errors = client.insert_rows_json(table_path, data_expanded)
        if errors == []:
            print("New row has been added.")
        else:
            print("Encountered errors while inserting rows: {}".format(errors))
    except Exception as e:
        client.report_exception()
        print(e)