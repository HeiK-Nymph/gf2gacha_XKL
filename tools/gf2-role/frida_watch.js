/*
 * Watch the pages holding reference values and report which code touches them.
 * Requires the caller to interact with the game while the watch is active.
 * Read-only: memory contents are never modified.
 */
'use strict';

function runWatch(PATTERNS, SECONDS) {
  function patternFor(value, kind) {
    const bytes = new Uint8Array(4);
    const view = new DataView(bytes.buffer);
    if (kind === 'float32') view.setFloat32(0, value, true);
    else view.setInt32(0, value, true);
    return bytes.reduce(function (acc, b) { return acc + b.toString(16).padStart(2, '0'); }, '');
  }

  const ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: true })
    .filter(r => r.size >= 16 * 1024 && r.size <= 512 * 1024 * 1024);
  const watched = new Set();
  const addresses = [];
  for (const spec of PATTERNS) {
    const pattern = patternFor(spec.value, spec.kind);
    for (const range of ranges) {
      try {
        for (const m of Memory.scanSync(range.base, range.size, pattern)) {
          addresses.push({ address: m.address, value: spec.value, kind: spec.kind });
          if (addresses.length > 200) break;
        }
      } catch (e) {
        continue;
      }
      if (addresses.length > 200) break;
    }
  }
  send({ kind: 'watchCandidates', count: addresses.length });

  const monitor = MemoryAccessMonitor;
  const hits = [];
  for (const item of addresses) {
    const page = item.address.and(ptr('0xfffffffffffff000'));
    const key = page.toString();
    if (watched.has(key)) continue;
    watched.add(key);
    try {
      monitor.enable([{ base: page, size: 4096 }], {
        onAccess: function (details) {
          let rip = null;
          try { rip = details.from.toString(); } catch (e) { rip = String(e); }
          hits.push({
            page: key,
            rip,
            operation: details.operation,
            resolvedValue: item.value,
            module: (function () {
              try {
                const m = Process.findModuleByAddress(details.from);
                return m ? { name: m.name, offset: details.from.sub(m.base).toString() } : null;
              } catch (e) {
                return null;
              }
            })(),
          });
          if (hits.length >= 100) {
            send({ kind: 'watchHits', truncated: true, hits });
            monitor.disable();
          }
        },
      });
    } catch (e) {
      continue;
    }
  }
  send({ kind: 'watching', pages: watched.size });

  setTimeout(function () {
    try { monitor.disable(); } catch (e) { /* already disabled */ }
    send({ kind: 'watchHits', truncated: false, hits });
    send({ kind: 'done', phase: 'watch' });
  }, SECONDS * 1000);
}

setTimeout(function () {
  try {
    runWatch(PATTERNS, SECONDS);
  } catch (e) {
    send({ kind: 'error', message: String(e), stack: e.stack });
    send({ kind: 'done', phase: 'watch' });
  }
}, 0);
