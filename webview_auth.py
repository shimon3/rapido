"""Native-only request authentication for Rapido's owned WebView2 windows.

No process token is placed in HTML, JavaScript, cookies, URLs or extension storage.
The desktop must own an exclusive loopback listener before attaching this policy.
"""
from urllib.parse import urlsplit, parse_qs

BASE = "http://127.0.0.1:9614"


def _local(url):
    if not isinstance(url, str) or any(ord(ch) < 32 for ch in url):
        return None
    try:
        value = urlsplit(url)
        if (value.scheme != "http" or value.hostname != "127.0.0.1" or value.port != 9614
                or value.username is not None or value.password is not None):
            return None
        return value
    except ValueError:
        return None


def trusted_page(current, initial):
    current, initial = _local(current), _local(initial)
    if current is None or initial is None or current.path != initial.path:
        return False
    if initial.path == "/":
        return not current.query and not current.fragment
    if initial.path != "/w":
        return False
    expected = parse_qs(initial.query, keep_blank_values=True)
    found = parse_qs(current.query, keep_blank_values=True)
    if set(expected) != {"id", "w", "view"} or set(found) != set(expected):
        return False
    return (found["id"] == expected["id"] and found["w"] == expected["w"] and
            len(found["id"]) == 1 and len(found["w"]) == 1 and
            len(found["view"]) == 1 and found["view"][0] in {"capture", "progress"} and
            not current.fragment)


def authorize_request(request, *, current_page, initial_page, auth):
    # Never let an already-added process header follow a redirect to another host.
    for key in list(request.headers):
        if key.lower() == "authorization":
            del request.headers[key]
    target = _local(request.url)
    if (target is None or not target.path.startswith("/api/") or
            not trusted_page(current_page, initial_page)):
        return False
    request.headers["Authorization"] = "Bearer " + auth.token_for_trusted_transport()
    return True


def attach(window, initial_page, auth):
    """Attach a synchronous native policy, preserving the existing hash-only CSP.

    pywebview 6.2.1's request_sent event is asynchronous by default; replace it
    with its synchronous Event implementation before any window is initialized.
    The callback executes on WebView2's request thread and reads Core.Source
    directly, avoiding a recursive get_current_url/evaluate_js GUI dispatch.
    """
    from webview.event import Event
    window.events.request_sent = Event(window, should_lock=True)

    def authenticate(request):
        try:
            source = str(window.native.browser.webview.CoreWebView2.Source)
        except (AttributeError, TypeError):
            source = None
        authorize_request(request, current_page=source, initial_page=initial_page, auth=auth)

    window.events.request_sent += authenticate
