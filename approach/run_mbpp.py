#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
""" Description
"""
import json
import os
import sys
import threading
import datetime
import re
import zipfile
import anthropic
from queue import Queue
from openai import OpenAI
from prompt_based_solution import Solution

# from code_based_solution import Solution
# from langgraph_based_solution import run_workflow

os.chdir(os.path.dirname(os.path.abspath(__file__)))

TEMP_DIR = "temp_data"
os.makedirs(TEMP_DIR, exist_ok=True)
PROMPT, BASELINE = None, None
EXPERIMENT_SECOND_STEP = False
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")
TEMPERATURE = 0

with open("../conf.json", "r") as f:
    # API_KEY = json.load(f)["openai-keys"]
    API_KEY = json.load(f)["openai-key"]
    #API_KEY = json.load(f)["claude_api_kpi"]


def get_mbpp_problems() -> list:
    result = list()
    with open(os.path.join("../evaluation", "sanitized-mbpp.json"), "r") as f:
        problems = json.load(f)
        for each_problem in problems:
            function_name = re.findall("def .+\n", each_problem['code'])[0]
            each_problem['prompt'] = f"{function_name}'''{each_problem['prompt']}\n'''\n"
            entry_point = re.findall(r"def (.+)\(", function_name)[0]
            each_problem['entry_point'] = entry_point
            result.append(each_problem)
    return result


def get_solution(problem, client, model, problem_info=None):
    """
    "gpt-3.5-turbo-0125"
    "gpt-3.5-turbo-1106"
    "gpt-4-turbo-2024-04-09"
    "gpt-4o-2024-05-13"
    "gpt-4o-2024-08-06"
    "gpt-4-turbo-2024-04-09"
    "gpt-4o-mini-2024-07-18"
    "gpt-4-0125-preview"
    "claude-3-5-sonnet-20240620"
    "claude-3-5-sonnet-20241022"
    "claude-3-5-haiku-20241022"
    :param problem:
    :param client:
    :return:
    """
    global PROMPT, BASELINE, EXPERIMENT_SECOND_STEP
    solution = Solution(client, temperature=TEMPERATURE, model=model)
    if EXPERIMENT_SECOND_STEP:
        return solution.second_step_code_enhancement(problem, PROMPT, BASELINE, problem_info)
    return solution.exception_handle(problem, PROMPT)
    # return solution.mask_code_percentage(problem, problem_info, mask_type="end")


def call_llm_and_save_result(ai_key, problems: Queue, model):
    if "gpt" in model.lower():
        client = OpenAI(api_key=ai_key)
    elif "claude" in model.lower():
        client = anthropic.Anthropic(api_key=ai_key)
    else:
        raise Exception(f"Model {model} is not supported!")
    while not problems.empty():
        each_problem = problems.get()
        print(f"[*] {'-' * 20} Thread:{threading.current_thread().name} {'-' * 20} ")
        print(f"[*] Problem: {each_problem['task_id']}")
        completion, prompt, others = get_solution(each_problem["prompt"], client, model,
                                                  problem_info=each_problem['task_id'])
        result = dict(task_id=each_problem['task_id'], completion=completion, prompt=json.dumps(prompt))
        order = re.findall(r"\d+", str(each_problem['task_id']))[0]
        with open(os.path.join(TEMP_DIR, f"{order}.json"), "w") as f:
            json.dump(result, f, indent=4)
        if result["completion"] == "Unknown" or result["completion"] is None:
            problems.put(each_problem)


def filter_problems():
    problems = get_mbpp_problems()
    after_filter = Queue()
    for each_problem in problems:
        file_name = f"{each_problem['task_id']}.json"
        if os.path.exists(os.path.join(TEMP_DIR, file_name)):
            with open(os.path.join(TEMP_DIR, file_name), "r") as f:
                result = json.load(f)
                if result["completion"] != "Unknown" and result["completion"] is not None:
                    continue
                after_filter.put(each_problem)
        else:
            after_filter.put(each_problem)
    return after_filter


def archive_result(file_name):
    with zipfile.ZipFile(f"{file_name}.zip", "w") as zip_file:
        start_dir = TEMP_DIR
        for root_path, dir_names, file_names in os.walk(start_dir):
            for each_file in file_names:
                zip_file.write(filename=os.path.join(root_path, each_file), arcname=each_file,
                               compress_type=zipfile.ZIP_DEFLATED)
                os.remove(os.path.join(root_path, each_file))


def run_mbpp(turn, PREFIX, model):
    file_name = f"{PREFIX}-mbpp-Trail{turn}.jsonl"
    if os.path.exists(file_name):
        raise Exception(f"File {file_name} already exists!")
    problems = filter_problems()
    thread_pool = list()
    for j in range(len(API_KEY)):
        t = threading.Thread(target=call_llm_and_save_result, args=(API_KEY[j], problems, model))
        thread_pool.append(t)
        t.start()
    for each_thread in thread_pool:
        each_thread.join()

    problems = get_mbpp_problems()
    samples = list()
    for j, each_problem in enumerate(problems):
        task_id = each_problem['task_id']
        if os.path.exists(os.path.join(TEMP_DIR, f"{task_id}.json")):
            with open(os.path.join(TEMP_DIR, f"{task_id}.json"), "r") as f:
                result = json.load(f)
            samples.append(result)
        else:
            samples.append(dict(task_id=each_problem['task_id'], completion="Unknown"))

    from evalplus.data import write_jsonl
    print(f"[*] Write to jsonl file: {file_name}")
    write_jsonl(file_name, samples)
    archive_result(file_name)


def rq1_run_multiple_prompts():
    global PROMPT
    errorhandle_prompts = """Incorporate various error handling techniques and complete the following code:
Implement multiple exception handling strategies and complete the following code:
Apply different error handling mechanisms and complete the following code:
Investigate different methods of managing exceptions and complete the following code:
Integrate diverse error handling approaches and complete the following code:
Utilize multiple error management techniques and complete the following code:
Experiment with various ways to handle exceptions and complete the following code:
Combine different error handling practices and complete the following code:
Evaluate multiple exception management strategies and complete the following code:
Develop a range of error handling solutions and complete the following code:"""
    codesmell_prompts = """Investigate various strategies to handle code smell and complete the following code:
Minimize code smell and complete the following code:
Eliminate code smell and complete the following code:
Identify and address different code smells and complete the following code:
Apply best practices to reduce code smell and complete the following code:
Mitigate code smell and complete the following code:
Tackle different code smell issues and complete the following code:
Implement techniques to prevent code smell and complete the following code:
Resolve code smell problems and complete the following code:
Optimize code to avoid code smell and complete the following code:"""
    readability_prompts = """Evaluate different coding practices for readability and complete the following code:
Investigate various techniques to enhance readability and complete the following code:
Improve the code readability and complete the following code:
Ensure the code is readable and complete the following code:
Apply coding practices that enhance readability and complete the following code:
Focus on readability and complete the following code:
Enhance the readability of the code and complete the following code:
Implement strategies to make the code more readable and complete the following code:
Optimize the code for better readability and complete the following code:
Adopt coding practices for improved readability and complete the following code:"""
    raw_prompts = """








"""
    performance_prompts = """Optimize for performance and complete the following code:
Focus on enhancing performance and complete the following code:
Ensure the code runs efficiently and complete the following code:
Prioritize runtime optimization and complete the following code:
Keep performance in mind while solving and complete the following code:
Aim for high-performance execution and complete the following code:
Reduce computational overhead and complete the following code:
Emphasize speed and efficiency and complete the following code:
Ensure minimal resource consumption and complete the following code:
Maximize performance in your solution and complete the following code:"""
    prompts_map = {
        # "performance": performance_prompts,
        # "errorhandle": errorhandle_prompts,
        # "codesmell": codesmell_prompts,
        # "readability": readability_prompts,
        "raw": raw_prompts
    }
    for name, prompts in prompts_map.items():
        for i, each_prompt in enumerate(prompts.split("\n")):
            PROMPT = each_prompt
            print(f"[*] Prompt{i}:{each_prompt}")
            PREFIX = f"{TODAY}-gpt-54-2026-03-05-t00-GenPrompt-{name}-prompt{i}"
            run_mbpp(turn=0, PREFIX=PREFIX, model="gpt-5.4-2026-03-05")


def rq2_run_two_steps_prompts():
    global PROMPT, BASELINE
    # CHANGE
    gpt_54_2026_03_05_mbpp = {
        "rawGPT": [
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt0-mbpp-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt1-mbpp-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt2-mbpp-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt3-mbpp-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt4-mbpp-Trail0.jsonl",
        ],
    }
    baseline = gpt_54_2026_03_05_mbpp
    errorhandle_prompts = """Incorporate various error handling techniques and improve the following code:
Implement multiple exception handling strategies and improve the following code:
Apply different error handling mechanisms and improve the following code:
Investigate different methods of managing exceptions and improve the following code:
Integrate diverse error handling approaches and improve the following code:
Utilize multiple error management techniques and improve the following code:
Experiment with various ways to handle exceptions and improve the following code:
Combine different error handling practices and improve the following code:
Evaluate multiple exception management strategies and improve the following code:
Develop a range of error handling solutions and improve the following code:"""
    codesmell_prompts = """Investigate various strategies to handle code smell and improve the following code:
Minimize code smell and improve the following code:
Eliminate code smell and improve the following code:
Identify and address different code smells and improve the following code:
Apply best practices to reduce code smell and improve the following code:
Mitigate code smell and improve the following code:
Tackle different code smell issues and improve the following code:
Implement techniques to prevent code smell and improve the following code:
Resolve code smell problems and improve the following code:
Optimize code to avoid code smell and improve the following code:"""
    readability_prompts = """Evaluate different coding practices for readability and improve the following code:
Investigate various techniques to enhance readability and improve the following code:
Improve the code readability and improve the following code:
Ensure the code is readable and improve the following code:
Apply coding practices that enhance readability and improve the following code:
Focus on readability and improve the following code:
Enhance the readability of the code and improve the following code:
Implement strategies to make the code more readable and improve the following code:
Optimize the code for better readability and improve the following code:
Adopt coding practices for improved readability and improve the following code:"""
    performance_prompts = """Optimize for performance and improve the following code:
Focus on enhancing performance and improve the following code:
Ensure the code runs efficiently and improve the following code:
Prioritize runtime optimization and improve the following code:
Keep performance in mind while solving and improve the following code:
Aim for high-performance execution and improve the following code:
Reduce computational overhead and improve the following code:
Emphasize speed and efficiency and improve the following code:
Ensure minimal resource consumption and improve the following code:
Maximize performance in your solution and improve the following code:"""
    prompts_map = {
        # "performance": performance_prompts,
        # "errorhandle": errorhandle_prompts,
        # "codesmell": codesmell_prompts,
        "readability": readability_prompts,
    }
    for name, prompts in prompts_map.items():
        for i, each_prompt in enumerate(prompts.split("\n")):
            PROMPT = each_prompt
            BASELINE = baseline["rawGPT"][i]
            print(f"[*] Prompt{i}:{each_prompt}")
            PREFIX = f"{TODAY}-gpt-54-2026-03-05-t00-GenPrompt-{name}-prompt{i}"  # CHANGE remember to change the baseline
            run_mbpp(turn=0, PREFIX=PREFIX, model="gpt-5.4-2026-03-05")


if __name__ == "__main__":
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _cfg_path = os.path.join(_repo_root, "nfrgen_experiment.json")
    if os.path.isfile(_cfg_path):
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from nfrgen_experiment import load_config, run_generation_mbpp

        _cfg, _, _ = load_config()
        if _cfg.get("generation", {}).get("benchmark", "humaneval") != "mbpp":
            print("[run_mbpp] nfrgen_experiment.json must set generation.benchmark to mbpp for this script.")
            sys.exit(2)
        run_generation_mbpp(_cfg)
    else:
        rq1_run_multiple_prompts()
    # rq2_run_two_steps_prompts()
