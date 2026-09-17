import pytest
from replayforge.redaction import redact
from replayforge.sandbox import LocalSandbox, PathViolation
from replayforge.sandbox.tools import TOOL_SCHEMAS, ToolExecutor


@pytest.fixture
def sandbox(suite):
    box = LocalSandbox(suite.fixture_path)
    yield box
    box.close()


def test_path_containment(sandbox, tmp_path):
    with pytest.raises(PathViolation):
        sandbox.resolve("../../etc/passwd")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (sandbox.workspace / "link").symlink_to(outside)
    with pytest.raises(PathViolation):
        sandbox.resolve("link")


async def test_malformed_arguments_are_recorded_not_raised(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    outcome = await executor.execute("apply_patch", {"file": "x", "text": "y"})
    assert not outcome.ok and outcome.error_kind == "malformed_arguments"


async def test_unauthorized_tool(sandbox):
    executor = ToolExecutor(sandbox, ["read_file", "finish"])
    outcome = await executor.execute("run_command", {"command": "python -m pytest -q"})
    assert outcome.error_kind == "unauthorized_tool"


async def test_apply_patch_and_run_tests(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    content = (
        (sandbox.workspace / "shop/cart.py")
        .read_text()
        .replace("item.unit_price_cents for", "item.unit_price_cents * item.quantity for")
    )
    patched = await executor.execute("apply_patch", {"path": "shop/cart.py", "content": content})
    assert patched.ok and patched.changed_files == ["shop/cart.py"]
    run = await executor.execute("run_command", {"command": "python -m pytest -q tests/test_cart.py"})
    assert run.ok and run.exit_code == 0


async def test_unified_diff_patch(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    diff = (
        "--- a/shop/dates.py\n+++ b/shop/dates.py\n@@ -4,4 +4,4 @@\n"
        ' def parse_order_date(value: str) -> date:\n     """Parse an ISO order date like 2026-09-17."""\n'
        '     year, month, day = value.strip().split("-")\n'
        "-    return date(int(year), int(day), int(month))\n+    return date(int(year), int(month), int(day))\n"
    )
    outcome = await executor.execute("apply_patch", {"patch": diff})
    assert outcome.ok, outcome.result
    assert "int(month), int(day)" in (sandbox.workspace / "shop/dates.py").read_text()


async def test_patch_path_escape_rejected(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    outcome = await executor.execute("apply_patch", {"patch": "--- a/../x\n+++ b/../x\n@@ -0,0 +1 @@\n+x\n"})
    assert outcome.error_kind == "path_violation"


async def test_rename_path_escape_rejected(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    patch = "diff --git a/shop/dates.py b/escaped.py\nsimilarity index 100%\nrename from shop/dates.py\nrename to ../escaped.py\n"
    outcome = await executor.execute("apply_patch", {"patch": patch})
    assert outcome.error_kind == "path_violation"


async def test_symbolic_link_patch_rejected(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    patch = "diff --git a/link b/link\nnew file mode 120000\n--- /dev/null\n+++ b/link\n@@ -0,0 +1 @@\n+../../outside\n"
    outcome = await executor.execute("apply_patch", {"patch": patch})
    assert outcome.error_kind == "path_violation"


async def test_disallowed_command_is_a_tool_error(sandbox):
    executor = ToolExecutor(sandbox, list(TOOL_SCHEMAS))
    outcome = await executor.execute("run_command", {"command": "python -c 'print(1)'"})
    assert outcome.error_kind == "tool_error"


async def test_timeout_kills_process(sandbox):
    (sandbox.workspace / "tests/test_sleep.py").write_text("import time\n\ndef test_sleep():\n    time.sleep(30)\n")
    result = await sandbox.run("python -m pytest -q tests/test_sleep.py", timeout_seconds=1.5)
    assert result.timed_out and result.duration_ms < 10_000


def test_redaction():
    text = redact("key sk-abcdefghijklmnopqrstuvwxyz0123 and ghp_" + "a" * 36)
    assert "sk-abc" not in text and "ghp_" not in text and "[REDACTED" in text
