#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import os.path
import re
import os
import json
from tqdm import tqdm
from multiprocessing import Pool, Manager
from pylint.lint import Run
from pylint.reporters.text import TextReporter
from pylint.lint import pylinter
from io import StringIO


def analyze_using_pylint(file_path):
    # Run(["--disable=line-too-long", "myfile.py"])
    pylinter.MANAGER.clear_cache()
    pylint_output = StringIO()  # Custom open stream
    reporter = TextReporter(pylint_output)
    Run([file_path], reporter=reporter, exit=False)
    return pylint_output.getvalue()


def format_result(pylint_output, num_id):
    result = {
        "Fatal": [],
        "Error": [],
        "Warning": [],
        "Convention": [],
        "Refactor": [],
        "Information": [],
        "Rate": ""
    }
    try:
        rate = re.findall("Your code has been rated at (.+?)/10", pylint_output)[0]
    except Exception as e:
        rate = 0.0
    for each_line in pylint_output.split("\n"):
        type_number = re.findall(rf"temp_pylint_meta_{num_id}.py:\d+:\d+: (\w+):", each_line)
        if len(type_number) == 0:
            continue
        type_number = type_number[0]
        if str(type_number).startswith("F"):
            result["Fatal"].append(each_line)
        elif str(type_number).startswith("E"):
            result["Error"].append(each_line)
        elif str(type_number).startswith("W"):
            result["Warning"].append(each_line)
        elif str(type_number).startswith("C"):
            result["Convention"].append(each_line)
        elif str(type_number).startswith("R"):
            result["Refactor"].append(each_line)
        elif str(type_number).startswith("I"):
            result["Information"].append(each_line)

    result["Rate"] = rate
    return result


def process_task(task_id, answer, num_id):
    if "pylint" in answer:
        return task_id, answer["pylint"]

    temp_file_name = f"temp_pylint_meta_{num_id}.py"
    try:
        with open(temp_file_name, "w", encoding="utf8") as temp_file:
            temp_file.write(answer["code"])
        response = format_result(analyze_using_pylint(temp_file_name), num_id)
        response["completion"] = answer["code"]
        return task_id, response
    finally:
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)


def pylint_analyze_from_json(file_path):
    with open(file_path, "r", encoding="utf8") as file:
        answers = json.load(file)

    if "pylint" not in next(iter(answers.values())):
        tasks = [(task_id, answer, num_id) for num_id, (task_id, answer) in enumerate(answers.items())]

        # Use a pool of workers to process tasks in parallel
        with Manager() as manager:
            with Pool(processes=os.cpu_count()) as pool:
                for task_id, result in tqdm(pool.starmap(process_task, tasks), total=len(tasks)):
                    answers[task_id]["pylint"] = result

        # Save updated results back to the JSON file
        with open(file_path, "w", encoding="utf8") as file:
            json.dump(answers, file, indent=4, ensure_ascii=False)

    return {problem_id: values["pylint"] for problem_id, values in answers.items()}


def extract_pylint_code_from_result(pylint_result):
    result = dict()
    for problem_id, pylint_output in pylint_result.items():
        for key, value in pylint_output.items():
            if type(value) == list:
                for each_line in value:
                    code_number = re.findall(rf".py:\d+:\d+: (\w+):", each_line)
                    if len(code_number) == 0:
                        continue
                    code_number = code_number[0]
                    result[code_number] = result.get(code_number, 0) + 1
    return result


def match_code_with_checkers(code_group, checkers):
    result = {key: dict() for key in checkers.keys()}
    code_map = dict()
    for key, value in checkers.items():
        code_map[value.lower()] = key
    for code, count in code_group.items():
        result[code_map[code[0].lower()]][code] = count
    return result


def classify_pylint_result(result):
    code_group = extract_pylint_code_from_result(result)
    checker_group = {"Fatal": "F", "Error": "E", "Warning": "W", "Convention": "C", "Refactor": "R", "Information": "I"}
    match_result = match_code_with_checkers(code_group, checker_group)
    return match_result


def get_pylint_types_report():
    file_list = [
        "../../archive/mbpp/2026-04-07-waterfall-08-round5_report.json",
    ]
    for file_path in file_list:
        # print(f"[*] Analyzing: {file_path}")
        result = {"scores": 0.0, "Fatal": 0, "Error": 0, "Warning": 0, "Convention": 0, "Refactor": 0, "Information": 0}
        with open(file_path, "r", encoding="utf8") as file:
            report = json.load(file)
            for each_task in report.values():
                result["scores"] += float(each_task["Rate"])
                for each_type in ["Fatal", "Error", "Warning", "Convention", "Refactor", "Information"]:
                    result[each_type] += len(each_task[each_type])
            print(f"{result['scores'] / len(report)}", end="\t")
            for each_type in ["Fatal", "Error", "Warning", "Convention", "Refactor", "Information"]:
                print(f"{result[each_type]}", end="\t")
            print("")
