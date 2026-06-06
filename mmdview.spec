# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['backend/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backend/templates', 'backend/templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'backend.apple_events',
        'backend.routers.html',
        'backend.routers.events',
        'backend.services.event_bus',
        'backend.services.watch_service',
        'backend.paths',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mmdview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='mmdview',
)

app = BUNDLE(
    coll,
    name='mmdview.app',
    icon='static/icons/icon.icns',
    bundle_identifier='com.degino.mmdview',
    info_plist={
        'NSHighResolutionCapable': True,
        "CFBundleShortVersionString": "0.2.15",
        'UTExportedTypeDeclarations': [
            {
                'UTTypeIdentifier': 'com.degino.mmdview.mermaid-diagram',
                'UTTypeDescription': 'Mermaid Diagram',
                'UTTypeConformsTo': ['public.plain-text'],
                'UTTypeTagSpecification': {
                    'public.filename-extension': ['mmd', 'mermaid'],
                },
            }
        ],
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Mermaid Diagram',
                'CFBundleTypeExtensions': ['mmd', 'mermaid'],
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Owner',
                'LSItemContentTypes': ['com.degino.mmdview.mermaid-diagram'],
            },
            {
                # .mmd files resolve to net.ia.markdown (MindNode) on some systems.
                # Alternate rank avoids stealing default from markdown editors.
                'CFBundleTypeName': 'Mermaid Diagram',
                'CFBundleTypeExtensions': ['mmd', 'mermaid'],
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['net.ia.markdown'],
            },
        ],
    },
)
