# Windows update security contract

Status: beta safety boundary. Rapido currently checks for updates and opens an
official GitHub page or installer link. It does not silently download or execute
an update.

## Current beta behavior

- The check reads the latest non-prerelease release from the fixed
  `shimon3/rapido` GitHub API endpoint.
- The final response URL must remain the exact HTTPS GitHub API endpoint; a
  redirected-to-foreign/path/query response is rejected.
- The response body is bounded to 2 MiB and must be a JSON object with an asset
  list before version fields are used.
- The tag must be a final numeric version.
- A direct installer is offered only when its name exactly matches the tag and
  its HTTPS URL is the exact official GitHub release-download path.
- A missing, mismatched, redirected-in-metadata, or foreign installer URL falls
  back to the human-readable official release page.
- No background installer execution, privilege prompt, tag creation, release,
  or publication is performed.

This is intentionally a notification flow, not automatic deployment. TLS and a
fixed GitHub origin prevent accidental metadata substitution, but they are not
a replacement for a verified publisher signature.

## Gate before automatic installation

Do not add unattended download-and-execute behavior until all of the following
are available:

1. a production Authenticode identity approved for Rapido;
2. a release manifest that binds version, asset name, byte length, SHA-256, and
   expected publisher certificate identity;
3. verification of the downloaded installer's hash, Authenticode trust,
   timestamp, and exact publisher before execution;
4. downgrade, replay, wrong-channel, wrong-architecture, wrong-publisher,
   tampered-file, revoked/expired/indeterminate-signature, and interrupted
   download tests;
5. a user-visible confirmation unless an explicitly administered update policy
   authorizes unattended installation;
6. graceful shutdown that does not interrupt active downloads without consent;
7. Windows 10 and Windows 11 upgrade, rollback/failure, repair, and uninstall
   evidence for the exact signed candidate.

A valid signature from an unexpected publisher must fail closed. A release
marked as a beta must never be offered to stable users merely because it is
newer.

## Recommended future flow

1. check the fixed official release endpoint;
2. validate the release schema, channel, and monotonic version;
3. download to a newly created, private temporary directory;
4. verify length and SHA-256 from the authenticated release manifest;
5. verify Authenticode and the pinned/approved publisher identity;
6. ask the user to install and coordinate a graceful Rapido shutdown;
7. launch the verified installer with a version-bound update token or mode;
8. after restart, verify the installed version and browser registrations;
9. retain only non-sensitive failure diagnostics and remove temporary content.

Until these gates are implemented and tested, the current manual update link is
the safe beta behavior.
