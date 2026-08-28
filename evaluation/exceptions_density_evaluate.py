#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import json
import re


class ExceptionsDensityEvaluate:
    def __init__(self):
        pass

    def get_non_code_count(self, raw_response):
        count_length = 0
        if "```python" in raw_response:
            non_code_part1 = re.findall("([\s\S]+?)```python[\s\S]+?```", raw_response, re.S)
            non_code_part1 = non_code_part1[0] if len(non_code_part1) > 0 else ""
            non_code_part2 = re.findall("```python[\s\S]+?```([\s\S]+)", raw_response, re.S)
            non_code_part2 = non_code_part2[0] if len(non_code_part2) > 0 else ""
            non_code = non_code_part1 + non_code_part2
        else:
            non_code = raw_response
        for each_line in non_code.split("\n"):
            if each_line.strip() != "":
                count_length += 1
        word_count = len(re.findall(r"\b\w+\b", non_code))
        return count_length, word_count

    def get_comment_loc(self, code):
        count_length = 0
        for each_line in code.split("\n"):
            if each_line.startswith("candidate "):
                break
            if each_line.strip() != "":
                if each_line.strip().startswith("#") or "#" in each_line:
                    count_length += 1
        return count_length

    def get_loc(self, code):
        count_length = 0
        for each_line in code.split("\n"):
            if each_line.startswith("candidate "):
                break
            if each_line.strip() != "":
                count_length += 1
        return count_length

    def exception_count(self, raw_code):
        result = 0
        except_times = re.findall(r"except.*:", raw_code)
        result += len(except_times)
        except_times = re.findall(r"if.+:\n.+raise", raw_code)
        result += len(except_times)
        return result

    def evaluate(self, file_path, dataset="humaneval"):
        with open(file_path, "r") as file:
            answers = json.load(file)
            length, total_pass, total_pass_et, total_loc, total_exceptions = len(answers), 0, 0, 0, 0
            comment_loc, total_non_code_length, total_non_code_word = 0, 0, 0
            for qid, each_answer in answers.items():
                loc = self.get_loc(each_answer["code"])
                comment_loc += self.get_comment_loc(each_answer["code"])
                non_code_length, non_code_word = self.get_non_code_count(each_answer["raw_response"])
                total_non_code_length += non_code_length
                total_non_code_word += non_code_word
                exceptions = self.exception_count(each_answer["code"])
                total_pass += 1 if "\nOK\n" in each_answer[f"{dataset}_result"] else 0
                total_pass_et += 1 if "\nOK\n" in each_answer[f"{dataset}_et_result"] else 0
                total_loc += loc
                total_exceptions += exceptions
            # print(f"{file_path}\t{total_loc}\t{total_exceptions/total_loc * 10}")
            # print(f"{total_pass / length:.2%}\t{total_pass_et / length:.2%}\t"
            #       f"{total_loc}\t{total_exceptions / total_loc * 10}")
        return {"loc": total_loc, "comment_loc": comment_loc, "non_code_length": total_non_code_length,
                "non_code_word": total_non_code_word,
                "exceptions-density per 10 loc": total_exceptions / total_loc * 10}


if __name__ == "__main__":
    files = [
        # "../results/2024-03-29/2024-03-29-0125-basic-prompt-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-29-0125-Trail2basic-prompt-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-29-0125-t7-Trail0basic-prompt-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-29-0125-t7-Trail1basic-prompt-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-29-0125-t0-Trail0basic-prompt-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-29-0125-t0-Trail1basic-prompt-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-30-0125-t07-exceptions-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-30-0125-t07-exceptions-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-no-structure-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-no-structure-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-30-0125-t07-exceptions-2-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-03-30-0125-t07-exceptions-2-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-step-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-step-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-json-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-json-Trail2-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-json-Trail3-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-json-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-md-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-md-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-md-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-md-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-diff-sentence-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-diff-sentence-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-diff-sentence-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-diff-sentence-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-diff-word-oper-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-diff-word-oper-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-diff-word-oper-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-diff-word-oper-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-diff-keyword-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t07-exceptions-diff-keyword-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-diff-keyword-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-01-0125-t00-exceptions-diff-keyword-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-02-0125-t07-exceptions-diff-keyword2-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-02-0125-t07-exceptions-diff-keyword2-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-02-0125-t00-exceptions-diff-keyword2-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-03-29/2024-04-02-0125-t00-exceptions-diff-keyword2-Trail1-humaneval_evaluate_result.json",
        # "../results/2024-04-09-langgraph/2024-04-09-0125-t00-langgraph-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-09-0125-t00-format-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-10-0125-t00-format-raw-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-10-0125-t00-format-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-10-0125-t00-format-markdown-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-10-0125-t00-format-yaml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-10-0125-t00-format-csv-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-09-format-mutation/2024-05-10-0125-t00-format-xml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-1106-t00-format-raw-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-1106-t00-format-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-1106-t00-format-markdown-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-1106-t00-format-yaml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-1106-t00-format-csv-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-1106-t00-format-xml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-gpt4o-0513-t00-format-raw-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-17-gpt4o-0513-t00-format-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4o-0513-t00-format-markdown-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4o-0513-t00-format-yaml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4o-0513-t00-format-csv-Trail0-humaneval_evaluate_result.json",
        # # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4o-0513-t00-format-xml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0409-t00-format-raw-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0409-t00-format-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0409-t00-format-markdown-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0409-t00-format-yaml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0409-t00-format-csv-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0409-t00-format-xml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0125-t00-format-raw-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0125-t00-format-json-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0125-t00-format-markdown-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0125-t00-format-yaml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0125-t00-format-csv-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-05-17-format-mutation-diff-models/2024-05-18-gpt4-0125-t00-format-xml-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-02-mask-code-evalplus/2024-07-02-gpt35-0125-t00-code-mask-15-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-02-mask-code-humaneval/2024-07-02-gpt35-0125-t00-code-mask-15-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-09-mask-top-end-code/2024-07-09-gpt35-0125-t00-code-mask-end-15-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-09-mask-top-end-code/2024-07-09-gpt35-0125-t00-code-mask-top-15-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-17-genPrompt/2024-07-17-gpt35-0125-t00-code-GenPrompt-code-smell-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-17-genPrompt/2024-07-17-gpt35-0125-t00-code-GenPrompt-readability-Trail0-humaneval_evaluate_result.json",
        # "../results/2024-07-17-genPrompt/2024-07-17-gpt35-0125-t00-code-GenPrompt-Trail0-humaneval_evaluate_result.json",
        "../results/2026-07-07-genPrompt/2026-07-07-gpt-54-2026-03-05-t00-code-GenPrompt-code-smell-Trail0-humaneval_evaluate_result.json",
        "../results/2026-07-07-genPrompt/2026-07-07-gpt-54-2026-03-05-t00-code-GenPrompt-readability-Trail0-humaneval_evaluate_result.json",
        "../results/2026-07-07-genPrompt/2026-07-07-gpt-54-2026-03-05-t00-code-GenPrompt-Trail0-humaneval_evaluate_result.json",
    ]
    ede = ExceptionsDensityEvaluate()
    for each_file in files:
        ede.evaluate(each_file)
