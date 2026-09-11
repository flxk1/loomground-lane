# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Lane boundaries, the structural request, durable versions on the chain."""
from __future__ import annotations

from dataclasses import dataclass

import pytest
from loomground_audit_chain.mutation_log import LogEvent, MutationLog
from loomground_governance import vocabulary

from loomground_lane import (
    EVENT_KIND, LEGACY_EVENT_KIND, GovernanceLane, LaneRequest, evaluate_lane,
    get_lane, list_lanes, register_lane,
)

GRADES = list(vocabulary("grades")["levels"])
FLOOR, TOP = GRADES[0], GRADES[-1]


@dataclass(frozen=True)
class Request:
    """A plain request; it satisfies ``LaneRequest`` by shape alone."""
    agent: str = "bot"
    action_class: str = "summarise"
    autonomy_grade: str = GRADES[3]
    footprint: tuple[str, ...] = ("personal-data",)
    folder: str = "/workspace"


def _lane(**changes):
    values = {
        "lane_id": "lane-research", "agent": "bot", "max_grade": GRADES[3],
        "action_classes": ("summarise",), "footprints": ("personal-data",),
        "folder": "/workspace", "use_cases": ("research",),
        "connectors": ("local-model",), "policy_fingerprint": "sha256:policy",
        "approved_by": "alice", "rationale": "bounded research assistant",
    }
    values.update(changes)
    return GovernanceLane(**values)


_CONTEXT = {"use_case_id": "research", "connector_id": "local-model",
            "policy_fingerprint": "sha256:policy"}


def test_plain_dataclass_satisfies_the_request_protocol():
    assert isinstance(Request(), LaneRequest)
    result = evaluate_lane(_lane(), Request(), **_CONTEXT)
    assert result.allowed and result.violations == ()
    assert result.to_dict() == {"lane_id": "lane-research", "allowed": True,
                                "violations": []}


@pytest.mark.parametrize("request_changes,context,fragment", [
    ({"action_class": "publish"}, {}, "action_class"),
    ({"autonomy_grade": GRADES[4]}, {}, "exceeds"),
    ({"footprint": ("personal-data", "external-publish")}, {}, "footprints"),
    ({"folder": "/other"}, {}, "folder"),
    ({"agent": "impostor"}, {}, "agent"),
    ({}, {"use_case_id": "sales"}, "use_case"),
    ({}, {"connector_id": "cloud-model"}, "connector"),
    ({}, {"policy_fingerprint": "sha256:changed"}, "fingerprint"),
])
def test_every_lane_dimension_fails_closed(request_changes, context, fragment):
    result = evaluate_lane(_lane(), Request(**request_changes),
                           **{**_CONTEXT, **context})
    assert not result.allowed
    assert any(fragment in violation for violation in result.violations)


@pytest.mark.parametrize("grade", GRADES)
def test_every_grade_without_lane_is_refused(grade):
    result = evaluate_lane(None, Request(autonomy_grade=grade))
    assert not result.allowed
    assert result.violations == ("no approved governance lane",)


@pytest.mark.parametrize("assigned,requested", list(zip(GRADES, GRADES[1:])))
def test_agent_cannot_request_a_grade_above_its_lane(assigned, requested):
    result = evaluate_lane(_lane(max_grade=assigned),
                           Request(autonomy_grade=requested), **_CONTEXT)
    assert not result.allowed
    assert f"grade {requested} exceeds {assigned}" in result.violations


def test_floor_action_remains_inside_a_floor_lane():
    result = evaluate_lane(_lane(max_grade=FLOOR), Request(autonomy_grade=FLOOR),
                           **_CONTEXT)
    assert result.allowed


def test_unknown_grade_ranks_at_the_floor():
    result = evaluate_lane(_lane(max_grade=FLOOR), Request(autonomy_grade="L99"),
                           **_CONTEXT)
    assert result.allowed


def test_lane_validation_uses_the_vocabulary_lattice():
    with pytest.raises(ValueError, match=", ".join(GRADES)):
        _lane(max_grade="L99")
    with pytest.raises(ValueError, match="action_class"):
        _lane(action_classes=())
    with pytest.raises(ValueError, match="approver"):
        _lane(approved_by=" ")
    with pytest.raises(ValueError, match="version"):
        _lane(version=0)
    assert GovernanceLane.from_dict(_lane().to_dict()) == _lane()


def test_lane_versions_are_signed_and_latest_wins(tmp_path):
    folder, log = tmp_path / "workspace", tmp_path / "log"
    first = _lane(folder=str(folder), version=1)
    second = _lane(folder=str(folder), version=2,
                   action_classes=("summarise", "classify"))
    out = register_lane(folder, first, log_root=log)
    assert out["ok"] and out["audit_id"] and out["lane"] == first.to_dict()
    register_lane(folder, second, log_root=log)
    assert get_lane(folder, "bot", log_root=log).version == 2
    assert len(list_lanes(folder, log_root=log)) == 1
    with pytest.raises(ValueError, match="increase the version"):
        register_lane(folder, first, log_root=log)
    with pytest.raises(ValueError, match="registry folder"):
        register_lane(tmp_path / "elsewhere", _lane(folder=str(folder)),
                      log_root=log)


def test_lane_events_ride_the_signed_chain(tmp_path):
    folder, log = tmp_path / "workspace", tmp_path / "log"
    register_lane(folder, _lane(folder=str(folder)), log_root=log)
    chain = MutationLog(folder, log_root=log)
    events = [e for e in chain.replay() if e.extra.get("kind") == EVENT_KIND]
    assert len(events) == 1
    assert events[0].actor == "alice" and events[0].pair_id == "lane:lane-research"
    assert events[0].signature and events[0].prev_hash
    assert chain.verify_chain().ok


def test_legacy_event_kind_still_reads(tmp_path):
    folder, log = tmp_path / "workspace", tmp_path / "log"
    lane = _lane(folder=str(folder))
    MutationLog(folder, log_root=log).append(LogEvent(
        event="system", folder_path=str(folder), pair_id="lane:legacy",
        actor="alice", extra={"kind": LEGACY_EVENT_KIND, "lane": lane.to_dict()}))
    assert get_lane(folder, "bot", log_root=log) == lane
    assert get_lane(folder, "stranger", log_root=log) is None


def test_chokepoint_violation_names_both_grades(tmp_path):
    folder, log = tmp_path / "workspace", tmp_path / "log"
    register_lane(folder, GovernanceLane(
        lane_id="lane-floor", agent="bot", max_grade=FLOOR,
        action_classes=("summarise",), folder=str(folder),
        approved_by="alice", rationale="interactive summarisation only",
    ), log_root=log)
    lane = get_lane(folder, "bot", log_root=log)
    escaped = evaluate_lane(lane, Request(autonomy_grade=GRADES[1], footprint=(),
                                          folder=str(folder)))
    contained = evaluate_lane(lane, Request(autonomy_grade=FLOOR, footprint=(),
                                            folder=str(folder)))
    assert escaped.allowed is False
    assert any(f"{GRADES[1]} exceeds {FLOOR}" in v for v in escaped.violations)
    assert contained.allowed is True
