import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
SCRATCH = SOURCE / '.test-work'


class CliCase(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='case-', dir=SCRATCH)
        self.base = Path(self.temp.name).resolve()
        self.assertEqual(self.base.parent, SCRATCH.resolve())
        self.addCleanup(self.temp.cleanup)
        self.repo = self.base / 'project with spaces'
        self.repo.mkdir()

    def cli(self, *args, code=0, repo=None):
        result = subprocess.run(
            [sys.executable, str(SOURCE / 'memo.py'), '--repo', str(repo or self.repo), *args],
            capture_output=True, text=True, encoding='utf-8',
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=30,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def notes(self, repo=None):
        return sorted((repo or self.repo).glob('.optmm/notes/*.json'))

    def state(self, repo=None):
        return json.loads(self.cli('status', '--json', repo=repo).stdout)

    def git(self, *args, repo=None):
        result = subprocess.run(
            ['git', '-C', str(repo or self.repo), '-c', 'user.name=OptMM Test',
             '-c', 'user.email=optmm@example.invalid', '-c', 'commit.gpgsign=false',
             '-c', 'core.autocrlf=false', '-c', f'core.hooksPath={self.base / "no-hooks"}', *args],
            capture_output=True, text=True, encoding='utf-8', timeout=30,
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout
