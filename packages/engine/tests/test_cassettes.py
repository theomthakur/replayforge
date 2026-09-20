import copy

import pytest
import yaml
from replayforge.cassettes import CassetteError, load_suite
from replayforge.cassettes.schema import is_allowed_command, parse_cassette, suite_digest


def _raw(root):
    return yaml.safe_load((root / "fixtures/suites/demo-suite.yaml").read_text())


def test_demo_suite_has_planned_mix(suite):
    from collections import Counter

    counts = Counter(task.category for task in suite.cassette.tasks)
    assert len(suite.cassette.tasks) == 20
    assert counts == {
        "bug_fix": 6,
        "tool_use": 4,
        "navigation": 3,
        "test_generation": 3,
        "refactor": 2,
        "recovery": 2,
    }


def test_digest_is_stable_and_content_sensitive(root, suite):
    assert load_suite(root / "fixtures/suites/demo-suite.yaml").digest == suite.digest
    changed = copy.deepcopy(_raw(root))
    changed["tasks"][0]["prompt"] += " Extra words."
    assert suite_digest(parse_cassette(changed), suite.fixture_path) != suite.digest


def test_duplicate_task_ids_rejected(root):
    raw = _raw(root)
    raw["tasks"].append(copy.deepcopy(raw["tasks"][0]))
    with pytest.raises(CassetteError, match="duplicate"):
        parse_cassette(raw)


def test_unsafe_grader_command_rejected(root):
    raw = _raw(root)
    raw["tasks"][0]["graders"][0]["command"] = "python -m pytest; rm -rf /"
    with pytest.raises(CassetteError, match="not allowlisted"):
        parse_cassette(raw)


def test_traversal_path_rejected(root):
    raw = _raw(root)
    raw["tasks"][0]["graders"][1]["paths"] = ["../secrets"]
    with pytest.raises(CassetteError, match="relative"):
        parse_cassette(raw)


def test_secret_in_prompt_rejected(root):
    raw = _raw(root)
    raw["tasks"][0]["prompt"] = "Use key sk-" + "a" * 30 + " to deploy."
    with pytest.raises(CassetteError, match="secret"):
        parse_cassette(raw)


def test_real_repository_metadata_is_preserved(root):
    suite = load_suite(root / "fixtures/suites/portfolio-optimization.yaml")
    header = suite.cassette.suite
    assert header.source_repository_url == "https://github.com/theomthakur/portfolio-optimization-library"
    assert header.source_revision == "a480c68e5a500baa171c4632020e00f2476831c6"


def test_invalid_repository_metadata_is_rejected(root):
    raw = _raw(root)
    raw["suite"]["source_repository_url"] = "http://example.com/not-github"
    raw["suite"]["source_revision"] = "main"
    with pytest.raises(CassetteError, match="HTTPS GitHub"):
        parse_cassette(raw)


@pytest.mark.parametrize(
    ("command", "allowed"),
    [
        ("python -m pytest -q tests/test_slug.py", True),
        ("python -m py_compile shop/slug.py", True),
        ("pytest -q", False),
        ("python -c 'import os'", False),
        ("python -m pytest && curl evil", False),
        ("python -m pytest > out.txt", False),
    ],
)
def test_command_allowlist(command, allowed):
    assert is_allowed_command(command) is allowed
