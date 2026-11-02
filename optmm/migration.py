"""Repeatable import of dated text and the original OptMem fixed-width log."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import uuid

from .store import MemoryError, Note, atomic_bytes, encoded, read_json, text_line


def import_notes(store, filename):
    source = Path(filename).read_text(encoding='utf-8')
    records = []
    day_counts = {}
    # read_text normalizes CR/LF; Unicode separators may be part of a memory.
    for line_number, line in enumerate(source.split('\n'), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r'(?:#\d+ )?(\d{4}-\d{2}-\d{2}) (.*)', line.rstrip())
        if not match:
            raise MemoryError(f'Import line {line_number}: expected YYYY-MM-DD text, optionally preceded by #N.')
        date, text = match.groups()
        try:
            timestamp = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            text = text_line(text)
        except ValueError as exc:
            raise MemoryError(f'Import line {line_number}: {exc}') from exc
        offset = day_counts.get(date, 0)
        day_counts[date] = offset + 1
        timestamp += timedelta(microseconds=offset)
        identity = uuid.uuid5(uuid.NAMESPACE_URL, f'optmm/import/v1/{len(records)}/{date}/{text}').hex
        records.append(Note(identity, timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), text))
    if not records:
        raise MemoryError('Import file contains no memories.')
    # Validate the complete input and all existing IDs before publishing any note.
    count = 0
    with store.lock():
        for note in records:
            path = store.notes / f'{note.id}.json'
            if path.exists() and read_json(path) != note.record():
                raise MemoryError(f'Imported ID conflicts with an existing note: {note.id}')
        for note in records:
            path = store.notes / f'{note.id}.json'
            if not path.exists():
                atomic_bytes(path, encoded(note.record()))
                count += 1
    return count, len(records) - count
