import json
import os
import subprocess
import sys
from .support import CliCase, SOURCE


class InstallTests(CliCase):
    def install(self, *args, code=0):
        result = subprocess.run([sys.executable, str(SOURCE / 'install.py'), str(self.repo), *args],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def installed(self, *args, repo=None, cwd=None):
        root = repo or self.repo
        result = subprocess.run([sys.executable, str(root / 'optmm.py'), *args], cwd=cwd or self.base,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_setup_is_self_contained_and_preserves_instructions(self):
        instructions = self.repo / 'AGENTS.md'
        instructions.write_bytes(b'# Team conventions\r\nKeep this exact line.\r\n')
        self.install()
        self.assertTrue(instructions.read_bytes().startswith(b'# Team conventions\r\nKeep this exact line.\r\n'))
        self.assertTrue((self.repo / 'CLAUDE.md').exists())
        self.assertIn('No memories', self.installed('wake'))
        self.installed('note', 'A shared project decision.')
        note = self.notes()[0]
        before = note.read_bytes()
        self.install()
        self.assertEqual(note.read_bytes(), before)
        self.assertEqual(instructions.read_text().count('<!-- optmm:start -->'), 1)
        self.assertIn('project decision', self.installed('recall', 'decision'))
        self.assertIn('/.optmm/cache/', (self.repo / '.gitignore').read_text())

    def test_existing_unrelated_launcher_is_not_overwritten(self):
        path = self.repo / 'optmm.py'
        path.write_text('print("my application")', encoding='utf-8')
        result = self.install(code=2)
        self.assertIn('Refusing', result.stderr)
        self.assertEqual(path.read_text(), 'print("my application")')
        self.assertFalse((self.repo / '.optmm').exists())

    def test_modified_installed_runtime_is_not_silently_overwritten(self):
        self.install()
        path = self.repo / '.optmm/runtime/optmm/store.py'
        path.write_text(path.read_text() + '\n# local customization\n', encoding='utf-8')
        before = path.read_bytes()
        result = self.install(code=2)
        self.assertIn('modified', result.stderr.lower())
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_manifest_checksums_fail_without_changing_files(self):
        self.install()
        launcher = self.repo / 'optmm.py'
        launcher.write_bytes(launcher.read_bytes() + b'\n# Local customization.\n')
        path = self.repo / '.optmm/install.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        for invalid in ({}, [], None, True, 42, 'short', 'g' * 64):
            with self.subTest(checksum=invalid):
                manifest['files']['optmm.py'] = invalid
                path.write_text(json.dumps(manifest), encoding='utf-8')
                before = {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
                result = self.install(code=2)
                self.assertIn('Invalid installation manifest', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(before, {p.relative_to(self.repo): p.read_bytes()
                                          for p in self.repo.rglob('*') if p.is_file()})

    def test_git_line_ending_conversion_does_not_block_reinstall(self):
        self.install()
        path = self.repo / '.optmm/runtime/optmm/store.py'
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.install()
        self.assertIn('No memories', self.installed('wake'))

    def test_broken_instruction_markers_fail_before_writing(self):
        (self.repo / 'AGENTS.md').write_text('<!-- optmm:start -->\nUnfinished block', encoding='utf-8')
        result = self.install(code=2)
        self.assertIn('markers', result.stderr)
        self.assertFalse((self.repo / 'optmm.py').exists())

    def test_interrupted_write_files_are_excluded_from_git(self):
        self.git('init', '-b', 'main')
        self.install()
        suffix = 'a' * 32 + '.tmp'
        temporary_files = [
            f'.optmm/.config.json.{suffix}', f'.optmm/.install.json.{suffix}',
            f'.optmm/.README.md.{suffix}', f'.optmm/runtime/optmm/.cli.py.{suffix}',
            f'.optmm/notes/.' + 'b' * 32 + f'.json.{suffix}',
            f'.optmm/notes/..gitkeep.{suffix}', f'.optmm.py.{suffix}',
            f'.AGENTS.md.{suffix}', f'.CLAUDE.md.{suffix}', f'..gitignore.{suffix}',
        ]
        for name in temporary_files:
            (self.repo / name).write_bytes(b'Interrupted unpublished write')
        (self.repo / '.unrelated.tmp').write_bytes(b'Unrelated project file')
        self.git('add', '.')
        tracked = set(self.git('ls-files').splitlines())
        self.assertFalse(tracked.intersection(temporary_files))
        self.assertIn('.unrelated.tmp', tracked)
        for name in ('optmm.py', '.optmm/config.json', '.optmm/install.json', '.optmm/runtime/optmm/cli.py'):
            self.assertIn(name, tracked)

    def test_clone_needs_no_installer_or_source_checkout(self):
        self.git('init', '-b', 'main')
        self.install()
        self.installed('note', 'This knowledge travels with Git.')
        self.git('add', '.')
        self.git('commit', '-m', 'Install shared memory')
        tracked = self.git('ls-files')
        self.assertNotIn('.optmm/cache/', tracked)
        clone = self.base / 'clone'
        self.git('clone', str(self.repo), str(clone))
        self.assertFalse((clone / '.optmm/cache').exists())
        self.assertIn('travels with Git', self.installed('wake', repo=clone))
        self.assertTrue((clone / '.optmm/cache').exists())
