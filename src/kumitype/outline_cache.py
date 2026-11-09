"""Content-keyed quadratic outline cache, using data rather than executable objects."""
import base64
import hashlib
import json
from pathlib import Path

from fontTools import version
from fontTools.ttLib.tables._g_l_y_f import Glyph

from .artifacts import write_text


class OutlineCache:
    def __init__(self, identity, root=Path('cache/outlines')):
        key = hashlib.sha256(json.dumps([4, version, identity], sort_keys=True).encode()).hexdigest()
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / (key + '.json')
        self.entries = {}
        self.dirty = False
        if self.path.exists():
            try:
                envelope = json.loads(self.path.read_text())
                payload = envelope['payload']
                if hashlib.sha256(payload.encode()).hexdigest() == envelope['sha256']:
                    self.entries = json.loads(payload)
            except (ValueError, KeyError, TypeError):
                pass

    def get(self, codepoint):
        entry = self.entries.get(str(codepoint))
        if entry is None:
            return None
        glyph = Glyph(base64.b64decode(entry['glyph'], validate=True))
        return glyph, entry['lsb'], entry['overflow'], entry['fitted']

    def put(self, codepoint, glyph, lsb, overflow, fitted):
        self.entries[str(codepoint)] = {'glyph': base64.b64encode(glyph.compile(None)).decode(),
                                       'lsb': lsb, 'overflow': overflow, 'fitted': fitted}
        self.dirty = True

    def save(self):
        if self.dirty:
            payload = json.dumps(self.entries, sort_keys=True, separators=(',', ':'))
            write_text(self.path, json.dumps({'payload': payload,
                       'sha256': hashlib.sha256(payload.encode()).hexdigest()}))
