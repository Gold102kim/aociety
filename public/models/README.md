# Local avatar assets (not distributed)

The source-only GitHub branch intentionally omits `ecy-avatar.glb` and
`ecy-avatar-preview.png`. The current Ecy asset is not established as freely
redistributable. Its local source folder contains CGmodel's notice at
`SourceAssets/Characters/Player_Ecy/注意！模型使用前须知.txt` (GBK text), requiring
written authorization for redistribution. See [the asset register](../../docs/THIRD_PARTY_ASSETS.md).

To restore your existing local development setup, copy the authorized runtime
GLB and matching PNG from your own preserved local project or asset backup into
this directory. Do not fetch or redistribute someone else's copies. If
re-exporting an authorized model, use `tools/blender_avatar_pipeline.py` and
record the original source, applicable license, export version and hashes.
The previous prototype export used Blender 5.2 LTS.

Then run:

```powershell
pnpm test:assets
pnpm check
```

For a fresh source-only checkout without either avatar file, opt in explicitly:

```powershell
$env:ECHO_ALLOW_MISSING_LOCAL_ASSETS = '1'
pnpm check
Remove-Item Env:ECHO_ALLOW_MISSING_LOCAL_ASSETS
```

This mode reports the avatar check as **skipped**, not passed. It is allowed only
when both files are absent. One missing file, a corrupt existing model/preview,
or a missing application icon still fails. A source-only build does not contain
the Ecy model or a complete UE scene and must not be advertised as the complete
game or a license-approved redistributable release.
