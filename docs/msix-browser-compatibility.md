# MSIX compatibility study for Rapido

Status: design study only. No MSIX package, Store submission, publication, or
claim of browser compatibility is made by this document.

## Decision for the current beta

Keep the Inno Setup installer for the current beta. Do not replace it with a
full MSIX package until an isolated Windows 10/11 experiment proves the native
messaging lifecycle for Chrome, Edge, and Firefox.

Rapido's browser bridge depends on three facts:

1. each external browser must see an ordinary HKCU NativeMessagingHosts key;
2. that key must point to a manifest whose host path remains valid after an
   install or upgrade;
3. uninstall must remove only the registrations still owned by that Rapido
   installation.

The existing installer and tests exercise those ownership rules directly.

## Why a conventional full MSIX is not yet equivalent

Chrome and Edge discover a Windows native messaging host through browser
registry keys. Firefox uses the corresponding Mozilla registry key. Those
browsers are separate processes outside the Rapido package.

A conventional converted desktop MSIX virtualizes HKCU writes into a private
per-app hive by default. Such writes are not visible to external browser
processes. Package files also live under a versioned, read-only WindowsApps
location, so a registry manifest path must be proven across package updates.

The restricted `unvirtualizedResources` capability can make HKCU writes
visible outside a package, but it changes the isolation model and those writes
are not automatically cleaned on uninstall. Store acceptance of a restricted
capability must not be assumed. On Windows 11, exclusions can be narrower; the
Windows 10 fallback and removal behavior still require explicit tests.

MSIX does not itself install the browser extension into Chrome, Edge, or
Firefox. Store-distributed extensions retain their own browser-store identity,
and the native host manifests must allow the exact final extension IDs.

## Alternatives worth testing

### Full MSIX proof of concept

Only as an isolated experiment:

- package the two executables and browser manifests;
- use a test certificate trusted only on the disposable VM;
- prove whether narrowly unvirtualized HKCU browser keys are available for the
  required Windows 10 baseline and accepted by packaging validation;
- resolve the native-host path without relying on a stale package-version
  directory;
- update the package and prove all three browsers still launch the new host;
- remove the package and prove that no owned keys or files remain.

A successful launch of Rapido alone is not sufficient evidence.

### Package with external location

A sparse/external-location package can add Windows package identity while
leaving the executables, installer, registry access, and update mechanism in
their existing locations. It is less disruptive to native messaging, but it
does not replace the Inno Setup lifecycle or automatically solve updates and
signing.

### Microsoft Store with the existing installer

Evaluate the Store's current unpackaged EXE/MSI route separately. If accepted,
this can preserve the proven browser bridge while the Store supplies discovery
and acquisition. It must still pass Store policy, silent-install behavior,
upgrade, uninstall, signature, and browser integration tests.

## Required compatibility matrix

For every packaging candidate, test on clean Windows 10 and Windows 11:

- fresh install and first launch;
- real Chrome, Edge, and Firefox native ping and capture;
- upgrade while preserving settings and registrations;
- repair or reinstall;
- uninstall with an unrelated/portable Rapido copy present;
- removal of owned registry values without deleting a newer owner's value;
- no stale versioned manifest paths;
- SmartScreen/Smart App Control and Authenticode status;
- rollback or failed-update behavior.

Until this matrix passes for an exact artifact, MSIX remains a research path,
not the beta distribution format.
