# Guarded Codex autofix for Rapido beta.2

This repository contains a deliberately disabled GitHub Actions loop for narrow
CI corrections. It reacts only to a failed, manually dispatched `Windows build`
on `automation/rapido-beta2-20261027` or on the loop's own draft-fix branch.

## What it can and cannot do

The loop can inspect bounded failed-job logs, ask Codex to edit an isolated
checkout, validate the resulting text patch, push a dedicated fix branch, open
or update a **draft** pull request targeting the beta automation branch, and
dispatch that branch's approved Windows validation workflow.

It cannot write to `main`, target `main` with its generated PR, merge a PR,
create a tag, publish a release, use production signing credentials, or change
workflows, packaging, dependencies, versions, licenses, or release controls.
Codex runs without Git credentials and with read-only GitHub permissions. A
separate deterministic publisher receives only the bounded patch after two
policy checks.

Each failure lineage is limited to three reserved attempts. The entire
repository is also limited to three Codex attempts in a rolling 24-hour window.
All runs share one non-cancelling concurrency group, and every reservation is
persisted as a marker in issue #37 before an API call is possible.

## Activation checklist (owner action required)

The loop remains inactive unless **all** of these steps are completed:

1. Review and merge the workflow PR into the default branch.
2. Keep the repository default workflow permission at `read` and keep Actions
   unable to approve pull requests.
3. Protect `main` with a ruleset requiring pull requests and blocking direct
   pushes. No such protection existed when this workflow was prepared.
4. Create a dedicated OpenAI API project, select an approved current Codex
   model, and configure a small project hard spend limit plus alerts. Spend-limit
   enforcement is not instantaneous, so the workflow's attempt caps remain
   necessary.
5. Add the project key as the Actions secret `OPENAI_API_KEY`.
6. Add the repository variable `RAPIDO_CODEX_AUTOFIX_ENABLED` with value `true`.
7. Merge and observe the separate periodic-dispatcher PR so a fresh failed run
   can start the loop. Do not manually dispatch unreviewed refs.

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
