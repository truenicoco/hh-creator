# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import sys
sys.modules['FixTk'] = None

a = Analysis(['hh-creator.py'],
             pathex=['pyinstaller-win'],
             binaries=[],
             datas=[('..\\hh_creator\\resource', 'resource')],
             hiddenimports=['pkg_resources.py2_warn'],
             hookspath=['.'],
             runtime_hooks=[],
             excludes=['FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='hh-creator',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='hh-creator')
