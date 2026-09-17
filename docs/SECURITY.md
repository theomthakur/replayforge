# Security notes

Audience: anyone running ReplayForge against repositories they did not write.

ReplayForge is an **evaluation prototype**, not a hardened code-execution service.

## Controls in place

- Repository text is treated as untrusted data in the system prompt; it is never promoted to instructions.
- Each case runs in a disposable copy of the fixture. File tools resolve paths after following symlinks and
  reject anything outside the workspace.
- Commands must match an allowlist (`python -m pytest`, `python -m py_compile`) with no shell syntax, and
  run without a shell, with a scrubbed environment (no application secrets), a dead proxy for network
  calls, CPU and file-size limits, and a process-group kill on timeout.
- Protected paths are hashed before and after each run; editing a test to make it pass fails grading.
- Secrets are redacted before persistence, events, reports and exports.
- API keys are read from the server environment only. `.env`, databases, traces and evidence are gitignored.
- GitHub webhooks require a valid HMAC signature; delivery IDs are deduplicated.
- Server-side budgets cap cases and provider calls independently of the UI.

## Known gaps

- The local sandbox is process-level, not kernel-level isolation. Use the Docker backend
  (`SANDBOX_BACKEND=docker`) once verified; it is written but has not been exercised yet.
- No authentication in local demo mode. Do not expose the API publicly without adding it.
- No rate limiting on experiment creation yet beyond the budget gate.
