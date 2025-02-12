import datetime
from typing import Optional
from promptflow.core import tool
from jinja2 import Template

from helper_functions.fix_corrupted_json import fix_corrupted_json
from helper_functions.schema import PfOutputItem


@tool
def build_output_panel_specimen(
    segment_1_panel_specimen: str,
    segment_2_panel_specimen: str,
    standardize_panel_specimen: str,
    flow_dict: dict,
    connection_name: str,
    connection_model: str,
    data_source_key: str,
    run_batch_name: str,
    schema_name: str,
    model: Optional[str] = None,
    deployment_name: Optional[str] = None,
) -> dict:
    """Makes a dictionary with the output of the panel specimen and the prompts used to generate it."""

    # recreates the prompt for the segment
    with open(
        "segment_1_panel_specimen.jinja2",
        "r",
        encoding="utf-8",
    ) as f:
        template = Template(f.read())
    segmentation_1_prompt = template.render(
        report_text=flow_dict["report_text"],
        panel=flow_dict["panel"],
        panel_test_names=flow_dict["panel_test_names"],
        panel_test_results=flow_dict["panel_test_results"],
        panel_test_synonyms=flow_dict["panel_test_synonyms"],
        segment_1_panel_instructions=flow_dict["segment_1_panel_instructions"],
    )
    segmentation_2_prompt = template.render(
        report_text=flow_dict["report_text"],
        panel=flow_dict["panel"],
        segment_2_panel_instructions=flow_dict["segment_2_panel_instructions"],
        segment_1_panel_specimen_output=segment_1_panel_specimen,
    )

    # recreates the prompt for the standardize feature report
    with open(
        "standardize_panel_specimen.jinja2",
        "r",
        encoding="utf-8",
    ) as f:
        template = Template(f.read())
    standardization_prompt = template.render(
        report_text=flow_dict["report_text"],
        segment_2_panel_specimen_output=segment_2_panel_specimen,
        panel=flow_dict["panel"],
        panel_test_names=flow_dict["panel_test_names"],
        panel_test_results=flow_dict["panel_test_results"],
        panel_test_synonyms=flow_dict["panel_test_synonyms"],
        standardize_panel_instructions=flow_dict["standardize_panel_instructions"],
    )

    # output_item = PfOutputItem(
    #     report_id=flow_dict["report_id"],
    #     intermediate_json_key=flow_dict["intermediate_json_key"],
    #     segment_feature_report_output=segment_feature_report,
    #     standardized_output=standardize_feature_report,
    #     item_name=flow_dict["feature"],
    #     item_type_coverage="feature_report",
    #     created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #     deployment_name=deployment_name,
    # )
    json_result_key = f"{data_source_key}_{run_batch_name}"

    output_item = PfOutputItem(
        report_id=flow_dict["report_id"],
        data_source_key=data_source_key,
        json_result_key=json_result_key,
        item_type_coverage="panel_specimen",
        item_name=flow_dict["panel"],
        created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        schema_name=schema_name,
        run_batch_name=run_batch_name,
        connection_name=connection_name,
        connection_model=connection_model,
        model=model,
        deployment_name=deployment_name,
        segment_1_panel_specimen_output={
            "output": fix_corrupted_json(segment_1_panel_specimen),
            "prompt": segmentation_1_prompt,
        },
        segment_2_panel_specimen_output={
            "output": fix_corrupted_json(segment_2_panel_specimen),
            "prompt": segmentation_2_prompt,
        },
        standardized_output={
            "output": fix_corrupted_json(standardize_panel_specimen),
            "prompt": standardization_prompt,
        },
    )
    output_dict = output_item.model_dump()

    return output_dict
