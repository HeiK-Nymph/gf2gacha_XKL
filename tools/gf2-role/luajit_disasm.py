"""Minimal LuaJIT 2.1 bytecode disassembler.

Parses a LuaJIT prototype tree out of an .lua bytecode file and prints the
instructions plus the constant table, inline with the source path when the
chunk carries debug info. Intended for reading the client's own panel
calculation code instead of fitting formulas from screenshots.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

BCDUMP_VERSION = 2
BSIZE = 4  # lua_Number is float64, so instruction is 32-bit
FLAGS = {
    0x01: "PROTO_CHILD",
    0x02: "PROTO_VARARG",
    0x04: "PROTO_FFI",
    0x08: "PROTO_NOJIT",
    0x10: "PROTO_ILOOP",
}

# LuaJIT 2.1 opcode names, in opcode order.
OPCODES = [
    "ISLT", "ISGE", "ISLE", "ISGT", "ISEQV", "ISNEV", "ISEQS", "ISNES", "ISEQN",
    "ISNEN", "ISEQP", "ISNEP", "ISTC", "ISFC", "IST", "ISF", "ISTYPE", "ISNUM",
    "MOV", "NOT", "UNM", "LEN", "ADDVN", "SUBVN", "MULVN", "DIVVN", "MODVN",
    "ADDNV", "SUBNV", "MULNV", "DIVNV", "MODNV", "ADDVV", "SUBVV", "MULVV",
    "DIVVV", "MODVV", "POW", "CAT", "KSTR", "KCDATA", "KSHORT", "KNUM", "KPRI",
    "KNIL", "UGET", "USETV", "USETS", "USETN", "USETP", "UCLO", "FNEW", "TNEW",
    "TDUP", "GGET", "GSET", "TGETV", "TGETS", "TGETB", "TSETV", "TSETS",
    "TSETB", "TSETM", "CALLM", "CALL", "CALLMT", "CALLT", "ITERC", "ITERN",
    "VARG", "ISNEXT", "RETM", "RET", "RET0", "RET1", "FORI", "JFORI", "FORL",
    "IFORL", "JFORL", "ITERL", "IITERL", "JITERL", "LOOP", "ILOOP", "JLOOP",
    "JMP", "FUNCF", "IFUNCF", "JFUNCF", "FUNCV", "IFUNCV", "JFUNCV", "FUNCC",
    "FUNCCW",
]


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def byte(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def uleb128(self) -> int:
        result = 0
        shift = 0
        while True:
            byte = self.byte()
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7

    def bytes(self, size: int) -> bytes:
        chunk = self.data[self.pos:self.pos + size]
        self.pos += size
        return chunk

    def string(self) -> str | None:
        length = self.uleb128()
        if length == 0:
            return None
        return self.bytes(length - 1).decode("utf-8", "replace")

    def uint(self) -> int:
        return struct.unpack_from("<I", self.data, self.pos)[0] if False else int.from_bytes(self.bytes(4), "little")


def parse_proto(reader: Reader, depth: int = 0) -> dict | None:
    length = reader.uleb128()
    if length == 0:
        return None
    end = reader.pos + length
    flags = reader.byte()
    numparams = reader.byte()
    framesize = reader.byte()
    numuv = reader.byte()
    numkgc = reader.uleb128()
    numkn = reader.uleb128()
    numbc = reader.uleb128()

    kgc = []
    for _ in range(numkgc):
        kind = reader.uleb128()
        kgc.append(("child" if kind == 0 else "complex", kind))

    knum = []
    for _ in range(numkn):
        raw = reader.bytes(8)
        knum.append(struct.unpack("<d", raw)[0])

    bytecode = [reader.uint() for _ in range(numbc)]

    # child prototypes then debug info
    children = []
    if flags & 0x01:
        while reader.pos < end:
            child = parse_proto(reader, depth + 1)
            if child is None:
                break
            children.append(child)

    firstline = reader.uleb128() if reader.pos < end else 0
    numline = reader.uleb128() if reader.pos < end else 0
    lines = None
    if reader.pos < end:
        size = reader.uleb128()
        payload = reader.bytes(size)
        lines = decode_lines(payload, numline, firstline)

    names = []
    if reader.pos < end and lines is not None:
        namecount = len(lines)
        for _ in range(namecount):
            if reader.pos >= end:
                break
            names.append(reader.string())
    varnames = []
    if reader.pos < end:
        count = reader.uleb128()
        for _ in range(count):
            varnames.append(reader.string())
    reader.pos = end

    return {
        "flags": flags, "numparams": numparams, "framesize": framesize,
        "numuv": numuv, "kgc": kgc, "knum": knum, "bytecode": bytecode,
        "children": children, "firstline": firstline, "numline": numline,
        "lines": lines, "names": names, "varnames": varnames,
    }


def decode_lines(payload: bytes, numline: int, firstline: int) -> list[int] | None:
    if not payload:
        return None
    lines = []
    pos = 0
    line = firstline
    while pos < len(payload) and len(lines) < numline:
        byte = payload[pos]
        pos += 1
        if byte >= 128:
            line = (byte - 128) * 128 + payload[pos]
            pos += 1
        elif byte < 64 and pos < len(payload):
            line += byte + 1 + payload[pos] * 64
            pos += 1
        elif byte >= 64:
            line += (byte - 64) + 1
        else:
            line += 1
        lines.append(line)
    return lines


def decode_const(proto: dict, index: int):
    if index < len(proto["knum"]):
        return f"num[{index}]={proto['knum'][index]:.10g}"
    idx = index - len(proto["knum"])
    if 0 <= idx < len(proto["kgc"]):
        return f"kgc[{idx}]"
    return f"?[{index}]"


def disasm(proto: dict, path: str, reader: Reader, out: list[str], source: str | None, depth: int = 0):
    pad = "  " * depth
    header = f"{pad}function {path} params={proto['numparams']} frame={proto['framesize']} bc={len(proto['bytecode'])}"
    if source:
        header += f"  [{source}]"
    out.append(header)
    if proto["kgc"]:
        out.append(f"{pad}  kgc: {proto['kgc']}")
    if proto["knum"]:
        preview = ", ".join(f"{v:.6g}" for v in proto["knum"][:24])
        out.append(f"{pad}  knum: {preview}")
    for index, word in enumerate(proto["bytecode"]):
        op = word & 0xFF
        name = OPCODES[op] if op < len(OPCODES) else f"OP{op}"
        a = (word >> 8) & 0xFF
        c = (word >> 16) & 0xFF
        b = (word >> 24) & 0xFF
        extra = ""
        if name in ("KSTR", "KCDATA", "KNUM", "KSHORT", "KPRI", "GGET", "GSET",
                    "TGETS", "TSETS", "USETS", "USETN", "USETP", "FNEW", "TDUP",
                    "TNEW", "TSETM", "UGET", "UCLO"):
            extra = f" const={decode_const(proto, c)}"
        line = proto["lines"][index] if proto["lines"] and index < len(proto["lines"]) else "?"
        out.append(f"{pad}  [{index:03d}] line {line}: {name:<7} A={a:<3} B={b:<3} C={c:<3}{extra}")
    for index, child in enumerate(proto["children"]):
        disasm(child, f"{path}.{index}", reader, out, None, depth + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out")
    ap.add_argument("--max-functions", type=int, default=0)
    args = ap.parse_args()

    raw = Path(args.path).read_bytes()
    data = bytes(255 - b for b in raw)
    reader = Reader(data)
    magic = reader.bytes(3)
    version = reader.byte()
    if magic != b"\x1bLJ":
        raise SystemExit(f"not coe260 bytecode: {magic!r}")
    strip = reader.uleb128()
    flags = reader.byte()
    _ = reader.uleb128()  # chunk length
    proto = parse_proto(reader)
    if proto is None:
        raise SystemExit("no top-level prototype")

    lines: list[str] = [f"# file {args.path} version={version} flags={flags:#x} strip={strip}"]
    disasm(proto, "0", reader, lines, Path(args.path).name)
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {len(lines)} lines")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
