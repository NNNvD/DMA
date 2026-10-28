import os
import ctypes
from types import SimpleNamespace

import pytest

from backend.agent.operator_identity import operator_identity
from backend.agent import operator_identity as identity_module


def test_operator_identity_cannot_be_supplied_through_reviewer_environment(monkeypatch):
    for name in ("USER", "USERNAME", "LOGNAME"):
        monkeypatch.setenv(name, "model-supplied-reviewer")
    actual = operator_identity()
    assert actual.startswith("windows:" if os.name == "nt" else "uid:")
    assert "model-supplied-reviewer" not in actual


@pytest.mark.parametrize("failure", ["size_unavailable", "identity_unavailable"])
def test_missing_os_identity_fails_without_a_reviewer_fallback(monkeypatch, failure):
    class Query:
        calls = 0

        def __call__(self, kind, buffer, size):
            self.calls += 1
            if self.calls == 1 and failure == "identity_unavailable":
                size._obj.value = 12
            return False

    monkeypatch.setattr(identity_module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *a, **k: SimpleNamespace(GetUserNameExW=Query()),
        raising=False,
    )
    with pytest.raises(RuntimeError, match="identity is unavailable"):
        operator_identity()


def test_posix_operator_uses_uid_instead_of_a_label(monkeypatch):
    monkeypatch.setattr(
        identity_module, "os", SimpleNamespace(name="posix", getuid=lambda: 42)
    )
    assert operator_identity() == "uid:42"
