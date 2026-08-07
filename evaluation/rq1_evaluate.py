#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import copy
import statistics
import numpy
import pandas
import os
import sys
import json
import density_metrics
from pylint_analyze import pylint_analyze_from_json, classify_pylint_result
from evaluate_humaneval_or_mbpp import evaluation_dataset, get_result_path
from humaneval_et_evaluation import evaluation_et
from exceptions_density_evaluate import ExceptionsDensityEvaluate
from error_type_analysis import extract_error_type

ERROR_TYPE = [
    "AssertionError", "TypeError", "NameError", "ValueError", "SyntaxError",
    "IndexError", "ModuleNotFoundError", "AttributeError", "TimeOut", "RecursionError",
    "IndentationError", "KeyError", "OtherError"
]
columns = ["approach", "task", "metrics", "model", "benchmark"]
columns.extend([f"prompt{i + 1}" for i in range(10)])
columns.extend(["AVG", "STDEV"])
NFR_REPORT = pandas.DataFrame(columns=columns)


def reset_nfr_report():
    """Clear the in-memory Excel aggregation (one clean report per configured evaluation run)."""
    global NFR_REPORT
    NFR_REPORT = pandas.DataFrame(columns=columns)


def get_test_time(result_path, dataset):
    with open(result_path) as f:
        result = json.load(f)
    test_time = list()
    test_time_et = list()
    for problem, each in result.items():
        # if "mean_time" in each and "\nOK\n" in each[f"{dataset}_result"]:
        if "mean_time" in each:
            test_time.append(each["mean_time"])
        # if "mean_time_et" in each and "\nOK\n" in each[f"{dataset}_et_result"]:
        if "mean_time_et" in each:
            test_time_et.append(each["mean_time_et"])
    return statistics.mean(test_time), statistics.mean(test_time_et)


def get_final_result(files, dataset="humaneval"):
    global ROOT
    final_result = dict()
    ede = ExceptionsDensityEvaluate()
    for each_file in files:
        print(f"Processing {each_file}")
        ROOT = os.path.dirname(each_file)
        rerun = need_rerun(dataset, each_file)
        evaluate_result, result_path = evaluation_dataset(each_file, ROOT, dataset=dataset, need_rerun=rerun)
        evaluate_et_result = evaluation_et(root_path=ROOT, file_path=result_path,
                                           dataset=dataset, need_rerun=rerun)
        pylint_result = pylint_analyze_from_json(result_path)
        pylint_result = classify_pylint_result(pylint_result)
        test_time, test_time_et = get_test_time(result_path, dataset)
        loc_and_exception_density = ede.evaluate(result_path, dataset=dataset)
        error_type = extract_error_type(result_path, f"{dataset}_result")
        et_error_type = extract_error_type(result_path, f"{dataset}_et_result")
        final_result[each_file] = {
            f"{dataset}": evaluate_result,
            f"{dataset}-ET": evaluate_et_result,
            f"test_time": test_time,
            f"test_time_ET": test_time_et,
            f"pylint_result": pylint_result,
            "LOC": loc_and_exception_density["loc"],
            "comment_loc": loc_and_exception_density["comment_loc"],
            "non_code_length": loc_and_exception_density["non_code_length"],
            "non_code_word": loc_and_exception_density["non_code_word"],
            "exception_density": loc_and_exception_density["exceptions-density per 10 loc"],
            f"{dataset}_error_type": error_type,
            f"{dataset}_et_error_type": et_error_type
        }
        print(f"{each_file}")
        print(f"{dataset}: {evaluate_result:.2%}\t"
              f"{dataset}-ET: {evaluate_et_result:.2%}\t"
              f"LOC: {loc_and_exception_density['loc']}\t"
              f"comment: {loc_and_exception_density['comment_loc']}\t"
              f"non-code-length: {loc_and_exception_density['non_code_length']}\t"
              f"non-code-word: {loc_and_exception_density['non_code_word']}\t"
              f"exception_density: {loc_and_exception_density['exceptions-density per 10 loc']:.2f}\t"
              f"{dataset}_error_type: {error_type}\t"
              f"{dataset}_et_error_type: {et_error_type}\t"
              f"test_time: {test_time:.4f}s\t"
              f"test_time_ET: {test_time_et:.4f}s\t")
    return final_result


def generate_summary_error_report(result, dataset="HumanEval"):
    global ERROR_TYPE
    error_counts = {key: 0 for key in ERROR_TYPE}
    error_counts_et = {key: 0 for key in ERROR_TYPE}
    for i, (prompt, details) in enumerate(result.items()):
        for error_type, value in details[f"{dataset}_error_type"].items():
            if error_type in ERROR_TYPE:
                error_counts[error_type] += value
        for error_type, value in details[f"{dataset}_et_error_type"].items():
            if error_type in ERROR_TYPE:
                error_counts_et[error_type] += value

    print("ErrorType:")
    need_print = "\t".join([str(value) for key, value in error_counts.items()])
    print(need_print)
    print("ET:")
    need_print = "\t".join([str(value) for key, value in error_counts_et.items()])
    print(need_print)


def generate_details_error_report(result, dataset="HumanEval"):
    global ERROR_TYPE
    error_counts = {key: list() for key in ERROR_TYPE}
    for key in error_counts.keys():
        error_counts[key] = [0 for i in range(len(result))]
    error_counts_et = copy.deepcopy(error_counts)

    for i, (prompt, details) in enumerate(result.items()):
        for error_type, value in details[f"{dataset}_error_type"].items():
            if error_type in ERROR_TYPE:
                error_counts[error_type][i] += value
        for error_type, value in details[f"{dataset}_et_error_type"].items():
            if error_type in ERROR_TYPE:
                error_counts_et[error_type][i] += value
    print("ErrorType:")
    need_prints = list()
    for key, value in error_counts.items():
        need_print = "/".join([str(value) for value in value])
        need_prints.append(need_print)
    print("_\t".join(need_prints))
    print("ET:")
    need_prints = list()
    for key, value in error_counts_et.items():
        need_print = "/".join([str(value) for value in value])
        need_prints.append(need_print)
    print("_\t".join(need_prints))


def generate_google_docs_report(result, dataset="HumanEval"):
    for metrics in [dataset, f"{dataset}-ET", "LOC", "comment_loc", "non_code_length", "non_code_word",
                    "exception_density", "test_time", "test_time_ET"]:
        need_print = list()
        for prompt, details in result.items():
            need_print.append(str(details[metrics]))
        print("\t".join(need_print))
    generate_summary_error_report(result, dataset)
    generate_details_error_report(result, dataset)


def need_rerun(dataset_name, file_path):
    global ROOT
    raw_name, result_path = get_result_path(dataset_name, file_path)
    result_path = os.path.join(ROOT, result_path)
    if not os.path.exists(result_path):
        return True
    with open(result_path) as f:
        result = json.load(f)
    for each_value in result.values():
        if "mean_time" in each_value or "mean_time_et" in each_value:
            return False
    return True


def generate_excel_sheet(result, output_path):
    output = pandas.DataFrame(columns=["prompt", "humaneval", "humaneval_et", "loc", "exception-handling-density",
                                       "humaneval-error", "humaneval-et-error"])
    for index, (prompt, details) in enumerate(result.items()):
        humaneval_error_type = {k: v for k, v in details["humaneval_error_type"].items() if v != 0}
        del humaneval_error_type["OK"]
        del humaneval_error_type["ERROR"]
        humaneval_et_error_type = {k: v for k, v in details["humaneval_et_error_type"].items() if v != 0}
        del humaneval_et_error_type["OK"]
        del humaneval_et_error_type["ERROR"]
        excel_info = [
            prompt,
            details["HumanEval"],
            details["HumanEval-ET"],
            details["LOC"],
            details["exception_density"],
            humaneval_error_type,
            humaneval_et_error_type
        ]

        output.loc[index] = excel_info
    output.to_excel(output_path)


def generate_nfr_report(result, benchmark, task, approach, model):
    global NFR_REPORT

    new_row = {
        "approach": approach,
        "task": task,
        "model": model,
        "benchmark": benchmark,
        **{f"prompt{i + 1}": None for i in range(10)},
        "metrics": "Metrics",
        "AVG": "AVG",
        "STDEV": "STDEV"
    }

    metrics = {"pass@1": benchmark, "ET-pass@1": f"{benchmark}-ET", "LOC": "LOC",
               "exception-density": "exception_density", "comment": "comment_loc",
               "non-code-length": "non_code_length", "non-code-word": "non_code_word",
               "mean-time": "test_time", "ET-mean-time": "test_time_ET"}
    for metric in metrics:
        temp_row = copy.deepcopy(new_row)
        data = list()
        for i, (prompt, details) in enumerate(result.items()):
            this_data = details[metrics[metric]]
            if metric == "maintainability":
                this_data = this_data["maintainability"]
            temp_row[f"prompt{i + 1}"] = this_data
            data.append(this_data)
        temp_row["AVG"] = numpy.mean(data)
        temp_row["STDEV"] = numpy.std(data, ddof=1)
        temp_row["metrics"] = metric
        NFR_REPORT.loc[len(NFR_REPORT)] = temp_row

    metrics = ["Fatal", "Error", "Warning", "Convention", "Refactor", "Information"]
    total_data = [0 for _ in range(len(result))]
    # Capture per-prompt raw counts so we can also publish densities per 10 LOC (N3).
    per_prompt_counts = {metric: [] for metric in metrics}
    for metric in metrics:
        data = list()
        temp_row = copy.deepcopy(new_row)
        for i, (prompt, details) in enumerate(result.items()):
            this_data = sum(details["pylint_result"][metric].values())
            temp_row[f"prompt{i + 1}"] = this_data
            total_data[i] += this_data
            data.append(this_data)
        per_prompt_counts[metric] = data
        temp_row["AVG"] = numpy.mean(data)
        temp_row["STDEV"] = numpy.std(data, ddof=1)
        temp_row["metrics"] = metric
        NFR_REPORT.loc[len(NFR_REPORT)] = temp_row

    # Total
    temp_row = copy.deepcopy(new_row)
    for i, each_prompt_result in enumerate(total_data):
        temp_row[f"prompt{i + 1}"] = each_prompt_result
    temp_row["metrics"] = "Total"
    temp_row["AVG"] = numpy.mean(total_data)
    temp_row["STDEV"] = numpy.std(total_data, ddof=1)
    NFR_REPORT.loc[len(NFR_REPORT)] = temp_row

    # N3: density per 10 LOC (code smell = Refactor/LOC*10, unreadability = Convention/LOC*10).
    # Added alongside the raw counts above so comparisons are not confounded by code length,
    # and so numbers are comparable with the RobuNFR paper definition.
    locs = [details["LOC"] for _, details in result.items()]
    for density_name, checker in density_metrics.DENSITY_METRICS.items():
        series = density_metrics.density_series(per_prompt_counts[checker], locs)
        temp_row = copy.deepcopy(new_row)
        for i, value in enumerate(series):
            temp_row[f"prompt{i + 1}"] = value
        temp_row["metrics"] = density_name
        temp_row["AVG"] = numpy.mean(series)
        temp_row["STDEV"] = numpy.std(series, ddof=1)
        NFR_REPORT.loc[len(NFR_REPORT)] = temp_row


def generate_rq2_summary_table(raw_data_path):
    df = pandas.read_excel(raw_data_path)
    model_list = [
        #"gpt-3.5-turbo-1106",
        #"gpt-3.5-turbo-0125",
        #"gpt-4o-2024-05-13",
        #"gpt-4o-2024-08-06",
        "gpt-5.4-2026-03-05", # CHANGE
        #"claude-3-5-sonnet-20240620",
        #"claude-3-5-haiku-20241022"
    ]

    # output raw
    groups = [
        #("direct", "rawGPT"),
        #("direct", "codesmell"), ("sequential", "codesmell"),
        #("direct", "readability"), ("sequential", "readability"),
        #("direct", "error_handling"), ("sequential", "error_handling"),
        ("direct", "performance"), 
        #("sequential", "performance")
    ]
    metrics = ["Total", "Fatal", "Error", "Warning", "Convention", "Refactor", "Information"]
    metrics_num = 28
    for approach, task in groups:
        average_result = list()
        average_data = [0 for _ in range(metrics_num * 2)]
        for each_model in model_list:
            result = list()
            model = each_model
            tdf = df[df["model"] == model]
            tdf = tdf[tdf["task"] == task]
            tdf = tdf[tdf["approach"] == approach]
            for i, benchmark in enumerate([
                "humaneval", 
                #"mbpp"
                ]):
                result_tdf = tdf[tdf["benchmark"] == benchmark]

                # Pass@1
                value = result_tdf[result_tdf["metrics"] == "pass@1"]["AVG"].iloc[0] * 100
                stddev = result_tdf[result_tdf["metrics"] == "pass@1"]["STDEV"].iloc[0] * 100
                et_value = result_tdf[result_tdf["metrics"] == "ET-pass@1"]["AVG"].iloc[0] * 100
                et_stddev = result_tdf[result_tdf["metrics"] == "ET-pass@1"]["STDEV"].iloc[0] * 100
                result.append(f"{value:.2f}±{stddev:.2f} ({et_value:.2f}±{et_stddev:.2f})")
                average_data[0 + i * metrics_num] += value
                average_data[1 + i * metrics_num] += stddev
                average_data[2 + i * metrics_num] += et_value
                average_data[3 + i * metrics_num] += et_stddev

                # LOC
                loc_value = result_tdf[result_tdf["metrics"] == "LOC"]["AVG"].iloc[0]
                loc_stddev = result_tdf[result_tdf["metrics"] == "LOC"]["STDEV"].iloc[0]
                result.append(f"{loc_value:.0f}±{loc_stddev:.0f}")
                average_data[4 + i * metrics_num] += loc_value
                average_data[5 + i * metrics_num] += loc_stddev

                # Exception Density
                value = result_tdf[result_tdf["metrics"] == "exception-density"]["AVG"].iloc[0]
                stddev = result_tdf[result_tdf["metrics"] == "exception-density"]["STDEV"].iloc[0]
                result.append(f"{value:.3f}±{stddev:.3f}")
                average_data[6 + i * metrics_num] += value
                average_data[7 + i * metrics_num] += stddev

                for j, metric in enumerate(metrics):
                    value = result_tdf[result_tdf["metrics"] == metric]["AVG"].iloc[0] / loc_value * 10
                    stddev = result_tdf[result_tdf["metrics"] == metric]["STDEV"].iloc[0] / loc_value * 10
                    result.append(f"{value:.2f}±{stddev:.2f}")
                    average_data[8 + j * 2 + i * metrics_num] += value
                    average_data[9 + j * 2 + i * metrics_num] += stddev

                # Performance
                value = result_tdf[result_tdf["metrics"] == "mean-time"]["AVG"].iloc[0]* 1000
                stddev = result_tdf[result_tdf["metrics"] == "mean-time"]["STDEV"].iloc[0] * 1000
                et_value = result_tdf[result_tdf["metrics"] == "ET-mean-time"]["AVG"].iloc[0] * 1000
                et_stddev = result_tdf[result_tdf["metrics"] == "ET-mean-time"]["STDEV"].iloc[0] * 1000
                # result.append(f"{value:.2f}±{stddev:.2f} ({et_value:.2f}±{et_stddev:.2f})")
                result.append(f"{et_value:.2f}")
                average_data[22 + i * metrics_num] += value
                average_data[23 + i * metrics_num] += stddev
                average_data[24 + i * metrics_num] += et_value
                average_data[25 + i * metrics_num] += et_stddev

                # maintainability
                value = result_tdf[result_tdf["metrics"] == "maintainability"]["AVG"].iloc[0]
                stddev = result_tdf[result_tdf["metrics"] == "maintainability"]["STDEV"].iloc[0]
                result.append(f"{value:.2f}±{stddev:.2f}")
                average_data[26 + i * metrics_num] += value
                average_data[27 + i * metrics_num] += stddev

            need_print = "\t".join(result)
            print(need_print)

        average_data = [x / len(model_list) for x in average_data]
        for i in range(2):
            average_result.append(
                f"{average_data[0 + i * metrics_num]:.2f}±{average_data[1 + i * metrics_num]:.2f}"
                f"({average_data[2 + i * metrics_num]:.2f}±{average_data[3 + i * metrics_num]:.2f})")
            average_result.append(f"{average_data[4 + i * metrics_num]:.0f}±{average_data[5 + i * metrics_num]:.0f}")
            average_result.append(f"{average_data[6 + i * metrics_num]:.3f}±{average_data[7 + i * metrics_num]:.3f}")
            for j in range(8 + i * metrics_num, 8 + i * metrics_num + len(metrics) * 2, 2):
                average_result.append(f"{average_data[j]:.2f}±{average_data[j + 1]:.2f}")
            # average_result.append(
            #     f"{average_data[22 + i * metrics_num]:.2f}±{average_data[23 + i * metrics_num]:.2f}"
            #     f"({average_data[24 + i * metrics_num]:.2f}±{average_data[25 + i * metrics_num]:.2f})")
            average_result.append(
                f"{average_data[24 + i * metrics_num]:.2f}")
            average_result.append(f"{average_data[26 + i * metrics_num]:.2f}±{average_data[27 + i * metrics_num]:.2f}")
        need_print = "\t".join(average_result)
        print(need_print)


if __name__ == "__main__":
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _cfg_path = os.path.join(_repo_root, "nfrgen_experiment.json")
    if os.path.isfile(_cfg_path):
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from nfrgen_experiment import load_config, run_evaluation

        run_evaluation(load_config()[0])
        raise SystemExit(0)
    globals()
    gpt4o_files = {
        "error-handling": [
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt0-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt1-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt2-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt3-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt4-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt5-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt6-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt7-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt8-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-19-gpt4omini-t00-code-GenPrompt-error-handling-prompt9-Trail0.jsonl",
        ],
        "code_smell": [
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt0-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt1-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt2-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt3-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt4-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt5-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt6-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt7-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt8-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-code-smell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-07-20-GenPrompt/2024-07-20-gpt4omini-t00-code-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "rawGPT": [
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-07-31-rq1-rawGPT/2024-07-31-gpt4omini-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "two_steps_errorhandle": [
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-errorhandle-prompt9-Trail0.jsonl",
        ],
        "two_steps_codesmell": [
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-codesmell-prompt9-Trail0.jsonl",
        ],
        "two_steps_readability": [
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt0-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt1-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt2-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt3-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt4-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt5-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt6-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt7-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt8-Trail0.jsonl",
            "../results/2024-08-06-two-steps/2024-08-06-gpt4o-mini-t00-GenPrompt-twoSteps-readability-prompt9-Trail0.jsonl",
        ],
    }
    gpt35_0125_files = {
        "codesmell": [
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "rawGPT": [
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-20-rq1-gpt35-0125-humaneval-performance/2024-11-20-gpt35-0125-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ],
    }
    gpt35_1106_files = {
        "codesmell": [
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "rawGPT": [
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-19-rq1-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ],
    }
    gpt4o_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "code_smell": [
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-04-gpt4o-mini-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-03-rq1-mbpp/2024-08-03-gpt4o-mini-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    gpt4o_0513_files = {
        "rawGPT": [
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-17-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-15-gpt-4o-0513-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    gpt4o_0513_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-20-gpt4o-0513-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq1-gpt4o-0513-mbpp-performance/2024-11-22-gpt4o-0513-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    gpt4o_0806_files = {
        "rawGPT": [
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    gpt4o_0806_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt4o-0806-mbpp-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    gpt35_0125_mbpp_files = {
        "error_handling": [
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-0125-mbpp-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ],
    }
    gpt35_1106_mbpp_files = {
        "error_handling": [
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq1-gpt35-1106-mbpp-performance/2024-11-21-gpt35-1106-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    rq2_gpt35_0125_humaneval_files = {
        "rawGPT": [
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-0125/2024-08-03-gpt35-0125-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt0-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt1-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt2-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt3-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt4-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt5-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt6-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt7-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt8-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-error-handle-prompt9-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps/2024-09-13-gpt-35-0125-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-humaneval-performance/2024-11-21-gpt35-0125-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    rq2_gpt35_1106_humaneval_files = {
        "rawGPT": [
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-03-rq1-gpt35-1106/2024-08-03-gpt35-1106-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-1106-two-steps/2024-09-13-gpt-35-1106-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-19-rq2-gpt35-1106-humaneval-performance/2024-11-19-gpt35-1106-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    rq2_gpt35_0125_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-0125-mbpp/2024-08-19-gpt35-0125-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-13-gpt-35-0125-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-13-rq2-gpt35-0125-two-steps-mbpp/2024-09-14-gpt-35-0125-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-0125-mbpp-performance/2024-11-21-gpt-35-0125-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    rq2_gpt35_1106_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt35-1106-mbpp/2024-08-19-gpt35-1106-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-14-rq2-gpt35-1106-two-steps-mbpp/2024-09-14-gpt-35-1106-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt35-1106-mbpp-performance/2024-11-21-gpt-35-1106-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    rq2_gpt4o_0806_humaneval_files = {
        "rawGPT": [
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0806/2024-08-15-gpt-4o-0806-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806/2024-09-19-gpt-4o-0806-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-humaneval-performance/2024-11-21-gpt4o-0806-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    rq2_gpt4o_0513_humaneval_files = {
        "rawGPT": [
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt3-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt4-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt5-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt6-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt7-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt8-Trail0.jsonl",
            "../results/2024-08-15-gpt-4o-0513/2024-08-16-gpt-4o-0513-t00-GenPrompt-rawGPT-prompt9-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt5-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt6-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt7-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt8-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt9-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt5-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt6-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt7-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt8-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-codesmell-prompt9-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt5-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt6-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt7-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt8-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0513/2024-09-19-gpt-4o-0513-t00-GenPrompt-readability-prompt9-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0513-humaneval-performance/2024-11-21-gpt4o-0513-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    rq2_gpt4o_0806_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0806-mbpp/2024-08-19-gpt4o-0806-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-19-gpt-4o-0806-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-19-rq2-two-steps-gpt4o0806-mbpp/2024-09-20-gpt-4o-0806-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-21-rq2-gpt4o-0806-mbpp-performance/2024-11-21-gpt-4o-0806-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    rq2_gpt4o_0513_mbpp_files = {
        "rawGPT": [
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-08-19-rq1-gpt-4o-0513-mbpp/2024-08-19-gpt4o-0513-t00-GenPrompt-rawGPT-prompt9-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-errorhandle-prompt9-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-codesmell-prompt9-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-09-20-rq2-two-steps-gpt4o0513-mbpp/2024-09-20-gpt-4o-0513-t00-GenPrompt-readability-prompt9-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt5-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt6-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt7-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt8-mbpp-Trail0.jsonl",
            "../results/2024-11-22-rq2-gpt4o-0513-mbpp-performance/2024-11-22-gpt-4o-0513-t00-GenPrompt-performance-prompt9-mbpp-Trail0.jsonl",
        ]
    }
    rq1_claude35_0620_humaneval_files = {
        "rawGPT": [
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-raw-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-raw-prompt4-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
        ]
    }
    rq1_claude35_1022_humaneval_files = {
        "rawGPT": [
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
        ]
    }
    rq1_claude35_haiku_humaneval_files = {
        "rawGPT": [
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt0-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt1-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt2-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt3-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt4-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
        ]
    }
    rq2_claude35_0620_humaneval_files = {
        "rawGPT": [
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20240620-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-raw-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq1-humaneval/2024-11-21-claude35-sonnet-0620-t00-GenPrompt-raw-prompt4-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-18-claude-3-5-20240620-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-18-claude35-0620-rq2-humaneval/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
        ]
    }
    rq2_claude35_1022_humaneval_files = {
        "rawGPT": [
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-rawGPT-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-rawGPT-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq1-humaneval/2024-11-18-claude-3-5-sonnet-20241022-t00-GenPrompt-rawGPT-prompt2-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-18-claude-3-5-20241022-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            # "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-18-claude-3-5-20241022-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            # "../results/2024-11-18-claude35-1022-rq2-humaneval/2024-11-19-claude-3-5-20241022-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
        ]
    }
    rq2_claude35_haiku_humaneval_files = {
        "rawGPT": [
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt0-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt1-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt2-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt3-Trail0.jsonl",
            "../results/2024-11-20-claude35-haiku-rq1-humaneval/2024-11-20-claude35-haiku-t00-GenPrompt-raw-prompt4-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2024-11-21-claude35-haiku-rq2-humaneval/2024-11-21-claude35-haiku-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
        ]
    }
    rq1_claude35_0620_mbpp_files = {
        "rawGPT": [
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt4-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
        ]
    }
    rq1_claude35_haiku_mbpp_files = {
        "rawGPT": [
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt4-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
        ]
    }
    rq2_claude35_0620_mbpp_files = {
        "rawGPT": [
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq1-mbpp/2024-11-22-claude35-sonnet-0620-t00-GenPrompt-raw-prompt4-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-sonnet0620-rq2-mbpp/2024-11-23-claude35-sonnet0620-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
        ]
    }
    rq2_claude35_haiku_mbpp_files = {
        "rawGPT": [
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq1-mbpp/2024-11-22-claude35-haiku-t00-GenPrompt-raw-prompt4-mbpp-Trail0.jsonl",
        ],
        "readability": [
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
        ],
        "codesmell": [
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
        ],
        "error_handling": [
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
        ],
        "performance": [
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
            "../results/2024-11-22-claude35-haiku-rq2-mbpp/2024-11-23-claude35-haiku-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
        ]
    }
    rq1_gpt_54_2026_03_05_humaneval_files = {
        "rawGPT": [
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt0-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt1-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt2-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt3-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt4-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt5-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt6-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt7-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt8-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-09-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt9-Trail0.jsonl",
        ],
        # "readability": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt0-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt1-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt2-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt3-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt4-Trail0.jsonl",
        # ],
        # "codesmell": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt0-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt1-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt2-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt3-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt4-Trail0.jsonl",
        # ],
        # "error_handling": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt0-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt1-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt2-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt3-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq2-humaneval/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt4-Trail0.jsonl",
        # ],
        "performance": [
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt0-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt1-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt2-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt3-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt4-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt5-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt6-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt7-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt8-Trail0.jsonl",
            "../results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt9-Trail0.jsonl",
        ]
    }
    rq1_gpt_54_2026_03_05_mbpp_files = {
        # "rawGPT": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt0-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt1-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt2-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt3-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-raw-prompt4-mbpp-Trail0.jsonl",
        # ],
        # "readability": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt0-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt1-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt2-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt3-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-readability-prompt4-mbpp-Trail0.jsonl",
        # ],
        # "codesmell": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt0-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt1-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt2-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt3-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt4-mbpp-Trail0.jsonl",
        # ],
        # "error_handling": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt0-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt1-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt2-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt3-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt4-mbpp-Trail0.jsonl",
        # ],
        # "performance": [
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt0-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt1-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt2-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt3-mbpp-Trail0.jsonl",
        #     "../results/2026-04-08-gpt-54-2026-03-05-rq1-mbpp/2026-04-08-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt4-mbpp-Trail0.jsonl",
        # ]
    }
    final_results = None
    approach1, approach2 = "direct", "sequential"
    results_set = {
        "mbpp": [
            (approach1, "gpt-3.5-turbo-1106", gpt35_1106_mbpp_files),
            (approach1, "gpt-3.5-turbo-0125", gpt35_0125_mbpp_files),
            (approach1, "gpt-4o-2024-08-06", gpt4o_0806_mbpp_files),
            (approach1, "gpt-4o-2024-05-13", gpt4o_0513_mbpp_files),
            (approach2, "gpt-3.5-turbo-1106", rq2_gpt35_1106_mbpp_files),
            (approach2, "gpt-3.5-turbo-0125", rq2_gpt35_0125_mbpp_files),
            (approach2, "gpt-4o-2024-08-06", rq2_gpt4o_0806_mbpp_files),
            (approach2, "gpt-4o-2024-05-13", rq2_gpt4o_0513_mbpp_files),
            (approach2, "gpt-5.4-2026-03-05", rq1_gpt_54_2026_03_05_mbpp_files),
            (approach1, "claude-3-5-sonnet-20240620", rq1_claude35_0620_mbpp_files),
            (approach1, "claude-3-5-haiku-20241022", rq1_claude35_haiku_mbpp_files),
            (approach2, "claude-3-5-sonnet-20240620", rq2_claude35_0620_mbpp_files),
            (approach2, "claude-3-5-haiku-20241022", rq2_claude35_haiku_mbpp_files)
        ],
        "humaneval": [
            (approach1, "gpt-3.5-turbo-0125", gpt35_0125_files),
            (approach1, "gpt-3.5-turbo-1106", gpt35_1106_files),
            (approach1, "gpt-4o-2024-05-13", gpt4o_0513_files),
            (approach1, "gpt-4o-2024-08-06", gpt4o_0806_files),
            (approach2, "gpt-3.5-turbo-0125", rq2_gpt35_0125_humaneval_files),
            (approach2, "gpt-3.5-turbo-1106", rq2_gpt35_1106_humaneval_files),
            (approach2, "gpt-4o-2024-08-06", rq2_gpt4o_0806_humaneval_files),
            (approach2, "gpt-4o-2024-05-13", rq2_gpt4o_0513_humaneval_files),
            (approach1, "gpt-5.4-2026-03-05", rq1_gpt_54_2026_03_05_humaneval_files),
            (approach1, "claude-3-5-sonnet-20240620", rq1_claude35_0620_humaneval_files),
            (approach1, "claude-3-5-haiku-20241022", rq1_claude35_haiku_humaneval_files),
            (approach2, "claude-3-5-sonnet-20240620", rq2_claude35_0620_humaneval_files),
            (approach2, "claude-3-5-haiku-20241022", rq2_claude35_haiku_humaneval_files)
        ],
    }
    target_path = "../results/2026-04-08-pylint-radon-meta-results/radon-correct-code-analysis.xlsx"
    # CHANGE TO RUN ALL
    # for dataset, answer_set in results_set.items():
    #     for approach_name, model_name, each_result in answer_set:
    #         for label in ["rawGPT", "error_handling", "codesmell", "readability", "performance"]:
    #             if label in each_result:
    #                 if model_name == "gpt-5.4-2026-03-05": # CHANGE TO RUN ALL
    #                     final_results = get_final_result(each_result[label], dataset)

    #                     generate_nfr_report(final_results, dataset, label, approach_name, model_name)
    #                     NFR_REPORT.to_excel(target_path, index=False)
    # Executar apenas o humaneval do gpt 54
    final_results = get_final_result(rq1_gpt_54_2026_03_05_humaneval_files["performance"], "humaneval") # CHANGE
    generate_nfr_report(final_results, "humaneval", "performance", approach1, "gpt-5.4-2026-03-05")
    print('NFR_REPORT.to_excel(target_path, index=False)')
    NFR_REPORT.to_excel(target_path, index=False)
    print('generate_rq2_summary_table')
    generate_rq2_summary_table(target_path) # Deu ERRO
    # dataset = "mbpp"
    # final_results = get_final_result(rq2_gpt4o_0513_mbpp_files["performance"], dataset)
    # if final_results:
    #     generate_google_docs_report(final_results, dataset)
    # else:
    #     print("No final results found")

    # generate_excel_sheet(final_results, target_path)

    # break
    pass