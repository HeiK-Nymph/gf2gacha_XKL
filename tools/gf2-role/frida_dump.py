"""Dump a large memory window from a live process to a local file.

Usage: python frida_dump.py <pid> <address-hex> <bytes> <out-file>
Read-only: the process is only read.
"""

from __future__ import annotations

import sys
from pathlib import Path

import frida


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    pid = int(sys.argv[1])
    address = int(sys.argv[2], 16)
    size = int(sys.argv[3])
    out = Path(sys.argv[4])

    session = frida.attach(pid)
    script = session.create_script(
        """
        rpc.exports = {
          dump: function (address, size) {
            const start = ptr(address);
            const data = start.readByteArray(size);
            return Array.from(new Uint8Array(data));
          }
        };
        """
    )
    script.load()
    data = script.exports_sync.dump(address, size)
    out.write_bytes(bytes(data))
    print(f"wrote {out} {len(data)} bytes")
    session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
