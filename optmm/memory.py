"""Snapshot-bound navigation and content-addressed, agent-written summaries."""
from dataclasses import dataclass
import re
import uuid

from .store import MemoryError, atomic_bytes, digest, directory, encoded, read_json, text_line


KEY_RE = re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True)
class Node:
    lo: int
    hi: int
    key: str
    left: object = None
    right: object = None

    @property
    def leaf(self):
        return self.hi - self.lo == 1


class History:
    def __init__(self, store):
        self.store = store
        self.notes = store.load()
        self.config = store.configuration()
        self.snapshot = digest({'history': 1, 'notes': [n.fingerprint for n in self.notes],
                                'config': self.config, 'revision': self.revision()})
        self.nodes = {}
        self.root = self._build(0, len(self.notes)) if self.notes else None
        self.summaries = store.cache / 'summaries'
        directory(self.summaries)
        self._cached = {}

    def _build(self, lo, hi):
        if hi - lo == 1:
            return Node(lo, hi, self.notes[lo].fingerprint)
        # A complete left subtree preserves old groups as new notes arrive.
        split = lo + (1 << ((hi - lo - 1).bit_length() - 1))
        left, right = self._build(lo, split), self._build(split, hi)
        key = digest({'tree': 1, 'left': left.key, 'right': right.key})
        node = Node(lo, hi, key, left, right)
        self.nodes[key] = node
        return node

    def summary(self, node):
        if node.key not in self._cached:
            value = None
            try:
                data = read_json(self.summaries / f'{node.key}.json')
                if (isinstance(data, dict) and data.get('schema') == 1 and data.get('key') == node.key
                        and data.get('children') == [node.left.key, node.right.key]
                        and isinstance(data.get('text'), str)):
                    value = text_line(data['text'])
            except (FileNotFoundError, ValueError, UnicodeError):
                pass
            self._cached[node.key] = value
        return self._cached[node.key]

    def pending(self):
        return [node for node in sorted(self.nodes.values(), key=lambda n: (n.hi - n.lo, n.lo))
                if self.summary(node) is None]

    def cover(self):
        if self.root is None:
            return []
        result = [self.root]
        while len(result) < self.config['WAKE_LINES']:
            index = next((i for i in range(len(result) - 1, -1, -1) if not result[i].leaf), None)
            if index is None:
                break
            node = result[index]
            result[index:index + 1] = [node.left, node.right]
        return result

    def line(self, node):
        if node.leaf:
            return self.notes[node.lo].line()
        text = self.summary(node)
        return f'@{node.key} [{node.hi - node.lo} notes] {text or "summary pending"}'

    def revision(self):
        path = self.store.cache / 'revision'
        if path.is_symlink():
            raise MemoryError('Unsafe cache revision file.')
        return path.read_text(encoding='utf-8') if path.exists() else ''

    def task(self, node=None):
        if node is None:
            pending = self.pending()
            if not pending:
                return None
            node = pending[0]
        if node.hi - node.lo <= 16:
            sources = [n.line() for n in self.notes[node.lo:node.hi]]
        else:
            sources = []
            for child in (node.left, node.right):
                if not child.leaf and self.summary(child) is None:
                    raise MemoryError('Child summaries are pending. Run nap for the next task.')
                sources.append(self.line(child))
        inputs = digest({'sources': sources, 'revision': self.revision(), 'limit': self.config['ENTRY_BYTES']})
        return {'key': node.key, 'token': f'{self.snapshot}:{node.key}:{inputs}',
                'sources': sources, 'limit': self.config['ENTRY_BYTES'],
                'instruction': 'Summarize the lasting facts in one line. Preserve uncertainty and contradictions. Invent nothing.'}

    def submit(self, token, text):
        parts = token.split(':')
        if len(parts) != 3 or not all(KEY_RE.fullmatch(p) for p in parts):
            raise MemoryError('Invalid summary token; copy the token from nap.')
        with self.store.lock():
            current = History(self.store)
            if parts[0] != current.snapshot:
                raise MemoryError('Memory history changed. Run nap again; this summary was not saved.')
            node = current.nodes.get(parts[1])
            if node is None or current.task(node)['token'] != token:
                raise MemoryError('Summary inputs changed. Run nap again; this summary was not saved.')
            text = text_line(text, current.config['ENTRY_BYTES'])
            if current.summary(node) is not None:
                return False
            atomic_bytes(current.summaries / f'{node.key}.json', encoded({
                'schema': 1, 'key': node.key, 'children': [node.left.key, node.right.key], 'text': text,
            }))
            return True

    def resolve(self, prefix):
        prefix = prefix.lstrip('@')
        hits = [node for key, node in self.nodes.items() if key.startswith(prefix)] if len(prefix) >= 8 else []
        if len(hits) != 1:
            raise MemoryError('Summary ID is missing or ambiguous in this branch. Copy an @ID from wake or nap.')
        return hits[0]

    def forget(self, prefix):
        with self.store.lock():
            current = History(self.store)
            key = current.resolve(prefix).key if prefix != 'all' else None
            records = {}
            for path in current.summaries.glob('*.json'):
                if not KEY_RE.fullmatch(path.stem) or path.is_symlink():
                    continue
                try:
                    data = read_json(path)
                    children = data.get('children') if isinstance(data, dict) else None
                    records[path.stem] = children if isinstance(children, list) else []
                except (ValueError, UnicodeError):
                    records[path.stem] = []
            removed = set(records) if key is None else {key}
            while True:
                parents = {k for k, children in records.items() if any(c in removed for c in children if isinstance(c, str))}
                if parents <= removed:
                    break
                removed.update(parents)
            count = 0
            for identity in removed:
                path = current.summaries / f'{identity}.json'
                if path.exists():
                    path.unlink()
                    count += 1
            atomic_bytes(self.store.cache / 'revision', uuid.uuid4().hex.encode('ascii'))
            return count


def pages(lines, config):
    result, page, size = [], [], 0
    for line in lines:
        length = len(line.encode('utf-8')) + 1
        if page and (len(page) >= config['PART_LINES'] or size + length > config['PART_BYTES']):
            result.append(page)
            page, size = [], 0
        page.append(line)
        size += length
    if page:
        result.append(page)
    return result or [[]]
