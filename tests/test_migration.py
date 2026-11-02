import json
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

    def test_unicode_separators_remain_inside_original_records(self):
        texts = [f'Document says A{separator}2026-01-02 B' for separator in ('\u2028', '\u2029', '\u0085')]
        source = b''.join(f'#{i} 2026-01-01 {text}'.encode('utf-8').ljust(319, b' ') + b'\n'
                          for i, text in enumerate(texts))
        path = self.base / 'LOG.txt'
        path.write_bytes(source)
        self.cli('import', str(path))
        records = sorted((json.loads(p.read_text(encoding='utf-8')) for p in self.notes()),
                         key=lambda record: record['created_at'])
        self.assertEqual([record['text'] for record in records], texts)
        self.assertTrue(all(record['created_at'].startswith('2026-01-01T') for record in records))
        before = {p.name: p.read_bytes() for p in self.notes()}
        self.cli('import', str(path))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.notes()})
        self.assertEqual(path.read_bytes(), source)

    def test_import_preserves_internal_tabs_and_crlf_record_boundaries(self):
        path = self.base / 'LOG.txt'
        source = b'#0 2026-01-01 key\tvalue'.ljust(319, b' ') + b'\r\n2026-01-02 field\tdata\r\n'
        path.write_bytes(source)
        self.cli('import', str(path))
        records = sorted((json.loads(p.read_text(encoding='utf-8')) for p in self.notes()),
                         key=lambda record: record['created_at'])
        self.assertEqual([record['text'] for record in records], ['key\tvalue', 'field\tdata'])
        for record in records:
            self.assertIn(record['text'], self.cli('get', record['id']).stdout)
        self.cli('check')
        before = {p.name: p.read_bytes() for p in self.notes()}
        self.cli('import', str(path))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.notes()})
        self.assertEqual(path.read_bytes(), source)

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
