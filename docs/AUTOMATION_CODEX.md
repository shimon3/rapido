# Guarded Codex autofix for Rapido beta.2

This repository contains a deliberately disabled GitHub Actions loop for narrow
CI corrections. It reacts only to a failed, manually dispatched `Windows build`
on `automation/rapido-beta2-20261027` or on the loop's own draft-fix branch.

## What it can and cannot do

The loop can inspect bounded failed-job logs, ask Codex to edit an isolated
checkout, validate the resulting text patch, push a dedicated fix branch, open
or update a **draft** pull request targeting the beta automation branch. A
third job, with `actions: write` but no checkout, write access to contents, or
OpenAI key, revalidates the draft and dispatches its approved Windows workflow.

Its intended path cannot target `main` with a generated PR, merge a PR, create
a tag, publish a release, use production signing credentials, or change
workflows, packaging, dependencies, versions, licenses, or release controls.
Codex runs without Git credentials and with read-only GitHub permissions. A
Git-only deploy key pushes the validated fix branch; a separate deterministic
publisher receives only the bounded result and can create/update a draft PR.
The publisher's GitHub token has `pull-requests:write` and `contents:read`, not
`contents:write`, so it cannot call GitHub's merge API. The push job uses the
SSH deploy key for Git transport and a read-only `GITHUB_TOKEN` for API reads;
the deploy key is not an API credential.

Each failure lineage is limited to three reserved attempts. The entire
repository is also limited to three Codex attempts in a rolling 24-hour window.
All runs share one non-cancelling concurrency group, and every reservation is
persisted as a marker in issue #37 before an API call is possible.

## Activation checklist (owner action required)

The loop remains inactive unless **all** of these steps are completed:

1. Review and merge the workflow PR into the default branch.
2. Keep the repository default workflow permission at `read`. GitHub currently
   couples the ability of `GITHUB_TOKEN` to create a pull request with the
   ability to approve one. The loop needs PR creation, so enable **Allow GitHub
   Actions to create and approve pull requests** only after the beta branch
   protection in the next step is active. This workflow contains no approval or
   merge command.
3. Protect both `main` and `automation/rapido-beta2-20261027` with a pull
   request, required `build` check, resolved conversations, and rules blocking
   deletion and force-push. Require **Code Owner approval**, not only one
   generic approval. Put only the repository owner in `CODEOWNERS`, and verify
   that this file is present on both target branches. This matters because
   GitHub couples permission to create PRs with permission to approve PRs, and
   the publisher has `pull-requests:write`; a compromised publisher could
   approve a human-authored PR if ordinary approval alone were the gate. The
   bot is not a Code Owner, so its review cannot satisfy this rule. The PR
   publisher lacks `contents:write`, which GitHub requires for its merge API.
   The push job uses a repository deploy key for Git-only access, not an API
   token. Do not grant Actions any ruleset bypass. The sole owner can approve a proposal authored
   by `github-actions[bot]`; for a self-authored PR, configure the owner as a
   bypass actor limited to **pull requests only**, which still blocks direct
   pushes. This bypass is not approval-only: before using it, the owner must
   inspect the diff and confirm all required checks passed. Keep auto-merge
   disabled. The workflow creates drafts, verifies the author/base/head/draft state and
   absence of auto-merge after publication, and contains no approval, ready,
   or merge command. These workflow checks are defense in depth; branch rules
   must independently prevent the bot from satisfying the review gate.
4. Create a dedicated OpenAI API project, explicitly select an approved Codex
   model and CLI version, and configure a small project hard spend limit plus
   alerts. The workflow allows at most three Codex sessions per rolling 24-hour
   period, with a 20-minute job timeout; that is not a limit of three API
   requests because one Codex session may make multiple billed requests. The
   current workflow has no explicit token budget and leaves model/CLI version
   at defaults, so choose and test those before activation. Spend-limit
   enforcement is not instantaneous and may slightly exceed the cap.
5. Create the `rapido-codex-autofix` environment and restrict its deployment
   branches to `main`.
6. Create a dedicated repository deploy key with write access, add its public
   key under Settings → Deploy keys, and store its private key only in the
   environment as `RAPIDO_AUTOFIX_PUSH_KEY`. Add the separate project API key
   there as `RAPIDO_CODEX_OPENAI_API_KEY`. Neither key belongs in repository
   secrets. The deploy key is used only for Git push; rulesets must block
   direct writes to protected refs.
7. Add the repository variable `RAPIDO_CODEX_AUTOFIX_ENABLED` with value `true`
   only after the environment restriction has been verified.
8. Verify the merged periodic dispatcher and its schedule before activation.
   Do not manually dispatch unreviewed refs.

## Current review checkpoint

- On 2026-10-27, commit `b447687` added an API postcondition that rejects any
  Codex proposal PR that is not a draft, and moved issue logging into a
  separate `issues:write` job. Commit `498b103` corrected the test boundary;
  run `40536424501` passed the full Windows build.
- The first Windows build found only a static-test boundary mistake: the test
  included the adjacent issue-reporting job when measuring the publisher's
  permissions. The workflow permissions were already separated correctly.
- The publication job verifies the bot author, exact base/head, draft status and
  absence of auto-merge after each publish or update. It exposes no command to
  mark a proposal ready, approve, or merge it. Its token has no `contents:write`,
  so the merge API rejects it even if the PR has otherwise passed checks. A
  separate Git-only push job uses the deploy key but no merge-capable token.
  This hardening is in the current PR head and must pass CI before review.
- The current branch rules still require zero approvals and give no bypass.
  Owner-only Code Owner review, `CODEOWNERS` coverage on both target branches,
  and owner-only pull-request bypass for self-authored PRs are required
  owner-side activation steps, not yet applied.
- No API key was configured or used; the Codex, publication and dispatch jobs
  remained skipped.

Set `RAPIDO_CODEX_AUTOFIX_ENABLED` to `false` (or remove it) for an immediate
logical stop. Removing the API secret is the second kill switch. Existing draft
PRs remain reviewable and are never merged automatically.

## Codex Cloud hosted variant

OpenAI's Agents API supports persistent sessions and cron automations with an
explicit timezone. A hosted Rapido automation can therefore be created with the
following reviewed specification once that API is provisioned:

- name: `Rapido beta.2 supervisor`;
- schedule: `17 */3 * * *`, timezone `Asia/Jerusalem`;
- dedicated session and repository checkout, never a general-purpose session;
- first action: read issue #37 and the current draft automation PR;
- refuse to work while the GitHub autofix workflow or another hosted invocation
  owns the current failure lineage;
- use the same three-attempt markers, path/size policy, draft-PR target, and
  release/signing prohibitions defined in this repository;
- stop and report when a required action, approval, budget limit, merge,
  production signature, or local Windows test is needed.

This hosted automation is **not active**. The environment that prepared these
files did not expose an Agents API automation-creation tool or an OpenAI project
credential, and activation would authorize billable API work. Do not run this
hosted variant at the same time as the GitHub correction loop unless both use a
single externally enforced lease. GitHub Actions' concurrency group does not
lock an independent Codex Cloud session.

Official references:

- Codex GitHub Action: https://learn.chatgpt.com/docs/github-action
- OpenAI spend limits: https://developers.openai.com/api/docs/guides/spend-limits
- Agents API costs: https://developers.openai.com/api/docs/guides/agents-api/observability
- Scheduled Agents API automations: https://developers.openai.com/api/docs/guides/agents-api/sessions/automations
