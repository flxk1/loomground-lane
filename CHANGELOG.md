<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Changelog

## 0.1.0

* Published `governance_lane.py` as `loomground_lane.governance_lane`; its capability projection algebra lives in `loomground_lane.lane_capabilities`, with compiled graph, enforcement evaluator, auto-grade threshold, and lane lookup injected as ports. The public host seam is in `docs/seam.md`.
* Decoupled from the host: `ActionRequest` is replaced by the structural `LaneRequest` protocol (the five attributes `evaluate_lane` reads); the grade lattice, the risk levels, the verdict alphabet and the language version are read from `loomground_governance.vocabulary(...)` / `language_version()` and declared nowhere in `src/`.
* Lane versions are appended to the signed chain through `loomground_audit_chain.mutation_log.{MutationLog, LogEvent}`; event kinds `governance-lane-approved` and the legacy `autonomy-lane-approved` are preserved.
* `preview_patch` gains the keyword-only `grade_required`; `lane_capabilities` gains the keyword-only ports `graph`, `evaluator`, `auto_grade_min`, `lane_lookup`.
* Licence: Apache-2.0 (code) and CC-BY-4.0 (README), relicensed by the sole rights holder, flxk1.
