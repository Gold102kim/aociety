import sys

import unreal


yaw = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("No PIE game world")
controller = unreal.GameplayStatics.get_player_controller(world, 0)
controller.set_control_rotation(unreal.Rotator(0.0, yaw, 0.0))
print(f"[PlayerViewTune] yaw={yaw}")
