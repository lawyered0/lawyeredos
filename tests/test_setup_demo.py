from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

def script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class SetupDemoTests(unittest.TestCase):
    def test_fictional_demo_passes_configuration_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination=Path(temporary)/'fictional-demo'
            with patch('sys.argv',['setup_demo.py','--destination',str(destination)]),redirect_stdout(io.StringIO()):
                self.assertEqual(script('setup_demo').main(),0)
            with patch('sys.argv',['validate_setup.py','--config',str(destination/'config.toml')]),redirect_stdout(io.StringIO()):
                self.assertEqual(script('validate_setup').main(),0)
            config=(destination/'config.toml').read_text(encoding='utf-8')
            self.assertIn('[branding]',config)
            self.assertIn('[modules]',config)
            self.assertIn('template_manifest',config)
