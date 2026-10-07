import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

class RuntimeConfigurationTests(unittest.TestCase):
    def test_default_port_stays_compatible(self):
        with patch.dict(os.environ, {}, clear=True):
            config=runpy.run_path(str(Path(__file__).parents[1]/'app/config.py'))
        self.assertEqual(config['RUNTIME_URL'],'http://127.0.0.1:8091')

    def test_oneforall_can_use_an_isolated_port(self):
        with patch.dict(os.environ, {'RUNTIME_URL':'http://127.0.0.1:18112'}, clear=True):
            config=runpy.run_path(str(Path(__file__).parents[1]/'app/config.py'))
        self.assertEqual(config['RUNTIME_URL'],'http://127.0.0.1:18112')

if __name__=='__main__': unittest.main()
