import json
import os
import subprocess
import sys
from .support import SOURCE, CliCase


class GitWorkflowTests(CliCase):
    def setUp(self):
        super().setUp()
        self.git('init', '-b', 'main')
        self.cli('install', str(self.repo))

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-m', message)

    def test_parallel_branches_merge_without_memory_conflicts(self):
        self.cli('note', 'Common starting knowledge.')
        self.commit('Common history')
        common = self.git('rev-parse', 'HEAD').strip()
        self.git('switch', '-c', 'alice')
        self.cli('note', 'Alice discovered the payment retry issue.')
        alice_records = {p.name: p.read_bytes() for p in self.notes()}
        self.commit('Alice notes')
        self.git('switch', '-c', 'bob', common)
        self.cli('note', 'Bob discovered the upload limit.')
        bob_task = json.loads(self.cli('nap', '--json').stdout)['task']
        self.cli('nap', bob_task['token'], 'Common knowledge and the upload limit.')
        self.commit('Bob notes')
        self.git('switch', 'main')
        self.git('merge', '--no-edit', 'alice')
        self.git('merge', '--no-edit', 'bob')
        self.assertEqual(self.state()['notes'], 3)
        self.assertEqual(self.state()['cached_summaries'], 0)
        self.assertIn('Alice', self.cli('recall', 'Alice').stdout)
        self.assertIn('Bob', self.cli('recall', 'Bob').stdout)
        for filename, data in alice_records.items():
            self.assertEqual((self.repo / '.optmm/notes' / filename).read_bytes(), data)
        self.cli('check')
        self.assertEqual(self.git('status', '--porcelain').strip(), '')
        self.git('switch', 'bob')
        self.assertEqual(self.state()['notes'], 2)
        self.assertEqual(self.state()['cached_summaries'], 1)
        self.assertIn('No match', self.cli('recall', 'Alice').stdout)

    def test_concurrent_writers_preserve_all_unique_notes(self):
        processes = [subprocess.Popen(
            [sys.executable, str(SOURCE / 'memo.py'), '--repo', str(self.repo), 'note', f'Parallel fact {i}.'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
        ) for i in range(16)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(self.state()['notes'], 16)
        ids = [json.loads(p.read_text())['id'] for p in self.notes()]
        self.assertEqual(len(set(ids)), 16)
        self.cli('check')
