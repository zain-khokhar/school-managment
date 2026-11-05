# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[('desktop_app/ui', 'desktop_app/ui')],
    hiddenimports=['xlsxwriter', 'num2words', 'dateutil.relativedelta'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SchoolManagementERP',
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
)
