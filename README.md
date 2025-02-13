# Prompts 2 Table

Welcome to the Prompts 2 table code repo! This contains some code to get started using this workflow for information extraction from medical texts
Check out [the pre-print here](https://www.medrxiv.org/content/10.1101/2025.02.11.25322107v1)

- [Prompts 2 Table](#prompts-2-table)
  - [Getting started](#getting-started)
  - [Tips for editing the schema \& prompts](#tips-for-editing-the-schema--prompts)
  - [Tips for inference](#tips-for-inference)
  - [Prompt flows](#prompt-flows)
    - [Prompt flow Structure](#prompt-flow-structure)
  - [Helper functions](#helper-functions)
  - [Roadmap](#roadmap)

## Getting started

NOTE: In `.vscode/settings.json` I have the word wrap for .json files turned on. This makes editing the schemas easier. There are also some recommended plugins in `.vscode/extensions.json`

1. Setting up the env: This project uses uv to set up the environment, see the [docs for uv here](https://docs.astral.sh/uv/getting-started/installation/). The venv can be created with `uv sync` followed by `source .venv/bin/activate`
2. Adding connections: First you'll need to check out the [example.env](example.env) and create your own `.env` so that you have LLM connections available for Prompt flow to use
3. Adding data: Data can be in either a csv format with the columns `report_id` and `report_text` or in a JSONL file with those same keys. See the [example jsonl data](/example_data/input/example_jsonl_data.jsonl) and [example csv data](/example_data/input/example_csv_data.csv)
4. Running a batch: The [example_workbook](/example_workflow_notebook.ipynb) walks through running a batch of data through the pipeline
5. Modifying a schema: The schema can be modified to use different sets of labels and instructions. When adding a new entity, first determine what entity type it is (see below), and add it under the key for that entity type, along with the required fields. See [schema.py](/app/helper_functions/schema.py) for info on the required keys for each entity type. Also there are two included schemas, one for our kidney tumor reports, and one for our quick investigation of breast cancer reports.
6. Modifying prompts: If modifications to the prompt templates are needed, they can be found in the Jinja templates for the respective entity type (see below again)

## Tips for editing the schema & prompts

1. The prompt templates should contain abstract instructions relevant to all entities of that class. Ideally, the examples given in these should not contain labels actually found in the schema to avoid biasing generation. These prompt templates all follow a markdown document format. Also these prompts have not had major changes since about August 2024. Given evolving LLM capabilities they could probably be shortened. Models are much more capable at providing properly structured JSON outputs than before. Also there are new methods for providing a template for generation that could be very useful. This would need to be integrated into the DAG in such a way that it can work with both [VLLM](https://docs.vllm.ai/en/latest/features/structured_outputs.html) and [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/structured-outputs?tabs=python-secure%2Cdotnet-entra-id&pivots=programming-language-python).
2. The schema is where entity specific instructions can go, in the fields for segmentation and standardization instructions.
3. Using the structured vocabulary for IHC results is currently explained mostly in the entity specific instructions in the kidney template. Moving forward we may move these to the prompt jinja template to keep with the consistency of having general instructions in the templates and specific instructions in the schema.

## Tips for inference

1. I've found managing connections manually with a .env file is easier to work with than adding them through the Prompt flow VS Code plugin
2. To reduce token usage and increase performance, pre processing of raw report text can be helpful. i.e. removing dislcaimers and MD signatures
3. The flows are setup to use [vllm](https://docs.vllm.ai/en/latest/) for inference with open weight models. For these, a context window of about 6000-8000 tokens is needed, especially if reports are long. Strong performance was found with FP8 quantized models, thus their use is encouraged to increase the total throughput. Also since large portions of the prompts are reused, enabling automatic prefix caching can be helpful
4. I typically use a temperature of 0 so this is hardcoded, but can be modified in the flow yamls
5. Spell checking plugins for VSCode are useful for ensuring typos are not present in the schema

## Prompt flows

The [app](/app) directory contains three subdirectories, each representing a specific type of data extraction flow:

- [feature_report_flow](app/feature_report_flow/) Entities with one label per report
- [feature_specimen_flow](app/feature_specimen_flow/) Entities with one label per specimen
- [panel_specimen_flow](app/panel_specimen_flow/) Entities for which a panel of tests exist (like IHC/FISH) where we want the specimen, block, test name, and test result for all instances in the report

Each of these subdirectories contains similar files and follows a consistent structure for defining and executing a Prompt flow.

### Prompt flow Structure

A typical Prompt flow consists of the following files:

1. `load_[type]_[coverage].py`: This file contains code to load and prepare the input data for the Prompt flow.

2. `segment_[type]_[coverage].jinja2`: This file contains a Jinja template for the prompt used in the segmentation step of the Prompt flow. The template includes placeholders for inserting specific information such as labels and custom instructions. The purpose of this LLM call is to segment the relevant text out of the report.

3. `standardize_[type]_[coverage].jinja2`: This file contains a Jinja template for the prompt used in the standardization step of the Prompt flow. Similar to the segmentation template, it includes placeholders for specific information. The purpose of this flow is to make standardized data and labels from the segmented text.

4. `build_output_[type]_[coverage].py`: This file contains code to combine the outputs from the previous steps, add metadata, and return the final output of the Prompt flow.

5. `flow.dag.yaml`: This file defines the structure and configuration of the Prompt flow. It specifies the inputs, outputs, and nodes of the flow, along with their respective sources, inputs, and connections. If you have the Prompt flow VS Code tool installed you can open these up in a visual editor for a really nice view of the inputs and outputs of each node, the LLM connections being use and their settings, and a nice view of the DAG.

## Helper functions

There are several helper function included for running flows, as well as utilities for data validation

- [schema.py](app/helper_functions/schema.py) Contains pydantic data models for I/O and for defining the structure of the extraction schema
- [get_json_outputs.py](app/helper_functions/get_json_outputs.py) Returns a pandas series of flow outputs, so you can look at the reasoning responses
- [prep_data.py](/app/helper_functions/prep_data.py) Contains helpers for getting data prepared for a flow
- [fix_corrupted_json.py](/app/helper_functions/fix_corrupted_json.py) Contains helpers for fixing outputs from LLMs that may not be JSON serializable
- [flat_results.py](/app/helper_functions/flat_results.py) Contains functions to extract and organize relevant portions of the JSON outputs into a nice table
- [run_pf_wrapper.py](/app/helper_functions/run_pf_wrapper.py) This is the main wrapper function that sets up everything for a batch flow run

## Roadmap

- Adding the ability to use JSON schema for guided generation
- Adding some way of detecting problematic reports and flagging for review
- Checking out reasoning models
- Clarifying the use of "Other- fill in the blank" label categories for helping with consistency
- Improve logging
