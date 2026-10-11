import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from urllib.error import HTTPError
from app import remote_ai
from app.diagnostics import InferenceError

class ModelLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.key=self.root/'key';self.key.write_text('private-key');self.key.chmod(0o600)
        self.value=dict(base_url='http://192.168.6.22:8888/v1',key_file=str(self.key),model=remote_ai.DEFAULT_MODEL,
                        auto_load=True,context_length=4096)
        self.ready=dict(active_model=remote_ai.DEFAULT_MODEL,model_identifier=remote_ai.DEFAULT_MODEL,
                        gguf_variant='Q4_K_M',context_length=4096,loaded=[remote_ai.DEFAULT_MODEL],loading=[])
        self.opener=MagicMock();self.requests=[];self.replies=[]
        def open_response(req,**kw):
            self.requests.append(req)
            reply=self.replies.pop(0)
            if isinstance(reply,Exception):raise reply
            response=MagicMock();response.__enter__.return_value=response
            response.read.return_value=json.dumps(reply).encode();return response
        self.opener.open.side_effect=open_response
        for target,value in [('DATA',self.root),('CONFIG',self.root/'remote-ai.json')]:
            p=patch.object(remote_ai,target,value);p.start();self.addCleanup(p.stop)
        p=patch('urllib.request.build_opener',return_value=self.opener);p.start();self.addCleanup(p.stop)

    def paths(self):return [r.full_url.removeprefix('http://192.168.6.22:8888') for r in self.requests]

    def test_switch_unloads_images_and_old_text_before_loading(self):
        self.replies=[dict(active_model='other',loaded=['other']),dict(loaded=False),{},dict(status='loaded'),self.ready]
        remote_ai.ensure_model(self.value)
        self.assertEqual(self.paths(),['/api/inference/status','/api/inference/images/unload','/api/inference/unload','/api/inference/load','/api/inference/status'])
        body=json.loads(self.requests[3].data)
        self.assertEqual(body['gguf_variant'],'Q4_K_M');self.assertEqual(body['max_seq_length'],4096)
        self.assertTrue(json.loads(self.requests[2].data)['force_cancel_active'])
        self.assertTrue(all(r.get_header('Authorization')=='Bearer private-key' for r in self.requests))

    def test_ready_model_does_not_reload(self):
        self.replies=[self.ready,dict(loaded=False)]
        remote_ai.ensure_model(self.value)
        self.assertNotIn('/api/inference/load',self.paths())

    def test_context_change_requires_reload(self):
        self.replies=[dict(self.ready,context_length=2048),dict(loaded=False),{},dict(status='loaded'),self.ready]
        remote_ai.ensure_model(self.value)
        self.assertIn('/api/inference/load',self.paths())

    def test_reduced_or_wrong_context_is_refused(self):
        self.replies=[dict(active_model=None,loaded=[]),dict(loaded=False),dict(status='loaded'),dict(self.ready,context_length=2048)]
        with self.assertRaises(InferenceError) as failure:remote_ai.ensure_model(self.value)
        self.assertEqual(failure.exception.diagnostic['code'],'remote_model_settings')

    def test_control_auth_failure_does_not_start_loading(self):
        self.replies=[HTTPError('private',403,'Forbidden',{},None)]
        with self.assertRaises(InferenceError) as failure:remote_ai.ensure_model(self.value)
        self.assertEqual(failure.exception.diagnostic['code'],'remote_control_auth')
        self.assertNotIn('private-key',str(failure.exception))
        self.assertEqual(len(self.requests),1)

    def test_image_unload_failure_does_not_load_alongside(self):
        self.replies=[dict(active_model=None,loaded=[]),dict(loaded=True)]
        with self.assertRaises(InferenceError):remote_ai.ensure_model(self.value)
        self.assertNotIn('/api/inference/load',self.paths())

    def test_disabled_switch_leaves_server_alone(self):
        remote_ai.ensure_model(dict(self.value,auto_load=False))
        self.assertFalse(self.requests)

    def test_context_is_validated_and_saved_privately(self):
        for value in (True,0,32769,'4096'):
            with self.assertRaises(ValueError):remote_ai.loading_options(dict(context_length=value))
        remote_ai.save_loading_options(8192,True)
        value=json.loads(remote_ai.CONFIG.read_text())
        self.assertEqual(value['context_length'],8192)
        self.assertEqual(remote_ai.CONFIG.stat().st_mode & 0o777,0o600)
        self.assertEqual(value['model'],remote_ai.DEFAULT_MODEL)

if __name__=='__main__':unittest.main()
