# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""loomground-lane — durable approval envelopes for governed agents.

:mod:`.governance_lane` holds the lane, its evaluation and its signed
versions; :mod:`.lane_capabilities` projects one lane over the host's gates
through injected ports.
"""
from __future__ import annotations

from ._version import __version__
from .governance_lane import (
    EVENT_KIND,
    LEGACY_EVENT_KIND,
    GovernanceLane,
    LaneDecision,
    LaneRequest,
    evaluate_lane,
    get_lane,
    list_lanes,
    register_lane,
)
from .lane_capabilities import (
    SCHEMA_KIND,
    LaneEvaluator,
    lane_capabilities,
    preview_patch,
)

__all__ = [
    "__version__",
    "EVENT_KIND", "LEGACY_EVENT_KIND", "GovernanceLane", "LaneDecision",
    "LaneRequest", "evaluate_lane", "get_lane", "list_lanes", "register_lane",
    "SCHEMA_KIND", "LaneEvaluator", "lane_capabilities", "preview_patch",
]
