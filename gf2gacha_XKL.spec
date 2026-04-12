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

# ==================== 主程序 Analysis ====================
a_main = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[(runtime_dll_path, 'pythonnet/runtime')],
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
        'google.protobuf',
        'google.protobuf.descriptor',
        'google.protobuf.descriptor_pool',
        'google.protobuf.runtime_version',
        'google.protobuf.symbol_database',
        'google.protobuf.internal',
        'google.protobuf.internal.builder',
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

# ==================== 更新器 Analysis ====================
# 更新器是独立的，不需要webview、pythonnet等大型依赖
a_updater = Analysis(
    ['updater.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('version.json', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'webview',
        'pythonnet',
        'clr',
        'clr_loader',
        'mitmproxy',
        'OpenSSL',
        'cryptography',
        'PIL',
        'pygame',
        'numpy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ==================== PYZ ====================
pyz_main = PYZ(a_main.pure, a_main.zipped_data, cipher=block_cipher)
pyz_updater = PYZ(a_updater.pure, a_updater.zipped_data, cipher=block_cipher)

# ==================== 主程序 EXE ====================
exe_main = EXE(
    pyz_main,
    a_main.scripts,
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

# ==================== 更新器 EXE ====================
exe_updater = EXE(
    pyz_updater,
    a_updater.scripts,
    a_updater.binaries,
    a_updater.zipfiles,
    a_updater.datas,
    [],
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 更新器显示控制台，方便查看更新进度
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='favicon.ico',
)

# ==================== COLLECT ====================
# 只收集主程序的内容，更新器已经是独立的单文件exe
coll = COLLECT(
    exe_main,
    a_main.binaries,
    a_main.zipfiles,
    a_main.datas,
    exe_updater,  # 将更新器exe也放入同一目录
    strip=False,
    upx=True,
    upx_exclude=['Python.Runtime.dll'],
    name='gf2gacha_XKL',
)
