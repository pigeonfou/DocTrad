import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location("configure_remote", Path(__file__).parents[1] / "scripts/configure-remote-ai.py")
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)

class ConfigureTests(unittest.TestCase):
    def run_configure(self, quant="Q4_K_M", finish="stop", text="Débranchez l’alimentation avant toute maintenance."):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "remote-ai.key"
            key.write_text("test-key\n")
            key.chmod(0o600)
            config = root / "remote-ai.json"
            config.write_text(json.dumps(dict(model="old-qwen", key_file=str(key))))
            previous = config.read_text()
            replies = [dict(data=[dict(id="mradermacher/translategemma-12b-it-GGUF", loaded=True, quant=quant)]),
                dict(choices=[dict(finish_reason=finish, message=dict(content=text))])]
            opener = MagicMock()
            def response(*args, **kwargs):
                result = MagicMock()
                result.__enter__.return_value = result
                result.read.return_value = json.dumps(replies.pop(0)).encode()
                return result
            opener.open.side_effect = response
            argv = ["configure", "--data-root", directory, "--translategemma", "--reuse-key"]
            with patch("sys.argv", argv), patch.object(configure.os, "geteuid", return_value=0), \
                    patch.object(configure.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=0, pw_gid=0)), \
                    patch.object(configure.os, "chown"), patch("urllib.request.build_opener", return_value=opener):
                if quant.upper() != "Q4_K_M" or finish != "stop" or "alimentation" not in text:
                    with self.assertRaises(SystemExit): configure.main()
                    self.assertEqual(config.read_text(), previous)
                else:
                    configure.main()
                    value = json.loads(config.read_text())
                    self.assertTrue(value["default"])
                    self.assertEqual(value["model"], "mradermacher/translategemma-12b-it-GGUF")
                    self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                    self.assertNotIn("test-key", config.read_text())
                self.assertEqual(key.read_text(), "test-key\n")
    def test_detect_test_and_save_preserving_key(self): self.run_configure()
    def test_lowercase_quantization(self): self.run_configure(quant="q4_k_m")
    def test_wrong_quantization_keeps_configuration(self): self.run_configure(quant="Q2_K")
    def test_truncated_response_keeps_configuration(self): self.run_configure(finish="length")

    def test_english_answer_keeps_configuration(self):
        self.run_configure(text="Okay, I understand. I will disconnect the power supply before servicing.\n<|im_end|>")
    def test_french_answer_with_control_token(self):
        self.run_configure(text="Débranchez l’alimentation avant toute maintenance.\n<|file_separator|>")
