# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

# 自动查找 Python.Runtime.dll
try:
    import pythonnet
    pythonnet_dir = os.path.dirname(pythonnet.__file__)
    runtime_dll_path = os.path.join(pythonnet_dir, 'runtime', 'Python.Runtime.dll')
except Exception as e:
    # 如果自动查找失败，可以手动指定
    runtime_dll_path = r"D:\python\Lib\site-packages\pythonnet\runtime\Python.Runtime.dll"
    print(f"自动查找失败，使用手动路径: {runtime_dll_path}")

# 验证 DLL 文件是否存在
if not os.path.exists(runtime_dll_path):
    raise FileNotFoundError(f"找不到 Python.Runtime.dll: {runtime_dll_path}")

print(f"找到 Python.Runtime.dll: {runtime_dll_path}")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[(runtime_dll_path, 'pythonnet/runtime')],  # ← 注意目标目录
    datas=[
        ('backend', 'backend'),
        ('json', 'json'),
        ('frontend/dist', 'frontend/dist'),
        ('version.json', '.'),
    ],
    hiddenimports=[
        'clr',
        'pythonnet',
        'webview.platforms.winforms',
        'clr_loader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='gf2gacha_XKL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='favicon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['Python.Runtime.dll'],  # 排除 UPX 压缩
    name='gf2gacha_XKL',
)
