"""Durable, narrow browser handoff. Called only on the manager event loop."""
import asyncio
import hmac
import secrets
import uuid
import engine
from native_protocol import public_capture
from native_diagnostics import event, trace

MAX_PREPARED = 128

from native_protocol import handoff_message as validate

def _persist(manager,dl):
    # A preparation acknowledgement requires durable protected state.
    if not engine.IS_WINDOWS:
        raise OSError("Protected handoff persistence unavailable")
    with trace('handoff', 'protect', records=len(manager.downloads)):
        record=dl.protected_record()
    with trace('handoff', 'persist', records=len(manager.downloads)):
        manager.save(force=True,protected_record=(dl.id,record))

def activate(manager,dl):
    if dl.status!="handoff":
        return {"type":"capture_result","ok":True}
    dialog=bool(manager.settings.get("show_capture_dialog",True))
    dl.status="pending" if dialog else "queued"
    try:
        _persist(manager,dl)
    except Exception:
        dl.status="handoff"
        event('handoff', 'rollback', operation='capture_commit', records=len(manager.downloads))
        raise
    # Never start the network/probe/window before the commit is persisted.
    if dialog:
        manager._probes[dl.id]=asyncio.create_task(manager._probe_pending(dl))
    else:
        manager.wake()
    if not dialog and not manager.settings.get("show_progress_window",True):
        return {"type":"capture_result","ok":True}
    try:
        manager.open_window(f"/w?view={'capture' if dialog else 'progress'}&id={dl.id}",
                            560 if dialog else 520,580 if dialog else 480)
    except Exception:
        pass  # Accepted record survives; it remains recoverable from the desktop.
    return {"type":"capture_result","ok":True}

async def dispatch(manager,data):
    kind,value=validate(data)
    event('handoff', 'validate', operation=kind, records=len(manager.downloads),
          prepared=sum(d.status=='handoff' for d in manager.downloads.values()))
    if kind=="capture_prepare":
        if sum(d.status=="handoff" for d in manager.downloads.values())>=MAX_PREPARED:
            raise ValueError("Too many pending handoffs")
        dl=engine.Download(id=uuid.uuid4().hex[:10],url=value["url"],status="handoff",
            filename=engine.safe_filename(value["filename"]) if value["filename"] else "",
            headers={"Referer":value["referrer"]} if value["referrer"] else {},
            connections=int(manager.settings["connections"]),handoff_ticket=secrets.token_hex(32))
        dl.category=engine.category_for(dl.filename or dl.url)
        manager.downloads[dl.id]=dl
        event('handoff', 'created', operation=kind, records=len(manager.downloads))
        try:
            _persist(manager,dl)
        except Exception:
            manager.downloads.pop(dl.id,None)
            event('handoff', 'rollback', operation=kind, records=len(manager.downloads))
            raise
        return {"type":"capture_prepared","ticket":dl.handoff_ticket}
    dl=next((d for d in manager.downloads.values() if d.handoff_ticket and
             hmac.compare_digest(d.handoff_ticket,value)),None)
    if dl is None:
        return {"type":"error","code":"unknown_handoff"}
    if kind=="capture_commit":
        return activate(manager,dl)
    if dl.status!="handoff":
        return {"type":"error","code":"already_committed"}
    manager.downloads.pop(dl.id)
    try:
        with trace('handoff', 'persist', operation=kind, records=len(manager.downloads)):
            manager.save(force=True)
    except Exception:
        manager.downloads[dl.id]=dl
        event('handoff', 'rollback', operation=kind, records=len(manager.downloads))
        raise
    return {"type":"capture_aborted","ok":True}
