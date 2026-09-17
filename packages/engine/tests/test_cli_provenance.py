import argparse
from subprocess import CompletedProcess

import pytest
from replayforge.cli import _lane
from replayforge.provenance import git_revision
from replayforge.providers import LaneConfig, build_provider


def test_cli_rejects_unknown_fixture_profile():
    with pytest.raises(argparse.ArgumentTypeError, match="unknown fixture profile"):
        _lane("fixture:fixture/repair-discount")


def test_provider_construction_rejects_unknown_fixture_profile(suite):
    with pytest.raises(ValueError, match="unknown fixture profile"):
        build_provider(
            LaneConfig("fixture", "fixture/not-real"),
            cassette=suite.cassette,
            solutions_dir=suite.source_path.parents[1] / "solutions",
        )


def test_git_revision_marks_dirty_tree(monkeypatch, tmp_path):
    responses = iter(
        [
            CompletedProcess([], 0, stdout="a" * 40 + "\n", stderr=""),
            CompletedProcess([], 0, stdout=" M file.py\n", stderr=""),
        ]
    )
    monkeypatch.setattr("replayforge.provenance.subprocess.run", lambda *args, **kwargs: next(responses))
    assert git_revision(tmp_path) == "a" * 40 + "-dirty"
