""" This module contains functions to prepare and validate the data/schema for the promptflow. """

from pathlib import Path

from typing import Literal
import json
from datetime import datetime
import logging

import pandas as pd
from pydantic import FilePath, DirectoryPath

from app.helper_functions.schema import ReportSchema, PfInputItem


def _load_and_validate_dataframe(data_path: FilePath) -> pd.DataFrame:

    # get file extension
    source = str(data_path).split(".")[-1]

    # read the data file
    if source == "csv":
        data = pd.read_csv(data_path)
    elif source == "jsonl":
        data = pd.read_json(data_path, lines=True)
    else:
        raise ValueError("Invalid data source format. Please use a 'csv' or 'jsonl'.")
    # check for the required columns
    if not all([col in data.columns for col in ["report_id", "report_text"]]):
        raise ValueError(
            "The data source must contain the columns 'report_id' and 'report_text'."
        )

    # check that the report_id and report_text columns contain strings
    if not all(
        [
            isinstance(row["report_id"], str) and isinstance(row["report_text"], str)
            for index, row in data.iterrows()
        ]
    ):
        raise ValueError(
            "The 'report_id' and 'report_text' columns must contain strings for all rows/values."
        )

    # check for duplicate report_ids
    if data["report_id"].duplicated().any():
        logging.warning("Duplicate report_ids found in the data source.")

    return data


def _load_and_validate_schema(
    schema_path: FilePath, item_type_coverage: str, item_name: str
) -> ReportSchema:

    # read the schema file
    try:
        with open(schema_path, "r") as file:
            schema = json.load(file)
    except Exception as e:
        raise ValueError("Invalid schema file.") from e

    try:
        schema = ReportSchema(**schema)
    except Exception as e:
        raise ValueError("Invalid schema file.") from e

    # ensure that the schema contains the keys for the entity type
    if item_type_coverage not in schema.model_dump().keys():
        raise ValueError(f"The schema must contain the key '{item_type_coverage}'.")

    # ensure that the entity name is in the schema under the entity type
    if item_name not in schema.model_dump()[item_type_coverage].keys():
        raise ValueError(
            f"The schema must contain the key '{item_name}' under '{item_type_coverage}'."
        )

    return schema


def prep_data(
    data_path: FilePath,
    schema_path: FilePath,
    item_type_coverage: str,
    item_name: str,
    connection_name: str,
    connection_model: str,
    api_type: Literal["azure", "openai"],
    output_path: DirectoryPath = "app/tmp",
) -> FilePath:
    """We write the prepared data to a JSONL as input into pf.run()"""

    data = _load_and_validate_dataframe(data_path)

    _load_and_validate_schema(schema_path, item_type_coverage, item_name)

    # iterate through the rows of the data
    input_items = []
    schmea_name = str(schema_path).split("/")[-1].split(".")[0]
    data_name = str(data_path).split("/")[-1].split(".")[0]

    # generate a run batch name
    date_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    run_batch_name = f"{data_name}_{schmea_name}_{connection_name}_{connection_model}_{item_type_coverage}_{item_name}_{date_time}"

    for index, row in data.iterrows():

        # generate an intermediate json key
        data_source_key = f"{data_name}_{row['report_id']}"

        if api_type == "azure":
            deployment_name = connection_model
            model = None
        else:
            deployment_name = None
            model = connection_model

        input_item = PfInputItem(
            report_text=row["report_text"],
            report_id=row["report_id"],
            data_source_key=data_source_key,
            run_batch_name=run_batch_name,
            item_type_coverage=item_type_coverage,
            item_name=item_name,
            schema_name=schmea_name,
            connection_name=connection_name,
            connection_model=connection_model,
            deployment_name=deployment_name,
            model=model,
        )
        input_items.append(input_item.model_dump())

    output_file = Path(output_path) / f"{run_batch_name}_intermediate.jsonl"
    # we write the prepared data to a temp file
    with open(f"{output_file}", "w") as f:
        for item in input_items:
            f.write(json.dumps(item) + "\n")

    return output_file
