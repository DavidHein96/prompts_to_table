""" Helper for getting the JSON outputs so that you can check out the reasoning section and also useful for debugging. """

import pandas as pd

from promptflow.client import PFClient
from promptflow.entities import Run


def get_json_outputs(pf_client: PFClient, flow_result: Run) -> pd.Series:
    """Gets only the JSON outputs from the flow

    Args:
        pf_client (PFClient): Promptflow client
        flow_result (Run): Run object from the promptflow client

    Returns:
        json_outputs: A pandas series of the JSON outputs
    """
    json_outputs = pf_client.get_details(flow_result)["outputs.json_items"]
    return json_outputs
