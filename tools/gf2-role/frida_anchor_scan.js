/*
 * Locate the assist-panel record: find an anchor float and the nearby defense
 * float, then report every float and ASCII string in a window around it.
 * Read-only.
 */
'use strict';

function runAnchorScan(ANCHOR, SIBLING, WINDOW) {
  function f32hex(value) {
    const bytes = new Uint8Array(4);
    new DataView(bytes.buffer).setFloat32(0, value, true);
    return Array.prototype.map.call(bytes, b => b.toString(16).padStart(2, '0')).join('');
  }

  const ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: true })
    .filter(r => r.size >= 16 * 1024 && r.size <= 512 * 1024 * 1024);
  const anchorPattern = f32hex(ANCHOR);
  const siblingPattern = f32hex(SIBLING);
  const anchors = [];
  for (const range of ranges) {
    try {
      for (const m of Memory.scanSync(range.base, range.size, anchorPattern)) {
        anchors.push(m.address);
        if (anchors.length >= 64) break;
      }
    } catch (e) {
      continue;
    }
    if (anchors.length >= 64) break;
  }
  send({ kind: 'anchors', count: anchors.length, addresses: anchors.map(a => a.toString()) });

  let best = null;
  for (const anchor of anchors) {
    const start = anchor.sub(WINDOW);
    let block;
    try {
      block = start.readByteArray(WINDOW * 2);
    } catch (e) {
      continue;
    }
    const bytes = new Uint8Array(block);
    let hex = '';
    for (let i = 0; i < bytes.length; i++) hex += bytes[i].toString(16).padStart(2, '0');
    const at = hex.indexOf(siblingPattern);
    if (at === -1) continue;
    const siblingOffset = (at / 2) - WINDOW;
    best = { anchor, siblingOffset, block };
    break;
  }

  if (!best) {
    send({ kind: 'noPair' });
    send({ kind: 'done', phase: 'anchor-scan' });
    return;
  }

  const bytes = new Uint8Array(best.block);
  const view = new DataView(bytes.buffer);
  const floats = [];
  for (let off = 0; off + 4 <= bytes.length; off += 4) {
    const value = view.getFloat32(off, true);
    if (Number.isFinite(value) && value !== 0 && Math.abs(value) > 0.0005 && Math.abs(value) < 1e7) {
      floats.push({ offset: off - WINDOW, value: Math.round(value * 10000) / 10000 });
    }
  }
  let ascii = '';
  for (let i = 0; i < bytes.length; i++) {
    const c = bytes[i];
    ascii += (c >= 0x20 && c < 0x7f) ? String.fromCharCode(c) : (c === 0 ? ' ' : '.');
  }
  send({
    kind: 'pair',
    anchor: best.anchor.toString(),
    anchorValue: ANCHOR,
    siblingValue: SIBLING,
    siblingOffset: best.siblingOffset,
    window: WINDOW,
    floats,
    ascii,
  });
  send({ kind: 'done', phase: 'anchor-scan' });
}

setTimeout(function () {
  try {
    runAnchorScan(ANCHOR, SIBLING, WINDOW);
  } catch (e) {
    send({ kind: 'error', message: String(e), stack: e.stack });
    send({ kind: 'done', phase: 'anchor-scan' });
  }
}, 0);
