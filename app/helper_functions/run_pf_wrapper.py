""" Wrapper for running batch jobs with promptflow, including creating connections and handling intermediate data """

import os
from typing import Literal
import logging
import json

from pydantic import FilePath
from promptflow.client import PFClient
from promptflow.entities import AzureOpenAIConnection, OpenAIConnection, Run
import dotenv

from app.helper_functions.schema import ReportSchema
from app.helper_functions.prep_data import prep_data

# this is needed to return more stuff in the pf result object
column_mapping = {
    "report_text": "${data.report_text}",
    "report_id": "${data.report_id}",
    "schema_name": "${data.schema_name}",
    "item_type_coverage": "${data.item_type_coverage}",
    "item_name": "${data.item_name}",
    "data_source_key": "${data.data_source_key}",
    "run_batch_name": "${data.run_batch_name}",
    "connection_name": "${data.connection_name}",
    "connection_model": "${data.connection_model}",
    "model": "${data.model}",
    "deployment_name": "${data.deployment_name}",
}

flow_directory_mapping = {
    "feature_report": "app/feature_report_flow",
    "feature_specimen": "app/feature_specimen_flow",
    "panel_specimen": "app/panel_specimen_flow",
}

# this is needed so we can over ride the connections for all nodes in the flow
flow_node_mapping = {
    "feature_report": [
        "segment_feature_report",
        "standardize_feature_report",
    ],
    "feature_specimen": [
        "segment_feature_specimen",
        "standardize_feature_specimen",
    ],
    "panel_specimen": [
        "segment_1_panel_specimen",
        "segment_2_panel_specimen",
        "standardize_panel_specimen",
    ],
}


def _get_item_type_coverage(
    schema_path: FilePath, item_name: str
) -> Literal["feature_report", "feature_specimen", "panel_specimen"]:
    """Auto loads the item type coverage based on the schema file and the requested item name"""
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
    try:
        schema.feature_report[item_name]
        return "feature_report"
    except KeyError:
        pass
    try:
        schema.feature_specimen[item_name]
        return "feature_specimen"
    except KeyError:
        pass
    try:
        schema.panel_specimen[item_name]
        return "panel_specimen"
    except KeyError:
        raise KeyError(f"Item name {item_name} not found in schema")


def _create_or_update_connections(
    pf_client: PFClient, connection_name: str, connection_model: str
) -> str:
    """Helps create or update connections based on the env vars"""

    # expects a .env, but exported env vars can also be used it will just give a warning if no .env is found
    dotenv.load_dotenv(verbose=True)

    api_type = os.getenv(f"{connection_name.upper()}_API_TYPE")

    if api_type == "azure":
        connection = AzureOpenAIConnection(
            name=connection_name,
            api_key=os.getenv(f"{connection_name.upper()}_API_KEY"),
            api_base=os.getenv(f"{connection_name.upper()}_API_BASE"),
            api_type=os.getenv(f"{connection_name.upper()}_API_TYPE"),
            api_version=os.getenv(f"{connection_name.upper()}_API_VERSION"),
        )
        result = pf_client.connections.create_or_update(connection)
    elif api_type == "openai":
        connection = OpenAIConnection(
            name=connection_name,
            model=connection_model,
            api_key=os.getenv(f"{connection_name.upper()}_API_KEY"),
            base_url=os.getenv(f"{connection_name.upper()}_API_BASE"),
        )
        result = pf_client.connections.create_or_update(connection)
    else:
        raise ValueError(
            "Invalid API type. Supports 'azure' and 'openai'. The openai api type can be used with vllm"
        )
    logging.info(f"Connection {connection_name} created or updated. {result}")
    return api_type


def _build_connection_override(
    connection_name: str, connection_model: str, api_type: str, item_type_coverage: str
) -> dict:
    """Sets up the promptflow connection overide so the requested connection is used for the batch job"""
    if api_type == "openai":
        connection_override = {
            node_name: {"connection": connection_name, "model": connection_model}
            for node_name in flow_node_mapping[item_type_coverage]
        }
    else:
        connection_override = {
            node_name: {
                "connection": connection_name,
                "deployment_name": connection_model,
            }
            for node_name in flow_node_mapping[item_type_coverage]
        }
    return connection_override


def pf_batch_run_wrapper(
    pf_client: PFClient,
    data_path: FilePath,
    schema_path: FilePath,
    item_name: str,
    connection_name: str,
    connection_model: str,
    flush_intermediate_data: bool = True,
) -> Run:
    """Wrapper for running batch jobs with promptflow, including creating connections and handling intermediate data

    Args:
        pf_client (PFClient): a pf client object returned from PFClient()
        data_path (FilePath): Path to either a CSV or JSONL file. The data needs to contain a report_id and report_text column/field.
        schema_path (FilePath): Path to a JSON schema file
        item_name (str): Name of the item to be processed, should be a key under one of the item types in the schema
        connection_name (str): Name of the connection to be used as per the .env file
        connection_model (str): Name of the model OR deployment to be used. Azure uses deployment, OpenAI uses model
        flush_intermediate_data (bool, optional): The intermediate data that is passed to pf.run is deleted by default, but it is interesting to look at and can also be used for debugging. If set to false it will be under app/tmp. Importantly there is a gitignore there so data wont be checked into code version control. Defaults to True.

    Raises:
        e: Passes on any exceptions that occur during the run
    Returns:
        Run: A promptflow run object that contains the results of the run. This can then be passed to flatten_outputs() to get the results in a nice organized CSV with one row per entity. The number of rows will depend on the entity type and report contents.
    """

    item_type_coverage = _get_item_type_coverage(schema_path, item_name)

    api_type = _create_or_update_connections(
        pf_client, connection_name, connection_model
    )

    connection_override = _build_connection_override(
        connection_model=connection_model,
        connection_name=connection_name,
        api_type=api_type,
        item_type_coverage=item_type_coverage,
    )

    try:
        tmp_dir = "app/tmp"
        os.makedirs(tmp_dir, exist_ok=True)
        intermediate_data = prep_data(
            data_path=data_path,
            schema_path=schema_path,
            item_type_coverage=item_type_coverage,
            item_name=item_name,
            connection_name=connection_name,
            connection_model=connection_model,
            api_type=api_type,
        )
        flow_result = pf_client.run(
            flow=flow_directory_mapping[item_type_coverage],
            data=intermediate_data,
            column_mapping=column_mapping,
            connections=connection_override,
        )
    except Exception as e:
        logging.error(f"Error running the flow: {e}")
        raise e
    finally:
        # delete the temp file by default, but can be set to False if needed for debugging or if you are just curious
        if flush_intermediate_data:
            try:
                os.remove(intermediate_data)
            except UnboundLocalError:
                raise UnboundLocalError(
                    "The intermediate data file was not created. A common cause of this is the data or schema not being found at the provided path."
                )
        print("All done! Check out the results in the flow_result object")

    return flow_result
