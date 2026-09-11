<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Copyright 2026 flxk1 -->
# loomground-lane

Durable approval envelopes for governed agents: what a grade covers, checked each iteration, appended to the signed audit chain.

## Problem

A grade says how independently an agent acts; nothing says over what. A durable approval envelope of actions, data, connectors, folder and policy, checked each iteration.

## Install

```
pip install loomground-lane
```

## Usage

```python
from loomground_lane import GovernanceLane, evaluate_lane, get_lane, register_lane
lane = GovernanceLane(lane_id="lane-research", agent="bot", max_grade="L2",
                      action_classes=("summarise",), footprints=("personal-data",),
                      folder=folder, approved_by="alice", rationale="bounded research assistant")
register_lane(folder, lane, log_root=log)
evaluate_lane(get_lane(folder, "bot", log_root=log), request)
```

`request`: any object with `agent`, `action_class`, `autonomy_grade`, `footprint`, `folder` — the `LaneRequest` protocol.

## Example

```
in : lane bot/L2/summarise/personal-data; request bot L2 summarise personal-data, then bot L3 publish personal-data+web
out: LaneDecision(lane_id='lane-research', allowed=True, violations=())
     ('grade L3 exceeds L2', "action_class 'publish' is outside the lane", 'footprints outside lane: web')
```

## Interface

- `GovernanceLane(lane_id, agent, max_grade, action_classes, footprints, folder, use_cases, connectors, policy_fingerprint, version, approved_by, rationale)`; `max_grade` is a level of `vocabulary("grades")`
- `evaluate_lane(lane, req, *, use_case_id, connector_id, policy_fingerprint) → LaneDecision(lane_id, allowed, violations)`; fails closed without a lane
- `register_lane(folder, lane, *, log_root)` appends `governance-lane-approved` through `loomground_audit_chain.mutation_log.MutationLog`; `get_lane(folder, agent, *, log_root)` · `list_lanes(folder, *, log_root)` read the latest version per agent (legacy `autonomy-lane-approved` too)
- a registered lane is the vocabulary's `human` verdict made durable; an agent's later `auto` runs are checked against it
- `lane_capabilities(folder_context, actor, *, graph, evaluator, auto_grade_min, kinds, risks, log_root, lane_lookup) → {ok, kind: "lane_capabilities/v1", advisory, readable, provenance, risk_axis, capabilities}`; ports: `graph` (graph dict or `(folder, log_root=) → dict`), `evaluator` (`evaluate_log`, `guard_holds`), `auto_grade_min` (rank or level), `lane_lookup`
- `preview_patch(graph, actor, kind, *, grade_required)` → the one-gate patch behind each cell
- symbols from `loomground_governance.vocabulary`; wiring: [docs/seam.md](docs/seam.md)

## Family

Runtime controls. Consumes the `loomground-governance` vocabulary and `loomground-audit-chain`. Consumed by hosts, e.g. RVND; optional for every consumer.

## Status

0.1.0 · 47 tests · Python >=3.10 · loomground-governance 0.11 · loomground-audit-chain 0.1

## License

Apache-2.0 `LICENSES/Apache-2.0.txt` (code) · CC-BY-4.0 `LICENSES/CC-BY-4.0.txt` (README) · `NOTICE`
