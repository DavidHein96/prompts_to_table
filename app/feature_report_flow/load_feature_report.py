import json
from promptflow.core import tool

from helper_functions.schema import ReportSchema


@tool
def load_feature_report(
    report_text: str,
    report_id: str,
    schema_name: str,
    item_name: str,
    item_type_coverage="feature_report",
) -> dict:
    """Creates a dictionary containing items that are needed by the LLM nodes.
    The items are used to generate the input prompts via jinja templates.
    """

    try:
        with open(f"schemas/{schema_name}.json", "r") as file:
            full_schema = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON") from exc

    full_schema = ReportSchema(**full_schema)

    relevant_schema = full_schema.feature_report[item_name].model_dump()

    try:
        flow_dict = {
            "report_id": report_id,
            "report_text": report_text,
            "feature": item_name,
            "feature_labels": json.dumps(relevant_schema["feature_labels"]),
            "segment_feature_instructions": json.dumps(
                relevant_schema["segment_feature_instructions"]
            ),
            "standardize_feature_instructions": json.dumps(
                relevant_schema["standardize_feature_instructions"]
            ),
            "item_type_coverage": item_type_coverage,
        }
    # raise the error with extra info on which key was not found or incorrect
    except KeyError as exc:
        raise ValueError("Key not found") from exc

    return flow_dict
