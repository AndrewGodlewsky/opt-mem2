import json
import shutil
from .support import CliCase


class MemoryTests(CliCase):
    def setUp(self):
        super().setUp()
        self.cli('init')

    def task(self, repo=None):
        return json.loads(self.cli('nap', '--json', repo=repo).stdout)['task']

    def settle(self, repo=None):
        while task := self.task(repo):
            self.cli('nap', task['token'], f"Summary for {task['key'][:12]}", repo=repo)

    def test_summary_round_trip_zoom_and_forget(self):
        self.cli('note', 'Payments require idempotency keys.')
        self.cli('note', 'Uploads are limited to 10 MB.')
        self.cli('config', 'WAKE_LINES=1')
        self.assertIn('summaries', self.cli('wake', code=2).stderr)
        task = self.task()
        self.assertIn('Payments', '\n'.join(task['sources']))
        self.cli('nap', task['token'], 'Use idempotency keys; uploads are limited to 10 MB.')
        self.assertIn('Use idempotency', self.cli('wake').stdout)
        self.assertIn('Payments', self.cli('zoom', task['key']).stdout)
        original = {p.name: p.read_bytes() for p in self.notes()}
        self.cli('forget', task['key'])
        self.assertIsNotNone(self.task())
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.notes()})
        self.cli('nap', task['token'], 'An answer offered before forget.', code=2)

    def test_stale_summary_submission_after_new_note(self):
        self.cli('note', 'First fact.')
        self.cli('note', 'Second fact.')
        task = self.task()
        self.cli('note', 'Third fact.')
        result = self.cli('nap', task['token'], 'Old snapshot summary.', code=2)
        self.assertIn('changed', result.stderr)
        self.assertEqual(self.state()['cached_summaries'], 0)

    def test_unchanged_summaries_survive_added_notes(self):
        self.cli('note', 'First fact.')
        self.cli('note', 'Second fact.')
        task = self.task()
        self.cli('nap', task['token'], 'Original pair summary.')
        self.cli('note', 'Third fact.')
        self.assertEqual(self.state()['cached_summaries'], 1)

    def test_branch_insertion_never_reuses_wrong_summary(self):
        self.cli('note', 'Common fact.')
        other = self.base / 'other'
        shutil.copytree(self.repo, other)
        self.cli('note', 'Alice fact.', repo=other)
        self.cli('note', 'Bob fact.')
        task = self.task()
        self.cli('nap', task['token'], 'Common fact and Bob fact.')
        for path in self.notes(other):
            if not (self.repo / '.optmm/notes' / path.name).exists():
                shutil.copyfile(path, self.repo / '.optmm/notes' / path.name)
        self.cli('config', 'WAKE_LINES=2')
        self.assertEqual(self.state()['cached_summaries'], 0)
        self.cli('wake', code=2)
        self.assertIn('Alice fact', self.cli('recall', 'Alice').stdout)

    def test_pagination_rejects_changed_snapshot(self):
        for text in ('one', 'two', 'three'):
            self.cli('note', text)
        self.cli('config', 'PART_LINES=1')
        snapshot = self.state()['snapshot']
        self.assertIn('Not awake yet', self.cli('wake').stdout)
        self.assertIn('two', self.cli('wake', '--page', '2', '--snapshot', snapshot).stdout)
        self.cli('note', 'four')
        self.cli('wake', '--page', '2', '--snapshot', snapshot, code=2)

    def test_invalid_config_does_not_change_settings(self):
        before = (self.repo / '.optmm/config.json').read_bytes()
        for assignment in ('WAKE_LINES=0', 'ENTRY_BYTES=999', 'PART_BYTES=1', 'NOPE=2'):
            self.cli('config', assignment, code=2)
            self.assertEqual(before, (self.repo / '.optmm/config.json').read_bytes())

    def test_pagination_rejects_changed_reading_budget(self):
        for text in ('first', 'second', 'third'):
            self.cli('note', text)
        self.cli('config', 'PART_LINES=1')
        snapshot = self.state()['snapshot']
        self.cli('wake')
        self.cli('config', 'PART_LINES=2')
        self.cli('wake', '--page', '2', '--snapshot', snapshot, code=2)

    def test_forget_invalidates_parent_summaries(self):
        for text in ('one', 'two', 'three', 'four'):
            self.cli('note', text)
        first = self.task()
        self.settle()
        self.assertEqual(self.state()['cached_summaries'], 3)
        self.cli('forget', first['key'])
        self.assertEqual(self.state()['cached_summaries'], 1)
        self.settle()
        self.assertEqual(self.state()['cached_summaries'], 3)

    def test_larger_tree_uses_child_summaries_and_stays_bounded(self):
        for i in range(18):
            self.cli('note', f'Project fact {i}.')
        while task := self.task():
            if len(task['sources']) == 2 and task['sources'][0].startswith('@'):
                break
            self.cli('nap', task['token'], 'Earlier project facts, with details available in originals.')
        self.assertIsNotNone(task)
        self.assertTrue(task['sources'][0].startswith('@'))
        self.cli('nap', task['token'], 'The project history is recorded in the original notes.')
        self.cli('config', 'WAKE_LINES=1')
        self.assertIn('project history', self.cli('wake').stdout)
        self.assertEqual(len(self.notes()), 18)
