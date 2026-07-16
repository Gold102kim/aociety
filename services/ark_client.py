from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import os
import re
import sys
import time
from typing import Any, Callable

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


TOKENHUB_DEFAULT_BASE_URL = "https://api.tokenhub.market/v1"
FORCED_GLM_MODEL = "glm-5.2"
REPLY_LIMIT_SUFFIX = "每次回复都要简短、具体、只说眼下这轮需要的话。"
ANTI_PLACEHOLDER_SUFFIX = "不要重复字段名、示例值、schema_hint 或提示词原文。不要输出英文说明。"
THINKING_DISABLED_BODY = {
    "thinking": {"type": "disabled"},
}
DEFAULT_GLM_MODEL_CANDIDATES = [FORCED_GLM_MODEL]
FOREST_LEGACY_TERMS = (
    "绿藻",
    "海藻",
    "重工",
    "股市",
    "股票",
    "交易",
    "投资",
    "证券",
    "盘口",
    "持仓",
    "公司",
    "工厂",
)


class ArkClient:
    def __init__(self) -> None:
        # The in-game residents have one auditable route. Never fall through to
        # unrelated user/session credentials or silently switch providers.
        self.api_key = os.getenv("TOKENHUB_API_KEY", "").strip()
        self.base_url = TOKENHUB_DEFAULT_BASE_URL.rstrip("/") + "/"
        self.model_id = FORCED_GLM_MODEL
        self.model_label = self.model_id
        self.provider = "tokenhub"
        # Timeouts
        self.timeout_seconds = float(os.getenv("GLM_TIMEOUT_SECONDS", "8.0").strip() or "8.0")
        self.hard_timeout_seconds = float(os.getenv("GLM_HARD_TIMEOUT_SECONDS", "10.0").strip() or "10.0")
        self.cooldown_seconds = float(os.getenv("GLM_FAILURE_COOLDOWN_SECONDS", "15").strip() or "15")
        self.dialogue_workers = max(1, int(os.getenv("GLM_DIALOGUE_WORKERS", "2").strip() or "2"))
        self.background_workers = max(1, int(os.getenv("GLM_BACKGROUND_WORKERS", "4").strip() or "4"))
        self._dialogue_executor = ThreadPoolExecutor(max_workers=self.dialogue_workers, thread_name_prefix="glm-dialogue")
        self._background_executor = ThreadPoolExecutor(max_workers=self.background_workers, thread_name_prefix="glm-background")
        self._client = None
        self._disabled_until = 0.0
        self._last_error = ""
        disable_for_unittest = "unittest" in sys.modules and os.getenv("GLM_ENABLE_IN_TESTS", "0") != "1"
        has_key = bool(self.api_key)
        if has_key and OpenAI is not None and not disable_for_unittest:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout_seconds)

    @property
    def enabled(self) -> bool:
        return self._client is not None and time.time() >= self._disabled_until

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _disable_temporarily(self, reason: str) -> None:
        self._last_error = str(reason or "").strip()
        self._disabled_until = max(self._disabled_until, time.time() + self.cooldown_seconds)

    def _executor_for_task(self, task_type: str) -> ThreadPoolExecutor:
        if task_type == "dialogue_turn":
            return self._dialogue_executor
        return self._background_executor

    def _create_completion(self, task_type: str, **kwargs: Any) -> Any:
        if self._client is None:
            raise RuntimeError("ark client disabled")
        if time.time() < self._disabled_until:
            raise RuntimeError("ark client cooling down")
        future = self._executor_for_task(task_type).submit(self._client.chat.completions.create, **kwargs)
        try:
            response = future.result(timeout=self.hard_timeout_seconds)
            self._disabled_until = 0.0
            self._last_error = ""
            return response
        except FuturesTimeoutError as exc:
            future.cancel()
            self._disable_temporarily(f"ark hard timeout after {self.hard_timeout_seconds:.1f}s")
            raise TimeoutError(f"ark hard timeout after {self.hard_timeout_seconds:.1f}s") from exc
        except Exception as exc:
            self._disable_temporarily(str(exc))
            raise

    @staticmethod
    def thinking_disabled_body() -> dict[str, Any]:
        return dict(THINKING_DISABLED_BODY)

    def generate_dialogue_turn(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        scene_observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="dialogue_turn",
            schema_hint='{"lines":["玩家原话","NPC回话"],"stance":"谨慎/强硬/敷衍/热心","truthfulness":0.58,"revealed_topic_ids":["market_whisper"]}',
            system_prompt=(
                "lines[1] 必须先正面回应 player_input，再补充氛围和剧情。\n"
                "你是《Aociety》的 NPC 对话引擎。"
                "你只负责生成一轮贴近身份的中文对话。"
                "玩家台词必须原样复述到 lines[0]。"
                "NPC 台词放到 lines[1]。"
                "只能依据 topic、listener、listener_sections、favorability_state、relationship_memory 和 district 回答。"
                "必须延续角色身份、利益、秘密、关系和最近记忆，不要把每轮都当成第一次见面。"
                "如果玩家在问身份、来路、立场、替谁办事、和谁一伙，必须先正面回答这个问题，再决定是否延伸到盘口或利益。"
                "如果玩家在问价格、持仓、做局、放风、谁先动手，优先回答市场和利益层。"
                "speech_register 偏 patronized/bought/owned/deferential 且 respect 高时可以抬称呼、少兜圈子；resentment 高时可以更硬。"
                "不能讲英文，不能解释规则，不能自称模型。"
            ),
            task_prompt=(
                "请直接返回一个 JSON 对象。"
                "如果信息不足，也要用角色口吻谨慎回答，不能空白。"
            ),
            state_prompt={
                "speaker": payload.get("speaker", {}),
                "listener": payload.get("listener", {}),
                "district": payload.get("district", ""),
                "trigger": payload.get("trigger", ""),
                "player_input": payload.get("player_input", ""),
                "topic": payload.get("topic", {}),
                "approach": payload.get("approach", "cautious"),
                "intent": payload.get("intent", ""),
                "truth_profile": payload.get("truth_profile", {}),
                "favorability_state": payload.get("favorability_state", {}),
                "listener_sections": payload.get("listener_sections", {}),
                "relationship_memory": payload.get("relationship_memory", {}),
                "scene_context": scene_observation.get("scene_context", {}),
            },
            screenshot_b64=scene_observation.get("screenshot_b64", ""),
            normalizer=lambda parsed: self._normalize_dialogue_turn(parsed, payload),
        )

    def generate_forest_resident_reply(
        self, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Generate isolated demo dialogue without the legacy market world."""
        if not self.enabled:
            return None

        system_prompt = (
            "你是 Aociety 全新森林小镇中的一名普通居民，不是旁白、客服或游戏教程。"
            "小镇居民过着安静、温暖的日常生活，会散步、休息、做饭、读书、照顾住处、"
            "花草和邻居。所有世界事实只来自本次请求中的居民档案、现场事件、场景与近期对话。"
            "不要继承其他故事，也不要编造输入中没有的人名、地名、组织名或背景事件。"
            "每轮都要先理解 live_event，再结合性格和短期记忆生成当下的新回应。"
            "如果是玩家互动，就直接回应玩家；如果是居民互聊，就直接回应 counterpart。"
            "不要背诵欢迎语，不要复述上一轮，不要提及 request_nonce，也不要输出思考过程。"
            "说话自然、简短、有生活感，每次一到两句，不要说自己是 AI 或语言模型。"
            "只返回 JSON：{\"reply\":\"居民说的话\",\"mood\":\"当前情绪\"}。"
        )
        recent_dialogue = payload.get("recent_dialogue", [])
        recent_replies = {
            self._normalize_reply_for_comparison(str(item.get(field, "")))
            for item in recent_dialogue
            if isinstance(item, dict)
            for field in ("reply", "heard_reply")
            if item.get(field)
        }
        rejected_reply = ""

        for attempt in range(2):
            user_prompt = json.dumps(
                {
                    "resident": payload.get("resident", {}),
                    "interaction_mode": payload.get("mode", "player"),
                    "live_event": payload.get("live_event", ""),
                    "counterpart": payload.get("counterpart", {}),
                    "scene": payload.get("scene", {}),
                    "recent_dialogue": recent_dialogue,
                    "counterpart_recent_dialogue": payload.get(
                        "counterpart_recent_dialogue", []
                    ),
                    "request_nonce": f"{payload.get('request_nonce', '')}-{attempt}",
                    "rejected_reply": rejected_reply,
                    "retry_instruction": (
                        "上一个候选回复与近期内容重复或引入了请求外设定，必须换一种全新的日常回应。"
                        if rejected_reply
                        else "这是一轮新的实时交互，请生成只属于此刻的回应。"
                    ),
                },
                ensure_ascii=False,
            )

            for model_name in self._model_candidates():
                try:
                    response = self._create_completion(
                        task_type="dialogue_turn",
                        model=model_name,
                        temperature=0.9,
                        max_tokens=220,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    )
                    content = self._message_to_text(
                        response.choices[0].message.content
                    )
                    parsed = self._extract_json(content)
                    reply = self._sanitize_text(str(parsed.get("reply", "")))
                    mood = self._sanitize_text(str(parsed.get("mood", "平静")))
                    normalized_reply = self._normalize_reply_for_comparison(reply)
                    if (
                        not normalized_reply
                        or normalized_reply in recent_replies
                        or self._contains_forest_legacy_term(reply)
                    ):
                        rejected_reply = reply
                        continue
                    return {
                        "reply": reply,
                        "mood": mood or "平静",
                        "_meta_source": "llm",
                        "_meta_model": model_name,
                        "_meta_provider": self.provider,
                    }
                except Exception:
                    continue
        return None

    @staticmethod
    def _normalize_reply_for_comparison(reply: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(reply or "")).lower()

    @staticmethod
    def _contains_forest_legacy_term(reply: str) -> bool:
        cleaned = str(reply or "").lower()
        return any(term.lower() in cleaned for term in FOREST_LEGACY_TERMS)

    def generate_news_copy(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        scene_observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="news_copy",
            schema_hint='{"title":"标题","body":"正文","tags":["街区","市场"],"tone":"冷静/煽动/审慎"}',
            system_prompt=(
                "你是《Aociety》的城内新闻编辑。"
                "只把输入里已经存在的市场变化、街区情绪和事件包装成一条短新闻。"
                "不要编造额外价格、余额或世界结果。"
            ),
            task_prompt="输出一条适合 HUD 和新闻栏展示的中文短新闻，只返回一个 JSON 对象。",
            state_prompt={
                "event_name": payload.get("event_name", ""),
                "district": payload.get("district", ""),
                "macro": payload.get("macro", {}),
                "stocks": payload.get("stocks", []),
                "source_line": payload.get("source_line", ""),
                "source_body": payload.get("source_body", ""),
                "tags": payload.get("tags", []),
                "goods_delta": payload.get("goods_delta", {}),
                "stocks_delta": payload.get("stocks_delta", {}),
                "family_delta": payload.get("family_delta", {}),
                "scene_context": scene_observation.get("scene_context", {}),
            },
            screenshot_b64=scene_observation.get("screenshot_b64", ""),
            normalizer=self._normalize_news_copy,
        )

    def generate_scene_read(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="scene_read",
            schema_hint='{"director_note":"导演旁白","headline_title":"标题","headline_body":"一句摘要"}',
            system_prompt=(
                "你是《Aociety》的场景导演。"
                "只总结画面氛围、街头紧张感、交易热度和舆论温度。"
                "不要编造成败结果。"
            ),
            task_prompt="根据画面和状态写一句导演旁白与一句标题摘要，只返回一个 JSON 对象。",
            state_prompt={
                "trigger": payload.get("trigger", ""),
                "day": payload.get("day", 1),
                "macro": payload.get("macro", {}),
                "current_district": observation.get("current_district", ""),
                "scene_context": observation.get("scene_context", {}),
                "headlines": payload.get("headlines", []),
            },
            screenshot_b64=observation.get("screenshot_b64", ""),
            normalizer=self._normalize_scene_read,
        )

    def generate_npc_spin(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        scene_observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="npc_spin",
            schema_hint=(
                '{"emotions":{"anger":0.2,"anxiety":0.5,"hope":0.3},"beliefs_update":{"focus":"一句更新"},'
                '"top_goals":["一句短期目标"],"social_message":"一句角色说法","stance":"谨慎/乐观/恐慌/挑衅","truthfulness":0.56,"market_tilt":"bullish/bearish/neutral",'
                '"trade_decision":{"action":"buy/sell/hold","stock_name":"海藻食业","quantity":3,"confidence":0.62,"note":"为什么这么做"},'
                '"topic_action":{"mode":"share/amplify/question/deny/silence","topic_id":"topic_x","intensity":0.62,"note":"为什么这么做"},'
                '"norm_action":{"mode":"reinforce/contest/seed/ignore","norm_id":"norm_x","text":"规范文本","intensity":0.58,"note":"为什么这么做"},'
                '"collective_action_attitude":{"mode":"hear/support/commit/attend/organize/suppress/avoid","action_id":"collective_x","kind":"strike/meeting/rally/party","intensity":0.63,"note":"为什么这么做"},'
                '"intended_actions":{"topic_action":{"mode":"share","topic_id":"topic_x","intensity":0.62,"note":"为什么这么做"},"norm_action":{"mode":"reinforce","norm_id":"norm_x","text":"规范文本","intensity":0.58,"note":"为什么这么做"},"collective_action":{"mode":"support","action_id":"collective_x","kind":"meeting","intensity":0.52,"note":"为什么这么做"}}}'
            ),
            system_prompt=(
                "你只负责写一名 NPC 此刻的结构化心智输出。"
                "传入的 topic 与 active_topics 是引擎里真实存在的议题对象。"
                "传入的 active_norms 是当前街区里显式存在的社会规范对象。"
                "传入的 active_collective_actions 是当前街区里显式存在的集体行动对象。"
                "relationship_memory 里的 conversation_history 和 local_memory 是这名角色的本地记忆。"
                "llm_sections 是这名角色的六段输入：你是谁、你当前状况、你最近经历、你周围的人和关系、城市摘要、允许动作列表。"
                "你要沿着这些记忆延续口风、偏见、关系和短期计划，不能每分钟失忆。"
                "语气必须符合该角色的职业、家族、债务、饥饿和街区位置。"
                "你只能选择放大、转发、质疑、压低或回避这些议题，不能凭空创造新事实。"
                "同时要返回 emotions、beliefs_update、top_goals、social_message、trade_decision、collective_action_attitude。"
                "如果 intended_actions 存在，里面要把 topic_action、norm_action、collective_action 一并写出来。"
                "只返回一个 JSON 对象。"
            ),
            task_prompt="按六段输入返回一个结构化 JSON，对这名角色此刻的情绪、目标、社交表达、交易决定和集体行动态度做出选择。",
            state_prompt={
                "npc": payload.get("npc", {}),
                "agent_profile": payload.get("agent_profile", {}),
                "llm_sections": payload.get("llm_sections", {}),
                "topic": payload.get("topic", {}),
                "active_topics": payload.get("active_topics", []),
                "active_norms": payload.get("active_norms", []),
                "active_collective_actions": payload.get("active_collective_actions", []),
                "truth_profile": payload.get("truth_profile", {}),
                "district_signals": payload.get("district_signals", {}),
                "relationship_memory": payload.get("relationship_memory", {}),
                "recent_briefs": payload.get("recent_briefs", []),
                "scene_context": scene_observation.get("scene_context", {}),
            },
            screenshot_b64=scene_observation.get("screenshot_b64", ""),
            normalizer=self._normalize_npc_spin,
        )

    def generate_family_briefing(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        scene_observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="family_briefing",
            schema_hint='{"public_line":"公开动作","hidden_line":"暗线动作","focus":"焦点","signal":"steady/rising/falling"}',
            system_prompt=(
                "你负责写家族简报。"
                "只能根据输入里的显式议题对象、控制关系和压力状态来写。"
                "active_norms 表示街区里当前在生效或被争议的行为规范。"
                "active_collective_actions 表示街区里正在酝酿或执行的集体行动。"
                "公开口风要像外放消息，暗线口风要像内部意图。"
                "不能编造资产数字。"
            ),
            task_prompt="根据家族控制力和街区压力写公开口风与暗线口风，只返回一个 JSON 对象。",
            state_prompt={
                "family": payload.get("family", {}),
                "controlled_companies": payload.get("controlled_companies", []),
                "active_topics": payload.get("active_topics", []),
                "active_norms": payload.get("active_norms", []),
                "active_collective_actions": payload.get("active_collective_actions", []),
                "district_signals": payload.get("district_signals", {}),
                "recent_briefs": payload.get("recent_briefs", []),
                "scene_context": scene_observation.get("scene_context", {}),
            },
            screenshot_b64=scene_observation.get("screenshot_b64", ""),
            normalizer=self._normalize_family_briefing,
        )

    def generate_company_briefing(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        scene_observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="company_briefing",
            schema_hint='{"headline":"公司摘要","worker_note":"工人感受","risk_note":"风险提示","signal":"steady/rising/falling"}',
            system_prompt=(
                "你负责写公司层简报。"
                "只能根据输入里的显式议题对象、劳工状态和经营状态来写。"
                "active_norms 表示街区里当前在生效或被争议的行为规范。"
                "active_collective_actions 表示街区里正在酝酿或执行的集体行动。"
                "只总结经营状态、劳工情绪和风险，不要编造不存在的财务数字。"
            ),
            task_prompt="根据公司状态写一条公司摘要、一条工人感受和一条风险提示，只返回一个 JSON 对象。",
            state_prompt={
                "company": payload.get("company", {}),
                "active_topics": payload.get("active_topics", []),
                "active_norms": payload.get("active_norms", []),
                "active_collective_actions": payload.get("active_collective_actions", []),
                "district_signals": payload.get("district_signals", {}),
                "recent_briefs": payload.get("recent_briefs", []),
                "scene_context": scene_observation.get("scene_context", {}),
            },
            screenshot_b64=scene_observation.get("screenshot_b64", ""),
            normalizer=self._normalize_company_briefing,
        )

    def generate_pulse_brief(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        scene_observation = payload.get("scene_observation", {})
        return self._request_json(
            task_type="pulse_brief",
            schema_hint=(
                '{"pulse_summary":"一句总览","market_note":"一句市场提示","scene_focus":"一句场景焦点",'
                '"npc_updates":[{"id":"npc_id","line":"一句口风","social_message":"一句社会表达","stance":"谨慎","market_tilt":"neutral",'
                '"emotions":{"anger":0.2,"anxiety":0.5,"hope":0.3},"beliefs_update":{"focus":"一句更新"},"top_goals":["一句短期目标"],'
                '"trade_decision":{"action":"buy/sell/hold","stock_name":"海藻食业","quantity":3,"confidence":0.62,"note":"为什么这么做"},'
                '"collective_action":{"mode":"hear","action_id":"collective_x","kind":"meeting","intensity":0.4,"note":"为什么"}}],'
                '"family_updates":[{"name":"家族名","public_line":"公开动作","hidden_line":"暗线动作","focus":"焦点","signal":"steady"}],'
                '"company_updates":[{"id":"company_id","headline":"一句状态","worker_note":"工人感受","risk_note":"风险提示","signal":"steady"}]}'
            ),
            system_prompt=(
                "你是《Aociety》的分钟级 AI 脉冲编辑。"
                "topics 字段给出的显式议题对象是当前真实社会变量摘要。"
                "norms 字段给出的显式规范对象是当前正在形成或被挑战的社会约束。"
                "collective_actions 字段给出的显式集体行动对象是当前正在酝酿或执行的现实组织过程。"
                "只总结当前已知状态，覆盖输入里的 NPC、家族和公司。"
                "不要额外编造价格、余额或结局。"
            ),
            task_prompt="请生成一次适合驱动 HUD 和街头耳语更新的中文脉冲摘要，只返回一个 JSON 对象。",
            state_prompt={
                "trigger": payload.get("trigger", ""),
                "day": payload.get("day", 1),
                "macro": payload.get("macro", {}),
                "district_signals": payload.get("district_signals", {}),
                "topics": payload.get("topics", []),
                "norms": payload.get("norms", []),
                "collective_actions": payload.get("collective_actions", []),
                "player": payload.get("player", {}),
                "goods": payload.get("goods", []),
                "stocks": payload.get("stocks", []),
                "families": payload.get("families", []),
                "companies": payload.get("companies", []),
                "npcs": payload.get("npcs", []),
                "scene_context": scene_observation.get("scene_context", {}),
                "current_district": scene_observation.get("current_district", ""),
            },
            screenshot_b64=scene_observation.get("screenshot_b64", ""),
            normalizer=self._normalize_pulse_brief,
        )

    def generate_conversation(self, payload: dict[str, Any]) -> list[str] | None:
        generated = self.generate_dialogue_turn(payload)
        if not generated:
            return None
        lines = generated.get("lines", [])
        if isinstance(lines, list) and len(lines) >= 2:
            return [str(lines[0]), str(lines[1])]
        return None

    def generate_news(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self.generate_news_copy(payload)

    def generate_scene_direction(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self.generate_scene_read(payload)

    def probe(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "ok": False,
                "message": "GLM 客户端未启用，请检查项目 .env 中的 TOKENHUB_API_KEY。",
                "model": self.model_id,
            }
        if not self.enabled:
            cooldown_left = max(0, int(round(self._disabled_until - time.time())))
            reason = self._last_error or "GLM 链路暂时冷却中"
            return {
                "ok": False,
                "message": f"{reason}；{cooldown_left} 秒后再试。",
                "model": self.model_id,
            }
        errors: list[str] = []
        for model_name in self._model_candidates():
            try:
                response = self._create_completion(
                    task_type="probe",
                    model=model_name,
                    temperature=0.1,
                    max_tokens=24,
                    extra_body=self.thinking_disabled_body(),
                    messages=[
                        {
                            "role": "system",
                            "content": "你是连通性测试助手。必须只返回一个 JSON 对象：{\"message\":\"GLM 连通\"}。",
                        },
                        {"role": "user", "content": "请按要求返回。"},
                    ],
                )
                content = self._message_to_text(response.choices[0].message.content)
                parsed = self._extract_json(content)
                message = self._sanitize_text(str(parsed.get("message", "")))
                if not message and "GLM 连通" in content:
                    message = "GLM 连通"
                if not message:
                    continue
                return {
                    "ok": True,
                    "message": message,
                    "model": model_name,
                }
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
        return {
            "ok": False,
            "message": " | ".join(errors),
            "model": self.model_id,
        }

    def _request_json(
        self,
        *,
        task_type: str,
        schema_hint: str,
        system_prompt: str,
        task_prompt: str,
        state_prompt: dict[str, Any],
        screenshot_b64: str = "",
        normalizer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        prompt = {
            "task_type": task_type,
            "task_prompt": task_prompt + REPLY_LIMIT_SUFFIX + ANTI_PLACEHOLDER_SUFFIX,
            "schema_hint": schema_hint,
            "state": state_prompt,
        }
        final_system = system_prompt + REPLY_LIMIT_SUFFIX + ANTI_PLACEHOLDER_SUFFIX
        for model_name in self._model_candidates():
            try:
                response = self._create_completion(
                    task_type=task_type,
                    model=model_name,
                    temperature=0.01,
                    max_tokens=self._task_max_tokens(task_type),
                    extra_body=self.thinking_disabled_body(),
                    messages=[
                        {"role": "system", "content": final_system},
                        {
                            "role": "user",
                            "content": self._build_multimodal_content(json.dumps(prompt, ensure_ascii=False), screenshot_b64),
                        },
                    ],
                )
                content = self._message_to_text(response.choices[0].message.content)
                parsed = self._extract_json(content)
                if not parsed and task_type == "dialogue_turn":
                    parsed = self._dialogue_fallback_from_text(content)
                if not parsed:
                    continue
                normalized = normalizer(parsed) if normalizer is not None else parsed
                if not normalized:
                    continue
                if not self._looks_usable_chinese(normalized):
                    continue
                normalized["_meta_model"] = model_name
                return normalized
            except Exception:
                continue
        return None

    @staticmethod
    def _task_max_tokens(task_type: str) -> int:
        if task_type == "dialogue_turn":
            return 160
        if task_type == "npc_spin":
            return 80
        if task_type in {"news_copy", "scene_read"}:
            return 112
        return 192

    @staticmethod
    def _message_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
        return str(content or "")

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        stripped = content.strip()
        if not stripped:
            return {}
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
        if fenced:
            stripped = fenced.group(1)
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                return parsed[0]
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", stripped, re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
        return {}

    @classmethod
    def _dialogue_fallback_from_text(cls, content: str) -> dict[str, Any]:
        cleaned = cls._sanitize_text(str(content))
        if not cleaned:
            return {}
        lines = [line.strip("：: -") for line in cleaned.splitlines() if line.strip()]
        npc_line = ""
        for line in lines:
            if len(line) >= 6:
                npc_line = line
                break
        if not npc_line:
            npc_line = cleaned[:120]
        return {"lines": ["……", npc_line], "stance": "谨慎", "truthfulness": 0.52}

    @classmethod
    def _looks_like_raw_dialogue_blob(cls, text: str) -> bool:
        cleaned = str(text or "").strip()
        if not cleaned:
            return False
        if cleaned.startswith("{") or cleaned.startswith("["):
            return True
        lowered = cleaned.lower()
        return any(token in lowered for token in ['"lines"', '"stance"', '"truthfulness"', "schema", "json", "revealed_topic_ids"])

    @classmethod
    def _extract_dialogue_line(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            ordered_items = list(value)
            if len(ordered_items) >= 2:
                ordered_items = [ordered_items[-1], *ordered_items[:-1]]
            for item in ordered_items:
                extracted = cls._extract_dialogue_line(item)
                if extracted:
                    return extracted
            return ""
        if isinstance(value, dict):
            for key in ("npc_reply", "reply", "line", "social_message", "body", "lines"):
                extracted = cls._extract_dialogue_line(value.get(key))
                if extracted:
                    return extracted
            return ""
        text = cls._sanitize_text(str(value))
        if not text or text.lower() == "none":
            return ""
        if cls._looks_like_raw_dialogue_blob(text):
            parsed = cls._extract_json(text)
            if parsed:
                return cls._extract_dialogue_line(parsed)
            text = re.sub(r'["{}\\[\\]]', " ", text)
            text = re.sub(r"\b(lines|stance|truthfulness|revealed_topic_ids|reply|npc_reply|line|schema)\b", " ", text, flags=re.I)
            text = re.sub(r"\s+", " ", text).strip(" ,:;")
        if cls._looks_like_raw_dialogue_blob(text):
            return ""
        return text[:180]

    def _model_candidates(self) -> list[str]:
        forced_model = str(self.model_id).strip() or FORCED_GLM_MODEL
        return [forced_model]

    @staticmethod
    def _build_multimodal_content(text_prompt: str, screenshot_b64: str) -> Any:
        if not screenshot_b64:
            return text_prompt
        return [
            {"type": "text", "text": text_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            },
        ]

    def _normalize_dialogue_turn(self, parsed: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        lines = parsed.get("lines", [])
        if not isinstance(lines, list):
            lines = []
        player_input = self._sanitize_text(str(payload.get("player_input", "")).strip())
        player_line = player_input or (self._sanitize_text(str(lines[0])) if len(lines) > 0 else "")
        if not player_line:
            player_line = "……"
        npc_line = self._extract_dialogue_line(lines[1]) if len(lines) > 1 else ""
        if not npc_line:
            npc_line = self._extract_dialogue_line(parsed.get("reply", "") or parsed.get("npc_reply", "") or parsed.get("line", ""))
        if not npc_line:
            npc_line = self._extract_dialogue_line(parsed)
        if not npc_line:
            return {}
        stance = self._sanitize_text(str(parsed.get("stance", "谨慎")))
        if not stance:
            stance = "谨慎"
        revealed = parsed.get("revealed_topic_ids", [])
        if not isinstance(revealed, list):
            revealed = [revealed]
        return {
            "lines": [player_line, npc_line],
            "stance": stance,
            "truthfulness": self._clamp_float(parsed.get("truthfulness", 0.55), 0.0, 1.0),
            "revealed_topic_ids": [str(item).strip() for item in revealed if str(item).strip()],
        }

    def _normalize_news_copy(self, parsed: dict[str, Any]) -> dict[str, Any]:
        tags = parsed.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags]
        body = self._sanitize_text(str(parsed.get("body", "")))
        title = self._sanitize_text(str(parsed.get("title", "")))
        if not title or not body:
            return {}
        return {
            "title": title,
            "body": body,
            "tags": [self._sanitize_text(str(tag)) for tag in tags if self._sanitize_text(str(tag))],
            "tone": self._sanitize_text(str(parsed.get("tone", "冷静"))) or "冷静",
        }

    def _normalize_scene_read(self, parsed: dict[str, Any]) -> dict[str, Any]:
        note = self._sanitize_text(str(parsed.get("director_note", "")))
        headline_title = self._sanitize_text(str(parsed.get("headline_title", "")))
        headline_body = self._sanitize_text(str(parsed.get("headline_body", "")))
        if not note:
            return {}
        return {
            "director_note": note,
            "headline_title": headline_title or "街头风向",
            "headline_body": headline_body or note,
        }

    @classmethod
    def _dialogue_fallback_from_text(cls, content: str) -> dict[str, Any]:
        cleaned = cls._sanitize_text(str(content))
        if not cleaned:
            return {}
        lines = [line.strip("：:- ") for line in cleaned.splitlines() if line.strip()]
        npc_line = ""
        for line in lines:
            if len(line) >= 6:
                npc_line = line
                break
        if not npc_line:
            npc_line = cleaned[:120]
        return {
            "lines": ["你先打量了对方一眼，还没正式开口。", npc_line],
            "stance": "谨慎",
            "truthfulness": 0.52,
        }

    def _normalize_dialogue_turn(self, parsed: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        lines = parsed.get("lines", [])
        if not isinstance(lines, list):
            lines = []
        player_input = self._sanitize_text(str(payload.get("player_input", "")).strip())
        player_line = player_input or (self._sanitize_text(str(lines[0])) if len(lines) > 0 else "")
        if not player_line:
            player_line = "你先打量了对方一眼，还没正式开口。"
        npc_line = self._extract_dialogue_line(lines[1]) if len(lines) > 1 else ""
        if not npc_line:
            npc_line = self._extract_dialogue_line(parsed.get("reply", "") or parsed.get("npc_reply", "") or parsed.get("line", ""))
        if not npc_line:
            npc_line = self._extract_dialogue_line(parsed)
        if not npc_line:
            return {}
        stance = self._sanitize_text(str(parsed.get("stance", "谨慎"))) or "谨慎"
        revealed = parsed.get("revealed_topic_ids", [])
        if not isinstance(revealed, list):
            revealed = [revealed]
        return {
            "lines": [player_line, npc_line],
            "stance": stance,
            "truthfulness": self._clamp_float(parsed.get("truthfulness", 0.55), 0.0, 1.0),
            "revealed_topic_ids": [str(item).strip() for item in revealed if str(item).strip()],
        }

    def _normalize_npc_spin(self, parsed: dict[str, Any]) -> dict[str, Any]:
        lines = parsed.get("lines", [])
        if not isinstance(lines, list):
            lines = []
        social_message = self._sanitize_text(str(parsed.get("social_message", "")))
        primary = self._sanitize_text(str(lines[0])) if lines else self._sanitize_text(str(parsed.get("line", ""))) or social_message
        if not primary:
            return {}
        intended_actions_raw = parsed.get("intended_actions", {})
        if not isinstance(intended_actions_raw, dict):
            intended_actions_raw = {}
        topic_action_raw = parsed.get("topic_action", {})
        if not isinstance(topic_action_raw, dict):
            topic_action_raw = intended_actions_raw.get("topic_action", {})
        norm_action_raw = parsed.get("norm_action", {})
        if not isinstance(norm_action_raw, dict):
            norm_action_raw = intended_actions_raw.get("norm_action", {})
        collective_action_raw = parsed.get("collective_action", parsed.get("collective_action_attitude", {}))
        if not isinstance(collective_action_raw, dict):
            collective_action_raw = intended_actions_raw.get("collective_action", {})
        trade_decision_raw = parsed.get("trade_decision", {})
        if not isinstance(trade_decision_raw, dict):
            trade_decision_raw = {}
        return {
            "emotions": parsed.get("emotions", {}) if isinstance(parsed.get("emotions", {}), dict) else {},
            "beliefs_update": parsed.get("beliefs_update", {}) if isinstance(parsed.get("beliefs_update", {}), dict) else {},
            "top_goals": [self._sanitize_text(str(value)) for value in parsed.get("top_goals", []) if self._sanitize_text(str(value))][:4] if isinstance(parsed.get("top_goals", []), list) else [],
            "stance": self._sanitize_text(str(parsed.get("stance", "谨慎"))) or "谨慎",
            "truthfulness": self._clamp_float(parsed.get("truthfulness", 0.52), 0.0, 1.0),
            "market_tilt": self._sanitize_market_tilt(str(parsed.get("market_tilt", "neutral"))),
            "lines": [primary],
            "social_message": social_message or primary,
            "trade_decision": {
                "action": self._sanitize_text(str(trade_decision_raw.get("action", trade_decision_raw.get("mode", "hold")))).lower() or "hold",
                "stock_name": self._sanitize_text(str(trade_decision_raw.get("stock_name", trade_decision_raw.get("target", "")))) or "",
                "quantity": max(0, int(trade_decision_raw.get("quantity", trade_decision_raw.get("shares", 0)) or 0)),
                "confidence": self._clamp_float(trade_decision_raw.get("confidence", 0.45), 0.0, 1.0),
                "note": self._sanitize_text(str(trade_decision_raw.get("note", trade_decision_raw.get("reason", "")))) or "",
            },
            "topic_action": {
                "mode": self._sanitize_topic_action_mode(str(topic_action_raw.get("mode", parsed.get("topic_action_mode", "")))),
                "topic_id": self._sanitize_text(str(topic_action_raw.get("topic_id", parsed.get("topic_id", "")))) or "",
                "intensity": self._clamp_float(topic_action_raw.get("intensity", parsed.get("topic_intensity", 0.56)), 0.0, 1.0),
                "note": self._sanitize_text(str(topic_action_raw.get("note", parsed.get("topic_note", "")))) or "",
            },
            "norm_action": {
                "mode": self._sanitize_norm_action_mode(str(norm_action_raw.get("mode", parsed.get("norm_action_mode", "")))),
                "norm_id": self._sanitize_text(str(norm_action_raw.get("norm_id", parsed.get("norm_id", "")))) or "",
                "text": self._sanitize_text(str(norm_action_raw.get("text", parsed.get("norm_text", "")))) or "",
                "intensity": self._clamp_float(norm_action_raw.get("intensity", parsed.get("norm_intensity", 0.5)), 0.0, 1.0),
                "note": self._sanitize_text(str(norm_action_raw.get("note", parsed.get("norm_note", "")))) or "",
            },
            "collective_action": {
                "mode": self._sanitize_collective_action_mode(str(collective_action_raw.get("mode", parsed.get("collective_action_mode", "")))),
                "action_id": self._sanitize_text(str(collective_action_raw.get("action_id", parsed.get("collective_action_id", "")))) or "",
                "kind": self._sanitize_collective_kind(str(collective_action_raw.get("kind", parsed.get("collective_kind", "")))),
                "intensity": self._clamp_float(collective_action_raw.get("intensity", parsed.get("collective_intensity", 0.48)), 0.0, 1.0),
                "note": self._sanitize_text(str(collective_action_raw.get("note", parsed.get("collective_note", "")))) or "",
            },
        }

    def _normalize_family_briefing(self, parsed: dict[str, Any]) -> dict[str, Any]:
        public_line = self._sanitize_text(str(parsed.get("public_line", "")))
        hidden_line = self._sanitize_text(str(parsed.get("hidden_line", "")))
        focus = self._sanitize_text(str(parsed.get("focus", "")))
        if not public_line and not hidden_line:
            return {}
        return {
            "public_line": public_line or "先稳住口风。",
            "hidden_line": hidden_line or "暗线暂不外露。",
            "focus": focus or "保住街区影响力",
            "signal": self._sanitize_signal(str(parsed.get("signal", "steady"))),
        }

    def _normalize_company_briefing(self, parsed: dict[str, Any]) -> dict[str, Any]:
        headline = self._sanitize_text(str(parsed.get("headline", "")))
        worker_note = self._sanitize_text(str(parsed.get("worker_note", "")))
        risk_note = self._sanitize_text(str(parsed.get("risk_note", "")))
        if not headline and not worker_note and not risk_note:
            return {}
        return {
            "headline": headline or "公司口风偏紧。",
            "worker_note": worker_note or "工人还在观望。",
            "risk_note": risk_note or "风险暂时可控。",
            "signal": self._sanitize_signal(str(parsed.get("signal", "steady"))),
        }

    def _normalize_pulse_brief(self, parsed: dict[str, Any]) -> dict[str, Any]:
        summary = self._sanitize_text(str(parsed.get("pulse_summary", "")))
        market_note = self._sanitize_text(str(parsed.get("market_note", "")))
        scene_focus = self._sanitize_text(str(parsed.get("scene_focus", "")))
        if not summary:
            return {}
        return {
            "pulse_summary": summary,
            "market_note": market_note or summary,
            "scene_focus": scene_focus or summary,
            "npc_updates": self._normalize_npc_updates(parsed.get("npc_updates", [])),
            "family_updates": self._normalize_family_updates(parsed.get("family_updates", [])),
            "company_updates": self._normalize_company_updates(parsed.get("company_updates", [])),
        }

    def _normalize_npc_updates(self, rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for row in rows[:64]:
            if not isinstance(row, dict):
                continue
            npc_id = str(row.get("id", "")).strip()
            line = self._sanitize_text(str(row.get("line", "")))
            if not npc_id or not line:
                continue
            intended_actions_raw = row.get("intended_actions", {})
            if not isinstance(intended_actions_raw, dict):
                intended_actions_raw = {}
            trade_decision_raw = row.get("trade_decision", {})
            if not isinstance(trade_decision_raw, dict):
                trade_decision_raw = {}
            topic_action_raw = row.get("topic_action", {})
            if not isinstance(topic_action_raw, dict):
                topic_action_raw = intended_actions_raw.get("topic_action", {})
            norm_action_raw = row.get("norm_action", {})
            if not isinstance(norm_action_raw, dict):
                norm_action_raw = intended_actions_raw.get("norm_action", {})
            collective_action_raw = row.get("collective_action", row.get("collective_action_attitude", {}))
            if not isinstance(collective_action_raw, dict):
                collective_action_raw = intended_actions_raw.get("collective_action", {})
            normalized.append(
                {
                    "id": npc_id,
                    "line": line,
                    "stance": self._sanitize_text(str(row.get("stance", "谨慎"))) or "谨慎",
                    "market_tilt": self._sanitize_market_tilt(str(row.get("market_tilt", "neutral"))),
                    "social_message": self._sanitize_text(str(row.get("social_message", line))) or line,
                    "emotions": row.get("emotions", {}) if isinstance(row.get("emotions", {}), dict) else {},
                    "beliefs_update": row.get("beliefs_update", {}) if isinstance(row.get("beliefs_update", {}), dict) else {},
                    "top_goals": [
                        self._sanitize_text(str(value))
                        for value in row.get("top_goals", [])
                        if self._sanitize_text(str(value))
                    ][:4] if isinstance(row.get("top_goals", []), list) else [],
                    "trade_decision": {
                        "action": self._sanitize_text(str(trade_decision_raw.get("action", trade_decision_raw.get("mode", "hold")))).lower() or "hold",
                        "stock_name": self._sanitize_text(str(trade_decision_raw.get("stock_name", trade_decision_raw.get("target", "")))) or "",
                        "quantity": max(0, int(trade_decision_raw.get("quantity", trade_decision_raw.get("shares", 0)) or 0)),
                        "confidence": self._clamp_float(trade_decision_raw.get("confidence", 0.45), 0.0, 1.0),
                        "note": self._sanitize_text(str(trade_decision_raw.get("note", trade_decision_raw.get("reason", "")))) or "",
                    },
                    "topic_action": {
                        "mode": self._sanitize_topic_action_mode(str(topic_action_raw.get("mode", row.get("topic_action_mode", "")))),
                        "topic_id": self._sanitize_text(str(topic_action_raw.get("topic_id", row.get("topic_id", "")))) or "",
                        "intensity": self._clamp_float(topic_action_raw.get("intensity", row.get("topic_intensity", 0.56)), 0.0, 1.0),
                        "note": self._sanitize_text(str(topic_action_raw.get("note", row.get("topic_note", "")))) or "",
                    },
                    "norm_action": {
                        "mode": self._sanitize_norm_action_mode(str(norm_action_raw.get("mode", row.get("norm_action_mode", "")))),
                        "norm_id": self._sanitize_text(str(norm_action_raw.get("norm_id", row.get("norm_id", "")))) or "",
                        "text": self._sanitize_text(str(norm_action_raw.get("text", row.get("norm_text", "")))) or "",
                        "intensity": self._clamp_float(norm_action_raw.get("intensity", row.get("norm_intensity", 0.5)), 0.0, 1.0),
                        "note": self._sanitize_text(str(norm_action_raw.get("note", row.get("norm_note", "")))) or "",
                    },
                    "collective_action": {
                        "mode": self._sanitize_collective_action_mode(str(collective_action_raw.get("mode", row.get("collective_action_mode", "")))),
                        "action_id": self._sanitize_text(str(collective_action_raw.get("action_id", row.get("collective_action_id", "")))) or "",
                        "kind": self._sanitize_collective_kind(str(collective_action_raw.get("kind", row.get("collective_kind", "")))),
                        "intensity": self._clamp_float(collective_action_raw.get("intensity", row.get("collective_intensity", 0.48)), 0.0, 1.0),
                        "note": self._sanitize_text(str(collective_action_raw.get("note", row.get("collective_note", "")))) or "",
                    },
                }
            )
        return normalized

    def _normalize_family_updates(self, rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for row in rows[:12]:
            if not isinstance(row, dict):
                continue
            name = self._sanitize_text(str(row.get("name", "")))
            public_line = self._sanitize_text(str(row.get("public_line", "")))
            hidden_line = self._sanitize_text(str(row.get("hidden_line", "")))
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "public_line": public_line or "先稳住门面。",
                    "hidden_line": hidden_line or "暗线继续压着。",
                    "focus": self._sanitize_text(str(row.get("focus", ""))) or "街区影响力",
                    "signal": self._sanitize_signal(str(row.get("signal", "steady"))),
                }
            )
        return normalized

    def _normalize_company_updates(self, rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for row in rows[:12]:
            if not isinstance(row, dict):
                continue
            company_id = str(row.get("id", "")).strip()
            headline = self._sanitize_text(str(row.get("headline", "")))
            if not company_id:
                continue
            normalized.append(
                {
                    "id": company_id,
                    "headline": headline or "公司口风偏紧。",
                    "worker_note": self._sanitize_text(str(row.get("worker_note", ""))) or "工人还在观望。",
                    "risk_note": self._sanitize_text(str(row.get("risk_note", ""))) or "风险仍在累积。",
                    "signal": self._sanitize_signal(str(row.get("signal", "steady"))),
                }
            )
        return normalized

    def _looks_usable_chinese(self, payload: Any) -> bool:
        critical = self._collect_leaf_strings(payload)
        if not critical:
            return False
        if self._contains_placeholder_schema_value(critical):
            return False
        chinese_hits = 0
        text_hits = 0
        for text in critical:
            stripped = text.strip()
            if not stripped:
                continue
            text_hits += 1
            if re.search(r"[\u4e00-\u9fff]", stripped):
                chinese_hits += 1
        return chinese_hits > 0 and chinese_hits >= max(1, text_hits // 3)

    @staticmethod
    def _contains_placeholder_schema_value(rows: list[str]) -> bool:
        exact_placeholders = {
            "玩家原话",
            "NPC回话",
            "立场",
            "topic_id",
            "信息不足",
            "未知",
        }
        suspicious_phrases = (
            "schema_hint",
            "只返回json",
            "只输出json",
            "字段说明",
            "json对象",
            "markdown",
            "example",
            "format",
            "玩家台词",
            "NPC台词",
        )
        seen_exact = 0
        for value in rows:
            stripped = value.strip()
            if not stripped:
                continue
            if stripped in exact_placeholders:
                seen_exact += 1
                continue
            lowered = stripped.lower()
            if any(phrase in lowered for phrase in suspicious_phrases):
                return True
        return seen_exact >= 2

    def _collect_leaf_strings(self, payload: Any) -> list[str]:
        rows: list[str] = []
        if isinstance(payload, dict):
            for value in payload.values():
                rows.extend(self._collect_leaf_strings(value))
        elif isinstance(payload, list):
            for value in payload:
                rows.extend(self._collect_leaf_strings(value))
        elif isinstance(payload, str):
            rows.append(payload)
        return rows

    @staticmethod
    def _sanitize_text(text: str) -> str:
        cleaned = text.replace("\r", " ").replace("\n", " ").strip()
        cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.replace("：：", "：")
        cleaned = re.sub(r"^(玩家原话|NPC回话|玩家台词|NPC台词|白页|壳仔)\s*[:：]\s*", "", cleaned)
        cleaned = re.sub(r"^(JSON|json)\s*[:：]\s*", "", cleaned)
        return cleaned[:220].strip()

    @staticmethod
    def _sanitize_market_tilt(value: str) -> str:
        lowered = value.strip().lower()
        if lowered in {"bullish", "bearish", "neutral"}:
            return lowered
        return "neutral"

    @staticmethod
    def _sanitize_signal(value: str) -> str:
        lowered = value.strip().lower()
        if lowered in {"steady", "rising", "falling"}:
            return lowered
        return "steady"

    @staticmethod
    def _sanitize_topic_action_mode(value: str) -> str:
        lowered = value.strip().lower()
        mapping = {
            "share": "share",
            "forward": "share",
            "转发": "share",
            "传播": "share",
            "amplify": "amplify",
            "boost": "amplify",
            "放大": "amplify",
            "添油加醋": "amplify",
            "question": "question",
            "doubt": "question",
            "质疑": "question",
            "challenge": "question",
            "deny": "deny",
            "rebut": "deny",
            "驳斥": "deny",
            "否认": "deny",
            "silence": "silence",
            "ignore": "silence",
            "沉默": "silence",
            "回避": "silence",
        }
        return mapping.get(lowered, "")

    @staticmethod
    def _sanitize_norm_action_mode(value: str) -> str:
        lowered = value.strip().lower()
        mapping = {
            "reinforce": "reinforce",
            "support": "reinforce",
            "强化": "reinforce",
            "contest": "contest",
            "challenge": "contest",
            "反对": "contest",
            "seed": "seed",
            "create": "seed",
            "播种": "seed",
            "ignore": "ignore",
            "silence": "ignore",
            "无视": "ignore",
        }
        return mapping.get(lowered, "")

    @staticmethod
    def _sanitize_collective_action_mode(value: str) -> str:
        lowered = value.strip().lower()
        mapping = {
            "hear": "hear",
            "notice": "hear",
            "听说": "hear",
            "support": "support",
            "join": "support",
            "支持": "support",
            "表态": "support",
            "commit": "commit",
            "pledge": "commit",
            "承诺": "commit",
            "attend": "attend",
            "show_up": "attend",
            "到场": "attend",
            "organize": "organize",
            "start": "organize",
            "发起": "organize",
            "组织": "organize",
            "suppress": "suppress",
            "block": "suppress",
            "压制": "suppress",
            "镇压": "suppress",
            "avoid": "avoid",
            "ignore": "avoid",
            "回避": "avoid",
            "沉默": "avoid",
        }
        return mapping.get(lowered, "")

    @staticmethod
    def _sanitize_collective_kind(value: str) -> str:
        lowered = value.strip().lower()
        mapping = {
            "strike": "strike",
            "罢工": "strike",
            "meeting": "meeting",
            "动员会": "meeting",
            "rally": "rally",
            "集会": "rally",
            "party": "party",
            "派对": "party",
        }
        return mapping.get(lowered, "")

    @staticmethod
    def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return minimum
        return max(minimum, min(maximum, number))

    # ------------------------------------------------------------------
    # Care dialogue
    # ------------------------------------------------------------------

    def generate_care_dialogue(
        self, npc_profile: dict[str, Any], player_emotion: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Generate empathetic NPC dialogue based on player's emotional state."""
        return self._request_json(
            task_type="care_dialogue",
            schema_hint=(
                '{"npc_line":"NPC关怀话语","action":"pat_head/offer_food/sit_quietly/speak_kindly/leave_space",'
                '"care_level":"nudge/care/guard","emotion_reflected":"sadness","duration_seconds":8}'
            ),
            system_prompt=(
                "你是《Aociety》中的一名 NPC，注意到玩家当前情绪状态不佳。"
                "根据角色身份、与玩家的关系和当前场景，决定如何回应。"
                "不能出戏，不能自称AI，不能解释你在做什么。"
                "输出简短的一句角色台词和一个关怀动作。"
            ),
            task_prompt="根据玩家情绪和NPC角色信息，生成一句关怀对话和动作。",
            state_prompt={
                "npc_id": npc_profile.get("id", ""),
                "npc_name": npc_profile.get("name", ""),
                "npc_role": npc_profile.get("social_band", ""),
                "npc_district": npc_profile.get("district", ""),
                "player_emotion": player_emotion.get("emotion", "unknown"),
                "player_valence": player_emotion.get("valence", 0.5),
                "player_arousal": player_emotion.get("arousal", 0.0),
                "support_need": player_emotion.get("support_need", 0.0),
                "confidence_gap": player_emotion.get("confidence_gap", 0.0),
                "relationship": npc_profile.get("relationship_with_player", "stranger"),
            },
            normalizer=self._normalize_care_dialogue,
        )

    def _normalize_care_dialogue(self, parsed: dict[str, Any]) -> dict[str, Any]:
        return {
            "npc_line": str(parsed.get("npc_line", "")),
            "action": str(parsed.get("action", "speak_kindly")),
            "care_level": str(parsed.get("care_level", "nudge")),
            "emotion_reflected": str(parsed.get("emotion_reflected", "")),
            "duration_seconds": float(parsed.get("duration_seconds", 5.0)),
        }
