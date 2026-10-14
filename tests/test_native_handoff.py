import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
import engine
from native_handoff import dispatch,activate,MAX_PREPARED
import native_host

MESSAGE={"type":"capture_prepare","url":"https://example.org/a.zip?signature=secret",
         "referrer":"https://example.org/page?token=secret","filename":"a.zip"}

@unittest.skipUnless(os.name=="nt","Durable handoff requires Windows DPAPI")
class HandoffTests(unittest.TestCase):
    def run_case(self,callback):
        async def run():
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
                m=engine.Manager(Path(folder))
                m.open_window=lambda *args: None
                m._probe_pending=AsyncMock()
                return await callback(m)
        return asyncio.run(run())

    def test_prepare_has_no_network_no_auto_schedule_and_private_durable_ticket(self):
        async def case(m):
            with patch.object(m,"wake") as wake:
                reply=await dispatch(m,MESSAGE)
            dl=next(iter(m.downloads.values()))
            self.assertEqual(dl.status,"handoff")
            self.assertFalse(m._eligible(dl))
            self.assertFalse(m._probes)
            m._probe_pending.assert_not_awaited()
            wake.assert_not_called()
            self.assertNotIn("ticket",json.dumps(dl.to_public()))
            raw=m.state_file.read_text()
            self.assertNotIn("signature=secret",raw)
            self.assertNotIn(reply["ticket"],raw)
            restored=engine.Manager(m.data_dir)
            self.assertEqual(restored.downloads[dl.id].handoff_ticket,reply["ticket"])
            self.assertEqual(restored.downloads[dl.id].status,"handoff")
        self.run_case(case)

    def test_abort_before_commit_leaves_no_native_download(self):
        async def case(m):
            prepared=await dispatch(m,MESSAGE)
            reply=await dispatch(m,{"type":"capture_abort","ticket":prepared["ticket"]})
            self.assertEqual(reply,{"type":"capture_aborted","ok":True})
            self.assertFalse(m.downloads)
            self.assertEqual(json.loads(m.state_file.read_text()),[])
            reply=await dispatch(m,{"type":"capture_commit","ticket":prepared["ticket"]})
            self.assertEqual(reply["code"],"unknown_handoff")
        self.run_case(case)

    def test_commit_is_idempotent_even_after_manager_restart(self):
        async def case(m):
            m.settings["show_capture_dialog"]=False
            prepared=await dispatch(m,MESSAGE)
            request={"type":"capture_commit","ticket":prepared["ticket"]}
            with patch.object(m,"wake") as wake:
                self.assertTrue((await dispatch(m,request))["ok"])
                self.assertTrue((await dispatch(m,request))["ok"])
                wake.assert_called_once()
            self.assertEqual(len(m.downloads),1)
            restored=engine.Manager(m.data_dir)
            self.assertTrue((await dispatch(restored,request))["ok"])
            self.assertEqual(len(restored.downloads),1)
            self.assertEqual(next(iter(restored.downloads.values())).status,"queued")
            self.assertEqual((await dispatch(restored,{"type":"capture_abort","ticket":prepared["ticket"]}))["code"],"already_committed")
        self.run_case(case)

    def test_commit_with_dialog_probes_only_once_after_commit(self):
        async def case(m):
            prepared=await dispatch(m,MESSAGE)
            request={"type":"capture_commit","ticket":prepared["ticket"]}
            await dispatch(m,request)
            await dispatch(m,request)
            await asyncio.sleep(0)
            m._probe_pending.assert_awaited_once()
            self.assertEqual(next(iter(m.downloads.values())).status,"pending")
        self.run_case(case)

    def test_persistence_failure_cannot_ack_prepare_or_start_commit(self):
        async def case(m):
            with patch.object(m,"save",side_effect=OSError("disk unavailable")):
                with self.assertRaises(OSError):
                    await dispatch(m,MESSAGE)
            self.assertFalse(m.downloads)
            prepared=await dispatch(m,MESSAGE)
            with patch.object(m,"save",side_effect=OSError("disk unavailable")),patch.object(m,"wake") as wake:
                with self.assertRaises(OSError):
                    await dispatch(m,{"type":"capture_commit","ticket":prepared["ticket"]})
                wake.assert_not_called()
            self.assertEqual(next(iter(m.downloads.values())).status,"handoff")
            self.assertFalse(m._probes)
        self.run_case(case)

    def test_dpapi_failure_cannot_ack_prepare(self):
        async def case(m):
            with patch.object(engine,"protect",side_effect=OSError("DPAPI")):
                with self.assertRaises(OSError):
                    await dispatch(m,MESSAGE)
            self.assertFalse(m.downloads)
        self.run_case(case)

    def test_capacity_bounds_and_schema_reject_arbitrary_authority(self):
        async def case(m):
            for i in range(MAX_PREPARED):
                m.downloads[str(i)]=engine.Download(id=str(i),url="https://example.org/",status="handoff")
            with self.assertRaises(ValueError):
                await dispatch(m,MESSAGE)
            for data in ({**MESSAGE,"headers":{"Cookie":"private"}},
                         {"type":"capture_commit","ticket":"bad"},
                         {"type":"capture_abort","ticket":"f"*64,"id":"other"}):
                with self.assertRaises(ValueError):
                    await dispatch(m,data)
        self.run_case(case)

class NativeHostHandoffTests(unittest.TestCase):
    def test_host_validates_request_and_reply_without_http_or_bearer(self):
        with patch.object(native_host,"_native_request",return_value={"type":"capture_prepared","ticket":"a"*64}):
            self.assertEqual(native_host.handle_message(MESSAGE),{"type":"capture_prepared","ticket":"a"*64})
        with patch.object(native_host,"_native_request",return_value={"type":"capture_prepared","ticket":"bad"}):
            self.assertEqual(native_host.handle_message(MESSAGE)["code"],"handoff_unavailable")
        with patch.object(native_host,"_native_request") as request:
            self.assertEqual(native_host.handle_message({**MESSAGE,"Cookie":"private"})["code"],"handoff_unavailable")
            request.assert_not_called()
        with patch.object(native_host,"_native_request",return_value={"type":"capture_result","ok":True}):
            self.assertTrue(native_host.handle_message({"type":"capture_commit","ticket":"a"*64})["ok"])

if __name__=="__main__":
    unittest.main()
