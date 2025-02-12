import datetime
from typing import Optional
from promptflow.core import tool
from jinja2 import Template

from helper_functions.fix_corrupted_json import fix_corrupted_json
from helper_functions.schema import PfOutputItem


@tool
def build_output_feature_report(
    segment_feature_report: str,
    standardize_feature_report: str,
    flow_dict: dict,
    connection_name: str,
    connection_model: str,
    data_source_key: str,
    run_batch_name: str,
    schema_name: str,
    model: Optional[str] = None,
    deployment_name: Optional[str] = None,
) -> dict:
    """Makes a dictionary with the output of the feature report and the prompts used to generate it."""

    # recreates the prompt for the segment feature report
    with open(
        "segment_feature_specimen.jinja2",
        "r",
        encoding="utf-8",
    ) as f:
        template = Template(f.read())
    segmentation_prompt = template.render(
        report_text=flow_dict["report_text"],
        feature=flow_dict["feature"],
        feature_labels=flow_dict["feature_labels"],
        segment_feature_instructions=flow_dict["segment_feature_instructions"],
    )

    # recreates the prompt for the standardize feature report
    with open(
        "standardize_feature_specimen.jinja2",
        "r",
        encoding="utf-8",
    ) as f:
        template = Template(f.read())
    standardization_prompt = template.render(
        segment_feature_report_output=segment_feature_report,
        feature=flow_dict["feature"],
        feature_labels=flow_dict["feature_labels"],
        standardize_feature_instructions=flow_dict["standardize_feature_instructions"],
    )

    json_result_key = f"{data_source_key}_{run_batch_name}"

    output_item = PfOutputItem(
        report_id=flow_dict["report_id"],
        data_source_key=data_source_key,
        json_result_key=json_result_key,
        item_type_coverage="feature_specimen",
        item_name=flow_dict["feature"],
        schema_name=schema_name,
        created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        run_batch_name=run_batch_name,
        connection_name=connection_name,
        connection_model=connection_model,
        model=model,
        deployment_name=deployment_name,
        segment_feature_specimen_output={
            "output": fix_corrupted_json(segment_feature_report),
            "prompt": segmentation_prompt,
        },
        standardized_output={
            "output": fix_corrupted_json(standardize_feature_report),
            "prompt": standardization_prompt,
        },
    )
    output = output_item.model_dump()
    return output
