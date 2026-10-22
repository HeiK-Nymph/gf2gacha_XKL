/*
 * Dump every float32/float64/int32 in a window around a given address, so a
 * candidate object can be inspected offline. Read-only.
 */
'use strict';

function runReadWindow(ADDRESS, RADIUS) {
  const base = ptr(ADDRESS);
  let block;
  try {
    block = new Uint8Array(base.sub(RADIUS).readByteArray(RADIUS * 2));
  } catch (e) {
    send({ kind: 'error', message: String(e) });
    send({ kind: 'done', phase: 'read-window' });
    return;
  }
  const view = new DataView(block.buffer);
  const floats = [];
  for (let off = 0; off + 4 <= block.length; off += 4) {
    const f = view.getFloat32(off, true);
    if (Number.isFinite(f) && f !== 0 && Math.abs(f) > 0.01 && Math.abs(f) < 1e7) {
      floats.push({ offset: off - RADIUS, value: Math.round(f * 10000) / 10000 });
    }
  }
  const ints = [];
  for (let off = 0; off + 4 <= block.length; off += 4) {
    const v = view.getInt32(off, true);
    if (v > 40 && v < 10_000_000) ints.push({ offset: off - RADIUS, value: v });
  }
  send({ kind: 'window', address: ADDRESS, radius: RADIUS, floats, ints });
  send({ kind: 'done', phase: 'read-window' });
}

setTimeout(function () {
  try {
    runReadWindow(ADDRESS, RADIUS);
  } catch (e) {
    send({ kind: 'error', message: String(e) });
    send({ kind: 'done', phase: 'read-window' });
  }
}, 0);
