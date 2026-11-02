import json
from .support import CliCase


class NotesTests(CliCase):
    def test_initialization_notes_recall_and_ids(self):
        self.cli('init')
        self.assertIn('No memories', self.cli('wake').stdout)
        self.cli('note', 'Payments require idempotency keys.')
        first = self.notes()[0]
        before = first.read_bytes()
        note = json.loads(before)
        self.assertEqual(first.stem, note['id'])
        self.assertRegex(note['id'], r'^[0-9a-f]{32}$')
        self.cli('note', 'Uploads are limited to 10 MB.')
        self.cli('init')
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(len(self.notes()), 2)
        self.assertIn(note['id'], self.cli('recall', 'PAYMENTS').stdout)
        self.assertIn('idempotency', self.cli('get', note['id']).stdout)
        self.assertEqual(self.state()['notes'], 2)
        self.cli('check')

    def test_invalid_notes_do_not_write(self):
        self.cli('init')
        for bad in ('', 'two\nlines', 'two\rlines', 'escape\x1bsequence', 'delete\x7fcharacter',
                    'vertical\vtab', 'form\ffeed', 'x' * 281, '\u00e9' * 141):
            self.cli('note', bad, code=2)
        self.assertEqual(self.notes(), [])

    def test_malformed_shared_note_stops_reads(self):
        self.cli('init')
        self.cli('note', 'A valid memory.')
        self.notes()[0].write_text('<<<<<<< merge conflict', encoding='utf-8')
        result = self.cli('wake', code=2)
        self.assertIn('Invalid note', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_hidden_malformed_note_is_not_silently_omitted(self):
        self.cli('init')
        (self.repo / '.optmm/notes/.damaged.json').write_text('<<<<<<< conflict', encoding='utf-8')
        result = self.cli('check', code=2)
        self.assertIn('Invalid note', result.stderr)

    def test_interrupted_unpublished_note_is_ignored(self):
        self.cli('init')
        path = self.repo / '.optmm/notes' / ('.' + 'a' * 32 + '.json.' + 'b' * 32 + '.tmp')
        path.write_bytes(b'{partial JSON')
        self.cli('check')
        self.assertEqual(self.state()['notes'], 0)
