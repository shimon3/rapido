"""Single-purpose browser IPC protocol; never accepts headers/cookies/commands."""
from urllib.parse import urlsplit

def public_capture(data):
    if not isinstance(data, dict) or set(data) != {"type","url","referrer","filename"} or data["type"] != "capture_public":
        raise ValueError("Invalid public capture")
    url, referrer, filename = data["url"], data["referrer"], data["filename"]
    def valid_url(value):
        if (not isinstance(value, str) or not value or len(value)>4096 or
                any(ord(c)<32 or ord(c)==127 for c in value)):
            raise ValueError("Invalid public URL")
        parts = urlsplit(value)
        parts.port
        if parts.scheme not in ("http","https") or not parts.hostname or parts.username is not None or parts.password is not None:
            raise ValueError("Invalid public URL")
        return parts
    valid_url(url)
    if filename is not None and (not isinstance(filename,str) or len(filename)>255 or
            any(c in filename for c in "/\\") or any(ord(c)<32 or ord(c)==127 for c in filename)):
        raise ValueError("Invalid public filename")
    safe_referrer = None
    if referrer:
        safe_referrer = valid_url(referrer)._replace(query="",fragment="").geturl()
    elif referrer is not None and referrer != "":
        raise ValueError("Invalid referrer")
    return {"url":url, "referrer":safe_referrer, "filename":filename}


def handoff_message(data):
    if not isinstance(data,dict):
        raise ValueError("Invalid handoff")
    kind=data.get("type")
    if kind=="capture_prepare":
        return kind,public_capture({**data,"type":"capture_public"})
    if kind not in ("capture_commit","capture_abort") or set(data)!={"type","ticket"}:
        raise ValueError("Invalid handoff")
    ticket=data["ticket"]
    if not isinstance(ticket,str) or len(ticket)!=64 or any(c not in "0123456789abcdef" for c in ticket):
        raise ValueError("Invalid handoff ticket")
    return kind,ticket

