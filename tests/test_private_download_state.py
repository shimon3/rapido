import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import engine
import native_host

SECRET = "SIGNED_SECRET_76"
URL = "https://files.example/private/"+SECRET+"/a.zip?X-Amz-Signature="+SECRET+"#"+SECRET

def download():
    return engine.Download(id="abc123def0",url=URL,status="downloading",path="saved.zip",
        segments=[engine.Segment(0,100,40)],page_url=URL,candidates=[URL],thumbnail=URL,
        headers={"Cookie":"session="+SECRET,"Referer":URL},error="URL failed: "+URL,
        probe_error="Probe failed: "+URL,description=SECRET)

@unittest.skipUnless(os.name=="nt","DPAPI requires Windows")
class PrivateStateTests(unittest.TestCase):
    def test_real_dpapi_roundtrip_and_resume_without_plaintext_metadata(self):
        original=download()
        saved=original.to_disk()
        self.assertEqual(set(saved),{"id","private_state_version","private_state_enc"})
        self.assertNotIn(SECRET,json.dumps(saved))
        self.assertNotIn("https://",json.dumps(saved))
        restored=engine.Download.from_disk(saved)
        self.assertEqual(restored.url,URL)
        self.assertEqual(restored.headers,original.headers)
        self.assertEqual(restored.candidates,[URL])
        self.assertEqual(restored.thumbnail,URL)
        self.assertEqual(restored.description,SECRET)
        self.assertEqual(restored.downloaded,40)
        self.assertEqual(restored.status,"queued")
        self.assertEqual(saved["id"],original.id)  # from_disk does not mutate the envelope

    def test_legacy_history_is_encrypted_immediately_on_manager_load(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path=Path(folder)/"downloads.json"
            legacy={"id":"abc123def0","url":URL,"status":"paused",
                    "headers":{"Cookie":"untrusted-plain","Referer":URL},
                    "cookie_enc":engine.protect("session="+SECRET)}
            path.write_text(json.dumps([legacy]),encoding="utf-8")
            manager=engine.Manager(Path(folder))
            self.assertEqual(manager.downloads["abc123def0"].url,URL)
            self.assertEqual(manager.downloads["abc123def0"].headers["Cookie"],"session="+SECRET)
            content=path.read_text()
            self.assertNotIn(SECRET,content)
            self.assertNotIn("untrusted-plain",content)
            self.assertIn("private_state_enc",content)
            restarted=engine.Manager(Path(folder))
            self.assertEqual(restarted.downloads["abc123def0"].url,URL)
            self.assertEqual(restarted.downloads["abc123def0"].status,"paused")

    def test_dpapi_failure_never_falls_back_to_plaintext(self):
        with patch.object(engine,"protect",side_effect=OSError("DPAPI failed")):
            saved=download().to_disk()
        self.assertNotIn(SECRET,json.dumps(saved))
        restored=engine.Download.from_disk(saved)
        self.assertEqual(restored.status,"error")
        self.assertEqual(restored.url,"")

    def test_unreadable_or_modified_envelope_never_uses_sibling_plaintext(self):
        saved=download().to_disk()
        saved.update(url=URL,headers={"Cookie":SECRET})
        with patch.object(engine,"unprotect",side_effect=OSError("different account")):
            restored=engine.Download.from_disk(saved)
        self.assertEqual(restored.url,"")
        self.assertEqual(restored.headers,{})
        self.assertEqual(restored.status,"error")
        wrong=dict(saved,private_state_version=99)
        self.assertEqual(engine.Download.from_disk(wrong).url,"")
        wrong=dict(saved,id="different")
        self.assertEqual(engine.Download.from_disk(wrong).url,"")

    def test_zone_identifier_preserves_zone_but_only_discloses_origins(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path=Path(folder)/"file.zip"
            path.write_bytes(b"x")
            engine.mark_of_the_web(str(path),URL,"https://user:pass@page.example:443/"+SECRET+"?token="+SECRET)
            value=Path(str(path)+":Zone.Identifier").read_bytes().decode()
            self.assertIn("ZoneId=3\r\n",value)
            self.assertIn("HostUrl=https://files.example/\r\n",value)
            self.assertIn("ReferrerUrl=https://page.example:443/\r\n",value)
            self.assertNotIn(SECRET,value)
            self.assertNotIn("user:pass",value)
            engine.mark_of_the_web(str(path),"https://[::1]:8443/private?token="+SECRET)
            self.assertIn("HostUrl=https://[::1]:8443/\r\n",Path(str(path)+":Zone.Identifier").read_bytes().decode())

    def test_non_windows_cannot_interpret_encrypted_history_as_plaintext(self):
        saved=download().to_disk()
        saved["url"]=URL
        with patch.object(engine,"IS_WINDOWS",False):
            restored=engine.Download.from_disk(saved)
        self.assertEqual(restored.url,"")
        self.assertEqual(restored.status,"error")

class SignedNativeTests(unittest.TestCase):
    def test_signed_capture_preserves_required_url_only_on_native_channel(self):
        with patch.object(native_host,"_native_request",return_value={"type":"capture_result","ok":True}) as request:
            reply=native_host.handle_message({"type":"capture_public","url":URL,"referrer":URL,"filename":"a.zip"})
        self.assertEqual(reply,{"type":"capture_result","ok":True})
        sent=request.call_args.args[0]
        self.assertEqual(sent["url"],URL)
        self.assertEqual(sent["referrer"],"https://files.example/private/"+SECRET+"/a.zip")
        self.assertNotIn("headers",sent)

    def test_untrusted_native_server_has_no_http_fallback(self):
        with patch.object(native_host,"_native_request",side_effect=PermissionError("untrusted server")):
            reply=native_host.handle_message({"type":"capture_public","url":URL,"referrer":None,"filename":None})
        self.assertEqual(reply,{"type":"error","code":"rapido_unavailable"})
        self.assertNotIn(SECRET,json.dumps(reply))

if __name__=="__main__":
    unittest.main()
