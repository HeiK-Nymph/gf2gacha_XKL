/*
 * Read a window around each anchor-value hit and report which sibling values
 * appear nearby. Anchor and siblings are caller-supplied; hits are candidates.
 */
'use strict';

function runNeighborhood(ANCHOR, ANCHOR_KIND, SIBLINGS, WINDOW) {
  const MAX_ANCHORS = 60;

  function patternFor(value, kind) {
    const width = kind === 'int16' ? 2 : 4;
    const bytes = new Uint8Array(width);
    const view = new DataView(bytes.buffer);
    if (kind === 'float32') view.setFloat32(0, value, true);
    else if (kind === 'int32') view.setInt32(0, value, true);
    else view.setInt16(0, value, true);
    let out = '';
    for (let i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, '0');
    return out;
  }

  function ranges() {
    return Process.enumerateRanges({ protection: 'rw-', coalesce: true })
      .filter(r => r.size >= 16 * 1024 && r.size <= 512 * 1024 * 1024);
  }

  function locateAnchors() {
    const pattern = patternFor(ANCHOR, ANCHOR_KIND);
    const found = [];
    for (const range of ranges()) {
      try {
        for (const m of Memory.scanSync(range.base, range.size, pattern)) {
          found.push(m.address);
          if (found.length >= MAX_ANCHORS) return found;
        }
      } catch (e) {
        continue;
      }
    }
    return found;
  }

  function nearValues(base) {
    const start = base.sub(WINDOW);
    let block;
    try {
      block = new Uint8Array(start.readByteArray(WINDOW * 2));
    } catch (e) {
      return null;
    }
    const view = new DataView(block.buffer);
    const out = {};
    for (const sibling of SIBLINGS) {
      const hits = [];
      for (const kind of sibling.kinds) {
        const width = kind === 'int16' ? 2 : 4;
        for (let off = 0; off + width <= block.length; off++) {
          if (kind === 'float32' && view.getFloat32(off, true) === sibling.value) {
            hits.push({ kind, offset: off - WINDOW });
          } else if (kind === 'int32' && view.getInt32(off, true) === sibling.value) {
            hits.push({ kind, offset: off - WINDOW });
          } else if (kind === 'int16' && view.getInt16(off, true) === sibling.value) {
            hits.push({ kind, offset: off - WINDOW });
          }
        }
      }
      if (hits.length) out[String(sibling.value)] = hits.slice(0, 12);
    }
    return out;
  }

  function digest(base, radius) {
    let block;
    try {
      block = new Uint8Array(base.sub(radius).readByteArray(radius * 2));
    } catch (e) {
      return null;
    }
    const view = new DataView(block.buffer);
    const floats = [];
    for (let off = 0; off + 4 <= block.length; off += 4) {
      const value = view.getFloat32(off, true);
      if (!Number.isFinite(value) || value === 0 || Math.abs(value) < 0.01 || Math.abs(value) > 1e6) {
        continue;
      }
      floats.push({ offset: off - radius, value: Math.round(value * 10000) / 10000 });
    }
    return floats;
  }

  const anchors = locateAnchors();
  send({ kind: 'anchors', anchor: ANCHOR, kindOfAnchor: ANCHOR_KIND, count: anchors.length });
  const reports = [];
  for (const address of anchors) {
    const siblings = nearValues(address);
    if (!siblings) continue;
    reports.push({ address: address.toString(), siblings });
  }
  send({ kind: 'neighborhood', count: reports.length, reports });

  // Hexdump the most promising anchor: the one with the most sibling matches.
  reports.sort((a, b) => Object.keys(b.siblings).length - Object.keys(a.siblings).length);
  if (reports.length) {
    const best = ptr(reports[0].address);
    try {
      const floats = digest(best, WINDOW) || [];
      send({ kind: 'bestWindow', address: reports[0].address, siblingMatches: reports[0].siblings, floats });
    } catch (e) {
      send({ kind: 'bestWindowError', message: String(e) });
    }
  }
  send({ kind: 'done', phase: 'neighborhood' });
}

// Defer so script loading returns before the memory sweep starts.
setTimeout(function () {
  try {
    runNeighborhood(ANCHOR, ANCHOR_KIND, SIBLINGS, WINDOW);
  } catch (e) {
    send({ kind: 'error', message: String(e), stack: e.stack });
    send({ kind: 'done', phase: 'neighborhood' });
  }
}, 0);
