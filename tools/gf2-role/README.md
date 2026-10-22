# GF2 role-panel investigation toolkit (offline + Frida)

## Fixed findings (2026-10-17)

* The assist snapshot response (command 10429) does not carry the displayed
  panel numbers. A full recursive scan of the complete response for
  attack/defense/crit/crit-damage in float32, float64, int32/int16 at
  scale 1/10/100/1000/10000, and in wire-level fixed fields, finds nothing.
* The client holds those numbers in memory as exact float32 values
  (3206.0/1336.0 reproduce reliably), but no single nearby object contains
  the whole panel; surrounding memory is a progression table, not the record.
* The only Lua module that references the panel accessor is
  UIChrAttributeDetailsDialogV3.lua (file 1888036FF34955641A2938EEDC8AE712,
  XOR 0xFF), calling GetGunPropertyDecimalValueWithPercentByType with
  AttributeShowType = 24.
* That method name does not exist as a literal in global-metadata.dat, the
  managed assemblies, or the live process (UTF-8 or UTF-16). Name-based
  IL2CPP or Lua binding hooks are therefore unavailable.

## Toolkit

* wire.py               frame + protobuf reader for the game TCP protocol
* assist_snapshot.py    decode a 10429 response into role/snapshot records
* panel_scan.py         multi-encoding scan of a snapshot for panel values
* assist_probe.py       replay a captured login and issue one read-only query
* frida_run.py          attach, load a probe, collect messages
* frida_panel_hunt.js   IL2CPP/XLua recon and bulk value scan
* frida_neighborhood.js anchor + sibling window scan
* frida_anchor_scan.js  locate an anchor and dump floats/ascii in a window
* frida_read_window.js  dump floats/ints around one address
* frida_recon.js        module and string recon
* frida_watch_rip.js    page-access watch reporting the touching code
* frida_dump.py         raw memory dump helper
* reflect/              .NET metadata dumper for StaticTable.dll

## Usage examples

    python tools/gf2-role/panel_scan.py --server-stream <stream.bin>
    python tools/gf2-role/frida_run.py --pid <pid> --phase scan \
        --values 3206 1336 59.4 161.8 --encodings float32
    python tools/gf2-role/frida_run.py --pid <pid> --neighborhood \
        --values 3206 1336 --window 4096
"""
