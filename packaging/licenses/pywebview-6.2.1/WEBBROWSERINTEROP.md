# pywebview 6.2.1 — WebBrowserInterop.x64.dll / WebBrowserInterop.x86.dll

These two small .NET assemblies are shipped inside pywebview (legacy MSHTML
backend helper). They are not part of the Microsoft WebView2 SDK.

| Shipped file | SHA-256 |
| --- | --- |
| `webview/lib/WebBrowserInterop.x64.dll` | `f6a646470f0e1058224a52e8e2e217501dca46939b30bfc9a5dd4dcdd43f088d` |
| `webview/lib/WebBrowserInterop.x86.dll` | `4e527297fbea7c5a0419f3a6af307c2681787beb0bf0ef3fea849a7fd85a08dc` |

Checked on 2026-10-15: both files are byte-identical to the binaries committed
in the pywebview repository at tag `6.2.1`, commit
`2fc63cd6a92b8630c14f6d4dd73f9691591f8eea`
(https://github.com/r0x0r/pywebview/tree/2fc63cd6a92b8630c14f6d4dd73f9691591f8eea/webview/lib).
The binaries were last changed in commit `519aacbf9fcf` (2020-04-18, "Added
user-agent support for MSHTML"). Their C# source and Visual Studio project are
in the same repository under `interop/mshtml` (`WebBrowserInterop.cs`,
`WebBrowserInterop.csproj`), whose `README.txt` states that the project
generates these DLLs. The repository `LICENSE` is pywebview's BSD 3-Clause
license (Roman Sirokov), shipped as
`third-party/packages/pywebview/pywebview-6.2.1.dist-info/licenses/LICENSE`.

Not established: that the committed binaries were built from exactly that
source (no reproducible build was performed), and whether Rapido's WebView2
configuration ever loads these assemblies. The assembly metadata only states
"Copyright © 2017" without a holder. This file records evidence. It is not a
legal opinion.
