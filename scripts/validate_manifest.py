"""Validate site/architecture.json before the landing page is deployed.

Checks that ids are unique, every edge and walkthrough step points at real
components, and that every cited source file exists in the audited commit.
Standard library only. Exits non-zero on the first set of problems.

    python3 scripts/validate_manifest.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "site" / "architecture.json"
STATUSES = {"implemented", "partial", "planned"}
AUDITED_COMMIT = "ea6e9ad1903ac9e35247f67df031e126343d3f70"


def file_in_commit(path: str) -> bool | None:
    """True/False if git can answer, None if the audited commit is not available locally."""
    try:
        subprocess.run(["git", "cat-file", "-e", AUDITED_COMMIT], cwd=ROOT, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    result = subprocess.run(["git", "cat-file", "-e", f"{AUDITED_COMMIT}:{path}"], cwd=ROOT, capture_output=True)
    return result.returncode == 0


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []

    ids = [n["id"] for n in m["nodes"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate node ids")
    id_set = set(ids)
    layers = {layer["id"] for layer in m["layers"]}
    status_of = {n["id"]: n["status"] for n in m["nodes"]}

    for n in m["nodes"]:
        if n["layer"] not in layers:
            problems.append(f"{n['id']}: unknown layer {n['layer']}")
        if n["kind"] not in m["kinds"]:
            problems.append(f"{n['id']}: unknown kind {n['kind']}")
        if n["status"] not in STATUSES:
            problems.append(f"{n['id']}: unknown status {n['status']}")
        if n["status"] == "planned" and n["files"]:
            problems.append(f"{n['id']}: planned component cites source files")
        if n["status"] != "planned" and not n["files"]:
            problems.append(f"{n['id']}: {n['status']} component cites no source files")

    for e in m["edges"] + m["agentView"]["edges"]:
        if e["source"] not in id_set or e["target"] not in id_set:
            problems.append(f"edge {e['source']} -> {e['target']}: unknown endpoint")
    for e in m["edges"]:
        if e.get("style") == "planned" and "planned" not in (status_of.get(e["source"]), status_of.get(e["target"])):
            problems.append(f"planned edge {e['source']} -> {e['target']} touches no planned component")

    positions = m["agentView"]["positions"]
    for key in positions:
        if key not in id_set:
            problems.append(f"lenses view: unknown node {key}")
    for e in m["agentView"]["edges"]:
        if e["source"] not in positions or e["target"] not in positions:
            problems.append(f"lenses view edge {e['source']} -> {e['target']} has no position")

    edge_pairs = {(e["source"], e["target"]) for e in m["edges"]}
    for step in m["walkthrough"]["steps"]:
        for node_id in step["nodes"]:
            if node_id not in id_set:
                problems.append(f"walkthrough '{step['title']}': unknown node {node_id}")
        for pair in step["edges"]:
            if tuple(pair) not in edge_pairs:
                problems.append(f"walkthrough '{step['title']}': edge {pair} not in the system map")

    vision = m.get("vision")
    if vision:
        for stage in vision["stages"]:
            if not stage["refs"]:
                problems.append(f"roadmap '{stage['title']}': links no components")
            for ref in stage["refs"]:
                if ref not in id_set:
                    problems.append(f"roadmap '{stage['title']}': unknown component {ref}")

    flow = m.get("flow")
    if flow:
        flow_ids = {n["id"] for n in flow["nodes"]}
        edge_ids = {e["id"] for e in flow["edges"]}
        for n in flow["nodes"]:
            if n["status"] not in STATUSES:
                problems.append(f"flow node {n['id']}: unknown status {n['status']}")
        for e in flow["edges"]:
            if e["source"] not in flow_ids or e["target"] not in flow_ids:
                problems.append(f"flow edge {e['id']}: unknown endpoint")
        for i, step in enumerate(flow["steps"], 1):
            for node_id in step["nodes"]:
                if node_id not in flow_ids:
                    problems.append(f"flow step {i}: unknown node {node_id}")
            for edge_id in step["edges"]:
                if edge_id not in edge_ids:
                    problems.append(f"flow step {i}: unknown edge {edge_id}")
            for key in step.get("state", {}):
                if key not in flow["state_keys"]:
                    problems.append(f"flow step {i}: unknown state key {key}")
        if next((n for n in flow["nodes"] if n["id"] == "orch"), {}).get("status") != "planned":
            problems.append("flow: the LangGraph orchestrator must stay 'planned' until it exists in code")

    checked = 0
    for n in m["nodes"]:
        for path in n["files"]:
            found = file_in_commit(path)
            if found is None:
                print("note: audited commit not available locally; skipped source-file checks", file=sys.stderr)
                break
            checked += 1
            if not found:
                problems.append(f"{n['id']}: {path} not in commit {AUDITED_COMMIT[:7]}")
        else:
            continue
        break

    if problems:
        print("Manifest problems:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    print(f"OK: {len(ids)} components, {len(m['edges'])} edges, {checked} source files verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
