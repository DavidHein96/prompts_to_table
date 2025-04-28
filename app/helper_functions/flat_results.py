"""Helps format the outputs of a flow run into a flat dataframe, one row per entity."""

import pandas as pd
from pydantic import computed_field

from promptflow.client import PFClient
from promptflow.entities import Run
from app.helper_functions.schema import FlatResultsRow

# expected columns in the output of the flow run
output_colnames = [
    "inputs.report_text",
    "inputs.report_id",
    "inputs.schema_name",
    "inputs.item_type_coverage",
    "inputs.item_name",
    "inputs.data_source_key",
    "inputs.run_batch_name",
    "inputs.connection_name",
    "inputs.connection_model",
    "inputs.model",
    "inputs.deployment_name",
    "inputs.line_number",
    "outputs.json_items",
]


class FlatFeatureReportConstructor(FlatResultsRow):
    pass


class FlatFeatureSpecimenConstructor(FlatResultsRow):
    @computed_field
    def specimen(self) -> str:
        return self.full_item_name.split("_")[1]


class FlatPanelSpecimenConstructor(FlatResultsRow):
    @computed_field
    def specimen(self) -> str:
        return self.full_item_name.split("_")[1]

    @computed_field
    def block(self) -> str:
        return self.full_item_name.split("_")[3]

    @computed_field
    def test_name(self) -> str:
        return self.full_item_name.split("_")[4]


result_type_to_flat_map = {
    "feature_report": FlatFeatureReportConstructor,
    "feature_specimen": FlatFeatureSpecimenConstructor,
    "panel_specimen": FlatPanelSpecimenConstructor,
}


def extract_item(row: pd.Series, pf_run_name: str) -> list[FlatResultsRow]:
    """_summary_

    Args:
        row (pd.Series): Row from the dataframe returned by the pf_client.get_details(flow_result) call
        pf_run_name (str): Name of the flow run that promptflow auto generates

    Returns:
        list (FlatResultsRow): list of FlatResultsRow objects, one for each entity in the output
    """

    dict_output = row["outputs.json_items"]["standardized_output"]["output"]
    item_type_coverage = row["inputs.item_type_coverage"]

    # NOTE: Note here that the result of the promptflow is a dictionary under the key "json_items"
    created_at = row["outputs.json_items"]["created_at"]

    results_typed = []
    for result_key, result_value in dict_output.items():
        if result_key == "reasoning_summary":
            continue
        result = (result_key, result_value)
        flat_result = result_type_to_flat_map[item_type_coverage](
            report_id=row["inputs.report_id"],
            item_name=row["inputs.item_name"],
            item_label=str(result[1]),
            full_item_name=result[0],
            item_type_coverage=item_type_coverage,
            schema_name=row["inputs.schema_name"],
            connection_name=row["inputs.connection_name"],
            connection_model=row["inputs.connection_model"],
            data_source_key=row["inputs.data_source_key"],
            pf_line_number=row["inputs.line_number"],
            created_at=created_at,
            pf_flow_result_name=pf_run_name,
        )

        results_typed.append(flat_result)

    return results_typed


def flatten_outputs(pf_client: PFClient, flow_result: Run) -> pd.DataFrame:
    """Takes in a flow result and returns a dataframe with the outputs flattened, one row per individual entity.

    Args:
        pf_client (PFClient): A PFClient instance created in the main code
        flow_result (Run): A flow result object, returend from either the pf flow wrapper or pf_client.runs.get(<name of the flow run>)

    Returns:
        pd.DataFrame: Dataframe with the outputs flattened, one row per individual entity. For feature reports this will be one row per report, for feature specimens one row per specimen, and for panel specimens one row per assay/test result
    """

    pf_run_name = flow_result.name

    df = pd.DataFrame(pf_client.get_details(flow_result, all_results=True))

    required_c = set(output_colnames)
    df_c = set(df.columns)

    assert df_c.issuperset(required_c)

    outputs = []
    for index, row in df.iterrows():
        if row["outputs.json_items"] == "(Failed)":
            print(f"Failed row: {row}")

        out_list = extract_item(row, pf_run_name)
        for out in out_list:
            out_series = pd.Series(out.model_dump())
            outputs.append(out_series)
    return pd.DataFrame(outputs)
