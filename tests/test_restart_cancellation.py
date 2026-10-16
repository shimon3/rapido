"""Restart must wait for the real old task, including concurrent API requests."""
import asyncio
from pathlib import Path
from unittest.mock import patch

import app
import engine


def manager_with_download(folder):
    final = folder / 'download.bin'
    part = Path(str(final) + '.part')
    part.write_bytes(b'partial')
    dl = engine.Download('abc123', 'https://example.org/file', path=str(final), status='downloading',
                         segments=[engine.Segment(0, 99, done=7)])
    manager = engine.Manager.__new__(engine.Manager)
    manager.downloads = {dl.id: dl}
    manager.tasks = {}
    manager._stop_flags = {}
    manager._procs = {}
    manager.save = lambda **kwargs: None
    manager.wake = lambda: None
    return manager, dl, final, part


def test_concurrent_restarts_wait_until_old_writer_finishes(tmp_path):
    async def scenario():
        manager, dl, final, part = manager_with_download(tmp_path)
        stopping, release = asyncio.Event(), asyncio.Event()
        async def writer():
            try:
                await asyncio.Event().wait()
            finally:
                stopping.set()
                await release.wait()
                part.write_bytes(b'last write from old task')
        old = manager.tasks[dl.id] = asyncio.create_task(writer())
        await asyncio.sleep(0)
        with patch.object(app, 'manager', manager):
            first = asyncio.create_task(app.redownload(dl.id))
            await asyncio.wait_for(stopping.wait(), 2)
            second = asyncio.create_task(app.redownload(dl.id))
            try:
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not first.done() and not second.done()
                assert manager.tasks.get(dl.id) is old
                assert part.read_bytes() == b'partial'
                assert dl.path == str(final) and dl.status == 'downloading'
            finally:
                release.set()
                await asyncio.gather(first, second)
            assert old.done()
            assert not part.exists()  # Old cleanup cannot recreate an orphan after reset.
            assert dl.path == '' and dl.segments == [] and dl.status == 'queued'
            assert dl.id not in manager.tasks
    asyncio.run(scenario())


def test_cancelled_restart_caller_does_not_interrupt_old_cleanup_or_reset_state(tmp_path):
    async def scenario():
        manager, dl, final, part = manager_with_download(tmp_path)
        stopping, release = asyncio.Event(), asyncio.Event()
        async def writer():
            try:
                await asyncio.Event().wait()
            finally:
                stopping.set()
                await release.wait()
                part.write_bytes(b'cleanup completed')
        old = manager.tasks[dl.id] = asyncio.create_task(writer())
        await asyncio.sleep(0)
        with patch.object(app, 'manager', manager):
            restart = asyncio.create_task(app.redownload(dl.id))
            await asyncio.wait_for(stopping.wait(), 2)
            try:
                restart.cancel()
                try:
                    await restart
                except asyncio.CancelledError:
                    pass
                else:
                    raise AssertionError('Cancelled request unexpectedly committed restart')
                assert not old.done() and old.cancelling() == 1
                assert manager.tasks.get(dl.id) is old
                assert dl.path == str(final) and part.read_bytes() == b'partial'
                assert dl.status == 'paused'  # Stop requested, restart not committed.
            finally:
                release.set()
                await asyncio.gather(old, return_exceptions=True)
            assert part.read_bytes() == b'cleanup completed'
            await app.redownload(dl.id)  # A later explicit retry can finish safely.
            assert not part.exists() and dl.status == 'queued'
    asyncio.run(scenario())


def test_restart_preserves_completed_file_and_clears_only_partial_state(tmp_path):
    async def scenario():
        manager, dl, final, part = manager_with_download(tmp_path)
        dl.status = 'completed'
        final.write_bytes(b'completed user file')
        with patch.object(app, 'manager', manager):
            await app.redownload(dl.id)
        assert final.read_bytes() == b'completed user file'
        assert not part.exists()
        assert dl.path == '' and dl.status == 'queued' and dl.segments == []
    asyncio.run(scenario())
