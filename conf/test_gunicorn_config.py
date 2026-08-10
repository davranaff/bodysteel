import importlib.util
from pathlib import Path
from unittest import TestCase


MODULE_PATH = Path(__file__).with_name('gunicorn_config.py')


class GunicornConfigTests(TestCase):
    def test_defaults_are_relative_to_the_checked_out_release(self):
        spec = importlib.util.spec_from_file_location('test_gunicorn_config', MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual(module.pythonpath, str(MODULE_PATH.parent.parent))
        self.assertEqual(module.bind, '127.0.0.1:8000')
        self.assertEqual(module.workers, 3)
        self.assertNotIn('/home/bodysteel/apps/', module.command)
