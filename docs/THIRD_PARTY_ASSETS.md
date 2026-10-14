# Third-party asset register and source-only distribution

Review date: 2026-10-14. This is an evidence register, not a legal clearance or
a replacement for the applicable license. The user chose to upload code and
redistributable resources only. Unverified/restricted binaries stay local.

## Identified local assets

| Asset | Evidence and origin | Distribution decision |
| --- | --- | --- |
| Ecy player/avatar | `SourceAssets/Characters/Player_Ecy/注意！模型使用前须知.txt` (GBK), supplied CGmodel material notice; `模型链接_768823.url` records the local model link. The notice says the original author retains copyright and written permission is required for redistribution. | Do not upload the original model, textures, exports, runtime GLB/preview or UE derivatives without documented permission. A purchase or a private repository does not itself establish redistribution permission. |
| Alicia Solid / Alicia Sakura | Embedded VRM 0.x metadata in `SourceAssets/Characters/NPC_Cute/AliciaSolid.vrm` and `AliciaSakura.vrm`: `© DWANGO Co., Ltd.`, model version `1.10`, commercial-use flag `Allow`, license `Other`, [model-specific rules](https://3d.nicovideo.jp/alicia/rule.html). The rules URL could not be retrieved during this review. | The commercial-use metadata alone is not proof of redistribution permission. Original VRM and modified textures/FBX/UE models remain local pending review of the full model-specific rules. |
| Seed-san | `SourceAssets/Characters/NPC_Cute/Seed-san.vrm` embedded VRM 1.0 metadata: `VirtualCast, Inc.`, `allowRedistribution=true`, `modification=allowModificationRedistribution`, `creditNotation=required`, [VRM Public License 1.0](https://vrm.dev/licenses/1.0/). | Metadata indicates conditional redistribution is allowed; attribution and retained license/settings are required. This source-only upload nonetheless excludes character binaries; do not generalize these permissions to Alicia or Ecy. |
| Manny / official Motion Matching material | `ue5_project/Content/Aociety/MotionMatching/` and editor builder/import scripts reference Unreal/Epic material. No complete standalone source-asset redistribution clearance is recorded in this repository. | Keep the asset binaries local. Restore through your authorized Unreal/Epic installation and verify its applicable terms; do not label them as project-owned or MIT. |
| Marketplace/environment packs and imported maps | Local marketplace pack references in `AocietyGameMode.cpp`; `SourceAssets/ImportedScene/`, `ue5_project/Content/Aociety/Maps/` and snow/material content may contain or reference third-party derivatives. | Exclude source/UE binaries as a conservative whole until dependencies, provenance and redistribution permissions are documented. |
| Test voice audio | `test_xiaoxiao.mp3`; generated voice provenance/redistribution clearance is not documented. | Exclude from source distribution; it is not needed by automated tests. |

The local CGmodel notice is a general accompanying notice, not a complete model
license. This review did not invent additional rights or assume that all assets
share one license. VRM metadata was read from each actual file; Alicia's full
rules remain unverified. VRM 1.0 permissions are determined by the model's
embedded settings together with its license, including required attribution.

## Excluded scope

The source-only branch excludes all `SourceAssets/`, all UE content binaries,
`public/models/ecy-avatar.glb`, `public/models/ecy-avatar-preview.png`, and the
test MP3. In particular, Ecy derivatives include:

- `SourceAssets/Characters/Player_Ecy/` (BLEND, FBX, textures and animation exports).
- `ue5_project/Content/Aociety/Characters/Ecy/` and other Ecy derivative folders.
- Ecy-containing imported maps, retarget/motion assets and generated materials.
- The launcher model and its rendered preview.

Executable/source code, configuration examples, project scripts and documented
original/distributable UI resources can remain in the source branch. Scripts
that reference omitted assets are tooling, not an included asset download.
Stopping tracking changes only Git's index; it does **not** delete the owner's
local files. Historical commits may still contain asset objects. This operation
does not rewrite Git history or guarantee removal from already published
branches, forks or caches. Review the exact pushed branch/history separately
before any public publication; history cleanup requires a separate decision.

## Restoring an authorized local setup

1. Keep the preserved complete local project/backup; do not overwrite or delete
   it while preparing a source-only checkout.
2. Restore authorized `SourceAssets` and UE content from your own local backup
   to their original relative directories. Unreal maps require their referenced
   meshes, materials, animation databases and skeletons, not just the `.umap`.
3. Restore the matching GLB and PNG in `public/models/` as described in its
   [README](../public/models/README.md). Run `pnpm test:assets` in strict mode.
4. Configure the backend/API credentials locally; never restore secret files
   into Git. Build UE with the matching engine and installed MSVC toolchain.
5. Record source/license evidence before replacing an asset or distributing a
   build. A source-only CI check that explicitly skips missing local avatar
   assets is not a complete-game, UE binary or licensing validation.

The machine used for this review has UE 5.8 headers, but the incremental C++
build was blocked by a missing valid Visual C++ toolchain. New UE source guards
and source-contract tests were checked; new C++ automation tests and rebuilt UE
binaries must still be compiled and run on a machine with the required MSVC
components. No paid assets or model credentials are downloaded by this guide.
