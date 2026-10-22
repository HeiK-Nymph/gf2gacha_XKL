/*
 * Recon for the PC client: XLua/IL2CPP runtime symbols, key method-name
 * strings in memory, and module inventory. Read-only.
 */
'use strict';

function runRecon(NEEDLES) {
  const module = Process.findModuleByName('GameAssembly.dll');
  send({ kind: 'module', name: 'GameAssembly.dll', base: module ? module.base.toString() : null, size: module ? module.size : null });

  const prefixes = ['lua_', 'xlua', 'il2cpp_'];
  for (const prefix of prefixes) {
    const names = [];
    for (const mod of Process.enumerateModules()) {
      for (const e of mod.enumerateExports()) {
        if (e.name.indexOf(prefix) !== -1) {
          names.push({ module: mod.name, name: e.name, address: e.address.toString() });
        }
      }
    }
    send({ kind: 'exports', prefix, count: names.length, sample: names.slice(0, 40) });
  }

  const textNeedles = [
    'GetGunPropertyDecimalValueWithPercentByType',
    'GetWeaponDecimalValueByName',
    'GrpAttributeBaseItemV3',
    'SetGunProp',
    'ChrPartsAtrributeItemV3',
  ];
  for (const needle of NEEDLES) {
    textNeedles.push(needle);
  }
  const ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: true })
    .filter(r => r.size >= 16 * 1024 && r.size <= 512 * 1024 * 1024);
  for (const needle of textNeedles) {
    const pattern = utf8Hex(needle);
    const hits = [];
    let total = 0;
    for (const range of ranges) {
      try {
        const found = Memory.scanSync(range.base, range.size, pattern);
        total += found.length;
        for (const m of found.slice(0, 3)) {
          hits.push({ address: m.address.toString(), module: Process.findModuleByAddress(m.address)?.name ?? null });
        }
      } catch (e) {
        continue;
      }
      if (total > 30) break;
    }
    send({ kind: 'string', needle, total, hits });
  }

  send({
    kind: 'modules',
    list: Process.enumerateModules().map(m => ({ name: m.name, base: m.base.toString(), size: m.size })),
  });
  send({ kind: 'done', phase: 'recon' });
}

function utf8Hex(text) {
  const bytes = [];
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (code < 0x80) bytes.push(code);
    else if (code < 0x800) bytes.push(0xC0 | (code >> 6), 0x80 | (code & 0x3F));
    else if (code < 0x10000) bytes.push(0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F));
    else bytes.push(0xF0 | (code >> 18), 0x80 | ((code >> 12) & 0x3F), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F));
  }
  return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
}

setTimeout(function () {
  try {
    runRecon([]);
  } catch (e) {
    send({ kind: 'error', message: String(e), stack: e.stack });
    send({ kind: 'done', phase: 'recon' });
  }
}, 0);
