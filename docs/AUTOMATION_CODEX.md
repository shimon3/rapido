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

It cannot write to `main`, target `main` with its generated PR, merge a PR,
create a tag, publish a release, use production signing credentials, or change
workflows, packaging, dependencies, versions, licenses, or release controls.
Codex runs without Git credentials and with read-only GitHub permissions. A
separate deterministic publisher receives only the bounded patch after two
policy checks; it cannot dispatch workflows.

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
3. Keep the active `Protect main` ruleset. For the single-maintainer beta
   branch, require a pull request, the `build` check, resolved conversations,
   and block deletion and force-pushes, but require **zero approvals** so the
   sole owner can merge their own reviewed PRs. Give no Actions actor a ruleset
   bypass. Codex-created proposals are opened as drafts, are checked as drafts
   after publication, and the workflow has no command that marks them ready,
   approves, or merges them. Keep repository auto-merge disabled. The owner
   must manually inspect, mark ready, and merge a proposal.
4. Create a dedicated OpenAI API project, explicitly select an approved Codex
   model and CLI version, and configure a small project hard spend limit plus
   alerts. The workflow allows at most three Codex sessions per rolling 24-hour
   period, with a 20-minute job timeout; that is not a limit of three API
   requests because one Codex session may make multiple billed requests. The
   current workflow has no explicit token budget and leaves model/CLI version
   at defaults, so choose and test those before activation. Spend-limit
   enforcement is not instantaneous and may slightly exceed the cap.
5. Create the GitHub environment `rapido-codex-autofix`, restrict its deployment
   branches to `main`, and add the project key there (not as a repository-wide
   secret) under the name `RAPIDO_CODEX_OPENAI_API_KEY`.
6. Add the repository variable `RAPIDO_CODEX_AUTOFIX_ENABLED` with value `true`
   only after the environment restriction has been verified.
7. Verify the merged periodic dispatcher and its schedule before activation.
   Do not manually dispatch unreviewed refs.

## Current review checkpoint

- On 2026-10-27, commit `b447687` added an API postcondition that rejects any
  Codex proposal PR that is no longer draft, and moved issue logging into a
  separate `issues:write` job. The policy dry-run passed.
- The first Windows build found only a static-test boundary mistake: the test
  included the adjacent issue-reporting job when measuring the publisher's
  permissions. The workflow permissions were already separated correctly.
- Retry 1 for this test-only cause succeeded after the section boundary was
  corrected. Run `40536424501` passed the policy tests, all regression tests,
  the Windows build, isolated self-test, installer and portable packaging.
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
