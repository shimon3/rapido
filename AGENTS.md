# Rapido automation guardrails

Before changing anything, read `docs/automation-state.md` and verify the
current branch, remote head, latest workflow result, and retry counters.

Work only on `automation/rapido-beta2-20261027` unless the owner explicitly
authorizes a different dedicated branch. Preserve full Git history and never
overwrite the older local `rapido` or `testrapido` folders.

Allowed: focused fixes confirmed by evidence, regression tests, non-publishing
CI artifacts, ordinary commits, pushes to the dedicated branch, and updates to
an unmerged pull request. Update `docs/automation-state.md` before every push.

Forbidden without new explicit approval: modifying or merging `main`, tags,
releases, deployments, production signing, purchases, deleting branches or
data, weakening security gates, and installing or running Rapido on the
owner's personal computer. Prefer GitHub Actions and disposable VMs for all
Windows execution.

For a repeated failure, record a root-cause-specific attempt in the journal.
Stop after three failed correction attempts for the same cause, document the
blocker in issue #37, and continue only with independent tasks.
