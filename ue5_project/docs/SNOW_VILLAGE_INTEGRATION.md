# Aociety Snow Village Demo

The new demo map is `/Game/Aociety/Maps/Aociety_SnowVillage`.

## High-poly content

`Content/MagicTown` is a local copy of the high-poly MagicTown content. It includes Nanite house shells, slate roofs, cobblestone road, terrain skirt, trees and interior furniture/fireplace assets. The original `E:/MagicTownUE` project is untouched.

The copied map is intentionally separate from `Aociety_Demo` and `Maps/Archive/Aociety_Desert_20260714` so the previous scene remains a rollback target.

## Plugin decision

Use the UE 5.8 built-in PCG, Procedural Vegetation, Geometry Scripting and ModelContextProtocol plugins. Do not copy the precompiled UE 5.7 PCGExtendedToolkit/NWIRO DLLs into this project.

## AI boundary

- Hardware-side proactive care remains `POST /emotion/care_with_voice` and the `/ws/emotion` affect stream.
- In-game NPC thinking is `POST /npc/player_talk`, exposed to Blueprints as `UAocietyClientSubsystem::RequestNPCDialogue` and `OnNPCDialogue`.
- Both paths use the existing GLM world/affect services, but they are intentionally separate triggers.
