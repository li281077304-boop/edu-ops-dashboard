# Ralph product-loop evidence (2026-09-16)

The Weekly Report module was exercised from a Ralph-owned isolated worktree;
the original product worktree and the desktop source workspace were not
modified.

## Durable runs

- `weekly-report-ralph-20260916-r3`: Chief SELECT and finite Luna Worker ran;
  Machine Gate failed because the initial required commands invoked unavailable
  bare `pytest`/`ruff` executables. Recovery then exposed a missing
  `worker_block.json` protocol path.
- `weekly-report-ralph-20260916-r5`: Chief SELECT, finite Luna Worker and
  Machine Gate ran; the gate recorded the same command-environment issue and
  entered technical recovery. Supervisor bounded repeated recovery failures.
- `weekly-report-ralph-20260916-r6`: Chief SELECT, finite Luna Worker and
  Machine Gate completed with both required commands passing. Checkpoint did
  not complete because the current Ralph checkpoint intent included controller
  runtime files in its working-tree intent; no review verdict was fabricated.
- `weekly-report-ralph-20260916-r7`: Host Chief transport reached the real
  Codex CLI but the model service repeatedly timed out before a SELECT reply;
  the run was stopped without manual verdict injection.

The raw run directories remain in their isolated Ralph worktrees under
`/private/tmp/edu-ops-dashboard-weekly-report-ralph-*`. This is intentionally
`TECHNICAL_OPEN`, not PASS: a complete Chief → Worker → Gate → checkpoint →
Review chain has not been proven for this product run.
