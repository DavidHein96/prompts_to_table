"""Wrapper for running batch jobs with promptflow, including creating connections and handling intermediate data"""

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

# This mapping defines the columns in the output of the flow run.
# It helps pass along all of the inputs
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

# This allows us to map the item type coverage to the flow directory
flow_directory_mapping = {
    "feature_report": "app/feature_report_flow",
    "feature_specimen": "app/feature_specimen_flow",
    "panel_specimen": "app/panel_specimen_flow",
}

# This is needed so we can over ride the connections for all nodes in the flow at run time
# This is extra important for switching between azure and openai (vllm) as we have to provide the model name
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


class PromptFlowExecutionError(Exception):
    """Custom exception for errors detected during PromptFlow execution analysis. This helps raise the error to the jupyter notebook"""

    def __init__(self, message, run_result=None):
        super().__init__(message)
        self.run_result = run_result


def _get_item_type_coverage(
    schema_path: FilePath, item_name: str
) -> Literal["feature_report", "feature_specimen", "panel_specimen"]:
    """Auto loads the item type coverage based on the schema file and the requested item name.
    Basically so you dont have to remember anything more than the item name and can just pass that at run time
    """

    try:
        with open(schema_path, "r") as file:
            schema = json.load(file)
    except Exception as e:
        raise ValueError("Invalid schema file.") from e

    try:
        schema = ReportSchema(**schema)
    except Exception as e:
        raise ValueError("Invalid schema file.") from e

    # Ensure that the schema contains the keys for the entity type
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
    """Helps create or update connections based on the env vars
    NOTE: This is set up to use the openai connection in the context of vllm"""

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
            name=os.getenv(f"{connection_name.upper()}_NAME"),
            model=connection_model,
            api_key=os.getenv(f"{connection_name.upper()}_API_KEY"),
            base_url=os.getenv(f"{connection_name.upper()}_BASE_URL"),
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
    """Sets up the promptflow connection overide so the requested connection is used for the batch job."""
    if api_type == "openai":
        connection_override = {
            node_name: {
                "connection": connection_model,
                "model": connection_model,
                "deployment_name": connection_model,
            }
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
    pf_worker_count: int = 4,
    flush_intermediate_data: bool = True,
    csv_to_filter: FilePath = None,
) -> Run:
    """Wrapper for running batch jobs with promptflow, including creating connections and handling intermediate data

    Args:
        pf_client (PFClient): a pf client object returned from PFClient()
        data_path (FilePath): Path to either a CSV or JSONL file. The data needs to contain a report_id and report_text column/field.
        schema_path (FilePath): Path to a JSON schema file
        item_name (str): Name of the item to be processed, should be a key under one of the item types in the schema
        connection_name (str): Name of the connection to be used as per the .env file
        connection_model (str): Name of the model OR deployment to be used. Azure uses deployment, OpenAI uses model
        pf_worker_count (int, optional): Number of workers to use for the batch job. Defaults to 4.
        flush_intermediate_data (bool, optional): The intermediate data that is passed to pf.run is deleted by default, but it is interesting to look at and can also be used for debugging. If set to false it will be under app/tmp. Importantly there is a gitignore there so data wont be checked into code version control. Defaults to True.
        csv_to_filter (FilePath, optional): Path to a CSV file to filter the data by report_id. Defaults to None.


    Raises:
        e: Passes on any exceptions that occur during the run. There is a lot of extra error handling here to help with debugging
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

    environmental_variables = {
        "PF_WORKER_COUNT": str(pf_worker_count),
    }

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
            csv_to_filter=csv_to_filter,
        )

        # Ensure intermediate_data is not None or empty before proceeding
        if not intermediate_data or not os.path.exists(intermediate_data):
            # Handle case where prep_data might return None or an invalid path without raising an exception
            raise ValueError(
                "Intermediate data preparation failed or produced no file."
            )

        print(f"Running PromptFlow job for item '{item_name}'...")  # Indicate start
        flow_result = pf_client.run(
            flow=flow_directory_mapping[item_type_coverage],
            data=intermediate_data,
            column_mapping=column_mapping,
            connections=connection_override,
            environmental_variables=environmental_variables,
        )
    except Exception as e:
        logging.error(f"Error running the flow: {e}")
        raise e
    else:
        # This block runs ONLY if pf_client.run completed without raising a Python exception.
        # Prompflow can still fail internally and not raise an exception or halt execution, so we need to check the result.
        # Now, inspect the returned 'flow_result' for the *actual execution status*.
        if flow_result is None:
            # This case should ideally not happen if try succeeded.
            logging.error("PromptFlow run call completed but returned None.")
            raise PromptFlowExecutionError(
                "PromptFlow run failed unexpectedly (returned None)."
            )

        # --- Check the status of the Promptflow Run object ---
        # Adjust attribute names based on the actual Run object structure!
        run_status = getattr(flow_result, "status", "Unknown")
        lines_failed = 0
        lines_total = 0
        lines_completed = 0
        try:
            if hasattr(flow_result, "properties") and flow_result.properties:
                # NOTE: This location of the metrics could change based on the PromptFlow version.
                # This is version 1.17.1
                metrics = flow_result.properties.get("system_metrics", {})
                lines_failed = metrics.get("__pf__.lines.failed", 0)
                lines_completed = metrics.get("__pf__.lines.completed", 0)
                lines_total = lines_completed + lines_failed

        except Exception as metrics_err:
            logging.warning(
                f"Could not retrieve detailed metrics for run {getattr(flow_result, 'name', 'unknown')}: {metrics_err}"
            )
            # Proceed based on status alone if metrics fail

        # Determine final success: Status must be 'Completed' AND no lines failed, AND at least one line processed
        is_successful_run = (
            run_status == "Completed" and lines_failed == 0 and lines_total > 0
        )

        if is_successful_run:
            print(
                f"Successfully completed PromptFlow job for item '{item_name}'! Status: {run_status}, Processed: {lines_completed}/{lines_total}, Failed: {lines_failed}. Check results in flow_result object."
            )
        else:
            # Log failure details and raise a specific exception
            error_message = (
                f"PromptFlow job for item '{item_name}' finished with issues. "
                f"Status: {run_status}, Processed: {lines_completed}/{lines_total}, Failed: {lines_failed}. "
                f"Run ID: {getattr(flow_result, 'name', 'unknown')}"
            )
            logging.error(error_message)
            print(error_message)  # Also print to console for visibility
            # Raise a specific error to signal the failure clearly to the caller
            raise PromptFlowExecutionError(error_message, run_result=flow_result)

    finally:
        # This block runs ALWAYS, for cleanup.
        # Delete the temp file by default, but can be set to False if needed
        if flush_intermediate_data and intermediate_data:
            try:
                if os.path.exists(intermediate_data):
                    os.remove(intermediate_data)
                    print(f"Cleaned up intermediate data file: {intermediate_data}")
                else:
                    # This case might happen if prep_data succeeded logically but the file disappeared somehow
                    print(
                        f"Intermediate data file not found for cleanup: {intermediate_data}"
                    )
            except OSError as rm_err:
                # Catch potential errors during file removal (e.g., permissions)
                logging.warning(
                    f"Could not remove intermediate data file {intermediate_data}: {rm_err}"
                )
            except Exception as clean_err:  # Catch other unexpected cleanup errors
                logging.warning(
                    f"An unexpected error occurred during cleanup of {intermediate_data}: {clean_err}"
                )
        elif flush_intermediate_data and not intermediate_data:
            # This handles the case where an error occurred *before* intermediate_data was assigned
            # The UnboundLocalError case you handled previously is covered by initializing intermediate_data=None
            logging.warning(
                "Intermediate data file was not created or its path was lost; skipping cleanup."
            )

    # This return statement is only reached if:
    # 1. The try block succeeded (flow_result is assigned).
    # 2. An exception occurred, was caught, and *not* re-raised (which isn't the case here, as we do re-raise).
    # If an exception is raised in 'try' and re-raised in 'except', the function exits via the exception,
    # and this return statement is effectively skipped.
    if flow_result is None:
        # This condition helps catch unexpected control flow where an error might have occurred
        # but wasn't properly raised, or if flow somehow completed without assigning flow_result.
        # Depending on desired behavior, you might raise an error here or return None explicitly.
        logging.error("Flow execution finished, but no result object was generated.")
        # raise RuntimeError("Flow completed without generating a result object.") # Option: raise an error
        return None  # Option: return None

    return flow_result
