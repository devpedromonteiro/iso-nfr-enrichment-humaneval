#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import json
import subprocess
import os
import time
import zipfile
import statistics
import re
import codecs
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm


def get_humaneval_problems():
    result = dict()
    with open(os.path.join("HumanEval.jsonl"), "r") as f:
        for each_line in f:
            this_line = json.loads(each_line)
            result[this_line["task_id"]] = this_line
    return result


def get_mbpp_problems():
    result = dict()
    with open(os.path.join("sanitized-mbpp.json"), "r") as f:
        raw_data = json.load(f)
        for each_line in raw_data:
            result[each_line["task_id"]] = each_line
    return result


def fix_indent_problem(code):
    if code.startswith("try:\n"):
        code = f"    {code}"
    return code


def fix_format_problem(code):
    if "```python" in code:
        code = re.findall(r"```python([\s\S]+?)```", code, re.S)[0]
    return code


def count_definition_number(code):
    definition_number = list()
    for each_line in code.split("\n"):
        if each_line.startswith("def "):
            definition_number.append(each_line)
    return definition_number


def fix_head_tail_empty(code):
    return code.strip("\n")


def delete_test_statements(code):
    code = code.strip("\n")
    if "def " not in code or code.startswith("    "):
        if code.startswith("   "):
            result = [x for x in code.split("\n") if x.startswith("   ")]
        else:
            result = [x for x in code.split("\n")]
        return "\n".join(result)
    result, prefix = list(), ""
    prefix = re.findall(r"([\s\S]*?)def", code)[0]
    code = code.split("\n")
    while len(code) > 0:
        each_line = code.pop(0)
        if each_line.startswith("# Test"):
            break
        if each_line.startswith("def "):
            result.append(each_line)
            each_line = code.pop(0)
            while each_line.startswith("    ") or each_line.strip() == "":
                result.append(each_line)
                if len(code) == 0:
                    break
                each_line = code.pop(0)
            code.insert(0, each_line)
    code = prefix + "\n".join(result)
    return code


def purify(code):
    code = codecs.decode(code, "unicode_escape")
    code = fix_indent_problem(code)
    code = fix_format_problem(code)
    definitions = count_definition_number(code)
    code = delete_test_statements(code)
    code = fix_head_tail_empty(code)
    return code, definitions


def get_function(definition, answer, function_name):
    prompt = "\n".join(answer['prompt'].encode().decode("unicode-escape").split("\n")[1:]).strip('"')
    answer, definitions = purify(answer["completion"])

    if "# missing code here" in prompt.split("\n")[-1] and "def" not in answer:
        return f"{prompt}\n{answer}\ncandidate = {function_name}\n"
    elif answer.split("\n")[0].startswith("   "):
        return f"{definition}\n{answer}\ncandidate = {function_name}\n"
    else:
        definition = "\n".join(definition.split("\n")[:-1])
        if any([function_name in code_method for code_method in definitions]):
            answer += f"\ncandidate = {function_name}\n"
        elif len(definitions) > 1:
            function_name = re.findall(r"def (.+)\(", answer)[-1]
            answer += f"\ncandidate = {function_name}\n"
        else:
            function_name = re.findall(r"def (.+?)\(", answer)[0]
            answer += f"\ncandidate = {function_name}\n"
        return f"{definition}\n{answer}"


def get_definition_from_problem(problem):
    result = list()
    for each_line in problem["prompt"].split("\n"):
        if f"def {problem['entry_point']}" in each_line:
            # function_name = re.findall("def (.+)\(", each_line)[0]
            # each_line = each_line.replace(f"def {function_name}", "def candidate")
            result.append(each_line)
            break
        else:
            result.append(each_line)
    return "\n".join(result), problem['entry_point']


def _gent_humaneval_test_script(problem_id, answer, problem_info):
    template = '''
import unittest
import re
import sys
import math
import copy

{function}

{tests}

class Test(unittest.TestCase):
    def test(self):
        check(candidate)

if __name__ == '__main__':
    unittest.main()
'''
    # if problem == "HumanEval/14":
    #     print("debug")
    definition, function_name = get_definition_from_problem(problem_info)
    function = get_function(definition, answer, function_name)
    test_code = template.format(function=function, tests=problem_info["test"])
    problem_id = re.findall(r'\d+', problem_id)[0]
    os.makedirs("test_scripts", exist_ok=True)
    file_path = os.path.join("test_scripts", f"test{problem_id}.py")
    with open(file_path, "w") as f:
        f.write(test_code)
    return file_path, function


def extract_answer(answer, problem):
    prompt = "\n".join(answer['prompt'].encode().decode("unicode-escape").split("\n")[1:]).strip('"')
    answer, definitions = purify(answer["completion"])
    if "\n'''" in prompt:
        prompt = prompt.replace("\n'''", "\n    '''")

    if "# missing code here" in prompt.split("\n")[-1] and "def" not in answer:
        raise Exception(f"not support yet")
    elif len(definitions) > 1:
        return answer, "\n".join(definitions)
    elif answer.split("\n")[0].startswith("   "):
        return f"{prompt}\n{answer}\n", prompt
    elif "def " in answer:
        definition = re.findall("def .+\n", answer)[0]
        return answer, definition
    elif not answer.split("\n")[0].startswith("   "):
        answer = "\n    ".join(answer.split("\n"))
        return f"{prompt}\n    {answer}\n", prompt
    else:
        return f"{prompt}\n{answer}\n", prompt


def get_entry_point_for_mbpp(test_case):
    if "assert set(" in test_case:
        return re.findall(r"assert set\((.+?)\(", test_case)[0]
    elif "assert math.isclose(" in test_case:
        return re.findall(r"assert math.isclose\((.+?)\(", test_case)[0]
    elif "assert " in test_case:
        return re.findall(r"assert (.+?)\(", test_case)[0]
    else:
        raise Exception("not support yet")


def _gent_mbpp_test_script(problem_id, answer, problem_info):
    template = '''
import unittest
import re
import sys
import math
import copy

{function}

class Test(unittest.TestCase):
    def test(self):
        {assertions}

if __name__ == '__main__':
    unittest.main()
'''
    # if int(problem_id) == 64:
    #     print("debug")
    entry_point = get_entry_point_for_mbpp(problem_info["test_list"][0])
    function, definition = extract_answer(answer, problem_info)
    test_list = problem_info["test_list"]
    if f"{entry_point}(" not in definition:
        function_name = re.findall(r"def (.+?)\(", definition)[-1].strip()
        new_test_list = list()
        for each_test in test_list:
            new_test_list.append(each_test.replace(entry_point, function_name))
        test_list = new_test_list
    asserts = list()
    for each_assert in test_list:
        asserts.append(each_assert.replace("))", ",))"))
    assertions = "\n        ".join(asserts)
    test_code = template.format(function=function, assertions=assertions)
    file_path = os.path.join("test_scripts", f"test{problem_id}.py")
    with open(file_path, "w") as f:
        f.write(test_code)
    return file_path, function


def gen_test_script(problem_id, answer, problem_info, dataset="humaneval"):
    if dataset == "humaneval":
        return _gent_humaneval_test_script(problem_id, answer, problem_info)
    elif dataset == "mbpp":
        return _gent_mbpp_test_script(problem_id, answer, problem_info)
    else:
        raise ValueError(f"dataset {dataset} is not supported")


def archive_result(name):
    with zipfile.ZipFile(os.path.join(ROOT, f"{name}_evaluation_scripts.zip"), "w") as zip_file:
        start_dir = os.path.join("test_scripts")
        for root_path, dir_names, file_names in os.walk(start_dir):
            for each_file in file_names:
                zip_file.write(filename=os.path.join(root_path, each_file), arcname=each_file,
                               compress_type=zipfile.ZIP_DEFLATED)
                os.remove(os.path.join(root_path, each_file))


def run_command_and_time(command):
    """
    Helper function to run a command and measure its execution time.
    """
    start_time = time.time()
    this_result = run_command(command)
    end_time = time.time()
    execution_time = end_time - start_time
    return execution_time, this_result


def measure_execution_times(command, runs=10):
    """
    Measure the execution times of a command using multiprocessing for faster runs.

    Args:
        command (str): The command to execute.
        runs (int): Number of times to execute the command.

    Returns:
        tuple: A list of execution times, the last command result, and the mean time.
    """
    with ProcessPoolExecutor(max_workers=runs) as executor:
        futures = [executor.submit(run_command_and_time, command) for _ in range(runs)]
        results = [future.result() for future in futures]

    times = [this_result[0] for this_result in results]
    last_result = results[-1][1]
    mean_time = statistics.mean(times)

    return times, last_result, mean_time


def run_command(command):
    try:
        out_bytes = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=10)
    except subprocess.CalledProcessError as e:
        out_bytes = e.output  # Output generated before error
        code = e.returncode  # Return code
    except subprocess.TimeoutExpired as e:
        return "TimeOut"
    return out_bytes.decode("utf8")


def evaluation_dataset(file_path, root_path, dataset="humaneval", need_rerun=False):
    global ROOT
    ROOT = root_path
    if dataset == "humaneval":
        all_problems = get_humaneval_problems()
    elif dataset == "mbpp":
        all_problems = get_mbpp_problems()
    else:
        raise ValueError("Dataset not found")

    # load answers
    answer = dict()
    with open(file_path) as f:
        for each_line in f:
            this_line = json.loads(each_line)
            answer[this_line["task_id"]] = {"completion": this_line["completion"], "prompt": this_line["prompt"]}

    # generate test scripts and execute
    raw_name, result_file = get_result_path(dataset, file_path)
    if need_rerun or not os.path.exists(os.path.join(ROOT, result_file)):
        evaluation = dict()
        for each_problem in tqdm(all_problems):
            evaluation[each_problem] = {"result": "Failed", "code": answer[each_problem]["completion"],
                                        "prompt": answer[each_problem]["prompt"],
                                        "raw_response": answer[each_problem]["completion"]}
            try:
                script, code = gen_test_script(each_problem, answer[each_problem], all_problems[each_problem], dataset)
                execution_times, last_result, mean_time = measure_execution_times(f"python3 {script}", runs=5)
                evaluation[each_problem] = {"result": last_result, "code": code, "execution_times": execution_times,
                                            "mean_time": mean_time, "prompt": answer[each_problem]["prompt"],
                                            "raw_response": answer[each_problem]["completion"]}
            except Exception as e:
                print(f"[-] Error evaluate: {each_problem} - {e}")
        with open(os.path.join(ROOT, result_file), "w") as f:
            json.dump(evaluation, f, indent=4, ensure_ascii=False)
        # archive
        archive_result(raw_name)

    # calculate
    with open(os.path.join(ROOT, result_file), "r") as f:
        evaluation = json.load(f)
        total = len(evaluation)
        passed = 0
        for each in evaluation.values():
            if "result" in each:
                value = each["result"]
            elif f"{dataset}_result" in each:
                value = each[f"{dataset}_result"]
            else:
                raise Exception("No result key")
            if "\nOK\n" in value:
                passed += 1
        return passed / total, os.path.join(ROOT, result_file)


def get_result_path(dataset, file_path):
    raw_name = os.path.basename(file_path)
    raw_name = raw_name.split(".")[0]
    result_file = f"{raw_name}-{dataset}_evaluate_result.json"
    return raw_name, result_file
