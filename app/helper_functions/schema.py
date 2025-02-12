""" Defines some basic classes for organizing data flow and validating the extraction schema """

from typing import Optional, Literal, Union
from pydantic import BaseModel


class Item(BaseModel):
    """
    Base class for an item to be extracted from a report.

    item_coverage: Whether the item pertains to a report
    as a whole or to individual specimens.

    item_type: Whether the item is a feature or a panel. A feature only has one label,
    while a panel could contain many tests each with its own result.
    """

    item_coverage: Literal["report", "specimen"]
    item_type: Literal["feature", "panel"]


class FeatureReport(Item):
    """Item for a feature that pertains to a report as a whole.
    Should have a list of feature labels, instructions for segmenting the feature,
    and instructions for standardizing the feature."""

    item_type: str = "feature"
    item_coverage: str = "report"
    feature_labels: list[str]
    segment_feature_instructions: str
    standardize_feature_instructions: str


class FeatureSpecimen(Item):
    """Item for a feature that pertains to an individual specimen.
    Should have a list of feature labels, instructions for segmenting the feature,
    and instructions for standardizing the feature."""

    item_type: str = "feature"
    item_coverage: str = "specimen"
    feature_labels: list[str]
    segment_feature_instructions: str
    standardize_feature_instructions: str


class PanelSpecimen(Item):
    """Item for a panel that pertains to an individual specimen.
    Should have a list of test names, results, and synonyms, and
    instructions for segmenting the panel and standardizing the panel.
    The synonyms are for tests that have multiple non obvious names.
    The two segmentations are needed because the LLMs need extra
    help finding and ordanizing all of the tests."""

    item_type: str = "panel"
    item_coverage: str = "specimen"
    panel_test_names: list[str]
    panel_test_results: Union[list[str], dict[str, list[str]]]
    panel_test_synonyms: list[str]
    segment_1_panel_instructions: str
    segment_2_panel_instructions: str
    standardize_panel_instructions: str


class PanelReport(Item):
    """Placeholder as the flow for a panel
    report is not yet implemented."""

    pass


class ReportSchema(BaseModel):
    """Defines the fields for a report schema.
    A report schema is a collection of items that define
    the structure of a report. The schema is used to extract
    the items from a report. It also contains helpful
    metadata about the schema, ideally schemas should be versioned in the schema name.
    """

    report_type: str
    report_subtype: str
    feature_report: Optional[dict[str, FeatureReport]] = None
    feature_specimen: Optional[dict[str, FeatureSpecimen]] = None
    panel_specimen: Optional[dict[str, PanelSpecimen]] = None


class IntermediateData(BaseModel):
    """Defines the fields for an input into a promptflow."""

    report_text: str
    report_id: str
    intermediate_json_key: str
    item_type_coverage: str
    item_name: str
    schema_name: str
    connection_name: str
    connection_model: str


class PfInputItem(BaseModel):
    """Defines the fields for an input into a promptflow."""

    report_text: str
    report_id: str
    data_source_key: str
    run_batch_name: str
    item_type_coverage: str
    item_name: str
    schema_name: str
    connection_name: str
    connection_model: str
    deployment_name: Optional[str] = None
    model: Optional[str] = None


class PfNodeOutputItem(BaseModel):
    """Defines the fields that are expected for an individual
    promptflow node output. The output is a dictionary that typically
    contains a reasoning summary and either a single field for a
    report item, or multiple fields for a specimen item, one for each specimen.
    The panel specimen output currently provides additional information
    about the block in the field names"""

    output: dict
    prompt: str


class PfOutputItem(BaseModel):
    """Defines all fields that should be returned from running a
    full promptflow. Note the optional return fields for
    the different segmentations that could be called."""

    report_id: str
    data_source_key: str
    json_result_key: str
    item_type_coverage: str
    item_name: str
    schema_name: str
    created_at: str
    run_batch_name: str
    connection_name: str
    connection_model: str
    model: Optional[str] = None
    deployment_name: Optional[str] = None
    standardized_output: PfNodeOutputItem
    segment_feature_report_output: Optional[PfNodeOutputItem] = None
    segment_feature_specimen_output: Optional[PfNodeOutputItem] = None
    segment_1_panel_report_output: Optional[PfNodeOutputItem] = None
    segment_2_panel_report_output: Optional[PfNodeOutputItem] = None
    segment_1_panel_specimen_output: Optional[PfNodeOutputItem] = None
    segment_2_panel_specimen_output: Optional[PfNodeOutputItem] = None


class Report(BaseModel):
    """Defines the fields for a report"""

    report_id: str
    report_text: str


class FlatResultsRow(BaseModel):
    """Defines the fields for a single flat result"""

    report_id: str
    item_name: str
    item_label: str
    full_item_name: str
    item_type_coverage: Literal[
        "feature_report", "feature_specimen", "panel_specimen", "panel_report"
    ]
    schema_name: str
    connection_name: str
    connection_model: str
    data_source_key: str
    pf_line_number: int
    created_at: str
    pf_flow_result_name: str
