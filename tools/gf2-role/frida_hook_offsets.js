/*
 * Hook module offsets reported by an access watch and log arguments plus
 * selected return values. Read-only: registers and memory are only read.
 */
'use strict';

function runHookOffsets(MODULE_NAME, OFFSETS, SECONDS) {
  const module = Process.findModuleByName(MODULE_NAME);
  if (!module) {
    send({ kind: 'error', message: 'module not found: ' + MODULE_NAME });
    send({ kind: 'done', phase: 'hook-offsets' });
    return;
  }

  function describe(pointer, depth) {
    try {
      if (pointer.isNull()) return null;
      if (depth > 0) {
        return pointer.readPointer().toString();
      }
      return pointer.toString();
    } catch (e) {
      return '<unreadable>';
    }
  }

  const events = [];
  const listeners = [];
  for (const offset of OFFSETS) {
    const target = module.base.add(offset);
    try {
      const listener = Interceptor.attach(target, {
        onEnter: function (args) {
          this.contextBackup = {
            rcx: this.context.rcx,
            rdx: this.context.rdx,
            r8: this.context.r8,
            r9: this.context.r9,
          };
          if (events.length < 40) {
            events.push({
              offset: offset.toString(),
              phase: 'enter',
              rcx: describe(this.context.rcx, 0),
              rcxValue: describe(this.context.rcx, 1),
              rdx: describe(this.context.rdx, 0),
              r8: describe(this.context.r8, 0),
              r9: describe(this.context.r9, 0),
              stack: (function () {
                try {
                  const values = [];
                  for (let i = 0; i < 4; i++) {
                    values.push(this.context.rsp.add(0x28 + i * 8).readPointer().toString());
                  }
                  return values;
                } catch (e) {
                  return null;
                }
              }).call(this),
            });
          }
        },
        onLeave: function (retval) {
          if (events.length < 40) {
            events.push({
              offset: offset.toString(),
              phase: 'leave',
              retval: retval.toString(),
              retvalFloat: (function () {
                try { return retval.toUInt32(); } catch (e) { return null; }
              })(),
            });
          }
        },
      });
      listeners.push(listener);
    } catch (e) {
      send({ kind: 'hookError', offset: offset.toString(), message: String(e) });
    }
  }
  send({ kind: 'hooked', module: MODULE_NAME, offsets: OFFSETS.map(o => o.toString()) });

  setTimeout(function () {
    for (const listener of listeners) {
      try { listener.detach(); } catch (e) { /* already detached */ }
    }
    send({ kind: 'events', count: events.length, events });
    send({ kind: 'done', phase: 'hook-offsets' });
  }, SECONDS * 1000);
}

setTimeout(function () {
  try {
    runHookOffsets(MODULE_NAME, OFFSETS, SECONDS);
  } catch (e) {
    send({ kind: 'error', message: String(e), stack: e.stack });
    send({ kind: 'done', phase: 'hook-offsets' });
  }
}, 0);
