import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import remote_ai
from app.translation import RemoteEngine, Runtime

class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root / "key"
        self.key.write_text("test-secret")
        self.key.chmod(0o600)
        self.config = self.root / "remote-ai.json"
        self.value = dict(enabled=True, default=True, base_url="http://192.168.6.22:8888/v1",
            model="test-model", key_file=str(self.key))
        self.config.write_text(json.dumps(self.value))
        self.patch = patch.object(remote_ai, "CONFIG", self.config)
        self.patch.start()
        self.addCleanup(self.patch.stop)
    def test_private_configuration_and_stable_revision(self):
        first = remote_ai.manifest()
        self.assertEqual(first["revision"], remote_ai.manifest()["revision"])
        self.value["model"] = "another-model"
        self.config.write_text(json.dumps(self.value))
        self.assertNotEqual(first["revision"], remote_ai.manifest()["revision"])
    def test_public_url_and_readable_key_rejected(self):
        for url in ("http://8.8.8.8/v1", "http://example.com/v1", "http://192.168.6.22/v1?key=x"):
            self.value["base_url"] = url
            self.config.write_text(json.dumps(self.value))
            with self.assertRaises(ValueError): remote_ai.settings()
        self.value["base_url"] = "http://192.168.6.22/v1"
        self.config.write_text(json.dumps(self.value))
        self.key.chmod(0o644)
        with self.assertRaises(ValueError): remote_ai.settings()
    def test_only_content_used_and_authentication_sent(self):
        engine = RemoteEngine()
        engine.load(remote_ai.manifest())
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"choices":[{"finish_reason":"stop",
            "message":{"content":"Bonjour", "reasoning_content":"Never export this"}}]}).encode()
        opener = MagicMock()
        opener.open.return_value = response
        with patch("urllib.request.build_opener", return_value=opener):
            self.assertEqual(engine.translate("Hello"), "Bonjour")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(request.full_url, "http://192.168.6.22:8888/v1/chat/completions")
        response.read.return_value = b'{"choices":[{"finish_reason":"length","message":{"content":"partial"}}]}'
        with patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "incomplète"): engine.translate("Hello")
    def test_remote_visible_without_local_weights(self):
        from app.registry import Registry
        selected = Registry(self.root).choose("remote-bc250")
        self.assertTrue(selected["remote"])
    def test_runtime_remote_switch(self):
        runtime = Runtime()
        with patch.object(RemoteEngine, "_translate_prose", return_value="Bonjour"):
            self.assertEqual(runtime.translate(remote_ai.manifest(), ["Hello"], contextual=True), ["Bonjour"])
        self.assertIsInstance(runtime.engine, RemoteEngine)
