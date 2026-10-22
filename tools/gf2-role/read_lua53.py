"""Read XOR-FF encoded standard Lua 5.3 bytecode; no code execution."""
import argparse
import json
import struct
from pathlib import Path


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        value = self.data[self.pos:self.pos + n]
        self.pos += n
        if len(value) != n:
            raise ValueError("Unexpected EOF")
        return value

    def num(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        n = self.num('<B')
        if n == 255:
            n = self.num('<Q')
        return self.take(n - 1).decode('utf-8', 'replace') if n else None

    def prototype(self, parent=None):
        source = self.string() or parent
        first, last = self.num('<i'), self.num('<i')
        params, vararg, stack = self.take(3)
        code = [self.num('<I') for _ in range(self.num('<i'))]
        constants = []
        for _ in range(self.num('<i')):
            kind = self.num('<B')
            if kind == 0: value = None
            elif kind == 1: value = bool(self.num('<B'))
            elif kind == 3: value = self.num('<d')
            elif kind == 19: value = self.num('<q')
            elif kind in (4, 20): value = self.string()
            else: raise ValueError(f'Unknown constant tag {kind}')
            constants.append(value)
        upvalues = [list(self.take(2)) for _ in range(self.num('<i'))]
        children = [self.prototype(source) for _ in range(self.num('<i'))]
        lines = [self.num('<i') for _ in range(self.num('<i'))]
        locals_ = [{'name': self.string(), 'start': self.num('<i'), 'end': self.num('<i')} for _ in range(self.num('<i'))]
        names = [self.string() for _ in range(self.num('<i'))]
        return dict(source=source, first=first, last=last, params=params, vararg=vararg, stack=stack,
                    constants=constants, upvalues=upvalues, children=children, lines=lines, locals=locals_, upvalue_names=names,
                    instructions=[{'pc': i, 'line': lines[i] if i < len(lines) else None,
                                   'op': w & 63, 'A': (w >> 6) & 255, 'B': w >> 23,
                                   'C': (w >> 14) & 511, 'Bx': w >> 14, 'sBx': (w >> 14) - 131071}
                                  for i, w in enumerate(code)])


def read(path):
    data = Path(path).read_bytes().translate(bytes.maketrans(bytes(range(256)), bytes(range(255, -1, -1))))
    if data[:12] != b'\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a' or data[12:17] != bytes([4, 8, 4, 8, 8]):
        raise ValueError('Unsupported Lua format')
    r = Reader(data)
    r.take(34)
    result = r.prototype()
    if r.pos != len(data):
        raise ValueError(f'Unconsumed data: {len(data)-r.pos}')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('path')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    result = read(args.path)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Read {result["source"]}, {len(result["children"])} top-level functions')
