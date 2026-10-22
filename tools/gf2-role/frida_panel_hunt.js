/*
 * Locate where the GF2 client keeps the assist detail panel numbers.
 *
 * Phase "recon": report IL2CPP exports, XLua runtime symbols, and whether the
 * property accessor names exist as strings in the process.
 * Phase "scan": search writable memory for reference values (float32/float64/
 * int32) and for the localized panel labels, and report clustered hit counts.
 *
 * Values are supplied by the caller. Hits are candidate locations, not proof.
 */
'use strict';

/* eslint-disable no-unused-vars */
function runPanelHunt(PHASE, VALUES, LABELS, SPECS) {
  const MAX_HITS_PER_PATTERN = 400;
  const HARD_LIMIT_MS = 90000;

function toHex(bytes) {
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    out += bytes[i].toString(16).padStart(2, '0');
  }
  return out;
}

function collectRanges() {
  const ranges = [];
  const found = Process.enumerateRanges({ protection: 'r--', coalesce: true });
  for (const r of found) {
    if (r.size < 16 * 1024) continue;
    if (r.size > 512 * 1024 * 1024) continue;
    ranges.push(r);
  }
  return ranges;
}

function recon() {
  const module = Process.findModuleByName('GameAssembly.dll');
  send({
    kind: 'module',
    name: 'GameAssembly.dll',
    base: module ? module.base.toString() : null,
    size: module ? module.size : null,
  });

  const wanted = ['il2cpp_', 'lua_', 'xlua'];
  for (const prefix of wanted) {
    const names = [];
    for (const mod of Process.enumerateModules()) {
      let exports = [];
      try {
        exports = mod.enumerateExports();
      } catch (e) {
        continue;
      }
      for (const e of exports) {
        if (e.name.indexOf(prefix) !== -1) {
          names.push({ module: mod.name, name: e.name, address: e.address.toString() });
        }
      }
    }
    send({ kind: 'exports', prefix, count: names.length, sample: names.slice(0, 60) });
  }

  const textNeedles = [
    'GetGunPropertyDecimalValueWithPercentByType',
    'GetWeaponDecimalValueByName',
    'GetGunPropertyDecimal',
  ];
  const ranges = collectRanges();
  for (const needle of textNeedles) {
    let total = 0;
    const hits = [];
    for (const range of ranges) {
      try {
        const found = Memory.scanSync(range.base, range.size, toHex(encodeUtf8(needle)));
        total += found.length;
        for (const m of found.slice(0, 5)) {
          hits.push(m.address.toString());
        }
      } catch (e) {
        continue;
      }
      if (total > 40) break;
    }
    send({ kind: 'string', needle, total, sample: hits });
  }
}

function encodeUtf8(text) {
  const bytes = [];
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (code < 0x80) {
      bytes.push(code);
    } else if (code < 0x800) {
      bytes.push(0xC0 | (code >> 6), 0x80 | (code & 0x3F));
    } else if (code < 0x10000) {
      bytes.push(0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F));
    } else {
      bytes.push(
        0xF0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3F),
        0x80 | ((code >> 6) & 0x3F),
        0x80 | (code & 0x3F),
      );
    }
  }
  return bytes;
}

function encodeUtf16le(text) {
  const bytes = [];
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    bytes.push(code & 0xFF, (code >> 8) & 0xFF);
  }
  return bytes;
}

function patternFor(value, kind) {
  let bytes;
  if (kind === 'float32' || kind === 'float64') {
    const buffer = new ArrayBuffer(kind === 'float32' ? 4 : 8);
    const view = new DataView(buffer);
    if (kind === 'float32') view.setFloat32(0, value, true);
    else view.setFloat64(0, value, true);
    bytes = new Uint8Array(buffer);
  } else if (kind === 'int32') {
    bytes = new Uint8Array(4);
    new DataView(bytes.buffer).setInt32(0, value, true);
  } else if (kind === 'int16') {
    bytes = new Uint8Array(2);
    new DataView(bytes.buffer).setInt16(0, value, true);
  } else {
    throw new Error('unknown encoding ' + kind);
  }
  let out = '';
  for (let i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, '0');
  return out;
}

function scanValues() {
  const ranges = collectRanges().filter(r => r.protection.indexOf('w') !== -1);
  send({ kind: 'ranges', count: ranges.length, totalBytes: ranges.reduce((a, r) => a + r.size, 0) });
  const started = Date.now();

  const results = [];
  for (const spec of SPECS) {
    const pattern = patternFor(spec.raw, spec.kind);
    const hits = [];
    for (const range of ranges) {
      if (Date.now() - started > HARD_LIMIT_MS) {
        send({ kind: 'budget', value: spec.value, encoding: spec.kind });
        break;
      }
      try {
        for (const m of Memory.scanSync(range.base, range.size, pattern)) {
          if (hits.length >= MAX_HITS_PER_PATTERN) break;
          hits.push(m.address);
        }
      } catch (e) {
        continue;
      }
      if (hits.length >= MAX_HITS_PER_PATTERN) break;
    }
    results.push({ spec, hits });
    send({
      kind: 'value',
      value: spec.value,
      raw: spec.raw,
      encoding: spec.kind,
      total: hits.length,
      elapsedMs: Date.now() - started,
      addresses: hits.map(a => a.toString()),
    });
  }

  // Clusters where two or more distinct reference values land within 8 KB.
  const clusters = [];
  for (let i = 0; i < results.length; i++) {
    for (let j = i + 1; j < results.length; j++) {
      for (const a of results[i].hits) {
        for (const b of results[j].hits) {
          const delta = a.compare(b) >= 0 ? a.sub(b) : b.sub(a);
          if (delta.toInt32() < 8192) {
            clusters.push({
              valueA: results[i].spec.value,
              valueB: results[j].spec.value,
              addressA: a.toString(),
              addressB: b.toString(),
              distance: delta.toInt32(),
              nearbyAscii: nearbyAscii(a),
            });
          }
        }
      }
    }
  }
  send({ kind: 'clusters', count: clusters.length, clusters: clusters.slice(0, 200) });

  for (const label of LABELS) {
    const pattern = toHex(encodeUtf16le(label));
    const hits = [];
    let total = 0;
    for (const range of ranges) {
      try {
        const found = Memory.scanSync(range.base, range.size, pattern);
        total += found.length;
        for (const m of found.slice(0, 20)) {
          hits.push({
            address: m.address.toString(),
            module: Process.findModuleByAddress(m.address)?.name ?? null,
          });
        }
      } catch (e) {
        continue;
      }
      if (hits.length >= 60) break;
    }
    send({ kind: 'label', label, total, hits });
  }
}

function nearbyAscii(address) {
  try {
    const start = address.sub(0x40);
    const bytes = new Uint8Array(start.readByteArray(0x80));
    let out = '';
    for (let i = 0; i < bytes.length; i++) {
      const c = bytes[i];
      out += (c >= 0x20 && c < 0x7f) ? String.fromCharCode(c) : '.';
    }
    return out;
  } catch (e) {
    return null;
  }
}

  // Defer the scan so script loading returns immediately; the driver waits
  // for the "done" message instead of relying on the RPC load timeout.
  setTimeout(function () {
    try {
      if (PHASE === 'recon') {
        recon();
      } else {
        scanValues();
      }
      send({ kind: 'done', phase: PHASE });
    } catch (e) {
      send({ kind: 'error', message: String(e), stack: e.stack });
    }
  }, 0);
}
