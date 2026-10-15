# Rapido — Work restart checkpoint

Updated 2026-10-15. Read this file first; do not repeat the repository overview or stack reconciliation.

## Scope and authority

- Repository `shimon3/rapido`; working branch `work/beta-engine-guards-20261015`.
- Base: `a4cae19e43cffa8028814e46f42b125e1971d918`, current PR #32 HEAD when this branch was started.
- Main last verified: `18e0997ed0e09ed73d3723faef0904f2c5964af0`.
- Allowed: ordinary pushes on dedicated branches, create/update draft PRs, nonpublishing Actions.
- Forbidden: direct main changes, force-push, merges, release tags/releases/deployments, tests on the user's PC.
- Goal: first stable Windows beta, essential corrections only. One targeted task at a time; targeted tests before full CI. No security check reductions to save quota.

## Validated security work

PR #32 / issue #26: held-file Authenticode verifier, exact SHA-256 certificate pin, strict nonzero trust rejection, signature-state cleanup. Latest hardening rejects non-disk inputs, leaf reparse points/directories and differing kernel-resolved final paths before verification and before admission.

[Windows CI #179](https://github.com/shimon3/rapido/actions/runs/38682625394), code `a4cae19`: SUCCESS. 15 real signature tests passed with no skips, including actual symlink/junction and cross-process replacement; 154 full regression tests passed, 5 signed-fixture skips after fixture cleanup, 88 subtests, 1 warning. Desktop/native builds, real-window self-test, installer lifecycle/portable coexistence, real Firefox and packaging passed. Build token Contents:read; release job skipped. Runner is Windows Server 2025, not proof of Windows 10/11 validation.

CI #178 initially rejected only an over-specific test expectation: os.replace failed with WinError 5 instead of 32. Test now accepts either denial and also checks the source remains and destination SHA-256 is unchanged. No production verifier weakening.

#26 remains OPEN: no runtime signature admission wiring, protected production policy, production signing identity or enforced browser host-selection anchor. Do not claim same-user compromise prevented, or signature verification prevents injection. See `docs/windows-managed-integrity-contract.md`.

## Current targeted task: beta engine consolidation

PR inventory/ancestry review found PR #11's engine HEAD is absent from #32; source inspection confirmed its guards were missing. Created this dependent branch from #32 and applied only the engine patch, preserving S2/S3 code and the read-only/nonpublishing workflow.

Current changes:
- Persist ETag/Last-Modified/probe Date within existing DPAPI records; correct strong If-Range selection, including strict date age evidence and no weak-ETag date fallback.
- Reject changed validators, invalid range totals/order and bodies exceeding their declared range before writing.
- Stop immediately on disk-full/quota/short writes; use unbuffered FileIO so Python buffering does not falsely advance progress.
- Bound Retry-After for 429/503 and retain finite retry budget.
- Refresh of a partial download requires the same usable validator and range support, restores old URL/metadata on refusal, and pauses queued/running state during the probe to prevent scheduler races.
- New `tests/test_engine_five_guards.py` adapts PR #11 tests to stdlib asyncio (no extra pytest plugin) and adds actual HTTP response/refresh/persistence regressions.
- Workflow also copies the existing project LICENSE unchanged into the bundled app. This does not complete third-party license compliance.

Focused Linux checks: 20 engine tests passed; combined engine/HTTP integrity/resume/API/private-state/handoff checks: 39 passed, 13 Windows skips, 1 warning. Initial extended attempt was blocked by missing socksio for this environment's configured SOCKS proxy; installing it in the isolated test venv resolved that environment failure. Production requirements were not changed for this environment issue.

Pending: save branch remotely, create a dependent draft PR against `work/security-26-followup-20261015`, inspect Windows CI, correct failures. The Windows workflow is still the only workflow: this new branch has no push trigger; PR runs use read-only build permissions and a release job gated on explicit publication-tag push. No deployment step.

## Beta review and remaining work

`docs/beta-readiness-20261015.md` records the 26-PR inventory, ancestry findings, initial primary-source license review and a task/difficulty/effort table. PRs #2/#8/#9 are separate; defer nonessential additions. #3/#28 remain open because fixes are unmerged; #30 reconciliation is already complete.

Main unresolved gates: exact bundle dependency/version/license notices, provenance/attribution (LICENSE says Samuel Tuil; installer says Samuel Bentouza; do not rewrite ownership), clean Windows 10/11 desktop/browser VM matrix, critical dialogs, artifact hashes/Defender/rollback/version identification, final integration review. The report's 5–10 effective-day range is an engineering estimate for an explicitly bounded beta, not a calendar promise or full #26 guarantee; production signer/external setup delays are unestimated.

## Tools and verification reuse

- Local isolated Python: `/workspace/scratch/a15d48cb1e30/rapido-test-venv/bin/python`; Node available on PATH.
- Local Git has no write credentials. Use GitHub Git-data connector: create tree on current tree, commit with correct parent, create branch or update_ref with expected_sha and force=false. Verify remote HEAD; fetch, compare index/remote trees, then soft-reset local HEAD only after identical content is confirmed. Never overwrite concurrent remote work.
- Keep code/test/workflow commits on CI; documentation-only checkpoints may avoid redundant packaging, with explicit reference to the exact validated code SHA and a note that the documentation HEAD itself did not run CI.
