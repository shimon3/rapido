# Rapido Windows beta release gate

Status: **NOT APPROVED FOR PUBLIC DISTRIBUTION**

This checklist is the release decision record, not proof that tests passed.

## Mandatory blockers
- [ ] S2: every state-changing local HTTP API endpoint is authenticated through a trusted native transport. Demonstrate arbitrary local HTTP clients without credentials cannot create downloads, delete files, change settings, launch tools, or trigger window/power actions.
- [ ] S2: Windows IPC uses an actual restrictive ACL and validates the connected client's identity; test untrusted same-user and other-user processes, reconnect and restart behavior. A SID-only DACL does not prove a caller is Rapido.
- [ ] S3: browser cookies, Authorization headers and private downloads cannot reach an unauthenticated loopback endpoint, including automatic capture, context menu and video capture paths. Private browser sessions should remain in Chrome until a reviewed authenticated solution exists.
- [ ] Clean install and uninstall on a separate Windows 11 test account; verify Chrome native-host registry registration, extension connection, removal, and no lingering processes.
- [ ] Run all unit/regression suites, Windows build/selftest, and manually verify cancel, pause, resume after restart, file integrity, 429/503, disk-full handling and changed-ETag recovery.
- [ ] Check packaged app and installer with Windows Defender and inspect external dependencies. Ensure release assets come from reviewed commit/tag; verify file hashes.
- [ ] Review PR integration order (#6 -> #7 -> #10 -> #11; #5 overlaps with #7, #2/#8/#9 separate). Never merge all branches blindly; check conflicts and retest.
- [ ] Confirm no test keys, debug logging, browser session secrets or access tokens are included in release files.
- [ ] Record signed-off Windows test results and rollback steps.

## Beta-specific UX checks
- [ ] French, English and Hebrew strings used in setup and critical dialogs are readable; Hebrew layout supports RTL without hiding actions.
- [ ] Extension disabled or missing: Rapido starts and downloads directly.
- [ ] Official download is clearly labeled beta and documents unsupported/private downloads.
- [ ] Updating a prior install preserves settings and partial downloads without silently downgrading a later installed version.

## Current evidence
- Chrome native ping/pong and one public `.dat` download via context menu were tested manually on one Windows PC.
- PR #10 contains a separate authenticated route, but legacy routes remain unauthenticated.
- PR #11 adds engine guards; automated CI results alone are insufficient to validate all real-world cases.

No public download link should be advertised as fully safe until every mandatory blocker is reviewed and checked off.
