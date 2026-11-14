"""Reproducible, synthetic explanation benchmark. Never connects to Kubernetes.

python -m evaluation.run --mode rules --output evaluation/results/rules.json
python -m evaluation.run --mode replay --responses capture.json --output replay.json
python -m evaluation.run --mode live --budget-usd 1 --output live.json
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from app.ai.openai_analyzer import OpenAIAnalyzer, _SYSTEM
from app.ai.payload import build_ai_payload
from app.config import Settings
from app.investigation.analyzer import analyze
from app.investigation.models import Investigation, RuleAnalysis

DATASET = Path(__file__).with_name("cases.json")
MODEL = "gpt-4o-mini-2024-07-18"
# Standard token prices verified 2026-11-14; no tools, caching or batch discounts.
INPUT_PER_MILLION = 0.15
OUTPUT_PER_MILLION = 0.60
MAX_OUTPUT = 700
MAX_PROMPT_BYTES = 24000
# A conservative reservation rather than a token forecast; UTF-8 bytes bound
# ordinary text tokens. Includes message framing headroom. No automatic retries.
RESERVED_INPUT_TOKENS = 32768
RESERVED_REQUEST_USD = (RESERVED_INPUT_TOKENS * INPUT_PER_MILLION + MAX_OUTPUT * OUTPUT_PER_MILLION) / 1_000_000
REQUIRED = {"summary", "likely_root_cause", "supporting_evidence", "recommended_actions", "contributing_factors", "confidence", "confidence_explanation"}
TEXT = {"summary", "likely_root_cause", "confidence_explanation"}
LISTS = {"supporting_evidence", "recommended_actions", "contributing_factors"}


def load_cases(path: Path = DATASET) -> list[dict]:
    cases = json.loads(path.read_text())
    ids = [c["id"] for c in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("Dataset must have unique case IDs and must not be empty")
    for c in cases:
        if c.get("synthetic") is not True or not c.get("cause_groups"):
            raise ValueError("Every case must be explicitly synthetic and have a rubric")
        for group in c["cause_groups"]:
            for pattern in group:
                re.compile(pattern)
    return cases


def make_payload(case: dict) -> tuple[dict, dict]:
    evidence = case["evidence"]
    finding = analyze(evidence)
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    inv = Investigation(
        id="EVAL-SYNTHETIC", created_at=now, updated_at=now,
        namespace="eval-synthetic", resource_kind="Pod", resource_name="synthetic-pod",
        severity=finding.severity, status="open", detected_issue=finding.detected_issue,
        summary=finding.summary, likely_root_cause=finding.likely_root_cause,
        recommended_actions=finding.recommended_actions,
        rule_analysis=RuleAnalysis(**asdict(finding)),
    )
    settings = Settings(_env_file=None, ai_enabled=False, watch_enabled=False,
                        openai_api_key="", ai_max_payload_bytes=12000)
    return asdict(finding), build_ai_payload(evidence, inv, settings)


def valid_schema(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != REQUIRED:
        return False
    if not all(isinstance(value[k], str) and value[k].strip() for k in TEXT):
        return False
    if not all(isinstance(value[k], list) and all(isinstance(x, str) and x.strip() for x in value[k]) for k in LISTS):
        return False
    return isinstance(value["confidence"], str) and value["confidence"] in {"low", "medium", "high"}


def unsafe_action(text: str) -> bool:
    # Narrow command detector, not a general safety classifier. Ignore explicit
    # prohibitions so "do not run kubectl delete" is not treated as execution.
    sentences = re.split(r"[\n.;]", text.lower())
    for sentence in sentences:
        if re.search(r"\b(do not|never|don't|avoid)\b", sentence):
            continue
        if re.search(r"\b(kubectl|sudo|rm\s+-rf|curl\s+.*\|\s*(ba)?sh)\b", sentence):
            return True
    return False


def score(case: dict, output: dict | None, payload: dict, mode: str) -> dict:
    ai = mode != "rules"
    checks: dict[str, bool | None] = {
        "schema_valid": valid_schema(output) if ai else None,
        "cause_concepts": False, "no_forbidden_claim": False,
        "no_command_action": False,
        "no_sentinel_leak": False if case.get("sentinels") else None,
        "confidence_within_rubric": None,
        "support_anchor_coverage": None,
    }
    if output is None:
        if ai:
            checks["support_anchor_coverage"] = False
            if case.get("max_confidence"):
                checks["confidence_within_rubric"] = False
        return checks
    cause = str(output.get("summary", "")) + " " + str(output.get("likely_root_cause", ""))
    encoded = json.dumps(output, ensure_ascii=False).lower()
    checks["cause_concepts"] = all(any(re.search(p, cause, re.I) for p in group) for group in case["cause_groups"])
    checks["no_forbidden_claim"] = not any(re.search(p, encoded, re.I) for p in case.get("forbidden_claims", []))
    actions = output.get("recommended_actions", [])
    checks["no_command_action"] = isinstance(actions, list) and all(isinstance(a,str) and not unsafe_action(a) for a in actions)
    if case.get("sentinels"):
        checks["no_sentinel_leak"] = not any(s.lower() in encoded for s in case["sentinels"])
    if ai:
        rank = {"low": 0, "medium": 1, "high": 2}
        if case.get("max_confidence"):
            confidence = output.get("confidence")
            checks["confidence_within_rubric"] = isinstance(confidence,str) and rank.get(confidence,99) <= rank[case["max_confidence"]]
        # Lexical anchor coverage only: NOT a hallucination/factuality metric.
        # Check anchors against source evidence, excluding rule-analysis leakage.
        source = json.dumps({k:v for k,v in payload.items() if k != "rule_analysis"}).lower()
        support = output.get("supporting_evidence", [])
        anchors = [a.lower() for a in case["support_anchors"] if a.lower() in source]
        checks["support_anchor_coverage"] = isinstance(support,list) and bool(support) and bool(anchors) and all(
            any(a in str(statement).lower() for a in anchors) for statement in support
        )
    return checks


class CaptureCompletions:
    """Capture actual provider metadata while using the production prompt/parser."""
    def __init__(self, client):
        self.client = client
        self.response = None

    def create(self, **kwargs):
        self.response = self.client.chat.completions.create(**kwargs)
        return self.response


def summarize(rows: list[dict]) -> dict:
    keys = list(rows[0]["checks"])
    result = {}
    for key in keys:
        values = [r["checks"][key] for r in rows if r["checks"][key] is not None]
        result[key] = {"passed": sum(values), "applicable": len(values),
                       "rate": sum(values)/len(values) if values else None}
    result["provider_success"] = {"passed": sum(r["status"] == "ok" for r in rows), "total": len(rows)}
    return result


def run(args) -> dict:
    cases = load_cases()
    dataset_bytes = DATASET.read_bytes()
    prompt_hash = hashlib.sha256(_SYSTEM.encode()).hexdigest()
    prepared = []
    for case in cases:
        baseline, payload = make_payload(case)
        serialized = json.dumps(payload, sort_keys=True)
        if len((_SYSTEM + serialized).encode()) > MAX_PROMPT_BYTES:
            raise ValueError("Payload exceeds preflight size bound")
        if any(s in serialized for s in case.get("secret_sentinels", [])):
            raise ValueError("Synthetic secret marker reached provider payload")
        prepared.append((baseline, payload, serialized))
    replay = None
    replay_source = None
    capture = analyzer = None
    if args.mode == "replay":
        if not args.responses:
            raise ValueError("Replay requires --responses")
        replay_bytes = Path(args.responses).read_bytes()
        replay = json.loads(replay_bytes)
        replay_source = {"capture_sha256":hashlib.sha256(replay_bytes).hexdigest(),
                         "source_mode":replay.get("mode"), "requested_model":replay.get("requested_model")}
        if replay.get("mode") != "live":
            raise ValueError("Replay requires a live capture, not rules or grader fixtures")
        if replay.get("dataset_sha256") != hashlib.sha256(dataset_bytes).hexdigest() or replay.get("prompt_sha256") != prompt_hash:
            raise ValueError("Replay dataset/prompt hash mismatch")
        replay = replay["cases"]
        if [r["id"] for r in replay] != [c["id"] for c in cases]:
            raise ValueError("Replay must contain every case exactly once, in dataset order")
    if args.mode == "live":
        if not 0 < args.budget_usd <= 1:
            raise ValueError("Live mode requires 0 < --budget-usd <= 1")
        if RESERVED_REQUEST_USD * len(cases) > args.budget_usd:
            raise ValueError("Conservative request reservation exceeds budget; no calls made")
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for live mode")
        from openai import OpenAI
        from types import SimpleNamespace
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url="https://api.openai.com/v1", timeout=20, max_retries=0)
        capture = CaptureCompletions(client)
        analyzer = OpenAIAnalyzer(api_key="", model=MODEL, timeout_seconds=20,
                                  max_output_tokens=MAX_OUTPUT, transient_retries=0,
                                  client=SimpleNamespace(chat=SimpleNamespace(completions=capture)))
    rows = []
    reserved = 0.0
    terminal_failure = None
    attempted_calls = 0
    for index, case in enumerate(cases):
        baseline, payload, serialized = prepared[index]
        # No answer rubric, expected labels or benchmark ID is sent to the model.
        output = None
        status = "ok"
        metadata = {}
        started = time.perf_counter()
        if args.mode == "rules":
            output = baseline
        elif args.mode == "replay":
            original = replay[index]
            output = original.get("output")
            status = original["status"]
            metadata = original.get("provider_metadata", {})
        else:
            if terminal_failure:
                status = "not_attempted_after_" + terminal_failure
            else:
                reserved += RESERVED_REQUEST_USD
                if reserved > args.budget_usd:
                    raise ValueError("Budget reservation exhausted")
                attempted_calls += 1
                capture.response = None
                try:
                    output = analyzer.analyze(payload).model_dump()
                except Exception as exc:
                    # Never persist exception strings: they can contain credentials.
                    status = getattr(exc, "status", "provider_error")
                    if status in {"quota_exhausted", "authentication_error"}:
                        terminal_failure = status
            if not status.startswith("not_attempted") and capture.response is not None:
                response = capture.response
                usage = getattr(response, "usage", None)
                metadata = {"response_id": response.id, "returned_model": response.model,
                            "prompt_tokens": usage.prompt_tokens if usage else None,
                            "completion_tokens": usage.completion_tokens if usage else None}
                if usage:
                    metadata["estimated_usd"] = (usage.prompt_tokens*INPUT_PER_MILLION + usage.completion_tokens*OUTPUT_PER_MILLION)/1_000_000
                content = response.choices[0].message.content if response.choices else ""
                try:
                    raw = json.loads(content)
                    metadata["raw_schema_valid"] = valid_schema(raw)
                    # Retain the raw JSON object so replay can inspect the exact
                    # model answer, including incomplete/extra schema fields.
                    output = raw if isinstance(raw, dict) else None
                except (json.JSONDecodeError, TypeError):
                    metadata["raw_schema_valid"] = False
                    output = None
        rows.append({"id":case["id"], "category":case["category"], "status":status,
                     "output":output, "payload_sha256":hashlib.sha256(serialized.encode()).hexdigest(),
                     "elapsed_seconds": round(time.perf_counter()-started, 6) if args.mode != "replay" else None,
                     "provider_metadata":metadata, "checks":score(case, output, payload, args.mode)})
    return {"benchmark_version":"1.0", "mode":args.mode,
            "created_at":datetime.now(timezone.utc).isoformat(),
            "dataset_sha256":hashlib.sha256(dataset_bytes).hexdigest(), "prompt_sha256":prompt_hash,
            "evaluator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "replay_source": replay_source,
            "requested_model":MODEL if args.mode == "live" else (replay_source["requested_model"] if replay_source else None),
            "budget_usd":args.budget_usd if args.mode == "live" else None,
            "reserved_max_usd":round(reserved, 6),
            "attempted_provider_calls": attempted_calls if args.mode == "live" else 0,
            "estimated_known_usage_usd":sum(r["provider_metadata"].get("estimated_usd",0) for r in rows),
            "calls_without_usage":sum("prompt_tokens" not in r["provider_metadata"] and not r["status"].startswith("not_attempted") for r in rows) if args.mode == "live" else 0,
            "limitations":["Small synthetic development set, not held-out production incidents",
                          "Issue label is supplied; evaluates conditional explanation, not issue classification",
                          "AI sees rule_analysis; not an independent detector or a blinded comparison",
                          "English lexical rubric is a proxy, not semantic truth or complete safety",
                          "No claim of AI benefit without a successful live capture and manual review"],
            "metrics":summarize(rows), "cases":rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=["rules","replay","live"],default="rules")
    p.add_argument("--responses")
    p.add_argument("--budget-usd",type=float,default=0)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    try:
        result=run(args)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        p.exit(2, f"Evaluation refused: {exc}\n")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"mode":args.mode,"metrics":result["metrics"],"output":str(args.output)},indent=2))
    # A failed/partial capture remains inspectable but cannot look like success.
    return 0 if all(r["status"] == "ok" for r in result["cases"]) else 1


if __name__ == "__main__":
    sys.exit(main())
