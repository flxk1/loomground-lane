# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""HOME, USERPROFILE, the key dir and every log-root variable the audit chain
honours are redirected to a per-session directory BEFORE the package under
test is first imported, so nothing here touches the real ``~/.workspace``."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_HOME: Path | None = None


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    global _HOME
    factory = getattr(config, "_tmp_path_factory", None)
    home = factory.mktemp("home") if factory is not None else Path(
        tempfile.mkdtemp(prefix="lane-home-"))
    _HOME = Path(home)
    os.environ["HOME"] = str(_HOME)
    os.environ["USERPROFILE"] = str(_HOME)
    os.environ["WORKSPACE_KEY_DIR"] = str(_HOME / ".workspace" / "keys")
    import loomground_audit_chain.audit_drop as audit_drop
    import loomground_audit_chain.mutation_log as mutation_log
    for module in (mutation_log, audit_drop):
        for name in dir(module):
            if name.endswith("LOG_ROOT_ENV"):
                os.environ[getattr(module, name)] = str(_HOME / "log")


@pytest.fixture(autouse=True)
def _isolated_chain_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_KEY_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv("WORKSPACES_ALLOW_UNREGISTERED", "1")
    for var in ("WORKSPACE_KEY_PINNING", "WORKSPACE_STRICT_KEY_PINNING",
                "WORKSPACE_STRICT_HOST_DIVERGENCE", "WORKSPACE_KEY_PASSPHRASE",
                "WORKSPACE_HOST_ID", "WORKSPACE_KEY_PIN_DIR"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def session_home() -> Path:
    assert _HOME is not None
    return _HOME
