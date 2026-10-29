"""Spec entrypoints: deterministic checks of supplied data or saved live feeds."""

from .live import check_live_input, check_live_result
from .nearby import check_input, check_result, verdict


def verify_input(tool, value):
    if tool == "get_live_snapshot":
        return check_live_input(value)
    if tool != "find_nearby_stations":
        return verdict(False, "unknown tool")
    return check_input(value)


def verify_output(tool, input_value, output_value, workspace):
    if tool == "get_live_snapshot":
        return check_live_result(input_value, output_value, workspace, snapshot_output=True)
    if tool != "find_nearby_stations":
        return verdict(False, "unknown tool")
    return check_result(input_value, output_value)


def verify_task(task, arguments, output, reference, workspace):
    if task == "find-live-stations":
        return check_live_result(arguments, output, workspace)
    if task != "find-nearby-stations":
        return verdict(False, "unknown task")
    return check_result(arguments, output)
