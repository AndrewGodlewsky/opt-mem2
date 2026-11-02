"""Immutable shared notes and atomic local filesystem operations."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid


class MemoryError(ValueError):
    """An actionable input or store error, suitable for CLI output."""


DEFAULTS = {'WAKE_LINES': 96, 'ENTRY_BYTES': 280, 'PART_BYTES': 16000, 'PART_LINES': 120}
ID_RE = re.compile(r'[0-9a-f]{32}')
TIME_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z')
TEMP_NOTE_RE = re.compile(r'\.[0-9a-f]{32}\.json\.[0-9a-f]{32}\.tmp')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def text_line(text, limit=280):
    text = text.strip()
    if not text or any(c != '\t' and (ord(c) < 32 or ord(c) == 127) for c in text):
        raise MemoryError('A memory must be one nonempty line; tabs are the only allowed control characters.')
    if len(text.encode('utf-8')) > limit:
        raise MemoryError(f'Too long: limit is {limit} UTF-8 bytes.')
    return text


def read_json(path):
    if path.is_symlink():
        raise MemoryError(f'Symbolic links are not supported here: {path}')
    if path.stat().st_size > 1024 * 1024:
        raise MemoryError(f'JSON file is unexpectedly large: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def directory(path):
    if path.is_symlink():
        raise MemoryError(f'Symbolic links are not supported here: {path}')
    path.mkdir(parents=True, exist_ok=True)


def atomic_bytes(path, data):
    """Publish a complete file from the same directory (also works on Windows)."""
    if path.is_symlink():
        raise MemoryError(f'Refusing to replace a symbolic link: {path}')
    temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def file_lock(path):
    """Serialize writers in one checkout; Git merges are handled by note identity."""
    if path.is_symlink():
        raise MemoryError(f'Refusing a symbolic link lock: {path}')
    with path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'\0')
                stream.flush()
            deadline = time.monotonic() + 30
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise MemoryError('Another OptMM writer holds the lock; retry shortly.')
                    time.sleep(0.02)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


@dataclass(frozen=True)
class Note:
    id: str
    created_at: str
    text: str

    def record(self):
        return {'schema': 1, 'id': self.id, 'created_at': self.created_at, 'text': self.text}

    @property
    def fingerprint(self):
        return digest(self.record())

    def line(self):
        return f'#{self.id} {self.created_at} {self.text}'


def parse_note(data, filename):
    try:
        if not isinstance(data, dict) or set(data) != {'schema', 'id', 'created_at', 'text'}:
            raise ValueError('expected schema, id, created_at and text')
        if type(data['schema']) is not int or data['schema'] != 1:
            raise ValueError('unsupported schema')
        identity, created, text = data['id'], data['created_at'], data['text']
        if not isinstance(identity, str) or not ID_RE.fullmatch(identity) or filename != identity:
            raise ValueError('filename must match the permanent ID')
        if not isinstance(created, str) or not TIME_RE.fullmatch(created):
            raise ValueError('expected a UTC timestamp with microseconds and Z')
        datetime.strptime(created, '%Y-%m-%dT%H:%M:%S.%fZ')
        if not isinstance(text, str) or text_line(text) != text:
            raise ValueError('invalid note text')
        return Note(identity, created, text)
    except (ValueError, TypeError) as exc:
        raise MemoryError(f'Invalid note {filename}: {exc}') from exc


def validate_config(data):
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1 or set(data) != {'schema', *DEFAULTS}:
        raise MemoryError('Unexpected configuration fields or schema.')
    for key in DEFAULTS:
        if type(data[key]) is not int or data[key] < 1:
            raise MemoryError(f'{key} must be a positive integer.')
    if data['ENTRY_BYTES'] > 280:
        raise MemoryError('ENTRY_BYTES cannot exceed 280.')
    if data['PART_BYTES'] < 1024:
        raise MemoryError('PART_BYTES must be at least 1024.')
    return data


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.data = self.root / '.optmm'
        self.notes = self.data / 'notes'
        self.cache = self.data / 'cache'
        self.config_path = self.data / 'config.json'

    def initialize(self):
        if not self.root.is_dir():
            raise MemoryError(f'Repository directory does not exist: {self.root}')
        directory(self.data)
        directory(self.cache)
        with self.lock():
            directory(self.notes)
            if not self.config_path.exists():
                atomic_bytes(self.config_path, encoded({'schema': 1, **DEFAULTS}))
        self.configuration()

    def require(self):
        if not self.config_path.exists():
            raise MemoryError('OptMM is not initialized here. Run init or install first.')
        for path in (self.data, self.notes):
            if path.is_symlink() or not path.is_dir():
                raise MemoryError(f'Missing or unsafe memory directory: {path}')
        directory(self.cache)
        self.configuration()

    def lock(self):
        return file_lock(self.cache / 'write.lock')

    def configuration(self):
        try:
            return validate_config(read_json(self.config_path))
        except (ValueError, TypeError) as exc:
            raise MemoryError(f'Invalid config {self.config_path}: {exc}') from exc

    def configure(self, assignments):
        with self.lock():
            config = self.configuration()
            for assignment in assignments:
                key, equal, value = assignment.partition('=')
                key = key.upper()
                if not equal or key not in DEFAULTS:
                    raise MemoryError('Use NAME=VALUE, with NAME one of: ' + ', '.join(DEFAULTS))
                try:
                    config[key] = int(value) if value else DEFAULTS[key]
                except ValueError as exc:
                    raise MemoryError(f'{key} must be an integer.') from exc
            validate_config(config)
            if assignments:
                atomic_bytes(self.config_path, encoded(config))
            return config

    def load(self):
        self.require()
        notes = []
        for path in sorted(self.notes.iterdir()):
            if path.name == '.gitkeep' or TEMP_NOTE_RE.fullmatch(path.name):
                continue
            if path.suffix != '.json' or not path.is_file() or path.is_symlink():
                raise MemoryError(f'Unexpected file in notes: {path.name}; resolve it before continuing.')
            try:
                notes.append(parse_note(read_json(path), path.stem))
            except (ValueError, UnicodeError) as exc:
                raise MemoryError(f'Invalid note {path.name}: {exc}. Resolve the file; it was not skipped.') from exc
        return sorted(notes, key=lambda note: (note.created_at, note.id))

    def add(self, text):
        self.require()
        note = Note(uuid.uuid4().hex, datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    text_line(text, self.configuration()['ENTRY_BYTES']))
        with self.lock():
            path = self.notes / f'{note.id}.json'
            if path.exists():
                raise MemoryError('An ID collision occurred; retry the note command.')
            atomic_bytes(path, encoded(note.record()))
        return note
