from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.bounded_worker import BoundedAsyncWorker
from scripts import start_all


def import_without_local_secrets(module_name: str):
    """Never read .env, initialize TTS devices, or use account credentials."""
    original_exists = Path.exists

    def safe_exists(path: Path):
        return False if path.name == ".env" else original_exists(path)

    with patch.dict(os.environ, {}, clear=True), patch.object(Path, "exists", safe_exists), patch("services.tts_service.TTSService"):
        return importlib.import_module(module_name)


class TestLaunchCommands(unittest.TestCase):
    def test_default_launch_is_loopback_and_not_reload(self) -> None:
        with patch("scripts.start_all.subprocess.Popen") as popen:
            children = []
            start_all.start_main_backend(children)
            command = popen.call_args.args[0]
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertNotIn("--reload", command)
        self.assertEqual(len(children), 1)

    def test_lan_and_reload_require_explicit_arguments(self) -> None:
        with patch("scripts.start_all.subprocess.Popen") as popen:
            start_all.start_main_backend([], host="0.0.0.0", reload=True)
            command = popen.call_args.args[0]
        self.assertEqual(command[command.index("--host") + 1], "0.0.0.0")
        self.assertIn("--reload", command)

    def test_model_servers_also_default_to_loopback(self) -> None:
        for launch in (start_all.start_r1_omni, start_all.start_arousal_service):
            with self.subTest(launch=launch.__name__), patch("scripts.start_all.subprocess.Popen") as popen:
                launch([])
                command = popen.call_args.args[0]
                self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")


class TestServiceLifecycles(unittest.IsolatedAsyncioTestCase):
    async def test_resident_lifespan_closes_both_clients(self) -> None:
        module = import_without_local_secrets("services.app")
        self.addCleanup(module.forest_ark.close)
        self.addCleanup(module.engine.ark.close)
        engine, forest = Mock(), Mock()
        with patch.object(module, "engine", engine), patch.object(module, "forest_ark", forest):
            async with module.lifespan(module.app):
                pass
        engine.reset.assert_called_once()
        engine.ark.close.assert_called_once()
        forest.close.assert_called_once()

    async def test_hardware_lifespan_closes_workers_and_clients(self) -> None:
        module = import_without_local_secrets("backend.main")
        for resource in (module.npc_glm, module.world_engine.ark, module.emotion_ws_worker, module.world_ws_worker):
            self.addCleanup(resource.close)
        engine, npc, emotion_worker, world_worker = Mock(), Mock(), Mock(), Mock()
        with patch.object(module, "world_engine", engine), patch.object(module, "npc_glm", npc), patch.object(module, "emotion_ws_worker", emotion_worker), patch.object(module, "world_ws_worker", world_worker):
            async with module.lifespan(module.app):
                pass
        for resource in (engine.ark, npc, emotion_worker, world_worker):
            resource.close.assert_called_once()

    async def test_emotion_websocket_sends_fused_analysis_instead_of_discarding_it(self) -> None:
        module = import_without_local_secrets("backend.main")
        worker = BoundedAsyncWorker(max_workers=1)
        self.addCleanup(worker.close)
        socket = SimpleNamespace(
            accept=AsyncMock(),
            receive_json=AsyncMock(side_effect=[{"text_hint": "开心"}, module.WebSocketDisconnect()]),
            send_json=AsyncMock(),
        )
        analysis = Mock(return_value=module.EmotionOut(emotion="joy", degraded=False, source_models={"emotion": "mock-cloud"}))
        with patch.object(module, "analyze_emotion", analysis), patch.object(module, "emotion_ws_worker", worker):
            await module.emotion_websocket(socket)
        analysis.assert_called_once()
        packet = socket.send_json.call_args.args[0]
        self.assertEqual(packet["emotion"], "joy")
        self.assertEqual(packet["source_models"]["emotion"], "mock-cloud")
        self.assertFalse(packet["degraded"])
        self.assertFalse(module.active_websockets)


class TestResidentScopeAPI(unittest.TestCase):
    def test_all_resident_routes_forward_the_explicit_scope(self) -> None:
        module = import_without_local_secrets("services.app")
        self.addCleanup(module.forest_ark.close)
        self.addCleanup(module.engine.ark.close)
        scope = "a" * 32
        routes = (
            (module.ForestResidentRequest, module.forest_resident_chat, {"npc_id": "npc_01"}, "player"),
            (module.PlayerTalkRequest, module.npc_player_talk, {"npc_id": "npc_01"}, "player"),
            (module.ConversationRequest, module.npc_conversation, {"speaker_id": "npc_01", "listener_id": "npc_02"}, "ambient"),
        )
        for request_type, handler, fields, mode in routes:
            with self.subTest(route=handler.__name__), patch.object(module.forest_residents, "chat", return_value={"source": "mock"}) as chat:
                handler(request_type(**fields, conversation_scope=scope))
                self.assertEqual(chat.call_args.kwargs["conversation_scope"], scope)
                self.assertEqual(chat.call_args.kwargs["mode"], mode)

    def test_request_models_reject_invalid_scope_and_keep_old_clients_stateless(self) -> None:
        from pydantic import ValidationError
        module = import_without_local_secrets("services.app")
        models = (
            (module.ForestResidentRequest, {"npc_id": "npc_01"}),
            (module.PlayerTalkRequest, {"npc_id": "npc_01"}),
            (module.ConversationRequest, {"speaker_id": "npc_01", "listener_id": "npc_02"}),
        )
        for request_type, fields in models:
            self.assertEqual(request_type(**fields).conversation_scope, "")
            self.assertEqual(request_type(**fields, conversation_scope="A" * 32).conversation_scope, "A" * 32)
            for invalid in ("x" * 32, "a" * 33, "../account", None):
                with self.subTest(model=request_type.__name__, invalid=invalid), self.assertRaises(ValidationError):
                    request_type(**fields, conversation_scope=invalid)


class TestHardwarePipelineStartup(unittest.TestCase):
    def test_voice_label_does_not_access_nonexistent_class_constant(self) -> None:
        fake_modules = {}
        for module_name, class_name in (
            ("services.vision_service", "VisionService"),
            ("services.audio_service", "AudioService"),
            ("services.body_pose_service", "BodyPoseService"),
        ):
            fake_module = ModuleType(module_name)
            setattr(fake_module, class_name, Mock())
            fake_modules[module_name] = fake_module
        with patch.dict("sys.modules", fake_modules):
            module = importlib.import_module("services.emotion_pipeline")
        pipeline = object.__new__(module.EmotionPipeline)
        pipeline.vision, pipeline.audio, pipeline.pose = Mock(), Mock(), Mock()
        pipeline.tts = SimpleNamespace(voice_name="xiaoxiao")
        pipeline.backend_url = "http://127.0.0.1:8010"
        with patch.object(module.threading, "Thread"), patch("builtins.print"):
            pipeline.start(enable_vision=False, enable_audio=False, enable_pose=False)
        self.assertTrue(pipeline._running)


if __name__ == "__main__":
    unittest.main()
