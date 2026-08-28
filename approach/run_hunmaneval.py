#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import json
import os
import sys
import threading
import datetime
import time
import re
import zipfile
import anthropic
from queue import Queue
from openai import OpenAI
from prompt_based_solution import Solution

_repo_root_for_stability = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root_for_stability not in sys.path:
    sys.path.insert(0, _repo_root_for_stability)
import stability_subset as _stability_subset  # noqa: E402

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
    # API_KEY = json.load(f)["claude_api_kpi"]


def get_solution(problem, client, model, problem_id=None):
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
    :return:
    """
    global PROMPT, BASELINE, EXPERIMENT_SECOND_STEP
    solution = Solution(client, temperature=TEMPERATURE, model=model)
    if EXPERIMENT_SECOND_STEP:
        return solution.second_step_code_enhancement(problem, PROMPT, BASELINE, problem_id)
    return solution.exception_handle(problem, PROMPT)
    # return solution.mask_code_percentage(problem, problem_id, mask_type="end")


def _get_solution_with_retry(each_problem, client, model, max_retries=5):
    """Call the LLM with bounded retries (infra only: same prompt/model/temperature).

    Added so that parallel worker threads (NFRGEN_GEN_THREADS) do not silently drop a
    problem when a transient API error occurs. On persistent failure the problem is
    returned unsolved so the caller re-queues it (consistent with the original
    "completion is None/Unknown -> retry" behaviour). Does not alter any experimental
    treatment, prompt content, evaluation procedure, or reported metric.
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            return get_solution(each_problem["prompt"], client, model, each_problem['task_id'])
        except Exception as exc:  # transient API/network errors
            last_err = exc
            print(f"[!] LLM error on {each_problem['task_id']} (attempt {attempt + 1}/{max_retries}): {exc}")
            time.sleep(min(2 ** attempt, 30))
    print(f"[!] Giving up on {each_problem['task_id']} after {max_retries} attempts: {last_err}")
    return None, "", {}


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
        completion, prompt, others = _get_solution_with_retry(each_problem, client, model)
        if completion is None or completion == "Unknown":
            # Persistent failure: do not persist a placeholder and do not re-queue
            # (avoids an infinite loop if the API is down). A later re-run of the same
            # config resumes this problem because no temp file exists for it yet.
            continue
        result = dict(task_id=each_problem['task_id'], completion=completion, prompt=json.dumps(prompt))
        result.update(others)
        order = re.findall(r"\d+", each_problem['task_id'])[0]
        with open(os.path.join(TEMP_DIR, f"{order}.json"), "w") as f:
            json.dump(result, f, indent=4)


def filter_problems():
    from evalplus.data import get_human_eval_plus
    problems = get_human_eval_plus()
    after_filter = Queue()
    subset_indices = None
    if _stability_subset.is_subset_mode():
        subset_indices = _stability_subset.allowed_indices()
        print(f"[*] Stability subset mode: {len(subset_indices)} HumanEval problems")
    for i, each_problem in enumerate(problems):
        if subset_indices is not None and i not in subset_indices:
            continue
        file_name = f"{i}.json"
        if os.path.exists(os.path.join(TEMP_DIR, file_name)):
            with open(os.path.join(TEMP_DIR, file_name), "r") as f:
                result = json.load(f)
                if result["completion"] != "Unknown" and result["completion"] is not None:
                    continue
                after_filter.put(problems[each_problem])
        else:
            after_filter.put(problems[each_problem])
    return after_filter


def _output_dir() -> str:
    """Directory for jsonl/zip outputs (default: approach cwd)."""
    out = os.environ.get("NFRGEN_OUTPUT_DIR", ".")
    os.makedirs(out, exist_ok=True)
    return out


def archive_result(file_name):
    with zipfile.ZipFile(f"{file_name}.zip", "w") as zip_file:
        start_dir = TEMP_DIR
        for root_path, dir_names, file_names in os.walk(start_dir):
            for each_file in file_names:
                zip_file.write(filename=os.path.join(root_path, each_file), arcname=each_file,
                               compress_type=zipfile.ZIP_DEFLATED)
                os.remove(os.path.join(root_path, each_file))


def run_humaneval(turn, PREFIX, model):
    out_dir = _output_dir()
    file_name = os.path.join(out_dir, f"{PREFIX}-Trail{turn}.jsonl")
    if os.path.exists(file_name):
        raise Exception(f"File {file_name} already exists!")
    problems = filter_problems()
    # Generation concurrency (infra only): NFRGEN_GEN_THREADS lets several worker threads
    # share the available API key(s) to speed up generation. This does NOT touch prompts,
    # model, temperature, evaluation, or any reported metric (generation has no timing
    # metric). Default = number of API keys, preserving the original single-thread behaviour.
    try:
        n_threads = max(int(os.environ.get("NFRGEN_GEN_THREADS", len(API_KEY))), 1)
    except ValueError:
        n_threads = len(API_KEY)
    thread_pool = list()
    for j in range(n_threads):
        ai_key = API_KEY[j % len(API_KEY)]
        t = threading.Thread(target=call_llm_and_save_result, args=(ai_key, problems, model))
        thread_pool.append(t)
        t.start()
    for each_thread in thread_pool:
        each_thread.join()

    from evalplus.data import get_human_eval_plus, write_jsonl
    problems = get_human_eval_plus()
    samples = list()
    for j, each_problem in enumerate(problems):
        if os.path.exists(os.path.join(TEMP_DIR, f"{j}.json")):
            with open(os.path.join(TEMP_DIR, f"{j}.json"), "r") as f:
                result = json.load(f)
            samples.append(result)
        else:
            samples.append(
                dict(
                    task_id=problems[each_problem]["task_id"],
                    completion="Unknown",
                    prompt="",
                )
            )

    print(f"[*] Write to jsonl file: {file_name}")
    write_jsonl(file_name, samples)
    archive_result(file_name)


def clear_stability_temp():
    """Remove temp_data entries so a stability re-run starts clean."""
    if not os.path.isdir(TEMP_DIR):
        return
    for name in os.listdir(TEMP_DIR):
        if name.endswith(".json"):
            os.remove(os.path.join(TEMP_DIR, name))


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
    prompts = performance_prompts # CHANGE 1
    # Item 3.3 do artigo 
    for i, each_prompt in enumerate(prompts.split("\n")): 
        PROMPT = each_prompt
        print(f"[*] Prompt{i}:{each_prompt}")
        PREFIX = f"{TODAY}-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt{i}" # CHANGE
        run_humaneval(turn=0, PREFIX=PREFIX, model="gpt-5.4-2026-03-05")


def rq2_run_two_steps_prompts():
    global PROMPT, BASELINE
    rq2_gpt_54_2026_03_05_humaneval_files = {
        "rawGPT": [
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt3-Trail0.jsonl",
            "../results/2026-04-08-gpt-54-2026-03-05-rq1-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt4-Trail0.jsonl",
        ],
    }
    baseline = rq2_gpt_54_2026_03_05_humaneval_files
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
        "performance": performance_prompts,
        # "errorhandle": errorhandle_prompts,
        # "codesmell": codesmell_prompts,
        # "readability": readability_prompts,
    }
    for name, prompts in prompts_map.items():
        for i, each_prompt in enumerate(prompts.split("\n")):
            if i > 4:
                continue
            PROMPT = each_prompt
            BASELINE = baseline["rawGPT"][i]
            print(f"[*] Prompt{i}:{each_prompt}")
            PREFIX = f"{TODAY}-gpt-54-2026-03-05-t00-GenPrompt-{name}-prompt{i}"  # CHANGE remember to change the baseline
            run_humaneval(turn=0, PREFIX=PREFIX, model="gpt-5.4-2026-03-05") # CHANGE 


if __name__ == "__main__":
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _cfg_path = os.path.join(_repo_root, "nfrgen_experiment.json")
    if os.path.isfile(_cfg_path):
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from nfrgen_experiment import load_config, run_generation_humaneval

        _cfg, _, _ = load_config()
        if _cfg.get("generation", {}).get("benchmark", "humaneval") != "humaneval":
            print("[run_hunmaneval] nfrgen_experiment.json has generation.benchmark != humaneval; run run_mbpp.py or python nfrgen_experiment.py instead.")
            sys.exit(2)
        run_generation_humaneval(_cfg)
    else:
        rq1_run_multiple_prompts()
    # rq2_run_two_steps_prompts()  # legacy: enable inside rq1_run or use config mode rq2 + use_second_step_enhancement
