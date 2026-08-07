"""NFR prompt blocks (single source of truth). Keys match nfrgen_experiment.json -> generation.nfr_prompt_set.

This module is the single place that builds the prompt strings fed to the LLM. It now
supports the THREE paired conditions of the experiment (see planejamento_final.md §3):

    - "natural"      -> NL-simples : the original one-line NFR phrase (RobuNFR baseline).
    - "rich_natural" -> NL-rico    : the SAME ISO-grounded content as the structured
                                     condition, written in prose (controls *content*).
    - "structured"   -> Estruturado: the SAME content serialized as JSON/YAML grounded in
                                     ISO/IEC 25010 (the *form* under test).

Why three conditions: comparing only "one short phrase" vs "a rich JSON spec" would confound
*content* with *form* (threat 1.1 / N1). By keeping NL-rico and Estruturado with identical
content and varying only the representation, NL-rico x Estruturado isolates the effect of the
*structure*, while NL-simples x NL-rico isolates the effect of the *content*.

Threats mitigated directly by this module:
    - 1.1 (form vs content) : NL-rico and Estruturado share the exact same content.
    - N1 (test-passing leak) : acceptance_criteria never mention "pass the tests" /
                               "functional correctness"; they describe the quality attribute only.
    - N10 (task clause)      : every condition ends with the identical functional clause
                               ("complete the following code:" for RQ1 / "improve the following
                               code:" for RQ2).
    - 1.4 (framing header)   : NL-rico and Estruturado share a symmetric "Consider the following
                               non-functional requirement ..." framing.
    - N7/N6 (provenance/diversity) : NL-rico and Estruturado are derived from ONE content source,
                               so their input diversity is identical by construction.
    - N11 (ISO mapping)      : the NFR -> ISO/IEC 25010 mapping is explicit and documented here.
"""

import json

# ---------------------------------------------------------------------------
# RQ1 / one-shot: "complete the following code"  (NL-simples baseline; unchanged)
# ---------------------------------------------------------------------------
RQ1 = {
    "raw": """








""",
    "performance": """Optimize for performance and complete the following code:
Focus on enhancing performance and complete the following code:
Ensure the code runs efficiently and complete the following code:
Prioritize runtime optimization and complete the following code:
Keep performance in mind while solving and complete the following code:
Aim for high-performance execution and complete the following code:
Reduce computational overhead and complete the following code:
Emphasize speed and efficiency and complete the following code:
Ensure minimal resource consumption and complete the following code:
Maximize performance in your solution and complete the following code:""",
    "codesmell": """Investigate various strategies to handle code smell and complete the following code:
Minimize code smell and complete the following code:
Eliminate code smell and complete the following code:
Identify and address different code smells and complete the following code:
Apply best practices to reduce code smell and complete the following code:
Mitigate code smell and complete the following code:
Tackle different code smell issues and complete the following code:
Implement techniques to prevent code smell and complete the following code:
Resolve code smell problems and complete the following code:
Optimize code to avoid code smell and complete the following code:""",
    "readability": """Evaluate different coding practices for readability and complete the following code:
Investigate various techniques to enhance readability and complete the following code:
Improve the code readability and complete the following code:
Ensure the code is readable and complete the following code:
Apply coding practices that enhance readability and complete the following code:
Focus on readability and complete the following code:
Enhance the readability of the code and complete the following code:
Implement strategies to make the code more readable and complete the following code:
Optimize the code for better readability and complete the following code:
Adopt coding practices for improved readability and complete the following code:""",
    "errorhandle": """Incorporate various error handling techniques and complete the following code:
Implement multiple exception handling strategies and complete the following code:
Apply different error handling mechanisms and complete the following code:
Investigate different methods of managing exceptions and complete the following code:
Integrate diverse error handling approaches and complete the following code:
Utilize multiple error management techniques and complete the following code:
Experiment with various ways to handle exceptions and complete the following code:
Combine different error handling practices and complete the following code:
Evaluate multiple exception management strategies and complete the following code:
Develop a range of error handling solutions and complete the following code:""",
}

# ---------------------------------------------------------------------------
# RQ2 / two-step prompts: "improve the following code" (NL-simples baseline; unchanged)
# ---------------------------------------------------------------------------
RQ2 = {
    "raw": RQ1["raw"],
    "performance": """Optimize for performance and improve the following code:
Focus on enhancing performance and improve the following code:
Ensure the code runs efficiently and improve the following code:
Prioritize runtime optimization and improve the following code:
Keep performance in mind while solving and improve the following code:
Aim for high-performance execution and improve the following code:
Reduce computational overhead and improve the following code:
Emphasize speed and efficiency and improve the following code:
Ensure minimal resource consumption and improve the following code:
Maximize performance in your solution and improve the following code:""",
    "codesmell": """Investigate various strategies to handle code smell and improve the following code:
Minimize code smell and improve the following code:
Eliminate code smell and improve the following code:
Identify and address different code smells and improve the following code:
Apply best practices to reduce code smell and improve the following code:
Mitigate code smell and improve the following code:
Tackle different code smell issues and improve the following code:
Implement techniques to prevent code smell and improve the following code:
Resolve code smell problems and improve the following code:
Optimize code to avoid code smell and improve the following code:""",
    "readability": """Evaluate different coding practices for readability and improve the following code:
Investigate various techniques to enhance readability and improve the following code:
Improve the code readability and improve the following code:
Ensure the code is readable and improve the following code:
Apply coding practices that enhance readability and improve the following code:
Focus on readability and improve the following code:
Enhance the readability of the code and improve the following code:
Implement strategies to make the code more readable and improve the following code:
Optimize the code for better readability and improve the following code:
Adopt coding practices for improved readability and improve the following code:""",
    "errorhandle": """Incorporate various error handling techniques and improve the following code:
Implement multiple exception handling strategies and improve the following code:
Apply different error handling mechanisms and improve the following code:
Investigate different methods of managing exceptions and improve the following code:
Integrate diverse error handling approaches and improve the following code:
Utilize multiple error management techniques and improve the following code:
Experiment with various ways to handle exceptions and improve the following code:
Combine different error handling practices and improve the following code:
Evaluate multiple exception management strategies and improve the following code:
Develop a range of error handling solutions and improve the following code:""",
}

# ---------------------------------------------------------------------------
# ISO/IEC 25010:2023 mapping (planejamento_final.md §2). Documented as a design
# decision, as required by ISO/IEC 25002:2024 §5 (mitigates N11).
# ---------------------------------------------------------------------------
ISO25010 = {
    "performance": {
        "characteristic": "Performance Efficiency",
        "subcharacteristics": ["Time Behaviour", "Resource Utilization"],
    },
    "errorhandle": {
        "characteristic": "Reliability",
        "subcharacteristics": ["Fault Tolerance", "Recoverability"],
    },
    "codesmell": {
        "characteristic": "Maintainability",
        "subcharacteristics": ["Modularity", "Analysability"],
    },
    "readability": {
        "characteristic": "Maintainability",
        "subcharacteristics": ["Analysability", "Modifiability"],
    },
}

# "associated constraints and conditions" (ISO/IEC 25002:2024, 3.25). One fixed
# set per NFR, shared by NL-rico and Estruturado.
CONSTRAINTS = {
    "performance": [
        "minimize the time complexity of the core algorithm",
        "avoid redundant computation and unnecessary allocations",
    ],
    "errorhandle": [
        "validate inputs and handle invalid arguments explicitly",
        "use specific exception types and do not silently swallow errors",
    ],
    "codesmell": [
        "avoid duplicated logic and overly long functions",
        "prefer cohesive, single-responsibility code with low coupling",
    ],
    "readability": [
        "use descriptive names and consistent formatting",
        "keep the control flow simple and easy to follow",
    ],
}

# Quality objectives / acceptance criteria. IMPORTANT (N1): these describe ONLY the
# quality attribute. They must NOT mention passing tests or functional correctness,
# otherwise pass@1 of the structured condition would rise because of the instruction,
# not because of the structure.
ACCEPTANCE = {
    "performance": [
        "average execution time is not worse than a straightforward solution",
        "resource usage stays bounded",
    ],
    "errorhandle": [
        "invalid inputs raise or handle the appropriate, specific exceptions",
        "error paths do not leave the program in an inconsistent state",
    ],
    "codesmell": [
        "the solution exposes no obvious code smells under static analysis",
        "responsibilities are clearly separated across the code",
    ],
    "readability": [
        "the code can be read and understood without additional explanation",
        "names and structure make the intent self-evident",
    ],
}

# Identical functional clause across all conditions (mitigates N10).
FUNCTIONAL_CLAUSE = {
    "rq1": "complete the following code:",
    "rq2": "improve the following code:",
}

# Tails appended to the NL-simples phrases, stripped to recover the bare intent.
_TAILS = (
    " and complete the following code:",
    " and improve the following code:",
)

PROMPT_FORMATS = ("natural", "rich_natural", "structured")

# NFRs that carry an ISO-grounded specification (everything except the "raw" baseline).
STRUCTURED_NFRS = tuple(ISO25010.keys())


def validate_nfr_key(nfr_key, rq):
    """rq is 'rq1' or 'rq2'."""
    table = RQ1 if rq == "rq1" else RQ2
    if nfr_key not in table:
        raise ValueError(f"Unknown nfr_prompt_set {nfr_key!r}. Choose one of: {sorted(table.keys())}")


def _mode_key(mode):
    """Normalize 'rq1'/'rq2' (default rq1)."""
    return "rq2" if str(mode).lower() == "rq2" else "rq1"


def _strip_tail(nl_phrase):
    """Remove the boilerplate functional tail so only the NFR intent remains."""
    phrase = nl_phrase.strip()
    for tail in _TAILS:
        if phrase.endswith(tail):
            return phrase[: -len(tail)].strip()
    return phrase


def _intents(nfr_key, mode):
    """Return the 10 bare intents derived from the NL-simples variations of this NFR."""
    table = RQ1 if _mode_key(mode) == "rq1" else RQ2
    return [_strip_tail(line) for line in table[nfr_key].split("\n")]


def _rich_header(mode):
    """Symmetric framing header for NL-rico (mitigates 1.4)."""
    clause = FUNCTIONAL_CLAUSE[_mode_key(mode)]
    return f"Consider the following non-functional requirement and its constraints, and {clause}"


def _structured_header(mode, serialization):
    """Symmetric framing header for Estruturado; the format descriptor is the treatment."""
    clause = FUNCTIONAL_CLAUSE[_mode_key(mode)]
    fmt = serialization.upper()
    return (
        f"Consider the following non-functional requirement, specified as a structured {fmt} "
        f"object grounded in ISO/IEC 25010, and {clause}"
    )


def build_rich_nl_prompts(nfr_key, mode="rq1"):
    """NL-rico: 10 prose strings with the same ISO-grounded content as the structured condition.

    Each string = symmetric header + quality attribute (ISO) + intent + constraints +
    acceptance criteria. Paired 1:1 with the NL-simples variations (only `intent` varies).
    """
    if nfr_key not in ISO25010:
        # 'raw' (and any non-ISO key) has no NFR content; fall back to the baseline.
        return (RQ1 if _mode_key(mode) == "rq1" else RQ2)[nfr_key].split("\n")
    header = _rich_header(mode)
    iso = ISO25010[nfr_key]
    subs = ", ".join(iso["subcharacteristics"])
    constraints = "; ".join(CONSTRAINTS[nfr_key])
    acceptance = "; ".join(ACCEPTANCE[nfr_key])
    out = []
    for intent in _intents(nfr_key, mode):
        block = (
            f"{header}\n"
            f"Quality attribute: {nfr_key} (ISO/IEC 25010 {iso['characteristic']} - {subs}).\n"
            f"Intent: {intent}.\n"
            f"Constraints: {constraints}.\n"
            f"Acceptance criteria: {acceptance}."
        )
        out.append(block)
    return out


def build_structured_prompts(nfr_key, mode="rq1", serialization="json"):
    """Estruturado: 10 strings with the SAME content as NL-rico, serialized as JSON/YAML.

    The only difference from build_rich_nl_prompts is the *form* (prose vs serialized object),
    which is exactly the variable under test.
    """
    if nfr_key not in ISO25010:
        return (RQ1 if _mode_key(mode) == "rq1" else RQ2)[nfr_key].split("\n")
    serialization = serialization.lower()
    if serialization not in ("json", "yaml"):
        raise ValueError(f"Unknown serialization {serialization!r}. Use 'json' or 'yaml'.")
    header = _structured_header(mode, serialization)
    out = []
    for intent in _intents(nfr_key, mode):
        spec = {
            "non_functional_requirement": {
                "attribute": nfr_key,
                "iso_iec_25010": ISO25010[nfr_key],
                "intent": intent,
                "constraints": CONSTRAINTS[nfr_key],
                "acceptance_criteria": ACCEPTANCE[nfr_key],
            }
        }
        if serialization == "json":
            body = json.dumps(spec, indent=2)
        else:
            import yaml  # lazy import: only needed for the YAML branch
            body = yaml.safe_dump(spec, sort_keys=False)
        out.append(f"{header}\n{body}")
    return out


def get_prompts(nfr_key, mode="rq1", prompt_format="natural", serialization="json"):
    """Single entry point: return the list of 10 prompt strings for any condition.

    Args:
        nfr_key: one of RQ1 keys (raw, performance, codesmell, readability, errorhandle).
        mode: 'rq1' or 'rq2'.
        prompt_format: 'natural' | 'rich_natural' | 'structured'.
        serialization: 'json' | 'yaml' (only used by 'structured').
    """
    validate_nfr_key(nfr_key, _mode_key(mode))
    if prompt_format == "natural":
        return (RQ1 if _mode_key(mode) == "rq1" else RQ2)[nfr_key].split("\n")
    if prompt_format == "rich_natural":
        return build_rich_nl_prompts(nfr_key, mode)
    if prompt_format == "structured":
        return build_structured_prompts(nfr_key, mode, serialization)
    raise ValueError(
        f"Unknown prompt_format {prompt_format!r}. Choose one of: {PROMPT_FORMATS}"
    )
