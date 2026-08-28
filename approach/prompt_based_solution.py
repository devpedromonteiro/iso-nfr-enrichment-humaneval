#!/bin/env python3
# -*- coding: utf-8 -*-
# version: Python3.X
import os
import openai
import re
import json
import anthropic
import yaml
import xml.etree.ElementTree as ET
from xmljson import Parker


class Solution:
    def __init__(self, client, temperature=0.7, model="gpt-3.5-turbo-0125"):
        self.client = client
        self.basic_prompt = f"Complete the following code:\n"
        self.temperature = temperature
        self.model = model
        # Token usage of the most recent request (mitigation note: lets us document
        # input/output token counts and estimate cost per generation, see token_report.py).
        self.last_usage = {}

    @staticmethod
    def _extract_openai_usage(completion, model):
        """Best-effort token usage from an OpenAI chat completion (None-safe)."""
        usage = getattr(completion, "usage", None)
        if usage is None:
            return {}
        return {
            "model": model,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    @staticmethod
    def _extract_claude_usage(response, model):
        """Best-effort token usage from an Anthropic message (None-safe)."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        return {
            "model": model,
            "prompt_tokens": getattr(usage, "input_tokens", None),
            "completion_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": None,
        }

    @staticmethod
    def generate_raw_format_prompt(json_data, raw_function_str):
        prompt = f"""{json_data["Task"]}:\n{raw_function_str}"""
        return prompt

    @staticmethod
    def generate_markdown_format_prompt(json_data):
        prompt = ""
        for key, values in json_data.items():
            prompt += f"# {key} \n {values}\n"
        return prompt

    @staticmethod
    def generate_yaml_format_prompt(json_data):
        return yaml.dump(json_data)

    @staticmethod
    def generate_xml_format_prompt(json_data):
        parker = Parker()
        xml_data = parker.etree(json_data)
        root = ET.Element("root")
        for child in xml_data:
            root.append(child)
        xml_string = ET.tostring(root, encoding='unicode')
        return xml_string

    @staticmethod
    def generate_csv_format_prompt(json_data):
        headers = list(json_data.keys())
        prompt = f"{','.join(headers)}\n"
        prompt += ",".join([f'"{x}"' for x in json_data.values()])
        prompt += "\n"
        return prompt

    def _get_function_str(self, raw_str):
        if raw_str.count("def ") == 1:
            return None, raw_str
        elif raw_str.count("def ") == 2:
            result = re.findall(r"(?m)^def\s+\w+\s*.*?(?=def|\Z)", raw_str, re.DOTALL)
            return result[0], result[1]
        else:
            raise Exception

    def generate_formatting_prompt(self, function_str, expected_format="json"):
        raw_function_str = function_str
        apis, function_str = self._get_function_str(function_str)
        function_name_pattern = r"def\s+(\w+)\s*\("
        parameters_pattern = r"\((.*?)\)"
        return_type_pattern = r"->\s*(\w+)\s*"
        docstring_pattern = r'["\']{3}(.*?)["\']{3}'
        examples_pattern = r">>>\s*(.*?)\n\s*(.*?)\n"
        feature_pattern = r'^(.*?)>>>'

        function_name: str = re.search(function_name_pattern, function_str).group(1)
        parameters: str = re.search(parameters_pattern, function_str).group(1)
        return_type = re.search(return_type_pattern, function_str)
        if return_type:
            return_type = return_type.group(1)
        docstring: str = re.search(docstring_pattern, function_str, re.DOTALL).group(1)
        if ">>>" not in docstring:
            feature_match: str = docstring
        else:
            feature_match: str = re.search(feature_pattern, docstring, re.DOTALL).group(1)
        examples: list = re.findall(examples_pattern, function_str, re.DOTALL)

        # Format examples as specified
        formatted_examples = [f"{call.strip()} == {result.strip()}" for call, result in examples]

        # Generate JSON object
        json_data = {
            "function name": function_name,
            "parameters": parameters,
            "feature": feature_match.strip(),
            "Task": "Consider different exception handle and Complete the Python code"
        }
        for key, values in json_data.items():
            assert len(values) > 0, f"[-] {key} empty, {function_str}"
        json_data["examples"] = formatted_examples
        if return_type:
            json_data["return value"] = return_type
        if apis is not None:
            json_data["APIs"] = apis

        if expected_format.lower() == "json":
            return json_data
        elif expected_format.lower() == "raw":
            return self.generate_raw_format_prompt(json_data, raw_function_str)
        elif expected_format.lower() == "markdown":
            return self.generate_markdown_format_prompt(json_data)
        elif expected_format.lower() == "yaml":
            return self.generate_yaml_format_prompt(json_data)
        elif expected_format.lower() == "csv":
            return self.generate_csv_format_prompt(json_data)
        elif expected_format.lower() == "xml":
            return self.generate_xml_format_prompt(json_data)
        else:
            raise Exception("Unsupported format type")

    def format_mutation(self, problem, expected_format="json"):
        generated_prompt = self.generate_formatting_prompt(problem, expected_format)
        final_prompt = json.dumps(generated_prompt, indent=4)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                # {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
                {"role": "user", "content": final_prompt}
            ],
            temperature=self.temperature
        )

        return completion.choices[0].message.content, final_prompt

    def raw(self, problem):
        final_prompt = f"Consider different exception handle and {self.basic_prompt}{problem}"
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                # {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
                {"role": "user", "content": final_prompt}
            ],
            temperature=self.temperature
        )

        return completion.choices[0].message.content, final_prompt

    def basic(self, problem):
        final_prompt = f"{self.basic_prompt}{problem}"
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                # {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
                {"role": "user", "content": final_prompt}
            ],
            temperature=self.temperature
        )

        return completion.choices[0].message.content, final_prompt

    def two_steps_code_enhancement(self, problem, prompt):
        result = dict()
        # first step
        final_prompt = f"{problem}"
        result["first_step_prompt"] = final_prompt
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                # {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
                {"role": "user", "content": final_prompt}
            ],
            temperature=self.temperature
        )
        result["first_step_response"] = completion.choices[0].message.content

        # second step
        if "```python" in result["first_step_response"]:
            purify_response = re.findall(r"```python\n(.*?)```", result["first_step_response"], re.DOTALL)[0]
            final_prompt = f"{prompt}\n{purify_response}"
        else:
            final_prompt = f"{prompt}\n{result['first_step_response']}"
        result["second_step_prompt"] = final_prompt
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                # {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
                {"role": "user", "content": final_prompt}
            ],
            temperature=self.temperature
        )
        result["second_step_response"] = completion.choices[0].message.content
        return completion.choices[0].message.content, final_prompt, result

    def exception_handle(self, problem, prompt):
        final_prompt = f"{prompt}\n{problem}"

        if "claude" in self.model.lower():
            response = self.claude_request(final_prompt)
        elif "gpt" in self.model.lower():
            response = self.openai_request(final_prompt)
        else:
            raise Exception("Unsupported model")
        # Carry token usage out via the "others" dict; run_humaneval merges it into the saved result.
        return response, final_prompt, dict(self.last_usage)

    def second_step_code_enhancement(self, problem, prompt, baseline_file, problem_id):
        with open(baseline_file, "r") as f:
            for each_line in f:
                each_line = json.loads(each_line)
                if each_line["task_id"] == problem_id:
                    baseline_code = each_line["completion"]
                    break
            else:
                raise Exception("Baseline code not found")

        if "```python" in baseline_code:
            baseline_code = re.findall(r"```python\n(.*?)```", baseline_code, re.DOTALL)[0]
        final_prompt = f"Problem:\n{problem}\n\n{prompt}\n{baseline_code}"

        if "claude" in self.model.lower():
            response = self.claude_request(final_prompt)
        elif "gpt" in self.model.lower():
            response = self.openai_request(final_prompt)
        else:
            raise Exception("Unsupported model")
        return response, final_prompt, dict(self.last_usage)

    def openai_request(self, prompt):
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature
        )
        self.last_usage = self._extract_openai_usage(completion, self.model)
        return completion.choices[0].message.content

    def claude_request(self, prompt):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=self.temperature,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        self.last_usage = self._extract_claude_usage(response, self.model)
        return response.content[0].text


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    question = '''
from typing import List

def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """ Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """
'''

    with open("../conf.json", "r") as f:
        api_key = json.load(f)["openai-key"] # CHANGE
    client = openai.OpenAI(api_key=api_key) # CHANGE
    # client = anthropic.Anthropic(api_key=api_key) # CHANGE
    solution = Solution(client, model="gpt-5.4-2026-03-05") # CHANGE
    answer, _, _ = solution.exception_handle(question, "")
    print(answer)
