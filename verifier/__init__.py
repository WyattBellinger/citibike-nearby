"""Spec entrypoints: no model, network, clock, file access, or runtime imports."""

from .nearby import check_input, check_result, verdict


def verify_input(tool, value):
    if tool != "find_nearby_stations":
        return verdict(False, "unknown tool")
    return check_input(value)


def verify_output(tool, input_value, output_value, workspace):
    if tool != "find_nearby_stations":
        return verdict(False, "unknown tool")
    return check_result(input_value, output_value)


def verify_task(task, arguments, output, reference, workspace):
    if task != "find-nearby-stations":
        return verdict(False, "unknown task")
    return check_result(arguments, output)
