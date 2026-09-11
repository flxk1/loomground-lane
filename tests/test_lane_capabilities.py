# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""lane_capabilities: schema, lane scoping, fail-closed reads, provenance
stamping, the injected ports — and THE fence: preview == enforcement."""
from __future__ import annotations

import pytest

from _evaluator import GRADES, RISKS, VERDICTS, ReferenceEvaluator, grade_meets
from loomground_lane import (
    SCHEMA_KIND, GovernanceLane, lane_capabilities, preview_patch, register_lane,
)

GHOST = "ghost_kind"
AUTO_GRADE_MIN = 3          # the host's threshold, a rank into the lattice
HARDENED, UNHARDENED = AUTO_GRADE_MIN, 0
EVAL = ReferenceEvaluator()


def _uc(kind, *, agents, grade, reservations=None, prohibited=False, tags=()):
    node = {"id": f"uc:{kind}", "kind": "use_case", "risk": RISKS[0],
            "grade": grade, "prohibited": prohibited, "tags": list(tags),
            "reservations": [dict(r) for r in (reservations or [])]}
    edges = [{"from": f"agent:{a}", "to": f"uc:{kind}", "kind": "authority"}
             for a in agents]
    return node, edges


@pytest.fixture()
def governed(tmp_path):
    """Two lanes and a compiled graph exercising every verdict symbol."""
    folder, log = str(tmp_path / "workspace"), str(tmp_path / "log")
    register_lane(folder, GovernanceLane(
        lane_id="lane-bot", agent="bot", max_grade=GRADES[2],
        action_classes=("classify", "pii_export", "publish_note",
                        "forbidden", "novice", GHOST),
        folder=folder, policy_fingerprint="sha256:approved",
        approved_by="controller", rationale="bounded worker"), log_root=log)
    register_lane(folder, GovernanceLane(
        lane_id="lane-rival", agent="rival", max_grade=GRADES[4],
        action_classes=("other_uc",),
        folder=folder, policy_fingerprint="sha256:rival",
        approved_by="controller", rationale="second lane"), log_root=log)
    specs = [
        _uc("classify", agents=["bot"], grade=HARDENED),
        _uc("pii_export", agents=["bot"], grade=HARDENED, reservations=[
            {"reserved_to": "privacy-officer", "when": f"risk >= {RISKS[2]}"}]),
        _uc("publish_note", agents=["bot"], grade=HARDENED,
            reservations=[{"reserved_to": "editor"}]),
        _uc("forbidden", agents=["bot"], grade=HARDENED, prohibited=True),
        _uc("novice", agents=["bot"], grade=UNHARDENED),
        _uc("other_uc", agents=["rival"], grade=HARDENED),
    ]
    graph = {"nodes": [n for n, _ in specs],
             "edges": [e for _, es in specs for e in es]}
    return folder, log, graph


def _caps(folder, log, graph, actor, **kw):
    return lane_capabilities(folder, actor, graph=graph, evaluator=EVAL,
                             auto_grade_min=AUTO_GRADE_MIN, log_root=log, **kw)


def _flat_or_cell(entry, risk):
    if "by_risk" in entry:
        return entry["by_risk"][risk]
    return {k: entry[k] for k in ("verdict", "grade_required", "escalation", "guard")}


def _by_kind(out):
    return {e["kind"]: e for e in out["capabilities"]}


def test_schema_shape_and_provenance_stamp(governed):
    folder, log, graph = governed
    out = _caps(folder, log, graph, "bot")
    assert out["ok"] is True and out["kind"] == SCHEMA_KIND
    assert out["advisory"] is True and out["readable"] is True
    assert out["actor"] == "bot"
    assert out["risk_axis"] == list(RISKS)
    prov = out["provenance"]
    assert prov["policy_fingerprint"] == "sha256:approved"
    assert prov["lane_id"] == "lane-bot" and prov["lane_version"] == 1
    assert prov["max_grade"] == GRADES[2] and prov["language_version"]
    assert prov["derived_at"] > 0 and "projection" in prov["source"]
    assert set(_by_kind(out)) == {"classify", "pii_export", "publish_note",
                                  "forbidden", "novice", GHOST, "other_uc"}
    for entry in out["capabilities"]:
        for r in out["risk_axis"]:
            cell = _flat_or_cell(entry, r)
            assert cell["verdict"] in VERDICTS
            assert set(cell) == {"verdict", "grade_required", "escalation", "guard"}


def test_projected_dispositions_and_attribution(governed):
    folder, log, graph = governed
    caps = _by_kind(_caps(folder, log, graph, "bot"))
    assert "by_risk" not in caps["classify"]
    assert caps["classify"]["verdict"] == "auto"
    assert caps["classify"]["grade_required"] == GRADES[AUTO_GRADE_MIN]
    assert caps["classify"]["escalation"] is None
    pii = caps["pii_export"]["by_risk"]
    assert pii[RISKS[0]]["verdict"] == "auto" and pii[RISKS[1]]["verdict"] == "auto"
    for tier in RISKS[2:]:
        assert pii[tier]["verdict"] == "reserved"
        assert pii[tier]["escalation"] == "privacy-officer"
        assert pii[tier]["guard"] == (
            f"reserve pii_export by privacy-officer when risk >= {RISKS[2]}")
    assert caps["publish_note"]["verdict"] == "reserved"
    assert caps["publish_note"]["escalation"] == "editor"
    assert caps["publish_note"]["guard"] == "reserve publish_note by editor"
    assert caps["forbidden"]["verdict"] == "prohibited"
    assert caps["forbidden"]["escalation"] == "severed"
    assert caps["forbidden"]["guard"] == "prohibit forbidden"
    assert caps["novice"]["verdict"] == "human"
    assert caps["novice"]["escalation"] == "human-in-the-loop"
    assert caps["novice"]["grade_required"] == GRADES[AUTO_GRADE_MIN]
    assert caps["other_uc"]["verdict"] == "refused"
    assert caps["other_uc"]["in_lane"] is False
    assert "default-deny" in caps["other_uc"]["guard"]
    assert caps[GHOST]["verdict"] == "refused"
    assert caps[GHOST]["in_lane"] is True and caps[GHOST]["wired"] is False


def test_lane_scoping_per_actor(governed):
    folder, log, graph = governed
    bot = _by_kind(_caps(folder, log, graph, "bot"))
    rival_out = _caps(folder, log, graph, "rival")
    rival = _by_kind(rival_out)
    assert rival_out["provenance"]["policy_fingerprint"] == "sha256:rival"
    assert rival_out["provenance"]["lane_id"] == "lane-rival"
    assert rival["other_uc"]["verdict"] == "auto"
    assert rival["other_uc"]["in_lane"] is True
    assert bot["other_uc"]["verdict"] == "refused"
    assert rival["classify"]["in_lane"] is False
    assert rival["classify"]["verdict"] == "refused"


def test_fail_closed_never_all_allowed(governed):
    folder, log, graph = governed
    out = _caps(folder, log, graph, "stranger")
    assert out["ok"] is False and out["capabilities"] == []
    assert out["reason"] == "no active governance lane"

    def _boom(*a, **k):
        raise OSError("chain unreadable")
    out = _caps(folder, log, graph, "bot", lane_lookup=_boom)
    assert out["ok"] is False and out["readable"] is False
    assert out["capabilities"] == []
    assert "policy unreadable" in out["reason"] and "OSError" in out["reason"]
    out = _caps(folder, log, _boom, "bot")
    assert out["ok"] is False and out["readable"] is False


def test_graph_port_accepts_a_compiler(governed):
    folder, log, graph = governed
    seen = {}

    def compile_graph(folder_arg, *, log_root):
        seen.update(folder=folder_arg, log_root=log_root)
        return graph
    out = _caps(folder, log, compile_graph, "bot")
    assert out["ok"] is True and seen == {"folder": folder, "log_root": log}
    assert out["capabilities"] == _caps(folder, log, graph, "bot")["capabilities"]


def test_risk_axis_is_vocabulary_gated(governed):
    folder, log, graph = governed
    out = _caps(folder, log, graph, "bot", risks=[RISKS[2]])
    assert out["risk_axis"] == [RISKS[2]]
    out = _caps(folder, log, graph, "bot", risks=["cosmic"])
    assert out["ok"] is False and out["capabilities"] == []


def test_kinds_filter_and_unknown_verdict_clamps(governed):
    folder, log, graph = governed
    out = _caps(folder, log, graph, "bot", kinds=["classify", "classify", "novel"])
    assert [e["kind"] for e in out["capabilities"]] == ["classify", "novel"]
    assert _by_kind(out)["novel"]["verdict"] == "refused"

    class Odd(ReferenceEvaluator):
        @staticmethod
        def evaluate_log(patch, transport):
            return [{"gate": "classify", "verdict": "cosmic"}]
    out = lane_capabilities(folder, "bot", graph=graph, evaluator=Odd(),
                            auto_grade_min=AUTO_GRADE_MIN, log_root=log,
                            kinds=["classify"])
    assert _by_kind(out)["classify"]["verdict"] == VERDICTS[-1]


def test_auto_threshold_accepts_rank_or_level(governed):
    folder, log, graph = governed
    by_rank = _caps(folder, log, graph, "bot")["capabilities"]
    by_level = lane_capabilities(
        folder, "bot", graph=graph, evaluator=EVAL,
        auto_grade_min=GRADES[AUTO_GRADE_MIN], log_root=log)["capabilities"]
    assert by_rank == by_level
    with pytest.raises(ValueError, match="lattice"):
        lane_capabilities(folder, "bot", graph=graph, evaluator=EVAL,
                          auto_grade_min="L99", log_root=log)


def test_projection_appends_nothing(governed):
    folder, log, graph = governed
    from loomground_audit_chain.mutation_log import MutationLog
    before = MutationLog(folder, log_root=log).count()
    _caps(folder, log, graph, "bot")
    assert MutationLog(folder, log_root=log).count() == before


def _fence(folder, log, graph, evaluator):
    checked, seen = 0, set()
    gates = {n["id"].split(":", 1)[1]: n for n in graph["nodes"]
             if n["kind"] == "use_case"}
    for actor in ("bot", "rival"):
        out = lane_capabilities(folder, actor, graph=graph, evaluator=evaluator,
                                auto_grade_min=AUTO_GRADE_MIN, log_root=log)
        for entry in out["capabilities"]:
            kind = entry["kind"]
            if kind not in gates:
                for risk in out["risk_axis"]:
                    assert _flat_or_cell(entry, risk)["verdict"] == "refused"
                    checked += 1
                seen.add("refused")
                continue
            patch = preview_patch(graph, actor, kind, grade_required=AUTO_GRADE_MIN)
            for risk in out["risk_axis"]:
                projected = _flat_or_cell(entry, risk)["verdict"]
                token = {"id": f"t:{kind}:{risk}", "kind": kind, "risk": risk,
                         "party": actor, "provenance": [],
                         "tags": list(gates[kind].get("tags") or [])}
                trace = evaluator.evaluate_log(patch, {"activations": [
                    {"source": kind, "actor": actor, "token": token}]})
                disposed = trace[-1]["verdict"]
                assert projected == disposed, (
                    f"preview/enforcement drift at ({actor}, {kind}, {risk}): "
                    f"projected {projected!r}, gate disposes {disposed!r}")
                seen.add(disposed)
                checked += 1
    assert seen == set(VERDICTS)
    assert checked == (7 + 6) * len(RISKS)


def test_preview_equals_enforcement(governed):
    folder, log, graph = governed
    _fence(folder, log, graph, EVAL)


def test_preview_equals_enforcement_against_the_language_engine(governed):
    """The same fence over the language's own evaluator when it is installed."""
    engine = pytest.importorskip("loomground_solver.loomground")

    class Engine:
        evaluate_log = staticmethod(engine.evaluate_log)
        guard_holds = staticmethod(engine._guard_holds)
    folder, log, graph = governed
    _fence(folder, log, graph, Engine())


def test_preview_auto_split_is_the_grade_rule(governed):
    folder, log, graph = governed
    caps = _by_kind(_caps(folder, log, graph, "bot"))
    gates = {n["id"].split(":", 1)[1]: n for n in graph["nodes"]}
    for kind in ("classify", "novice"):
        expected = ("auto" if grade_meets(gates[kind]["grade"], AUTO_GRADE_MIN)
                    else "human")
        assert caps[kind]["verdict"] == expected


def test_preview_patch_shape(governed):
    folder, log, graph = governed
    assert preview_patch(graph, "bot", GHOST, grade_required=AUTO_GRADE_MIN) is None
    patch = preview_patch(graph, "bot", "pii_export", grade_required=AUTO_GRADE_MIN)
    assert [n["class"] for n in patch["nodes"]] == ["actor", "gate", "master"]
    assert patch["nodes"][0] == {"id": "bot", "class": "actor", "grade": HARDENED}
    assert patch["nodes"][1]["grade_required"] == AUTO_GRADE_MIN
    assert patch["nodes"][1]["risk_floor"] == RISKS[0]
    assert patch["cords"] == [{"from": "bot", "to": "pii_export", "type": "authority"},
                              {"from": "pii_export", "to": "master", "type": "egress"}]
    assert patch["reservations"] == [{"kind": "pii_export", "when": f"risk >= {RISKS[2]}"}]
    assert patch["prohibitions"] == [] and patch["grants"] == [] and patch["obligations"] == []
    rival = preview_patch(graph, "rival", "pii_export", grade_required=AUTO_GRADE_MIN)
    assert rival["cords"] == [{"from": "pii_export", "to": "master", "type": "egress"}]
