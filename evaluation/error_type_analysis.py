#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import json

ERROR_TYPE = [
    "AssertionError", "TypeError", "NameError", "ValueError", "SyntaxError",
    "IndexError", "ModuleNotFoundError", "AttributeError", "TimeOut", "RecursionError",
    "IndentationError", "KeyError", "OtherError"
]


def analyze_execution_log(log_info):
    raw_log_info = log_info
    result = {error_key: False for error_key in ERROR_TYPE}
    if "----------------------------------------------------------------------" in log_info:
        log_info = log_info.split("----------------------------------------------------------------------")[1]
    for error_key in result.keys():
        if error_key in log_info:
            result[error_key] = True
            break
    else:
        result["OtherError"] = True
        print(f"[-] log error: {log_info}")
    return result


def extract_error_type(result_file, key_name):
    analysis = {error_key: 0 for error_key in ERROR_TYPE}
    analysis["OK"] = 0
    analysis["ERROR"] = 0
    with open(result_file, "r", encoding="utf8") as f:
        data = json.load(f)
        for each_problem, result in data.items():
            result = result[key_name]
            if "\nOK\n" in result:
                analysis["OK"] += 1
                continue
            analysis["ERROR"] += 1
            details = analyze_execution_log(result)
            for error_type in ERROR_TYPE:
                if details[error_type]:
                    analysis[error_type] += 1
                    break
    assert analysis["OK"] + analysis["ERROR"] == len(data)
    assert analysis["ERROR"] == sum([analysis[error_key] for error_key in ERROR_TYPE])
    return analysis
