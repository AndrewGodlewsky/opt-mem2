from .support import CliCase


class MigrationTests(CliCase):
    def setUp(self):
        super().setUp()
        self.cli('init')

    def test_original_optmem_log_import_is_lossless_and_repeatable(self):
        path = self.base / 'LOG.txt'
        lines = ['#0 2026-01-01 First historical decision.', '#1 2026-01-02 Caf\u00e9 tests need UTF-8.']
        path.write_bytes(b''.join(line.encode('utf-8').ljust(319, b' ') + b'\n' for line in lines))
        self.cli('import', str(path))
        before = {p.name: p.read_bytes() for p in self.notes()}
        self.cli('import', str(path))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.notes()})
        self.assertEqual(self.state()['notes'], 2)
        self.assertIn('Caf\u00e9', self.cli('recall', 'UTF-8').stdout)
        self.assertIn('2026-01-01', self.cli('recall', 'historical').stdout)

    def test_invalid_import_writes_nothing(self):
        path = self.base / 'bad.txt'
        path.write_text('2026-01-01 Valid note.\n2026-99-99 Invalid date.\n', encoding='utf-8')
        result = self.cli('import', str(path), code=2)
        self.assertIn('line 2', result.stderr)
        self.assertEqual(self.notes(), [])

    def test_identical_text_at_distinct_positions_remains_distinct(self):
        path = self.base / 'notes.txt'
        path.write_text('2026-01-01 Same fact.\n2026-01-01 Same fact.\n', encoding='utf-8')
        self.cli('import', str(path))
        self.assertEqual(self.state()['notes'], 2)
