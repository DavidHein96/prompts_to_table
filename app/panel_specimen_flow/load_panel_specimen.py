import json
from promptflow.core import tool

from helper_functions.schema import ReportSchema


@tool
def load_panel_specimen(
    report_text: str,
    report_id: str,
    schema_name: str,
    item_name: str,
    item_type_coverage="panel_specimen",
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

    relevant_schema = full_schema.panel_specimen[item_name].model_dump()

    try:
        flow_dict = {
            "report_id": report_id,
            "report_text": report_text,
            "panel": item_name,
            "panel_test_names": json.dumps(relevant_schema["panel_test_names"]),
            "panel_test_results": json.dumps(relevant_schema["panel_test_results"]),
            "panel_test_synonyms": json.dumps(relevant_schema["panel_test_names"]),
            "segment_1_panel_instructions": json.dumps(
                relevant_schema["segment_1_panel_instructions"]
            ),
            "segment_2_panel_instructions": json.dumps(
                relevant_schema["segment_2_panel_instructions"]
            ),
            "standardize_panel_instructions": json.dumps(
                relevant_schema["standardize_panel_instructions"]
            ),
            "item_type_coverage": item_type_coverage,
        }
    # raise the error with extra info on which key was not found or incorrect
    except KeyError as exc:
        raise ValueError("Key not found") from exc

    return flow_dict
