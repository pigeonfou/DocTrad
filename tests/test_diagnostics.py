import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from app import diagnostics

class DiagnosticsTests(unittest.TestCase):
    def test_whitelist_never_retains_text_or_credentials(self):
        clean = diagnostics.safe_details(dict(code="invalid_control_tokens", characters=42,
            source="secret document", response="secret response", api_key="secret key",
            exception="invalid message containing document", markers=["<|im_start|>", "secret token"]))
        self.assertEqual(clean, dict(code="invalid_control_tokens", characters=42,
            markers=["<|im_start|>", "unknown"]))
    def test_origin_is_bounded_and_content_free(self):
        clean = diagnostics.safe_details({"origin": "opendataloader.py:87:normalize"})
        self.assertEqual(clean, {"origin": "opendataloader.py:87:normalize"})
        self.assertEqual(diagnostics.safe_details({"origin": "../secret path"}), {})
    def test_rolling_history_and_job_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(diagnostics, "DATA", Path(directory)):
            job = str(uuid.uuid4())
            for i in range(205): diagnostics.record(job, "segment_done", segment=i)
            history = diagnostics.history(job)
            self.assertEqual(len(history), 200)
            self.assertEqual(history[-1]["segment"], 204)
            self.assertEqual(diagnostics.history(str(uuid.uuid4())), [])
            self.assertEqual(diagnostics.path_for(job).stat().st_mode & 0o777, 0o600)
            self.assertEqual(diagnostics.history("../../etc/passwd"), [])
