# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main5.py'],
    pathex=[],
    binaries=[],
    datas=[
        *collect_data_files('pystray'),
        ('dist', 'dist')
    ],
    hiddenimports=[
        'passlib.handlers.bcrypt', 
        'passlib.handlers.sha2_crypt',
        'win32timezone',  
        'pystray._win32',
        'module.conf',
        'module.api',
        'uvicorn.lifespan.on',
        'uvicorn.protocols.http'
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AutoBangumi',
    debug=False,
    bootloader_ignore_signals=True, 
    strip=False,
    upx=True,  
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  
    icon='app.ico',  
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)