#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import json
import os
import zipfile
import re
import subprocess
from tqdm import tqdm
from evaluate_humaneval_or_mbpp import gen_test_script, get_mbpp_problems, measure_execution_times

ROOT = "../results/2026-04-07"
TEMP_DIR = "test_scripts"


def get_humaneval_et_problems():
    result = dict()
    with open(os.path.join("HumanEval_ET.jsonl"), "r") as f:
        for each_line in f:
            this_line = json.loads(each_line)
            result[this_line["task_id"]] = this_line
    return result


def get_mbpp_et_problems():
    result = dict()
    mbpp = get_mbpp_problems()
    with open(os.path.join("MBPP_ET.jsonl"), "r") as f:
        for each_line in f:
            this_line = json.loads(each_line)
            if this_line['task_id'] not in mbpp:
                continue
            result[str(this_line["task_id"])] = this_line
    return result


def generate_test_script_humaneval_et(problem, answer, humaneval_et):
    template = '''
import unittest

{function}

class Test(unittest.TestCase):
    def test(self):
        {assertions}

if __name__ == '__main__':
    unittest.main()
'''
    test_case_list = [x.replace(humaneval_et["entry_point"], "candidate") for x in humaneval_et["test_case_list"]]
    assertions = "\n        ".join(test_case_list)
    test_code = template.format(function=answer, assertions=assertions)
    problem_id = re.findall(r'\d+', problem)[0]
    file_path = os.path.join("test_scripts", f"test{problem_id}.py")
    with open(file_path, "w") as f:
        f.write(test_code)
    return file_path


def run_command(command):
    try:
        out_bytes = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=10)
    except subprocess.CalledProcessError as e:
        out_bytes = e.output  # Output generated before error
        code = e.returncode  # Return code
    except subprocess.TimeoutExpired as e:
        return "TimeOut"
    return out_bytes.decode("utf8")


def archive_result(name):
    with zipfile.ZipFile(os.path.join(ROOT, f"{name}-humaneval_et_evaluation_scripts.zip"), "w") as zip_file:
        start_dir = TEMP_DIR
        for root_path, dir_names, file_names in os.walk(start_dir):
            for each_file in file_names:
                zip_file.write(filename=os.path.join(root_path, each_file), arcname=each_file,
                               compress_type=zipfile.ZIP_DEFLATED)
                os.remove(os.path.join(root_path, each_file))
    if os.path.exists(os.path.join(ROOT, f"{name}_evaluation_scripts.zip")):
        os.rename(os.path.join(ROOT, f"{name}_evaluation_scripts.zip"),
                  os.path.join(ROOT, f"{name}-humaneval_evaluation_scripts.zip"))


def evaluation_et(file_path, root_path, dataset="humaneval", need_rerun=False):
    global ROOT
    ROOT = root_path
    if dataset == "humaneval":
        all_problems = get_humaneval_et_problems()
    elif dataset == "mbpp":
        all_problems = get_mbpp_et_problems()
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    raw_name = os.path.basename(file_path)
    raw_name = raw_name[:raw_name.find(f"-{dataset}_evaluate_result.json")]

    # load answers
    with open(file_path) as f:
        result = json.load(f)

    # generate test scripts and execute
    if need_rerun or f"{dataset}_et_result" not in result[list(result.keys())[0]]:
        for each_problem in tqdm(all_problems):
            try:
                if dataset == "humaneval":
                    script_path = generate_test_script_humaneval_et(each_problem, result[each_problem]["code"],
                                                                    all_problems[each_problem])
                else:
                    answer = {"completion": result[each_problem]["code"], "prompt": result[each_problem]["prompt"]}
                    script_path, code = gen_test_script(each_problem, answer, all_problems[each_problem], dataset)
                execution_times, last_result, mean_time = measure_execution_times(f"python3 {script_path}", runs=5)
                result[each_problem][f"{dataset}_et_result"] = last_result
                result[each_problem][f"mean_time_et"] = mean_time
                result[each_problem][f"execution_times_et"] = execution_times
                result[each_problem][f"{dataset}_result"] = result[each_problem]["result"]
                result[each_problem]["prompt"] = result[each_problem]["prompt"]
                del result[each_problem]["result"]
            except Exception as e:
                print(f"[-] Error evaluate: {each_problem} -- {e}")
                result[each_problem][f"{dataset}_et_result"] = "Failed"
                result[each_problem][f"{dataset}_result"] = result[each_problem]["result"]
                result[each_problem]["prompt"] = result[each_problem]["prompt"]
                del result[each_problem]["result"]
        with open(file_path, "w") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        # archive
        archive_result(raw_name)

    # calculate
    total = len(result)
    passed = 0
    for each in result.values():
        if "\nOK\n" in each[f"{dataset}_et_result"]:
            passed += 1
    # print(f"total: {total}, passed: {passed}, rate: {passed / total:.2%}")
    return passed / total
