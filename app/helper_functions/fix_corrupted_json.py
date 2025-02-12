""" Helper functions for fixing corrupted JSON strings- sometimes returned by less powerful LLMs """

import json


def fix_corrupted_json(input_str):
    try:
        return json.loads(input_str)
    except json.JSONDecodeError as e:
        # Logging initial error
        print(f"Initial JSONDecodeError: {e}")

        # Attempt to fix common JSON errors
        if "Expecting ',' delimiter" in e.msg:
            fixed_str = _fix_missing_bracket(input_str, e.pos)
        else:
            fixed_str = _fix_extra_char(input_str, e.pos)

        try:
            return json.loads(fixed_str)
        except json.JSONDecodeError as e2:
            print(f"Second JSONDecodeError after first fix attempt: {e2}")
            fixed_str = _fix_missing_comma(input_str, e2.pos)

            try:
                return json.loads(fixed_str)
            except json.JSONDecodeError as e3:
                print(f"Third JSONDecodeError after second fix attempt: {e3}")
                # Last resort: Attempt to extract the most likely valid JSON
                return _extract_valid_json(input_str)


def _fix_missing_bracket(json_string, pos):
    """Adds an extra closing bracket at the error position."""
    return json_string[:pos] + "}" + json_string[pos:]


def _fix_missing_comma(json_string, pos):
    """Adds a comma at the error position."""
    return json_string[:pos] + "," + json_string[pos:]


def _fix_extra_char(json_string, pos):
    """Removes an extra character from the JSON string at the specified position."""
    return json_string[:pos] + json_string[pos + 1 :]


def _extract_valid_json(json_string):
    """Attempts to extract the largest valid JSON from the string."""
    try:
        start = json_string.find("{")
        end = json_string.rfind("}") + 1
        return json.loads(json_string[start:end])
    except json.JSONDecodeError as e:
        # If all fixes fail, log and return a failure message
        print(f"Final JSONDecodeError after trying to extract valid JSON: {e}")
        return {"error": "Unable to fix JSON"}
