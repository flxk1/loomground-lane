# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The preserved public surface, the decoupled request, the grounding."""
from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import loomground_audit_chain.mutation_log as chain
from loomground_governance import vocabulary

import loomground_lane
from loomground_lane import _vocabulary as V

SRC = Path(loomground_lane.__file__).parent

SURFACE = {
    "governance_lane": ["GovernanceLane", "LaneDecision", "evaluate_lane",
                        "get_lane", "list_lanes", "register_lane"],
    "lane_capabilities": ["SCHEMA_KIND", "lane_capabilities", "preview_patch"],
}


def _params(fn):
    return {name: p.kind for name, p in inspect.signature(fn).parameters.items()}


def test_every_surface_name_is_importable_from_both_levels():
    for module, names in SURFACE.items():
        mod = importlib.import_module(f"loomground_lane.{module}")
        for name in names:
            assert getattr(mod, name) is getattr(loomground_lane, name)
            assert name in loomground_lane.__all__
    assert loomground_lane.SCHEMA_KIND == "lane_capabilities/v1"
    assert loomground_lane.EVENT_KIND == "governance-lane-approved"
    assert loomground_lane.LEGACY_EVENT_KIND == "autonomy-lane-approved"


def test_signatures_stay_host_compatible():
    KW, POS = inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert _params(loomground_lane.evaluate_lane) == {
        "lane": POS, "req": POS, "use_case_id": KW, "connector_id": KW,
        "policy_fingerprint": KW}
    assert _params(loomground_lane.register_lane) == {"folder": POS, "lane": POS,
                                                      "log_root": KW}
    assert _params(loomground_lane.get_lane) == {"folder": POS, "agent": POS,
                                                 "log_root": KW}
    assert _params(loomground_lane.list_lanes) == {"folder": POS, "log_root": KW}
    caps = _params(loomground_lane.lane_capabilities)
    assert [k for k, kind in caps.items() if kind == POS] == ["folder_context", "actor"]
    assert {"kinds", "risks", "log_root", "graph", "evaluator", "auto_grade_min",
            "lane_lookup"} <= {k for k, kind in caps.items() if kind == KW}
    prev = _params(loomground_lane.preview_patch)
    assert [k for k, kind in prev.items() if kind == POS] == ["graph", "actor", "kind"]
    assert prev["grade_required"] == KW
    assert inspect.signature(loomground_lane.lane_capabilities).parameters[
        "lane_lookup"].default is loomground_lane.get_lane


def test_lattice_and_alphabets_come_from_the_vocabulary():
    assert list(V.grade_levels()) == vocabulary("grades")["levels"]
    assert list(V.risk_levels()) == vocabulary("risk")["levels"]
    assert list(V.verdicts()) == vocabulary("verdicts")["restrictiveness_order"]
    steps = V.verdict_steps()
    assert set(steps.values()) == set(vocabulary("verdicts")["alphabet"])
    priority = vocabulary("verdicts")["assignment_priority"]
    assert [steps["severed"], steps["denied"], steps["escalated"]] == priority[:3]
    assert vocabulary("verdicts")["releases_at_master"][steps["releasing"]] is True
    assert V.language_version()


def test_no_local_alphabet_in_src():
    grade = re.compile(r"""["']L\d["']""")
    verdict = re.compile(r"""["'](%s)["']""" % "|".join(
        re.escape(v) for v in vocabulary("verdicts")["alphabet"]))
    for path in SRC.glob("*.py"):
        text = path.read_text()
        assert not grade.search(text), path.name
        assert not verdict.search(text), path.name


def test_chain_writes_go_through_the_audit_chain():
    import loomground_lane.governance_lane as gl
    assert gl.MutationLog is chain.MutationLog and gl.LogEvent is chain.LogEvent
    text = (SRC / "governance_lane.py").read_text()
    assert "open(" not in text and "jsonl" not in text
