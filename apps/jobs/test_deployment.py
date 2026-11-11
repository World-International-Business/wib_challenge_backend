from pathlib import Path
import shutil
import subprocess
import unittest

from django.conf import settings
from django.test import SimpleTestCase


@unittest.skipUnless(shutil.which('sh'), 'POSIX shell required')
class EntrypointTests(SimpleTestCase):
    def test_shell_syntax(self):
        result = subprocess.run(
            ['sh', '-n', str(Path(settings.BASE_DIR) / 'entrypoint.sh')],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_command_skips_web_initialization(self):
        result = subprocess.run(
            ['sh', str(Path(settings.BASE_DIR) / 'entrypoint.sh'),
             'sh', '-c', 'printf worker-command'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'worker-command')

    def test_explicit_command_preserves_failure(self):
        result = subprocess.run(
            ['sh', str(Path(settings.BASE_DIR) / 'entrypoint.sh'), 'sh', '-c', 'exit 7'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 7, result.stderr)
