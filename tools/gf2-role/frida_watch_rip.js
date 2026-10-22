/*
 * Find a float32 anchor value, arm a page-access watch, and report the code
 * addresses that read those pages while the caller refreshes the panel.
 * Read-only: memory contents are never modified.
 */
'use strict';

function runWatchRip(VALUE, SECONDS) {
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setFloat32(0, VALUE, true);
  const pattern = Array.prototype.map.call(bytes, b => b.toString(16).padStart(2, '0')).join('');

  const ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: true })
    .filter(r => r.size >= 16 * 1024 && r.size <= 512 * 1024 * 1024);
  const pages = [];
  for (const range of ranges) {
    try {
      for (const m of Memory.scanSync(range.base, range.size, pattern)) {
        const page = m.address.and(ptr('0xfffffffffffff000'));
        if (!pages.some(p => p.equals(page))) pages.push(page);
        if (pages.length >= 24) break;
      }
    } catch (e) {
      continue;
    }
    if (pages.length >= 24) break;
  }
  send({ kind: 'anchors', value: VALUE, pages: pages.map(p => p.toString()) });

  const seen = new Set();
  const hits = [];
  try {
    MemoryAccessMonitor.enable(pages.map(p => ({ base: p, size: 4096 })), {
      onAccess: function (details) {
        let from = null;
        let module = null;
        try {
          from = details.from.toString();
          const m = Process.findModuleByAddress(details.from);
          module = m ? { name: m.name, offset: details.from.sub(m.base).toString() } : null;
        } catch (e) {
          from = String(e);
        }
        const key = from + '|' + details.operation;
        if (seen.has(key)) return;
        seen.add(key);
        hits.push({
          page: details.address.toString(),
          from,
          operation: details.operation,
          module,
          instruction: (function () {
            try { return Instruction.parse(details.from).toString(); } catch (e) { return null; }
          })(),
          backtrace: (function () {
            try {
              return Thread.backtrace(details.context, Backtracer.ACCURATE)
                .slice(0, 6)
                .map(a => {
                  const m = Process.findModuleByAddress(a);
                  return m ? m.name + '+' + a.sub(m.base).toString() : a.toString();
                });
            } catch (e) {
              return null;
            }
          })(),
        });
        if (hits.length >= 60) {
          send({ kind: 'accessHits', truncated: true, hits });
          MemoryAccessMonitor.disable();
        }
      },
    });
  } catch (e) {
    send({ kind: 'error', message: 'enable failed: ' + String(e) });
    send({ kind: 'done', phase: 'watch-rip' });
    return;
  }
  send({ kind: 'armed', pages: pages.length, seconds: SECONDS });

  setTimeout(function () {
    try { MemoryAccessMonitor.disable(); } catch (e) { /* already disabled */ }
    send({ kind: 'accessHits', truncated: false, hits });
    send({ kind: 'done', phase: 'watch-rip' });
  }, SECONDS * 1000);
}

setTimeout(function () {
  try {
    runWatchRip(ANCHOR_VALUE, SECONDS);
  } catch (e) {
    send({ kind: 'error', message: String(e), stack: e.stack });
    send({ kind: 'done', phase: 'watch-rip' });
  }
}, 0);
