# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path, PurePosixPath

block_cipher = None

added_files = [
    ('stskit/mplstyle/dark.mplstyle', 'stskit/mplstyle' ),
    ('stskit/qt/*.ui', 'stskit/qt'),
    ('stskit/qt/*.css', 'stskit/qt'),
    ('stskit/config/*.json', 'stskit/config')
    ]

excluded_files = set([
    'd3dcompiler_47.dll',
    'libcrypto-1_1-x64.dll',
    'libeay32.dll',
    'libEGL.dll',
    'libGLESv2.dll',
    'libssl-1_1-x64.dll',
    'opengl32sw.dll',
    'Qt5Bluetooth.dll',
    'Qt5DBus.dll',
    'Qt5Designer.dll',
    'Qt5Location.dll',
    'Qt5Multimedia.dll',
    'Qt5Network.dll',
    'Qt5Nfc.dll',
    'Qt5OpenGL.dll',
    'Qt5PositioningQuick.dll',
    'Qt5PrintSupport.dll',
    'Qt5Qml.dll',
    'Qt5QmlModels.dll',
    'Qt5QmlWorkerScript.dll',
    'Qt5Quick3DAssetImport.dll',
    'Qt5Quick3D.dll',
    'Qt5Quick3DRender.dll',
    'Qt5Quick3DRuntimeRender.dll',
    'Qt5Quick3DUtils.dll',
    'Qt5QuickControls2.dll',
    'Qt5Quick.dll',
    'Qt5QuickParticles.dll',
    'Qt5QuickTemplates2.dll',
    'Qt5QuickTest.dll',
    'Qt5QuickWidgets.dll',
    'Qt5RemoteObjects.dll',
    'Qt5Sensors.dll',
    'Qt5SerialPort.dll',
    'Qt5Sql.dll',
    'Qt5Svg.dll',
    'Qt5TextToSpeech.dll',
    'Qt5WebChannel.dll',
    'Qt5WebSockets.dll',
    'Qt5WebView.dll',
    'Qt5Xml.dll',
    'Qt5XmlPatterns.dll',
    'ssleay32.dll',
    'QtBluetooth.pyd',
    'QtDBus.pyd',
    'QtDesigner.pyd',
    'QtLocation.pyd',
    'QtMultimedia.pyd',
    'QtMultimediaWidgets.pyd',
    'QtNetwork.pyd',
    'QtNfc.pyd',
    'QtOpenGL.pyd',
    'QtPositioning.pyd',
    'QtPrintSupport.pyd',
    'QtQml.pyd',
    'QtQuick3D.pyd',
    'QtQuick.pyd',
    'QtQuickWidgets.pyd',
    'QtRemoteObjects.pyd',
    'QtSensors.pyd',
    'QtSerialPort.pyd',
    'QtSql.pyd',
    'QtSvg.pyd',
    'QtTextToSpeech.pyd',
    'QtWebChannel.pyd',
    'QtWebSockets.pyd',
    'QtWebView.pyd',
    'QtXml.pyd',
    'QtXmlPatterns.pyd'])

excluded_dirs = [
    'PyQt5/Qt5/qml',
    'PyQt5/Qt5/plugins/audio',
    'PyQt5/Qt5/plugins/bearer',
    'PyQt5/Qt5/plugins/geoservices',
    'PyQt5/Qt5/plugins/mediaservice',
    'PyQt5/Qt5/plugins/playlistformats',
    'PyQt5/Qt5/plugins/printsupport',
    'PyQt5/Qt5/plugins/sensorgestures',
    'PyQt5/Qt5/plugins/sensors',
    'PyQt5/Qt5/plugins/sqldrivers',
    'PyQt5/Qt5/translations',
    'PyQt5/uic/widget-plugins'
    ]

a = Analysis(
    ['stscharts.py'],
    pathex=[],
    binaries=[],
    datas = added_files,
    hiddenimports=[],
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

def is_excluded(item):
    p = Path(item[0])
    if p.name in excluded_files:
        print("exclude", p)
        return True
    for dir in excluded_dirs:
        q = PurePosixPath(dir)
        if p.is_relative_to(q):
            print("exclude", p)
            return True
    return False

a.binaries = TOC([x for x in a.binaries if not is_excluded(x)])
a.datas = TOC([x for x in a.datas if not is_excluded(x)])

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stscharts',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stscharts',
)
