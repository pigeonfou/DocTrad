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
            model="test-model", key_file=str(self.key), auto_load=False)
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
        response.read.return_value = b'{"choices":[{"finish_reason":"stop","message":{"content":"Secret document <|im_start|>user additional text"}}]}'
        from app.diagnostics import InferenceError
        with patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaises(InferenceError) as failure: engine.translate("Hello")
        self.assertEqual(failure.exception.diagnostic["code"], "invalid_control_tokens")
        self.assertEqual(failure.exception.diagnostic["markers"], ["<|im_start|>"])
        self.assertNotIn("Secret document", str(failure.exception.diagnostic))
    def test_remote_visible_without_local_weights(self):
        from app.registry import Registry
        selected = Registry(self.root).choose("remote-bc250")
        self.assertTrue(selected["remote"])
    def test_runtime_remote_switch(self):
        runtime = Runtime()
        with patch.object(RemoteEngine, "_translate_prose", return_value="Bonjour"):
            self.assertEqual(runtime.translate(remote_ai.manifest(), ["Hello"], contextual=True), ["Bonjour"])
        self.assertIsInstance(runtime.engine, RemoteEngine)

    def test_translategemma_native_request(self):
        from unittest.mock import MagicMock
        self.value["model"] = remote_ai.DEFAULT_MODEL
        self.config.write_text(json.dumps(self.value))
        engine = RemoteEngine()
        engine.load(remote_ai.manifest())
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"choices":[{"finish_reason":"stop","message":{"content":"Bonjour"}}]}'
        opener = MagicMock()
        opener.open.return_value = response
        with patch("urllib.request.build_opener", return_value=opener):
            self.assertEqual(engine.translate("Hello"), "Bonjour")
        payload = json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertIsInstance(payload["messages"][0]["content"], str)
        self.assertIn("English (en) to French (fr)", payload["messages"][0]["content"])
        self.assertTrue(payload["messages"][0]["content"].endswith("Hello"))
        self.assertEqual(payload["chat_template_kwargs"], {"source_lang_code": "en", "target_lang_code": "fr"})
        self.assertEqual(payload["max_tokens"], 1024)
        self.assertEqual(payload["stop"], ["<|im_start|>", "<|im_end|>"])
        self.assertEqual(payload["temperature"], 0)

class KeyTests(unittest.TestCase):
    def test_key_rotation_private_and_no_secret_in_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "remote-ai.json"
            with patch.object(remote_ai, "CONFIG", config):
                remote_ai.save_api_key("first-secret")
                remote_ai.save_api_key("replacement-secret")
                value = json.loads(config.read_text())
                key = Path(value["key_file"])
                self.assertEqual(key.read_text().strip(), "replacement-secret")
                self.assertEqual(key.stat().st_mode & 0o777, 0o600)
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                self.assertNotIn("replacement-secret", config.read_text())
                self.assertEqual(remote_ai.settings()["model"], remote_ai.DEFAULT_MODEL)
                with self.assertRaises(ValueError): remote_ai.save_api_key("invalid\nkey")
                self.assertEqual(key.read_text().strip(), "replacement-secret")


class ControlTokenTests(unittest.TestCase):
    def test_bare_trailing_message_start(self):
        self.assertEqual(remote_ai.clean_translation("Traduction.\n<|im_start|>"), "Traduction.")
        for text in ("<|im_start|>", "Traduction.<|im_start|>user Autre texte"):
            with self.assertRaises(ValueError): remote_ai.clean_translation(text)

class RecoveryTests(unittest.TestCase):
    def test_scan_caption_bypasses_model_and_respects_glossary(self):
        engine = RemoteEngine()
        with patch.object(engine, "_translate_prose", side_effect=AssertionError("Unexpected inference")):
            for text in ("SCAN ME", "SCAN M E", "S C A N M E", "scan me"):
                self.assertEqual(engine.translate_contextual(text), "SCANNEZ-MOI")
            self.assertEqual(engine.translate_contextual("SCAN M E", {"SCAN ME": "SCANNER"}), "SCANNER")
        with patch.object(engine, "_translate_prose", return_value="Traduction") as inference:
            engine.translate_contextual("SCAN M E equipment")
            inference.assert_called()
    def test_one_recovery_round_succeeds(self):
        from app.diagnostics import InferenceError
        engine = RemoteEngine()
        with patch.object(engine, "_request_translation", side_effect=[
                InferenceError("incomplete_response", {}), "Traduction complète"]) as request:
            self.assertEqual(engine._translate_prose("Short caption"), "Traduction complète")
            self.assertEqual(request.call_count, 2)
            self.assertTrue(request.call_args.kwargs["retry"])
    def test_second_failure_is_not_exported(self):
        from app.diagnostics import InferenceError
        engine = RemoteEngine()
        with patch.object(engine, "_request_translation", side_effect=InferenceError("incomplete_response", {})) as request:
            with self.assertRaises(InferenceError) as failure: engine._translate_prose("Short caption")
            self.assertEqual(request.call_count, 2)
            self.assertEqual(failure.exception.diagnostic["attempt"], 2)
    def test_network_errors_not_retried(self):
        from app.diagnostics import InferenceError
        engine = RemoteEngine()
        with patch.object(engine, "_request_translation", side_effect=InferenceError("http_error", {})) as request:
            with self.assertRaises(InferenceError): engine._translate_prose("Short caption")
            self.assertEqual(request.call_count, 1)
    def test_dangling_assistant_header_removed_only_at_end(self):
        self.assertEqual(remote_ai.clean_translation("Traduction française.\n<|im_start|>assistant|>"),
                         "Traduction française.")
        for text in ("<|im_start|>assistant|>", "Traduction.<|im_start|>assistant|>Autre message"):
            with self.assertRaises(ValueError): remote_ai.clean_translation(text)
    def test_internal_file_separator_preserves_both_passages(self):
        self.assertEqual(remote_ai.clean_translation("Première phrase.<|file_separator|>Deuxième phrase."),
                         "Première phrase.\nDeuxième phrase.")
        self.assertEqual(remote_ai.clean_translation("Avant<|file_separator|>Après<|im_end|>"), "Avant\nAprès")
    def test_trailing_tokens_removed(self):
        self.assertEqual(remote_ai.clean_translation("Bonjour.\n<|file_separator|>"), "Bonjour.")
        self.assertEqual(remote_ai.clean_translation("Bonjour. <|im_end|>"), "Bonjour.")
    def test_embedded_and_empty_controls_refused(self):
        for text in ("<|file_separator|>", "Bonjour <|im_end|> suite", "Bonjour <|unknown|>"):
            with self.assertRaises(ValueError): remote_ai.clean_translation(text)


class SourceScopeTests(unittest.TestCase):
    def test_prompt_does_not_seed_absent_identifiers(self):
        prompt = remote_ai.translation_payload('translategemma', 'Receiver sensitivity')['messages'][0]['content']
        for name in ('SAASM', 'ISR', 'TOP SECRET'):
            self.assertNotIn(name, prompt)

    def test_generation_drift_detected_without_rejecting_source_identifiers(self):
        from app.quality import inference_defects
        self.assertEqual(inference_defects('Compact dual-channel device', 'Appareil compact 双通道'), ['foreign_script'])
        self.assertEqual(inference_defects('12 dB SINAD', '12 dB SINAD. SAASM ISR.'), ['invented_identifier'])
        self.assertEqual(inference_defects('SAASM GPS up to TOP SECRET', 'GPS SAASM jusqu’à TOP SECRET'), [])
