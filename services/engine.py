from __future__ import annotations

import copy
import json
import math
import os
import random
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .ark_client import ArkClient
from .npc_story_overrides import NPC_STORY_OVERRIDES

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TIME_SEGMENTS: list[dict[str, Any]] = [
    {"key": "morning", "label": "早晨", "start": 8 * 60, "end": 12 * 60, "real_seconds": 600},
    {"key": "noon", "label": "中午", "start": 12 * 60, "end": 14 * 60, "real_seconds": 300},
    {"key": "afternoon", "label": "下午", "start": 14 * 60, "end": 18 * 60, "real_seconds": 600},
    {"key": "evening", "label": "晚上", "start": 18 * 60, "end": 24 * 60, "real_seconds": 900},
]
REALTIME_MINUTES_PER_SECOND = 0.4
HOUSE_DEFS: dict[str, dict[str, str]] = {
    "贫民街": {
        "id": "slum_house",
        "title": "山坡租屋",
        "class": "low",
        "district": "贫民街",
        "scene_id": "forest_farm",
        "entry_spawn_id": "farm_gate",
        "anchor_x": "610.0",
        "anchor_y": "560.0",
    },
    "港口": {
        "id": "dock_house",
        "title": "石桥住屋",
        "class": "dock",
        "district": "港口",
        "scene_id": "stonebridge_quarter",
        "entry_spawn_id": "bridge_square",
        "anchor_x": "860.0",
        "anchor_y": "720.0",
    },
    "工厂区": {
        "id": "factory_house",
        "title": "厂房宿舍",
        "class": "industrial",
        "district": "工厂区",
        "scene_id": "watermill_yard",
        "entry_spawn_id": "mill_gate",
        "anchor_x": "2240.0",
        "anchor_y": "1120.0",
    },
    "交易所": {
        "id": "exchange_house",
        "title": "账房公寓",
        "class": "merchant",
        "district": "交易所",
        "scene_id": "rune_tower",
        "entry_spawn_id": "tower_steps",
        "anchor_x": "1370.0",
        "anchor_y": "610.0",
    },
}

SUBREGION_ROUTE_POINTS: dict[str, list[tuple[float, float]]] = {
    "forest_farm": [(430.0, 320.0), (560.0, 300.0), (700.0, 360.0), (610.0, 540.0)],
    "courtyard_garden": [(410.0, 700.0), (560.0, 760.0), (700.0, 860.0), (520.0, 930.0)],
    "wild_path": [(250.0, 1470.0), (420.0, 1510.0), (600.0, 1430.0), (740.0, 1570.0)],
    "shipyard_workshop": [(980.0, 1510.0), (1190.0, 1610.0), (1450.0, 1530.0), (1600.0, 1660.0)],
    "canal_harbor": [(1080.0, 980.0), (1260.0, 1080.0), (1440.0, 980.0), (1490.0, 1180.0)],
    "stonebridge_quarter": [(700.0, 720.0), (860.0, 720.0), (990.0, 820.0), (820.0, 920.0)],
    "watermill_yard": [(1920.0, 980.0), (2140.0, 1110.0), (2310.0, 1220.0), (2050.0, 1320.0)],
    "stoneyard_workcamp": [(2350.0, 1400.0), (2520.0, 1460.0), (2690.0, 1530.0), (2440.0, 1600.0)],
    "clocktower_market": [(2050.0, 220.0), (2240.0, 300.0), (2440.0, 330.0), (2640.0, 260.0)],
    "rune_tower": [(1220.0, 400.0), (1370.0, 610.0), (1530.0, 520.0), (1480.0, 310.0)],
    "church_graveyard": [(1950.0, 540.0), (2100.0, 500.0), (2240.0, 610.0), (2380.0, 660.0)],
}

HOUSE_PATROL_POINTS: dict[str, list[tuple[float, float]]] = {
    "slum_house": [(592.0, 582.0), (630.0, 584.0), (574.0, 620.0), (648.0, 618.0)],
    "dock_house": [(840.0, 736.0), (884.0, 738.0), (824.0, 774.0), (902.0, 772.0)],
    "factory_house": [(2214.0, 1140.0), (2258.0, 1142.0), (2202.0, 1178.0), (2270.0, 1176.0)],
    "exchange_house": [(1348.0, 628.0), (1394.0, 628.0), (1338.0, 666.0), (1402.0, 664.0)],
}

COLLECTIVE_GATHER_POINTS: dict[str, dict[str, dict[str, Any]]] = {
    "贫民街": {
        "meeting": {"location_id": "charity_board", "title": "山坡告示牌", "subregion_id": "forest_farm", "subregion_name": "农坡地", "x": 240.0, "y": 360.0},
        "rally": {"location_id": "forest_stall", "title": "街口风声", "subregion_id": "courtyard_garden", "subregion_name": "鱼市前街", "x": 720.0, "y": 900.0},
        "party": {"location_id": "rag_broker", "title": "巷口杂铺", "subregion_id": "courtyard_garden", "subregion_name": "鱼市前街", "x": 430.0, "y": 760.0},
    },
    "港口": {
        "meeting": {"location_id": "harbor_broker", "title": "运河耳报", "subregion_id": "canal_harbor", "subregion_name": "运河码头", "x": 1260.0, "y": 1080.0},
        "strike": {"location_id": "dock_labor", "title": "船坞工牌", "subregion_id": "shipyard_workshop", "subregion_name": "船坞工坊", "x": 1430.0, "y": 1540.0},
        "rally": {"location_id": "bridge_notice", "title": "石桥留言牌", "subregion_id": "canal_harbor", "subregion_name": "运河码头", "x": 980.0, "y": 1000.0},
        "party": {"location_id": "dock_house", "title": "石桥住屋", "subregion_id": "stonebridge_quarter", "subregion_name": "石桥街口", "x": 860.0, "y": 720.0},
    },
    "工厂区": {
        "meeting": {"location_id": "rumor_post", "title": "货场小报", "subregion_id": "stoneyard_workcamp", "subregion_name": "石料工地", "x": 2520.0, "y": 1450.0},
        "strike": {"location_id": "mill_notice", "title": "机房白板", "subregion_id": "watermill_yard", "subregion_name": "磨坊前院", "x": 2070.0, "y": 980.0},
        "rally": {"location_id": "foreman_desk", "title": "工头值台", "subregion_id": "watermill_yard", "subregion_name": "磨坊前院", "x": 1940.0, "y": 1200.0},
        "party": {"location_id": "canteen_supply", "title": "厂区配给", "subregion_id": "watermill_yard", "subregion_name": "磨坊前院", "x": 1850.0, "y": 1440.0},
    },
    "交易所": {
        "meeting": {"location_id": "family_registry", "title": "会客前厅", "subregion_id": "rune_tower", "subregion_name": "塔楼会客厅", "x": 1120.0, "y": 620.0},
        "rally": {"location_id": "chapel_notice", "title": "广场耳语", "subregion_id": "church_graveyard", "subregion_name": "教堂墓园", "x": 2040.0, "y": 520.0},
        "party": {"location_id": "exchange_board", "title": "交易牌价", "subregion_id": "clocktower_market", "subregion_name": "钟楼市集", "x": 2190.0, "y": 220.0},
    },
}

SOCIAL_BAND_SUBREGIONS: dict[str, dict[str, str]] = {
    "贫民街": {
        "elite": "forest_farm",
        "authority": "forest_farm",
        "manager": "forest_farm",
        "finance": "courtyard_garden",
        "trade": "courtyard_garden",
        "media": "courtyard_garden",
        "organizer": "courtyard_garden",
        "labor": "courtyard_garden",
        "precariat": "wild_path",
        "resident": "wild_path",
    },
    "港口": {
        "elite": "canal_harbor",
        "authority": "canal_harbor",
        "manager": "canal_harbor",
        "finance": "canal_harbor",
        "trade": "stonebridge_quarter",
        "media": "stonebridge_quarter",
        "organizer": "shipyard_workshop",
        "labor": "shipyard_workshop",
        "precariat": "stonebridge_quarter",
        "resident": "stonebridge_quarter",
    },
    "工厂区": {
        "elite": "watermill_yard",
        "authority": "watermill_yard",
        "manager": "watermill_yard",
        "finance": "watermill_yard",
        "trade": "stoneyard_workcamp",
        "media": "watermill_yard",
        "organizer": "stoneyard_workcamp",
        "labor": "stoneyard_workcamp",
        "precariat": "stoneyard_workcamp",
        "resident": "stoneyard_workcamp",
    },
    "交易所": {
        "elite": "rune_tower",
        "authority": "rune_tower",
        "manager": "rune_tower",
        "finance": "clocktower_market",
        "trade": "clocktower_market",
        "media": "church_graveyard",
        "organizer": "church_graveyard",
        "labor": "clocktower_market",
        "precariat": "clocktower_market",
        "resident": "church_graveyard",
    },
}

SOCIAL_BAND_WHITELIST: dict[str, set[str]] = {
    "elite": {"elite", "authority", "manager", "finance", "media"},
    "authority": {"elite", "authority", "manager", "finance", "media", "trade"},
    "manager": {"elite", "authority", "manager", "finance", "media", "trade", "organizer"},
    "finance": {"elite", "authority", "manager", "finance", "media", "trade"},
    "trade": {"authority", "manager", "finance", "trade", "media", "labor", "precariat", "resident"},
    "media": {"elite", "authority", "manager", "finance", "trade", "media", "organizer", "labor", "precariat", "resident"},
    "organizer": {"manager", "media", "organizer", "labor", "precariat", "trade", "resident"},
    "labor": {"trade", "media", "organizer", "labor", "precariat", "resident"},
    "precariat": {"trade", "media", "organizer", "labor", "precariat", "resident"},
    "resident": {"trade", "media", "organizer", "labor", "precariat", "resident"},
}

NPC_WORK_SUBREGION_OVERRIDES: dict[str, str] = {
    "npc_07": "church_graveyard",
    "npc_09": "rune_tower",
    "npc_10": "rune_tower",
    "npc_11": "rune_tower",
    "npc_14": "clocktower_market",
    "npc_15": "clocktower_market",
    "npc_16": "rune_tower",
    "npc_17": "clocktower_market",
    "npc_22": "rune_tower",
    "npc_35": "church_graveyard",
}


@dataclass
class ActionResult:
    message: str
    world_state: dict[str, Any]


class WorldEngine:
    def __init__(self, pulse_interval_seconds: int = 60) -> None:
        self.pulse_interval_seconds = pulse_interval_seconds
        self.random = random.Random(11)
        self.lock = threading.RLock()
        self.ark = ArkClient()
        self.goods_defs = self._load_json("goods.json")
        self.stock_defs = self._load_json("stocks.json")
        self.event_defs = self._load_json("events.json")
        self.npc_defs = self._load_json("npcs.json")
        self.npc_prompt_defs = self._load_json("npc_prompt_profiles.json")
        self.family_defs = self._load_json("families.json")
        self.company_defs = self._load_json("companies.json")
        self.residence_defs = self._load_json("residences.json")
        self.macro_defaults = self._load_json("macro.json")
        self.districts_defs = self._load_json("districts.json")
        self.dialogue_templates = self._load_json("dialogue_templates.json")
        self.demo_flow = self._load_json("demo_flow.json")
        self.task_defs = self._load_json("tasks.json")
        self.npc_path_plans = self._load_json_optional("npc_path_plans.json", {})
        self.poi_slot_defs = self._load_json_optional("poi_slots.json", {})
        self.state: dict[str, Any] = {}
        self._snapshot_cache: dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        with self.lock:
            goods = []
            for good in self.goods_defs:
                item = copy.deepcopy(good)
                item["current_price"] = item["base_price"]
                item["price_trend"] = "平"
                goods.append(item)

            stocks = []
            for stock in self.stock_defs:
                item = copy.deepcopy(stock)
                item["current_price"] = item["base_price"]
                item["market_sentiment"] = "谨慎"
                item["previous_close"] = int(item.get("base_price", 10))
                item["reference_price"] = float(item.get("base_price", 10))
                item["issued_shares"] = int(item.get("issued_shares", self._stock_issued_shares(item)))
                item["free_float"] = int(item.get("free_float", max(1, round(item["issued_shares"] * 0.56))))
                item["trade_volume"] = 0
                item["float_turnover"] = 0.0
                item["net_cash_flow"] = 0.0
                item["last_trade_price"] = int(item["current_price"])
                item["change_amount"] = 0
                item["change_pct"] = 0.0
                item["market_cap"] = int(item["issued_shares"] * item["current_price"])
                item["display_name"] = str(item.get("display_name", item.get("name", "")))
                item["ticker"] = str(item.get("ticker", item.get("id", ""))).upper()
                stocks.append(item)

            families = copy.deepcopy(self.family_defs)
            companies = copy.deepcopy(self.company_defs)
            for family in families:
                family["sector_focus"] = family.get("sector_focus", family["type"])
                family["hidden_action"] = family.get("hidden_action", "暂未出手")
            for family in families:
                self._bootstrap_family(family)
            for company in companies:
                self._bootstrap_company(company)
            districts = copy.deepcopy(self.districts_defs)
            subregions = self._flatten_subregions(districts)
            subregion_lookup = {row["id"]: row for row in subregions}
            npcs = copy.deepcopy(self.npc_defs)
            residence_occupancy: dict[str, int] = {}
            for index, npc in enumerate(npcs):
                npc_id = str(npc.get("id", ""))
                story_override = copy.deepcopy(NPC_STORY_OVERRIDES.get(npc_id, {}))
                prompt_override = story_override.pop("prompt_profile", {}) if isinstance(story_override, dict) else {}
                if isinstance(story_override, dict):
                    npc.update(story_override)
                base_prompt_profile = copy.deepcopy(self.npc_prompt_defs.get(npc_id, {}))
                if isinstance(prompt_override, dict):
                    base_prompt_profile.update(prompt_override)
                npc["prompt_profile"] = base_prompt_profile
                npc["social_band"] = self._npc_social_band(npc)
                npc["current_goal"] = npc.get("current_goal", "守住今天")
                npc["mood"] = npc.get("mood", "wary")
                npc["stance"] = npc.get("stance", "观望")
                npc["action_tendency"] = npc.get("action_tendency", "低头做事")
                npc["target"] = npc.get("target", npc["district"])
                npc["broadcast_intent"] = "low"
                npc["emotion_delta"] = {"fear": 0, "greed": 0}
                npc["speech_lines"] = []
                npc["cadence_seconds"] = 4.0
                npc["cooldown_until"] = 0.0
                npc["subregion_id"] = str(npc.get("subregion_id", ""))
                subregion_meta = subregion_lookup.get(npc["subregion_id"], {})
                npc["subregion_name"] = str(
                    npc.get("subregion_name", subregion_meta.get("name", ""))
                )
                preferred_work_subregion = self._preferred_work_subregion(npc)
                work_subregion_id = str(npc.get("work_subregion_id", preferred_work_subregion or npc["subregion_id"]))
                work_subregion_meta = subregion_lookup.get(work_subregion_id, subregion_meta)
                work_anchor_x, work_anchor_y, work_anchor_slot = self._work_anchor_for_npc(npc, work_subregion_id)
                npc["work_subregion_id"] = work_subregion_id
                npc["work_subregion_name"] = str(npc.get("work_subregion_name", work_subregion_meta.get("name", npc["subregion_name"])))
                npc["work_anchor_slot"] = work_anchor_slot
                npc["work_x"] = work_anchor_x
                npc["work_y"] = work_anchor_y
                residence = self._residence_for_npc(npc, index, residence_occupancy, subregion_lookup)
                npc["home_building_id"] = str(residence.get("id", ""))
                npc["home_building_title"] = str(residence.get("title", "屋子"))
                npc["home_subregion_id"] = str(residence.get("subregion_id", npc["subregion_id"]))
                npc["home_subregion_name"] = str(subregion_lookup.get(npc["home_subregion_id"], {}).get("name", npc["subregion_name"]))
                npc["home_mode"] = str(npc.get("home_mode", "doorstep"))
                npc["home_slot"] = int(residence.get("assigned_slot", 0))
                npc["home_id"] = npc["home_building_id"]
                npc["home_label"] = npc["home_building_title"]
                npc["home_class"] = str(residence.get("class", "low"))
                home_x, home_y = self._residence_anchor(residence, npc["home_slot"], "door")
                npc["home_indoor_x"], npc["home_indoor_y"] = self._residence_anchor(residence, npc["home_slot"], "indoor")
                npc["home_x"] = home_x
                npc["home_y"] = home_y
                npc["activity"] = "working"
                npc["home_state"] = "away"
                npc["indoor_activity"] = "away"
                npc["collective_action_id"] = ""
                npc["collective_role"] = ""
                npc["response_mode"] = ""
                npc["lights_on"] = False
                npc["schedule_note"] = "白天还在外面奔忙。"
                npc["schedule_role"] = self._schedule_role_for_npc(npc)

            for npc in npcs:
                self._bootstrap_npc(npc, companies)

            self.state = {
                "day": 1,
                "clock_minutes": 8 * 60,
                "time_period": "morning",
                "light_level": 0.95,
                "weather": {"kind": "sunny", "label": "晴天", "intensity": 0.12, "slot": -1, "day": 1},
                "last_tick_at": time.time(),
                "realtime_minute_buffer": 0.0,
                "player": {
                    "cash": 1_000_000,
                    "credit": 20,
                    "health": 100,
                    "reputation": 5,
                    "class_position": "底层",
                    "story_route": "",
                    "financial_route": "",
                    "route_intro_pending": True,
                    "route_selected_at": "",
                    "stock_margin_debt": 0,
                    "stock_short_positions": {"海藻重工": {"quantity": 0, "avg_price": 0.0}, "市政债券": {"quantity": 0, "avg_price": 0.0}, "龟甲物流": {"quantity": 0, "avg_price": 0.0}},
                    "stock_account_locked": False,
                    "stock_account_lock_reason": "",
                    "stock_liquidation_pending": False,
                    "stock_liquidation_note": "",
                    "stock_liquidation_due_tick": 0,
                    "attitude_style": "respectful",
                    "last_talk_approach": "cautious",
                    "goods_inventory": {"面包": 1, "煤": 0, "罐头": 0},
                    "stock_holdings": {"海藻重工": 0, "市政债券": 0, "龟甲物流": 0},
                    "reputation_tracks": {"FC": 10, "FB": 5, "SN": 20},
                    "shadow_reputation": {"S_WWI": 15, "S_DBH": 10, "S_NAC": 20, "SUI": 15, "ST": 1.0, "WL": 1},
                    "rumors": [],
                    "family_relations": {"海藻资本": 0, "镇政府": 0, "龟甲家族": 0, "居民与底层": 0, "影子中枢": 0},
                    "collective_profile": {
                        "support_count": 0,
                        "mediate_count": 0,
                        "suppress_count": 0,
                        "worker_standing": 0.0,
                        "capital_standing": 0.0,
                        "government_standing": 0.0,
                        "public_standing": 0.0,
                        "dominant_mode": "observe",
                        "stance_label": "看风向的人",
                        "consecutive_mode": "",
                        "consecutive_count": 0,
                        "history": [],
                    },
                    "task_progress": {},
                    "active_task_id": "",
                    "completed_tasks": [],
                    "hunger": 100.0,
                    "stamina": 100.0,
                },
                "goods": goods,
                "stocks": stocks,
                "stock_trade_tape": [],
                "stock_holder_registry": {},
                "stock_exchange_feedback": "",
                "stock_exchange_view": {},
                "stock_price_history": {str(row["name"]): [int(row["current_price"])] * 24 for row in stocks},
                "story_metrics": {
                    "sam_revolution_fund": 0,
                    "sam_tax_total": 0,
                    "player_trading_fees": 0,
                    "reputation": {"FC": 10, "FB": 5, "SN": 20},
                    "shadow_reputation": {"S_WWI": 15, "S_DBH": 10, "S_NAC": 20, "SUI": 15, "ST": 1.0, "WL": 1},
                },
                "families": families,
                "companies": companies,
                "districts": districts,
                "subregions": subregions,
                "current_subregion": "",
                "macro": copy.deepcopy(self.macro_defaults),
                "npcs": npcs,
                "ambient_speeches": {},
                "local_broadcasts": [],
                "rumor_log": [],
                "local_rumor": [],
                "topic_registry": [],
                "active_topics": [],
                "topic_decay_tick": 8 * 60,
                "norm_registry": [],
                "active_norms": [],
                "norm_decay_tick": 8 * 60,
                "collective_action_registry": [],
                "active_collective_actions": [],
                "collective_action_decay_tick": 8 * 60,
                "collective_outcomes": [],
                "collective_followups": [],
                "district_topic": {},
                "city_news": [],
                "company_states": [],
                "family_moves": [],
                "institution_actions": [],
                "npc_truth_profile": {},
                "market_pressure": {
                    "goods": {row["name"]: 0.0 for row in goods},
                    "stocks": {row["name"]: 0.0 for row in stocks},
                    "families": {row["name"]: 0.0 for row in families},
                },
                "district_signals": {
                    district["name"]: {
                        "trade_heat": 0.0,
                        "labor_heat": 0.0,
                        "gossip": 0.0,
                        "fear": 0.0,
                        "liquidity": 0.0,
                    }
                    for district in districts
                },
                "global_news": [],
                "headline_news": [],
                "pending_events": [],
                "story_timeline": {"fired": [], "log": []},
                "npc_highlights": [],
                "npc_cards": [],
                "ending_state": {},
                "house_states": {},
                "macro_summary": {},
                "quick_hud": {},
                "talk_topics": [],
                "demo_metrics": {
                    "work_actions": 0,
                    "goods_trades": 0,
                    "stock_trades": 0,
                    "intel_actions": 0,
                    "npc_talks": 0,
                    "days_ended": 0,
                    "ai_pulses": 0,
                },
                "task_board": copy.deepcopy(self.task_defs),
                "last_dialogue": {},
                "scene_observation": {},
                "scene_director_note": "",
                "llm_pulse_summary": "",
                "llm_market_note": "",
                "llm_scene_focus": "",
                "npc_spin_map": {},
                "family_briefings": {},
                "company_briefings": {},
                "npc_brief_history": {},
                "family_brief_history": {},
                "company_brief_history": {},
                "pulse_journal": [],
                "last_scene_capture_at": "未收到",
                "last_pulse_at": "未触发",
                "last_day_end_at": "未触发",
            }
            self._seed_norm_registry()
            self._seed_global_news()
            self._apply_clock_state()
            self._apply_npc_schedule()
            self._generate_ai_pulse(trigger="boot")

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            if self._route_choice_required():
                self.state["last_tick_at"] = time.time()
                self._refresh_derived_views()
                return copy.deepcopy(self.state)
            self._advance_realtime_clock()
            self._refresh_derived_views()
            return copy.deepcopy(self.state)

    def snapshot_cached(self) -> dict[str, Any]:
        cached = copy.deepcopy(self._snapshot_cache)
        if cached:
            return cached
        return self.snapshot()

    def _snapshot_after_refresh(self, rebuild_agent_prompts: bool = True) -> dict[str, Any]:
        self._check_stock_account_state(trigger="refresh")
        self._refresh_derived_views(rebuild_agent_prompts=rebuild_agent_prompts)
        cached = copy.deepcopy(self._snapshot_cache)
        if cached:
            return cached
        return copy.deepcopy(self.state)

    def action(self, action_type: str, district: str, payload: dict[str, Any] | None = None) -> ActionResult:
        payload = payload or {}
        with self.lock:
            if action_type == "choose_route":
                return self._apply_route_selection(str(payload.get("route", "")))
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                title = str(ending.get("title", "结局已触发"))
                body = str(ending.get("body", "当前存档已经进入失败结局。"))
                return ActionResult(f"{title}：{body}", self.snapshot_cached())
            self._advance_realtime_clock()
            self._advance_clock(16)
            self._check_stock_account_state(trigger=action_type)
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
            match action_type:
                case "work":
                    return self._do_work(district)
                case "gather_info":
                    return self._gather_info(district)
                case "rest":
                    return self._rest_at_home(district, payload)
                case "cook_meal":
                    return self._cook_meal(district, payload)
                case "search_home":
                    return self._search_home(district, payload)
                case "review_ledger":
                    return self._review_ledger(district, payload)
                case "buy_goods":
                    return self._trade_good(payload["good_name"], int(payload.get("quantity", 1)), 1, payload)
                case "sell_goods":
                    return self._trade_good(payload["good_name"], int(payload.get("quantity", 1)), -1, payload)
                case "buy_stock":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_v2(stock_ref, int(payload.get("quantity", 1)), 1, int(payload.get("leverage", 1)))
                case "sell_stock":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_v2(stock_ref, int(payload.get("quantity", 1)), -1, int(payload.get("leverage", 1)))
                case "short_stock":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_short_v2(stock_ref, int(payload.get("quantity", 1)), 1, int(payload.get("leverage", 1)))
                case "cover_short":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_short_v2(stock_ref, int(payload.get("quantity", 1)), -1, int(payload.get("leverage", 1)))
                case "gift_money":
                    return self._gift_money_to_npc(str(payload.get("npc_id", "")), int(payload.get("amount", 0)), district)
                case "buy_intel":
                    return self._buy_intel_from_npc(str(payload.get("npc_id", "")), int(payload.get("amount", 0)), str(payload.get("topic_id", "")), district)
                case "fake_boom_report":
                    return self._run_stock_special_operation("fake_boom_report")
                case "manufacture_dock_conflict":
                    return self._run_stock_special_operation("manufacture_dock_conflict")
                case "emergency_bond_issue":
                    return self._run_stock_special_operation("emergency_bond_issue")
                case "hostile_takeover":
                    return self._run_stock_special_operation("hostile_takeover")
                case "policy_shield":
                    return self._run_stock_special_operation("policy_shield")
                case "hire_scar_cover":
                    return self._run_stock_special_operation("hire_scar_cover")
                case "collective_intervene":
                    return self._intervene_collective(district, payload)
                case "accept_task":
                    return self._accept_task(payload["task_id"])
                case "claim_task":
                    return self._claim_task(payload["task_id"])
                case _:
                    return ActionResult("未识别的行动。", self.snapshot())

    def end_day(self) -> ActionResult:
        with self.lock:
            self._advance_realtime_clock()
            self._check_stock_account_state(trigger="end_day")
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
            self._run_livelihood_tick("end_day")
            self._settle_company_operations("end_day")
            previous_clock = int(self.state.get("clock_minutes", 8 * 60))
            self.state["day"] += 1
            self.state["clock_minutes"] = 6 * 60 + self.random.randint(0, 45)
            self._apply_clock_state()
            overnight_minutes = max(1, (24 * 60 - previous_clock) + int(self.state.get("clock_minutes", 6 * 60)))
            self._apply_collective_followups(overnight_minutes)
            self._decay_district_signals()
            event = self._pick_event_for_day()
            self.state["pending_events"] = [event]
            self._apply_macro_shift(event)
            self._apply_goods_shift(event)
            self._apply_stock_shift(event)
            self._apply_family_shift(event)
            self._apply_district_shift(event)
            self._apply_institution_actions("end_day")
            self._append_news_for_event(event)
            self.state["last_day_end_at"] = self._now_label()
            self.state["demo_metrics"]["days_ended"] = int(self.state["demo_metrics"].get("days_ended", 0)) + 1
            self._generate_ai_pulse(trigger="end_day")
            self._apply_npc_schedule()
            self._refresh_derived_views()
            return ActionResult("黄铜钟响过，城市进入下一天。", self.snapshot())

    def ai_pulse(
        self,
        trigger: str = "scheduled",
        scene_observation: dict[str, Any] | None = None,
        allow_live_llm: bool | None = None,
    ) -> ActionResult:
        with self.lock:
            self._advance_realtime_clock()
            self._advance_clock(6)
            self._check_stock_account_state(trigger=trigger)
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
            self._run_livelihood_tick(trigger)
            self._settle_company_operations(trigger)
            self._apply_institution_actions(trigger)
            if scene_observation:
                self._record_scene_observation(scene_observation)
            self.state["demo_metrics"]["ai_pulses"] = int(self.state["demo_metrics"].get("ai_pulses", 0)) + 1
            self._generate_ai_pulse(trigger=trigger, allow_live_llm_override=allow_live_llm)
            var_allow_social_llm = self._allow_live_pulse_llm(trigger) if allow_live_llm is None else bool(allow_live_llm)
            self._run_agent_social_turns(scene_observation or {}, allow_llm=var_allow_social_llm)
            self._apply_intraday_market_move(reason="ai_pulse", decay=0.72)
            self._decay_district_signals()
            self._refresh_derived_views()
            return ActionResult("街头耳语刷新了。", self.snapshot())

    def reset_world(self) -> ActionResult:
        self.reset()
        return ActionResult("世界已重置回第一天清晨。", self.snapshot())

    def probe_ai(self) -> ActionResult:
        probe_result = self.ark.probe()
        message = probe_result["message"]
        snapshot = self.snapshot()
        snapshot["probe"] = probe_result
        return ActionResult(message, snapshot)

    def player_talk(
        self,
        npc_id: str,
        district: str,
        topic_id: str = "",
        approach: str = "cautious",
        intent: str = "",
        player_input: str = "",
        scene_observation: dict[str, Any] | None = None,
    ) -> ActionResult:
        dialogue = None
        llm_payload: dict[str, Any] | None = None
        live_observation: dict[str, Any] = {}
        latency_ms = 0
        execute_contract: dict[str, Any] | None = None
        # UE demo interactions are explicit, visible user-facing requests. They
        # must not fall back to rule text because the background simulation has
        # already consumed an NPC's daily agent budget.
        force_demo_llm = topic_id in {
            "player_interaction",
            "ambient_resident_chat",
            "ue_demo",
        }
        with self.lock:
            npc = self._find_npc(npc_id)
            if not npc:
                return ActionResult("你身边没有这个角色。", self.snapshot())
            if scene_observation:
                self._record_scene_observation(scene_observation)

            district = district or str(npc["district"])
            player_input = str(player_input or "").strip()
            contract_result = self._maybe_handle_action_contract_layer(npc, district, player_input)
            if contract_result is not None:
                if isinstance(contract_result, dict) and contract_result.get("_execute", False):
                    execute_contract = contract_result
                else:
                    return contract_result
            live_observation = copy.deepcopy(self.state.get("scene_observation", {}))
            self._refresh_derived_views()
            topic = self._select_player_talk_topic(npc, topic_id, district, player_input, intent)
            truth_profile = self._truth_metrics_for_topic(npc, topic, approach, intent)
            trust_delta, intel_strength, npc_openness = self._evaluate_talk_approach(npc, topic, approach)
            favorability_state = self._npc_favorability_state(npc)
            npc["last_spoken_topic_id"] = str(topic.get("id", ""))
            npc["last_spoken_topic_label"] = str(topic.get("label", ""))
            self._queue_agent_task(npc, "player_talk", str(topic.get("label", "街头风声")))
            if force_demo_llm or self._consume_agent_budget(npc, "player_talk", 1):
                npc_snapshot = copy.deepcopy(npc)
                llm_payload = {
                    "speaker": {
                        "name": "玩家",
                        "district": district,
                        "role": "玩家",
                        "mood": "wary",
                        "current_goal": topic.get("label", "街头风声"),
                    },
                    "listener": self._dialogue_listener_brief(npc_snapshot),
                    "district": district,
                    "trigger": "玩家搭话",
                    "topic": topic,
                    "approach": approach,
                    "intent": intent,
                    "player_input": player_input,
                    "truth_profile": truth_profile,
                    "favorability_state": favorability_state,
                    "listener_sections": self._dialogue_listener_sections(npc_snapshot, topic),
                    "relationship_memory": {
                        "player_memory": {
                            "talk_count": int(dict(npc_snapshot.get("player_memory", {})).get("talk_count", 0)),
                            "cash_gift_total": int(dict(npc_snapshot.get("player_memory", {})).get("cash_gift_total", 0)),
                            "friendly_count": int(dict(npc_snapshot.get("player_memory", {})).get("friendly_count", 0)),
                            "hardball_count": int(dict(npc_snapshot.get("player_memory", {})).get("hardball_count", 0)),
                            "bought_over": bool(dict(npc_snapshot.get("player_memory", {})).get("bought_over", False)),
                            "follows_player": bool(dict(npc_snapshot.get("player_memory", {})).get("follows_player", False)),
                        },
                        "recent_events": copy.deepcopy(list(npc_snapshot.get("relationship_memory", []))[:1]),
                        "conversation_history": self._dialogue_history_view(npc_snapshot, counterpart_id="player", limit=1),
                        "local_memory": self._local_memory_view(npc_snapshot, counterpart_id="player", topic_id=str(topic.get("id", "")), limit=1),
                    },
                    "scene_observation": {
                        "current_district": district,
                        "scene_context": live_observation.get("scene_context", {}),
                        "screenshot_b64": live_observation.get("screenshot_b64", ""),
                    },
                }
        if llm_payload is not None:
            started_at = time.perf_counter()
            dialogue = self.ark.generate_dialogue_turn(llm_payload)
            latency_ms = max(1, int((time.perf_counter() - started_at) * 1000))
        if execute_contract is not None:
            action_type = str(execute_contract.get("action_type", "")).strip()
            payload = dict(execute_contract.get("payload", {}) or {})
            contract_district = str(execute_contract.get("district", "")).strip() or district
            npc_name = str(execute_contract.get("npc_name", "")).strip() or str(execute_contract.get("npc_name_fallback", "")).strip() or "对方"
            player_line = str(execute_contract.get("player_line", "")).strip()
            result = self.action(action_type, contract_district, payload)
            world_state = result.world_state
            npc_line = f"{npc_name}：行，按你说的办。"
            if result.message:
                npc_line = f"{npc_line}\n[{result.message}]"
            world_state["last_dialogue"] = {
                "title": f"行动契约：{self._action_contract_label(action_type)}",
                "tone": "conversation",
                "lines": [player_line, npc_line],
                "layer": "action_contract",
                "contract": {
                    "status": "executed",
                    "action_type": action_type,
                    "district": contract_district,
                    "payload": payload,
                    "message": str(result.message or ""),
                },
                "npc_id": str(execute_contract.get("npc_id", "")),
                "npc_name": npc_name,
                "district": contract_district,
                "player_input": player_line,
                "response_state": "action_contract_executed",
            }
            return ActionResult(result.message, world_state)
        with self.lock:
            npc = self._find_npc(npc_id)
            if not npc:
                return ActionResult("你身边没有这个角色。", self.snapshot())
            player = self.state["player"]
            player_input = player_input.strip()
            lines = [str(line) for line in dialogue.get("lines", [])[:2]] if dialogue else []
            stance = str(dialogue.get("stance", truth_profile.get("bias", npc.get("stance", "观望")))) if dialogue else str(
                truth_profile.get("bias", npc.get("stance", "观望"))
            )
            revealed_topic_ids = [str(value) for value in dialogue.get("revealed_topic_ids", []) if str(value).strip()] if dialogue else []
            if len(lines) < 2:
                lines = self._rule_player_talk_lines(npc, topic, approach, npc_openness, intent=intent, player_input=player_input)
            if player_input:
                if not lines:
                    lines = [player_input, ""]
                else:
                    lines[0] = player_input
            if len(lines) < 2:
                fallback_lines = self._rule_player_talk_lines(npc, topic, approach, npc_openness, intent=intent, player_input=player_input)
                lines = [player_input, fallback_lines[1]] if player_input else fallback_lines
            fallback_reply = self._rule_player_talk_lines(npc, topic, approach, npc_openness, intent=intent, player_input=player_input)[1]
            lines[1] = self._normalize_spoken_line(str(npc.get("name", "")), lines[1], fallback_reply)
            hint_flags = self._player_talk_hint_flags(player_input, intent)
            if player_input and bool(hint_flags.get("greeting", False)) and not bool(hint_flags.get("market", False)) and not bool(hint_flags.get("actor", False)):
                market_tokens = ["盘", "股", "仓", "价格", "杠杆", "做局", "交易", "行情", "拉盘", "利息"]
                if len(player_input) <= 8 or any(token in lines[1] for token in market_tokens):
                    npc_name_clean = str(npc.get("name", "对方"))
                    district_clean = str(npc.get("district", "这片街区"))
                    lines[1] = f"{npc_name_clean}：你好。先别紧张，我在{district_clean}这边跑腿。你想先聊近况、身份，还是哪件麻烦事？"
            render_lines = self._dialogue_render_lines(lines, str(npc.get("name", "对方")))
            if dialogue:
                self._remember_agent_output(npc, "player_talk", lines[1])

            npc["speech_lines"] = [lines[1], *npc["speech_lines"][:2]]
            npc["stance"] = stance
            npc["player_relation"] = int(npc.get("player_relation", 0)) + trust_delta
            npc["player_trust"] = max(0.0, min(100.0, float(npc.get("player_trust", 0.0)) + trust_delta * 2.4))
            player["attitude_style"] = approach
            player["last_talk_approach"] = approach
            player["credit"] = min(100, int(player["credit"]) + 1)
            player["reputation"] = min(100, int(player["reputation"]) + (1 if npc["class"] != "底层" and trust_delta > 0 else 0))
            npc["memory_tags"] = self._push_memory(npc["memory_tags"], "talk:player")
            npc["heard_topic_ids"] = self._push_memory(npc.get("heard_topic_ids", []), str(topic.get("id", "")))
            self.state["demo_metrics"]["npc_talks"] = int(self.state["demo_metrics"].get("npc_talks", 0)) + 1
            intel = self._build_intel_packet_from_topic(topic, npc, district)
            effective_strength = max(0.0, intel_strength * (0.45 + float(truth_profile.get("truthfulness", 0.5)) * 0.8))
            intel = self._spin_intel_packet(intel, npc, truth_profile, topic)
            promote_news = effective_strength >= 0.66 or str(topic.get("kind", "")) in {"asset", "family", "company", "institution", "panic"}
            if effective_strength > 0.12:
                self._apply_intel_packet(intel, to_player=True, promote_news=promote_news, intensity=effective_strength)
            self._remember_player_talk(npc, topic, approach, intent, trust_delta, effective_strength)
            self._append_dialogue_history(
                npc,
                "player",
                "玩家",
                lines[0],
                lines[1],
                str(topic.get("id", "")),
                str(topic.get("label", "")),
                "玩家搭话",
                "player_talk",
                "player",
            )
            memory_summary = f"玩家这次围着{topic.get('label', '街头风声')}来问“{lines[0]}”，你回了：{lines[1]}"
            self._remember_local_memory(
                npc,
                kind="player_talk",
                summary=memory_summary,
                counterpart_id="player",
                counterpart_name="玩家",
                topic_id=str(topic.get("id", "")),
                topic_label=str(topic.get("label", "")),
                tags=["玩家", str(topic.get("kind", "")), approach, intent],
                salience=max(0.42, min(0.95, 0.38 + abs(trust_delta) * 0.08 + effective_strength * 0.4)),
            )
            self._bump_district_signal(npc["district"], "gossip", 0.12)
            self._bump_district_signal(npc["district"], "liquidity", 0.05 if topic.get("kind") in {"asset", "family", "company"} else 0.0)
            self.state["local_broadcasts"].insert(
                0,
                {
                    "source": "player",
                    "district": npc["district"],
                    "radius": 110,
                    "line": lines[1],
                    "type": "conversation",
                },
            )
            self.state["local_broadcasts"] = self.state["local_broadcasts"][:18]
            heard_by = self._apply_player_talk_fallout(npc, topic, intel, effective_strength, live_observation, lines[1], approach, intent)
            if not revealed_topic_ids:
                revealed_topic_ids = [str(topic.get("id", ""))]
            world_effects = self._describe_world_effects(intel, effective_strength)
            trade_quotes = self._default_trade_quotes_for_npc(npc, str(topic.get("id", "")))
            intel_note = intel["line"] if effective_strength > 0.12 else "这次没问出实货，只摸到一点态度。"
            self.state["last_dialogue"] = {
                "title": f"你与 {npc['name']} 交谈",
                "tone": "conversation",
            }
            self.state["last_dialogue"]["body"] = (
                f"[b]话题[/b]：{topic.get('label', '街头风向')}  路  [b]方式[/b]：{self._approach_label(approach)}\n\n"
                f"[b]你[/b]：{lines[0]}\n\n"
                f"[b]{npc['name']}[/b]：{lines[1]}\n\n"
                f"[color=#6b4f2a][b]你实际拿到[/b][/color]\n{intel_note}\n"
                f"可信度 {int(round(float(truth_profile.get('confidence', 0.5)) * 100))}%  路  真话率 {int(round(float(truth_profile.get('truthfulness', 0.5)) * 100))}%\n\n"
                f"[color=#6b4f2a][b]世界变化[/b][/color]\n{world_effects}\n\n"
                f"[i]{npc['district']} 的风向因此更清楚了一点。[/i]"
            )
            self.state["last_dialogue"]["lines"] = lines
            self.state["last_dialogue"]["stance"] = stance
            self.state["last_dialogue"]["truthfulness"] = round(float(truth_profile.get("truthfulness", 0.5)), 3)
            self.state["last_dialogue"]["confidence"] = round(float(truth_profile.get("confidence", 0.5)), 3)
            self.state["last_dialogue"]["revealed_topic_ids"] = revealed_topic_ids
            self.state["last_dialogue"]["topic_id"] = str(topic.get("id", ""))
            self.state["last_dialogue"]["approach"] = approach
            self.state["last_dialogue"]["intent"] = intent
            self.state["last_dialogue"]["player_input"] = player_input
            self.state["last_dialogue"]["world_effects"] = world_effects
            self.state["last_dialogue"]["npc_id"] = npc_id
            self.state["last_dialogue"]["npc_name"] = str(npc.get("name", ""))
            self.state["last_dialogue"]["district"] = npc["district"]
            self.state["last_dialogue"]["relation_status"] = self._npc_player_status(npc)
            self.state["last_dialogue"]["speech_register"] = self._npc_favorability_state(npc).get("speech_register_label", "平视你")
            self.state["last_dialogue"]["heard_by"] = heard_by
            self.state["last_dialogue"]["source"] = "llm" if dialogue else "rule"
            self.state["last_dialogue"]["model"] = str(dialogue.get("_meta_model", self.ark.model_id)) if dialogue else "rule"
            self.state["last_dialogue"]["trade_quotes"] = trade_quotes
            self.state["last_dialogue"]["response_state"] = "llm" if dialogue else "fallback_rule"
            self.state["last_dialogue"]["latency_ms"] = latency_ms
            self.state["last_dialogue"]["title"] = f"你与 {npc['name']} 交谈"
            self.state["last_dialogue"]["render_lines"] = render_lines
            self.state["last_dialogue"]["render_body"] = self._dialogue_render_body(
                npc_name=str(npc.get("name", "对方")),
                topic_label=str(topic.get("label", "街头风向")),
                approach=approach,
                render_lines=render_lines,
                intel_note=intel["line"] if effective_strength > 0.12 else "这次没问到硬情报，只摸到了态度。",
                world_effects=world_effects,
                truth_profile=truth_profile,
            )
            self.state["last_dialogue"]["body"] = self.state["last_dialogue"]["render_body"]
            self._refresh_ambient_speeches()
            self._apply_intraday_market_move(reason="player_talk", decay=0.78)
            self._refresh_derived_views()
            return ActionResult(f"你和 {npc['name']} 搭了几句线。", self.snapshot())

    def conversation(
        self,
        speaker_id: str,
        listener_id: str,
        trigger: str,
        scene_observation: dict[str, Any] | None = None,
        allow_llm: bool = True,
    ) -> ActionResult:
        with self.lock:
            speaker = self._find_npc(speaker_id)
            listener = self._find_npc(listener_id)
            now = time.time()
            if not speaker or not listener:
                return ActionResult("搭话对象不存在。", self.snapshot())
            if now < float(speaker.get("cooldown_until", 0)) or now < float(listener.get("cooldown_until", 0)):
                return ActionResult("", self.snapshot())
            if scene_observation:
                self._record_scene_observation(scene_observation)

            live_observation = copy.deepcopy(self.state.get("scene_observation", {}))
            self._refresh_derived_views()
            topic = self._resolve_talk_topic(speaker, "", speaker["district"])
            speaker["last_spoken_topic_id"] = str(topic.get("id", ""))
            speaker["last_spoken_topic_label"] = str(topic.get("label", ""))
            listener["last_spoken_topic_id"] = str(topic.get("id", ""))
            listener["last_spoken_topic_label"] = str(topic.get("label", ""))
            self._queue_agent_task(speaker, "npc_conversation", str(listener.get("name", "")))
            self._queue_agent_task(listener, "npc_conversation", str(speaker.get("name", "")))
            dialogue = None
            force_demo_llm = trigger in {
                "player_interaction",
                "ambient_resident_chat",
                "ue_demo",
            }
            has_agent_budget = (
                force_demo_llm
                or (
                    self._consume_agent_budget(speaker, "npc_conversation", 1)
                    and self._consume_agent_budget(listener, "npc_conversation", 1)
                )
            )
            if allow_llm and has_agent_budget:
                dialogue = self.ark.generate_dialogue_turn(
                    {
                        "speaker": speaker,
                        "speaker_agent": self._npc_agent_profile(speaker),
                        "speaker_sections": self._npc_llm_sections(speaker, topic),
                        "listener": listener,
                        "listener_agent": self._npc_agent_profile(listener),
                        "listener_sections": self._npc_llm_sections(listener, topic),
                        "district": speaker["district"],
                        "trigger": trigger,
                        "topic": topic,
                        "active_topics": self._active_public_topics(limit=4, district_name=str(speaker.get("district", ""))),
                        "active_norms": self._active_norms_view(limit=4, district_name=str(speaker.get("district", ""))),
                        "active_collective_actions": self._active_collective_actions_view(limit=4, district_name=str(speaker.get("district", ""))),
                        "approach": "cautious",
                        "intent": "街头搭话",
                        "scene_observation": live_observation,
                        "truth_profile": self._truth_metrics_for_topic(listener, topic, "cautious", "街头搭话"),
                        "relationship_memory": {
                            "speaker_recent_events": copy.deepcopy(list(speaker.get("relationship_memory", []))[:3]),
                            "listener_recent_events": copy.deepcopy(list(listener.get("relationship_memory", []))[:3]),
                            "speaker_conversation_history": self._dialogue_history_view(speaker, counterpart_id=listener_id, limit=4),
                            "listener_conversation_history": self._dialogue_history_view(listener, counterpart_id=speaker_id, limit=4),
                            "speaker_local_memory": self._local_memory_view(speaker, counterpart_id=listener_id, topic_id=str(topic.get("id", "")), limit=4),
                            "listener_local_memory": self._local_memory_view(listener, counterpart_id=speaker_id, topic_id=str(topic.get("id", "")), limit=4),
                        },
                    }
                )
            lines = None
            if dialogue:
                raw_lines = dialogue.get("lines", [])
                if isinstance(raw_lines, list) and len(raw_lines) >= 2:
                    lines = [str(raw_lines[0]), str(raw_lines[1])]
            if not lines:
                lines = self._rule_conversation_lines(speaker, listener, trigger)
            else:
                fallback_lines = self._rule_conversation_lines(speaker, listener, trigger)
                lines[0] = self._normalize_spoken_line(str(speaker.get("name", "")), lines[0], fallback_lines[0])
                lines[1] = self._normalize_spoken_line(str(listener.get("name", "")), lines[1], fallback_lines[1])
            if dialogue:
                self._remember_agent_output(speaker, "npc_conversation", lines[0])
                self._remember_agent_output(listener, "npc_conversation", lines[1])

            speaker["speech_lines"] = [lines[0], *speaker["speech_lines"][:2]]
            listener["speech_lines"] = [lines[1], *listener["speech_lines"][:2]]
            speaker["mood"] = self._shift_mood_after_talk(speaker["mood"])
            listener["mood"] = self._shift_mood_after_talk(listener["mood"])
            speaker["fear"] = min(100, speaker["fear"] + self.random.randint(0, 4))
            listener["fear"] = min(100, listener["fear"] + self.random.randint(0, 4))
            speaker["memory_tags"] = self._push_memory(speaker["memory_tags"], f"talk:{listener_id}")
            listener["memory_tags"] = self._push_memory(listener["memory_tags"], f"talk:{speaker_id}")
            self._remember_npc_event(
                speaker,
                "npc_conversation",
                {
                    "counterpart": str(listener.get("name", "")),
                    "counterpart_id": listener_id,
                    "trigger": trigger,
                    "topic_id": str(topic.get("id", "")),
                },
            )
            self._remember_npc_event(
                listener,
                "npc_conversation",
                {
                    "counterpart": str(speaker.get("name", "")),
                    "counterpart_id": speaker_id,
                    "trigger": trigger,
                    "topic_id": str(topic.get("id", "")),
                },
            )
            self._append_dialogue_history(
                speaker,
                listener_id,
                str(listener.get("name", "")),
                lines[0],
                lines[1],
                str(topic.get("id", "")),
                str(topic.get("label", "")),
                trigger,
                "npc_conversation",
                "npc",
            )
            self._append_dialogue_history(
                listener,
                speaker_id,
                str(speaker.get("name", "")),
                lines[1],
                lines[0],
                str(topic.get("id", "")),
                str(topic.get("label", "")),
                trigger,
                "npc_conversation",
                "npc",
            )
            conversation_intensity = max(0.22, min(0.92, float(topic.get("heat", 0.3)) * 0.55 + 0.28))
            self._remember_local_memory(
                speaker,
                kind="npc_conversation",
                summary=f"{listener.get('name', '对方')}刚围着{topic.get('label', '风声')}跟你低声换话：{lines[1]}",
                counterpart_id=listener_id,
                counterpart_name=str(listener.get("name", "")),
                topic_id=str(topic.get("id", "")),
                topic_label=str(topic.get("label", "")),
                tags=["社交", str(topic.get("kind", "")), trigger],
                salience=max(0.34, min(0.88, conversation_intensity)),
            )
            self._remember_local_memory(
                listener,
                kind="npc_conversation",
                summary=f"{speaker.get('name', '对方')}刚围着{topic.get('label', '风声')}跟你低声换话：{lines[0]}",
                counterpart_id=speaker_id,
                counterpart_name=str(speaker.get("name", "")),
                topic_id=str(topic.get("id", "")),
                topic_label=str(topic.get("label", "")),
                tags=["社交", str(topic.get("kind", "")), trigger],
                salience=max(0.34, min(0.88, float(topic.get("heat", 0.3)) * 0.55 + 0.28)),
            )
            self._register_topic_heard(
                speaker,
                topic,
                listener,
                channel="conversation",
                salience=min(0.94, conversation_intensity + 0.08),
                line=f"{listener.get('name', '对方')}刚刚围着“{topic.get('label', '街面风声')}”回了你一句：{lines[1]}",
            )
            self._register_topic_heard(
                listener,
                topic,
                speaker,
                channel="conversation",
                salience=min(0.94, conversation_intensity + 0.08),
                line=f"{speaker.get('name', '对方')}刚刚围着“{topic.get('label', '街面风声')}”递了你一句：{lines[0]}",
            )
            speaker["cooldown_until"] = now + 7
            listener["cooldown_until"] = now + 7

            self.state["local_broadcasts"].insert(
                0,
                {
                    "source": speaker["id"],
                    "district": speaker["district"],
                    "radius": max(speaker["social_radius"], listener["social_radius"]),
                    "line": lines[0],
                    "type": "conversation",
                },
            )
            self.state["local_broadcasts"] = self.state["local_broadcasts"][:18]
            self._apply_local_hearing(speaker)
            self._apply_local_hearing(listener)
            self._check_local_escalation(speaker)
            self._check_local_escalation(listener)
            if dialogue or float(topic.get("heat", 0.0)) >= 0.24:
                packet = self._build_intel_packet_from_topic(topic, speaker, speaker["district"])
                packet["source"] = f"{speaker['name']}和{listener['name']}的私语"
                packet["line"] = f"{speaker['name']}压着声线递话：{packet['line']}"
                packet["body"] = f"{speaker['name']}和{listener['name']}的低声交谈里冒出一句：{packet['line']}"
                promote_news = conversation_intensity >= 0.72 or str(packet.get("scope", "district")) == "city"
                self._apply_intel_packet(packet, to_player=False, promote_news=promote_news, intensity=conversation_intensity)
                self._apply_intraday_market_move(reason="npc_conversation", decay=0.84)
                self._bump_district_signal(speaker["district"], "gossip", 0.14 + float(topic.get("heat", 0.0)) * 0.08)
            self._refresh_ambient_speeches()
            self._refresh_derived_views()
            return ActionResult(f"{speaker['name']} 与 {listener['name']} 低声交换了风向。", self.snapshot())

    def hearing_event(self, speaker_id: str, listener_id: str, line: str) -> ActionResult:
        with self.lock:
            speaker = self._find_npc(speaker_id)
            listener = self._find_npc(listener_id)
            if not speaker or not listener:
                return ActionResult("", self.snapshot())
            listener["fear"] = min(100, listener["fear"] + 3)
            listener["memory_tags"] = self._push_memory(listener["memory_tags"], f"heard:{speaker_id}")
            listener["speech_lines"] = [f"有人刚提到：{line[:18]}"]
            self._check_local_escalation(listener)
            self._refresh_ambient_speeches()
            self._refresh_derived_views()
            return ActionResult("", self.snapshot())

    def _run_agent_social_turns(self, scene_observation: dict[str, Any], allow_llm: bool = True) -> None:
        rows: list[tuple[float, float, str, str, str]] = []
        npcs = self.state.get("npcs", [])
        for index, speaker in enumerate(npcs):
            for listener in npcs[index + 1 :]:
                if str(speaker.get("district", "")) != str(listener.get("district", "")):
                    continue
                distance = self._distance(speaker, listener)
                if distance > min(float(speaker.get("social_radius", 180)), float(listener.get("social_radius", 180))) * 0.82:
                    continue
                district_signals = self.state.get("district_signals", {}).get(str(speaker.get("district", "")), {})
                district_heat = float(district_signals.get("gossip", 0.0)) + float(district_signals.get("fear", 0.0)) + float(district_signals.get("labor_heat", 0.0))
                pair_score = self._npc_social_pair_score(speaker, listener, distance, district_heat)
                if pair_score is None:
                    continue
                social_pull = float(speaker.get("proactive_interest", 0.3)) + float(listener.get("proactive_interest", 0.3))
                role_bonus = 0.18 if str(speaker.get("role", "")) in {"记者", "代理人", "工会领袖"} else 0.0
                role_bonus += 0.18 if str(listener.get("role", "")) in {"记者", "代理人", "工会领袖"} else 0.0
                score = pair_score + social_pull * 0.35 + district_heat * 0.18 + role_bonus
                if score < 0.08:
                    continue
                subregion_key = (
                    f"{speaker.get('district', '')}:{speaker.get('subregion_id', '')}"
                    if str(speaker.get("subregion_id", "")) == str(listener.get("subregion_id", ""))
                    else ""
                )
                rows.append((score, distance, str(speaker.get("id", "")), str(listener.get("id", "")), subregion_key))
        rows.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        used: set[str] = set()
        subregion_turns: dict[str, int] = {}
        turns = 0
        max_turns = min(2, max(1, len(npcs) // 10 + 1))
        for _, _, speaker_id, listener_id, subregion_key in rows:
            if speaker_id in used or listener_id in used:
                continue
            speaker = self._find_npc(speaker_id)
            listener = self._find_npc(listener_id)
            if not speaker or not listener:
                continue
            if subregion_key:
                pressure = self._district_social_pressure(str(speaker.get("district", "")))
                cap = 2 if float(pressure.get("total_heat", 0.0)) >= 0.88 else 1
                if int(subregion_turns.get(subregion_key, 0)) >= cap:
                    continue
            self._queue_agent_task(speaker, "agent_social", str(listener.get("name", "")))
            self._queue_agent_task(listener, "agent_social", str(speaker.get("name", "")))
            trigger = "盘前试探"
            if str(speaker.get("district", "")) == "工厂区":
                trigger = "工棚低声串话"
            elif str(speaker.get("district", "")) == "港口":
                trigger = "码头换班闲聊"
            elif str(speaker.get("district", "")) == "贫民街":
                trigger = "巷口传话"
            self.conversation(speaker_id, listener_id, trigger, scene_observation=scene_observation, allow_llm=allow_llm)
            used.add(speaker_id)
            used.add(listener_id)
            if subregion_key:
                subregion_turns[subregion_key] = int(subregion_turns.get(subregion_key, 0)) + 1
            turns += 1
            if turns >= max_turns:
                break

    def _load_json(self, filename: str) -> Any:
        return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))

    def _load_json_optional(self, filename: str, default: Any) -> Any:
        path = DATA_DIR / filename
        if not path.exists():
            return copy.deepcopy(default)
        return json.loads(path.read_text(encoding="utf-8"))

    def _flatten_subregions(self, districts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for district in districts:
            district_id = str(district.get("id", ""))
            district_name = str(district.get("name", ""))
            for subregion in district.get("subregions", []):
                row = copy.deepcopy(subregion)
                row["district_id"] = district_id
                row["district_name"] = district_name
                rows.append(row)
        return rows

    def _residence_rows(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(row) for row in self.residence_defs if isinstance(row, dict)]

    def _residences_for_district(self, district_name: str) -> list[dict[str, Any]]:
        rows = [row for row in self._residence_rows() if str(row.get("district", "")) == district_name]
        if rows:
            return rows
        legacy = self._house_for_district(district_name)
        return [legacy] if legacy else []

    def _doc_plan_for_npc(self, npc: dict[str, Any]) -> dict[str, Any]:
        npc_id = str(npc.get("id", "")).strip()
        plan = self.npc_path_plans.get(npc_id, {})
        return plan if isinstance(plan, dict) else {}

    def _doc_schedule_day_matches(self, day_key: str, day: int) -> bool:
        value = str(day_key).strip()
        if not value.startswith("Day_"):
            return False
        day_numbers = [int(token) for token in re.findall(r"\d+", value)]
        if not day_numbers:
            return False
        if len(day_numbers) == 1:
            return day_numbers[0] == day
        return day_numbers[0] <= day <= day_numbers[-1]

    @staticmethod
    def _doc_parse_clock_label(value: str) -> int:
        hour_text, minute_text = str(value).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if hour == 24:
            return 24 * 60
        return hour * 60 + minute

    def _doc_schedule_time_matches(self, window: str, minutes: int) -> bool:
        value = str(window).strip()
        if "-" not in value:
            return False
        start_text, end_text = [part.strip() for part in value.split("-", 1)]
        try:
            start_minutes = self._doc_parse_clock_label(start_text)
            end_minutes = self._doc_parse_clock_label(end_text)
        except Exception:
            return False
        if start_minutes == end_minutes:
            return True
        if end_minutes <= 24 * 60 and start_minutes < end_minutes:
            return start_minutes <= minutes < end_minutes
        normalized_minutes = minutes
        return normalized_minutes >= start_minutes or normalized_minutes < min(end_minutes, 24 * 60)

    def _doc_pick_target_tag(self, npc: dict[str, Any], entry: dict[str, Any], minutes: int) -> str:
        target = entry.get("TargetTag")
        if isinstance(target, list):
            tags = [str(value).strip() for value in target if str(value).strip()]
            if not tags:
                return ""
            if not bool(entry.get("Loop", False)) or len(tags) == 1:
                return tags[0]
            seed = sum(ord(ch) for ch in str(npc.get("id", "")))
            index = int(minutes // 30 + seed) % len(tags)
            return tags[index]
        return str(target).strip()

    def _doc_poi_slot(self, tag: str) -> dict[str, Any]:
        if not tag:
            return {}
        slot = self.poi_slot_defs.get(str(tag), {})
        return copy.deepcopy(slot) if isinstance(slot, dict) else {}

    def _doc_action_activity(self, action: str) -> str:
        value = str(action).strip().upper()
        if value in {
            "SIT_HOMELESS",
            "SLEEP_ON_CARDBOARD",
            "SLEEP_ON_DESK",
            "REST_BORED",
            "WAIT_FOR_END",
        }:
            return "home"
        if value in {
            "SPEECH_UNDERGROUND",
            "LEAD_PROTEST",
            "SIT_SILENTLY_PROTEST",
            "TRUTH_BROADCAST",
            "ARGUE_WITH_OFFICERS",
            "ASSAULT_BUILDING",
            "FIRE_HEAVY_WEAPON",
        }:
            return "protesting"
        if value in {
            "SECRET_MEETING",
            "GOLF_SWING_AND_TALK",
            "SOCIALIZE_ELEGANTLY",
            "DRINK_BEER",
            "DRINK_SOLITARY",
            "DRINK_HEAVILY_DEPRESSED",
            "TEND_BAR_AND_LISTEN",
            "SIP_COFFEE_READ",
            "HOST_PARTY",
            "WAIT_FOR_TRADE",
            "DEAL_SMUGGLE",
            "NOD_OBSEQUIOUSLY",
        }:
            return "gathering"
        if value in {
            "LOOK_AROUND_PARANOID",
            "LOOK_DOWN_WINDOW",
            "PASSIVE_STANDBY",
            "EAVESDROP_HIGH_LEVEL",
            "STARE_AT_STOCK_TICKER",
            "STARE_AT_HQ",
            "OBSERVE_CROWD",
            "LEAN_AND_WATCH",
            "WAIT_FOR_BRIBE",
        }:
            return "watching"
        if value in {
            "SIGN_PAPERS",
            "STAMP_DOCUMENT_QUICK",
            "ORGANIZE_DOCUMENTS_COLD",
            "COUNT_MONEY",
            "COUNT_DIRTY_MONEY",
            "TYPE_KEYBOARD_FRANTIC",
            "TYPE_SILENTLY",
            "TYPE_TYPEWRITER",
            "WRITE_URGENT",
            "COPY_DOCUMENTS",
            "PASTE_NEWSPAPER",
            "PASTE_RED_NEWSPAPER",
            "PLAY_GUITAR_METAPHOR",
            "SIGNAL_RELAY",
            "PREPARE_BROADCAST",
            "HACKING_TERMINAL",
            "SEND_MESSAGE",
            "SHRED_DOCUMENTS",
        }:
            return "working"
        if value in {
            "EVICT_TENANT",
            "INTIMIDATE_AND_EXTORT",
            "PATROL_WALK",
            "ASSIST_EVICTION",
            "READY_TO_RUN",
        }:
            return "responding"
        return "working"

    def _doc_sync_offset(self, npc: dict[str, Any], entry: dict[str, Any]) -> tuple[float, float]:
        raw_sync = str(entry.get("Sync_With_NPC", "")).strip()
        sync_numbers = re.findall(r"\d+", raw_sync)
        sync_id = int(sync_numbers[0]) if sync_numbers else 0
        if sync_id <= 0:
            return 0.0, 0.0
        try:
            npc_num = int(str(npc.get("id", "0")).split("_")[-1])
        except ValueError:
            npc_num = 0
        if npc_num == sync_id:
            return 0.0, 0.0
        return (-16.0, 0.0) if npc_num < sync_id else (16.0, 0.0)

    def _doc_schedule_override(self, npc: dict[str, Any], minutes: int) -> dict[str, Any]:
        plan = self._doc_plan_for_npc(npc)
        schedules = plan.get("Daily_Schedules", {})
        if not isinstance(schedules, dict):
            return {}
        day = int(self.state.get("day", 1))
        active_entry: dict[str, Any] | None = None
        for day_key, entries in schedules.items():
            if not self._doc_schedule_day_matches(str(day_key), day):
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if self._doc_schedule_time_matches(str(entry.get("Time", "")), minutes):
                    active_entry = entry
                    break
            if active_entry:
                break
        if not active_entry:
            return {}
        target_tag = self._doc_pick_target_tag(npc, active_entry, minutes)
        slot = self._doc_poi_slot(target_tag)
        if not slot:
            return {}
        offset_x, offset_y = self._doc_sync_offset(npc, active_entry)
        action = str(active_entry.get("Action", "")).strip()
        activity = self._doc_action_activity(action)
        target_subregion_id = str(slot.get("subregion_id", npc.get("subregion_id", "")))
        return {
            "activity": activity,
            "x": round(float(slot.get("x", npc.get("x", 0.0))) + offset_x, 1),
            "y": round(float(slot.get("y", npc.get("y", 0.0))) + offset_y, 1),
            "target_subregion_id": target_subregion_id,
            "target_subregion_name": self._subregion_name(target_subregion_id),
            "goal": str(active_entry.get("Detail", "")).strip() or str(plan.get("Identity", plan.get("Faction", ""))).strip(),
            "current_target": target_tag,
            "schedule_note": str(active_entry.get("Detail", "")).strip() or "%s → %s" % [str(plan.get("Name", npc.get("name", ""))), target_tag],
            "anchor_type": "doc_poi",
            "doc_action": action,
            "target_tag": target_tag,
        }

    def _residence_for_npc(
        self,
        npc: dict[str, Any],
        index: int,
        occupancy: dict[str, int],
        subregion_lookup: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        district_name = str(npc.get("district", ""))
        rows = self._residences_for_district(district_name)
        if not rows:
            return {}
        preferred_subregion = str(
            npc.get("home_subregion_id", "")
            or npc.get("work_subregion_id", "")
            or npc.get("subregion_id", "")
        )
        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            residence_id = str(row.get("id", ""))
            capacity = max(1, int(row.get("capacity", 1)))
            used = int(occupancy.get(residence_id, 0))
            same_subregion = 1.0 if str(row.get("subregion_id", "")) == preferred_subregion else 0.0
            fill_ratio = used / float(capacity)
            distance_bias = 0.0
            if preferred_subregion:
                preferred_meta = subregion_lookup.get(preferred_subregion, {})
                target_meta = subregion_lookup.get(str(row.get("subregion_id", "")), {})
                if preferred_meta and target_meta:
                    px = float(preferred_meta.get("center", {}).get("x", preferred_meta.get("x", 0.0))) if isinstance(preferred_meta.get("center"), dict) else 0.0
                    py = float(preferred_meta.get("center", {}).get("y", preferred_meta.get("y", 0.0))) if isinstance(preferred_meta.get("center"), dict) else 0.0
                    tx = float(target_meta.get("center", {}).get("x", target_meta.get("x", 0.0))) if isinstance(target_meta.get("center"), dict) else 0.0
                    ty = float(target_meta.get("center", {}).get("y", target_meta.get("y", 0.0))) if isinstance(target_meta.get("center"), dict) else 0.0
                    distance_bias = math.dist((px, py), (tx, ty)) / 2400.0
            score = same_subregion * 2.0 - fill_ratio * 1.2 - distance_bias - used * 0.04
            score += ((index % 5) * 0.01)
            ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        chosen = copy.deepcopy(ranked[0][1])
        chosen_id = str(chosen.get("id", ""))
        occupancy[chosen_id] = int(occupancy.get(chosen_id, 0)) + 1
        chosen["assigned_slot"] = max(0, occupancy[chosen_id] - 1)
        return chosen

    def _residence_slot_offsets(self, residence_id: str) -> list[tuple[float, float]]:
        custom = {
            "slum_house": [(-18.0, 18.0), (14.0, 20.0), (-26.0, 42.0), (24.0, 40.0)],
            "yard_shack": [(-12.0, 12.0), (14.0, 14.0), (0.0, 30.0)],
            "trail_loft": [(-18.0, 12.0), (16.0, 14.0), (-28.0, 34.0), (24.0, 36.0)],
            "dock_house": [(-18.0, 16.0), (16.0, 18.0), (0.0, 34.0)],
            "canal_flat": [(-12.0, 12.0), (12.0, 12.0)],
            "wharf_bunk": [(-22.0, 16.0), (18.0, 18.0), (-28.0, 36.0), (24.0, 38.0)],
            "factory_house": [(-20.0, 14.0), (16.0, 16.0), (0.0, 34.0)],
            "mill_row": [(-22.0, 14.0), (18.0, 16.0), (-30.0, 38.0), (26.0, 40.0)],
            "quarry_row": [(-24.0, 14.0), (20.0, 16.0), (-32.0, 38.0), (28.0, 40.0)],
            "exchange_house": [(-16.0, 16.0), (16.0, 16.0), (-20.0, 36.0), (20.0, 36.0)],
            "market_row": [(-14.0, 14.0), (14.0, 14.0), (0.0, 32.0)],
            "chapel_flat": [(-14.0, 14.0), (14.0, 14.0), (0.0, 30.0)],
        }
        return custom.get(residence_id, [(-12.0, 12.0), (12.0, 12.0), (0.0, 28.0)])

    def _residence_anchor(self, residence: dict[str, Any], slot: int = 0, mode: str = "door") -> tuple[float, float]:
        base_x = float(residence.get("door_x", residence.get("anchor_x", 0.0)))
        base_y = float(residence.get("door_y", residence.get("anchor_y", 0.0)))
        if mode == "indoor":
            base_x = float(residence.get("indoor_x", base_x))
            base_y = float(residence.get("indoor_y", base_y))
        offsets = self._residence_slot_offsets(str(residence.get("id", "")))
        offset_x, offset_y = offsets[max(slot, 0) % len(offsets)]
        return round(base_x + offset_x, 1), round(base_y + offset_y, 1)

    def _residence_patrol_points(self, residence_id: str) -> list[tuple[float, float]]:
        meta = next((row for row in self._residence_rows() if str(row.get("id", "")) == residence_id), None)
        if not meta:
            return HOUSE_PATROL_POINTS.get(residence_id, [])
        base_x = float(meta.get("door_x", meta.get("anchor_x", 0.0)))
        base_y = float(meta.get("door_y", meta.get("anchor_y", 0.0)))
        points = []
        for offset_x, offset_y in self._residence_slot_offsets(residence_id):
            points.append((round(base_x + offset_x, 1), round(base_y + offset_y, 1)))
        points.append((round(base_x, 1), round(base_y - 12.0, 1)))
        return points

    def _work_anchor_for_npc(self, npc: dict[str, Any], work_subregion_id: str) -> tuple[float, float, int]:
        route_points = SUBREGION_ROUTE_POINTS.get(work_subregion_id, [])
        if not route_points:
            anchor_x, anchor_y = self._subregion_anchor(
                work_subregion_id,
                float(npc.get("x", 0.0)),
                float(npc.get("y", 0.0)),
            )
            return round(anchor_x, 1), round(anchor_y, 1), 0
        raw_id = str(npc.get("id", "npc_0")).split("_")[-1]
        try:
            seed = max(1, int(raw_id))
        except ValueError:
            seed = max(1, (sum(ord(ch) for ch in str(npc.get("id", ""))) % 37) + 1)
        slot = (seed - 1) % len(route_points)
        base_x, base_y = route_points[slot]
        work_slot_x, work_slot_y = self._npc_slot_offset(npc, "work")
        return round(base_x + work_slot_x * 0.45, 1), round(base_y + work_slot_y * 0.45, 1), slot

    def _subregion_anchor(self, subregion_id: str, fallback_x: float, fallback_y: float) -> tuple[float, float]:
        points = SUBREGION_ROUTE_POINTS.get(str(subregion_id), [])
        if not points:
            return round(float(fallback_x), 1), round(float(fallback_y), 1)
        x = sum(point[0] for point in points) / float(len(points))
        y = sum(point[1] for point in points) / float(len(points))
        return round(x, 1), round(y, 1)

    def _npc_social_band(self, npc: dict[str, Any]) -> str:
        role = str(npc.get("role", ""))
        title = str(npc.get("title", ""))
        family = str(npc.get("family_affiliation", ""))
        class_name = str(npc.get("class", ""))
        if family == "镇政府":
            return "authority"
        if role == "记者":
            return "media"
        if role == "工会领袖":
            return "organizer"
        if role == "投机者":
            return "finance"
        if role == "银行经理":
            return "elite" if any(token in title for token in ["掌门", "总", "监管官"]) else "finance"
        if role == "老板":
            return "elite"
        if role == "代理人":
            return "manager"
        if role == "店主":
            return "trade"
        if role == "工人":
            return "labor"
        if role == "临时工":
            return "precariat" if class_name == "底层" else "resident"
        return "resident"

    def _preferred_work_subregion(self, npc: dict[str, Any]) -> str:
        npc_id = str(npc.get("id", "")).strip()
        override = NPC_WORK_SUBREGION_OVERRIDES.get(npc_id, "")
        if override:
            return override
        district_name = str(npc.get("district", ""))
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        return str(SOCIAL_BAND_SUBREGIONS.get(district_name, {}).get(band, npc.get("subregion_id", "")))

    def _npc_contact_names(self, npc: dict[str, Any], key: str) -> set[str]:
        profile = npc.get("prompt_profile", {})
        if not isinstance(profile, dict):
            return set()
        return {str(value).strip() for value in profile.get(key, []) if str(value).strip()}

    def _subregion_name(self, subregion_id: str) -> str:
        needle = str(subregion_id).strip()
        for row in self.state.get("subregions", []):
            if str(row.get("id", "")) == needle:
                return str(row.get("name", needle))
        return needle

    @staticmethod
    def _normalized_district_signal(value: Any) -> float:
        numeric = float(value or 0.0)
        if numeric <= 1.0:
            return max(0.0, numeric)
        return max(0.0, min(1.0, numeric / 5.0))

    def _district_social_pressure(self, district_name: str) -> dict[str, Any]:
        signals = self.state.get("district_signals", {}).get(district_name, {})
        trade_heat = self._normalized_district_signal(signals.get("trade_heat", 0.0))
        labor_heat = self._normalized_district_signal(signals.get("labor_heat", 0.0))
        gossip = self._normalized_district_signal(signals.get("gossip", 0.0))
        fear = self._normalized_district_signal(signals.get("fear", 0.0))
        liquidity = self._normalized_district_signal(signals.get("liquidity", 0.0))
        topics = self._active_public_topics(limit=4, district_name=district_name)
        norms = self._active_norms_view(limit=3, district_name=district_name)
        top_topic = topics[0] if topics else {}
        topic_kind = str(top_topic.get("kind", ""))
        topic_label = str(top_topic.get("label", ""))
        topic_heat = float(top_topic.get("heat", 0.0))
        labor_topic_heat = max((float(row.get("heat", 0.0)) for row in topics if str(row.get("kind", "")) in {"labor", "public"}), default=0.0)
        gossip_topic_heat = max((float(row.get("heat", 0.0)) for row in topics if str(row.get("kind", "")) in {"panic", "rumor", "media", "public"}), default=0.0)
        finance_topic_heat = max((float(row.get("heat", 0.0)) for row in topics if str(row.get("kind", "")) in {"finance", "asset", "trade"}), default=0.0)
        norm_pressure = max((float(row.get("pressure", 0.0)) for row in norms), default=0.0)
        norm_text = str(norms[0].get("text", "")) if norms else ""
        return {
            "trade_heat": trade_heat,
            "labor_heat": labor_heat,
            "gossip": gossip,
            "fear": fear,
            "liquidity": liquidity,
            "total_heat": trade_heat + labor_heat + gossip + fear,
            "topic_id": str(top_topic.get("id", "")),
            "topic_kind": topic_kind,
            "topic_label": topic_label,
            "topic_heat": topic_heat,
            "labor_topic_heat": labor_topic_heat,
            "gossip_topic_heat": gossip_topic_heat,
            "finance_topic_heat": finance_topic_heat,
            "norm_pressure": norm_pressure,
            "norm_text": norm_text,
        }

    def _npc_social_target_name(self, npc: dict[str, Any], purpose: str, topic_id: str = "") -> str:
        trusted = list(self._npc_contact_names(npc, "trusted_people"))
        watch = list(self._npc_contact_names(npc, "watch_people"))
        ordered_names: list[str] = []
        if purpose in {"organize", "steady"}:
            ordered_names = trusted + [name for name in watch if name not in trusted]
        elif purpose in {"watch", "broadcast"}:
            ordered_names = watch + [name for name in trusted if name not in watch]
        else:
            ordered_names = trusted + [name for name in watch if name not in trusted]
        if topic_id:
            npc_heard = {str(value) for value in npc.get("heard_topic_ids", []) if str(value).strip()}
            knows_topic = topic_id in npc_heard
            for name in ordered_names:
                other = self._find_by_name(self.state.get("npcs", []), name)
                if not other or str(other.get("id", "")) == str(npc.get("id", "")):
                    continue
                if str(other.get("district", "")) != str(npc.get("district", "")):
                    continue
                other_heard = {str(value) for value in other.get("heard_topic_ids", []) if str(value).strip()}
                if purpose in {"organize", "broadcast"} and knows_topic and topic_id not in other_heard:
                    return name
                if purpose == "watch" and name in watch:
                    return name
        if purpose in {"organize", "steady"} and trusted:
            return trusted[0]
        if purpose in {"watch", "broadcast"} and watch:
            return watch[0]
        if trusted:
            return trusted[0]
        if watch:
            return watch[0]
        return ""

    def _resolve_focus_topic(self, npc: dict[str, Any]) -> dict[str, Any]:
        topic_id = str(npc.get("last_spoken_topic_id", "")).strip()
        if topic_id:
            topic = self._find_by_id(self.state.get("talk_topics", []), topic_id)
            if not topic:
                topic = self._find_by_id(self.state.get("topic_registry", []), topic_id)
            if not topic:
                topic = next((row for row in self._npc_personal_topics(npc) if str(row.get("id", "")) == topic_id), None)
            if topic:
                return copy.deepcopy(topic)
        district_name = str(npc.get("district", ""))
        active = self._active_public_topics(limit=1, district_name=district_name)
        if active:
            return copy.deepcopy(active[0])
        return {}

    def _topic_spread_bonus(self, speaker: dict[str, Any], listener: dict[str, Any], district_name: str) -> float:
        speaker_heard = {str(value) for value in speaker.get("heard_topic_ids", []) if str(value).strip()}
        listener_heard = {str(value) for value in listener.get("heard_topic_ids", []) if str(value).strip()}
        if not speaker_heard and not listener_heard:
            return 0.0
        bonus = 0.0
        for topic in self._active_public_topics(limit=3, district_name=district_name):
            topic_id = str(topic.get("id", "")).strip()
            if not topic_id:
                continue
            topic_heat = float(topic.get("heat", 0.0))
            spread_value = 0.1 + min(0.2, topic_heat * 0.22)
            if topic_id in speaker_heard and topic_id not in listener_heard:
                bonus = max(bonus, spread_value)
            if topic_id in listener_heard and topic_id not in speaker_heard:
                bonus = max(bonus, spread_value)
        return round(bonus, 3)

    def _register_topic_heard(
        self,
        listener: dict[str, Any],
        topic: dict[str, Any],
        source_npc: dict[str, Any],
        player_input: str = "",
        *,
        channel: str,
        salience: float,
        line: str = "",
    ) -> bool:
        topic_id = str(topic.get("id", "")).strip()
        if not topic_id:
            return False
        heard = [str(value) for value in listener.get("heard_topic_ids", []) if str(value).strip()]
        already_known = topic_id in heard
        listener["heard_topic_ids"] = self._push_memory(heard, topic_id)
        listener["memory_tags"] = self._push_memory(list(listener.get("memory_tags", [])), f"heard_topic:{topic_id}")
        topic_label = str(topic.get("label", "街面风声"))
        source_name = str(source_npc.get("name", "街头")) or "街头"
        summary = line.strip() or f"{source_name}通过{channel}把“{topic_label}”递到了你耳边。"
        self._remember_local_memory(
            listener,
            kind="heard_topic",
            summary=summary,
            counterpart_id=str(source_npc.get("id", "")),
            counterpart_name=source_name,
            topic_id=topic_id,
            topic_label=topic_label,
            tags=["heard", channel, str(topic.get("kind", ""))],
            salience=salience,
        )
        if already_known:
            return False
        registry_topic = self._find_by_id(self.state.get("topic_registry", []), topic_id)
        if registry_topic:
            registry_topic["spread_count"] = int(registry_topic.get("spread_count", 0)) + 1
            registry_topic["heat"] = round(min(1.8, float(registry_topic.get("heat", 0.0)) + salience * 0.05), 3)
        return True

    def _npc_slot_offset(self, npc: dict[str, Any], mode: str) -> tuple[float, float]:
        raw_id = str(npc.get("id", "npc_0")).split("_")[-1]
        try:
            seed = max(1, int(raw_id))
        except ValueError:
            seed = max(1, (sum(ord(ch) for ch in str(npc.get("id", ""))) % 41) + 1)
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        radius_x = 18.0
        radius_y = 12.0
        if mode == "home":
            radius_x = 10.0
            radius_y = 6.0
        elif mode == "social":
            radius_x = 34.0
            radius_y = 22.0
        elif mode == "collective":
            radius_x = 16.0
            radius_y = 10.0
        if band in {"elite", "authority", "finance"}:
            if mode == "home":
                radius_x *= 0.8
                radius_y *= 0.8
            else:
                radius_x *= 1.35
                radius_y *= 1.2
        elif band in {"labor", "precariat", "organizer"}:
            radius_x *= 1.08
            radius_y *= 1.08
        phase = seed * 0.91 + len(mode) * 0.37
        return round(math.sin(phase) * radius_x, 1), round(math.cos(phase * 1.21) * radius_y, 1)

    def _social_window_open(
        self,
        npc: dict[str, Any],
        minutes: int,
        base_activity: str,
        pressure: dict[str, Any],
    ) -> bool:
        if base_activity != "working":
            return False
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        total_heat = float(pressure.get("total_heat", 0.0))
        labor_heat = max(float(pressure.get("labor_heat", 0.0)), float(pressure.get("labor_topic_heat", 0.0)))
        gossip_heat = max(float(pressure.get("gossip", 0.0)), float(pressure.get("gossip_topic_heat", 0.0)))
        finance_heat = max(float(pressure.get("trade_heat", 0.0)), float(pressure.get("finance_topic_heat", 0.0)))
        lunch_window = 11 * 60 + 30 <= minutes < 13 * 60 + 30
        evening_window = 18 * 60 <= minutes < 21 * 60
        morning_window = 7 * 60 <= minutes < 8 * 60 + 30
        if band in {"media", "organizer"}:
            return lunch_window or evening_window or total_heat >= 0.6
        if band in {"authority", "elite", "manager", "finance"}:
            return total_heat >= 0.7 or finance_heat >= 0.72 or labor_heat >= 0.78 or gossip_heat >= 0.78
        if band in {"labor", "precariat", "trade", "resident"}:
            return lunch_window or evening_window or morning_window or total_heat >= 0.76 or labor_heat >= 0.8
        return False

    @staticmethod
    def _social_override_quota(target_band: str) -> int:
        if target_band == "media":
            return 1
        if target_band in {"organizer", "trade"}:
            return 2
        return 0

    @staticmethod
    def _social_override_subregion_cap(target_subregion_id: str) -> int:
        if not str(target_subregion_id).strip():
            return 0
        return 2

    def _scheduled_base_activity(self, npc: dict[str, Any], minutes: int) -> str:
        depart_start, work_start, work_end, settle_home, _sleep_start = self._schedule_window_for_npc(npc)
        if work_start <= minutes < work_end:
            return "working"
        if depart_start <= minutes < work_start:
            return "commuting"
        if work_end <= minutes < settle_home:
            return "returning"
        return "home"

    def _social_override_interest(
        self,
        npc: dict[str, Any],
        target_band: str,
        pressure: dict[str, Any],
    ) -> float:
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        role = str(npc.get("role", ""))
        trust = float(npc.get("player_trust", 0.0)) / 100.0
        debt = min(1.0, float(npc.get("debt", 0.0)) / 100.0)
        hunger = min(1.0, float(npc.get("hunger", 0.0)) / 100.0)
        anxiety = min(1.0, float(npc.get("anxiety", 0.0)) / 100.0)
        heard_topics = len(list(npc.get("heard_topic_ids", []))[:6]) * 0.02
        score = trust * 0.05 + debt * 0.12 + hunger * 0.12 + anxiety * 0.08 + heard_topics
        if target_band == "media":
            score += 0.5 if band == "media" else 0.0
            score += 0.18 if role == "记者" else 0.0
            score += max(float(pressure.get("gossip", 0.0)), float(pressure.get("finance_topic_heat", 0.0))) * 0.4
        elif target_band == "organizer":
            score += 0.55 if band == "organizer" else 0.0
            score += 0.18 if role == "工会领袖" else 0.0
            score += max(float(pressure.get("labor_heat", 0.0)), float(pressure.get("norm_pressure", 0.0))) * 0.45
        elif target_band == "trade":
            score += 0.45 if band == "trade" else 0.0
            score += 0.14 if role in {"店主", "老板"} else 0.0
            score += max(float(pressure.get("trade_heat", 0.0)), float(pressure.get("gossip", 0.0))) * 0.34
        return round(score, 4)

    def _social_target_band_for_npc(
        self,
        npc: dict[str, Any],
        pressure: dict[str, Any],
    ) -> tuple[str, str, str]:
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        labor_push = max(float(pressure["labor_heat"]), float(pressure["labor_topic_heat"]), float(pressure["norm_pressure"]) * 0.7)
        gossip_push = max(float(pressure["gossip"]), float(pressure["gossip_topic_heat"]))
        finance_push = max(float(pressure["trade_heat"]), float(pressure["finance_topic_heat"]), float(pressure["liquidity"]) * 0.55)
        if band == "media" and max(labor_push, gossip_push, finance_push) >= 0.34:
            return "media", "watching", "broadcast"
        if band == "organizer" and (labor_push >= 0.44 or gossip_push >= 0.46):
            return "organizer", "assembling", "organize"
        if band == "trade" and max(finance_push, gossip_push) >= 0.38:
            return "trade", "gathering", "broadcast" if gossip_push >= finance_push else "steady"
        return "", "", ""

    def _social_override_allowed(
        self,
        npc: dict[str, Any],
        target_band: str,
        target_subregion_id: str,
        minutes: int,
        pressure: dict[str, Any],
        base_activity: str,
    ) -> bool:
        quota = self._social_override_quota(target_band)
        subregion_cap = self._social_override_subregion_cap(target_subregion_id)
        if quota <= 0 or subregion_cap <= 0 or base_activity != "working":
            return False
        district_name = str(npc.get("district", ""))
        band_candidates: list[dict[str, Any]] = []
        subregion_candidates: list[tuple[dict[str, Any], str]] = []
        for other in self.state.get("npcs", []):
            if str(other.get("district", "")) != district_name:
                continue
            other_base_activity = self._scheduled_base_activity(other, minutes)
            if not self._social_window_open(other, minutes, other_base_activity, pressure):
                continue
            other_target_band, _other_activity, _other_purpose = self._social_target_band_for_npc(other, pressure)
            if not other_target_band:
                continue
            other_target_subregion_id = str(SOCIAL_BAND_SUBREGIONS.get(district_name, {}).get(other_target_band, ""))
            if other_target_band == target_band:
                band_candidates.append(other)
            if other_target_subregion_id == target_subregion_id:
                subregion_candidates.append((other, other_target_band))
        band_candidates.sort(
            key=lambda row: (
                -self._social_override_interest(row, target_band, pressure),
                str(row.get("id", "")),
            )
        )
        subregion_candidates.sort(
            key=lambda item: (
                -self._social_override_interest(item[0], item[1], pressure),
                str(item[0].get("id", "")),
            )
        )
        band_allowed_ids = {str(row.get("id", "")) for row in band_candidates[:quota]}
        subregion_allowed_ids = {str(row.get("id", "")) for row, _band in subregion_candidates[:subregion_cap]}
        npc_id = str(npc.get("id", ""))
        return npc_id in band_allowed_ids and npc_id in subregion_allowed_ids

    def _npc_social_pair_score(
        self,
        speaker: dict[str, Any],
        listener: dict[str, Any],
        distance: float,
        district_heat: float,
    ) -> float | None:
        if str(speaker.get("district", "")) != str(listener.get("district", "")):
            return None
        speaker_band = str(speaker.get("social_band", self._npc_social_band(speaker)))
        listener_band = str(listener.get("social_band", self._npc_social_band(listener)))
        speaker_name = str(speaker.get("name", ""))
        listener_name = str(listener.get("name", ""))
        speaker_trusted = self._npc_contact_names(speaker, "trusted_people")
        listener_trusted = self._npc_contact_names(listener, "trusted_people")
        speaker_watch = self._npc_contact_names(speaker, "watch_people")
        listener_watch = self._npc_contact_names(listener, "watch_people")
        trusted_link = listener_name in speaker_trusted or speaker_name in listener_trusted
        watch_link = listener_name in speaker_watch or speaker_name in listener_watch
        same_collective = (
            str(speaker.get("collective_action_id", ""))
            and str(speaker.get("collective_action_id", "")) == str(listener.get("collective_action_id", ""))
        )
        same_subregion = str(speaker.get("subregion_id", "")) == str(listener.get("subregion_id", ""))
        current_target_link = listener_name == str(speaker.get("current_target", "")) or speaker_name == str(listener.get("current_target", ""))
        speaker_activity = str(speaker.get("activity", ""))
        listener_activity = str(listener.get("activity", ""))
        speaker_allowed = listener_band in SOCIAL_BAND_WHITELIST.get(speaker_band, set())
        listener_allowed = speaker_band in SOCIAL_BAND_WHITELIST.get(listener_band, set())
        if not same_collective and not trusted_link and not current_target_link:
            if speaker_band == "elite" and listener_band in {"labor", "precariat", "organizer"}:
                return None
            if listener_band == "elite" and speaker_band in {"labor", "precariat", "organizer"}:
                return None
        if not same_subregion and not same_collective:
            cross_subregion_ok = (
                trusted_link
                or current_target_link
                or ("media" in {speaker_band, listener_band})
                or ("authority" in {speaker_band, listener_band} and district_heat >= 0.42)
            )
            if not cross_subregion_ok:
                return None
        if not same_collective and not trusted_link and not current_target_link and not (speaker_allowed and listener_allowed):
            if not ("media" in {speaker_band, listener_band} and district_heat >= 0.26):
                return None
        if (
            speaker_activity == "working"
            and listener_activity == "working"
            and not same_collective
            and not trusted_link
            and not current_target_link
            and district_heat < 0.72
            and "media" not in {speaker_band, listener_band}
            and "organizer" not in {speaker_band, listener_band}
        ):
            return None
        if watch_link and district_heat < 0.42 and not same_collective and not current_target_link:
            return None
        shared_heard_topics = len(set(speaker.get("heard_topic_ids", [])) & set(listener.get("heard_topic_ids", [])))
        target_bonus = 0.22 if current_target_link else 0.0
        topic_gap_bonus = self._topic_spread_bonus(speaker, listener, str(speaker.get("district", "")))
        band_bonus = 0.18 if speaker_band == listener_band else 0.08 if speaker_allowed and listener_allowed else -0.1
        trusted_bonus = 0.34 if trusted_link else 0.0
        watch_bias = 0.12 + district_heat * 0.18 if watch_link else 0.0
        media_bonus = 0.16 if "media" in {speaker_band, listener_band} else 0.0
        collective_bonus = 0.42 if same_collective else 0.0
        subregion_bonus = 0.2 if same_subregion else -0.08
        shared_topic_bonus = min(0.18, shared_heard_topics * 0.06)
        distance_penalty = distance / 520.0
        return (
            band_bonus
            + trusted_bonus
            + watch_bias
            + media_bonus
            + collective_bonus
            + subregion_bonus
            + shared_topic_bonus
            + target_bonus
            + topic_gap_bonus
            - distance_penalty
        )

    def _social_schedule_override(self, npc: dict[str, Any], minutes: int, base_activity: str) -> dict[str, Any]:
        district_name = str(npc.get("district", ""))
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        pressure = self._district_social_pressure(district_name)
        topic_label = str(pressure.get("topic_label", ""))
        norm_text = str(pressure.get("norm_text", ""))
        if not self._social_window_open(npc, minutes, base_activity, pressure):
            return {}

        target_band, activity, purpose = self._social_target_band_for_npc(npc, pressure)
        if not target_band:
            return {}
        target_subregion_id = str(SOCIAL_BAND_SUBREGIONS.get(district_name, {}).get(target_band, ""))
        if not target_subregion_id:
            return {}
        if not self._social_override_allowed(npc, target_band, target_subregion_id, minutes, pressure, base_activity):
            return {}
        anchor_x, anchor_y = self._subregion_anchor(
            target_subregion_id,
            float(npc.get("work_x", npc.get("x", 0.0))),
            float(npc.get("work_y", npc.get("y", 0.0))),
        )
        slot_x, slot_y = self._npc_slot_offset(npc, "social")
        anchor_x = round(anchor_x + slot_x, 1)
        anchor_y = round(anchor_y + slot_y, 1)
        target_name = self._npc_social_target_name(npc, purpose, str(pressure.get("topic_id", "")))
        goal_bits: list[str] = []
        if activity == "assembling":
            goal_bits.append("去串联一圈")
        elif activity == "watching":
            goal_bits.append("先盯风向")
        elif activity == "gathering":
            goal_bits.append("去听街面回声")
        else:
            goal_bits.append("先缩回自己的圈层")
        if topic_label:
            goal_bits.append(topic_label)
        elif norm_text:
            goal_bits.append(norm_text)
        if target_name:
            goal_bits.append(target_name)
        goal = " / ".join(goal_bits[:3])
        note = ""
        if band in {"elite", "authority", "manager", "finance"}:
            note = f"{npc['name']} 正缩回 {self._subregion_name(target_subregion_id)}，先把{topic_label or norm_text or '风向'}看稳。"
        elif band in {"media", "trade"}:
            note = f"{npc['name']} 正往 {self._subregion_name(target_subregion_id)} 靠，准备围着{topic_label or '街面风声'}找人开口。"
        else:
            note = f"{npc['name']} 正往 {self._subregion_name(target_subregion_id)} 串人，想把{topic_label or norm_text or '这股情绪'}拢起来。"
        return {
            "activity": activity,
            "x": anchor_x,
            "y": anchor_y,
            "target_subregion_id": target_subregion_id,
            "target_subregion_name": self._subregion_name(target_subregion_id),
            "goal": goal,
            "current_target": target_name or topic_label or norm_text or str(npc.get("current_target", "")),
            "schedule_note": note,
        }

    def _do_work(self, district: str) -> ActionResult:
        wages = 7 if district == "港口" else 5
        player = self.state["player"]
        player["cash"] += wages
        player["credit"] = min(100, player["credit"] + 1)
        player["reputation"] = min(100, player["reputation"] + 1)
        self.state["demo_metrics"]["work_actions"] = int(self.state["demo_metrics"].get("work_actions", 0)) + 1
        self.state["macro"]["economy_heat"] = min(100, int(self.state["macro"]["economy_heat"]) + 1)
        self._bump_district_signal(district, "labor_heat", 0.2)
        self._bump_district_signal(district, "liquidity", 0.08)
        self._increment_task_progress("work", district, 1)
        return ActionResult(f"你在{district}干完一轮活，拿到 {wages} 铜币。", self.snapshot())

    def _gather_info(self, district: str) -> ActionResult:
        player = self.state["player"]
        if player["cash"] < 2:
            return ActionResult("你连买消息的钱都不够。", self.snapshot())
        player["cash"] -= 2
        intel = self._build_intel_packet(district, source="街头耳报")
        self._apply_intel_packet(intel, to_player=True, promote_news=True, intensity=1.0)
        self._increment_task_progress("gather_info", "any", 1)
        self.state["demo_metrics"]["intel_actions"] = int(self.state["demo_metrics"].get("intel_actions", 0)) + 1
        self._bump_district_signal(district, "gossip", 0.3)
        self._bump_district_signal(district, "fear", 0.08 if "恐慌" in intel.get("tags", []) else 0.0)
        self._apply_intraday_market_move(reason="gather_info", decay=0.74)
        return ActionResult(f"你从脏兮兮的墙报上抄下一条风声：{intel['line']}", self.snapshot())

    def _rest_at_home(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        player["credit"] = min(100, player["credit"] + 2)
        player["reputation"] = min(100, player["reputation"] + 1)
        player["rumors"] = player["rumors"][-5:]
        self._advance_clock(42)
        house_title = str(payload.get("house_title", "屋子"))
        self.state["global_news"].insert(
            0,
            {
                "title": f"{district} 夜灯渐稳",
                "body": f"你在 {house_title} 的木床上歇了片刻，脑子终于没那么紧了。",
                "tags": ["休整", district],
                "scope": "district",
            },
        )
        self.state["global_news"] = self.state["global_news"][:8]
        return ActionResult(f"你在 {house_title} 的木床上缓了口气。", self.snapshot())

    def _cook_meal(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        inventory = player["goods_inventory"]
        if inventory.get("面包", 0) > 0:
            inventory["面包"] -= 1
            meal_note = "你把面包烤热，又煮了一小锅浓汤。"
        else:
            if player["cash"] < 3:
                return ActionResult("灶台有火，但你手里连做饭的钱都快没了。", self.snapshot())
            player["cash"] -= 3
            meal_note = "你掏了 3 铜币凑出一顿热饭。"
        player["credit"] = min(100, player["credit"] + 1)
        self._advance_clock(26)
        return ActionResult(meal_note, self.snapshot())

    def _search_home(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        roll = self.random.random()
        self._advance_clock(14)
        if roll < 0.34:
            coins = self.random.randint(2, 5)
            player["cash"] += coins
            return ActionResult(f"你在储物箱底翻出 {coins} 枚铜币。", self.snapshot())
        if roll < 0.68:
            player["goods_inventory"]["罐头"] = player["goods_inventory"].get("罐头", 0) + 1
            return ActionResult("你在旧木柜里翻出一听还没过期的罐头。", self.snapshot())
        hint = self.random.choice(self.demo_flow["intel_lines"])
        player["rumors"].append(hint)
        player["rumors"] = player["rumors"][-6:]
        return ActionResult("你在夹层里找到一张旧纸条，上面写着一条风声。", self.snapshot())

    def _review_ledger(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        self._advance_clock(18)
        player["credit"] = min(100, player["credit"] + 1)
        hint = self.random.choice(self.demo_flow["intel_lines"])
        player["rumors"].append(hint)
        player["rumors"] = player["rumors"][-6:]
        self.state["last_dialogue"] = {
            "title": "账桌记下的新线索",
            "body": f"[b]你[/b]：把今天看到的价差、传闻和人情都记了下来。\n\n[i]{hint}[/i]",
            "tone": "conversation",
        }
        return ActionResult("你在账桌前把价格、风声和人情重新理顺了一遍。", self.snapshot())

    def _intervene_collective(self, district: str, payload: dict[str, Any]) -> ActionResult:
        action_id = str(payload.get("action_id", "")).strip()
        mode = str(payload.get("mode", "support")).strip().lower()
        mode = {
            "support": "support",
            "back": "support",
            "mediate": "mediate",
            "negotiate": "mediate",
            "suppress": "suppress",
            "pressure": "suppress",
        }.get(mode, "support")
        action = self._collective_row_by_id(action_id)
        if not action:
            candidates = self._active_collective_actions_view(limit=4, district_name=district)
            action = self._collective_row_by_id(str(candidates[0].get("id", ""))) if candidates else None
        if not action:
            return ActionResult("这片街区眼下没有能介入的集体行动。", self.snapshot())
        if str(action.get("resolution_kind", "")):
            return ActionResult("这场集体行动已经出结果了，街上讨论的是它留下的后果。", self.snapshot())
        influence = 0.18 + int(self.state.get("player", {}).get("reputation", 0)) / 140.0 + int(self.state.get("player", {}).get("credit", 0)) / 220.0
        if mode == "support":
            action["player_support"] = round(self._clamp(float(action.get("player_support", 0.0)) + influence, 0.0, 1.6), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) + 0.02 + influence * 0.05, 0.0, 1.0), 3)
            action["commitment"] = round(self._clamp(float(action.get("commitment", 0.0)) + influence * 0.03, 0.0, 1.0), 3)
            self._bump_district_signal(str(action.get("district", district)), "labor_heat", 0.12)
            self._bump_district_signal(str(action.get("district", district)), "gossip", 0.09)
            self.state["player"]["reputation"] = min(100, int(self.state["player"].get("reputation", 0)) + 1)
            message = f"你去 {action.get('target_location_title', '现场')} 给 {action.get('label', '这场行动')} 撑场，现场的承诺阈值被往下压了一截。"
        elif mode == "mediate":
            action["player_mediation"] = round(self._clamp(float(action.get("player_mediation", 0.0)) + influence, 0.0, 1.6), 3)
            action["risk"] = round(self._clamp(float(action.get("risk", 0.0)) - 0.03 - influence * 0.05, 0.08, 1.0), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) + influence * 0.02, 0.0, 1.0), 3)
            self._bump_district_signal(str(action.get("district", district)), "gossip", 0.07)
            self.state["player"]["reputation"] = min(100, int(self.state["player"].get("reputation", 0)) + 1)
            self.state["player"]["family_relations"]["镇政府"] = int(self.state["player"]["family_relations"].get("镇政府", 0)) + 1
            message = f"你在 {action.get('target_location_title', '现场')} 两边跑口风，{action.get('label', '这场行动')} 的谈判阈值开始松动。"
        else:
            action["player_suppression"] = round(self._clamp(float(action.get("player_suppression", 0.0)) + influence, 0.0, 1.6), 3)
            action["risk"] = round(self._clamp(float(action.get("risk", 0.0)) + 0.04 + influence * 0.06, 0.08, 1.0), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) - influence * 0.03, 0.0, 1.0), 3)
            action["commitment"] = round(self._clamp(float(action.get("commitment", 0.0)) - influence * 0.02, 0.0, 1.0), 3)
            self._bump_district_signal(str(action.get("district", district)), "fear", 0.11)
            self.state["player"]["family_relations"]["镇政府"] = int(self.state["player"]["family_relations"].get("镇政府", 0)) + 1
            message = f"你去 {action.get('target_location_title', '现场')} 帮着压场，{action.get('label', '这场行动')} 的到场门槛被抬高了。"
        action["last_actor_id"] = "player"
        action["last_action"] = f"player_{mode}"
        action["last_tick"] = self._world_tick()
        self._record_player_collective_intervention(action, mode)
        self._refresh_collective_action_row(action)
        self._refresh_derived_views()
        return ActionResult(message, self.snapshot())

    def _player_collective_profile(self) -> dict[str, Any]:
        player = self.state.setdefault("player", {})
        profile = player.get("collective_profile", {})
        if not isinstance(profile, dict):
            profile = {}
        defaults: dict[str, Any] = {
            "support_count": 0,
            "mediate_count": 0,
            "suppress_count": 0,
            "worker_standing": 0.0,
            "capital_standing": 0.0,
            "government_standing": 0.0,
            "public_standing": 0.0,
            "dominant_mode": "observe",
            "stance_label": "看风向的人",
            "consecutive_mode": "",
            "consecutive_count": 0,
            "history": [],
        }
        for key, value in defaults.items():
            if key not in profile:
                profile[key] = copy.deepcopy(value)
        if not isinstance(profile.get("history", []), list):
            profile["history"] = []
        player["collective_profile"] = profile
        return profile

    def _refresh_player_collective_profile(self) -> dict[str, Any]:
        profile = self._player_collective_profile()
        counts = {
            "support": int(profile.get("support_count", 0)),
            "mediate": int(profile.get("mediate_count", 0)),
            "suppress": int(profile.get("suppress_count", 0)),
        }
        if sum(counts.values()) <= 0:
            profile["dominant_mode"] = "observe"
            profile["stance_label"] = "看风向的人"
            return profile
        dominant_mode = max(
            counts.keys(),
            key=lambda key: (
                counts[key],
                abs(float(profile.get(f"{'worker' if key == 'support' else 'government' if key == 'suppress' else 'public'}_standing", 0.0))),
            ),
        )
        profile["dominant_mode"] = dominant_mode
        streak = int(profile.get("consecutive_count", 0))
        if dominant_mode == "support":
            profile["stance_label"] = "街头动员者" if streak >= 3 else "给现场撑场的人"
        elif dominant_mode == "mediate":
            profile["stance_label"] = "两边递话的人" if streak < 3 else "能把两边按在桌边的人"
        else:
            profile["stance_label"] = "替机构压场的人" if streak < 3 else "街上都认得的压场熟手"
        return profile

    def _player_collective_attitude_for_family(self, family_name: str) -> str:
        profile = self._refresh_player_collective_profile()
        worker = float(profile.get("worker_standing", 0.0))
        capital = float(profile.get("capital_standing", 0.0))
        government = float(profile.get("government_standing", 0.0))
        public = float(profile.get("public_standing", 0.0))
        dominant = str(profile.get("dominant_mode", "observe"))
        if family_name == "龟甲船坞":
            if worker >= 0.22 and dominant == "support":
                return "把你当成会把工友拢起来的人"
            if capital >= 0.18 and dominant == "suppress":
                return "觉得你会替厂里压场面"
            if dominant == "mediate":
                return "在观察你能不能把工潮按进谈判桌"
        if family_name == "珊瑚银行":
            if capital >= 0.18:
                return "把你当成能替资本看场子的人"
            if worker >= 0.18:
                return "提防你把街头情绪带进盘面"
            if dominant == "mediate":
                return "想先试试你是不是能递话的中间人"
        if family_name == "海藻家族":
            if public >= 0.16 or dominant == "mediate":
                return "觉得你有机会稳住民生口风"
            if worker >= 0.2:
                return "担心你把缺粮和工价拧成一股"
        return ""

    def _record_player_collective_intervention(self, action: dict[str, Any], mode: str) -> None:
        profile = self._player_collective_profile()
        player = self.state.get("player", {})
        counter_key = f"{mode}_count"
        profile[counter_key] = int(profile.get(counter_key, 0)) + 1
        if str(profile.get("consecutive_mode", "")) == mode:
            profile["consecutive_count"] = int(profile.get("consecutive_count", 0)) + 1
        else:
            profile["consecutive_mode"] = mode
            profile["consecutive_count"] = 1
        streak_bonus = max(0.0, min(0.18, (int(profile.get("consecutive_count", 1)) - 1) * 0.03))
        if mode == "support":
            profile["worker_standing"] = round(self._clamp(float(profile.get("worker_standing", 0.0)) + 0.14 + streak_bonus, -1.5, 1.5), 3)
            profile["public_standing"] = round(self._clamp(float(profile.get("public_standing", 0.0)) + 0.08 + streak_bonus * 0.5, -1.5, 1.5), 3)
            profile["capital_standing"] = round(self._clamp(float(profile.get("capital_standing", 0.0)) - 0.06 - streak_bonus * 0.3, -1.5, 1.5), 3)
            profile["government_standing"] = round(self._clamp(float(profile.get("government_standing", 0.0)) - 0.05 - streak_bonus * 0.24, -1.5, 1.5), 3)
            player["family_relations"]["街头互助会"] = int(player.get("family_relations", {}).get("街头互助会", 0)) + 1
        elif mode == "mediate":
            profile["worker_standing"] = round(self._clamp(float(profile.get("worker_standing", 0.0)) + 0.05 + streak_bonus * 0.2, -1.5, 1.5), 3)
            profile["public_standing"] = round(self._clamp(float(profile.get("public_standing", 0.0)) + 0.1 + streak_bonus * 0.36, -1.5, 1.5), 3)
            profile["capital_standing"] = round(self._clamp(float(profile.get("capital_standing", 0.0)) + 0.03 + streak_bonus * 0.12, -1.5, 1.5), 3)
            profile["government_standing"] = round(self._clamp(float(profile.get("government_standing", 0.0)) + 0.06 + streak_bonus * 0.24, -1.5, 1.5), 3)
        else:
            profile["worker_standing"] = round(self._clamp(float(profile.get("worker_standing", 0.0)) - 0.12 - streak_bonus * 0.32, -1.5, 1.5), 3)
            profile["public_standing"] = round(self._clamp(float(profile.get("public_standing", 0.0)) - 0.06 - streak_bonus * 0.18, -1.5, 1.5), 3)
            profile["capital_standing"] = round(self._clamp(float(profile.get("capital_standing", 0.0)) + 0.08 + streak_bonus * 0.26, -1.5, 1.5), 3)
            profile["government_standing"] = round(self._clamp(float(profile.get("government_standing", 0.0)) + 0.14 + streak_bonus * 0.4, -1.5, 1.5), 3)
        profile["history"].insert(
            0,
            {
                "kind": "intervention",
                "clock_label": self._clock_label(),
                "mode": mode,
                "action_id": str(action.get("id", "")),
                "label": str(action.get("label", "")),
                "district": str(action.get("district", "")),
            },
        )
        profile["history"] = profile["history"][:12]
        self._refresh_player_collective_profile()

    def _record_player_collective_outcome(self, action: dict[str, Any], resolution_kind: str) -> None:
        profile = self._player_collective_profile()
        support_push = float(action.get("player_support", 0.0)) + float(action.get("player_mediation", 0.0))
        suppress_push = float(action.get("player_suppression", 0.0))
        if resolution_kind == "conceded":
            if support_push >= suppress_push:
                profile["worker_standing"] = round(self._clamp(float(profile.get("worker_standing", 0.0)) + 0.06, -1.5, 1.5), 3)
                profile["public_standing"] = round(self._clamp(float(profile.get("public_standing", 0.0)) + 0.08, -1.5, 1.5), 3)
                profile["government_standing"] = round(self._clamp(float(profile.get("government_standing", 0.0)) + (0.05 if float(action.get("player_mediation", 0.0)) > 0 else -0.03), -1.5, 1.5), 3)
            else:
                profile["capital_standing"] = round(self._clamp(float(profile.get("capital_standing", 0.0)) + 0.04, -1.5, 1.5), 3)
        elif resolution_kind == "escalated":
            if suppress_push > support_push:
                profile["government_standing"] = round(self._clamp(float(profile.get("government_standing", 0.0)) + 0.07, -1.5, 1.5), 3)
                profile["capital_standing"] = round(self._clamp(float(profile.get("capital_standing", 0.0)) + 0.05, -1.5, 1.5), 3)
                profile["worker_standing"] = round(self._clamp(float(profile.get("worker_standing", 0.0)) - 0.08, -1.5, 1.5), 3)
            else:
                profile["worker_standing"] = round(self._clamp(float(profile.get("worker_standing", 0.0)) + 0.08, -1.5, 1.5), 3)
                profile["public_standing"] = round(self._clamp(float(profile.get("public_standing", 0.0)) + 0.06, -1.5, 1.5), 3)
                profile["government_standing"] = round(self._clamp(float(profile.get("government_standing", 0.0)) - 0.08, -1.5, 1.5), 3)
                profile["capital_standing"] = round(self._clamp(float(profile.get("capital_standing", 0.0)) - 0.05, -1.5, 1.5), 3)
        profile["history"].insert(
            0,
            {
                "kind": "outcome",
                "clock_label": self._clock_label(),
                "mode": str(profile.get("dominant_mode", "observe")),
                "action_id": str(action.get("id", "")),
                "label": str(action.get("label", "")),
                "district": str(action.get("district", "")),
                "resolution_kind": resolution_kind,
            },
        )
        profile["history"] = profile["history"][:12]
        self._refresh_player_collective_profile()

    def _queue_collective_followup(self, action: dict[str, Any], resolution_kind: str) -> None:
        current_tick = self._world_tick()
        followups = list(self.state.get("collective_followups", []))
        source_id = str(action.get("id", ""))
        if resolution_kind == "conceded":
            company = self._collective_company_for_action(action)
            if company:
                followups.insert(
                    0,
                    {
                        "id": f"{source_id}_settlement_{current_tick}",
                        "source_action_id": source_id,
                        "company_id": str(company.get("id", "")),
                        "family_name": str(company.get("family_owner", "")),
                        "district": str(action.get("district", "")),
                        "kind": "settlement",
                        "status": "active",
                        "created_tick": current_tick,
                        "last_tick": current_tick,
                        "expires_tick": current_tick + 14 * 60,
                        "wage_bonus_remaining": 0.42 if str(action.get("kind", "")) == "strike" else 0.24,
                        "inventory_release_remaining": 10.0 if str(action.get("district", "")) in {"工厂区", "港口"} else 8.0,
                        "payroll_relief_remaining": 9.0,
                    },
                )
        elif resolution_kind == "escalated":
            followups.insert(
                0,
                {
                    "id": f"{source_id}_crackdown_{current_tick}",
                    "source_action_id": source_id,
                    "district": str(action.get("district", "")),
                    "kind": "crackdown",
                    "status": "active",
                    "created_tick": current_tick,
                    "last_tick": current_tick,
                    "expires_tick": current_tick + 12 * 60,
                    "rumor_tick": current_tick + 18,
                    "action_tick": current_tick + 40,
                    "secondary_topic_id": "",
                    "followup_action_id": "",
                    "escalation_level": int(action.get("escalation_level", 0)) + 1,
                },
            )
        self.state["collective_followups"] = followups[:16]

    def _spawn_collective_followup_action(self, source_action: dict[str, Any], topic_id: str, escalation_level: int) -> dict[str, Any] | None:
        action_id = f"{str(source_action.get('id', 'collective'))}_followup_{escalation_level}"
        existing = self._collective_row_by_id(action_id)
        if existing:
            return existing
        district = "交易所" if str(source_action.get("district", "")) != "交易所" else str(source_action.get("district", ""))
        thresholds = self._collective_thresholds("rally")
        current_tick = self._world_tick()
        action = {
            "id": action_id,
            "kind": "rally",
            "district": district,
            "scope": "city",
            "label": f"全城声援{str(source_action.get('district', '街区'))}集会",
            "theme": f"反对{str(source_action.get('label', '集体行动'))}后的镇压",
            "status": "emerging",
            "stage": "forming",
            "heat": round(self._clamp(float(source_action.get("heat", 0.0)) * 0.76 + 0.18, 0.18, 0.92), 3),
            "support": round(self._clamp(float(source_action.get("support", 0.0)) * 0.74 + 0.12, 0.12, 0.9), 3),
            "commitment": round(self._clamp(float(source_action.get("commitment", 0.0)) * 0.68 + 0.06, 0.04, 0.6), 3),
            "turnout": 0.0,
            "risk": round(self._clamp(float(source_action.get("risk", 0.0)) + 0.08, 0.16, 1.0), 3),
            "expected_reward": max(0.38, thresholds["reward"]),
            "support_threshold": thresholds["support"],
            "commitment_threshold": thresholds["commitment"],
            "turnout_threshold": thresholds["turnout"],
            "source_topic_ids": self._dedupe_id_list([topic_id, *list(source_action.get("source_topic_ids", []))]),
            "source_norm_ids": self._dedupe_id_list(list(source_action.get("source_norm_ids", []))),
            "target_groups": self._dedupe_id_list([*list(source_action.get("target_groups", [])), "居民", "店主", "记者"], limit=10),
            "heard_ids": self._dedupe_id_list([*list(source_action.get("heard_ids", [])), *list(source_action.get("supporter_ids", []))], limit=14),
            "supporter_ids": self._dedupe_id_list([*list(source_action.get("supporter_ids", [])), *list(source_action.get("committed_ids", []))], limit=12),
            "committed_ids": self._dedupe_id_list(list(source_action.get("committed_ids", [])), limit=8),
            "attendee_ids": [],
            "organizer_ids": self._dedupe_id_list(list(source_action.get("organizer_ids", [])), limit=4),
            "suppression_ids": [],
            "created_tick": current_tick,
            "start_tick": 0,
            "last_tick": current_tick,
            "last_actor_id": "system",
            "last_action": "aftershock",
            "player_support": 0.0,
            "player_mediation": 0.0,
            "player_suppression": 0.0,
            "player_threshold_shift": 0.0,
            "effective_support_threshold": thresholds["support"],
            "effective_commitment_threshold": thresholds["commitment"],
            "effective_turnout_threshold": thresholds["turnout"],
            "resolution_kind": "",
            "resolution_label": "",
            "resolution_note": "",
            "resolution_tick": 0,
            "resolution_crowd_score": 0.0,
            "resolution_response_score": 0.0,
            "parent_action_id": str(source_action.get("id", "")),
            "escalation_level": int(escalation_level),
        }
        registry = list(self.state.get("collective_action_registry", []))
        registry.append(action)
        self.state["collective_action_registry"] = registry
        self._resolve_collective_responses()
        self._refresh_collective_action_row(action)
        return action

    def _apply_collective_followups(self, delta_minutes: int) -> None:
        if delta_minutes <= 0:
            return
        current_tick = self._world_tick()
        keep_rows: list[dict[str, Any]] = []
        for raw_row in list(self.state.get("collective_followups", [])):
            row = raw_row
            kind = str(row.get("kind", ""))
            status = str(row.get("status", "active"))
            if status not in {"active", "completed"}:
                continue
            if kind == "settlement" and status == "active":
                company = self._find_by_id(self.state.get("companies", []), str(row.get("company_id", "")))
                scale = max(0.24, min(1.0, delta_minutes / 42.0))
                if not company:
                    row["status"] = "expired"
                else:
                    wage_step = min(float(row.get("wage_bonus_remaining", 0.0)), 0.06 * scale)
                    if wage_step > 0:
                        company["wage_level"] = round(min(14.0, float(company.get("wage_level", 5.0)) + wage_step), 3)
                        row["wage_bonus_remaining"] = round(max(0.0, float(row.get("wage_bonus_remaining", 0.0)) - wage_step), 3)
                    inventory_step = min(float(row.get("inventory_release_remaining", 0.0)), max(0.0, round(delta_minutes / 18.0, 2)))
                    if inventory_step > 0:
                        company["inventory"] = int(min(220, int(company.get("inventory", 60)) + max(1, int(round(inventory_step)))))
                        row["inventory_release_remaining"] = round(max(0.0, float(row.get("inventory_release_remaining", 0.0)) - inventory_step), 3)
                    payroll_step = min(float(row.get("payroll_relief_remaining", 0.0)), 1.1 * scale)
                    if payroll_step > 0:
                        company["payroll_delay"] = round(max(0.0, float(company.get("payroll_delay", 0.0)) - payroll_step), 3)
                        row["payroll_relief_remaining"] = round(max(0.0, float(row.get("payroll_relief_remaining", 0.0)) - payroll_step), 3)
                    row["last_tick"] = current_tick
                    if (
                        float(row.get("wage_bonus_remaining", 0.0)) <= 0.01
                        and float(row.get("inventory_release_remaining", 0.0)) <= 0.01
                        and float(row.get("payroll_relief_remaining", 0.0)) <= 0.01
                    ) or current_tick >= int(row.get("expires_tick", current_tick)):
                        row["status"] = "completed"
                        packet = {
                            "id": f"{row.get('id', 'settlement')}_landed_{current_tick}",
                            "district": str(row.get("district", "")),
                            "source": "让步落实",
                            "title": "让步开始落地",
                            "line": f"{company.get('name', '公司')} 开始把答应过的工资和配给一点点吐出来了。",
                            "body": f"{company.get('name', '公司')} 的让步正在落地，工资、拖薪和库存都比前一阵松了一截。",
                            "tags": ["集体行动", "让步", "落实"],
                            "scope": "district",
                            "topic_kind": "labor",
                            "goods_delta": {},
                            "stocks_delta": {str(company.get('stock_name', '')): -0.01} if str(company.get("stock_name", "")) else {},
                            "macro_delta": {"worker_unrest": -0.6},
                            "family_delta": {str(row.get("family_name", "")): -0.01} if str(row.get("family_name", "")) else {},
                        }
                        self._apply_intel_packet(packet, to_player=False, promote_news=False, intensity=0.5)
            elif kind == "crackdown" and status == "active":
                source_action = self._collective_row_by_id(str(row.get("source_action_id", "")))
                if not source_action:
                    row["status"] = "expired"
                else:
                    if not str(row.get("secondary_topic_id", "")) and current_tick >= int(row.get("rumor_tick", current_tick)):
                        company = self._collective_company_for_action(source_action)
                        packet = {
                            "id": f"{row.get('id', 'crackdown')}_rumor_{current_tick}",
                            "district": str(source_action.get("district", "")),
                            "source": "镇压余波",
                            "title": "清场画面传开了",
                            "line": f"{source_action.get('target_location_title', '现场')} 的清场画面传开后，更多人开始把这事当成全镇议题。",
                            "body": f"{source_action.get('label', '集体行动')} 的清场余波已经传出原街区，记者、商户和居民都开始讨论要不要继续跟进。",
                            "tags": ["集体行动", "镇压", "扩散"],
                            "scope": "city",
                            "topic_kind": "public",
                            "goods_delta": {},
                            "stocks_delta": {str((company or {}).get('stock_name', '')): -0.03} if str((company or {}).get("stock_name", "")) else {},
                            "macro_delta": {"worker_unrest": 1.4, "media_sentiment": -0.6},
                            "family_delta": {str((company or {}).get('family_owner', '')): -0.03} if str((company or {}).get("family_owner", "")) else {},
                        }
                        topic_row = self._apply_intel_packet(packet, to_player=False, promote_news=True, intensity=0.86)
                        row["secondary_topic_id"] = str((topic_row or {}).get("id", ""))
                        row["last_tick"] = current_tick
                    if str(row.get("secondary_topic_id", "")) and not str(row.get("followup_action_id", "")) and current_tick >= int(row.get("action_tick", current_tick)):
                        followup_action = self._spawn_collective_followup_action(source_action, str(row.get("secondary_topic_id", "")), int(row.get("escalation_level", 1)))
                        if followup_action:
                            row["followup_action_id"] = str(followup_action.get("id", ""))
                        row["status"] = "completed"
                        row["last_tick"] = current_tick
            if str(row.get("status", "active")) in {"active", "completed"} and current_tick - int(row.get("last_tick", current_tick)) <= 8 * 60:
                keep_rows.append(row)
        self.state["collective_followups"] = keep_rows[:16]

    def _trade_good(self, good_name: str, quantity: int, direction: int, payload: dict[str, Any] | None = None) -> ActionResult:
        player = self.state["player"]
        good = self._find_by_name(self.state["goods"], good_name)
        if not good:
            return ActionResult("没有这个货物。", self.snapshot())
        payload = payload or {}
        npc: dict[str, Any] | None = None
        npc_id = str(payload.get("npc_id", ""))
        if npc_id:
            npc = self._find_npc(npc_id)
        quantity = max(quantity, 1)
        unit_price = int(good["current_price"])
        trade_tone = "按市场价"
        if npc:
            unit_price, trade_tone = self._npc_good_quote(npc, good_name, direction)
        cost = unit_price * quantity
        if direction > 0:
            if npc and int(npc.get("inventory", {}).get(good_name, 0)) < quantity:
                return ActionResult(f"{npc['name']} 手里现在没有这么多 {good_name}。", self.snapshot())
            if player["cash"] < cost:
                return ActionResult("铜币不够。", self.snapshot())
            player["cash"] -= cost
            player["goods_inventory"][good_name] = player["goods_inventory"].get(good_name, 0) + quantity
            if npc:
                npc["cash"] = int(npc.get("cash", 0)) + cost
                npc["inventory"][good_name] = max(0, int(npc.get("inventory", {}).get(good_name, 0)) - quantity)
                npc["speech_lines"] = [f"{trade_tone}，{good_name} 我先给你 {quantity} 份。", *npc.get("speech_lines", [])[:2]]
            self._increment_task_progress("trade_goods", good_name, quantity)
            self.state["demo_metrics"]["goods_trades"] = int(self.state["demo_metrics"].get("goods_trades", 0)) + quantity
            self.state["market_pressure"]["goods"][good_name] = float(self.state["market_pressure"]["goods"].get(good_name, 0.0)) + 0.05 * quantity
            self._bump_district_signal("贫民街" if good_name == "面包" else "工厂区" if good_name == "煤" else "港口", "trade_heat", 0.08 * quantity)
            self._update_player_class()
            self._refresh_derived_views()
            if npc:
                return ActionResult(f"你从 {npc['name']} 手里买下 {good_name} x{quantity}，成交价 {cost} 铜币。", self.snapshot())
            return ActionResult(f"买入 {good_name} x{quantity}。", self.snapshot())
        if player["goods_inventory"].get(good_name, 0) < quantity:
            return ActionResult("库存不足。", self.snapshot())
        if npc and int(npc.get("cash", 0)) < cost:
            return ActionResult(f"{npc['name']} 手头铜币不够，不肯接这单。", self.snapshot())
        player["goods_inventory"][good_name] -= quantity
        player["cash"] += cost
        if npc:
            npc["cash"] = max(0, int(npc.get("cash", 0)) - cost)
            npc["inventory"][good_name] = int(npc.get("inventory", {}).get(good_name, 0)) + quantity
            npc["speech_lines"] = [f"{trade_tone}，{good_name} 我收下了。", *npc.get("speech_lines", [])[:2]]
        self._increment_task_progress("trade_goods", good_name, quantity)
        self.state["demo_metrics"]["goods_trades"] = int(self.state["demo_metrics"].get("goods_trades", 0)) + quantity
        self.state["market_pressure"]["goods"][good_name] = float(self.state["market_pressure"]["goods"].get(good_name, 0.0)) - 0.04 * quantity
        self._bump_district_signal("贫民街" if good_name == "面包" else "工厂区" if good_name == "煤" else "港口", "trade_heat", 0.06 * quantity)
        self._update_player_class()
        self._refresh_derived_views()
        if npc:
            return ActionResult(f"你把 {good_name} x{quantity} 卖给了 {npc['name']}，收回 {cost} 铜币。", self.snapshot())
        return ActionResult(f"卖出 {good_name} x{quantity}。", self.snapshot())

    def _record_player_cash_gift(self, npc: dict[str, Any], amount: int) -> dict[str, Any]:
        memory = self._npc_player_memory(npc)
        total = int(memory.get("cash_gift_total", 0)) + amount
        memory["cash_gift_total"] = total
        memory["cash_gift_count"] = int(memory.get("cash_gift_count", 0)) + 1
        memory["last_gift_amount"] = amount
        bribe_threshold = self._npc_bribe_threshold(npc)
        follow_threshold = self._npc_follow_threshold(npc)
        if total >= bribe_threshold:
            memory["bought_over"] = True
        if total >= follow_threshold:
            memory["follows_player"] = True
        trust_boost = 4.0 if amount >= bribe_threshold else 2.2 if amount >= max(10_000, bribe_threshold // 2) else 0.8
        relation_boost = 5 if amount >= follow_threshold else 3 if amount >= bribe_threshold else 1
        npc["player_trust"] = min(100.0, float(npc.get("player_trust", 0.0)) + trust_boost)
        npc["player_relation"] = int(npc.get("player_relation", 0)) + relation_boost
        npc["proactive_interest"] = min(0.98, float(npc.get("proactive_interest", 0.3)) + (0.18 if bool(memory.get("follows_player", False)) else 0.08))
        npc["player_memory"] = memory
        return memory

    def _high_finance_contact(self, npc: dict[str, Any]) -> bool:
        name = str(npc.get("name", ""))
        title = str(npc.get("title", ""))
        role = str(npc.get("role", ""))
        if name in {"戈登", "伊莎贝拉", "温斯顿", "伊芙琳"}:
            return True
        return role in {"镇长", "律师", "银行经理"} or any(token in title for token in ["局长", "镇长", "法律", "银行"])

    def _intel_required_tier_rank(self, charge: int) -> int:
        if charge >= 5_000:
            return 3
        if charge >= 1_000:
            return 2
        return 1

    def _gift_money_to_npc(self, npc_id: str, amount: int, district: str) -> ActionResult:
        npc = self._find_npc(npc_id)
        if not npc:
            return ActionResult("找不到这个人。", self.snapshot())
        player = self._ensure_player_financial_state()
        amount = max(0, int(amount))
        if amount <= 0:
            return ActionResult("送钱至少也得掏出一点真铜币。", self.snapshot())
        tier = self._stock_account_tier()
        if self._high_finance_contact(npc) and int(tier.get("rank", 1)) < 3:
            return ActionResult("你的账户等级不够，暂时没有资格收买这种级别的人物。", self.snapshot())
        if int(player.get("cash", 0)) < amount:
            return ActionResult("你手头没有这么多钱。", self.snapshot())
        player["cash"] = int(player.get("cash", 0)) - amount
        npc["cash"] = int(npc.get("cash", 0)) + amount
        memory = self._record_player_cash_gift(npc, amount)
        bought_over = bool(memory.get("bought_over", False))
        follows_player = bool(memory.get("follows_player", False))
        npc["speech_lines"] = [
            "这笔钱我记下了，后面该往哪边站我会重新掂量。"
            if bought_over and not follows_player
            else "你这一下给得不轻，我会记住是谁在托我。"
            if follows_player
            else "钱先收下，这份人情我记着。",
            *npc.get("speech_lines", [])[:2],
        ]
        self._remember_npc_event(
            npc,
            "player_gift_money",
            {
                "amount": amount,
                "bought_over": bought_over,
                "follows_player": follows_player,
            },
        )
        self._remember_local_memory(
            npc,
            kind="player_gift_money",
            summary=f"玩家当面给了你 {amount} 铜币，这笔钱已经进了你的兜。你现在对他的态度是：{self._npc_player_status(npc)}。",
            counterpart_id="player",
            counterpart_name="玩家",
            tags=["送钱", "收买" if bought_over else "人情", "跟随" if follows_player else "观察"],
            salience=0.92 if follows_player else 0.8 if bought_over else 0.58,
        )
        self._bump_district_signal(str(npc.get("district", district)), "liquidity", min(0.6, amount / 40_000.0))
        self._refresh_derived_views()
        if follows_player:
            return ActionResult(f"你塞给 {npc['name']} {amount} 铜币。对方已经把你当成新的靠山。", self.snapshot())
        if bought_over:
            return ActionResult(f"你塞给 {npc['name']} {amount} 铜币。对方的口风已经明显往你这边偏了。", self.snapshot())
        return ActionResult(f"你给了 {npc['name']} {amount} 铜币。对方记下了这笔钱。", self.snapshot())

    def _intel_topic_for_npc(self, npc: dict[str, Any], district: str, topic_id: str = "") -> dict[str, Any]:
        topic = self._resolve_talk_topic(npc, topic_id, district or str(npc.get("district", "")))
        personal_topics = self._npc_personal_topics(npc)
        if personal_topics:
            lead = personal_topics[0]
            if not topic or str(topic.get("id", "")) == "generic_wind" or float(lead.get("heat", 0.0)) > float(topic.get("heat", 0.0)) + 0.08:
                return lead
        return topic

    def _buy_intel_from_npc(self, npc_id: str, amount: int, topic_id: str, district: str) -> ActionResult:
        npc = self._find_npc(npc_id)
        if not npc:
            return ActionResult("找不到这个人。", self.snapshot())
        if not self._npc_can_sell_info(npc):
            return ActionResult(f"{npc['name']} 现在还不肯拿真消息换钱。", self.snapshot())
        player = self._ensure_player_financial_state()
        topic = self._intel_topic_for_npc(npc, district, topic_id)
        price = self._npc_intel_price(npc, topic)
        charge = max(price, int(amount or 0))
        tier = self._stock_account_tier()
        required_rank = self._intel_required_tier_rank(charge)
        if int(tier.get("rank", 1)) < required_rank:
            label = "白银级" if required_rank == 2 else "黄金级"
            return ActionResult(f"这条内幕需要 {label} 账户权限。你现在的账户等级还不够。", self.snapshot())
        if int(player.get("cash", 0)) < charge:
            return ActionResult(f"这条口风要 {charge} 铜币，你现在拿不出来。", self.snapshot())
        player["cash"] = int(player.get("cash", 0)) - charge
        npc["cash"] = int(npc.get("cash", 0)) + charge
        memory = self._npc_player_memory(npc)
        memory["intel_spend_total"] = int(memory.get("intel_spend_total", 0)) + charge
        memory["intel_bought"] = int(memory.get("intel_bought", 0)) + 1
        memory["trust_streak"] = min(8, int(memory.get("trust_streak", 0)) + 1)
        npc["player_memory"] = memory
        truth_profile = self._truth_metrics_for_topic(npc, topic, "friendly", "花钱买消息")
        intel = self._build_intel_packet_from_topic(topic, npc, district or str(npc.get("district", "")))
        intel = self._spin_intel_packet(intel, npc, truth_profile, topic)
        paid_ratio = charge / float(max(price, 1))
        strength = max(0.42, min(1.0, 0.52 + paid_ratio * 0.22 + float(npc.get("player_trust", 0.0)) / 220.0))
        promote_news = strength >= 0.78 or str(topic.get("kind", "")) in {"asset", "family", "company", "institution", "finance"}
        self._apply_intel_packet(intel, to_player=True, promote_news=promote_news, intensity=strength)
        npc["speech_lines"] = [f"钱我收了，这条你拿稳：{intel.get('line', topic.get('summary', '风声先记着。'))}", *npc.get("speech_lines", [])[:2]]
        self._remember_npc_event(
            npc,
            "player_buy_intel",
            {
                "amount": charge,
                "topic_id": str(topic.get("id", "")),
                "topic_label": str(topic.get("label", "")),
            },
        )
        self._remember_local_memory(
            npc,
            kind="player_buy_intel",
            summary=f"玩家花了 {charge} 铜币从你这里买走了一条关于{topic.get('label', '街头风声')}的消息。",
            counterpart_id="player",
            counterpart_name="玩家",
            topic_id=str(topic.get("id", "")),
            topic_label=str(topic.get("label", "")),
            tags=["卖消息", str(topic.get("kind", "")), "现金"],
            salience=0.84,
        )
        self._bump_district_signal(str(npc.get("district", district)), "gossip", 0.16 + min(0.24, charge / 12_000.0))
        self._bump_district_signal(str(npc.get("district", district)), "liquidity", min(0.42, charge / 20_000.0))
        self.state["demo_metrics"]["intel_actions"] = int(self.state["demo_metrics"].get("intel_actions", 0)) + 1
        self._apply_intraday_market_move(reason="player_talk", decay=0.76)
        self._refresh_derived_views()
        return ActionResult(f"你花了 {charge} 铜币从 {npc['name']} 那里买到一条消息。", self.snapshot())

    def _npc_good_quote(self, npc: dict[str, Any], good_name: str, direction: int) -> tuple[int, str]:
        good = self._find_by_name(self.state["goods"], good_name)
        base_price = int(good.get("current_price", 1)) if good else 1
        pressure = float(npc.get("anxiety", npc.get("fear", 0))) * 0.02
        greed = float(npc.get("greed_drive", npc.get("greed", 0))) * 0.015
        trust_discount = max(-0.12, min(0.08, (50.0 - float(npc.get("player_trust", 50.0))) / 250.0))
        if direction > 0:
            factor = 1.0 + greed + pressure + trust_discount
            tone = "要按我这口价"
        else:
            factor = 0.84 - greed * 0.12 - pressure * 0.06 - trust_discount * 0.4
            factor = max(0.55, factor)
            tone = "只能按这个价回收"
        return max(1, int(round(base_price * factor))), tone

    def _default_trade_quotes_for_npc(self, npc: dict[str, Any], topic_id: str = "") -> list[dict[str, Any]]:
        quotes: list[dict[str, Any]] = []
        inventory = copy.deepcopy(npc.get("inventory", {}))
        for action_type, good_name, quantity, prefix in [
            ("buy_goods", "面包", 1, "买"),
            ("buy_goods", "煤", 1, "买"),
            ("sell_goods", "罐头", 1, "卖"),
        ]:
            if action_type == "buy_goods" and int(inventory.get(good_name, 0)) <= 0:
                continue
            if action_type == "sell_goods" and int(self.state["player"]["goods_inventory"].get(good_name, 0)) <= 0:
                continue
            unit_price, tone = self._npc_good_quote(npc, good_name, 1 if action_type == "buy_goods" else -1)
            quotes.append(
                {
                    "action_type": action_type,
                    "good_name": good_name,
                    "quantity": quantity,
                    "amount": unit_price * quantity,
                    "unit_price": unit_price,
                    "description": f"{prefix}{good_name} x{quantity}，{tone}，单价 {unit_price} 铜币。",
                    "button": f"{prefix}{good_name}",
                }
            )
        bribe_threshold = self._npc_bribe_threshold(npc)
        follow_threshold = self._npc_follow_threshold(npc)
        for amount in [max(1_000, bribe_threshold // 4), bribe_threshold, follow_threshold]:
            label = "打点一下" if amount < bribe_threshold else "直接收买" if amount < follow_threshold else "砸成自己人"
            quotes.append(
                {
                    "action_type": "gift_money",
                    "quantity": 1,
                    "amount": amount,
                    "button": f"送 {amount} 铜币",
                    "description": f"{label}，把 {amount} 铜币真的塞到对方手里。对方现金会增加，也会把这笔钱记在你头上。",
                }
            )
        intel_topic = self._intel_topic_for_npc(npc, str(npc.get("district", "")), topic_id)
        if self._npc_can_sell_info(npc):
            intel_price = self._npc_intel_price(npc, intel_topic)
            quotes.append(
                {
                    "action_type": "buy_intel",
                    "quantity": 1,
                    "amount": intel_price,
                    "topic_id": str(intel_topic.get("id", "")),
                    "button": f"买消息 {intel_price}",
                    "description": f"花 {intel_price} 铜币买一条关于“{intel_topic.get('label', '街头风声')}”的消息，这笔钱会真的进对方口袋。",
                }
            )
        return quotes

    def _npc_inventory_summary(self, npc: dict[str, Any]) -> str:
        inventory = copy.deepcopy(npc.get("inventory", {}))
        rows = [f"{name}:{int(inventory.get(name, 0))}" for name in ["面包", "煤", "罐头"]]
        return " / ".join(rows)

    def _normalize_npc_inventory(self, npc: dict[str, Any]) -> dict[str, int]:
        inventory = copy.deepcopy(npc.get("inventory", {}))
        if not isinstance(inventory, dict):
            inventory = {}
        normalized = {
            "面包": int(inventory.get("面包", 0)),
            "煤": int(inventory.get("煤", 0)),
            "罐头": int(inventory.get("罐头", 0)),
        }
        if sum(normalized.values()) > 0:
            return normalized
        role = str(npc.get("role", ""))
        district = str(npc.get("district", ""))
        class_name = str(npc.get("class", ""))
        if role in {"店主", "老板"}:
            normalized = {"面包": 3, "煤": 1, "罐头": 2}
        elif role in {"代理人", "银行经理", "记者", "投机者"}:
            normalized = {"面包": 1, "煤": 0, "罐头": 1}
        elif role in {"工会领袖"}:
            normalized = {"面包": 2, "煤": 1, "罐头": 1}
        elif class_name == "底层":
            normalized = {"面包": 1, "煤": 1, "罐头": 0}
        else:
            normalized = {"面包": 2, "煤": 1, "罐头": 1}
        if district == "港口":
            normalized["罐头"] = max(normalized["罐头"], 1)
        if district == "工厂区":
            normalized["煤"] = max(normalized["煤"], 1)
        return normalized

    def _stock_issued_shares(self, stock: dict[str, Any]) -> int:
        name = str(stock.get("name", ""))
        ticker = str(stock.get("ticker", "")).upper()
        if name in {"海藻重工", "海藻食业"} or ticker == "SWC":
            return 120_000
        if name in {"市政债券", "珊瑚金控"} or ticker == "AMB":
            return 90_000
        if name in {"龟甲物流", "龟甲船运"} or ticker == "TSL":
            return 100_000
        return 60_000

    def _rebuild_stock_holder_registry(self) -> None:
        registry: dict[str, list[dict[str, Any]]] = {str(stock.get("name", "")): [] for stock in self.state.get("stocks", [])}
        player = self.state.get("player", {})
        for stock_name, qty in dict(player.get("stock_holdings", {})).items():
            if int(qty) <= 0 or stock_name not in registry:
                continue
            registry[stock_name].append({"holder_id": "player", "holder_name": "玩家", "holder_kind": "player", "shares": int(qty)})
        for npc in self.state.get("npcs", []):
            for stock_name, qty in dict(npc.get("stock_positions", {})).items():
                if int(qty) <= 0 or stock_name not in registry:
                    continue
                registry[stock_name].append(
                    {
                        "holder_id": str(npc.get("id", "")),
                        "holder_name": str(npc.get("name", "")),
                        "holder_kind": "npc",
                        "shares": int(qty),
                    }
                )
        for rows in registry.values():
            rows.sort(key=lambda row: int(row.get("shares", 0)), reverse=True)
        self.state["stock_holder_registry"] = registry

    @staticmethod
    def _stock_market_session_bounds() -> tuple[int, int]:
        return 0, 24 * 60 - 1

    def _stock_market_is_open(self) -> bool:
        return True

    def _stock_market_session_label(self) -> str:
        start_minutes, end_minutes = self._stock_market_session_bounds()
        return f"{start_minutes // 60:02d}:{start_minutes % 60:02d}-{(end_minutes + 1) // 60:02d}:{(end_minutes + 1) % 60:02d}"

    def _stock_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        needle = str(ticker).strip().upper()
        if not needle:
            return None
        for stock in self.state.get("stocks", []):
            if str(stock.get("ticker", "")).strip().upper() == needle:
                return stock
        return None

    def _stock_view_name(self, stock: dict[str, Any]) -> str:
        ticker = str(stock.get("ticker", "")).strip().upper()
        display_name = str(stock.get("display_name", stock.get("name", ""))).strip()
        if ticker and display_name and display_name.startswith(ticker):
            return display_name
        if ticker and display_name:
            return f"{ticker} {display_name}"
        return display_name or str(stock.get("name", ""))

    def _story_metrics_state(self) -> dict[str, Any]:
        metrics = self.state.setdefault("story_metrics", {})
        metrics.setdefault("sam_revolution_fund", 0)
        metrics.setdefault("sam_tax_total", 0)
        metrics.setdefault("player_trading_fees", 0)
        metrics.setdefault("reputation", {"FC": 10, "FB": 5, "SN": 20})
        metrics.setdefault("shadow_reputation", {"S_WWI": 15, "S_DBH": 10, "S_NAC": 20, "SUI": 15, "ST": 1.0, "WL": 1})
        return metrics

    def _stock_ops_state(self) -> dict[str, Any]:
        metrics = self._story_metrics_state()
        ops = metrics.setdefault("stock_ops", {})
        ops.setdefault("policy_shield_until_tick", 0)
        ops.setdefault("scar_cover_until_tick", 0)
        ops.setdefault("rep_drag_until_tick", 0)
        ops.setdefault("victor_takeover_done", False)
        ops.setdefault("gala_invite_unlocked", False)
        ops.setdefault("story_sui_bonus", 0.0)
        ops.setdefault("story_st_floor", 1.0)
        ops.setdefault("last_action", "")
        return ops

    def _ensure_player_financial_state(self) -> dict[str, Any]:
        player = self.state.setdefault("player", {})
        player.setdefault("health", 100)
        player.setdefault("story_route", "")
        player.setdefault("financial_route", "")
        player.setdefault("route_intro_pending", True)
        player.setdefault("route_selected_at", "")
        player.setdefault("stock_margin_debt", 0)
        player.setdefault("stock_short_positions", {})
        player.setdefault("stock_account_locked", False)
        player.setdefault("stock_account_lock_reason", "")
        player.setdefault("stock_liquidation_pending", False)
        player.setdefault("stock_liquidation_note", "")
        player.setdefault("stock_liquidation_due_tick", 0)
        for stock in self.state.get("stocks", []):
            stock_name = str(stock.get("name", ""))
            if stock_name and stock_name not in player["stock_short_positions"]:
                player["stock_short_positions"][stock_name] = {"quantity": 0, "avg_price": 0.0}
        self.state.setdefault("ending_state", {})
        return player

    def _route_choice_required(self) -> bool:
        player = self._ensure_player_financial_state()
        return bool(player.get("route_intro_pending", False)) or not str(player.get("story_route", "")).strip()

    def _story_timeline_state(self) -> dict[str, Any]:
        timeline = self.state.setdefault("story_timeline", {})
        timeline.setdefault("fired", [])
        timeline.setdefault("log", [])
        return timeline

    def _story_event_fired(self, event_id: str) -> bool:
        timeline = self._story_timeline_state()
        return str(event_id) in {str(value) for value in timeline.get("fired", [])}

    def _mark_story_event_fired(self, event_id: str) -> None:
        timeline = self._story_timeline_state()
        fired = [str(value) for value in timeline.get("fired", [])]
        if str(event_id) not in fired:
            fired.append(str(event_id))
        timeline["fired"] = fired

    def _append_story_timeline_log(self, event_id: str, title: str, description: str) -> None:
        timeline = self._story_timeline_state()
        log = list(timeline.get("log", []))
        log.insert(
            0,
            {
                "id": str(event_id),
                "title": str(title),
                "description": str(description),
                "clock": self._clock_label(),
                "day": int(self.state.get("day", 1)),
            },
        )
        timeline["log"] = log[:12]

    def _force_stock_price(self, ticker: str, target_price: int, *, note: str = "", pressure: float | None = None) -> dict[str, Any] | None:
        stock = self._stock_by_ticker(ticker)
        if not stock:
            return None
        stock["current_price"] = max(1, int(target_price))
        stock["last_trade_price"] = int(stock["current_price"])
        stock["reference_price"] = round(float(stock["current_price"]), 3)
        stock["market_cap"] = int(int(stock.get("issued_shares", 0)) * int(stock["current_price"]))
        stock["market_sentiment"] = "乐观" if int(stock["current_price"]) >= int(stock.get("previous_close", stock["current_price"])) else "恐慌"
        if pressure is not None:
            self.state["market_pressure"]["stocks"][str(stock.get("name", ""))] = float(max(-0.8, min(0.8, pressure)))
        self._append_stock_history_point(str(stock.get("name", "")), int(stock["current_price"]))
        if note:
            self._push_system_news(f"{ticker} 时间线异动", note, ["时间线", ticker, "股价"])
        return stock

    def _queue_story_event(self, event_id: str, title: str, description: str) -> None:
        event = {
            "id": str(event_id),
            "name": str(title),
            "description": str(description),
            "scope": "timeline",
            "day": int(self.state.get("day", 1)),
            "clock": self._clock_label(),
        }
        self.state["pending_events"] = [event]
        self._append_story_timeline_log(event_id, title, description)

    def _apply_route_selection(self, route_key: str) -> ActionResult:
        player = self._ensure_player_financial_state()
        route = str(route_key).strip().lower()
        if route not in {"elite", "commoner"}:
            return ActionResult("未识别的路线选择。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        player["stock_margin_debt"] = 0
        player["stock_liquidation_pending"] = False
        player["stock_liquidation_due_tick"] = 0
        player["stock_liquidation_note"] = ""
        player["stock_account_locked"] = False
        player["stock_account_lock_reason"] = ""
        player["stock_holdings"] = {str(name): 0 for name in dict(player.get("stock_holdings", {})).keys()}
        player["stock_short_positions"] = {
            str(name): {"quantity": 0, "avg_price": 0.0}
            for name in dict(player.get("stock_short_positions", {})).keys()
        }
        self.state["stock_trade_tape"] = []
        self.state["stock_exchange_feedback"] = ""
        self.state["story_timeline"] = {"fired": [], "log": []}
        metrics = self._story_metrics_state()
        metrics["sam_revolution_fund"] = 0
        metrics["sam_tax_total"] = 0
        metrics["player_trading_fees"] = 0
        ops = self._stock_ops_state()
        ops["story_sui_bonus"] = 0.0
        ops["story_st_floor"] = 1.0
        ops["policy_shield_until_tick"] = 0
        ops["scar_cover_until_tick"] = 0
        ops["rep_drag_until_tick"] = 0
        ops["victor_takeover_done"] = False
        ops["gala_invite_unlocked"] = False
        ops["last_action"] = ""
        if route == "elite":
            player["story_route"] = "精英路线"
            player["financial_route"] = "暗池交易终端"
            player["class_position"] = "前高管"
            player["cash"] = 500
            player["health"] = 100
            player["credit"] = 20
            player["goods_inventory"] = {"面包": 0, "煤": 0, "罐头": 0}
            player["reputation_tracks"] = {"FC": 5, "FB": 5, "SN": 5}
            player["shadow_reputation"] = {"S_WWI": 10, "S_DBH": 12, "S_NAC": 8, "SUI": 15, "ST": 1.0, "WL": 1}
            message = "你选择了精英路线。常规交易账户已封禁，PDA 上的暗池交易终端正在等待物理基站授权。接下来你得靠事件窗口和交易活下来。"
        else:
            player["story_route"] = "平民路线"
            player["financial_route"] = "底层互助网"
            player["class_position"] = "底层居民"
            player["cash"] = 5
            player["health"] = 100
            player["credit"] = 5
            player["goods_inventory"] = {"面包": 0, "煤": 0, "罐头": 0}
            player["reputation_tracks"] = {"FC": 10, "FB": 5, "SN": 20}
            player["shadow_reputation"] = {"S_WWI": 15, "S_DBH": 10, "S_NAC": 20, "SUI": 15, "ST": 1.0, "WL": 1}
            message = "你选择了平民路线。你在狭窄、漏风的底层公寓里醒来，手里只剩 5 铜币，接下来得靠街坊、工厂和码头的声望活下去。"
        metrics["reputation"] = copy.deepcopy(player["reputation_tracks"])
        metrics["shadow_reputation"] = copy.deepcopy(player["shadow_reputation"])
        player["route_intro_pending"] = False
        player["route_selected_at"] = self._now_label()
        self._queue_story_event(
            "route_choice",
            "路线选择",
            "你已经选定了接下来三天的活法。市场、声望和人物关系会沿这条线推进。",
        )
        self.state["stock_exchange_feedback"] = message
        self._push_system_news("路线选择", message, ["路线", player["story_route"]])
        return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=True))

    def _player_stock_holdings_value(self) -> int:
        player = self._ensure_player_financial_state()
        stock_rows = self.state.get("stocks", [])
        return sum(
            int(player.get("stock_holdings", {}).get(str(row.get("name", "")), 0)) * int(row.get("current_price", 0))
            for row in stock_rows
        )

    def _player_stock_short_exposure(self) -> int:
        player = self._ensure_player_financial_state()
        short_positions = dict(player.get("stock_short_positions", {}))
        stock_rows = self.state.get("stocks", [])
        return sum(
            int(dict(short_positions.get(str(row.get("name", "")), {})).get("quantity", 0)) * int(row.get("current_price", 0))
            for row in stock_rows
        )

    def _player_stock_margin_debt(self) -> int:
        player = self._ensure_player_financial_state()
        return max(0, int(player.get("stock_margin_debt", 0)))

    def _stock_tier_rank(self, label: str) -> int:
        return {"青铜级": 1, "白银级": 2, "黄金级": 3}.get(str(label), 1)

    def _stock_account_tier(self) -> dict[str, Any]:
        wealth = self._player_total_wealth()
        if wealth > 50_000:
            return {"label": "黄金级", "fee_rate": 0.12, "leverage": "1x-50x", "max_leverage": 50, "rank": 3}
        if wealth > 10_000:
            return {"label": "白银级", "fee_rate": 0.08, "leverage": "1x-30x", "max_leverage": 30, "rank": 2}
        return {"label": "青铜级", "fee_rate": 0.05, "leverage": "1x-10x", "max_leverage": 10, "rank": 1}

    def _player_stock_equity(self) -> int:
        player = self._ensure_player_financial_state()
        return int(player.get("cash", 0)) + self._player_stock_holdings_value() - self._player_stock_short_exposure() - self._player_stock_margin_debt()

    def _stock_maintenance_margin(self) -> int:
        player = self._ensure_player_financial_state()
        debt = self._player_stock_margin_debt()
        gross_exposure = self._player_stock_holdings_value() + self._player_stock_short_exposure()
        if debt <= 0 and gross_exposure <= 0:
            return 0
        shadow = dict(self._story_metrics_state().get("shadow_reputation", {}))
        ratio = 0.15
        if float(shadow.get("SUI", 15.0)) >= 80.0:
            ratio += 0.05
        elif float(shadow.get("SUI", 15.0)) >= 50.0:
            ratio += 0.02
        swc = self._stock_by_ticker("SWC") or {}
        if int(player.get("stock_holdings", {}).get(str(swc.get("name", "")), 0)) > 0 and float(shadow.get("SUI", 15.0)) >= 31.0:
            ratio += 0.03
        if self._player_stock_short_exposure() > 0:
            ratio += 0.05
        return int(round(max(500.0, gross_exposure * ratio)))

    def _player_stock_buying_power(self, leverage_override: int | None = None) -> int:
        equity = max(0, self._player_stock_equity())
        tier = self._stock_account_tier()
        max_allowed_leverage = int(tier.get("max_leverage", 10))
        leverage = max_allowed_leverage if leverage_override is None else max(1, min(int(leverage_override), max_allowed_leverage))
        max_exposure = max(500, equity) * leverage
        gross_exposure = self._player_stock_holdings_value() + self._player_stock_short_exposure()
        return max(0, int(max_exposure - gross_exposure))

    def _resolve_stock_reference(self, stock_ref: str) -> dict[str, Any] | None:
        stock = self._find_by_name(self.state.get("stocks", []), stock_ref)
        if stock:
            return stock
        return self._stock_by_ticker(stock_ref)

    def _stock_op_active(self, key: str) -> bool:
        return int(self._stock_ops_state().get(key, 0)) > self._world_tick()

    def _set_stock_op_window(self, key: str, ap_count: int) -> None:
        self._stock_ops_state()[key] = self._world_tick() + max(1, ap_count) * 16 + 1

    def _push_system_news(self, title: str, body: str, tags: list[str] | None = None, *, scope: str = "city") -> None:
        payload = {
            "title": title,
            "body": body,
            "line": body,
            "tags": list(tags or []),
            "scope": scope,
        }
        self.state.setdefault("global_news", []).insert(0, payload)
        self.state["global_news"] = list(self.state.get("global_news", []))[:8]

    def _find_npc_by_name(self, name: str) -> dict[str, Any] | None:
        needle = str(name).strip()
        if not needle:
            return None
        for npc in self.state.get("npcs", []):
            if str(npc.get("name", "")).strip() == needle:
                return npc
        return None

    def _shock_stock_price(self, ticker: str, pct: float, *, pressure_delta: float = 0.0, note: str = "") -> dict[str, Any] | None:
        stock = self._stock_by_ticker(ticker)
        if not stock:
            return None
        previous = int(stock.get("current_price", 0))
        next_price = max(3, int(round(previous * (1.0 + pct))))
        stock["current_price"] = next_price
        stock["reference_price"] = round(float(stock.get("reference_price", previous)) * 0.9 + next_price * 0.1, 3)
        if pressure_delta:
            name = str(stock.get("name", ""))
            current = float(self.state.get("market_pressure", {}).get("stocks", {}).get(name, 0.0))
            self.state["market_pressure"]["stocks"][name] = max(-0.8, min(0.8, current + pressure_delta))
        self._append_stock_history_point(str(stock.get("name", "")), next_price)
        if note:
            self._push_system_news(f"{ticker} 盘面异动", note, ["暗池", ticker, "操纵"])
        return stock

    def _append_stock_history_point(self, stock_name: str, price: int) -> None:
        history_map = self.state.setdefault("stock_price_history", {})
        series = list(history_map.get(stock_name, []))
        series.append(int(price))
        history_map[stock_name] = series[-24:]

    def _record_stock_fee(self, trade_value: int, *, player_paid: bool) -> int:
        if trade_value <= 0:
            return 0
        tier = self._stock_account_tier()
        metrics = self._story_metrics_state()
        shadow = dict(metrics.get("shadow_reputation", {}))
        fee_rate = float(tier.get("fee_rate", 0.05))
        sui = float(shadow.get("SUI", 15.0))
        if sui >= 86:
            fee_rate *= 1.45
        elif sui >= 61:
            fee_rate *= 1.2
        fee = max(1, int(round(trade_value * fee_rate)))
        metrics["sam_tax_total"] = int(metrics.get("sam_tax_total", 0)) + fee
        metrics["sam_revolution_fund"] = int(metrics.get("sam_revolution_fund", 0)) + fee
        if player_paid:
            metrics["player_trading_fees"] = int(metrics.get("player_trading_fees", 0)) + fee
        return fee

    def _major_holders_for_stock(self, stock_name: str, limit: int = 3) -> list[dict[str, Any]]:
        holders = list(self.state.get("stock_holder_registry", {}).get(stock_name, []))
        holders.sort(key=lambda row: int(row.get("shares", 0)), reverse=True)
        return [
            {
                "holder_name": str(row.get("holder_name", "")),
                "holder_kind": str(row.get("holder_kind", "")),
                "shares": int(row.get("shares", 0)),
            }
            for row in holders[:limit]
        ]

    def _derive_story_reputation(self) -> tuple[dict[str, int], dict[str, Any]]:
        player = self.state.get("player", {})
        demo_metrics = dict(self.state.get("demo_metrics", {}))
        if str(player.get("story_route", "")).strip() and not list(self._story_timeline_state().get("fired", [])):
            metrics_total = sum(
                int(demo_metrics.get(key, 0))
                for key in ["work_actions", "goods_trades", "intel_actions", "stock_trades", "days_ended"]
            )
            if metrics_total <= 0:
                return (
                    copy.deepcopy(dict(player.get("reputation_tracks", {"FC": 10, "FB": 5, "SN": 20}))),
                    copy.deepcopy(dict(player.get("shadow_reputation", {"S_WWI": 15, "S_DBH": 10, "S_NAC": 20, "SUI": 15, "ST": 1.0, "WL": 1}))),
                )
        player = self.state.get("player", {})
        profile = dict(player.get("collective_profile", {}))
        worker = float(profile.get("worker_standing", 0.0))
        public = float(profile.get("public_standing", 0.0))
        capital = float(profile.get("capital_standing", 0.0))
        government = float(profile.get("government_standing", 0.0))
        key_bonus = {"FC": 0.0, "FB": 0.0, "SN": 0.0}
        for npc in self.state.get("npcs", []):
            memory = dict(npc.get("player_memory", {}))
            trust = float(npc.get("player_trust", 0.0))
            relation = float(npc.get("player_relation", 0))
            bonus = max(0.0, trust * 0.04 + relation * 0.85 + int(memory.get("friendly_count", 0)) * 1.6)
            faction = str(npc.get("shadow_faction", ""))
            if faction == "FC":
                key_bonus["FC"] += bonus
            elif faction == "FB":
                key_bonus["FB"] += bonus
            elif faction == "SN":
                key_bonus["SN"] += bonus
        fc = int(max(0, min(100, round(10 + worker * 40 + public * 8 + key_bonus["FC"]))))
        fb = int(max(0, min(100, round(5 + worker * 12 + capital * -6 + key_bonus["FB"]))))
        sn = int(max(0, min(100, round(20 + public * 34 + government * 6 + key_bonus["SN"]))))
        swc = self._stock_by_ticker("SWC") or {}
        amb = self._stock_by_ticker("AMB") or {}
        tsl = self._stock_by_ticker("TSL") or {}
        swc_price = max(1, int(swc.get("current_price", swc.get("base_price", 150))))
        amb_price = max(1, int(amb.get("current_price", amb.get("base_price", 80))))
        tsl_price = max(1, int(tsl.get("current_price", tsl.get("base_price", 45))))
        worker_unrest = float(self.state.get("macro", {}).get("worker_unrest", 50))
        s_wwi = int(max(0, min(100, round(15 + fc * 0.62 + worker_unrest * 0.35 + max(0, (80 - swc_price)) * 0.22))))
        s_dbh = int(max(0, min(100, round(10 + fb * 0.74 + max(0, 60 - tsl_price) * 0.3 + int(self._story_metrics_state().get("sam_revolution_fund", 0)) / 220))))
        s_nac = int(max(0, min(100, round(20 + sn * 0.58 + max(0, (90 - amb_price)) * 0.16 + max(0, (swc_price - 140)) * 0.08))))
        sui = round(s_wwi * 0.5 + s_dbh * 0.3 + s_nac * 0.2, 1)
        st = round((swc_price / 150.0 * 0.6) + (80.0 / amb_price * 0.4), 2)
        ops = self._stock_ops_state()
        sui = round(min(100.0, sui + float(ops.get("story_sui_bonus", 0.0))), 1)
        st = round(max(st, float(ops.get("story_st_floor", 1.0))), 2)
        if self._stock_op_active("policy_shield_until_tick"):
            sui = round(15.0 + (sui - 15.0) * 0.5, 1)
        if self._stock_op_active("rep_drag_until_tick"):
            fc = max(0, fc - 6)
            fb = max(0, fb - 4)
            sn = max(0, sn - 5)
        revolution_fund = int(self._story_metrics_state().get("sam_revolution_fund", 0))
        wl = 4 if revolution_fund > 20_000 else 3 if revolution_fund > 8_000 else 2 if revolution_fund > 2_000 else 1
        shadow = {
            "S_WWI": s_wwi,
            "S_DBH": s_dbh,
            "S_NAC": s_nac,
            "SUI": sui,
            "ST": st,
            "WL": wl,
            "sam_revolution_fund": revolution_fund,
            "police_side": "精英猎犬" if amb_price > 100 else "消极待命" if amb_price < 40 else "摇摆观望",
            "market_risk": "临界点" if sui >= 86 else "动荡期" if sui >= 61 else "摩擦期" if sui >= 31 else "缄默期",
            "policy_shield_active": self._stock_op_active("policy_shield_until_tick"),
        }
        return {"FC": fc, "FB": fb, "SN": sn}, shadow

    def _build_stock_exchange_view(self) -> dict[str, Any]:
        player = self._ensure_player_financial_state()
        holdings = {str(name): int(value) for name, value in dict(player.get("stock_holdings", {})).items()}
        stocks_view: list[dict[str, Any]] = []
        holdings_value = 0
        market_total = 0
        metrics = self._story_metrics_state()
        reputation = copy.deepcopy(metrics.get("reputation", {}))
        shadow = copy.deepcopy(metrics.get("shadow_reputation", {}))
        account_tier = self._stock_account_tier()
        for stock in self.state.get("stocks", []):
            stock_name = str(stock.get("name", ""))
            held = holdings.get(stock_name, 0)
            short_row = dict(player.get("stock_short_positions", {}).get(stock_name, {}))
            short_qty = int(short_row.get("quantity", 0))
            short_avg_price = float(short_row.get("avg_price", 0.0))
            current_price = int(stock.get("current_price", 0))
            market_cap = int(stock.get("market_cap", int(stock.get("issued_shares", 0)) * current_price))
            holding_value = held * current_price
            holdings_value += holding_value
            market_total += market_cap
            stocks_view.append(
                {
                    "id": str(stock.get("id", "")),
                    "ticker": str(stock.get("ticker", "")),
                    "name": stock_name,
                    "display_name": self._stock_view_name(stock),
                    "industry": str(stock.get("industry", "")),
                    "family_owner": str(stock.get("family_owner", "")),
                    "current_price": current_price,
                    "previous_close": int(stock.get("previous_close", stock.get("base_price", 0))),
                    "reference_price": float(stock.get("reference_price", stock.get("base_price", 0))),
                    "issued_shares": int(stock.get("issued_shares", 0)),
                    "market_cap": market_cap,
                    "held": held,
                    "holding_value": holding_value,
                    "short_qty": short_qty,
                    "short_avg_price": round(short_avg_price, 3),
                    "short_exposure": short_qty * current_price,
                    "change_amount": int(stock.get("change_amount", 0)),
                    "change_pct": round(float(stock.get("change_pct", 0.0)), 4),
                    "trade_volume": int(stock.get("trade_volume", 0)),
                    "float_turnover": round(float(stock.get("float_turnover", 0.0)), 4),
                    "net_cash_flow": round(float(stock.get("net_cash_flow", 0.0)), 2),
                    "market_sentiment": str(stock.get("market_sentiment", "")),
                    "history": [int(value) for value in list(self.state.get("stock_price_history", {}).get(stock_name, []))[-24:]],
                    "major_holders": self._major_holders_for_stock(stock_name, limit=3),
                }
            )
        tape = [
            {
                "stock_name": str(row.get("stock_name", "")),
                "side": str(row.get("side", "")),
                "quantity": int(row.get("quantity", 0)),
                "unit_price": int(row.get("unit_price", 0)),
                "total_amount": int(row.get("total_amount", 0)),
                "clock": str(row.get("clock", "")),
                "anonymous_label": str(row.get("anonymous_label", "")),
            }
            for row in list(self.state.get("stock_trade_tape", []))[:8]
            if isinstance(row, dict)
        ]
        sui = float(shadow.get("SUI", 15.0))
        market_risk = str(shadow.get("market_risk", "缄默期"))
        margin_debt = self._player_stock_margin_debt()
        equity = self._player_stock_equity()
        maintenance_margin = self._stock_maintenance_margin()
        short_exposure = self._player_stock_short_exposure()
        liquidation_pending = bool(player.get("stock_liquidation_pending", False))
        account_locked = bool(player.get("stock_account_locked", False))
        ops = self._stock_ops_state()
        warnings: list[str] = []
        if sui >= 86:
            warnings.append("系统性风险极高：盘口可能出现临时熔断与黑天鹅抛压。")
        elif sui >= 61:
            warnings.append("动荡期：萨姆手续费上调，TSL 可能随机闪崩。")
        elif sui >= 31:
            warnings.append("摩擦期：SWC 保证金要求上升，盘口波动开始放大。")
        if float(shadow.get("ST", 1.0)) > 1.5:
            warnings.append("社会张力上升：底层生存压力正在反向压迫市场。")
        if margin_debt > 0:
            warnings.append(f"融资仓位已开启：当前负债 {margin_debt}，维持保证金 {maintenance_margin}。")
        if liquidation_pending:
            warnings.append(str(player.get("stock_liquidation_note", "萨姆已经把你的坐标卖出去了。")))
        elif account_locked:
            warnings.append(str(player.get("stock_account_lock_reason", "暗池账户已被冻结，需要 5000 现金重新入场。")))
        if self._stock_op_active("policy_shield_until_tick"):
            warnings.append("政策保护伞生效：未来几个 AP 内，SUI 的自然升温会被压低。")
        if self._stock_op_active("scar_cover_until_tick"):
            warnings.append("刀疤护盘中：这一个 AP 里的交易动作会更隐蔽。")
        if self._stock_op_active("rep_drag_until_tick"):
            warnings.append("虚假繁荣仍在覆盖舆论：街上的真实声望增长被压慢了。")
        if bool(ops.get("victor_takeover_done", False)):
            warnings.append("维克多质押盘已被打穿：海藻资本的安保调度正在失血。")
        return {
            "market_open": self._stock_market_is_open(),
            "session_label": self._stock_market_session_label(),
            "clock_label": self._clock_label(),
            "feedback": str(self.state.get("stock_exchange_feedback", "")),
            "player_health": int(player.get("health", 100)),
            "player_cash": int(player.get("cash", 0)),
            "player_holdings_value": holdings_value,
            "player_total_wealth": self._player_total_wealth(),
            "market_total_value": market_total,
            "account_tier": account_tier,
            "account_locked": account_locked,
            "account_lock_reason": str(player.get("stock_account_lock_reason", "")),
            "story_route": str(player.get("story_route", "")),
            "route_pending": bool(player.get("route_intro_pending", False)),
            "financial_route": str(player.get("financial_route", "")),
            "liquidation_pending": liquidation_pending,
            "liquidation_note": str(player.get("stock_liquidation_note", "")),
            "margin_debt": margin_debt,
            "maintenance_margin": maintenance_margin,
            "equity": equity,
            "short_exposure": short_exposure,
            "buying_power": self._player_stock_buying_power(),
            "sam_tax_total": int(metrics.get("sam_tax_total", 0)),
            "player_trading_fees": int(metrics.get("player_trading_fees", 0)),
            "revolution_fund": int(metrics.get("sam_revolution_fund", 0)),
            "reputation": reputation,
            "shadow_reputation": shadow,
            "market_risk": market_risk,
            "warnings": warnings,
            "stock_ops": copy.deepcopy(ops),
            "stocks": stocks_view,
            "tape": tape,
            "ending_state": copy.deepcopy(self.state.get("ending_state", {})),
        }

    def _maybe_restore_dark_pool_access(self) -> None:
        player = self._ensure_player_financial_state()
        if not bool(player.get("stock_account_locked", False)):
            return
        if bool(self.state.get("ending_state", {}).get("game_over", False)):
            return
        if int(player.get("cash", 0)) < 5_000:
            return
        player["stock_account_locked"] = False
        player["stock_account_lock_reason"] = ""
        player["stock_liquidation_note"] = ""
        self.state["stock_exchange_feedback"] = "萨姆重新给你开了暗池账户。你可以再次入场，但这次没人会替你擦屁股。"
        self._push_system_news(
            "暗池账户恢复",
            "你拿着 5000 现金重新敲开了萨姆的门。黑市账户恢复，但之前的信用已经清空。",
            ["暗池", "账户恢复", "萨姆"],
        )

    def _trigger_financial_ending(self, ending_id: str, title: str, body: str) -> None:
        current = dict(self.state.get("ending_state", {}))
        if current.get("id") == ending_id and current.get("game_over"):
            return
        self.state["ending_state"] = {
            "id": ending_id,
            "title": title,
            "body": body,
            "game_over": True,
            "clock": self._clock_label(),
            "day": int(self.state.get("day", 1)),
        }
        self.state["stock_exchange_feedback"] = body
        self._push_system_news(title, body, ["结局", "金融", ending_id])

    def _resolve_debt_liquidation(self, *, fatal: bool, reason: str) -> None:
        player = self._ensure_player_financial_state()
        player["health"] = max(0, int(player.get("health", 100)) - 50)
        player["cash"] = 0
        player["stock_margin_debt"] = 0
        player["stock_holdings"] = {str(name): 0 for name in dict(player.get("stock_holdings", {})).keys()}
        player["stock_short_positions"] = {
            str(name): {"quantity": 0, "avg_price": 0.0}
            for name in dict(player.get("stock_short_positions", {})).keys()
        }
        player["goods_inventory"] = {str(name): 0 for name in dict(player.get("goods_inventory", {})).keys()}
        player["stock_liquidation_pending"] = False
        player["stock_liquidation_due_tick"] = 0
        player["stock_account_locked"] = True
        player["stock_account_lock_reason"] = "暗池账户已冻结，需要至少 5000 现金才能重新入场。"
        player["stock_liquidation_note"] = "刀疤已经收完账。你被打掉半条命，账户和存货都被清空。"
        player["financial_route"] = "负债工贼"
        player["class_position"] = "负债工贼"
        note = "刀疤上门完成了物理清算：生命 -50，账户归零，所有存货被抄走。"
        self.state["stock_exchange_feedback"] = note
        self._push_system_news("刀疤上门", note, ["刀疤", "清算", reason])
        if fatal or int(player.get("health", 0)) <= 0:
            self._trigger_financial_ending(
                "debt_bodily_liquidation",
                "债务的肉体清算",
                "你在暗池穿仓后没能补上保证金。萨姆卖掉了你的坐标，刀疤上门完成了最后清算。",
            )

    def _force_dark_pool_auto_close(self, stock: dict[str, Any], reason: str) -> None:
        player = self._ensure_player_financial_state()
        stock_name = str(stock.get("name", ""))
        held = int(player.get("stock_holdings", {}).get(stock_name, 0))
        if held <= 0:
            return
        unit_price = int(stock.get("current_price", 0))
        trade_value = unit_price * held
        fee = self._record_stock_fee(trade_value, player_paid=True)
        realized_cash = max(0, trade_value - fee)
        paydown = min(self._player_stock_margin_debt(), realized_cash)
        player["stock_margin_debt"] = self._player_stock_margin_debt() - paydown
        player["cash"] = int(player.get("cash", 0)) + max(0, realized_cash - paydown)
        player["stock_holdings"][stock_name] = 0
        self._record_stock_trade(
            actor_kind="system",
            actor_id="dark_pool",
            actor_name="暗池风控",
            stock_name=stock_name,
            quantity=held,
            direction=-1,
            unit_price=unit_price,
            source=reason,
        )
        self.state["stock_exchange_feedback"] = f"暗池风控强平 {stock_name} x{held}，回笼 {realized_cash}，手续费 {fee}。"
        self._push_system_news(
            "暗池强平",
            f"由于 {reason}，暗池系统强行平掉了你在 {stock_name} 的仓位。",
            ["暗池", "强平", stock_name],
        )

    def _check_stock_account_state(self, *, trigger: str) -> None:
        player = self._ensure_player_financial_state()
        self._maybe_restore_dark_pool_access()
        ending = dict(self.state.get("ending_state", {}))
        if bool(ending.get("game_over", False)):
            return
        equity = self._player_stock_equity()
        maintenance_margin = self._stock_maintenance_margin()
        debt = self._player_stock_margin_debt()
        if equity < 0:
            self._resolve_debt_liquidation(fatal=True, reason="global_margin_call")
            return
        if bool(player.get("stock_liquidation_pending", False)):
            due_tick = int(player.get("stock_liquidation_due_tick", 0))
            if self._world_tick() >= due_tick and trigger != "trade_preview":
                self._resolve_debt_liquidation(fatal=False, reason="margin_call")
                return
        if debt > 0 and maintenance_margin > 0 and equity <= maintenance_margin and not bool(player.get("stock_liquidation_pending", False)):
            player["stock_liquidation_pending"] = True
            player["stock_liquidation_due_tick"] = self._world_tick() + 1
            player["stock_account_locked"] = True
            player["stock_account_lock_reason"] = "保证金不足，暗池交易权限已被冻结。"
            player["stock_liquidation_note"] = "PDA 震动：萨姆留言“有人来收账了，祝你好运。”"
            self.state["stock_exchange_feedback"] = str(player["stock_liquidation_note"])
            self._push_system_news(
                "暗池追保",
                "你的账户净值已经跌穿维持保证金。萨姆冻结了交易权限，并把坐标准备卖给刀疤。",
                ["保证金", "刀疤", "暗池"],
            )
        if int(self.state.get("day", 1)) >= 3 and int(self.state.get("clock_minutes", 0)) >= 20 * 60:
            shadow = dict(self._story_metrics_state().get("shadow_reputation", {}))
            if int(player.get("cash", 0)) < 5_000 and float(shadow.get("SUI", 15.0)) >= 70.0 and int(shadow.get("WL", 1)) >= 3:
                self._trigger_financial_ending(
                    "guikong_scapegoat",
                    "归空结局：被抛弃的替罪羊",
                    "第三天夜里，AMB 形同归零。你既没钱压低 SUI，也没本钱加固安保，最终被旧秩序当成替罪羊一起丢进废墟里。",
                )

    def _run_stock_special_operation(self, operation: str) -> ActionResult:
        player = self._ensure_player_financial_state()
        if bool(self.state.get("ending_state", {}).get("game_over", False)):
            ending = dict(self.state.get("ending_state", {}))
            return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if bool(player.get("stock_account_locked", False)):
            return ActionResult(str(player.get("stock_account_lock_reason", "暗池账户已冻结。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
        tier = self._stock_account_tier()
        tier_rank = int(tier.get("rank", 1))
        ops = self._stock_ops_state()
        message = "操作未执行。"
        success = False
        match operation:
            case "fake_boom_report":
                if tier_rank < 3:
                    message = "虚假繁荣报道需要黄金级账户。"
                elif int(player.get("cash", 0)) < 3_000:
                    message = "现金不足，无法买通报馆洗白 SWC。"
                else:
                    player["cash"] = int(player.get("cash", 0)) - 3_000
                    self._shock_stock_price("SWC", 0.10, pressure_delta=0.14, note="报馆头版开始为海藻资本粉饰太平，SWC 被强行拉抬。")
                    self.state["macro"]["media_sentiment"] = min(100, int(self.state["macro"].get("media_sentiment", 50)) + 8)
                    self.state["macro"]["worker_unrest"] = min(100, int(self.state["macro"].get("worker_unrest", 50)) + 4)
                    self._set_stock_op_window("rep_drag_until_tick", 3)
                    message = "你砸下 3000 铜币买通报馆，SWC 被强行拉升，街上的真实怨气也被一层假象压住了。"
                    success = True
            case "manufacture_dock_conflict":
                if tier_rank < 2:
                    message = "制造码头冲突至少需要白银级账户。"
                elif int(player.get("cash", 0)) < 5_000:
                    message = "现金不足，无法雇人把港口点起来。"
                else:
                    player["cash"] = int(player.get("cash", 0)) - 5_000
                    self._shock_stock_price("TSL", -0.25, pressure_delta=-0.22, note="港口冲突被人为点燃，TSL 盘口被狠狠砸穿。")
                    self._bump_district_signal("港口", "fear", 0.28)
                    self._bump_district_signal("港口", "gossip", 0.24)
                    self._bump_district_signal("港口", "labor_heat", 0.18)
                    message = "港口冲突被你做出来了，TSL 短线跳水，码头那边已经开始骂娘。"
                    success = True
            case "emergency_bond_issue":
                if tier_rank < 2:
                    message = "紧急增发债券至少需要白银级账户。"
                elif int(player.get("cash", 0)) < 8_000:
                    message = "现金不足，无法替镇政府托底 AMB。"
                else:
                    player["cash"] = int(player.get("cash", 0)) - 8_000
                    bond = self._shock_stock_price("AMB", 0.18, pressure_delta=0.18, note="镇政府紧急增发债券，AMB 被短暂托住。")
                    if bond and int(bond.get("current_price", 0)) < 70:
                        bond["current_price"] = 70
                    mayor = self._find_npc_by_name("温斯顿")
                    if mayor:
                        mayor["player_trust"] = min(100.0, float(mayor.get("player_trust", 0.0)) + 6.0)
                        mayor["player_relation"] = int(mayor.get("player_relation", 0)) + 4
                    ops["gala_invite_unlocked"] = True
                    message = "你用 8000 铜币替温斯顿托了 AMB 一口气，高级酒会的门缝也被撬开了一点。"
                    success = True
            case "hostile_takeover":
                swc = self._stock_by_ticker("SWC") or {}
                if tier_rank < 3:
                    message = "定向收购维克多的对手盘需要黄金级账户。"
                elif int(self._player_total_wealth()) < 100_000:
                    message = "你的总资产还不够，没资格去吞维克多的质押盘。"
                elif int(swc.get("current_price", 0)) >= 80:
                    message = "SWC 还没跌到 80 以下，维克多的质押仓现在还撬不动。"
                elif bool(ops.get("victor_takeover_done", False)):
                    message = "维克多的质押仓已经被你动过一次了。"
                else:
                    ops["victor_takeover_done"] = True
                    self.state["market_pressure"]["families"]["海藻资本"] = float(self.state["market_pressure"]["families"].get("海藻资本", 0.0)) - 0.25
                    self.state["macro"]["worker_unrest"] = max(0, int(self.state["macro"].get("worker_unrest", 50)) - 4)
                    victor = self._find_npc_by_name("维克多")
                    if victor:
                        victor["loyalty"] = max(0, int(victor.get("loyalty", 0)) - 18)
                        victor["fear"] = min(100, int(victor.get("fear", 0)) + 12)
                    message = "你强平了维克多的一部分质押盘。海藻资本的私保体系开始松动，第三夜的反扑会更弱。"
                    self._push_system_news("维克多仓位被打穿", message, ["维克多", "暗池", "敌意收购"])
                    success = True
            case "policy_shield":
                if tier_rank < 3:
                    message = "政策保护伞需要黄金级账户。"
                elif int(player.get("cash", 0)) < 20_000:
                    message = "现金不足，没法让温斯顿替你按住治安法案。"
                else:
                    player["cash"] = int(player.get("cash", 0)) - 20_000
                    self._set_stock_op_window("policy_shield_until_tick", 3)
                    mayor = self._find_npc_by_name("温斯顿")
                    if mayor:
                        mayor["player_trust"] = min(100.0, float(mayor.get("player_trust", 0.0)) + 10.0)
                        mayor["player_relation"] = int(mayor.get("player_relation", 0)) + 6
                    message = "温斯顿替你签了紧急治安法案。接下来 3 个 AP 内，SUI 的自然升温会被硬压一半。"
                    self._push_system_news("政策保护伞生效", message, ["温斯顿", "治安法案", "SUI"])
                    success = True
            case "hire_scar_cover":
                if int(player.get("cash", 0)) < 5_000:
                    message = "现金不足，刀疤不会白白替你站门。"
                else:
                    player["cash"] = int(player.get("cash", 0)) - 5_000
                    self._set_stock_op_window("scar_cover_until_tick", 1)
                    message = "刀疤接单了。接下来 1 个 AP 内，你在交易所的动作不会把街口的平民目光都引过来。"
                    self._push_system_news("刀疤护盘", message, ["刀疤", "暗池", "护盘"])
                    success = True
            case _:
                message = "未识别的金融操纵动作。"
        ops["last_action"] = operation if success else str(ops.get("last_action", ""))
        self.state["stock_exchange_feedback"] = message
        self._check_stock_account_state(trigger=operation)
        return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))

    def _reprice_stock_after_trade(self, stock: dict[str, Any], trade_cash: float, direction: int) -> None:
        previous = int(stock.get("current_price", 0))
        current_price = max(1.0, float(stock.get("current_price", 1)))
        free_float_value = max(1.0, float(stock.get("free_float", 1)) * current_price)
        flow_ratio = max(-0.16, min(0.16, (float(trade_cash) / max(free_float_value * 0.08, 1.0)) * float(direction)))
        existing_pressure = float(self.state.get("market_pressure", {}).get("stocks", {}).get(str(stock.get("name", "")), 0.0))
        reference_price = float(stock.get("reference_price", current_price))
        mispricing = (current_price - reference_price) / max(reference_price, 1.0)
        factor = 1.0 + flow_ratio * 0.42 + existing_pressure * 0.08 - mispricing * 0.06
        factor = max(0.9, min(1.12, factor))
        next_price = max(3, int(round(current_price * factor)))
        if next_price == previous and abs(float(trade_cash)) >= current_price * 10.0:
            next_price = max(3, previous + (1 if direction > 0 else -1))
        stock["current_price"] = next_price
        stock["last_trade_price"] = int(stock["current_price"])
        stock["change_amount"] = int(stock["current_price"]) - int(stock.get("previous_close", previous))
        base = max(float(stock.get("previous_close", previous)), 1.0)
        stock["change_pct"] = round((float(stock["current_price"]) - base) / base, 4)
        stock["reference_price"] = round(reference_price * 0.992 + float(stock["current_price"]) * 0.008, 3)
        stock["market_cap"] = int(int(stock.get("issued_shares", 0)) * int(stock["current_price"]))
        stock["market_sentiment"] = "乐观" if stock["current_price"] > previous else "恐慌" if stock["current_price"] < previous else "谨慎"
        stock["float_turnover"] = round(
            float(stock.get("trade_volume", 0)) / max(float(stock.get("free_float", 1)), 1.0),
            4,
        )
        self._append_stock_history_point(str(stock.get("name", "")), int(stock["current_price"]))

    def _record_stock_trade(
        self,
        *,
        actor_kind: str,
        actor_id: str,
        actor_name: str,
        stock_name: str,
        quantity: int,
        direction: int,
        unit_price: int,
        source: str,
    ) -> None:
        stock = self._find_by_name(self.state.get("stocks", []), stock_name)
        if not stock:
            return
        stock_name = str(stock.get("name", stock_name))
        quantity = max(1, int(quantity))
        total_amount = int(unit_price) * quantity
        side = "buy" if direction > 0 else "sell"
        label = f"{'买入' if direction > 0 else '卖出'} {stock_name} {quantity} 股 / {total_amount} 铜币"
        if source == "player_short_open":
            side = "short"
            label = f"做空 {stock_name} {quantity} 股 / {total_amount} 铜币"
        elif source == "player_short_cover":
            side = "cover"
            label = f"平空 {stock_name} {quantity} 股 / {total_amount} 铜币"
        stock["trade_volume"] = int(stock.get("trade_volume", 0)) + quantity
        stock["net_cash_flow"] = round(float(stock.get("net_cash_flow", 0.0)) + total_amount * (1 if direction > 0 else -1), 2)
        tape = list(self.state.get("stock_trade_tape", []))
        tape.insert(
            0,
            {
                "stock_name": stock_name,
                "side": side,
                "quantity": quantity,
                "unit_price": int(unit_price),
                "total_amount": total_amount,
                "actor_kind": actor_kind,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "source": source,
                "clock": self._clock_label(),
                "anonymous_label": label,
            },
        )
        self.state["stock_trade_tape"] = tape[:24]
        pressure = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0))
        cash_ratio = total_amount / max(float(stock.get("free_float", 1)) * max(float(stock.get("current_price", 1)), 1.0), 1.0)
        self.state["market_pressure"]["stocks"][stock_name] = max(-0.8, min(0.8, pressure + cash_ratio * (2.1 if direction > 0 else -2.1)))
        self._reprice_stock_after_trade(stock, total_amount, direction)
        self._rebuild_stock_holder_registry()

    def _npc_stock_trade_budget(self, npc: dict[str, Any], stock: dict[str, Any], direction: int) -> int:
        cash = int(npc.get("cash", 0))
        role = str(npc.get("role", ""))
        class_name = str(npc.get("class", ""))
        weight = 0.03
        if role in {"投机者", "银行经理"}:
            weight = 0.14
        elif role in {"代理人", "老板"} or class_name in {"特殊角色", "关键角色"}:
            weight = 0.09
        elif role in {"店主", "记者"}:
            weight = 0.05
        if direction < 0:
            weight = 1.0
        return max(int(stock.get("current_price", 1)), int(round(cash * weight)))

    def _coerce_trade_decision(self, raw: Any, npc: dict[str, Any]) -> dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        action = str(payload.get("action", payload.get("mode", "hold"))).strip().lower()
        if action not in {"buy", "sell", "hold"}:
            action = "hold"
        stock_name = str(payload.get("stock_name", payload.get("target", ""))).strip()
        if not stock_name:
            preferred = next((name for name, qty in dict(npc.get("stock_positions", {})).items() if int(qty) > 0), "")
            if not preferred:
                family = str(npc.get("family_affiliation", ""))
                preferred = next((str(row.get("name", "")) for row in self.state.get("stocks", []) if str(row.get("family_owner", "")) == family), "")
            stock_name = preferred
        quantity = max(0, int(payload.get("quantity", payload.get("shares", 0)) or 0))
        confidence = round(max(0.0, min(1.0, float(payload.get("confidence", 0.45)))), 3)
        note = str(payload.get("note", payload.get("reason", ""))).strip()
        return {"action": action, "stock_name": stock_name, "quantity": quantity, "confidence": confidence, "note": note}

    def _rule_npc_trade_decision(self, npc: dict[str, Any]) -> dict[str, Any]:
        role = str(npc.get("role", ""))
        if role not in {"投机者", "银行经理", "代理人", "记者", "店主", "老板"} and sum(int(value) for value in dict(npc.get("stock_positions", {})).values()) <= 0:
            return {"action": "hold", "stock_name": "", "quantity": 0, "confidence": 0.2, "note": ""}
        family = str(npc.get("family_affiliation", ""))
        preferred = next((str(row.get("name", "")) for row in self.state.get("stocks", []) if str(row.get("family_owner", "")) == family), "")
        holdings = {str(name): int(value) for name, value in dict(npc.get("stock_positions", {})).items()}
        owned_name = next((name for name, qty in holdings.items() if qty > 0), preferred)
        focus_name = preferred or owned_name or (self.state.get("stocks", [])[0].get("name", "") if self.state.get("stocks") else "")
        if not focus_name:
            return {"action": "hold", "stock_name": "", "quantity": 0, "confidence": 0.2, "note": ""}
        pressure = float(self.state["market_pressure"]["stocks"].get(focus_name, 0.0))
        sentiment = next((str(row.get("market_sentiment", "谨慎")) for row in self.state.get("stocks", []) if str(row.get("name", "")) == focus_name), "谨慎")
        if pressure <= -0.08 and holdings.get(focus_name, 0) > 0:
            return {"action": "sell", "stock_name": focus_name, "quantity": max(1, holdings.get(focus_name, 0) // 3), "confidence": 0.62, "note": "盘口发冷"}
        if pressure >= 0.06 or sentiment == "乐观":
            return {"action": "buy", "stock_name": focus_name, "quantity": 0, "confidence": 0.58, "note": "想跟一手"}
        return {"action": "hold", "stock_name": focus_name, "quantity": 0, "confidence": 0.32, "note": ""}

    def _apply_npc_trade_decision(self, npc: dict[str, Any], raw: Any, source: str = "rule") -> dict[str, Any] | None:
        if not self._stock_market_is_open():
            return None
        decision = self._coerce_trade_decision(raw, npc)
        if decision["action"] == "hold":
            decision = self._rule_npc_trade_decision(npc)
        action = str(decision.get("action", "hold"))
        stock_name = str(decision.get("stock_name", ""))
        stock = self._find_by_name(self.state.get("stocks", []), stock_name)
        if not stock or action == "hold":
            return None
        stock_name = str(stock.get("name", stock_name))
        holdings = {str(name): int(value) for name, value in dict(npc.get("stock_positions", {})).items()}
        unit_price = int(stock.get("current_price", 0))
        quantity = int(decision.get("quantity", 0))
        if action == "buy":
            budget = self._npc_stock_trade_budget(npc, stock, 1)
            affordable = max(0, min(int(npc.get("cash", 0)) // max(unit_price, 1), max(1, budget // max(unit_price, 1))))
            quantity = max(1, quantity or affordable)
            if affordable <= 0:
                return None
            quantity = min(quantity, affordable)
            total_amount = unit_price * quantity
            fee = self._record_stock_fee(total_amount, player_paid=False)
            total_cost = total_amount + fee
            if int(npc.get("cash", 0)) < total_cost:
                return None
            npc["cash"] = int(npc.get("cash", 0)) - total_cost
            holdings[stock_name] = holdings.get(stock_name, 0) + quantity
            self._record_stock_trade(actor_kind="npc", actor_id=str(npc.get("id", "")), actor_name=str(npc.get("name", "")), stock_name=stock_name, quantity=quantity, direction=1, unit_price=unit_price, source=source)
        else:
            available = holdings.get(stock_name, 0)
            if available <= 0:
                return None
            quantity = max(1, quantity or max(1, available // 3))
            quantity = min(quantity, available)
            total_amount = unit_price * quantity
            fee = self._record_stock_fee(total_amount, player_paid=False)
            npc["cash"] = int(npc.get("cash", 0)) + max(0, total_amount - fee)
            holdings[stock_name] = max(0, available - quantity)
            self._record_stock_trade(actor_kind="npc", actor_id=str(npc.get("id", "")), actor_name=str(npc.get("name", "")), stock_name=stock_name, quantity=quantity, direction=-1, unit_price=unit_price, source=source)
        npc["stock_positions"] = holdings
        npc["last_trade_pnl"] = round(float(npc.get("last_trade_pnl", 0.0)) + total_amount * (1 if action == "sell" else -1), 2)
        self._bump_district_signal("交易所", "trade_heat", 0.03 + quantity * 0.006)
        self._bump_district_signal("交易所", "liquidity", 0.02 + quantity * 0.005)
        return {"action": action, "stock_name": stock_name, "quantity": quantity, "amount": total_amount}

    def _run_npc_market_round(self, trigger: str) -> None:
        acted = 0
        for npc in self.state.get("npcs", []):
            role = str(npc.get("role", ""))
            if role not in {"投机者", "银行经理", "代理人", "记者", "店主", "老板"} and sum(int(value) for value in dict(npc.get("stock_positions", {})).values()) <= 0:
                continue
            spin = self.state.get("npc_spin_map", {}).get(str(npc.get("id", "")), {})
            if spin.get("trade_execution"):
                continue
            raw_decision = spin.get("trade_decision", {})
            decision = self._apply_npc_trade_decision(npc, raw_decision, source=trigger)
            if not decision:
                continue
            acted += 1
            if acted >= 6:
                break
        if acted > 0:
            self.state["demo_metrics"]["stock_trades"] = int(self.state.get("demo_metrics", {}).get("stock_trades", 0)) + acted

    def _trade_stock(self, stock_name: str, quantity: int, direction: int) -> ActionResult:
        player = self.state["player"]
        stock = self._find_by_name(self.state["stocks"], stock_name)
        if not stock:
            return ActionResult("没有这支股票。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        stock_name = str(stock.get("name", stock_name))
        quantity = max(quantity, 1)
        cost = stock["current_price"] * quantity
        if direction > 0:
            if player["cash"] < cost:
                return ActionResult("现金不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
            player["cash"] -= cost
            player["stock_holdings"][stock_name] = player["stock_holdings"].get(stock_name, 0) + quantity
            if stock_name == "珊瑚金控":
                self._increment_task_progress("swing_trade_media", stock_name, quantity)
            self.state["demo_metrics"]["stock_trades"] = int(self.state["demo_metrics"].get("stock_trades", 0)) + quantity
            self._record_stock_trade(
                actor_kind="player",
                actor_id="player",
                actor_name="玩家",
                stock_name=stock_name,
                quantity=quantity,
                direction=1,
                unit_price=int(stock.get("current_price", 0)),
                source="player_action",
            )
            self._bump_district_signal("交易所", "liquidity", 0.12 * quantity)
            self._bump_district_signal("交易所", "trade_heat", 0.08 * quantity)
            self._update_player_class()
            return ActionResult(f"买入 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if player["stock_holdings"].get(stock_name, 0) < quantity:
            return ActionResult("持仓不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        player["stock_holdings"][stock_name] -= quantity
        player["cash"] += cost
        self.state["demo_metrics"]["stock_trades"] = int(self.state["demo_metrics"].get("stock_trades", 0)) + quantity
        self._record_stock_trade(
            actor_kind="player",
            actor_id="player",
            actor_name="玩家",
            stock_name=stock_name,
            quantity=quantity,
            direction=-1,
            unit_price=int(stock.get("current_price", 0)),
            source="player_action",
        )
        self._bump_district_signal("交易所", "liquidity", 0.1 * quantity)
        self._bump_district_signal("交易所", "trade_heat", 0.06 * quantity)
        self._update_player_class()
        return ActionResult(f"卖出 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))

    def _trade_stock_v2(self, stock_name: str, quantity: int, direction: int) -> ActionResult:
        player = self._ensure_player_financial_state()
        stock = self._find_by_name(self.state["stocks"], stock_name)
        if not stock:
            self.state["stock_exchange_feedback"] = "没有这支股票。"
            return ActionResult("没有这支股票。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        stock_name = str(stock.get("name", stock_name))
        self._check_stock_account_state(trigger="trade_preview")
        if bool(self.state.get("ending_state", {}).get("game_over", False)):
            ending = dict(self.state.get("ending_state", {}))
            return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if bool(player.get("stock_account_locked", False)):
            message = str(player.get("stock_account_lock_reason", "暗池交易权限已被冻结。"))
            self.state["stock_exchange_feedback"] = message
            return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if not self._stock_market_is_open():
            message = f"交易所当前闭市，可交易时段为 {self._stock_market_session_label()}。"
            self.state["stock_exchange_feedback"] = message
            return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))
        quantity = max(quantity, 1)
        unit_price = int(stock.get("current_price", 0))
        trade_value = unit_price * quantity
        previous_tier_label = str(self._stock_account_tier().get("label", "青铜级"))
        stealth_cover = self._stock_op_active("scar_cover_until_tick")
        if direction > 0:
            fee = self._record_stock_fee(trade_value, player_paid=True)
            total_cost = trade_value + fee
            cash_available = int(player.get("cash", 0))
            shortfall = max(0, total_cost - cash_available)
            if shortfall > 0 and shortfall > self._player_stock_buying_power():
                self.state["stock_exchange_feedback"] = "现金和可用融资额度都不足，无法完成买入。"
                return ActionResult("现金不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
            if shortfall > 0:
                player["cash"] = 0
                player["stock_margin_debt"] = self._player_stock_margin_debt() + shortfall
            else:
                player["cash"] = cash_available - total_cost
            player["stock_holdings"][stock_name] = int(player["stock_holdings"].get(stock_name, 0)) + quantity
            if str(stock.get("ticker", "")).upper() == "AMB":
                self._increment_task_progress("swing_trade_media", str(stock.get("name", stock_name)), quantity)
            self.state["demo_metrics"]["stock_trades"] = int(self.state["demo_metrics"].get("stock_trades", 0)) + quantity
            self._record_stock_trade(
                actor_kind="player",
                actor_id="player",
                actor_name="玩家",
                stock_name=stock_name,
                quantity=quantity,
                direction=1,
                unit_price=unit_price,
                source="player_action",
            )
            if not stealth_cover:
                self._bump_district_signal("交易所", "liquidity", 0.12 * quantity)
                self._bump_district_signal("交易所", "trade_heat", 0.08 * quantity)
            self._check_stock_account_state(trigger="buy_stock")
            self._update_player_class()
            tier_label = str(self._stock_account_tier().get("label", "青铜级"))
            debt_now = self._player_stock_margin_debt()
            debt_line = f" 当前融资负债 {debt_now}。" if debt_now > 0 else ""
            downgrade_line = f" 账户已从 {previous_tier_label} 降到 {tier_label}。" if self._stock_tier_rank(tier_label) < self._stock_tier_rank(previous_tier_label) else ""
            stealth_line = " 刀疤把交易所门口的人群视线都挡开了。" if stealth_cover else ""
            self.state["stock_exchange_feedback"] = f"买入 {stock_name} x{quantity}，成交额 {trade_value} 铜币，萨姆抽成 {fee}。{debt_line}{downgrade_line}{stealth_line}".strip()
            return ActionResult(f"买入 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if int(player["stock_holdings"].get(stock_name, 0)) < quantity:
            self.state["stock_exchange_feedback"] = "持仓不足，无法完成卖出。"
            return ActionResult("持仓不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        fee = self._record_stock_fee(trade_value, player_paid=True)
        player["stock_holdings"][stock_name] = int(player["stock_holdings"].get(stock_name, 0)) - quantity
        realized_cash = max(0, trade_value - fee)
        margin_debt = self._player_stock_margin_debt()
        paydown = min(margin_debt, realized_cash)
        player["stock_margin_debt"] = margin_debt - paydown
        player["cash"] = int(player.get("cash", 0)) + max(0, realized_cash - paydown)
        self.state["demo_metrics"]["stock_trades"] = int(self.state["demo_metrics"].get("stock_trades", 0)) + quantity
        self._record_stock_trade(
            actor_kind="player",
            actor_id="player",
            actor_name="玩家",
            stock_name=stock_name,
            quantity=quantity,
            direction=-1,
            unit_price=unit_price,
            source="player_action",
        )
        if not stealth_cover:
            self._bump_district_signal("交易所", "liquidity", 0.1 * quantity)
            self._bump_district_signal("交易所", "trade_heat", 0.06 * quantity)
        self._check_stock_account_state(trigger="sell_stock")
        self._update_player_class()
        tier_label = str(self._stock_account_tier().get("label", "青铜级"))
        downgrade_line = f" 账户已从 {previous_tier_label} 降到 {tier_label}。" if self._stock_tier_rank(tier_label) < self._stock_tier_rank(previous_tier_label) else ""
        repay_line = f" 其中 {paydown} 已自动用于归还融资。" if paydown > 0 else ""
        stealth_line = " 刀疤把交易所门口的人群视线都挡开了。" if stealth_cover else ""
        self.state["stock_exchange_feedback"] = f"卖出 {stock_name} x{quantity}，回笼资金 {realized_cash} 铜币，萨姆抽成 {fee}。{repay_line}{downgrade_line}{stealth_line}".strip()
        return ActionResult(f"卖出 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))

    def _trade_stock_v2(self, stock_name: str, quantity: int, direction: int, leverage: int = 1) -> ActionResult:
        player = self._ensure_player_financial_state()
        stock = self._resolve_stock_reference(stock_name)
        if not stock:
            self.state["stock_exchange_feedback"] = "没有这支股票。"
            return ActionResult("没有这支股票。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        stock_name = str(stock.get("name", stock_name))
        self._check_stock_account_state(trigger="trade_preview")
        if bool(self.state.get("ending_state", {}).get("game_over", False)):
            ending = dict(self.state.get("ending_state", {}))
            return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if bool(player.get("stock_account_locked", False)):
            message = str(player.get("stock_account_lock_reason", "暗池交易权限已被冻结。"))
            self.state["stock_exchange_feedback"] = message
            return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if not self._stock_market_is_open():
            message = f"交易所当前休市，可交易时段为 {self._stock_market_session_label()}。"
            self.state["stock_exchange_feedback"] = message
            return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))
        quantity = max(quantity, 1)
        leverage = max(1, min(int(leverage), int(self._stock_account_tier().get("max_leverage", 10))))
        unit_price = int(stock.get("current_price", 0))
        trade_value = unit_price * quantity
        previous_tier_label = str(self._stock_account_tier().get("label", "青铜级"))
        stealth_cover = self._stock_op_active("scar_cover_until_tick")
        if direction > 0:
            fee = self._record_stock_fee(trade_value, player_paid=True)
            total_cost = trade_value + fee
            cash_available = int(player.get("cash", 0))
            shortfall = max(0, total_cost - cash_available)
            if trade_value > self._player_stock_buying_power(leverage):
                self.state["stock_exchange_feedback"] = "这笔买入超过了当前股数和杠杆允许的敞口。"
                return ActionResult("买入力度超过可用杠杆。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
            if shortfall > 0 and shortfall > self._player_stock_buying_power(leverage):
                self.state["stock_exchange_feedback"] = "现金和可用融资额度都不足，无法完成买入。"
                return ActionResult("现金不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
            if shortfall > 0:
                player["cash"] = 0
                player["stock_margin_debt"] = self._player_stock_margin_debt() + shortfall
            else:
                player["cash"] = cash_available - total_cost
            player["stock_holdings"][stock_name] = int(player["stock_holdings"].get(stock_name, 0)) + quantity
            if str(stock.get("ticker", "")).upper() == "AMB":
                self._increment_task_progress("swing_trade_media", str(stock.get("name", stock_name)), quantity)
            self.state["demo_metrics"]["stock_trades"] = int(self.state["demo_metrics"].get("stock_trades", 0)) + quantity
            self._record_stock_trade(
                actor_kind="player",
                actor_id="player",
                actor_name="玩家",
                stock_name=stock_name,
                quantity=quantity,
                direction=1,
                unit_price=unit_price,
                source="player_action",
            )
            if not stealth_cover:
                self._bump_district_signal("交易所", "liquidity", 0.12 * quantity)
                self._bump_district_signal("交易所", "trade_heat", 0.08 * quantity)
            self._check_stock_account_state(trigger="buy_stock")
            self._update_player_class()
            tier_label = str(self._stock_account_tier().get("label", "青铜级"))
            debt_now = self._player_stock_margin_debt()
            debt_line = f" 当前融资负债 {debt_now}。" if debt_now > 0 else ""
            downgrade_line = f" 账户已从 {previous_tier_label} 降到 {tier_label}。" if self._stock_tier_rank(tier_label) < self._stock_tier_rank(previous_tier_label) else ""
            stealth_line = " 刀疤把交易所门口的视线都挡开了。" if stealth_cover else ""
            self.state["stock_exchange_feedback"] = f"买入 {stock_name} x{quantity}，成交额 {trade_value} 铜币，杠杆 {leverage}x，萨姆抽成 {fee}。{debt_line}{downgrade_line}{stealth_line}".strip()
            return ActionResult(f"买入 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if int(player["stock_holdings"].get(stock_name, 0)) < quantity:
            self.state["stock_exchange_feedback"] = "持仓不足，无法完成卖出。"
            return ActionResult("持仓不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        fee = self._record_stock_fee(trade_value, player_paid=True)
        player["stock_holdings"][stock_name] = int(player["stock_holdings"].get(stock_name, 0)) - quantity
        realized_cash = max(0, trade_value - fee)
        margin_debt = self._player_stock_margin_debt()
        paydown = min(margin_debt, realized_cash)
        player["stock_margin_debt"] = margin_debt - paydown
        player["cash"] = int(player.get("cash", 0)) + max(0, realized_cash - paydown)
        self.state["demo_metrics"]["stock_trades"] = int(self.state["demo_metrics"].get("stock_trades", 0)) + quantity
        self._record_stock_trade(
            actor_kind="player",
            actor_id="player",
            actor_name="玩家",
            stock_name=stock_name,
            quantity=quantity,
            direction=-1,
            unit_price=unit_price,
            source="player_action",
        )
        if not stealth_cover:
            self._bump_district_signal("交易所", "liquidity", 0.1 * quantity)
            self._bump_district_signal("交易所", "trade_heat", 0.06 * quantity)
        self._check_stock_account_state(trigger="sell_stock")
        self._update_player_class()
        tier_label = str(self._stock_account_tier().get("label", "青铜级"))
        downgrade_line = f" 账户已从 {previous_tier_label} 降到 {tier_label}。" if self._stock_tier_rank(tier_label) < self._stock_tier_rank(previous_tier_label) else ""
        repay_line = f" 其中 {paydown} 已自动用于归还融资。" if paydown > 0 else ""
        stealth_line = " 刀疤把交易所门口的视线都挡开了。" if stealth_cover else ""
        self.state["stock_exchange_feedback"] = f"卖出 {stock_name} x{quantity}，回笼资金 {realized_cash} 铜币，萨姆抽成 {fee}。{repay_line}{downgrade_line}{stealth_line}".strip()
        return ActionResult(f"卖出 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))

    def _trade_stock_short_v2(self, stock_name: str, quantity: int, direction: int, leverage: int = 1) -> ActionResult:
        player = self._ensure_player_financial_state()
        stock = self._resolve_stock_reference(stock_name)
        if not stock:
            self.state["stock_exchange_feedback"] = "没有这支股票。"
            return ActionResult("没有这支股票。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        stock_name = str(stock.get("name", stock_name))
        self._check_stock_account_state(trigger="trade_preview")
        if bool(self.state.get("ending_state", {}).get("game_over", False)):
            ending = dict(self.state.get("ending_state", {}))
            return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if bool(player.get("stock_account_locked", False)):
            message = str(player.get("stock_account_lock_reason", "暗池交易权限已被冻结。"))
            self.state["stock_exchange_feedback"] = message
            return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if not self._stock_market_is_open():
            message = f"交易所当前休市，可交易时段为 {self._stock_market_session_label()}。"
            self.state["stock_exchange_feedback"] = message
            return ActionResult(message, self._snapshot_after_refresh(rebuild_agent_prompts=False))
        quantity = max(quantity, 1)
        leverage = max(1, min(int(leverage), int(self._stock_account_tier().get("max_leverage", 10))))
        unit_price = int(stock.get("current_price", 0))
        trade_value = unit_price * quantity
        stealth_cover = self._stock_op_active("scar_cover_until_tick")
        current_short = dict(player.get("stock_short_positions", {}).get(stock_name, {"quantity": 0, "avg_price": 0.0}))
        short_qty = int(current_short.get("quantity", 0))
        short_avg_price = float(current_short.get("avg_price", 0.0))
        if direction > 0:
            if trade_value > self._player_stock_buying_power(leverage):
                self.state["stock_exchange_feedback"] = "这笔做空超过了当前股数和杠杆允许的敞口。"
                return ActionResult("做空力度超过可用杠杆。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
            fee = self._record_stock_fee(trade_value, player_paid=True)
            proceeds = max(0, trade_value - fee)
            player["cash"] = int(player.get("cash", 0)) + proceeds
            combined_qty = short_qty + quantity
            combined_avg = ((short_avg_price * short_qty) + (unit_price * quantity)) / max(combined_qty, 1)
            player["stock_short_positions"][stock_name] = {"quantity": combined_qty, "avg_price": round(combined_avg, 3)}
            self._record_stock_trade(
                actor_kind="player",
                actor_id="player",
                actor_name="玩家",
                stock_name=stock_name,
                quantity=quantity,
                direction=-1,
                unit_price=unit_price,
                source="player_short_open",
            )
            if not stealth_cover:
                self._bump_district_signal("交易所", "liquidity", 0.11 * quantity)
                self._bump_district_signal("交易所", "trade_heat", 0.09 * quantity)
            self._check_stock_account_state(trigger="short_stock")
            stealth_line = " 刀疤把交易所门口的视线都挡开了。" if stealth_cover else ""
            self.state["stock_exchange_feedback"] = f"做空 {stock_name} x{quantity}，名义金额 {trade_value} 铜币，杠杆 {leverage}x，萨姆抽成 {fee}。{stealth_line}".strip()
            return ActionResult(f"做空 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        if short_qty < quantity:
            self.state["stock_exchange_feedback"] = "空仓不足，无法平空。"
            return ActionResult("空仓不足。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
        fee = self._record_stock_fee(trade_value, player_paid=True)
        total_cost = trade_value + fee
        cash_available = int(player.get("cash", 0))
        shortfall = max(0, total_cost - cash_available)
        if shortfall > 0:
            player["cash"] = 0
            player["stock_margin_debt"] = self._player_stock_margin_debt() + shortfall
        else:
            player["cash"] = cash_available - total_cost
        remaining_qty = short_qty - quantity
        if remaining_qty > 0:
            player["stock_short_positions"][stock_name] = {"quantity": remaining_qty, "avg_price": short_avg_price}
        else:
            player["stock_short_positions"][stock_name] = {"quantity": 0, "avg_price": 0.0}
        pnl = int(round((short_avg_price - unit_price) * quantity))
        self._record_stock_trade(
            actor_kind="player",
            actor_id="player",
            actor_name="玩家",
            stock_name=stock_name,
            quantity=quantity,
            direction=1,
            unit_price=unit_price,
            source="player_short_cover",
        )
        if not stealth_cover:
            self._bump_district_signal("交易所", "liquidity", 0.09 * quantity)
            self._bump_district_signal("交易所", "trade_heat", 0.05 * quantity)
        self._check_stock_account_state(trigger="cover_short")
        debt_now = self._player_stock_margin_debt()
        debt_line = f" 当前融资负债 {debt_now}。" if debt_now > 0 else ""
        stealth_line = " 刀疤把交易所门口的视线都挡开了。" if stealth_cover else ""
        self.state["stock_exchange_feedback"] = f"平空 {stock_name} x{quantity}，成交额 {trade_value} 铜币，盈亏 {pnl}，萨姆抽成 {fee}。{debt_line}{stealth_line}".strip()
        return ActionResult(f"平空 {stock_name} x{quantity}。", self._snapshot_after_refresh(rebuild_agent_prompts=False))

    def _accept_task(self, task_id: str) -> ActionResult:
        player = self.state["player"]
        task = self._find_by_id(self.state["task_board"], task_id)
        if not task:
            return ActionResult("没有这张告示。", self.snapshot())
        player["active_task_id"] = task_id
        player["task_progress"].setdefault(task_id, 0)
        return ActionResult(f"你接下了任务：{task['title']}。", self.snapshot())

    def _claim_task(self, task_id: str) -> ActionResult:
        player = self.state["player"]
        task = self._find_by_id(self.state["task_board"], task_id)
        if not task:
            return ActionResult("没有这张告示。", self.snapshot())
        progress = int(player["task_progress"].get(task_id, 0))
        need = int(task["requirement"]["quantity"])
        if progress < need:
            return ActionResult("任务还没做够。", self.snapshot())
        reward = task["reward"]
        player["cash"] += int(reward.get("cash", 0))
        player["reputation"] = min(100, player["reputation"] + int(reward.get("reputation", 0)))
        family_name = str(reward.get("family_name", ""))
        if family_name:
            player["family_relations"][family_name] = int(player["family_relations"].get(family_name, 0)) + int(reward.get("family_relation", 0))
        player["completed_tasks"].append(task_id)
        player["active_task_id"] = ""
        self.state["task_board"] = [row for row in self.state["task_board"] if row["id"] != task_id]
        self.state["global_news"].insert(
            0,
            {
                "title": "一张告示换来了一点台阶",
                "body": f"你完成了“{task['title']}”，{family_name if family_name else '街头'} 对你的看法更不一样了。",
                "tags": ["任务", family_name if family_name else "街头"],
                "scope": "district",
            },
        )
        self.state["global_news"] = self.state["global_news"][:8]
        self._refresh_derived_views()
        return ActionResult(f"任务完成：{task['title']}。", self.snapshot())

    def _apply_macro_shift(self, event: dict[str, Any]) -> None:
        macro = self.state["macro"]
        macro["interest_rate"] = max(0.8, round(macro["interest_rate"] + self.random.uniform(-0.2, 0.3), 2))
        macro["economy_heat"] = int(max(15, min(100, macro["economy_heat"] + event["macro_effect"]["economy_heat"])))
        macro["housing_heat"] = int(max(10, min(100, macro["housing_heat"] + event["macro_effect"]["housing_heat"])))
        macro["media_sentiment"] = int(max(0, min(100, macro["media_sentiment"] + event["macro_effect"]["media_sentiment"])))
        macro["worker_unrest"] = int(max(0, min(100, macro["worker_unrest"] + event["macro_effect"]["worker_unrest"])))

    def _apply_goods_shift(self, event: dict[str, Any]) -> None:
        for good in self.state["goods"]:
            drift = self.random.uniform(-good["volatility"], good["volatility"])
            shock = event["goods_effect"].get(good["name"], 0.0)
            macro_bonus = (self.state["macro"]["worker_unrest"] - 40) * 0.01
            rumor_pressure = float(self.state["market_pressure"]["goods"].get(good["name"], 0.0))
            factor = 1.0 + drift + shock + macro_bonus + rumor_pressure * 0.8 + self._good_chain_bonus(good)
            new_price = max(1, int(round(good["current_price"] * factor)))
            good["price_trend"] = "涨" if new_price > good["current_price"] else "跌" if new_price < good["current_price"] else "平"
            good["current_price"] = new_price
            self.state["market_pressure"]["goods"][good["name"]] = rumor_pressure * 0.4

    def _apply_stock_shift(self, event: dict[str, Any]) -> None:
        for stock in self.state["stocks"]:
            drift = self.random.uniform(-stock["volatility"], stock["volatility"])
            shock = event["stock_effect"].get(stock["name"], 0.0)
            macro_bonus = self._stock_macro_bonus(stock)
            family_bonus = self._stock_family_bonus(stock)
            company_bonus = self._stock_company_bonus(stock)
            rumor_pressure = float(self.state["market_pressure"]["stocks"].get(stock["name"], 0.0))
            reference_price = float(stock.get("reference_price", stock["current_price"]))
            stock["reference_price"] = reference_price
            mispricing = (float(stock["current_price"]) - reference_price) / max(reference_price, 1.0)
            reversion = -mispricing * 0.18
            interest_drag = -max(0.0, float(self.state.get("macro", {}).get("interest_rate", 4.0)) - 4.2) * 0.008
            profit_taking = -max(0.0, mispricing - 0.22) * 0.28
            factor = 1.0 + drift + shock + macro_bonus + family_bonus + company_bonus + rumor_pressure * 0.52 + reversion + interest_drag + profit_taking
            factor = max(0.86, min(1.16, factor))
            previous_price = int(stock["current_price"])
            stock["current_price"] = max(3, int(round(stock["current_price"] * factor)))
            stock["reference_price"] = round(reference_price * 0.985 + float(stock["current_price"]) * 0.015, 3)
            stock["market_sentiment"] = "乐观" if factor > 1.02 else "恐慌" if factor < 0.98 else "谨慎"
            if stock["current_price"] == previous_price:
                stock["market_sentiment"] = "谨慎"
            self.state["market_pressure"]["stocks"][stock["name"]] = rumor_pressure * 0.38

    def _apply_family_shift(self, event: dict[str, Any]) -> None:
        relations = self.state["player"].get("family_relations", {})
        for family in self.state["families"]:
            controlled = [company for company in self.state.get("companies", []) if company.get("family_owner") == family["name"]]
            family["cash"] = int(max(60, family["cash"] + self.random.randint(-25, 40)))
            family["reputation"] = int(max(10, min(100, family["reputation"] + self.random.randint(-4, 4))))
            family["strategy"] = self.random.choice(event["family_effect"].get(family["name"], [family["strategy"]]))
            focus_stock, focus_good = self._family_focus_targets(family)
            relation = int(relations.get(family["name"], 0))
            family_pressure = self.random.uniform(-0.05, 0.09) + relation * 0.0015 + self._family_company_pressure(controlled)
            if focus_stock:
                self.state["market_pressure"]["stocks"][focus_stock] = float(self.state["market_pressure"]["stocks"].get(focus_stock, 0.0)) + family_pressure
            if focus_good:
                self.state["market_pressure"]["goods"][focus_good] = float(self.state["market_pressure"]["goods"].get(focus_good, 0.0)) + family_pressure * 0.7
            family["sector_focus"] = focus_stock or focus_good or family.get("sector_focus", family["type"])
            family["risk_appetite"] = round(max(0.05, min(0.95, float(family.get("risk_appetite", 0.5)) + family_pressure * 0.5)), 3)
            family["public_action"] = self.random.choice(
                [
                    f"盯住 {focus_stock or focus_good}",
                    "低调观望",
                    "收紧账本",
                    "拉拢街头代理人",
                    "暗中吃货",
                ]
            )
            family["hidden_action"] = self.random.choice(
                [
                    f"沿着 {focus_good or focus_stock} 放风",
                    "买通小报",
                    "压住银行口风",
                    "试探性砸盘",
                    "让代理人去试温度",
                ]
            )
            family["market_move"] = f"{'推高' if family_pressure >= 0 else '压低'} {focus_stock or focus_good}"
            if controlled:
                family["public_action"] = self._family_public_move(family, controlled, focus_stock or focus_good)
                family["hidden_action"] = self._family_hidden_move(family, controlled, focus_stock or focus_good)
            if relation >= 10:
                family["player_attitude"] = "开始把你当成能办事的人"
            elif relation <= -8:
                family["player_attitude"] = "对你留了一手"

    def _apply_district_shift(self, event: dict[str, Any]) -> None:
        for district in self.state["districts"]:
            district["state"] = event["district_effect"].get(district["name"], district["state"])

    def _append_news_for_event(self, event: dict[str, Any]) -> None:
        payload = {
            "event_name": event["name"],
            "district": event["district"],
            "macro": self.state["macro"],
            "stocks": [{s["name"]: s["current_price"]} for s in self.state["stocks"]],
            "scene_observation": self.state.get("scene_observation", {}),
        }
        generated = self.ark.generate_news_copy(payload)
        if not generated:
            generated = {
                "title": event["news_template"]["title"],
                "body": event["news_template"]["body"].format(district=event["district"]),
                "tags": event["news_template"]["tags"],
            }
        generated["scope"] = "city"
        self.state["global_news"].insert(0, generated)
        self.state["global_news"] = self.state["global_news"][:8]

    def _generate_ai_pulse(self, trigger: str, allow_live_llm_override: bool | None = None) -> None:
        self.state["local_broadcasts"] = []
        allow_boot_spread = trigger != "boot"
        for npc in self.state["npcs"]:
            self._update_npc_state(npc, trigger)
            self._generate_npc_speech(npc)
            if allow_boot_spread:
                self._apply_local_hearing(npc)
                self._check_local_escalation(npc)
        use_live_llm = self._allow_live_pulse_llm(trigger) if allow_live_llm_override is None else bool(allow_live_llm_override)
        if use_live_llm:
            self._apply_llm_pulse_brief(trigger)
            self._apply_scene_director_note(trigger)
        else:
            self._apply_fallback_pulse_brief()
            self.state["scene_director_note"] = self._fallback_scene_focus()
        self._run_npc_market_round(trigger)
        self._refresh_ambient_speeches()
        self._refresh_derived_views()
        self.state["last_pulse_at"] = self._now_label()

    def _update_npc_state(self, npc: dict[str, Any], trigger: str) -> None:
        district_state = self._district_state(npc["district"])
        npc["hunger"] = min(100, max(0, npc["hunger"] + self.random.randint(0, 5)))
        npc["fatigue"] = min(100, max(0, npc["fatigue"] + self.random.randint(0, 4)))
        npc["fear"] = min(100, max(0, npc["fear"] + self.random.randint(-2, 5)))
        npc["greed"] = min(100, max(0, npc["greed"] + self.random.randint(-1, 4)))
        if district_state in {"unrest", "tense"}:
            npc["fear"] = min(100, npc["fear"] + 6)
        if trigger == "end_day":
            npc["fatigue"] = max(10, npc["fatigue"] - self.random.randint(4, 10))

        if npc["fear"] >= 70:
            npc["mood"] = "anxious"
            npc["stance"] = "谨慎"
            npc["current_goal"] = "守住口粮"
            npc["action_tendency"] = "散播坏消息"
            npc["broadcast_intent"] = "fear"
        elif npc["greed"] >= 68:
            npc["mood"] = "excited"
            npc["stance"] = "激进"
            npc["current_goal"] = "抢先套利"
            npc["action_tendency"] = "追逐风口"
            npc["broadcast_intent"] = "greed"
        elif npc["loyalty"] >= 70:
            npc["mood"] = "defiant"
            npc["stance"] = "抱团"
            npc["current_goal"] = "替靠山试探街头"
            npc["action_tendency"] = "替人放话"
            npc["broadcast_intent"] = "faction"
        else:
            npc["mood"] = self.random.choice(["wary", "hopeful", "tired"])
            npc["stance"] = self.random.choice(["观望", "现实", "冷笑"])
            npc["current_goal"] = self.random.choice(["先填饱肚子", "盯住消息", "保住工作", "找条上升的缝", "别被人当垫脚石"])
            npc["action_tendency"] = self.random.choice(["低声抱怨", "左右张望", "讨价还价", "装作无事"])
            npc["broadcast_intent"] = "low"
        collective_override = self._collective_schedule_override(npc, int(self.state.get("clock_minutes", 8 * 60)))
        if collective_override:
            collective_role = str(collective_override.get("role", ""))
            npc["current_goal"] = str(collective_override.get("goal", npc.get("current_goal", "")))
            if collective_role == "organizer":
                npc["mood"] = "defiant"
                npc["stance"] = "抱团"
                npc["action_tendency"] = "四处串联"
                npc["broadcast_intent"] = "faction"
            elif collective_role in {"attendee", "committed", "supporter"}:
                npc["mood"] = "defiant" if float(npc.get("fear", 0)) < 74 else "anxious"
                npc["stance"] = "抱团"
                npc["action_tendency"] = "朝人堆里靠"
                npc["broadcast_intent"] = "faction"
            elif collective_role == "negotiator":
                npc["mood"] = "wary"
                npc["stance"] = "现实"
                npc["action_tendency"] = "试探让步"
                npc["broadcast_intent"] = "low"
            elif collective_role == "suppressor":
                npc["mood"] = "defiant"
                npc["stance"] = "谨慎"
                npc["action_tendency"] = "压住场面"
                npc["broadcast_intent"] = "faction"
            elif collective_role == "observer":
                npc["mood"] = "wary"
                npc["stance"] = "观望"
                npc["action_tendency"] = "围着看风向"
                npc["broadcast_intent"] = "low"
        npc["emotion_delta"] = {"fear": self.random.randint(-1, 4), "greed": self.random.randint(-1, 3)}

    def _generate_npc_speech(self, npc: dict[str, Any]) -> None:
        mood_templates = self.dialogue_templates["moods"].get(npc["mood"], self.dialogue_templates["moods"]["wary"])
        role_templates = self.dialogue_templates["roles"].get(npc["role"], self.dialogue_templates["roles"]["工人"])
        district_templates = self.dialogue_templates["districts"].get(npc["district"], [])
        pool = mood_templates + role_templates + district_templates
        scene_observation = self.state.get("scene_observation", {})
        scene_context = scene_observation.get("scene_context", {})
        player_memory = self._npc_player_memory(npc)
        memory_summary = self._npc_memory_summary(npc)
        if scene_context.get("current_district") == npc["district"]:
            pool.extend(
                [
                    "{name}瞥了一眼那名外来人，像在盘算 {goal}。",
                    "{name}压低声音：外来人又在这儿晃，今天的风怕是要改。",
                    "{name}朝街口努嘴：有人在附近盯盘，别把话说太满。",
                ]
            )
        if int(player_memory.get("talk_count", 0)) > 0:
            pool.extend(
                [
                    "{name}心里还记着你上次问的事，嘴上却不肯全认。",
                    "{name}把你当成会回头的人，先掂量你这次是不是又来买消息。",
                ]
            )
        if float(player_memory.get("pressure_from_player", 0.0)) >= 1.2:
            pool.extend(
                [
                    "{name}看见你就先收住半句，像怕你又把话往死里逼。",
                    "{name}肩膀先紧了一下，像还记得你上回的压法。",
                ]
            )
        self.random.shuffle(pool)
        lines = []
        for raw in pool:
            line = raw.format(
                name=npc["name"],
                family=npc["family_affiliation"],
                district=npc["district"],
                goal=npc["current_goal"],
            )
            if line not in lines:
                lines.append(line)
            if len(lines) >= self.random.randint(2, 5):
                break
        if memory_summary:
            lines = [lines[0], f"{npc['name']}心里算盘没放下：{memory_summary}"] if lines else [f"{npc['name']}心里算盘没放下：{memory_summary}"]
        npc["speech_lines"] = lines
        npc["cadence_seconds"] = self.random.choice([3.0, 4.0, 5.0])

    def _apply_local_hearing(self, speaker: dict[str, Any]) -> None:
        if not speaker["speech_lines"]:
            return
        focus_topic = self._resolve_focus_topic(speaker)
        speaker_band = str(speaker.get("social_band", self._npc_social_band(speaker)))
        self.state["local_broadcasts"].append(
            {
                "source": speaker["id"],
                "district": speaker["district"],
                "radius": speaker["social_radius"],
                "line": speaker["speech_lines"][0],
                "type": speaker["broadcast_intent"],
            }
        )
        for listener in self.state["npcs"]:
            if listener["id"] == speaker["id"]:
                continue
            if listener["district"] != speaker["district"]:
                continue
            same_subregion = str(listener.get("subregion_id", "")) == str(speaker.get("subregion_id", ""))
            if not same_subregion and speaker_band not in {"media", "authority"} and not str(listener.get("collective_action_id", "")):
                continue
            if self._distance(speaker, listener) > speaker["social_radius"]:
                continue
            listener["fear"] = min(100, listener["fear"] + max(0, speaker["emotion_delta"]["fear"]))
            listener["greed"] = min(100, listener["greed"] + max(0, speaker["emotion_delta"]["greed"]))
            listener["memory_tags"] = self._push_memory(listener["memory_tags"], f"heard:{speaker['id']}")
            if focus_topic:
                watch_link = str(listener.get("name", "")) in self._npc_contact_names(speaker, "watch_people")
                trusted_link = str(listener.get("name", "")) in self._npc_contact_names(speaker, "trusted_people")
                chance = 0.18
                if same_subregion:
                    chance += 0.28
                if trusted_link:
                    chance += 0.22
                elif watch_link:
                    chance += 0.12
                chance += float(listener.get("rumor_susceptibility", 0.2)) * 0.24
                if speaker_band in {"media", "organizer"}:
                    chance += 0.08
                if self.random.random() < min(0.92, chance):
                    self._register_topic_heard(
                        listener,
                        focus_topic,
                        speaker,
                        channel="overheard",
                        salience=min(0.82, 0.28 + chance * 0.42),
                        line=f"你在{speaker.get('district', '街口')}听见{speaker.get('name', '有人')}压着嗓子提到“{focus_topic.get('label', '街面风声')}”。",
                    )
            if speaker["broadcast_intent"] in {"fear", "greed", "faction"} and self.random.random() < listener["rumor_susceptibility"]:
                rumor_line = f"有人在{speaker['district']}低声说：{speaker['speech_lines'][0][:18]}"
                listener["speech_lines"] = [rumor_line, *listener["speech_lines"][:2]]
        self.state["local_broadcasts"] = self.state["local_broadcasts"][:18]

    def _check_local_escalation(self, npc: dict[str, Any]) -> None:
        if npc["fear"] >= 82:
            packet = self._build_intel_packet(npc["district"], source=f"{npc['name']}散的恐慌", speaker=npc)
            packet["line"] = f"{npc['name']} 把坏消息说得像真的：{packet['line']}"
            packet["scope"] = "district"
            self._apply_intel_packet(packet, to_player=False, promote_news=True, intensity=1.15)
            event = {
                "title": f"{npc['district']} 挤兑风声",
                "body": f"{npc['district']} 有人开始囤货，{npc['name']} 把坏消息说得像真相。",
                "tags": ["恐慌", npc["district"]],
                "scope": "district",
            }
            self.state["global_news"].insert(0, event)
            self.state["global_news"] = self.state["global_news"][:8]
            npc["fear"] = 68
        elif npc["greed"] >= 84:
            packet = self._build_intel_packet(npc["district"], source=f"{npc['name']}散的口信", speaker=npc)
            packet["line"] = f"{npc['name']} 一路兜售发财口信：{packet['line']}"
            packet["scope"] = "district"
            self._apply_intel_packet(packet, to_player=False, promote_news=True, intensity=1.0)
            event = {
                "title": f"{npc['district']} 抢购声起",
                "body": f"{npc['name']} 一路兜售发财口信，附近摊位价格开始往上蹿。",
                "tags": ["投机", npc["district"]],
                "scope": "district",
            }
            self.state["global_news"].insert(0, event)
            self.state["global_news"] = self.state["global_news"][:8]
            npc["greed"] = 71

    def _record_scene_observation(self, scene_observation: dict[str, Any]) -> None:
        self.state["scene_observation"] = {
            "current_district": str(scene_observation.get("current_district", "")),
            "player_position": dict(scene_observation.get("player_position", {})),
            "scene_context": copy.deepcopy(scene_observation.get("scene_context", {})),
            "screenshot_b64": str(scene_observation.get("screenshot_b64", "")),
        }
        self.state["last_scene_capture_at"] = self._now_label()

    def _llm_scene_observation(self, observation: dict[str, Any], *, include_image: bool) -> dict[str, Any]:
        llm_observation = copy.deepcopy(observation if isinstance(observation, dict) else {})
        if not include_image:
            llm_observation["screenshot_b64"] = ""
        return llm_observation

    @staticmethod
    def _is_background_scene_pulse(trigger: str) -> bool:
        return str(trigger or "") in {"scheduled", "scheduled_scene", "manual_scene"}

    def _allow_live_pulse_llm(self, trigger: str) -> bool:
        if self._is_background_scene_pulse(trigger) and not self._full_scheduled_llm_mode():
            return False
        if self._full_scheduled_llm_mode():
            return True
        return self.ark.enabled

    def _full_scheduled_llm_mode(self) -> bool:
        return "unittest" in sys.modules or os.getenv("SHELL_MARKET_FULL_SCHEDULED_LLM", "0") == "1"

    def _use_lightweight_scheduled_llm(self) -> bool:
        return not self._full_scheduled_llm_mode()

    def _apply_llm_pulse_brief(self, trigger: str) -> None:
        observation = copy.deepcopy(self.state.get("scene_observation", {}))
        payload = self._build_llm_pulse_payload(trigger, observation)
        generated = self.ark.generate_pulse_brief(payload)
        if not generated:
            self._apply_fallback_pulse_brief()
            return

        self.state["llm_pulse_summary"] = self._prefer_chinese_text(
            str(generated.get("pulse_summary", "")).strip(),
            self._fallback_pulse_summary(),
        )
        self.state["llm_market_note"] = self._prefer_chinese_text(
            str(generated.get("market_note", "")).strip(),
            self._fallback_market_note(),
        )
        self.state["llm_scene_focus"] = self._prefer_chinese_text(
            str(generated.get("scene_focus", "")).strip(),
            self._fallback_scene_focus(),
        )
        seen_npcs = self._apply_llm_npc_updates(generated.get("npc_updates", []))
        seen_families = self._apply_llm_family_updates(generated.get("family_updates", []))
        seen_companies = self._apply_llm_company_updates(generated.get("company_updates", []))
        self._refresh_all_npc_briefs(observation, seen_npcs)
        self._refresh_all_family_briefs(observation, seen_families)
        self._refresh_all_company_briefs(observation, seen_companies)
        self._apply_llm_attention_pressure()
        self._append_pulse_journal(trigger)

    def _build_llm_pulse_payload(self, trigger: str, observation: dict[str, Any]) -> dict[str, Any]:
        self._rebuild_company_states()
        self._rebuild_family_moves()
        self._rebuild_npc_truth_profile()
        self._decay_topic_registry()
        self._decay_norm_registry()
        self._rebuild_talk_topics()
        self.state["active_topics"] = self._active_public_topics(limit=10)
        self.state["active_norms"] = self._active_norms_view(limit=10)
        self._sync_collective_actions()
        self.state["active_collective_actions"] = self._active_collective_actions_view(limit=10)
        for npc in self.state.get("npcs", []):
            npc["agent_prompt"] = self._npc_agent_prompt(npc)
        npc_cards = self._build_npc_cards()
        family_moves = copy.deepcopy(self.state.get("family_moves", []))
        company_states = copy.deepcopy(self.state.get("company_states", []))
        active_topics = copy.deepcopy(self.state.get("active_topics", []))
        active_norms = copy.deepcopy(self.state.get("active_norms", []))
        active_collective_actions = copy.deepcopy(self.state.get("active_collective_actions", []))
        include_image = (not self._is_background_scene_pulse(trigger)) or self._full_scheduled_llm_mode()
        return {
            "trigger": trigger,
            "day": self.state.get("day", 1),
            "scene_observation": self._llm_scene_observation(observation, include_image=include_image),
            "macro": copy.deepcopy(self.state.get("macro", {})),
            "district_signals": copy.deepcopy(self.state.get("district_signals", {})),
            "topics": [
                {
                    "id": str(topic.get("id", "")),
                    "kind": str(topic.get("kind", "")),
                    "district": str(topic.get("district", "")),
                    "label": str(topic.get("label", "")),
                    "summary": str(topic.get("summary", "")),
                    "heat": float(topic.get("heat", 0.0)),
                    "credibility": float(topic.get("credibility", 0.0)),
                    "spread_count": int(topic.get("spread_count", 0)),
                    "status": str(topic.get("status", "")),
                    "tags": list(topic.get("tags", [])),
                }
                for topic in active_topics
            ],
            "norms": [
                {
                    "id": str(norm.get("id", "")),
                    "text": str(norm.get("text", "")),
                    "category": str(norm.get("category", "")),
                    "district": str(norm.get("district", "")),
                    "support": float(norm.get("support", 0.0)),
                    "strength": float(norm.get("strength", 0.0)),
                    "violation_cost": float(norm.get("violation_cost", 0.0)),
                    "status": str(norm.get("status", "")),
                    "source_topic_ids": list(norm.get("source_topic_ids", [])),
                }
                for norm in active_norms
            ],
            "collective_actions": [
                {
                    "id": str(action.get("id", "")),
                    "kind": str(action.get("kind", "")),
                    "district": str(action.get("district", "")),
                    "label": str(action.get("label", "")),
                    "theme": str(action.get("theme", "")),
                    "stage": str(action.get("stage", "")),
                    "status": str(action.get("status", "")),
                    "heat": float(action.get("heat", 0.0)),
                    "support": float(action.get("support", 0.0)),
                    "commitment": float(action.get("commitment", 0.0)),
                    "turnout": float(action.get("turnout", 0.0)),
                    "risk": float(action.get("risk", 0.0)),
                    "expected_reward": float(action.get("expected_reward", 0.0)),
                    "target_location_title": str(action.get("target_location_title", "")),
                    "target_subregion_name": str(action.get("target_subregion_name", "")),
                    "target_x": float(action.get("target_x", 0.0)),
                    "target_y": float(action.get("target_y", 0.0)),
                    "response_mode": str(action.get("response_mode", "")),
                    "response_note": str(action.get("response_note", "")),
                    "source_topic_ids": list(action.get("source_topic_ids", [])),
                    "source_norm_ids": list(action.get("source_norm_ids", [])),
                }
                for action in active_collective_actions
            ],
            "player": {
                "cash": int(self.state.get("player", {}).get("cash", 0)),
                "credit": int(self.state.get("player", {}).get("credit", 0)),
                "reputation": int(self.state.get("player", {}).get("reputation", 0)),
                "class_position": str(self.state.get("player", {}).get("class_position", "底层")),
                "rumors": list(self.state.get("player", {}).get("rumors", []))[-4:],
            },
            "goods": [
                {
                    "name": str(good.get("name", "")),
                    "current_price": int(good.get("current_price", 0)),
                    "price_trend": str(good.get("price_trend", "平")),
                }
                for good in self.state.get("goods", [])
            ],
            "stocks": [
                {
                    "name": str(stock.get("name", "")),
                    "current_price": int(stock.get("current_price", 0)),
                    "market_sentiment": str(stock.get("market_sentiment", "平")),
                    "family_owner": str(stock.get("family_owner", "")),
                }
                for stock in self.state.get("stocks", [])
            ],
            "families": [
                {
                    "id": str(move.get("id", "")),
                    "name": str(move.get("name", "")),
                    "public_action": str(move.get("public_action", "")),
                    "hidden_action": str(move.get("hidden_action", "")),
                    "target_asset": str(move.get("target_asset", "")),
                    "pressure_score": float(move.get("pressure_score", 0.0)),
                    "player_attitude": str(move.get("player_attitude", "")),
                    "capital_posture": str(move.get("capital_posture", "")),
                    "recent_briefs": copy.deepcopy(move.get("recent_briefs", [])),
                }
                for move in family_moves
            ],
            "companies": [
                {
                    "id": str(company.get("id", "")),
                    "name": str(company.get("name", "")),
                    "district": str(company.get("district", "")),
                    "headline": str(company.get("headline", "")),
                    "stock_name": str(company.get("stock_name", "")),
                    "operating_state": str(company.get("operating_state", "")),
                    "funding_state": str(company.get("funding_state", "")),
                    "workforce_mood": str(company.get("workforce_mood", "")),
                    "pressure_score": float(company.get("pressure_score", 0.0)),
                    "recent_briefs": copy.deepcopy(company.get("recent_briefs", [])),
                }
                for company in company_states
            ],
            "npcs": [
                {
                    "id": str(card.get("id", "")),
                    "name": str(card.get("name", "")),
                    "district": str(card.get("district", "")),
                    "title": str(card.get("title", "")),
                    "role": str(card.get("role", "")),
                    "agent_prompt": str(card.get("agent_prompt", "")),
                    "agent_budget_left": int(card.get("agent_budget_left", 0)),
                    "summary": str(card.get("personal_summary", "")),
                    "topic_digest": str(card.get("topic_digest", "")),
                    "norm_digest": str(card.get("norm_digest", "")),
                    "collective_digest": str(card.get("collective_digest", "")),
                    "memory_summary": str(card.get("memory_summary", "")),
                    "truthfulness": float(card.get("truthfulness", 0.5)),
                    "confidence": float(card.get("confidence", 0.5)),
                    "economic_pressure": float(card.get("economic_pressure", 0.0)),
                    "position_name": str(card.get("position_name", "")),
                    "position_bias": str(card.get("position_bias", "")),
                    "relation_status": str(card.get("relation_status", "")),
                    "recent_briefs": copy.deepcopy(card.get("brief_history", [])),
                }
                for card in npc_cards
            ],
        }

    def _apply_fallback_pulse_brief(self) -> None:
        self.state["llm_pulse_summary"] = self._fallback_pulse_summary()
        self.state["llm_market_note"] = self._fallback_market_note()
        self.state["llm_scene_focus"] = self._fallback_scene_focus()
        spin_map: dict[str, dict[str, Any]] = {}
        for npc in self.state.get("npcs", []):
            npc_id = str(npc.get("id", ""))
            tilt = self._npc_market_tilt(npc)
            line = str(npc.get("speech_lines", [""])[0]) if npc.get("speech_lines") else ""
            spin_map[npc_id] = {
                "line": line,
                "stance": str(npc.get("stance", "")),
                "market_tilt": tilt,
                "topic_action": {"mode": "silence", "topic_id": "", "intensity": 0.0, "note": ""},
                "norm_action": {"mode": "ignore", "norm_id": "", "text": "", "intensity": 0.0, "note": ""},
                "collective_action": {"mode": "avoid", "action_id": "", "kind": "", "intensity": 0.0, "note": ""},
                "source": "rule",
            }
            self._append_entity_brief_history(
                "npc_brief_history",
                npc_id,
                {
                    "line": line,
                    "stance": str(npc.get("stance", "")),
                    "market_tilt": tilt,
                    "topic_action": "silence",
                    "norm_action": "ignore",
                    "collective_action": "avoid",
                    "source": "rule",
                },
            )
        self.state["npc_spin_map"] = spin_map
        family_briefings: dict[str, dict[str, Any]] = {}
        for family in self.state.get("families", []):
            family_name = str(family.get("name", ""))
            signal = self._family_signal_from_state(family)
            family_briefings[family_name] = {
                "public_line": str(family.get("public_action", "")),
                "hidden_line": str(family.get("hidden_action", "")),
                "focus": str(family.get("strategy", "")),
                "signal": signal,
                "source": "rule",
            }
            self._append_entity_brief_history(
                "family_brief_history",
                family_name,
                {
                    "public_line": str(family.get("public_action", "")),
                    "hidden_line": str(family.get("hidden_action", "")),
                    "focus": str(family.get("strategy", "")),
                    "signal": signal,
                    "source": "rule",
                },
            )
        self.state["family_briefings"] = family_briefings
        company_briefings: dict[str, dict[str, Any]] = {}
        for company in self.state.get("company_states", []):
            company_id = str(company.get("id", ""))
            signal = self._company_signal_from_state(company)
            company_briefings[company_id] = {
                "headline": str(company.get("headline", company.get("name", ""))),
                "worker_note": str(company.get("workforce_mood", "")),
                "risk_note": str(company.get("funding_state", "")),
                "signal": signal,
                "source": "rule",
            }
            self._append_entity_brief_history(
                "company_brief_history",
                company_id,
                {
                    "headline": str(company.get("headline", company.get("name", ""))),
                    "worker_note": str(company.get("workforce_mood", "")),
                    "risk_note": str(company.get("funding_state", "")),
                    "signal": signal,
                    "source": "rule",
                },
            )
        self.state["company_briefings"] = company_briefings
        self._append_pulse_journal("fallback")

    def _apply_llm_npc_updates(self, updates: Any) -> set[str]:
        spin_map: dict[str, dict[str, Any]] = copy.deepcopy(self.state.get("npc_spin_map", {}))
        update_rows = updates if isinstance(updates, list) else []
        seen_ids: set[str] = set()
        for row in update_rows:
            if not isinstance(row, dict):
                continue
            npc_id = str(row.get("id", "")).strip()
            if not npc_id:
                continue
            npc = self._find_npc(npc_id)
            if not npc:
                continue
            seen_ids.add(npc_id)
            line = str(row.get("line", "")).strip()
            stance = str(row.get("stance", "")).strip()
            if line:
                existing = [str(value) for value in npc.get("speech_lines", []) if str(value).strip() and str(value) != line]
                npc["speech_lines"] = [line, *existing[:2]]
            if stance:
                npc["stance"] = stance
            fallback_topic = self._resolve_talk_topic(npc, str(row.get("topic_id", "")), str(npc.get("district", "")))
            topic_action = self._coerce_npc_topic_action(row.get("topic_action", {}), npc, fallback_topic)
            applied_topic = self._apply_topic_action(npc, fallback_topic, topic_action)
            norm_action = self._coerce_npc_norm_action(row.get("norm_action", {}), npc, applied_topic or fallback_topic, topic_action)
            applied_norm = self._record_norm_action(npc, applied_topic or fallback_topic, topic_action, norm_action)
            collective_action = self._coerce_npc_collective_action(
                row.get("collective_action", {}),
                npc,
                applied_topic or fallback_topic,
                applied_norm,
                topic_action,
                norm_action,
            )
            applied_collective = self._apply_collective_action(npc, applied_topic or fallback_topic, applied_norm, collective_action)
            trade_decision = self._coerce_trade_decision(row.get("trade_decision", {}), npc)
            applied_trade = self._apply_npc_trade_decision(npc, trade_decision, source="llm")
            market_tilt = self._coerce_market_tilt(str(row.get("market_tilt", "")).strip(), npc)
            spin_map[npc_id] = {
                "line": line or (str(npc.get("speech_lines", [""])[0]) if npc.get("speech_lines") else ""),
                "stance": stance or str(npc.get("stance", "")),
                "market_tilt": market_tilt,
                "emotions": copy.deepcopy(row.get("emotions", {})),
                "beliefs_update": copy.deepcopy(row.get("beliefs_update", {})),
                "top_goals": copy.deepcopy(row.get("top_goals", [])),
                "social_message": str(row.get("social_message", line or "")),
                "trade_decision": copy.deepcopy(trade_decision),
                "trade_execution": copy.deepcopy(applied_trade or {}),
                "topic_action": copy.deepcopy(topic_action),
                "norm_action": copy.deepcopy(norm_action),
                "collective_action": copy.deepcopy(collective_action),
                "topic_id": str((applied_topic or fallback_topic or {}).get("id", "")),
                "norm_id": str((applied_norm or {}).get("id", "")),
                "collective_action_id": str((applied_collective or {}).get("id", "")),
                "source": "llm",
            }
            self._append_entity_brief_history(
                "npc_brief_history",
                npc_id,
                {
                    "line": spin_map[npc_id]["line"],
                    "stance": spin_map[npc_id]["stance"],
                    "market_tilt": market_tilt,
                    "social_message": str(row.get("social_message", line or "")),
                    "trade_decision": str(trade_decision.get("action", "hold")),
                    "topic_action": str(topic_action.get("mode", "")),
                    "norm_action": str(norm_action.get("mode", "")),
                    "collective_action": str(collective_action.get("mode", "")),
                    "source": "llm",
                },
            )
        for npc in self.state.get("npcs", []):
            npc_id = str(npc.get("id", ""))
            if npc_id in seen_ids or npc_id in spin_map:
                continue
            spin_map[npc_id] = {
                "line": str(npc.get("speech_lines", [""])[0]) if npc.get("speech_lines") else "",
                "stance": str(npc.get("stance", "")),
                "market_tilt": self._npc_market_tilt(npc),
                "emotions": {},
                "beliefs_update": {},
                "top_goals": [],
                "social_message": "",
                "trade_decision": {"action": "hold", "stock_name": "", "quantity": 0, "confidence": 0.0, "note": ""},
                "topic_action": {"mode": "silence", "topic_id": "", "intensity": 0.0, "note": ""},
                "norm_action": {"mode": "ignore", "norm_id": "", "text": "", "intensity": 0.0, "note": ""},
                "collective_action": {"mode": "avoid", "action_id": "", "kind": "", "intensity": 0.0, "note": ""},
                "source": "rule",
            }
        self.state["npc_spin_map"] = spin_map
        return seen_ids

    def _apply_llm_family_updates(self, updates: Any) -> set[str]:
        briefings: dict[str, dict[str, Any]] = copy.deepcopy(self.state.get("family_briefings", {}))
        update_rows = updates if isinstance(updates, list) else []
        rows_by_name = {
            str(row.get("name", "")).strip(): row
            for row in update_rows
            if isinstance(row, dict) and str(row.get("name", "")).strip()
        }
        for family in self.state.get("families", []):
            family_name = str(family.get("name", ""))
            row = rows_by_name.get(family_name, {})
            existing = briefings.get(family_name, {})
            public_line = str(row.get("public_line", "")).strip() or str(existing.get("public_line", "")) or str(family.get("public_action", ""))
            hidden_line = str(row.get("hidden_line", "")).strip() or str(existing.get("hidden_line", "")) or str(family.get("hidden_action", family.get("shadow_strategy", "")))
            focus = str(row.get("focus", "")).strip() or str(existing.get("focus", "")) or str(family.get("strategy", ""))
            signal = self._coerce_family_signal(str(row.get("signal", "")).strip() or str(existing.get("signal", "")), family)
            family["public_action"] = public_line
            family["hidden_action"] = hidden_line
            family["llm_focus"] = focus
            briefings[family_name] = {
                "public_line": public_line,
                "hidden_line": hidden_line,
                "focus": focus,
                "signal": signal,
                "source": "llm" if family_name in rows_by_name else str(existing.get("source", "rule")),
            }
            self._append_entity_brief_history(
                "family_brief_history",
                family_name,
                {
                    "public_line": public_line,
                    "hidden_line": hidden_line,
                    "focus": focus,
                    "signal": signal,
                    "source": briefings[family_name]["source"],
                },
            )
        self.state["family_briefings"] = briefings
        return set(rows_by_name.keys())

    def _apply_llm_company_updates(self, updates: Any) -> set[str]:
        briefings: dict[str, dict[str, Any]] = copy.deepcopy(self.state.get("company_briefings", {}))
        update_rows = updates if isinstance(updates, list) else []
        rows_by_id = {
            str(row.get("id", "")).strip(): row
            for row in update_rows
            if isinstance(row, dict) and str(row.get("id", "")).strip()
        }
        for company in self.state.get("company_states", []):
            company_id = str(company.get("id", ""))
            row = rows_by_id.get(company_id, {})
            existing = briefings.get(company_id, {})
            headline = str(row.get("headline", "")).strip() or str(existing.get("headline", "")) or str(company.get("headline", ""))
            worker_note = str(row.get("worker_note", "")).strip() or str(existing.get("worker_note", "")) or str(company.get("workforce_mood", ""))
            risk_note = str(row.get("risk_note", "")).strip() or str(existing.get("risk_note", "")) or str(company.get("funding_state", ""))
            signal = self._coerce_company_signal(str(row.get("signal", "")).strip() or str(existing.get("signal", "")), company)
            company["llm_headline"] = headline
            company["llm_worker_note"] = worker_note
            company["llm_risk_note"] = risk_note
            briefings[company_id] = {
                "headline": headline,
                "worker_note": worker_note,
                "risk_note": risk_note,
                "signal": signal,
                "source": "llm" if company_id in rows_by_id else str(existing.get("source", "rule")),
            }
            self._append_entity_brief_history(
                "company_brief_history",
                company_id,
                {
                    "headline": headline,
                    "worker_note": worker_note,
                    "risk_note": risk_note,
                    "signal": signal,
                    "source": briefings[company_id]["source"],
                },
            )
        self.state["company_briefings"] = briefings
        return set(rows_by_id.keys())

    def _backfill_missing_npc_briefs(self, seen_ids: set[str], observation: dict[str, Any]) -> None:
        if not self.ark.enabled:
            return
        nearby_ids = self._nearby_npc_ids(observation)
        for npc in self.state.get("npcs", []):
            npc_id = str(npc.get("id", ""))
            if not npc_id or npc_id in seen_ids:
                continue
            topic = self._resolve_talk_topic(npc, "", str(npc.get("district", "")))
            truth_profile = self._truth_metrics_for_topic(npc, topic, "cautious", "街头风声")
            cadence = self._npc_brief_cadence_pulses(npc, observation, nearby_ids)
            use_image = cadence == 1 or npc_id in nearby_ids
            generated = self.ark.generate_npc_spin(
                {
                    "npc": copy.deepcopy(npc),
                    "llm_sections": self._npc_llm_sections(npc, topic),
                    "topic": copy.deepcopy(topic),
                    "active_topics": self._active_public_topics(limit=4, district_name=str(npc.get("district", ""))),
                    "active_norms": self._active_norms_view(limit=4, district_name=str(npc.get("district", ""))),
                    "active_collective_actions": self._active_collective_actions_view(limit=4, district_name=str(npc.get("district", ""))),
                    "truth_profile": truth_profile,
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {}).get(str(npc.get("district", "")), {})),
                    "relationship_memory": {
                        "player_memory": copy.deepcopy(self._npc_player_memory(npc)),
                        "recent_events": copy.deepcopy(list(npc.get("relationship_memory", []))[:4]),
                        "conversation_history": self._dialogue_history_view(npc, limit=4),
                        "local_memory": self._local_memory_view(npc, topic_id=str(topic.get("id", "")), limit=5),
                    },
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("npc_brief_history", npc_id)[:3]),
                    "scene_observation": self._llm_scene_observation(observation, include_image=use_image),
                }
            )
            if not generated:
                continue
            self._apply_llm_npc_updates(
                [
                    {
                        "id": npc_id,
                        "line": str((generated.get("lines", [""]) or [""])[0]),
                        "stance": str(generated.get("stance", "")),
                        "market_tilt": str(generated.get("market_tilt", "")),
                        "topic_action": copy.deepcopy(generated.get("topic_action", {})),
                        "norm_action": copy.deepcopy(generated.get("norm_action", {})),
                        "collective_action": copy.deepcopy(generated.get("collective_action", {})),
                    }
                ]
            )

    def _backfill_missing_family_briefs(self, seen_names: set[str], observation: dict[str, Any]) -> None:
        if not self.ark.enabled:
            return
        for family_move in self.state.get("family_moves", []):
            family_name = str(family_move.get("name", ""))
            if not family_name or family_name in seen_names:
                continue
            generated = self.ark.generate_family_briefing(
                {
                    "family": copy.deepcopy(family_move),
                    "controlled_companies": [
                        copy.deepcopy(company)
                        for company in self.state.get("company_states", [])
                        if str(company.get("family_owner", "")) == family_name
                    ],
                    "active_topics": self._active_public_topics(limit=4, district_name=str(family_move.get("district", ""))),
                    "active_norms": self._active_norms_view(limit=4, district_name=str(family_move.get("district", ""))),
                    "active_collective_actions": self._active_collective_actions_view(limit=4, district_name=str(family_move.get("district", ""))),
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {})),
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("family_brief_history", family_name)[:3]),
                    "scene_observation": self._llm_scene_observation(observation, include_image=False),
                }
            )
            if not generated:
                continue
            self._apply_llm_family_updates(
                [
                    {
                        "name": family_name,
                        "public_line": str(generated.get("public_line", "")),
                        "hidden_line": str(generated.get("hidden_line", "")),
                        "focus": str(generated.get("focus", "")),
                        "signal": str(generated.get("signal", "")),
                    }
                ]
            )

    def _backfill_missing_company_briefs(self, seen_ids: set[str], observation: dict[str, Any]) -> None:
        if not self.ark.enabled:
            return
        for company in self.state.get("company_states", []):
            company_id = str(company.get("id", ""))
            if not company_id or company_id in seen_ids:
                continue
            generated = self.ark.generate_company_briefing(
                {
                    "company": copy.deepcopy(company),
                    "active_topics": self._active_public_topics(limit=4, district_name=str(company.get("district", ""))),
                    "active_norms": self._active_norms_view(limit=4, district_name=str(company.get("district", ""))),
                    "active_collective_actions": self._active_collective_actions_view(limit=4, district_name=str(company.get("district", ""))),
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {}).get(str(company.get("district", "")), {})),
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("company_brief_history", company_id)[:3]),
                    "scene_observation": self._llm_scene_observation(observation, include_image=False),
                }
            )
            if not generated:
                continue
            self._apply_llm_company_updates(
                [
                    {
                        "id": company_id,
                        "headline": str(generated.get("headline", "")),
                        "worker_note": str(generated.get("worker_note", "")),
                        "risk_note": str(generated.get("risk_note", "")),
                        "signal": str(generated.get("signal", "")),
                    }
                ]
            )

    def _refresh_all_npc_briefs(self, observation: dict[str, Any], seed_seen_ids: set[str] | None = None) -> None:
        if not self.ark.enabled:
            return
        seen_ids = set(seed_seen_ids or set())
        pulse_index = int(self.state.get("demo_metrics", {}).get("ai_pulses", 0))
        nearby_ids = self._nearby_npc_ids(observation)
        refreshed = 0
        refresh_cap = 4 if self._use_lightweight_scheduled_llm() else max(4, len(self.state.get("npcs", [])))
        for npc in self.state.get("npcs", []):
            if refreshed >= refresh_cap:
                break
            npc_id = str(npc.get("id", ""))
            if not npc_id:
                continue
            if npc_id in seen_ids:
                continue
            cadence = self._npc_brief_cadence_pulses(npc, observation, nearby_ids)
            last_refresh = int(npc.get("last_llm_brief_pulse", -999))
            if last_refresh >= 0 and pulse_index - last_refresh < cadence:
                continue
            topic = self._resolve_talk_topic(npc, "", str(npc.get("district", "")))
            truth_profile = self._truth_metrics_for_topic(npc, topic, "cautious", "街头风声")
            if not self._consume_agent_budget(npc, "npc_spin", 1):
                continue
            self._queue_agent_task(npc, "npc_spin", str(topic.get("label", "街头风声")))
            generated = self.ark.generate_npc_spin(
                {
                    "npc": copy.deepcopy(npc),
                    "agent_profile": self._npc_agent_profile(npc),
                    "llm_sections": self._npc_llm_sections(npc, topic),
                    "topic": copy.deepcopy(topic),
                    "active_topics": self._active_public_topics(limit=4, district_name=str(npc.get("district", ""))),
                    "active_norms": self._active_norms_view(limit=4, district_name=str(npc.get("district", ""))),
                    "active_collective_actions": self._active_collective_actions_view(limit=4, district_name=str(npc.get("district", ""))),
                    "truth_profile": truth_profile,
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {}).get(str(npc.get("district", "")), {})),
                    "relationship_memory": {
                        "player_memory": copy.deepcopy(self._npc_player_memory(npc)),
                        "recent_events": copy.deepcopy(list(npc.get("relationship_memory", []))[:4]),
                        "conversation_history": self._dialogue_history_view(npc, limit=4),
                        "local_memory": self._local_memory_view(npc, topic_id=str(topic.get("id", "")), limit=5),
                    },
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("npc_brief_history", npc_id)[:3]),
                    "scene_observation": self._llm_scene_observation(
                        observation,
                        include_image=cadence == 1 or npc_id in nearby_ids,
                    ),
                }
            )
            if not generated:
                continue
            npc["last_llm_brief_pulse"] = pulse_index
            npc["llm_refresh_cadence"] = cadence
            self._remember_agent_output(npc, "npc_spin", str((generated.get("lines", [""]) or [""])[0]))
            self._apply_llm_npc_updates(
                [
                    {
                        "id": npc_id,
                        "line": str((generated.get("lines", [""]) or [""])[0]),
                        "stance": str(generated.get("stance", "")),
                        "market_tilt": str(generated.get("market_tilt", "")),
                        "topic_action": copy.deepcopy(generated.get("topic_action", {})),
                        "norm_action": copy.deepcopy(generated.get("norm_action", {})),
                        "collective_action": copy.deepcopy(generated.get("collective_action", {})),
                    }
                ]
            )
            refreshed += 1

    def _nearby_npc_ids(self, observation: dict[str, Any]) -> set[str]:
        scene_context = observation.get("scene_context", {}) if isinstance(observation, dict) else {}
        rows = scene_context.get("nearby_npcs", []) if isinstance(scene_context, dict) else []
        nearby_ids: set[str] = set()
        if not isinstance(rows, list):
            return nearby_ids
        for row in rows:
            if not isinstance(row, dict):
                continue
            npc_id = str(row.get("id", "")).strip()
            if npc_id:
                nearby_ids.add(npc_id)
        return nearby_ids

    def _npc_brief_cadence_pulses(self, npc: dict[str, Any], observation: dict[str, Any], nearby_ids: set[str] | None = None) -> int:
        npc_id = str(npc.get("id", ""))
        nearby = npc_id in (nearby_ids or set())
        current_district = str(observation.get("current_district", "")) if isinstance(observation, dict) else ""
        npc_district = str(npc.get("district", ""))
        class_name = str(npc.get("class", ""))
        topic_heat = 0.0
        for topic in self._talk_topics_for_npc(npc_id, npc_district):
            topic_heat = max(topic_heat, float(topic.get("heat", 0.0)))
        profile = self.state.get("npc_truth_profile", {}).get(npc_id, {})
        economic_pressure = float(profile.get("economic_pressure", 0.0))
        memory = self._npc_player_memory(npc)
        recent_player_attention = int(memory.get("talk_count", 0)) > 0 and int(self.state.get("day", 1)) - int(memory.get("last_seen_day", 0)) <= 1
        district_signals = self.state.get("district_signals", {}).get(npc_district, {})
        district_heat = (
            float(district_signals.get("gossip", 0.0))
            + float(district_signals.get("fear", 0.0))
            + float(district_signals.get("trade_heat", 0.0))
            + float(district_signals.get("labor_heat", 0.0))
        )
        if class_name == "特殊角色":
            if nearby or npc_district == current_district or topic_heat >= 0.18 or district_heat >= 0.28 or recent_player_attention:
                return 1
            return 2
        if class_name == "关键角色" and (nearby or npc_district == current_district or topic_heat >= 0.18 or district_heat >= 0.28):
            return 1
        if nearby or topic_heat >= 0.55 or economic_pressure >= 0.42 or recent_player_attention:
            return 1
        if npc_district == current_district and district_heat >= 0.5:
            return 1
        if class_name in {"关键角色", "中层"} and (topic_heat >= 0.18 or economic_pressure >= 0.18 or npc_district == current_district):
            return 2
        if topic_heat >= 0.28 or economic_pressure >= 0.22 or npc_district == current_district:
            return 2
        stable_bias = sum(ord(ch) for ch in npc_id) % 2
        return 3 if stable_bias == 0 else 2

    def _refresh_all_family_briefs(self, observation: dict[str, Any], seed_seen_names: set[str] | None = None) -> None:
        if not self.ark.enabled:
            return
        seen_names = set(seed_seen_names or set())
        refreshed = 0
        refresh_cap = 2 if self._use_lightweight_scheduled_llm() else max(2, len(self.state.get("family_moves", [])))
        for family_move in self.state.get("family_moves", []):
            if refreshed >= refresh_cap:
                break
            family_name = str(family_move.get("name", ""))
            if not family_name:
                continue
            if family_name in seen_names:
                continue
            generated = self.ark.generate_family_briefing(
                {
                    "family": copy.deepcopy(family_move),
                    "controlled_companies": [
                        copy.deepcopy(company)
                        for company in self.state.get("company_states", [])
                        if str(company.get("family_owner", "")) == family_name
                    ],
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {})),
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("family_brief_history", family_name)[:3]),
                    "scene_observation": self._llm_scene_observation(observation, include_image=False),
                }
            )
            if not generated:
                continue
            self._apply_llm_family_updates(
                [
                    {
                        "name": family_name,
                        "public_line": str(generated.get("public_line", "")),
                        "hidden_line": str(generated.get("hidden_line", "")),
                        "focus": str(generated.get("focus", "")),
                        "signal": str(generated.get("signal", "")),
                    }
                ]
            )
            refreshed += 1

    def _refresh_all_company_briefs(self, observation: dict[str, Any], seed_seen_ids: set[str] | None = None) -> None:
        if not self.ark.enabled:
            return
        seen_ids = set(seed_seen_ids or set())
        refreshed = 0
        refresh_cap = 2 if self._use_lightweight_scheduled_llm() else max(2, len(self.state.get("company_states", [])))
        for company in self.state.get("company_states", []):
            if refreshed >= refresh_cap:
                break
            company_id = str(company.get("id", ""))
            if not company_id:
                continue
            if company_id in seen_ids:
                continue
            generated = self.ark.generate_company_briefing(
                {
                    "company": copy.deepcopy(company),
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {}).get(str(company.get("district", "")), {})),
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("company_brief_history", company_id)[:3]),
                    "scene_observation": self._llm_scene_observation(observation, include_image=False),
                }
            )
            if not generated:
                continue
            self._apply_llm_company_updates(
                [
                    {
                        "id": company_id,
                        "headline": str(generated.get("headline", "")),
                        "worker_note": str(generated.get("worker_note", "")),
                        "risk_note": str(generated.get("risk_note", "")),
                        "signal": str(generated.get("signal", "")),
                    }
                ]
            )
            refreshed += 1

    def _append_pulse_journal(self, trigger: str) -> None:
        rows = self.state.get("pulse_journal", [])
        journal = rows if isinstance(rows, list) else []
        journal.insert(
            0,
            {
                "day": int(self.state.get("day", 1)),
                "clock": self._clock_label(),
                "trigger": trigger,
                "pulse_summary": str(self.state.get("llm_pulse_summary", "")),
                "market_note": str(self.state.get("llm_market_note", "")),
                "scene_focus": str(self.state.get("llm_scene_focus", "")),
            },
        )
        self.state["pulse_journal"] = journal[:8]

    def _apply_llm_attention_pressure(self) -> None:
        for npc in self.state.get("npcs", []):
            npc_id = str(npc.get("id", ""))
            spin = self.state.get("npc_spin_map", {}).get(npc_id, {})
            if str(spin.get("source", "")) != "llm":
                continue
            tilt = self._coerce_market_tilt(str(spin.get("market_tilt", "")), npc)
            position_kind, position_name, _, _ = self._dominant_position(npc)
            district_name = str(npc.get("district", ""))
            policy = npc.get("agent_policy", {})
            style = str(policy.get("market_style", self._npc_market_style(npc)))
            weight = float(policy.get("budget_weight", 1.0))
            if position_name and position_kind == "stock":
                base_delta = 0.012 if tilt in {"bullish", "supportive"} else -0.012 if tilt in {"bearish", "panic"} else 0.0
                if "控险" in style:
                    base_delta *= 0.68
                elif "追涨杀跌" in style:
                    base_delta *= 1.18
                delta = base_delta * weight
                if delta != 0.0:
                    self.state["market_pressure"]["stocks"][position_name] = float(self.state["market_pressure"]["stocks"].get(position_name, 0.0)) + delta
            elif position_name and position_kind == "goods":
                base_delta = 0.01 if tilt in {"bullish", "supportive"} else -0.01 if tilt in {"bearish", "panic"} else 0.0
                if "保现金流" in style:
                    base_delta *= 0.72
                delta = base_delta * weight
                if delta != 0.0:
                    self.state["market_pressure"]["goods"][position_name] = float(self.state["market_pressure"]["goods"].get(position_name, 0.0)) + delta
            if tilt in {"panic", "bearish"}:
                self._bump_district_signal(district_name, "fear", 0.03)
                self._bump_district_signal(district_name, "gossip", 0.02)
            elif tilt in {"bullish", "supportive"}:
                self._bump_district_signal(district_name, "trade_heat", 0.03)
                self._bump_district_signal(district_name, "gossip", 0.02)

        for family_move in self.state.get("family_moves", []):
            family_name = str(family_move.get("name", ""))
            briefing = self.state.get("family_briefings", {}).get(family_name, {})
            if str(briefing.get("source", "")) != "llm":
                continue
            signal = self._coerce_family_signal(str(briefing.get("signal", "")), family_move)
            target_asset = str(family_move.get("target_asset", ""))
            district_name = "交易所"
            if signal == "spin":
                self.state["macro"]["media_sentiment"] = min(100, int(self.state["macro"].get("media_sentiment", 50)) + 1)
                self._bump_district_signal(district_name, "gossip", 0.05)
            elif signal == "support":
                if target_asset in self.state["market_pressure"]["stocks"]:
                    self.state["market_pressure"]["stocks"][target_asset] = float(self.state["market_pressure"]["stocks"].get(target_asset, 0.0)) + 0.016
                if target_asset in self.state["market_pressure"]["goods"]:
                    self.state["market_pressure"]["goods"][target_asset] = float(self.state["market_pressure"]["goods"].get(target_asset, 0.0)) + 0.012
                self._bump_district_signal(district_name, "liquidity", 0.04)
            elif signal in {"clampdown", "short"}:
                if target_asset in self.state["market_pressure"]["stocks"]:
                    self.state["market_pressure"]["stocks"][target_asset] = float(self.state["market_pressure"]["stocks"].get(target_asset, 0.0)) - 0.016
                if target_asset in self.state["market_pressure"]["goods"]:
                    self.state["market_pressure"]["goods"][target_asset] = float(self.state["market_pressure"]["goods"].get(target_asset, 0.0)) - 0.012
                self._bump_district_signal(district_name, "fear", 0.04)

        for company in self.state.get("company_states", []):
            company_id = str(company.get("id", ""))
            briefing = self.state.get("company_briefings", {}).get(company_id, {})
            if str(briefing.get("source", "")) != "llm":
                continue
            signal = self._coerce_company_signal(str(briefing.get("signal", "")), company)
            stock_name = str(company.get("stock_name", ""))
            district_name = str(company.get("district", ""))
            if signal == "expansion":
                if stock_name in self.state["market_pressure"]["stocks"]:
                    self.state["market_pressure"]["stocks"][stock_name] = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0)) + 0.014
                self._bump_district_signal(district_name, "trade_heat", 0.03)
                self._bump_district_signal(district_name, "liquidity", 0.02)
            elif signal == "stress":
                if stock_name in self.state["market_pressure"]["stocks"]:
                    self.state["market_pressure"]["stocks"][stock_name] = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0)) - 0.014
                self._bump_district_signal(district_name, "fear", 0.03)
            elif signal == "labor":
                self.state["macro"]["worker_unrest"] = min(100, int(self.state["macro"].get("worker_unrest", 50)) + 1)
                self._bump_district_signal(district_name, "labor_heat", 0.04)

    def _fallback_pulse_summary(self) -> str:
        hottest_district, signals = max(
            self.state.get("district_signals", {}).items(),
            key=lambda item: float(item[1].get("gossip", 0.0)) + float(item[1].get("fear", 0.0)) + float(item[1].get("trade_heat", 0.0)),
            default=("街区", {"gossip": 0.0, "fear": 0.0, "trade_heat": 0.0}),
        )
        if float(signals.get("fear", 0.0)) >= 0.3:
            return f"{hottest_district} 先紧起来了，风声比价格跑得更快。"
        if float(signals.get("trade_heat", 0.0)) >= 0.3:
            return f"{hottest_district} 正有人抢着换手，铜币和货都在挪。"
        return f"{hottest_district} 还没炸锅，但每个人都在试别人的底。"

    def _fallback_market_note(self) -> str:
        hot_good = self._top_market_move(self.state.get("goods", []), "price_trend")
        hot_stock = self._top_market_move(self.state.get("stocks", []), "market_sentiment")
        return f"{hot_good}，{hot_stock}。"

    def _fallback_scene_focus(self) -> str:
        observation = self.state.get("scene_observation", {})
        scene_context = observation.get("scene_context", {})
        district_name = str(observation.get("current_district", "街巷"))
        nearby_npcs = scene_context.get("nearby_npcs", [])
        if nearby_npcs:
            return f"{district_name} 里，{nearby_npcs[0].get('name', '有人')} 盯你的时间比摊位还久。"
        return f"{district_name} 还在动，只是没人愿意先把真话说全。"

    def _apply_scene_director_note(self, trigger: str) -> None:
        observation = self.state.get("scene_observation", {})
        generated = self.ark.generate_scene_read(
            {
                "trigger": trigger,
                "day": self.state["day"],
                "scene_observation": observation,
                "macro": self.state["macro"],
                "headlines": self.state.get("headline_news", []),
            }
        )
        note = ""
        if generated:
            note = str(generated.get("director_note", "")).strip()
            headline_title = str(generated.get("headline_title", "")).strip()
            headline_body = str(generated.get("headline_body", "")).strip()
            if headline_title and headline_body:
                self.state["global_news"].insert(
                    0,
                    {
                        "title": headline_title,
                        "body": headline_body,
                        "tags": ["场景", str(observation.get("current_district", "街区"))],
                        "scope": "district",
                    },
                )
                self.state["global_news"] = self.state["global_news"][:8]
        if not note:
            if str(self.state.get("llm_scene_focus", "")).strip():
                note = str(self.state.get("llm_scene_focus", "")).strip()
            else:
                scene_context = observation.get("scene_context", {})
                district_name = str(observation.get("current_district", "街巷"))
                nearby_npcs = scene_context.get("nearby_npcs", [])
                if nearby_npcs:
                    note = f"{district_name} 里，{nearby_npcs[0].get('name', '有人')} 正把目光往你身上压。"
                elif district_name:
                    note = f"{district_name} 的空气正在发紧，下一轮风声会更真。"
                else:
                    note = "城里照旧在转，但风向开始变了。"
        self.state["scene_director_note"] = note[:140]

    def _refresh_ambient_speeches(self) -> None:
        self.state["ambient_speeches"] = {
            npc["id"]: {"lines": npc["speech_lines"], "cadence_seconds": npc["cadence_seconds"]}
            for npc in self.state["npcs"]
        }

    def _seed_global_news(self) -> None:
        self.state["global_news"] = [
            {
                "title": "晨钟刚响，城里先涨的是面包",
                "body": "贫民街和工棚的配给越来越薄，底层今天依旧得先为口粮发愁。",
                "tags": ["面包", "底层", "开局"],
                "scope": "city",
            },
            {
                "title": "三大家族都在等别人先犯错",
                "body": "海藻盯供给、龟甲压班次、珊瑚看盘面，这座镇还没开盘就满是算计。",
                "tags": ["家族", "开局"],
                "scope": "city",
            },
        ]
        self._refresh_derived_views()

    def _seed_norm_registry(self) -> None:
        tick = self._world_tick()
        self.state["norm_registry"] = [
            {
                "id": "norm_supply_poor_ration",
                "text": "先保住口粮",
                "category": "supply",
                "district": "贫民街",
                "scope": "district",
                "support": 0.58,
                "strength": 0.46,
                "violation_cost": 0.22,
                "pressure": 0.34,
                "status": "active",
                "origin": "seed",
                "source_topic_ids": [],
                "tags": ["民生", "口粮"],
                "target_groups": ["居民", "店主", "工人"],
                "mention_count": 1,
                "reinforce_count": 1,
                "contest_count": 0,
                "seed_count": 1,
                "last_tick": tick,
            },
            {
                "id": "norm_labor_factory_wage",
                "text": "降薪不能忍",
                "category": "labor",
                "district": "工厂区",
                "scope": "district",
                "support": 0.54,
                "strength": 0.44,
                "violation_cost": 0.28,
                "pressure": 0.38,
                "status": "active",
                "origin": "seed",
                "source_topic_ids": [],
                "tags": ["工资", "工厂"],
                "target_groups": ["工人", "临时工", "工会"],
                "mention_count": 1,
                "reinforce_count": 1,
                "contest_count": 0,
                "seed_count": 1,
                "last_tick": tick,
            },
            {
                "id": "norm_port_schedule_cargo",
                "text": "货运不能乱",
                "category": "logistics",
                "district": "港口",
                "scope": "district",
                "support": 0.52,
                "strength": 0.41,
                "violation_cost": 0.24,
                "pressure": 0.31,
                "status": "active",
                "origin": "seed",
                "source_topic_ids": [],
                "tags": ["港口", "物流"],
                "target_groups": ["工人", "代理人", "船员"],
                "mention_count": 1,
                "reinforce_count": 1,
                "contest_count": 0,
                "seed_count": 1,
                "last_tick": tick,
            },
            {
                "id": "norm_finance_exchange_caution",
                "text": "行情乱时先缩仓",
                "category": "finance",
                "district": "交易所",
                "scope": "district",
                "support": 0.49,
                "strength": 0.39,
                "violation_cost": 0.2,
                "pressure": 0.27,
                "status": "warming",
                "origin": "seed",
                "source_topic_ids": [],
                "tags": ["金融", "仓位"],
                "target_groups": ["投机者", "银行经理", "店主"],
                "mention_count": 1,
                "reinforce_count": 1,
                "contest_count": 0,
                "seed_count": 1,
                "last_tick": tick,
            },
        ]

    def _refresh_derived_views(self, rebuild_agent_prompts: bool = True) -> None:
        self.state["headline_news"] = self.state["global_news"][:3]
        self.state["house_states"] = self._build_house_states()
        self._update_player_class()
        collective_profile = copy.deepcopy(self._refresh_player_collective_profile())
        self.state["player_collective_profile"] = collective_profile
        reputation_tracks, shadow_reputation = self._derive_story_reputation()
        metrics = self._story_metrics_state()
        metrics["reputation"] = copy.deepcopy(reputation_tracks)
        metrics["shadow_reputation"] = copy.deepcopy(shadow_reputation)
        self.state["player"]["reputation_tracks"] = copy.deepcopy(reputation_tracks)
        self.state["player"]["shadow_reputation"] = copy.deepcopy(shadow_reputation)
        self.state["population_bias"] = self._build_population_bias()
        self._rebuild_company_states()
        self._rebuild_family_moves()
        self._rebuild_npc_truth_profile()
        self._decay_topic_registry()
        self._rebuild_talk_topics()
        self.state["active_topics"] = self._active_public_topics(limit=8)
        self._decay_norm_registry()
        self.state["active_norms"] = self._active_norms_view(limit=8)
        self._sync_collective_actions()
        self.state["active_collective_actions"] = self._active_collective_actions_view(limit=8)
        for stock in self.state.get("stocks", []):
            stock["market_cap"] = int(int(stock.get("issued_shares", 0)) * int(stock.get("current_price", 0)))
            stock["float_turnover"] = round(
                float(stock.get("trade_volume", 0)) / max(float(stock.get("free_float", 1)), 1.0),
                4,
            )
            base = max(float(stock.get("previous_close", stock.get("base_price", stock.get("current_price", 1)))), 1.0)
            stock["change_amount"] = int(stock.get("current_price", 0)) - int(stock.get("previous_close", stock.get("base_price", 0)))
            stock["change_pct"] = round((float(stock.get("current_price", 0)) - base) / base, 4)
        self._rebuild_stock_holder_registry()
        self.state["stock_exchange_view"] = self._build_stock_exchange_view()
        for npc in self.state["npcs"]:
            if rebuild_agent_prompts or not str(npc.get("agent_prompt", "")).strip():
                npc["agent_prompt"] = self._npc_agent_prompt(npc)
                npc["agent_tool_policy"] = self._npc_tool_policy(npc)
                npc["agent_policy"] = {
                    **npc.get("agent_policy", {}),
                    "social_style": self._npc_social_style(npc),
                    "market_style": self._npc_market_style(npc),
                    "agenda": self._npc_agent_agenda(npc),
                    "budget_weight": round(max(0.4, min(1.8, self._npc_daily_agent_budget(npc) / 6.0)), 2),
                    "topic_digest": self._npc_topic_digest(npc),
                    "norm_digest": self._npc_norm_digest(npc),
                    "collective_digest": self._npc_collective_digest(npc),
                }
        self.state["npc_cards"] = self._build_npc_cards()
        self.state["local_rumor"] = copy.deepcopy(self.state.get("rumor_log", [])[:8])
        self.state["city_news"] = self._build_city_news()
        self.state["district_topic"] = self._build_district_topic_map()
        ranked = sorted(
            self.state["npcs"],
            key=lambda npc: (npc["fear"] + npc["greed"] + npc["loyalty"]),
            reverse=True,
        )
        self.state["npc_highlights"] = [
            {
                "id": npc["id"],
                "name": npc["name"],
                "district": npc["district"],
                "mood": npc["mood"],
                "activity": npc.get("activity", ""),
                "home_state": npc.get("home_state", "away"),
                "indoor_activity": npc.get("indoor_activity", "away"),
                "home_id": npc.get("home_id", ""),
                "schedule_note": npc.get("schedule_note", ""),
                "lights_on": bool(npc.get("lights_on", False)),
                "goal": npc["current_goal"],
                "stance": npc["stance"],
                "fear": npc["fear"],
                "greed": npc["greed"],
                "line": npc["speech_lines"][0] if npc["speech_lines"] else "",
            }
            for npc in ranked[:6]
        ]
        macro = self.state["macro"]
        unrest_bias = "紧绷" if macro["worker_unrest"] >= 60 else "可控" if macro["worker_unrest"] < 50 else "升温"
        city_mood = "投机抬头" if macro["media_sentiment"] > 55 else "谨慎收缩" if macro["media_sentiment"] < 45 else "观望"
        self.state["macro_summary"] = {
            "clock_label": self._clock_label(),
            "time_period": self.state.get("time_period", "day"),
            "light_level": self.state.get("light_level", 1.0),
            "weather": copy.deepcopy(self.state.get("weather", {})),
            "weather_label": str(self.state.get("weather", {}).get("label", "晴天")),
            "interest_rate": macro["interest_rate"],
            "economy_heat": macro["economy_heat"],
            "housing_heat": macro["housing_heat"],
            "media_sentiment": macro["media_sentiment"],
            "worker_unrest": macro["worker_unrest"],
            "city_mood": city_mood,
            "unrest_bias": unrest_bias,
            "lit_houses": sum(1 for house in self.state["house_states"].values() if house.get("lights_on")),
            "scene_director_note": self.state.get("scene_director_note", ""),
            "llm_pulse_summary": self.state.get("llm_pulse_summary", ""),
            "llm_market_note": self.state.get("llm_market_note", ""),
            "llm_scene_focus": self.state.get("llm_scene_focus", ""),
            "norms_brief": "；".join(str(row.get("text", "")) for row in self.state.get("active_norms", [])[:2]),
            "collective_brief": "；".join(
                (
                    f"{row.get('label', '')}:{row.get('resolution_label', '')}"
                    if str(row.get("resolution_label", ""))
                    else str(row.get("label", ""))
                )
                for row in self.state.get("active_collective_actions", [])[:2]
            ),
            "collective_resolution_brief": "；".join(
                f"{row.get('label', '')}:{row.get('resolution_label', '')}"
                for row in self.state.get("collective_outcomes", [])[:2]
            ),
            "reputation_brief": " / ".join(f"{key}:{value}" for key, value in reputation_tracks.items()),
            "shadow_brief": " / ".join(
                [
                    f"SUI:{shadow_reputation.get('SUI', 15)}",
                    f"ST:{shadow_reputation.get('ST', 1.0)}",
                    f"WL:{shadow_reputation.get('WL', 1)}",
                    f"警局:{shadow_reputation.get('police_side', '摇摆观望')}",
                ]
            ),
            "last_scene_capture_at": self.state.get("last_scene_capture_at", "未收到"),
        }
        player = self.state["player"]
        active_task_id = str(player.get("active_task_id", ""))
        self.state["task_summary"] = {
            "active_task_id": active_task_id,
            "active_task": self._find_by_id(self.state["task_board"], active_task_id) if active_task_id else None,
            "family_relations": copy.deepcopy(player.get("family_relations", {})),
            "player_collective_profile": copy.deepcopy(collective_profile),
            "collective_followups": copy.deepcopy(self.state.get("collective_followups", [])[:6]),
        }
        hot_good = self._top_market_move(self.state["goods"], "price_trend")
        hot_stock = self._top_market_move(self.state["stocks"], "market_sentiment")
        latest_trade = self.state.get("stock_trade_tape", [{}])[0] if self.state.get("stock_trade_tape") else {}
        latest_news = self.state["headline_news"][0] if self.state["headline_news"] else {}
        latest_rumor = self.state["rumor_log"][0] if self.state["rumor_log"] else {}
        lead_topic = self.state["active_topics"][0] if self.state["active_topics"] else self.state["talk_topics"][0] if self.state["talk_topics"] else {}
        lead_norm = self.state["active_norms"][0] if self.state["active_norms"] else {}
        lead_collective = self.state["active_collective_actions"][0] if self.state.get("active_collective_actions") else {}
        lead_institution = self.state["institution_actions"][0] if self.state.get("institution_actions") else {}
        metrics = self.state.get("demo_metrics", {})
        objective = "先在街上看一圈，摸清地形和价格。"
        if self._route_choice_required():
            objective = "先选路线：精英路线接通暗池交易终端，平民路线接通底层互助网与声望检定。"
        elif int(metrics.get("work_actions", 0)) + int(metrics.get("goods_trades", 0)) > 0:
            objective = "去打听一条风声，看看消息怎么推市场。"
        elif int(metrics.get("intel_actions", 0)) > 0 or player.get("rumors"):
            objective = "去交易所买卖一支股票，感受舆论和价格联动。"
        elif int(metrics.get("stock_trades", 0)) > 0:
            objective = "敲响日钟，看事件、新闻和街区状态怎么反馈。"
        elif int(metrics.get("days_ended", 0)) > 0:
            objective = "Demo 闭环已经形成，可以继续试不同赚钱路径。"
        self.state["quick_hud"] = {
            "objective": objective,
            "market_flash": f"{hot_good} · {hot_stock}",
            "latest_news_title": str(latest_news.get('title', '')),
            "latest_news_body": str(latest_news.get('body', '')),
            "latest_rumor": str(latest_rumor.get('line', '')),
            "weather_label": str(self.state.get("weather", {}).get("label", "晴天")),
            "social_prompt": str(lead_topic.get("label", "")),
            "norm_prompt": str(lead_norm.get("text", "")),
            "collective_prompt": (
                f"{str(lead_collective.get('label', ''))} / {str(lead_collective.get('resolution_label', ''))}"
                if str(lead_collective.get("resolution_label", ""))
                else str(lead_collective.get("label", ""))
            ),
            "player_collective_stance": str(collective_profile.get("stance_label", "")),
            "player_collective_mode": str(collective_profile.get("dominant_mode", "observe")),
            "collective_aftermath": "；".join(
                f"{str(row.get('kind', 'followup'))}:{str(row.get('status', 'active'))}"
                for row in self.state.get("collective_followups", [])[:2]
            ),
            "institution_flash": str(lead_institution.get("public_line", "")),
            "ai_focus": str(self.state.get("llm_pulse_summary", "")),
            "market_note": str(self.state.get("llm_market_note", "")),
            "market_tape": str(latest_trade.get("anonymous_label", "")),
            "reputation_flash": self.state["macro_summary"]["reputation_brief"],
            "shadow_flash": self.state["macro_summary"]["shadow_brief"],
        }
        self._snapshot_cache = copy.deepcopy(self.state)

    def _build_population_bias(self) -> dict[str, Any]:
        districts: dict[str, dict[str, Any]] = {}
        band_counts: dict[str, int] = {}
        for district in self.state.get("districts", []):
            name = str(district.get("name", ""))
            signal = dict(self.state.get("district_signals", {}).get(name, {}))
            district_norms = self._active_norms_view(limit=4, district_name=name)
            district_collectives = self._active_collective_actions_view(limit=4, district_name=name)
            districts[name] = {
                "district": name,
                "gossip_bias": round(float(signal.get("gossip", 0.0)), 3),
                "labor_bias": round(float(signal.get("labor_heat", 0.0)), 3),
                "finance_bias": round(float(signal.get("trade_heat", 0.0)), 3),
                "fear_bias": round(float(signal.get("fear", 0.0)), 3),
                "top_norms": [
                    {
                        "id": str(row.get("id", "")),
                        "text": str(row.get("text", "")),
                        "support": round(float(row.get("support", 0.0)), 3),
                        "strength": round(float(row.get("strength", 0.0)), 3),
                    }
                    for row in district_norms[:3]
                ],
                "top_collectives": [
                    {
                        "id": str(row.get("id", "")),
                        "label": str(row.get("label", "")),
                        "stage": str(row.get("stage", "")),
                        "support": round(float(row.get("support", 0.0)), 3),
                        "commitment": round(float(row.get("commitment", 0.0)), 3),
                    }
                    for row in district_collectives[:3]
                ],
                "social_bands": {},
            }
        for npc in self.state.get("npcs", []):
            band = str(npc.get("social_band", self._npc_social_band(npc)))
            district_name = str(npc.get("district", ""))
            band_counts[band] = int(band_counts.get(band, 0)) + 1
            district_row = districts.setdefault(
                district_name,
                {
                    "district": district_name,
                    "gossip_bias": 0.0,
                    "labor_bias": 0.0,
                    "finance_bias": 0.0,
                    "fear_bias": 0.0,
                    "top_norms": [],
                    "top_collectives": [],
                    "social_bands": {},
                },
            )
            band_map = district_row.setdefault("social_bands", {})
            band_map[band] = int(band_map.get(band, 0)) + 1
        city_norms = self._active_norms_view(limit=6)
        city_collectives = self._active_collective_actions_view(limit=6)
        return {
            "citywide": {
                "dominant_norms": [str(row.get("text", "")) for row in city_norms[:4] if str(row.get("text", "")).strip()],
                "dominant_collectives": [str(row.get("label", "")) for row in city_collectives[:4] if str(row.get("label", "")).strip()],
                "social_band_distribution": band_counts,
            },
            "districts": districts,
        }

    def _pick_event_for_day(self) -> dict[str, Any]:
        scored: list[tuple[float, dict[str, Any]]] = []
        recent_rumors = self.state.get("rumor_log", [])[:5]
        for event in self.event_defs:
            score = 1.0 + self.random.uniform(0.0, 0.35)
            for condition in event.get("trigger_conditions", []):
                score += self._condition_score(condition)
            for rumor in recent_rumors:
                rumor_tags = rumor.get("tags", [])
                if event["district"] == rumor.get("district"):
                    score += 0.45
                if any(tag in rumor_tags for tag in event["news_template"].get("tags", [])):
                    score += 0.32
            scored.append((score, event))
        scored.sort(key=lambda row: row[0], reverse=True)
        return copy.deepcopy(scored[0][1])

    def _condition_score(self, condition: str) -> float:
        condition = str(condition).strip()
        if condition == "seasonal":
            return 0.7
        parts = condition.split()
        if len(parts) != 3:
            return 0.2
        key, operator, raw_threshold = parts
        value = float(self.state["macro"].get(key, 0))
        threshold = float(raw_threshold)
        if operator == ">":
            if value > threshold:
                return 1.1 + min(0.9, (value - threshold) / 28.0)
            return max(0.0, 0.4 - (threshold - value) / 35.0)
        if operator == "<":
            if value < threshold:
                return 1.1 + min(0.9, (threshold - value) / 28.0)
            return max(0.0, 0.4 - (value - threshold) / 35.0)
        return 0.2

    def _time_segment(self, minutes: int | None = None) -> dict[str, Any]:
        clock_minutes = int(self.state.get("clock_minutes", 8 * 60) if minutes is None else minutes)
        for segment in TIME_SEGMENTS:
            if int(segment["start"]) <= clock_minutes < int(segment["end"]):
                return copy.deepcopy(segment)
        return copy.deepcopy(TIME_SEGMENTS[-1])

    def _next_time_segment_start(self, minutes: int | None = None) -> int:
        clock_minutes = int(self.state.get("clock_minutes", 8 * 60) if minutes is None else minutes)
        for segment in TIME_SEGMENTS:
            if clock_minutes < int(segment["start"]):
                return int(segment["start"])
            if int(segment["start"]) <= clock_minutes < int(segment["end"]):
                next_index = TIME_SEGMENTS.index(segment) + 1
                if next_index < len(TIME_SEGMENTS):
                    return int(TIME_SEGMENTS[next_index]["start"])
                return 24 * 60
        return 24 * 60

    def _realtime_speed_multiplier(self) -> float:
        shadow = dict(self._story_metrics_state().get("shadow_reputation", {}))
        st_value = float(shadow.get("ST", self.state.get("player", {}).get("shadow_reputation", {}).get("ST", 1.0)))
        if st_value > 2.5:
            return 1.5
        if st_value > 2.0:
            return 1.2
        return 1.0

    def _apply_realtime_body_drain(self, elapsed_minutes: float) -> None:
        player = self._ensure_player_financial_state()
        hunger = float(player.get("hunger", 100.0))
        stamina = float(player.get("stamina", 100.0))
        st_value = float(dict(player.get("shadow_reputation", {})).get("ST", 1.0))
        hunger_loss = elapsed_minutes * 1.0
        stamina_loss = elapsed_minutes * 0.5 * max(1.0, st_value)
        if hunger < 20.0:
            stamina_loss *= 2.0
        player["hunger"] = round(max(0.0, hunger - hunger_loss), 1)
        player["stamina"] = round(max(0.0, stamina - stamina_loss), 1)

    def _consume_ap_block(self, reason: str = "") -> None:
        current = int(self.state.get("clock_minutes", 8 * 60))
        target = min(self._next_time_segment_start(current), 23 * 60 + 45)
        if target <= current:
            return
        if reason:
            self.state["scene_director_note"] = reason
        self._advance_clock(target - current)

    def _upcoming_story_event_hint(self, district: str, speaker: dict[str, Any] | None = None) -> dict[str, Any] | None:
        day = int(self.state.get("day", 1))
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        upcoming: list[tuple[int, str, str, str, str, list[str], str]] = []
        if day == 1 and minutes < 17 * 60:
            upcoming.append((17 * 60, "Market_Intel", "管网私有化公报", "今天 17:00 会发布管网私有化公报，AMB 会先承压，SWC 会先被资金抬起来。", "这不是已经发生的结果，而是盘面正在提前下注的方向。", ["AMB", "SWC", "私有化"], "交易所"))
        if day == 2:
            if minutes < 12 * 60:
                upcoming.append((12 * 60, "Persona_Intel", "亚瑟的死期", "中午会先传出亚瑟被盯上的消息；如果不干预，下午 16:00 他会被抹掉。", "这条消息更适合拿去预警、救人或做威慑。", ["亚瑟", "刀疤", "暗杀"], district))
            if minutes < 16 * 60:
                upcoming.append((16 * 60, "Event_Intel", "刀疤的行动线", "刀疤正在朝目标移动，下午 16:00 左右会完成一次物理清除。", "这条线索属于物理事件，不属于已经落地的新闻。", ["刀疤", "突袭", "行动"], district))
        if day == 3 and minutes < 20 * 60:
            upcoming.append((20 * 60, "Event_Intel", "零号起义结算", "今晚 20:00 前后会进入结算窗口，市场、街区和封锁线会一起失稳。", "越接近晚上，消息的时效越短。", ["起义", "结算", "封锁"], district))
        if not upcoming:
            return None
        target = sorted(upcoming, key=lambda item: item[0])[0]
        due_minutes, intel_type, title, line, body, tags, hint_district = target
        if district and hint_district not in {"", district, "交易所"} and district != "交易所":
            return None
        return {
            "intel_type": intel_type,
            "title": title,
            "line": line,
            "body": body,
            "tags": tags,
            "due_minutes": due_minutes,
            "source_bias": "timeline",
        }

    def _district_market_intel(self, district: str) -> dict[str, Any] | None:
        stock = max(self.state.get("stocks", []), key=lambda row: abs(float(row.get("change_pct", 0.0))), default=None)
        if not isinstance(stock, dict):
            return None
        company = self._company_for_stock(stock) or {}
        price = int(stock.get("current_price", 0))
        change_pct = float(stock.get("change_pct", 0.0)) * 100.0
        tone = "抬价" if change_pct >= 0 else "砸价"
        return {
            "intel_type": "Market_Intel",
            "title": f"{stock.get('ticker', stock.get('name', '标的'))} 盘口异动",
            "line": f"{stock.get('ticker', stock.get('name', '标的'))} 现价 {price}，盘面正在被{tone}，主因更像 {company.get('name', district or '街区')} 那边的仓位变化。",
            "body": f"这条消息指向市场层面的短时方向，适合用于买卖、对冲或观望，不该被写成已经发生的社会新闻。",
            "tags": ["盘口", str(stock.get("ticker", "")), str(company.get("name", ""))],
            "due_minutes": int(self.state.get("clock_minutes", 0)) + 90,
            "source_bias": "market",
            "stocks_delta": {str(stock.get('name', '')): 0.04 if change_pct >= 0 else -0.04},
        }

    def _district_event_intel(self, district: str) -> dict[str, Any] | None:
        active_actions = self._active_collective_actions_view(limit=4, district_name=district)
        if active_actions:
            action = dict(active_actions[0])
            when = str(action.get("stage_label", action.get("stage", "形成中")))
            return {
                "intel_type": "Event_Intel",
                "title": str(action.get("label", f"{district} 现场动向")),
                "line": f"{district} 的 {action.get('label', '现场动向')} 现在处在“{when}”阶段，相关人群已经朝 {action.get('target_location_title', '目标点')} 聚拢。",
                "body": f"这条消息描述的是物理现场和人群位移，适合用于赶路、回避或介入，不该被表述成抽象的“谁交换了风声”。",
                "tags": ["现场", district, str(action.get("kind", ""))],
                "due_minutes": int(self.state.get("clock_minutes", 0)) + 60,
                "source_bias": "event",
            }
        return None

    def _district_persona_intel(self, district: str, speaker: dict[str, Any] | None = None) -> dict[str, Any] | None:
        candidate = speaker or next(
            (npc for npc in self.state.get("npcs", []) if str(npc.get("district", "")) == district and float(npc.get("info_reliability", 0.0)) >= 0.6),
            None,
        )
        if not isinstance(candidate, dict):
            return None
        title = f"{candidate.get('name', '某人')} 的立场缝隙"
        line = f"{candidate.get('name', '某人')} 现在更在乎 {candidate.get('current_goal', '自身安全')}，这条线索适合用来试探、交换或威慑。"
        return {
            "intel_type": "Persona_Intel",
            "title": title,
            "line": line,
            "body": "这属于角色秘辛或立场弱点，真正的价值在对话分支、威慑和改道，而不是直接推价格。",
            "tags": ["人物", str(candidate.get("name", "")), str(candidate.get("role", ""))],
            "due_minutes": int(self.state.get("clock_minutes", 0)) + 180,
            "source_bias": "persona",
            "speaker_id": str(candidate.get("id", "")),
            "speaker_name": str(candidate.get("name", "")),
        }

    def _intel_metadata(self, intel_type: str, source: str, speaker: dict[str, Any] | None = None) -> dict[str, Any]:
        authenticity = 0.55
        dissemination = 2
        time_limit = 120
        source_text = str(source)
        if intel_type == "Market_Intel":
            time_limit = 90
            dissemination = 2
        elif intel_type == "Event_Intel":
            time_limit = 60
            dissemination = 1
        elif intel_type == "Persona_Intel":
            time_limit = 180
            dissemination = 1
        if "街头耳报" in source_text:
            authenticity -= 0.08
            dissemination += 1
        if speaker:
            role = str(speaker.get("role", ""))
            if role in {"记者", "代理人", "银行经理", "老板"}:
                authenticity += 0.18
            elif role in {"工会领袖", "店主"}:
                authenticity += 0.1
            elif role in {"工人", "临时工"}:
                authenticity += 0.04
            authenticity = max(0.12, min(0.96, authenticity + (float(speaker.get("info_reliability", 0.5)) - 0.5) * 0.4))
        return {
            "authenticity": round(max(0.12, min(0.98, authenticity)), 3),
            "dissemination": max(1, min(5, dissemination)),
            "time_limit_minutes": max(30, time_limit),
        }

    def _build_intel_packet(
        self,
        district: str,
        source: str,
        speaker: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        district_keywords = {
            "贫民街": ("贫民街", "海藻", "面包", "囤货", "市集"),
            "港口": ("港口", "龟甲船运", "慢工", "船", "物流"),
            "工厂区": ("工厂", "船坞", "事故", "工资", "煤"),
            "交易所": ("交易所", "珊瑚", "银行", "利息", "证券"),
        }
        pool = [
            line
            for line in self.demo_flow.get("intel_lines", [])
            if any(keyword in line for keyword in district_keywords.get(district, (district,)))
        ]
        if not pool:
            pool = list(self.demo_flow.get("intel_lines", []))
        if speaker and str(speaker.get("role", "")) == "记者":
            pool.extend([line for line in self.demo_flow.get("intel_lines", []) if any(token in line for token in ["记者", "旧账", "话题", "公告"])])
        line = self.random.choice(pool) if pool else f"{district} 今天的风向发紧，先动的是消息。"
        goods_delta: dict[str, float] = {}
        stocks_delta: dict[str, float] = {}
        macro_delta: dict[str, float] = {}
        family_delta: dict[str, float] = {}
        tags = ["传闻", district]

        def bump(bucket: dict[str, float], key: str, amount: float) -> None:
            bucket[key] = round(float(bucket.get(key, 0.0)) + amount, 3)

        if any(token in line for token in ["港口", "龟甲船运", "慢工", "船", "物流"]):
            bump(stocks_delta, "龟甲船运", -0.09)
            bump(goods_delta, "罐头", 0.05)
            bump(goods_delta, "煤", 0.04)
            bump(macro_delta, "worker_unrest", 2.0)
            bump(family_delta, "龟甲船坞", -0.06)
            tags.extend(["港口", "物流"])
        if any(token in line for token in ["工厂", "龟甲船坞", "事故", "工资", "煤"]):
            bump(stocks_delta, "龟甲船运", -0.1)
            bump(goods_delta, "煤", 0.1)
            bump(macro_delta, "worker_unrest", 2.0)
            bump(family_delta, "龟甲船坞", -0.05)
            tags.extend(["工厂", "工资"])
        if any(token in line for token in ["海藻家族", "海藻食业", "面包", "囤货", "市集", "口粮"]):
            bump(stocks_delta, "海藻食业", 0.07)
            bump(goods_delta, "面包", 0.08)
            bump(macro_delta, "worker_unrest", 2.2)
            bump(family_delta, "海藻家族", 0.08)
            tags.extend(["粮价", "民生"])
        if any(token in line for token in ["珊瑚银行", "珊瑚金控", "利息", "银行", "证券", "短债"]):
            bump(stocks_delta, "珊瑚金控", 0.11)
            bump(macro_delta, "media_sentiment", 5.0)
            bump(macro_delta, "interest_rate", 0.12)
            bump(macro_delta, "economy_heat", -1.0)
            bump(family_delta, "珊瑚银行", 0.08)
            tags.extend(["金融", "利率"])
        if any(token in line for token in ["记者", "旧账", "话题", "公告", "全镇"]):
            bump(macro_delta, "media_sentiment", 4.0)
            bump(macro_delta, "worker_unrest", 1.0)
            tags.extend(["媒体", "舆论"])

        if not goods_delta and not stocks_delta:
            fallback_good, fallback_stock = {
                "贫民街": ("面包", "海藻食业"),
                "港口": ("罐头", "龟甲船运"),
                "工厂区": ("煤", "龟甲船运"),
                "交易所": ("面包", "珊瑚金控"),
            }.get(district, ("面包", "海藻食业"))
            bump(goods_delta, fallback_good, 0.05)
            bump(stocks_delta, fallback_stock, 0.04)

        if speaker:
            role = str(speaker.get("role", ""))
            family = str(speaker.get("family_affiliation", ""))
            if role in {"记者", "投机者"}:
                bump(stocks_delta, "珊瑚金控", 0.03)
                tags.append("人物")
            if role in {"工人", "临时工", "工会领袖"}:
                bump(macro_delta, "worker_unrest", 1.0)
            if family and family != "无":
                bump(family_delta, family, 0.04)
                tags.append(family)

        unique_tags = list(dict.fromkeys(tags))
        return {
            "id": f"rumor_{self.state['day']}_{len(self.state.get('rumor_log', []))}_{self.random.randint(100, 999)}",
            "district": district,
            "source": source,
            "speaker_id": str(speaker.get("id", "")) if speaker else "",
            "speaker_name": str(speaker.get("name", "")) if speaker else "",
            "title": f"{district} 风声",
            "line": line,
            "body": f"{source} 说：{line}",
            "tags": unique_tags,
            "scope": "city" if any(tag in unique_tags for tag in ["金融", "楼市", "媒体"]) else "district",
            "goods_delta": goods_delta,
            "stocks_delta": stocks_delta,
            "macro_delta": macro_delta,
            "family_delta": family_delta,
        }

    def _world_tick(self) -> int:
        return max(0, (int(self.state.get("day", 1)) - 1) * 24 * 60 + int(self.state.get("clock_minutes", 0)))

    def _packet_primary_target(self, packet: dict[str, Any]) -> tuple[str, str, float]:
        for bucket_name in ("stocks_delta", "goods_delta", "family_delta", "macro_delta"):
            bucket = packet.get(bucket_name, {})
            if not isinstance(bucket, dict) or not bucket:
                continue
            key, value = max(bucket.items(), key=lambda item: abs(float(item[1])))
            return bucket_name, str(key), float(value)
        return "", "", 0.0

    def _topic_kind_from_packet(self, packet: dict[str, Any]) -> str:
        explicit = str(packet.get("topic_kind", "")).strip()
        if explicit:
            return explicit
        tags = {str(tag) for tag in packet.get("tags", [])}
        macro_delta = {str(key): float(value) for key, value in dict(packet.get("macro_delta", {})).items()}
        if "interest_rate" in macro_delta or "金融" in tags or "银行" in tags:
            return "finance"
        if packet.get("family_delta") and "家族" in tags:
            return "family"
        if packet.get("stocks_delta") and ("股票" in tags or str(packet.get("district", "")) == "交易所"):
            return "asset"
        if "worker_unrest" in macro_delta or {"工厂", "港口", "工作"} & tags:
            return "labor"
        if packet.get("goods_delta"):
            return "supply"
        if "媒体" in tags or "舆论" in tags:
            return "media"
        if "传闻" in tags:
            return "rumor"
        return "public"

    def _topic_stance_from_packet(self, packet: dict[str, Any]) -> str:
        stocks_delta = {str(key): float(value) for key, value in dict(packet.get("stocks_delta", {})).items()}
        goods_delta = {str(key): float(value) for key, value in dict(packet.get("goods_delta", {})).items()}
        family_delta = {str(key): float(value) for key, value in dict(packet.get("family_delta", {})).items()}
        macro_delta = {str(key): float(value) for key, value in dict(packet.get("macro_delta", {})).items()}
        if float(macro_delta.get("worker_unrest", 0.0)) > 0.0:
            return "mobilizing"
        if float(macro_delta.get("interest_rate", 0.0)) > 0.0:
            return "tightening"
        if any(delta < 0.0 for delta in stocks_delta.values()) or any(delta < 0.0 for delta in family_delta.values()):
            return "alarm"
        if any(delta > 0.0 for delta in goods_delta.values()):
            return "scarcity"
        if any(delta > 0.0 for delta in stocks_delta.values()) or any(delta > 0.0 for delta in family_delta.values()):
            return "support"
        return "uncertain"

    def _topic_credibility_hint(self, packet: dict[str, Any]) -> float:
        score = 0.42
        source = str(packet.get("source", ""))
        speaker_name = str(packet.get("speaker_name", ""))
        tags = {str(tag) for tag in packet.get("tags", [])}
        if "街头耳报" in source:
            score += 0.05
        if speaker_name:
            speaker = self._find_npc(str(packet.get("speaker_id", ""))) or self._find_npc(speaker_name)
            if speaker:
                role = str(speaker.get("role", ""))
                if role in {"记者", "代理人", "银行经理", "老板"}:
                    score += 0.15
                elif role in {"工会领袖", "店主"}:
                    score += 0.09
                elif role in {"工人", "临时工"}:
                    score += 0.04
        if "金融" in tags or "公司" in tags:
            score += 0.05
        if "围观" in source or "恐慌" in source:
            score -= 0.08
        return round(max(0.12, min(0.92, score)), 3)

    def _topic_label_from_packet(self, packet: dict[str, Any], kind: str, target_name: str) -> str:
        district = str(packet.get("district", "街区"))
        if kind == "asset" and target_name:
            return f"{target_name}的风向"
        if kind == "family" and target_name:
            return f"{target_name}的动作"
        if kind == "finance":
            return f"{district}的利息和信用"
        if kind == "labor":
            return f"{district}的工钱与班次"
        if kind == "supply" and target_name:
            return f"{target_name}的供给风声"
        if kind == "media":
            return f"{district}的舆论风向"
        title = str(packet.get("title", "")).strip()
        if title:
            return title
        return f"{district} 的街头议题"

    def _topic_signature_from_packet(self, packet: dict[str, Any], kind: str, target_name: str) -> str:
        explicit_topic_id = str(packet.get("topic_id", "")).strip()
        if explicit_topic_id:
            return explicit_topic_id
        district = str(packet.get("district", "")).strip() or "city"
        focus = target_name.strip() or str(packet.get("scope", "district"))
        focus = focus.replace(" ", "_")
        return f"topic_{kind}_{district}_{focus}"

    def _merge_delta_map(self, existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, float]:
        merged = {str(key): float(value) for key, value in dict(existing).items()}
        for key, value in dict(incoming).items():
            current = float(merged.get(str(key), 0.0))
            merged[str(key)] = round(max(-0.45, min(0.45, current * 0.55 + float(value) * 0.95)), 3)
        return merged

    def _record_topic_from_packet(self, packet: dict[str, Any], intensity: float) -> dict[str, Any]:
        kind = self._topic_kind_from_packet(packet)
        target_bucket, target_name, _target_value = self._packet_primary_target(packet)
        topic_id = self._topic_signature_from_packet(packet, kind, target_name)
        label = self._topic_label_from_packet(packet, kind, target_name)
        tick = self._world_tick()
        topic_registry = list(self.state.get("topic_registry", []))
        topic = next((row for row in topic_registry if str(row.get("id", "")) == topic_id), None)
        source = str(packet.get("source", "")).strip() or "街头风声"
        summary = str(packet.get("line", "")).strip() or str(packet.get("body", "")).strip() or label
        speaker_id = str(packet.get("speaker_id", "")).strip()
        credibility = self._topic_credibility_hint(packet)
        if topic is None:
            topic = {
                "id": topic_id,
                "signature": topic_id,
                "kind": kind,
                "status": "emerging",
                "scope": str(packet.get("scope", "district")) or "district",
                "district": str(packet.get("district", "")),
                "label": label,
                "summary": summary,
                "stance": self._topic_stance_from_packet(packet),
                "target_bucket": target_bucket,
                "target_name": target_name,
                "origin": source,
                "latest_source": source,
                "heat": round(max(0.12, min(1.0, 0.28 + intensity * 0.38)), 3),
                "intensity": round(max(0.05, min(1.0, intensity)), 3),
                "credibility": credibility,
                "novelty": round(max(0.15, min(1.0, 0.34 + intensity * 0.42)), 3),
                "suppression_level": 0.08,
                "mention_count": 1,
                "spread_count": 1,
                "source_count": 1,
                "sources": [source],
                "speaker_ids": [speaker_id] if speaker_id else [],
                "tags": list(dict.fromkeys([str(tag) for tag in packet.get("tags", [])])),
                "recent_lines": [summary],
                "goods_delta": {str(key): float(value) for key, value in dict(packet.get("goods_delta", {})).items()},
                "stocks_delta": {str(key): float(value) for key, value in dict(packet.get("stocks_delta", {})).items()},
                "family_delta": {str(key): float(value) for key, value in dict(packet.get("family_delta", {})).items()},
                "macro_delta": {str(key): float(value) for key, value in dict(packet.get("macro_delta", {})).items()},
                "first_seen_day": int(self.state.get("day", 1)),
                "first_seen_minute": int(self.state.get("clock_minutes", 0)),
                "last_seen_day": int(self.state.get("day", 1)),
                "last_seen_minute": int(self.state.get("clock_minutes", 0)),
                "first_seen_tick": tick,
                "last_seen_tick": tick,
            }
            topic_registry.append(topic)
        else:
            topic["status"] = "active"
            topic["scope"] = str(packet.get("scope", topic.get("scope", "district"))) or "district"
            topic["district"] = str(packet.get("district", topic.get("district", "")))
            topic["label"] = str(topic.get("label", "")) or label
            topic["summary"] = summary
            topic["stance"] = self._topic_stance_from_packet(packet)
            topic["latest_source"] = source
            topic["target_bucket"] = target_bucket or str(topic.get("target_bucket", ""))
            topic["target_name"] = target_name or str(topic.get("target_name", ""))
            topic["heat"] = round(max(0.06, min(1.0, float(topic.get("heat", 0.0)) * 0.68 + 0.26 * intensity + 0.04)), 3)
            topic["intensity"] = round(max(0.05, min(1.0, float(topic.get("intensity", 0.0)) * 0.55 + intensity * 0.75)), 3)
            topic["credibility"] = round(max(0.1, min(0.96, float(topic.get("credibility", 0.4)) * 0.74 + credibility * 0.26)), 3)
            topic["novelty"] = round(max(0.04, min(1.0, float(topic.get("novelty", 0.0)) * 0.58 + 0.18 * intensity + 0.06)), 3)
            topic["suppression_level"] = round(max(0.0, min(1.0, float(topic.get("suppression_level", 0.08)) * 0.92)), 3)
            topic["mention_count"] = int(topic.get("mention_count", 0)) + 1
            topic["spread_count"] = int(topic.get("spread_count", 0)) + max(1, int(round(intensity * 2)))
            sources = [str(value) for value in topic.get("sources", []) if str(value).strip()]
            if source and source not in sources:
                sources.append(source)
            topic["sources"] = sources[:6]
            topic["source_count"] = len(topic["sources"])
            speaker_ids = [str(value) for value in topic.get("speaker_ids", []) if str(value).strip()]
            if speaker_id and speaker_id not in speaker_ids:
                speaker_ids.append(speaker_id)
            topic["speaker_ids"] = speaker_ids[:8]
            topic["tags"] = list(dict.fromkeys([*list(topic.get("tags", [])), *[str(tag) for tag in packet.get("tags", [])]]))[:12]
            topic["recent_lines"] = [summary, *[str(value) for value in topic.get("recent_lines", []) if str(value).strip() and str(value) != summary]][:4]
            topic["goods_delta"] = self._merge_delta_map(topic.get("goods_delta", {}), packet.get("goods_delta", {}))
            topic["stocks_delta"] = self._merge_delta_map(topic.get("stocks_delta", {}), packet.get("stocks_delta", {}))
            topic["family_delta"] = self._merge_delta_map(topic.get("family_delta", {}), packet.get("family_delta", {}))
            topic["macro_delta"] = self._merge_delta_map(topic.get("macro_delta", {}), packet.get("macro_delta", {}))
            topic["last_seen_day"] = int(self.state.get("day", 1))
            topic["last_seen_minute"] = int(self.state.get("clock_minutes", 0))
            topic["last_seen_tick"] = tick
        if float(topic.get("heat", 0.0)) >= 0.62:
            topic["status"] = "active"
        elif int(topic.get("mention_count", 0)) >= 2:
            topic["status"] = "warming"
        else:
            topic["status"] = "emerging"
        topic_registry.sort(key=lambda row: (float(row.get("heat", 0.0)), int(row.get("mention_count", 0))), reverse=True)
        self.state["topic_registry"] = topic_registry[:24]
        return copy.deepcopy(topic)

    def _decay_topic_registry(self) -> None:
        current_tick = self._world_tick()
        last_tick = int(self.state.get("topic_decay_tick", current_tick))
        delta = max(0, current_tick - last_tick)
        if delta <= 0:
            return
        heat_factor = pow(0.9988, delta)
        novelty_factor = pow(0.9982, delta)
        keep_rows: list[dict[str, Any]] = []
        for topic in self.state.get("topic_registry", []):
            row = copy.deepcopy(topic)
            row["heat"] = round(max(0.0, min(1.0, float(row.get("heat", 0.0)) * heat_factor)), 3)
            row["novelty"] = round(max(0.0, min(1.0, float(row.get("novelty", 0.0)) * novelty_factor)), 3)
            age = current_tick - int(row.get("last_seen_tick", current_tick))
            if float(row.get("suppression_level", 0.0)) > 0.0:
                row["suppression_level"] = round(max(0.0, min(1.0, float(row.get("suppression_level", 0.0)) * 0.9975)), 3)
            if float(row.get("heat", 0.0)) >= 0.58:
                row["status"] = "active"
            elif float(row.get("heat", 0.0)) >= 0.22:
                row["status"] = "cooling"
            else:
                row["status"] = "dormant"
            if age > 3 * 24 * 60 and float(row.get("heat", 0.0)) < 0.08:
                continue
            keep_rows.append(row)
        keep_rows.sort(key=lambda row: (float(row.get("heat", 0.0)), int(row.get("mention_count", 0))), reverse=True)
        self.state["topic_registry"] = keep_rows[:24]
        self.state["topic_decay_tick"] = current_tick

    def _topic_to_talk_topic(self, topic: dict[str, Any]) -> dict[str, Any]:
        district_name = str(topic.get("district", ""))
        scope = str(topic.get("scope", "district"))
        if scope == "city":
            npc_ids: list[str] = []
        else:
            npc_ids = [str(npc.get("id", "")) for npc in self.state.get("npcs", []) if str(npc.get("district", "")) == district_name]
        kind = str(topic.get("kind", "rumor"))
        approaches = ["cautious", "friendly", "hardball"]
        if kind in {"finance", "asset"}:
            approaches = ["cautious", "hardball", "friendly"]
        elif kind in {"labor", "supply"}:
            approaches = ["friendly", "cautious", "hardball"]
        return {
            "id": str(topic.get("id", "")),
            "kind": kind,
            "district": district_name,
            "label": str(topic.get("label", "")),
            "summary": str(topic.get("summary", "")),
            "heat": round(float(topic.get("heat", 0.0)), 3),
            "credibility": round(float(topic.get("credibility", 0.0)), 3),
            "novelty": round(float(topic.get("novelty", 0.0)), 3),
            "spread_count": int(topic.get("spread_count", 0)),
            "status": str(topic.get("status", "")),
            "tags": list(topic.get("tags", [])),
            "npc_ids": npc_ids,
            "approaches": approaches,
            "impacts": {
                "goods": copy.deepcopy(topic.get("goods_delta", {})),
                "stocks": copy.deepcopy(topic.get("stocks_delta", {})),
                "macro": copy.deepcopy(topic.get("macro_delta", {})),
                "families": copy.deepcopy(topic.get("family_delta", {})),
            },
            "source_topic_id": str(topic.get("id", "")),
        }

    def _active_public_topics(self, limit: int = 8, district_name: str = "") -> list[dict[str, Any]]:
        topics: list[dict[str, Any]] = []
        for topic in self.state.get("topic_registry", []):
            district = str(topic.get("district", ""))
            scope = str(topic.get("scope", "district"))
            if district_name and scope != "city" and district not in {"", district_name}:
                continue
            if float(topic.get("heat", 0.0)) < 0.12:
                continue
            topics.append(self._topic_to_talk_topic(topic))
        topics.sort(key=lambda item: (float(item.get("heat", 0.0)), float(item.get("credibility", 0.0))), reverse=True)
        return topics[:limit]

    def _npc_topic_digest(self, npc: dict[str, Any]) -> str:
        district_name = str(npc.get("district", ""))
        topic_pool = self._active_public_topics(limit=2, district_name=district_name)
        for topic in self._talk_topics_for_npc(str(npc.get("id", "")), district_name):
            if any(str(existing.get("id", "")) == str(topic.get("id", "")) for existing in topic_pool):
                continue
            topic_pool.append(copy.deepcopy(topic))
            if len(topic_pool) >= 4:
                break
        pieces: list[str] = []
        for topic in topic_pool[:3]:
            label = str(topic.get("label", "")).strip()
            if not label:
                continue
            heat = int(round(float(topic.get("heat", 0.0)) * 100))
            credibility = int(round(float(topic.get("credibility", topic.get("confidence", 0.5))) * 100))
            spread = int(topic.get("spread_count", max(1, len(topic.get("npc_ids", [])))))
            pieces.append(f"{label}(热{heat}|信{credibility}|扩{spread})")
        return "；".join(pieces) if pieces else "暂无成形议题"

    def _coerce_topic_action_mode(self, value: str, npc: dict[str, Any], topic: dict[str, Any]) -> str:
        normalized = value.strip().lower()
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
        if normalized in mapping:
            return mapping[normalized]
        role = str(npc.get("role", ""))
        family = str(npc.get("family_affiliation", ""))
        topic_kind = str(topic.get("kind", ""))
        tags = {str(tag) for tag in topic.get("tags", [])}
        if role in {"记者", "工会领袖"}:
            return "amplify" if topic_kind in {"labor", "media", "family", "public"} else "share"
        if role in {"投机者", "银行经理"}:
            return "amplify" if topic_kind in {"asset", "finance"} else "question"
        if role in {"老板", "代理人"} and family and family in tags:
            return "deny" if topic_kind in {"labor", "supply", "family"} else "share"
        if float(npc.get("rumor_susceptibility", 0.4)) >= 0.62 or float(npc.get("fear", 0.0)) >= 58.0:
            return "share"
        if float(npc.get("info_reliability", 0.5)) >= 0.7:
            return "question"
        return "silence"

    def _coerce_norm_action_mode(self, value: str, topic_action_mode: str, topic: dict[str, Any]) -> str:
        normalized = value.strip().lower()
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
        if normalized in mapping:
            return mapping[normalized]
        if topic_action_mode in {"share", "amplify"}:
            return "reinforce"
        if topic_action_mode in {"question", "deny"}:
            return "contest"
        if topic and str(topic.get("kind", "")) in {"labor", "supply", "finance", "asset"}:
            return "seed"
        return "ignore"

    def _coerce_npc_topic_action(self, raw: Any, npc: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        mode = self._coerce_topic_action_mode(str(payload.get("mode", "")), npc, topic)
        topic_id = str(payload.get("topic_id", "")).strip() or str(topic.get("source_topic_id", topic.get("id", "")))
        base_intensity = 0.56 if mode == "share" else 0.68 if mode == "amplify" else 0.52 if mode == "question" else 0.58 if mode == "deny" else 0.18
        intensity = float(payload.get("intensity", base_intensity))
        note = str(payload.get("note", "")).strip()
        if not topic_id and mode == "silence":
            return {"mode": "silence", "topic_id": "", "intensity": 0.18, "note": note}
        return {
            "mode": mode,
            "topic_id": topic_id,
            "intensity": round(max(0.0, min(1.0, intensity)), 3),
            "note": note,
        }

    def _coerce_npc_norm_action(self, raw: Any, npc: dict[str, Any], topic: dict[str, Any], topic_action: dict[str, Any]) -> dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        topic_action_mode = str(topic_action.get("mode", "silence"))
        mode = self._coerce_norm_action_mode(str(payload.get("mode", "")), topic_action_mode, topic)
        norm_id = str(payload.get("norm_id", "")).strip()
        text = str(payload.get("text", "")).strip()
        base_intensity = 0.58 if mode == "reinforce" else 0.54 if mode == "contest" else 0.5 if mode == "seed" else 0.16
        intensity = float(payload.get("intensity", topic_action.get("intensity", base_intensity)))
        note = str(payload.get("note", "")).strip()
        return {
            "mode": mode,
            "norm_id": norm_id,
            "text": text,
            "intensity": round(max(0.0, min(1.0, intensity)), 3),
            "note": note,
        }

    def _topic_row_by_id(self, topic_id: str) -> dict[str, Any] | None:
        needle = str(topic_id).strip()
        if not needle:
            return None
        for topic in self.state.get("topic_registry", []):
            if str(topic.get("id", "")) == needle:
                return topic
        return None

    def _materialize_topic_for_action(self, npc: dict[str, Any], topic: dict[str, Any], topic_action: dict[str, Any]) -> dict[str, Any] | None:
        topic_id = str(topic_action.get("topic_id", "")).strip()
        existing = self._topic_row_by_id(topic_id)
        if existing:
            return existing
        if not topic:
            return None
        packet = self._build_intel_packet_from_topic(topic, npc, str(topic.get("district", npc.get("district", ""))))
        packet["topic_id"] = topic_id or str(topic.get("source_topic_id", topic.get("id", "")))
        packet["topic_kind"] = str(topic.get("kind", ""))
        intensity = max(0.18, float(topic_action.get("intensity", 0.2)) * 0.55)
        recorded = self._record_topic_from_packet(packet, intensity)
        return self._topic_row_by_id(str(recorded.get("id", "")))

    def _topic_action_pressure(self, npc: dict[str, Any]) -> float:
        class_name = str(npc.get("class", ""))
        role = str(npc.get("role", ""))
        power = 0.03
        if class_name == "特殊角色":
            power += 0.05
        elif class_name == "关键角色":
            power += 0.03
        elif class_name == "中层":
            power += 0.015
        if role in {"记者", "代理人", "工会领袖"}:
            power += 0.02
        if role in {"银行经理", "投机者"}:
            power += 0.018
        return power

    def _apply_topic_action(self, npc: dict[str, Any], topic: dict[str, Any], topic_action: dict[str, Any]) -> dict[str, Any] | None:
        mode = str(topic_action.get("mode", "silence"))
        topic_row = self._materialize_topic_for_action(npc, topic, topic_action)
        if not topic_row:
            return None
        intensity = float(topic_action.get("intensity", 0.2))
        pressure = self._topic_action_pressure(npc)
        reliability = float(npc.get("info_reliability", 0.5))
        rumor_pull = float(npc.get("rumor_susceptibility", 0.4))
        controversy = float(topic_row.get("controversy", 0.0))
        if mode == "share":
            topic_row["heat"] = round(min(1.0, float(topic_row.get("heat", 0.0)) + 0.03 + intensity * (0.05 + pressure)), 3)
            topic_row["credibility"] = round(min(0.96, float(topic_row.get("credibility", 0.4)) + reliability * 0.02), 3)
            topic_row["spread_count"] = int(topic_row.get("spread_count", 0)) + 1
        elif mode == "amplify":
            topic_row["heat"] = round(min(1.0, float(topic_row.get("heat", 0.0)) + 0.05 + intensity * (0.07 + pressure)), 3)
            topic_row["novelty"] = round(min(1.0, float(topic_row.get("novelty", 0.0)) + 0.02 + intensity * 0.04), 3)
            topic_row["spread_count"] = int(topic_row.get("spread_count", 0)) + 2
            controversy += 0.03 + intensity * 0.04
        elif mode == "question":
            topic_row["heat"] = round(min(1.0, float(topic_row.get("heat", 0.0)) + 0.01 + intensity * 0.03), 3)
            topic_row["credibility"] = round(max(0.08, float(topic_row.get("credibility", 0.4)) - max(0.01, reliability * 0.03)), 3)
            controversy += 0.05 + intensity * 0.05
        elif mode == "deny":
            topic_row["heat"] = round(max(0.02, float(topic_row.get("heat", 0.0)) - 0.01 + intensity * 0.01), 3)
            topic_row["credibility"] = round(max(0.08, float(topic_row.get("credibility", 0.4)) - max(0.012, reliability * 0.025)), 3)
            topic_row["suppression_level"] = round(min(1.0, float(topic_row.get("suppression_level", 0.0)) + 0.03 + pressure * 0.3), 3)
            controversy += 0.04 + intensity * 0.03
        else:
            topic_row["heat"] = round(max(0.0, float(topic_row.get("heat", 0.0)) - 0.004), 3)
            topic_row["suppression_level"] = round(min(1.0, float(topic_row.get("suppression_level", 0.0)) + max(0.0, pressure - 0.03) * 0.15), 3)
        topic_row["controversy"] = round(max(0.0, min(1.0, controversy)), 3)
        topic_row["mention_count"] = int(topic_row.get("mention_count", 0)) + (0 if mode == "silence" else 1)
        topic_row["support_count"] = int(topic_row.get("support_count", 0)) + (1 if mode in {"share", "amplify"} else 0)
        topic_row["question_count"] = int(topic_row.get("question_count", 0)) + (1 if mode == "question" else 0)
        topic_row["deny_count"] = int(topic_row.get("deny_count", 0)) + (1 if mode == "deny" else 0)
        topic_row["silence_count"] = int(topic_row.get("silence_count", 0)) + (1 if mode == "silence" else 0)
        topic_row["last_actor_id"] = str(npc.get("id", ""))
        topic_row["last_action"] = mode
        topic_row["last_seen_tick"] = self._world_tick()
        topic_row["last_seen_day"] = int(self.state.get("day", 1))
        topic_row["last_seen_minute"] = int(self.state.get("clock_minutes", 0))
        if mode in {"share", "amplify"}:
            self._bump_district_signal(str(topic_row.get("district", npc.get("district", ""))), "gossip", 0.03 + intensity * 0.04)
        elif mode in {"question", "deny"}:
            self._bump_district_signal(str(topic_row.get("district", npc.get("district", ""))), "fear", 0.01 + rumor_pull * 0.03)
        return copy.deepcopy(topic_row)

    def _norm_seed_from_topic(self, topic: dict[str, Any], text_hint: str = "") -> dict[str, Any]:
        district = str(topic.get("district", "")) or "全城"
        kind = str(topic.get("kind", "public"))
        text = text_hint.strip()
        category = kind
        tags = [str(tag) for tag in topic.get("tags", [])]
        target_groups: list[str] = []
        if not text:
            if kind == "labor":
                text = "降薪不能忍"
                category = "labor"
                target_groups = ["工人", "临时工", "工会"]
            elif kind == "supply":
                text = "先保住口粮"
                category = "supply"
                target_groups = ["居民", "店主", "工人"]
            elif kind in {"finance", "asset"}:
                text = "行情乱时先缩仓"
                category = "finance"
                target_groups = ["投机者", "银行经理", "店主"]
            elif kind in {"media", "family", "public"}:
                text = "大事先看谁在放风"
                category = "media"
                target_groups = ["记者", "代理人", "居民"]
            else:
                text = f"{district}的人得先顾自己"
                target_groups = ["居民"]
        stable_suffix = sum(ord(ch) for ch in f"{category}:{district}:{text}") % 10000
        norm_id = f"norm_{category}_{district}_{stable_suffix}"
        return {
            "id": norm_id,
            "text": text,
            "category": category,
            "district": district,
            "scope": "city" if str(topic.get("scope", "district")) == "city" else "district",
            "tags": list(dict.fromkeys(tags + [category])),
            "target_groups": target_groups,
        }

    def _norm_row_by_id(self, norm_id: str) -> dict[str, Any] | None:
        needle = str(norm_id).strip()
        if not needle:
            return None
        for norm in self.state.get("norm_registry", []):
            if str(norm.get("id", "")) == needle:
                return norm
        return None

    def _record_norm_action(self, npc: dict[str, Any], topic: dict[str, Any] | None, topic_action: dict[str, Any], norm_action: dict[str, Any]) -> dict[str, Any] | None:
        mode = str(norm_action.get("mode", "ignore"))
        if mode == "ignore":
            return None
        seed = self._norm_seed_from_topic(topic or {}, str(norm_action.get("text", "")))
        norm_id = str(norm_action.get("norm_id", "")).strip() or str(seed.get("id", ""))
        norm = self._norm_row_by_id(norm_id)
        intensity = float(norm_action.get("intensity", topic_action.get("intensity", 0.4)))
        conformity = max(0.12, min(0.92, float(npc.get("moral_floor", 0.4)) + float(npc.get("loyalty", 0.0)) / 220.0))
        if norm is None:
            if mode not in {"seed", "reinforce", "contest"}:
                return None
            norm = {
                "id": norm_id,
                "text": str(seed.get("text", "")),
                "category": str(seed.get("category", "public")),
                "district": str(seed.get("district", topic.get("district", "") if topic else "")),
                "scope": str(seed.get("scope", "district")),
                "support": round(0.32 + intensity * 0.16 + conformity * 0.08, 3),
                "strength": round(0.28 + intensity * 0.18, 3),
                "violation_cost": round(0.16 + conformity * 0.24, 3),
                "pressure": round(0.18 + intensity * 0.14, 3),
                "status": "warming",
                "origin": str(norm_action.get("note", "")) or str(npc.get("name", "")) or "seed",
                "source_topic_ids": [str(topic.get("id", ""))] if topic else [],
                "tags": list(seed.get("tags", [])),
                "target_groups": list(seed.get("target_groups", [])),
                "mention_count": 1,
                "reinforce_count": 1 if mode in {"seed", "reinforce"} else 0,
                "contest_count": 1 if mode == "contest" else 0,
                "seed_count": 1,
                "last_tick": self._world_tick(),
            }
            self.state.setdefault("norm_registry", []).append(norm)
        if topic and str(topic.get("id", "")) and str(topic.get("id", "")) not in [str(value) for value in norm.get("source_topic_ids", [])]:
            norm["source_topic_ids"] = [*list(norm.get("source_topic_ids", [])), str(topic.get("id", ""))][:6]
        if mode in {"seed", "reinforce"}:
            norm["support"] = round(min(0.98, float(norm.get("support", 0.3)) + 0.03 + intensity * 0.04 + conformity * 0.02), 3)
            norm["strength"] = round(min(0.98, float(norm.get("strength", 0.2)) + 0.03 + intensity * 0.05), 3)
            norm["pressure"] = round(min(0.98, float(norm.get("pressure", 0.2)) + 0.02 + intensity * 0.03), 3)
            norm["reinforce_count"] = int(norm.get("reinforce_count", 0)) + 1
        elif mode == "contest":
            norm["support"] = round(max(0.04, float(norm.get("support", 0.3)) - 0.02 - intensity * 0.04), 3)
            norm["strength"] = round(max(0.04, float(norm.get("strength", 0.2)) - 0.01 - intensity * 0.03), 3)
            norm["pressure"] = round(max(0.02, float(norm.get("pressure", 0.2)) - 0.005 + intensity * 0.01), 3)
            norm["contest_count"] = int(norm.get("contest_count", 0)) + 1
        norm["mention_count"] = int(norm.get("mention_count", 0)) + 1
        norm["violation_cost"] = round(max(0.08, min(0.98, float(norm.get("violation_cost", 0.2)) * 0.92 + float(norm.get("strength", 0.2)) * 0.12)), 3)
        norm["last_tick"] = self._world_tick()
        if float(norm.get("support", 0.0)) >= 0.62 and float(norm.get("strength", 0.0)) >= 0.46:
            norm["status"] = "active"
        elif float(norm.get("support", 0.0)) >= 0.38:
            norm["status"] = "warming"
        else:
            norm["status"] = "contested"
        self.state["norm_registry"].sort(key=lambda row: (float(row.get("strength", 0.0)), float(row.get("support", 0.0))), reverse=True)
        self.state["norm_registry"] = self.state["norm_registry"][:24]
        return copy.deepcopy(norm)

    def _decay_norm_registry(self) -> None:
        current_tick = self._world_tick()
        last_tick = int(self.state.get("norm_decay_tick", current_tick))
        delta = max(0, current_tick - last_tick)
        if delta <= 0:
            return
        decay = pow(0.999, delta)
        keep_rows: list[dict[str, Any]] = []
        for norm in self.state.get("norm_registry", []):
            row = copy.deepcopy(norm)
            row["support"] = round(max(0.0, min(1.0, float(row.get("support", 0.0)) * decay)), 3)
            row["strength"] = round(max(0.0, min(1.0, float(row.get("strength", 0.0)) * decay)), 3)
            row["pressure"] = round(max(0.0, min(1.0, float(row.get("pressure", 0.0)) * decay)), 3)
            if float(row.get("support", 0.0)) >= 0.58 and float(row.get("strength", 0.0)) >= 0.42:
                row["status"] = "active"
            elif float(row.get("support", 0.0)) >= 0.28:
                row["status"] = "warming"
            else:
                row["status"] = "dormant"
            if current_tick - int(row.get("last_tick", current_tick)) > 4 * 24 * 60 and float(row.get("strength", 0.0)) < 0.08:
                continue
            keep_rows.append(row)
        keep_rows.sort(key=lambda row: (float(row.get("strength", 0.0)), float(row.get("support", 0.0))), reverse=True)
        self.state["norm_registry"] = keep_rows[:24]
        self.state["norm_decay_tick"] = current_tick

    def _active_norms_view(self, limit: int = 8, district_name: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for norm in self.state.get("norm_registry", []):
            district = str(norm.get("district", ""))
            scope = str(norm.get("scope", "district"))
            if district_name and scope != "city" and district not in {"", district_name}:
                continue
            if float(norm.get("strength", 0.0)) < 0.14 and float(norm.get("support", 0.0)) < 0.22:
                continue
            rows.append(
                {
                    "id": str(norm.get("id", "")),
                    "text": str(norm.get("text", "")),
                    "category": str(norm.get("category", "")),
                    "district": district,
                    "scope": scope,
                    "support": round(float(norm.get("support", 0.0)), 3),
                    "strength": round(float(norm.get("strength", 0.0)), 3),
                    "violation_cost": round(float(norm.get("violation_cost", 0.0)), 3),
                    "status": str(norm.get("status", "")),
                    "pressure": round(float(norm.get("pressure", 0.0)), 3),
                    "source_topic_ids": list(norm.get("source_topic_ids", [])),
                    "tags": list(norm.get("tags", [])),
                }
            )
        rows.sort(key=lambda row: (float(row.get("strength", 0.0)), float(row.get("support", 0.0))), reverse=True)
        return rows[:limit]

    def _npc_norm_digest(self, npc: dict[str, Any]) -> str:
        district_name = str(npc.get("district", ""))
        norms = self._active_norms_view(limit=3, district_name=district_name)
        pieces: list[str] = []
        for norm in norms[:2]:
            text = str(norm.get("text", "")).strip()
            if not text:
                continue
            support = int(round(float(norm.get("support", 0.0)) * 100))
            strength = int(round(float(norm.get("strength", 0.0)) * 100))
            pieces.append(f"{text}(支{support}|强{strength})")
        return "；".join(pieces) if pieces else "暂无成形规范"

    def _collective_row_by_id(self, action_id: str) -> dict[str, Any] | None:
        needle = str(action_id).strip()
        if not needle:
            return None
        for row in self.state.get("collective_action_registry", []):
            if str(row.get("id", "")) == needle:
                return row
        return None

    @staticmethod
    def _collective_kind_rank(kind: str) -> int:
        return {
            "party": 1,
            "meeting": 2,
            "rally": 3,
            "strike": 4,
        }.get(str(kind), 0)

    @staticmethod
    def _collective_stage_rank(stage: str) -> int:
        return {
            "active": 4,
            "committing": 3,
            "signaling": 2,
            "forming": 1,
            "cooling": 0,
            "dormant": -1,
        }.get(str(stage), 0)

    @staticmethod
    def _collective_stage_label(stage: str) -> str:
        return {
            "active": "到场",
            "committing": "承诺",
            "signaling": "表态",
            "forming": "听说",
            "cooling": "降温",
            "dormant": "沉底",
        }.get(str(stage), "听说")

    @staticmethod
    def _dedupe_id_list(values: Any, limit: int = 24) -> list[str]:
        rows: list[str] = []
        for value in values if isinstance(values, list) else []:
            text = str(value).strip()
            if text and text not in rows:
                rows.append(text)
            if len(rows) >= limit:
                break
        return rows

    def _collective_norm_for_topic(self, topic: dict[str, Any]) -> dict[str, Any] | None:
        topic_id = str(topic.get("id", ""))
        topic_kind = str(topic.get("kind", ""))
        district = str(topic.get("district", ""))
        matches: list[tuple[int, float, float, dict[str, Any]]] = []
        for norm in self.state.get("norm_registry", []):
            norm_district = str(norm.get("district", ""))
            norm_scope = str(norm.get("scope", "district"))
            if norm_scope != "city" and district and norm_district not in {"", district}:
                continue
            source_ids = {str(value) for value in norm.get("source_topic_ids", [])}
            score = 0
            if topic_id and topic_id in source_ids:
                score += 3
            if str(norm.get("category", "")) == topic_kind:
                score += 2
            if topic_kind in {str(tag) for tag in norm.get("tags", [])}:
                score += 1
            if score <= 0:
                continue
            matches.append(
                (
                    score,
                    float(norm.get("strength", 0.0)),
                    float(norm.get("support", 0.0)),
                    norm,
                )
            )
        if not matches:
            return None
        matches.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return matches[0][3]

    def _collective_kind_from_topic(
        self,
        topic: dict[str, Any],
        norm: dict[str, Any] | None = None,
        kind_hint: str = "",
    ) -> str:
        normalized_hint = str(kind_hint).strip().lower()
        hint_map = {
            "strike": "strike",
            "罢工": "strike",
            "meeting": "meeting",
            "动员会": "meeting",
            "集会": "rally",
            "rally": "rally",
            "party": "party",
            "派对": "party",
        }
        if normalized_hint in hint_map:
            return hint_map[normalized_hint]
        kind = str(topic.get("kind", ""))
        norm_category = str((norm or {}).get("category", ""))
        heat = float(topic.get("heat", 0.0))
        controversy = float(topic.get("controversy", 0.0))
        worker_unrest = float(self.state.get("macro", {}).get("worker_unrest", 0.0))
        if kind == "labor":
            if heat >= 0.56 or worker_unrest >= 68 or norm_category == "labor":
                return "strike"
            return "meeting"
        if kind in {"media", "public", "family"} and max(heat, controversy) >= 0.24:
            return "rally"
        if kind == "supply" and (heat >= 0.44 or worker_unrest >= 64):
            return "rally"
        return ""

    def _collective_target_groups(self, kind: str, topic: dict[str, Any], norm: dict[str, Any] | None) -> list[str]:
        if norm and norm.get("target_groups"):
            return self._dedupe_id_list(list(norm.get("target_groups", [])), limit=8)
        if kind in {"strike", "meeting"}:
            return ["工人", "临时工", "工会"]
        if kind == "rally":
            return ["居民", "工人", "店主", "记者"]
        if kind == "party":
            return ["居民", "店主", "记者"]
        topic_kind = str(topic.get("kind", ""))
        if topic_kind == "labor":
            return ["工人", "临时工", "工会"]
        return ["居民"]

    def _collective_theme(self, topic: dict[str, Any], norm: dict[str, Any] | None, kind: str) -> str:
        norm_text = str((norm or {}).get("text", "")).strip()
        if norm_text:
            return norm_text
        label = str(topic.get("label", "")).strip()
        if label:
            return label
        district = str(topic.get("district", "")) or "全城"
        if kind == "strike":
            return f"{district}的工钱与班次"
        if kind == "rally":
            return f"{district}的街头情绪"
        if kind == "party":
            return f"{district}的夜间社交"
        return f"{district}的集体动作"

    def _collective_label(self, kind: str, district: str, _theme: str) -> str:
        district_name = district or "全城"
        if kind == "strike":
            return f"{district_name}罢工动员"
        if kind == "meeting":
            return f"{district_name}动员会"
        if kind == "rally":
            return f"{district_name}集会"
        if kind == "party":
            return f"{district_name}派对"
        return f"{district_name}集体行动"

    def _collective_thresholds(self, kind: str) -> dict[str, float]:
        if kind == "strike":
            return {"support": 0.34, "commitment": 0.18, "turnout": 0.12, "risk": 0.58, "reward": 0.66}
        if kind == "rally":
            return {"support": 0.28, "commitment": 0.14, "turnout": 0.1, "risk": 0.46, "reward": 0.48}
        if kind == "party":
            return {"support": 0.18, "commitment": 0.08, "turnout": 0.08, "risk": 0.16, "reward": 0.34}
        return {"support": 0.22, "commitment": 0.1, "turnout": 0.08, "risk": 0.28, "reward": 0.38}

    def _collective_target_for_action(self, action: dict[str, Any]) -> dict[str, Any]:
        district = str(action.get("district", ""))
        kind = str(action.get("kind", "meeting"))
        district_points = COLLECTIVE_GATHER_POINTS.get(district, {})
        point = district_points.get(kind) or district_points.get("meeting") or district_points.get("rally") or {
            "location_id": "",
            "title": f"{district or '全城'}集结点",
            "subregion_id": str(action.get("subregion_id", "")),
            "subregion_name": str(action.get("subregion_name", district)),
            "x": float(action.get("target_x", 0.0)),
            "y": float(action.get("target_y", 0.0)),
        }
        return {
            "target_location_id": str(point.get("location_id", "")),
            "target_location_title": str(point.get("title", "")),
            "target_subregion_id": str(point.get("subregion_id", "")),
            "target_subregion_name": str(point.get("subregion_name", district)),
            "target_x": round(float(point.get("x", 0.0)), 1),
            "target_y": round(float(point.get("y", 0.0)), 1),
        }

    def _collective_window_for_kind(self, kind: str) -> tuple[int, int]:
        if kind == "strike":
            return 9 * 60 + 30, 17 * 60 + 30
        if kind == "meeting":
            return 18 * 60, 22 * 60
        if kind == "rally":
            return 12 * 60, 19 * 60
        if kind == "party":
            return 19 * 60, 23 * 60
        return 10 * 60, 18 * 60

    def _collective_response_candidates(self, action: dict[str, Any]) -> dict[str, list[str]]:
        district = str(action.get("district", ""))
        company = next((row for row in self.state.get("companies", []) if str(row.get("district", "")) == district), None)
        company_id = str((company or {}).get("id", ""))
        family_name = str((company or {}).get("family_owner", ""))
        government_ids: list[str] = []
        police_ids: list[str] = []
        company_ids: list[str] = []
        family_ids: list[str] = []
        media_ids: list[str] = []
        for npc in self.state.get("npcs", []):
            npc_id = str(npc.get("id", ""))
            title = str(npc.get("title", ""))
            role = str(npc.get("role", ""))
            affiliation = str(npc.get("family_affiliation", ""))
            npc_company_id = str(npc.get("company_id", ""))
            if affiliation == "镇政府":
                government_ids.append(npc_id)
                if "治安队长" in title:
                    police_ids.append(npc_id)
                if role in {"记者", "代理人"}:
                    media_ids.append(npc_id)
            if company_id and npc_company_id == company_id and role in {"老板", "代理人", "银行经理", "记者"}:
                company_ids.append(npc_id)
            if family_name and affiliation == family_name and npc_id not in company_ids:
                family_ids.append(npc_id)
        return {
            "government": self._dedupe_id_list(government_ids, limit=8),
            "police": self._dedupe_id_list(police_ids, limit=4),
            "company": self._dedupe_id_list(company_ids, limit=8),
            "family": self._dedupe_id_list(family_ids, limit=8),
            "media": self._dedupe_id_list(media_ids, limit=6),
        }

    def _collective_response_mode(self, action: dict[str, Any]) -> str:
        kind = str(action.get("kind", "meeting"))
        stage = str(action.get("stage", "forming"))
        support = float(action.get("support", 0.0))
        commitment = float(action.get("commitment", 0.0))
        turnout = float(action.get("turnout", 0.0))
        risk = float(action.get("risk", 0.0))
        organizers = int(action.get("organizer_count", 0))
        if kind == "party":
            return "observe"
        if kind == "meeting":
            if support >= 0.4 or commitment >= 0.14 or stage in {"committing", "active"}:
                return "negotiate"
            if organizers > 0 and support < 0.24 and risk < 0.62:
                return "suppress"
            return "observe"
        if kind in {"strike", "rally"}:
            if turnout >= float(action.get("turnout_threshold", 0.1)) or stage == "active" or support >= 0.46:
                return "negotiate"
            if organizers > 0 and support < 0.32 and risk < 0.7:
                return "suppress"
            if commitment >= 0.1 or support >= 0.24:
                return "observe"
            return "suppress"
        return "observe"

    def _collective_response_note(self, action: dict[str, Any], mode: str) -> str:
        label = str(action.get("label", "集体行动"))
        if mode == "negotiate":
            return f"政府和企业正在围着 {label} 试探谈判口风。"
        if mode == "suppress":
            return f"政府和企业正在围着 {label} 部署压制和清场。"
        return f"政府和企业正在盯着 {label} 的规模和扩散。"

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _collective_threshold_shift(self, action: dict[str, Any]) -> float:
        support_push = float(action.get("player_support", 0.0)) * 0.055
        mediation_push = float(action.get("player_mediation", 0.0)) * 0.045
        suppression_push = float(action.get("player_suppression", 0.0)) * 0.065
        return round(self._clamp(support_push + mediation_push - suppression_push, -0.18, 0.18), 3)

    def _collective_effective_thresholds(self, action: dict[str, Any]) -> dict[str, float]:
        kind = str(action.get("kind", "meeting"))
        thresholds = self._collective_thresholds(kind)
        response_mode = str(action.get("response_mode", "observe"))
        response_drag = 0.045 if response_mode == "suppress" else -0.025 if response_mode == "negotiate" else 0.0
        player_shift = self._collective_threshold_shift(action)
        support_threshold = self._clamp(float(action.get("support_threshold", thresholds["support"])) + response_drag - player_shift, 0.12, 0.68)
        commitment_threshold = self._clamp(float(action.get("commitment_threshold", thresholds["commitment"])) + response_drag * 0.9 - player_shift * 0.85, 0.06, 0.52)
        turnout_threshold = self._clamp(float(action.get("turnout_threshold", thresholds["turnout"])) + response_drag - player_shift * 1.05, 0.05, 0.44)
        return {
            "support": round(support_threshold, 3),
            "commitment": round(commitment_threshold, 3),
            "turnout": round(turnout_threshold, 3),
            "shift": round(player_shift, 3),
        }

    @staticmethod
    def _collective_resolution_label(kind: str) -> str:
        return {
            "conceded": "谈判让步",
            "escalated": "镇压升级",
            "fizzled": "到场不足流产",
            "held": "现场成局",
        }.get(str(kind), "现场结算")

    def _collective_signature(self, topic: dict[str, Any], norm: dict[str, Any] | None, district: str) -> str:
        source_key = str(topic.get("id", "")).strip() or str((norm or {}).get("id", "")).strip()
        if not source_key:
            source_key = f"{district}:{self._collective_theme(topic, norm, '')}"
        stable_suffix = sum(ord(ch) for ch in source_key) % 10000
        return f"collective_{district or 'city'}_{stable_suffix}"

    def _collective_system_pressure(self, topic: dict[str, Any], norm: dict[str, Any] | None) -> float:
        district = str(topic.get("district", ""))
        signals = self.state.get("district_signals", {}).get(district, {})
        heat = float(topic.get("heat", 0.0))
        controversy = float(topic.get("controversy", 0.0))
        norm_strength = float((norm or {}).get("strength", 0.0))
        norm_support = float((norm or {}).get("support", 0.0))
        labor_heat = float(signals.get("labor_heat", 0.0))
        gossip = float(signals.get("gossip", 0.0))
        worker_unrest = float(self.state.get("macro", {}).get("worker_unrest", 0.0)) / 100.0
        media_sentiment = float(self.state.get("macro", {}).get("media_sentiment", 0.0)) / 100.0
        kind = str(topic.get("kind", ""))
        score = heat * 0.52 + norm_strength * 0.18 + norm_support * 0.14 + controversy * 0.08
        if kind == "labor":
            score += labor_heat * 0.18 + worker_unrest * 0.16
        elif kind in {"media", "public", "family"}:
            score += gossip * 0.12 + abs(media_sentiment - 0.5) * 0.08
        elif kind == "supply":
            score += worker_unrest * 0.12
        return round(max(0.0, min(1.0, score)), 3)

    def _npc_matches_collective_group(self, npc: dict[str, Any], group: str) -> bool:
        target = str(group).strip()
        if not target:
            return False
        role = str(npc.get("role", ""))
        title = str(npc.get("title", ""))
        class_name = str(npc.get("class", ""))
        text = " ".join([role, title, class_name, str(npc.get("family_affiliation", ""))])
        if target in text:
            return True
        mapping = {
            "工人": {"工人", "临时工"},
            "临时工": {"临时工"},
            "工会": {"工会领袖"},
            "居民": {"居民", "家庭主妇", "失业青年", "退休老人", "老人"},
            "店主": {"店主"},
            "记者": {"记者"},
            "代理人": {"代理人"},
        }
        allowed = mapping.get(target, set())
        return role in allowed or any(token in title for token in allowed)

    def _collective_eligible_npc_ids(self, action: dict[str, Any]) -> list[str]:
        district = str(action.get("district", ""))
        scope = str(action.get("scope", "district"))
        target_groups = [str(value) for value in action.get("target_groups", []) if str(value).strip()]
        rows: list[str] = []
        for npc in self.state.get("npcs", []):
            if scope != "city" and district and str(npc.get("district", "")) not in {"", district}:
                continue
            if target_groups and not any(self._npc_matches_collective_group(npc, group) for group in target_groups):
                continue
            npc_id = str(npc.get("id", "")).strip()
            if npc_id and npc_id not in rows:
                rows.append(npc_id)
        if rows:
            return rows
        return [str(npc.get("id", "")) for npc in self.state.get("npcs", []) if str(npc.get("id", "")).strip()]

    def _refresh_collective_action_row(
        self,
        action: dict[str, Any],
        *,
        baseline_heat: float | None = None,
        baseline_support: float | None = None,
    ) -> dict[str, Any]:
        current_tick = self._world_tick()
        eligible_ids = self._collective_eligible_npc_ids(action)
        potential_size = max(1, len(eligible_ids))
        heard_ids = self._dedupe_id_list(action.get("heard_ids", []))
        supporter_ids = self._dedupe_id_list(action.get("supporter_ids", []))
        committed_ids = self._dedupe_id_list(action.get("committed_ids", []))
        attendee_ids = self._dedupe_id_list(action.get("attendee_ids", []))
        organizer_ids = self._dedupe_id_list(action.get("organizer_ids", []))
        suppression_ids = self._dedupe_id_list(action.get("suppression_ids", []))
        action["heard_ids"] = heard_ids
        action["supporter_ids"] = supporter_ids
        action["committed_ids"] = committed_ids
        action["attendee_ids"] = attendee_ids
        action["organizer_ids"] = organizer_ids
        action["suppression_ids"] = suppression_ids
        heard_ratio = len(heard_ids) / potential_size
        support_ratio = len(supporter_ids) / potential_size
        commit_ratio = len(committed_ids) / potential_size
        turnout_ratio = len(attendee_ids) / potential_size
        suppression_ratio = len(suppression_ids) / potential_size
        kind = str(action.get("kind", "meeting"))
        thresholds = self._collective_thresholds(kind)
        systemic_pressure = 0.0
        if kind == "strike":
            systemic_pressure = float(self.state.get("macro", {}).get("worker_unrest", 0.0)) / 240.0
        elif kind == "rally":
            systemic_pressure = float(self.state.get("macro", {}).get("media_sentiment", 0.0)) / 320.0
        elif kind == "party":
            systemic_pressure = float(self.state.get("macro", {}).get("economy_heat", 0.0)) / 420.0
        target_heat = max(
            baseline_heat if baseline_heat is not None else 0.0,
            heard_ratio * 0.22 + support_ratio * 0.28 + commit_ratio * 0.22 + turnout_ratio * 0.24 + systemic_pressure - suppression_ratio * 0.16,
        )
        target_support = max(
            baseline_support if baseline_support is not None else 0.0,
            support_ratio + len(organizer_ids) / potential_size * 0.12 - suppression_ratio * 0.08,
        )
        action["heat"] = round(max(0.0, min(1.0, max(float(action.get("heat", 0.0)) * 0.92, target_heat))), 3)
        action["support"] = round(max(0.0, min(1.0, max(float(action.get("support", 0.0)) * 0.94, target_support))), 3)
        action["commitment"] = round(max(0.0, min(1.0, max(float(action.get("commitment", 0.0)) * 0.95, commit_ratio))), 3)
        action["turnout"] = round(max(0.0, min(1.0, max(float(action.get("turnout", 0.0)) * 0.94, turnout_ratio))), 3)
        action["risk"] = round(
            max(0.08, min(1.0, float(action.get("risk", thresholds["risk"])) * 0.84 + thresholds["risk"] * 0.16 + suppression_ratio * 0.18)),
            3,
        )
        action["expected_reward"] = round(
            max(
                0.08,
                min(1.0, float(action.get("expected_reward", thresholds["reward"])) * 0.88 + thresholds["reward"] * 0.12 + action["support"] * 0.06),
            ),
            3,
        )
        effective_thresholds = self._collective_effective_thresholds(action)
        action["player_threshold_shift"] = round(float(effective_thresholds["shift"]), 3)
        action["effective_support_threshold"] = round(float(effective_thresholds["support"]), 3)
        action["effective_commitment_threshold"] = round(float(effective_thresholds["commitment"]), 3)
        action["effective_turnout_threshold"] = round(float(effective_thresholds["turnout"]), 3)
        if str(action.get("resolution_kind", "")):
            resolved_age = max(0, current_tick - int(action.get("resolution_tick", current_tick)))
            action["stage"] = "cooling" if resolved_age <= 4 * 60 else "dormant"
            action["status"] = "resolved"
            action["potential_size"] = potential_size
            action["heard_count"] = len(heard_ids)
            action["support_count"] = len(supporter_ids)
            action["commit_count"] = len(committed_ids)
            action["attendee_count"] = len(attendee_ids)
            action["organizer_count"] = len(organizer_ids)
            action["suppression_count"] = len(suppression_ids)
            return
        if action["turnout"] >= effective_thresholds["turnout"] or len(attendee_ids) >= max(2, math.ceil(potential_size * effective_thresholds["turnout"])):
            stage = "active"
            status = "active"
        elif action["commitment"] >= effective_thresholds["commitment"] or len(committed_ids) >= max(1, math.ceil(potential_size * effective_thresholds["commitment"])):
            stage = "committing"
            status = "warming"
        elif action["support"] >= effective_thresholds["support"] or len(supporter_ids) >= max(1, math.ceil(potential_size * effective_thresholds["support"])):
            stage = "signaling"
            status = "warming"
        elif action["heat"] >= 0.12 or heard_ids:
            stage = "forming"
            status = "emerging"
        elif action["heat"] >= 0.06:
            stage = "cooling"
            status = "cooling"
        else:
            stage = "dormant"
            status = "dormant"
        action["stage"] = stage
        action["status"] = status
        action["potential_size"] = potential_size
        action["heard_count"] = len(heard_ids)
        action["support_count"] = len(supporter_ids)
        action["commit_count"] = len(committed_ids)
        action["attendee_count"] = len(attendee_ids)
        action["organizer_count"] = len(organizer_ids)
        action["suppression_count"] = len(suppression_ids)
        if stage == "active" and not int(action.get("start_tick", 0)):
            action["start_tick"] = current_tick

    def _upsert_collective_seed(
        self,
        topic: dict[str, Any],
        norm: dict[str, Any] | None,
        pressure: float,
        kind_hint: str = "",
    ) -> dict[str, Any] | None:
        kind = self._collective_kind_from_topic(topic, norm, kind_hint)
        if not kind:
            return None
        district = str(topic.get("district", "")) or str((norm or {}).get("district", ""))
        action_id = self._collective_signature(topic, norm, district)
        theme = self._collective_theme(topic, norm, kind)
        label = self._collective_label(kind, district, theme)
        thresholds = self._collective_thresholds(kind)
        baseline_heat = round(max(0.08, min(1.0, float(topic.get("heat", 0.0)) * 0.56 + pressure * 0.28)), 3)
        baseline_support = round(
            max(
                0.04,
                min(1.0, pressure * 0.44 + float((norm or {}).get("support", 0.0)) * 0.18 + float((norm or {}).get("strength", 0.0)) * 0.12),
            ),
            3,
        )
        registry = list(self.state.get("collective_action_registry", []))
        action = next((row for row in registry if str(row.get("id", "")) == action_id), None)
        current_tick = self._world_tick()
        if action is None:
            action = {
                "id": action_id,
                "kind": kind,
                "district": district,
                "scope": "city" if str(topic.get("scope", "district")) == "city" or str((norm or {}).get("scope", "district")) == "city" else "district",
                "label": label,
                "theme": theme,
                "status": "emerging",
                "stage": "forming",
                "heat": baseline_heat,
                "support": baseline_support,
                "commitment": 0.0,
                "turnout": 0.0,
                "risk": thresholds["risk"],
                "expected_reward": thresholds["reward"],
                "support_threshold": thresholds["support"],
                "commitment_threshold": thresholds["commitment"],
                "turnout_threshold": thresholds["turnout"],
                "source_topic_ids": self._dedupe_id_list([str(topic.get("id", ""))]),
                "source_norm_ids": self._dedupe_id_list([str((norm or {}).get("id", ""))]),
                "target_groups": self._collective_target_groups(kind, topic, norm),
                "heard_ids": [],
                "supporter_ids": [],
                "committed_ids": [],
                "attendee_ids": [],
                "organizer_ids": [],
                "suppression_ids": [],
                "created_tick": current_tick,
                "start_tick": 0,
                "last_tick": current_tick,
                "last_actor_id": "",
                "last_action": "seed",
                "player_support": 0.0,
                "player_mediation": 0.0,
                "player_suppression": 0.0,
                "player_threshold_shift": 0.0,
                "effective_support_threshold": thresholds["support"],
                "effective_commitment_threshold": thresholds["commitment"],
                "effective_turnout_threshold": thresholds["turnout"],
                "resolution_kind": "",
                "resolution_label": "",
                "resolution_note": "",
                "resolution_tick": 0,
                "resolution_crowd_score": 0.0,
                "resolution_response_score": 0.0,
            }
            registry.append(action)
            self.state["collective_action_registry"] = registry
        else:
            if self._collective_kind_rank(kind) > self._collective_kind_rank(str(action.get("kind", ""))):
                action["kind"] = kind
            action["label"] = label
            action["theme"] = theme
            action["scope"] = "city" if str(action.get("scope", "district")) == "city" or str(topic.get("scope", "district")) == "city" else "district"
            action["target_groups"] = self._dedupe_id_list(
                [*list(action.get("target_groups", [])), *self._collective_target_groups(kind, topic, norm)],
                limit=8,
            )
            action["source_topic_ids"] = self._dedupe_id_list([*list(action.get("source_topic_ids", [])), str(topic.get("id", ""))])
            action["source_norm_ids"] = self._dedupe_id_list([*list(action.get("source_norm_ids", [])), str((norm or {}).get("id", ""))])
            action["last_tick"] = current_tick
        self._refresh_collective_action_row(action, baseline_heat=baseline_heat, baseline_support=baseline_support)
        self._sort_collective_registry()
        return action

    def _sort_collective_registry(self) -> None:
        registry = list(self.state.get("collective_action_registry", []))
        registry.sort(
            key=lambda row: (
                self._collective_stage_rank(str(row.get("stage", ""))),
                float(row.get("heat", 0.0)),
                float(row.get("support", 0.0)),
            ),
            reverse=True,
        )
        self.state["collective_action_registry"] = registry[:24]

    def _decay_collective_actions(self) -> None:
        current_tick = self._world_tick()
        last_tick = int(self.state.get("collective_action_decay_tick", current_tick))
        delta = max(0, current_tick - last_tick)
        if delta <= 0:
            return
        heat_decay = pow(0.9987, delta)
        support_decay = pow(0.999, delta)
        commit_decay = pow(0.9988, delta)
        turnout_decay = pow(0.9983, delta)
        keep_rows: list[dict[str, Any]] = []
        for row in self.state.get("collective_action_registry", []):
            action = copy.deepcopy(row)
            action["heat"] = round(max(0.0, min(1.0, float(action.get("heat", 0.0)) * heat_decay)), 3)
            action["support"] = round(max(0.0, min(1.0, float(action.get("support", 0.0)) * support_decay)), 3)
            action["commitment"] = round(max(0.0, min(1.0, float(action.get("commitment", 0.0)) * commit_decay)), 3)
            action["turnout"] = round(max(0.0, min(1.0, float(action.get("turnout", 0.0)) * turnout_decay)), 3)
            self._refresh_collective_action_row(action)
            age = current_tick - int(action.get("last_tick", current_tick))
            if age > 4 * 24 * 60 and float(action.get("heat", 0.0)) < 0.06 and int(action.get("attendee_count", 0)) == 0:
                continue
            keep_rows.append(action)
        self.state["collective_action_registry"] = keep_rows[:24]
        self.state["collective_action_decay_tick"] = current_tick

    def _sync_collective_actions(self) -> None:
        self._decay_collective_actions()
        for topic in self._active_public_topics(limit=8):
            norm = self._collective_norm_for_topic(topic)
            pressure = self._collective_system_pressure(topic, norm)
            if pressure < 0.24:
                continue
            self._upsert_collective_seed(topic, norm, pressure)
        self._resolve_collective_responses()
        for action in self.state.get("collective_action_registry", []):
            self._refresh_collective_action_row(action)
        self._resolve_collective_outcomes()
        for action in self.state.get("collective_action_registry", []):
            self._refresh_collective_action_row(action)
        self._sort_collective_registry()

    def _resolve_collective_responses(self) -> None:
        for action in self.state.get("collective_action_registry", []):
            target = self._collective_target_for_action(action)
            action.update(target)
            window_start, window_end = self._collective_window_for_kind(str(action.get("kind", "meeting")))
            action["window_start_minutes"] = int(window_start)
            action["window_end_minutes"] = int(window_end)
            mode = self._collective_response_mode(action)
            if float(action.get("player_suppression", 0.0)) >= 0.18:
                mode = "suppress"
            elif float(action.get("player_mediation", 0.0)) >= 0.18:
                mode = "negotiate"
            elif float(action.get("player_support", 0.0)) >= 0.22 and mode == "observe":
                mode = "negotiate"
            candidates = self._collective_response_candidates(action)
            response_actor_ids: list[str] = []
            if mode == "negotiate":
                response_actor_ids = self._dedupe_id_list([
                    *candidates.get("government", [])[:2],
                    *candidates.get("company", [])[:2],
                    *candidates.get("family", [])[:1],
                ], limit=6)
            elif mode == "suppress":
                response_actor_ids = self._dedupe_id_list([
                    *candidates.get("police", [])[:2],
                    *candidates.get("company", [])[:2],
                    *candidates.get("government", [])[:1],
                ], limit=6)
            else:
                response_actor_ids = self._dedupe_id_list([
                    *candidates.get("government", [])[:1],
                    *candidates.get("company", [])[:1],
                    *candidates.get("media", [])[:1],
                ], limit=4)
            action["response_mode"] = mode
            action["response_actor_ids"] = response_actor_ids
            action["response_note"] = self._collective_response_note(action, mode)
            action["response_target_x"] = round(float(action.get("target_x", 0.0)) + (58.0 if mode == "suppress" else -42.0 if mode == "negotiate" else 24.0), 1)
            action["response_target_y"] = round(float(action.get("target_y", 0.0)) + (16.0 if mode == "suppress" else -12.0 if mode == "negotiate" else -18.0), 1)
            if mode == "suppress":
                action["suppression_ids"] = self._dedupe_id_list([*list(action.get("suppression_ids", [])), *response_actor_ids], limit=10)
                action["risk"] = round(min(1.0, float(action.get("risk", 0.0)) + 0.02), 3)
            elif mode == "negotiate":
                action["negotiator_ids"] = self._dedupe_id_list(response_actor_ids, limit=8)
                action["risk"] = round(max(0.08, float(action.get("risk", 0.0)) - 0.015), 3)
            effective_thresholds = self._collective_effective_thresholds(action)
            action["player_threshold_shift"] = round(float(effective_thresholds["shift"]), 3)
            action["effective_support_threshold"] = round(float(effective_thresholds["support"]), 3)
            action["effective_commitment_threshold"] = round(float(effective_thresholds["commitment"]), 3)
            action["effective_turnout_threshold"] = round(float(effective_thresholds["turnout"]), 3)

    def _collective_company_for_action(self, action: dict[str, Any]) -> dict[str, Any] | None:
        district = str(action.get("district", ""))
        for company in self.state.get("companies", []):
            if str(company.get("district", "")) == district:
                return company
        return None

    def _collective_crowd_score(self, action: dict[str, Any]) -> float:
        potential_size = max(1, int(action.get("potential_size", 0)))
        organizer_share = int(action.get("organizer_count", 0)) / potential_size
        player_bias = float(action.get("player_support", 0.0)) * 0.08 + float(action.get("player_mediation", 0.0)) * 0.05 - float(action.get("player_suppression", 0.0)) * 0.06
        return round(
            self._clamp(
                float(action.get("support", 0.0)) * 0.28
                + float(action.get("commitment", 0.0)) * 0.32
                + float(action.get("turnout", 0.0)) * 0.46
                + organizer_share * 0.12
                + player_bias,
                0.0,
                1.6,
            ),
            3,
        )

    def _collective_response_score(self, action: dict[str, Any]) -> float:
        potential_size = max(1, int(action.get("potential_size", 0)))
        response_share = len(self._dedupe_id_list(action.get("response_actor_ids", []), limit=12)) / potential_size
        mode_bias = 0.16 if str(action.get("response_mode", "")) == "suppress" else -0.04 if str(action.get("response_mode", "")) == "negotiate" else 0.03
        player_bias = float(action.get("player_suppression", 0.0)) * 0.08 - float(action.get("player_support", 0.0)) * 0.03 - float(action.get("player_mediation", 0.0)) * 0.05
        takeover_drag = 0.0
        if bool(self._stock_ops_state().get("victor_takeover_done", False)) and str(action.get("district", "")) in {"工厂区", "交易所", "富人区"}:
            takeover_drag = 0.18
        return round(
            self._clamp(
                response_share * 0.36
                + float(action.get("risk", 0.0)) * 0.24
                + mode_bias
                + player_bias
                - takeover_drag,
                -0.2,
                1.4,
            ),
            3,
        )

    def _collective_ready_for_resolution(self, action: dict[str, Any]) -> bool:
        if str(action.get("resolution_kind", "")):
            return False
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        stage = str(action.get("stage", "forming"))
        if stage in {"dormant", "cooling"}:
            return False
        start = int(action.get("window_start_minutes", 0))
        end = int(action.get("window_end_minutes", 24 * 60))
        kind = str(action.get("kind", "meeting"))
        early_offset = 22 if kind in {"meeting", "rally"} else 28 if kind == "strike" else 36
        if minutes >= end + 20:
            return True
        if minutes < start + early_offset:
            return False
        if stage == "active":
            return True
        if float(action.get("player_mediation", 0.0)) >= 0.28:
            return True
        if str(action.get("response_mode", "")) == "suppress" and int(action.get("suppression_count", 0)) > 0:
            return True
        return False

    def _collective_result_packet(self, action: dict[str, Any], resolution_kind: str, note: str) -> dict[str, Any]:
        district = str(action.get("district", ""))
        label = str(action.get("label", "集体行动"))
        company = self._collective_company_for_action(action)
        family_name = str((company or {}).get("family_owner", ""))
        stock_name = str((company or {}).get("stock_name", ""))
        goods_delta: dict[str, float] = {}
        if district == "工厂区":
            goods_delta = {"煤": -0.03 if resolution_kind == "escalated" else 0.02}
        elif district == "港口":
            goods_delta = {"罐头": -0.03 if resolution_kind == "escalated" else 0.02}
        elif district == "贫民街":
            goods_delta = {"面包": -0.02 if resolution_kind == "escalated" else 0.02}
        stocks_delta = {stock_name: -0.05 if resolution_kind == "escalated" else -0.02 if resolution_kind == "conceded" else 0.01} if stock_name else {}
        macro_delta = {
            "worker_unrest": 2.4 if resolution_kind == "escalated" else -1.8 if resolution_kind == "conceded" else -0.8 if resolution_kind == "fizzled" else 0.2,
            "media_sentiment": -1.2 if resolution_kind == "escalated" else 0.9 if resolution_kind == "conceded" else -0.4 if resolution_kind == "fizzled" else 1.2,
        }
        family_delta = {family_name: -0.05 if resolution_kind == "escalated" else -0.02 if resolution_kind == "conceded" else 0.01} if family_name else {}
        return {
            "id": f"{action.get('id', 'collective')}_{resolution_kind}_{self._world_tick()}",
            "district": district,
            "source": "集体行动结算",
            "title": f"{label}：{self._collective_resolution_label(resolution_kind)}",
            "line": note,
            "body": note,
            "tags": ["集体行动", str(action.get("kind", "")), resolution_kind],
            "scope": "city" if resolution_kind in {"escalated", "conceded"} else "district",
            "topic_kind": "labor" if str(action.get("kind", "")) in {"strike", "meeting"} else "public",
            "goods_delta": goods_delta,
            "stocks_delta": stocks_delta,
            "macro_delta": macro_delta,
            "family_delta": family_delta,
        }

    def _apply_collective_resolution(self, action: dict[str, Any], resolution_kind: str, note: str, crowd_score: float, response_score: float) -> None:
        if str(action.get("resolution_kind", "")):
            return
        current_tick = self._world_tick()
        label = str(action.get("label", "集体行动"))
        district = str(action.get("district", ""))
        action["resolution_kind"] = resolution_kind
        action["resolution_label"] = self._collective_resolution_label(resolution_kind)
        action["resolution_note"] = note
        action["resolution_tick"] = current_tick
        action["resolution_crowd_score"] = round(crowd_score, 3)
        action["resolution_response_score"] = round(response_score, 3)
        action["last_action"] = resolution_kind
        action["last_tick"] = current_tick
        action["status"] = "resolved"
        action["stage"] = "cooling"
        company = self._collective_company_for_action(action)
        linked_npcs = self._linked_npcs_for_company(str((company or {}).get("id", ""))) if company else [npc for npc in self.state.get("npcs", []) if str(npc.get("district", "")) == district]
        player = self.state.get("player", {})
        family_name = str((company or {}).get("family_owner", ""))
        if resolution_kind == "conceded":
            action["heat"] = round(self._clamp(max(float(action.get("heat", 0.0)) * 0.54, 0.16), 0.08, 0.52), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) * 0.82, 0.08, 0.92), 3)
            action["commitment"] = round(self._clamp(float(action.get("commitment", 0.0)) * 0.68, 0.04, 0.84), 3)
            action["turnout"] = round(self._clamp(float(action.get("turnout", 0.0)) * 0.58, 0.03, 0.82), 3)
            self.state["macro"]["worker_unrest"] = max(0, int(self.state["macro"].get("worker_unrest", 50)) - 3)
            self.state["macro"]["media_sentiment"] = min(100, int(self.state["macro"].get("media_sentiment", 50)) + 1)
            self._bump_district_signal(district, "labor_heat", -0.12)
            self._bump_district_signal(district, "fear", -0.08)
            self._bump_district_signal(district, "gossip", 0.08)
            if company:
                company["payroll_delay"] = max(0.0, float(company.get("payroll_delay", 0.0)) - 8.0)
                company["wage_pressure"] = max(10.0, float(company.get("wage_pressure", 35.0)) - 8.0)
                company["order_pressure"] = max(12.0, float(company.get("order_pressure", 50.0)) - 4.0)
                company["profit_margin"] = max(0.04, float(company.get("profit_margin", 0.12)) - 0.015)
                company["wage_level"] = min(12.0, float(company.get("wage_level", 5.0)) + 0.3)
            for npc in linked_npcs[:6]:
                npc["anxiety"] = max(0.0, float(npc.get("anxiety", 0.0)) - 6.0)
                npc["fear"] = max(0, int(npc.get("fear", 0)) - 4)
                npc["job_security"] = min(100.0, float(npc.get("job_security", 50.0)) + 4.0)
            if float(action.get("player_support", 0.0)) + float(action.get("player_mediation", 0.0)) > float(action.get("player_suppression", 0.0)):
                player["reputation"] = min(100, int(player.get("reputation", 0)) + 1)
                if family_name:
                    player["family_relations"][family_name] = int(player.get("family_relations", {}).get(family_name, 0)) - 1
                player["family_relations"]["镇政府"] = int(player.get("family_relations", {}).get("镇政府", 0)) + (1 if float(action.get("player_mediation", 0.0)) > 0 else 0)
        elif resolution_kind == "escalated":
            action["heat"] = round(self._clamp(float(action.get("heat", 0.0)) + 0.16, 0.14, 0.95), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) + 0.08, 0.1, 0.95), 3)
            action["commitment"] = round(self._clamp(float(action.get("commitment", 0.0)) + 0.06, 0.06, 0.9), 3)
            action["turnout"] = round(self._clamp(float(action.get("turnout", 0.0)) * 0.72, 0.04, 0.88), 3)
            action["risk"] = round(self._clamp(float(action.get("risk", 0.0)) + 0.16, 0.08, 1.0), 3)
            self.state["macro"]["worker_unrest"] = min(100, int(self.state["macro"].get("worker_unrest", 50)) + 6)
            self.state["macro"]["media_sentiment"] = max(0, int(self.state["macro"].get("media_sentiment", 50)) - 3)
            self.state["macro"]["economy_heat"] = max(0, int(self.state["macro"].get("economy_heat", 50)) - 1)
            self._bump_district_signal(district, "labor_heat", 0.16)
            self._bump_district_signal(district, "fear", 0.18)
            self._bump_district_signal(district, "gossip", 0.1)
            if company:
                company["order_pressure"] = max(12.0, float(company.get("order_pressure", 50.0)) - 6.0)
                company["payroll_delay"] = min(100.0, float(company.get("payroll_delay", 0.0)) + 5.0)
                company["wage_pressure"] = min(100.0, float(company.get("wage_pressure", 35.0)) + 4.0)
                company["financing_pressure"] = min(100.0, float(company.get("financing_pressure", 45.0)) + 3.0)
            for npc in linked_npcs[:6]:
                npc["anxiety"] = min(100.0, float(npc.get("anxiety", 0.0)) + 8.0)
                npc["fear"] = min(100, int(npc.get("fear", 0)) + 6)
                npc["job_security"] = max(8.0, float(npc.get("job_security", 50.0)) - 6.0)
            if float(action.get("player_suppression", 0.0)) > float(action.get("player_support", 0.0)) + float(action.get("player_mediation", 0.0)):
                player["family_relations"]["镇政府"] = int(player.get("family_relations", {}).get("镇政府", 0)) + 1
                if family_name:
                    player["family_relations"][family_name] = int(player.get("family_relations", {}).get(family_name, 0)) + 1
                player["reputation"] = max(0, int(player.get("reputation", 0)) - 1)
        elif resolution_kind == "held":
            action["heat"] = round(self._clamp(float(action.get("heat", 0.0)) * 0.62, 0.1, 0.56), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) * 0.8, 0.08, 0.88), 3)
            action["commitment"] = round(self._clamp(float(action.get("commitment", 0.0)) * 0.66, 0.04, 0.82), 3)
            action["turnout"] = round(self._clamp(float(action.get("turnout", 0.0)) * 0.6, 0.03, 0.82), 3)
            self.state["macro"]["media_sentiment"] = min(100, int(self.state["macro"].get("media_sentiment", 50)) + 2)
            self.state["macro"]["economy_heat"] = min(100, int(self.state["macro"].get("economy_heat", 50)) + 1)
            self._bump_district_signal(district, "gossip", 0.12)
        else:
            action["heat"] = round(self._clamp(float(action.get("heat", 0.0)) * 0.34, 0.03, 0.28), 3)
            action["support"] = round(self._clamp(float(action.get("support", 0.0)) * 0.46, 0.02, 0.52), 3)
            action["commitment"] = round(self._clamp(float(action.get("commitment", 0.0)) * 0.36, 0.01, 0.46), 3)
            action["turnout"] = round(self._clamp(float(action.get("turnout", 0.0)) * 0.24, 0.0, 0.34), 3)
            self.state["macro"]["worker_unrest"] = max(0, int(self.state["macro"].get("worker_unrest", 50)) - 1)
            self.state["macro"]["media_sentiment"] = max(0, int(self.state["macro"].get("media_sentiment", 50)) - 1)
            self._bump_district_signal(district, "labor_heat", -0.08)
            self._bump_district_signal(district, "gossip", -0.04)
            for npc in linked_npcs[:4]:
                npc["anxiety"] = min(100.0, float(npc.get("anxiety", 0.0)) + 2.0)
                npc["fear"] = min(100, int(npc.get("fear", 0)) + 2)
        for norm in self.state.get("norm_registry", []):
            if str(norm.get("id", "")) not in set(str(value) for value in action.get("source_norm_ids", [])):
                continue
            if resolution_kind in {"conceded", "escalated"}:
                norm["support"] = round(self._clamp(float(norm.get("support", 0.0)) + 0.05, 0.0, 1.0), 3)
                norm["strength"] = round(self._clamp(float(norm.get("strength", 0.0)) + 0.06, 0.0, 1.0), 3)
                norm["reinforce_count"] = int(norm.get("reinforce_count", 0)) + 1
            elif resolution_kind == "fizzled":
                norm["support"] = round(self._clamp(float(norm.get("support", 0.0)) - 0.05, 0.0, 1.0), 3)
                norm["strength"] = round(self._clamp(float(norm.get("strength", 0.0)) - 0.04, 0.0, 1.0), 3)
                norm["contest_count"] = int(norm.get("contest_count", 0)) + 1
        outcome_row = {
            "id": str(action.get("id", "")),
            "label": label,
            "district": district,
            "resolution_kind": resolution_kind,
            "resolution_label": action["resolution_label"],
            "note": note,
            "tick": current_tick,
            "clock_label": self._clock_label(),
            "player_support": round(float(action.get("player_support", 0.0)), 3),
            "player_mediation": round(float(action.get("player_mediation", 0.0)), 3),
            "player_suppression": round(float(action.get("player_suppression", 0.0)), 3),
        }
        self.state["collective_outcomes"].insert(0, outcome_row)
        self.state["collective_outcomes"] = self.state["collective_outcomes"][:12]
        self._record_player_collective_outcome(action, resolution_kind)
        self._queue_collective_followup(action, resolution_kind)
        packet = self._collective_result_packet(action, resolution_kind, note)
        self._apply_intel_packet(packet, to_player=False, promote_news=True, intensity=0.92 if resolution_kind in {"conceded", "escalated"} else 0.68)

    def _resolve_collective_outcomes(self) -> None:
        for action in self.state.get("collective_action_registry", []):
            if not self._collective_ready_for_resolution(action):
                continue
            effective_thresholds = self._collective_effective_thresholds(action)
            turnout_threshold = float(effective_thresholds["turnout"])
            crowd_score = self._collective_crowd_score(action)
            response_score = self._collective_response_score(action)
            turnout = float(action.get("turnout", 0.0))
            support = float(action.get("support", 0.0))
            mode = str(action.get("response_mode", "observe"))
            kind = str(action.get("kind", "meeting"))
            minutes = int(self.state.get("clock_minutes", 8 * 60))
            end = int(action.get("window_end_minutes", 24 * 60))
            if kind == "party":
                if turnout >= turnout_threshold or crowd_score >= turnout_threshold + 0.08:
                    note = f"{action.get('label', '集体行动')} 在 {action.get('target_location_title', '现场')} 成局了，围观和闲谈把气氛越推越热。"
                    self._apply_collective_resolution(action, "held", note, crowd_score, response_score)
                elif minutes >= end + 20:
                    note = f"{action.get('label', '集体行动')} 到场的人不够，大家在 {action.get('target_location_title', '现场')} 等了一阵就散了。"
                    self._apply_collective_resolution(action, "fizzled", note, crowd_score, response_score)
                continue
            if minutes >= end + 20 and turnout < turnout_threshold * 0.82 and support < float(effective_thresholds["support"]) * 0.94:
                note = f"{action.get('label', '集体行动')} 到了收场时人还是没凑够，现场只剩零散抱怨，行动先流产了。"
                self._apply_collective_resolution(action, "fizzled", note, crowd_score, response_score)
                continue
            negotiation_ready = mode == "negotiate" and (crowd_score >= turnout_threshold + 0.08 or float(action.get("player_mediation", 0.0)) >= 0.24)
            suppression_ready = mode == "suppress" and response_score >= crowd_score + 0.08 and float(action.get("risk", 0.0)) >= 0.34
            if negotiation_ready:
                note = f"{action.get('target_location_title', '现场')} 外圈开始松口，{action.get('label', '这场行动')} 换来了一轮实打实的让步。"
                self._apply_collective_resolution(action, "conceded", note, crowd_score, response_score)
            elif suppression_ready:
                note = f"{action.get('target_location_title', '现场')} 的压制升级了，{action.get('label', '这场行动')} 被硬推成更大的冲突。"
                self._apply_collective_resolution(action, "escalated", note, crowd_score, response_score)
            elif minutes >= end + 20:
                note = f"{action.get('label', '这场行动')} 顶着压力撑到了收场，机构虽然没完全让步，但已经留下了后续谈判口子。"
                self._apply_collective_resolution(action, "conceded", note, crowd_score, response_score)

    def _active_collective_actions_view(self, limit: int = 8, district_name: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current_tick = self._world_tick()
        for action in self.state.get("collective_action_registry", []):
            district = str(action.get("district", ""))
            scope = str(action.get("scope", "district"))
            if district_name and scope != "city" and district not in {"", district_name}:
                continue
            resolution_kind = str(action.get("resolution_kind", ""))
            resolved_recently = resolution_kind and current_tick - int(action.get("resolution_tick", 0)) <= 4 * 60
            if not resolved_recently and float(action.get("heat", 0.0)) < 0.08 and int(action.get("heard_count", 0)) <= 0:
                continue
            rows.append(
                {
                    "id": str(action.get("id", "")),
                    "kind": str(action.get("kind", "")),
                    "district": district,
                    "scope": scope,
                    "label": str(action.get("label", "")),
                    "theme": str(action.get("theme", "")),
                    "stage": str(action.get("stage", "")),
                    "stage_label": self._collective_stage_label(str(action.get("stage", ""))),
                    "status": str(action.get("status", "")),
                    "heat": round(float(action.get("heat", 0.0)), 3),
                    "support": round(float(action.get("support", 0.0)), 3),
                    "commitment": round(float(action.get("commitment", 0.0)), 3),
                    "turnout": round(float(action.get("turnout", 0.0)), 3),
                    "risk": round(float(action.get("risk", 0.0)), 3),
                    "expected_reward": round(float(action.get("expected_reward", 0.0)), 3),
                    "heard_count": int(action.get("heard_count", 0)),
                    "support_count": int(action.get("support_count", 0)),
                    "commit_count": int(action.get("commit_count", 0)),
                    "attendee_count": int(action.get("attendee_count", 0)),
                    "organizer_count": int(action.get("organizer_count", 0)),
                    "potential_size": int(action.get("potential_size", 0)),
                    "target_groups": list(action.get("target_groups", [])),
                    "target_location_id": str(action.get("target_location_id", "")),
                    "target_location_title": str(action.get("target_location_title", "")),
                    "target_subregion_id": str(action.get("target_subregion_id", "")),
                    "target_subregion_name": str(action.get("target_subregion_name", "")),
                    "target_x": round(float(action.get("target_x", 0.0)), 1),
                    "target_y": round(float(action.get("target_y", 0.0)), 1),
                    "response_mode": str(action.get("response_mode", "")),
                    "response_actor_ids": list(action.get("response_actor_ids", [])),
                    "response_note": str(action.get("response_note", "")),
                    "response_target_x": round(float(action.get("response_target_x", 0.0)), 1),
                    "response_target_y": round(float(action.get("response_target_y", 0.0)), 1),
                    "effective_support_threshold": round(float(action.get("effective_support_threshold", 0.0)), 3),
                    "effective_commitment_threshold": round(float(action.get("effective_commitment_threshold", 0.0)), 3),
                    "effective_turnout_threshold": round(float(action.get("effective_turnout_threshold", 0.0)), 3),
                    "player_threshold_shift": round(float(action.get("player_threshold_shift", 0.0)), 3),
                    "player_support": round(float(action.get("player_support", 0.0)), 3),
                    "player_mediation": round(float(action.get("player_mediation", 0.0)), 3),
                    "player_suppression": round(float(action.get("player_suppression", 0.0)), 3),
                    "resolution_kind": resolution_kind,
                    "resolution_label": str(action.get("resolution_label", "")),
                    "resolution_note": str(action.get("resolution_note", "")),
                    "resolution_tick": int(action.get("resolution_tick", 0)),
                    "source_topic_ids": list(action.get("source_topic_ids", [])),
                    "source_norm_ids": list(action.get("source_norm_ids", [])),
                }
            )
        rows.sort(
            key=lambda item: (
                self._collective_stage_rank(str(item.get("stage", ""))),
                float(item.get("heat", 0.0)),
                float(item.get("support", 0.0)),
            ),
            reverse=True,
        )
        return rows[:limit]

    def _npc_collective_digest(self, npc: dict[str, Any]) -> str:
        district = str(npc.get("district", ""))
        rows = self._active_collective_actions_view(limit=3, district_name=district)
        pieces: list[str] = []
        for row in rows[:2]:
            label = str(row.get("label", "")).strip()
            if not label:
                continue
            stage = str(row.get("stage_label", "听说"))
            support = int(round(float(row.get("support", 0.0)) * 100))
            commit = int(round(float(row.get("commitment", 0.0)) * 100))
            pieces.append(f"{label}(阶{stage}|支{support}|诺{commit})")
        return "；".join(pieces) if pieces else "暂无成形集体行动"

    def _coerce_collective_action_mode(
        self,
        value: str,
        npc: dict[str, Any],
        topic: dict[str, Any],
        norm: dict[str, Any] | None,
        topic_action: dict[str, Any],
        norm_action: dict[str, Any],
    ) -> str:
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
        if lowered in mapping:
            return mapping[lowered]
        role = str(npc.get("role", ""))
        kind = self._collective_kind_from_topic(topic, norm)
        pressure = float(npc.get("debt", 0)) / 120.0 + float(npc.get("hunger", 0)) / 100.0 + float(npc.get("fear", 0)) / 180.0
        if role in {"工会领袖", "记者"} and kind in {"strike", "meeting", "rally"}:
            return "organize" if str(norm_action.get("mode", "")) in {"reinforce", "seed"} or str(topic_action.get("mode", "")) == "amplify" else "support"
        if role in {"工人", "临时工"} and kind in {"strike", "meeting"}:
            if pressure >= 1.0 and str(norm_action.get("mode", "")) in {"reinforce", "seed"}:
                return "commit"
            if pressure >= 0.48:
                return "support"
            return "hear"
        if role in {"老板", "代理人", "银行经理"} and kind in {"strike", "rally"}:
            return "suppress"
        if str(topic_action.get("mode", "")) in {"share", "amplify"} and str(norm_action.get("mode", "")) in {"reinforce", "seed"}:
            return "support"
        if str(topic_action.get("mode", "")) in {"question", "deny"} and role in {"老板", "代理人", "银行经理"}:
            return "suppress"
        if kind:
            return "hear"
        return "avoid"

    def _coerce_collective_kind(self, value: str, topic: dict[str, Any], norm: dict[str, Any] | None) -> str:
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
        if lowered in mapping:
            return mapping[lowered]
        return self._collective_kind_from_topic(topic, norm)

    def _match_collective_action(self, topic: dict[str, Any], district_name: str, kind_hint: str = "") -> dict[str, Any] | None:
        topic_id = str(topic.get("id", ""))
        rows = self._active_collective_actions_view(limit=8, district_name=district_name)
        for row in rows:
            if topic_id and topic_id in [str(value) for value in row.get("source_topic_ids", [])]:
                return row
        for row in rows:
            if kind_hint and str(row.get("kind", "")) != kind_hint:
                continue
            return row
        return None

    def _coerce_npc_collective_action(
        self,
        raw: Any,
        npc: dict[str, Any],
        topic: dict[str, Any],
        norm: dict[str, Any] | None,
        topic_action: dict[str, Any],
        norm_action: dict[str, Any],
    ) -> dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        kind = self._coerce_collective_kind(str(payload.get("kind", "")), topic, norm)
        mode = self._coerce_collective_action_mode(str(payload.get("mode", "")), npc, topic, norm, topic_action, norm_action)
        matched = self._match_collective_action(topic, str(npc.get("district", "")), kind)
        action_id = str(payload.get("action_id", "")).strip() or str((matched or {}).get("id", ""))
        base_intensity = {
            "hear": 0.22,
            "support": 0.48,
            "commit": 0.62,
            "attend": 0.72,
            "organize": 0.78,
            "suppress": 0.58,
            "avoid": 0.08,
        }.get(mode, 0.2)
        intensity = float(payload.get("intensity", topic_action.get("intensity", norm_action.get("intensity", base_intensity))))
        note = str(payload.get("note", "")).strip()
        return {
            "mode": mode,
            "action_id": action_id,
            "kind": kind,
            "intensity": round(max(0.0, min(1.0, intensity)), 3),
            "note": note,
        }

    def _materialize_collective_action(
        self,
        npc: dict[str, Any],
        topic: dict[str, Any],
        norm: dict[str, Any] | None,
        collective_action: dict[str, Any],
    ) -> dict[str, Any] | None:
        action_id = str(collective_action.get("action_id", "")).strip()
        existing = self._collective_row_by_id(action_id)
        if existing:
            return existing
        kind_hint = str(collective_action.get("kind", "")).strip()
        if topic or norm:
            seeded = self._upsert_collective_seed(
                topic,
                norm,
                max(0.18, float(collective_action.get("intensity", 0.18)) * 0.7),
                kind_hint,
            )
            if seeded:
                return seeded
        matched = self._match_collective_action(topic, str(npc.get("district", "")), kind_hint)
        if matched:
            return self._collective_row_by_id(str(matched.get("id", "")))
        return None

    def _apply_collective_action(
        self,
        npc: dict[str, Any],
        topic: dict[str, Any],
        norm: dict[str, Any] | None,
        collective_action: dict[str, Any],
    ) -> dict[str, Any] | None:
        mode = str(collective_action.get("mode", "avoid"))
        if mode == "avoid" and not str(collective_action.get("action_id", "")).strip() and not str(collective_action.get("kind", "")).strip():
            return None
        action = self._materialize_collective_action(npc, topic, norm, collective_action)
        if not action:
            return None
        if str(action.get("resolution_kind", "")):
            return action
        npc_id = str(npc.get("id", ""))
        intensity = float(collective_action.get("intensity", 0.2))
        if mode == "hear":
            action["heard_ids"] = self._dedupe_id_list([npc_id, *list(action.get("heard_ids", []))])
            action["heat"] = round(min(1.0, float(action.get("heat", 0.0)) + 0.01 + intensity * 0.02), 3)
        elif mode == "support":
            action["heard_ids"] = self._dedupe_id_list([npc_id, *list(action.get("heard_ids", []))])
            action["supporter_ids"] = self._dedupe_id_list([npc_id, *list(action.get("supporter_ids", []))])
            action["support"] = round(min(1.0, float(action.get("support", 0.0)) + 0.02 + intensity * 0.04), 3)
        elif mode == "commit":
            action["heard_ids"] = self._dedupe_id_list([npc_id, *list(action.get("heard_ids", []))])
            action["supporter_ids"] = self._dedupe_id_list([npc_id, *list(action.get("supporter_ids", []))])
            action["committed_ids"] = self._dedupe_id_list([npc_id, *list(action.get("committed_ids", []))])
            action["commitment"] = round(min(1.0, float(action.get("commitment", 0.0)) + 0.02 + intensity * 0.05), 3)
        elif mode == "attend":
            action["heard_ids"] = self._dedupe_id_list([npc_id, *list(action.get("heard_ids", []))])
            action["supporter_ids"] = self._dedupe_id_list([npc_id, *list(action.get("supporter_ids", []))])
            action["committed_ids"] = self._dedupe_id_list([npc_id, *list(action.get("committed_ids", []))])
            action["attendee_ids"] = self._dedupe_id_list([npc_id, *list(action.get("attendee_ids", []))])
            action["turnout"] = round(min(1.0, float(action.get("turnout", 0.0)) + 0.03 + intensity * 0.05), 3)
        elif mode == "organize":
            action["heard_ids"] = self._dedupe_id_list([npc_id, *list(action.get("heard_ids", []))])
            action["supporter_ids"] = self._dedupe_id_list([npc_id, *list(action.get("supporter_ids", []))])
            action["committed_ids"] = self._dedupe_id_list([npc_id, *list(action.get("committed_ids", []))])
            action["organizer_ids"] = self._dedupe_id_list([npc_id, *list(action.get("organizer_ids", []))])
            action["support"] = round(min(1.0, float(action.get("support", 0.0)) + 0.03 + intensity * 0.05), 3)
            action["commitment"] = round(min(1.0, float(action.get("commitment", 0.0)) + 0.01 + intensity * 0.04), 3)
        elif mode == "suppress":
            action["suppression_ids"] = self._dedupe_id_list([npc_id, *list(action.get("suppression_ids", []))])
            action["heat"] = round(max(0.0, float(action.get("heat", 0.0)) - 0.01 + intensity * 0.01), 3)
            action["support"] = round(max(0.0, float(action.get("support", 0.0)) - 0.01 - intensity * 0.03), 3)
            action["risk"] = round(min(1.0, float(action.get("risk", 0.0)) + 0.02 + intensity * 0.05), 3)
        action["last_actor_id"] = npc_id
        action["last_action"] = mode
        action["last_tick"] = self._world_tick()
        self._refresh_collective_action_row(action)
        district = str(action.get("district", npc.get("district", "")))
        kind = str(action.get("kind", ""))
        if kind in {"strike", "meeting"}:
            self._bump_district_signal(district, "labor_heat", 0.03 + intensity * (0.04 if mode in {"commit", "attend", "organize"} else 0.02))
            self._bump_district_signal(district, "gossip", 0.01 + intensity * 0.02)
        elif kind == "rally":
            self._bump_district_signal(district, "gossip", 0.02 + intensity * 0.03)
            self._bump_district_signal(district, "fear", 0.01 + intensity * (0.03 if mode == "suppress" else 0.01))
        elif kind == "party":
            self._bump_district_signal(district, "gossip", 0.02 + intensity * 0.02)
            self._bump_district_signal(district, "trade_heat", 0.01 + intensity * 0.02)
        if kind == "strike" and mode in {"commit", "attend", "organize"}:
            self.state["macro"]["worker_unrest"] = int(min(100, float(self.state["macro"].get("worker_unrest", 0.0)) + 1.0 + intensity * 1.4))
        if kind == "rally" and mode in {"support", "organize", "attend"}:
            self.state["macro"]["media_sentiment"] = int(min(100, max(0, float(self.state["macro"].get("media_sentiment", 0.0)) + 0.6 + intensity * 0.9)))
        if mode == "suppress":
            self.state["macro"]["worker_unrest"] = int(min(100, float(self.state["macro"].get("worker_unrest", 0.0)) + intensity * 0.8))
            self._bump_district_signal(district, "fear", 0.02 + intensity * 0.04)
        self._sort_collective_registry()
        return copy.deepcopy(action)

    def _apply_intel_packet(
        self,
        packet: dict[str, Any],
        *,
        to_player: bool,
        promote_news: bool,
        intensity: float,
    ) -> None:
        topic_row = self._record_topic_from_packet(packet, intensity)
        enriched_packet = copy.deepcopy(packet)
        enriched_packet["topic_id"] = str(topic_row.get("id", ""))
        enriched_packet["topic_label"] = str(topic_row.get("label", ""))
        enriched_packet["topic_kind"] = str(topic_row.get("kind", ""))
        enriched_packet["topic_status"] = str(topic_row.get("status", ""))
        self.state["rumor_log"].insert(0, enriched_packet)
        self.state["rumor_log"] = self.state["rumor_log"][:12]

        for good_name, delta in packet.get("goods_delta", {}).items():
            current = float(self.state["market_pressure"]["goods"].get(good_name, 0.0))
            self.state["market_pressure"]["goods"][good_name] = max(-0.35, min(0.35, current + float(delta) * intensity))
        for stock_name, delta in packet.get("stocks_delta", {}).items():
            current = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0))
            self.state["market_pressure"]["stocks"][stock_name] = max(-0.35, min(0.35, current + float(delta) * intensity))
        for family_name, delta in packet.get("family_delta", {}).items():
            current = float(self.state["market_pressure"]["families"].get(family_name, 0.0))
            self.state["market_pressure"]["families"][family_name] = max(-0.35, min(0.35, current + float(delta) * intensity))
            family = self._find_by_name(self.state["families"], family_name)
            if family:
                family["hidden_action"] = f"沿着 {packet.get('district', '街区')} 的风声试探仓位"
        for key, delta in packet.get("macro_delta", {}).items():
            if key == "interest_rate":
                self.state["macro"][key] = round(max(0.8, min(5.5, float(self.state["macro"].get(key, 0.0)) + float(delta) * intensity)), 2)
            else:
                self.state["macro"][key] = int(max(0, min(100, float(self.state["macro"].get(key, 0.0)) + float(delta) * intensity)))

        if to_player:
            player = self.state["player"]
            player["rumors"].append(enriched_packet["line"])
            player["rumors"] = player["rumors"][-6:]

        self.state["local_broadcasts"].insert(
            0,
            {
                "source": enriched_packet.get("source", "rumor"),
                "district": enriched_packet.get("district", ""),
                "radius": 150,
                "line": enriched_packet.get("line", ""),
                "type": "rumor",
            },
        )
        self.state["local_broadcasts"] = self.state["local_broadcasts"][:18]

        if promote_news:
            self.state["global_news"].insert(0, self._compose_packet_news(enriched_packet))
            self.state["global_news"] = self.state["global_news"][:8]

        if enriched_packet.get("district"):
            district = self._find_by_name(self.state["districts"], enriched_packet["district"])
            if district and district.get("state") == "normal" and intensity >= 1.0:
                district["state"] = "tense"
            self._bump_district_signal(enriched_packet["district"], "gossip", 0.08 * intensity)
            if "股票" in enriched_packet.get("tags", []) or "金融" in enriched_packet.get("tags", []) or "媒体" in enriched_packet.get("tags", []):
                self._bump_district_signal(enriched_packet["district"], "liquidity", 0.06 * intensity)
            if "底层" in enriched_packet.get("tags", []) or "工厂" in enriched_packet.get("tags", []) or "港口" in enriched_packet.get("tags", []):
                self._bump_district_signal(enriched_packet["district"], "fear", 0.05 * intensity)

        return topic_row

    def _compose_packet_news(self, packet: dict[str, Any]) -> dict[str, Any]:
        generated = self.ark.generate_news_copy(
            {
                "event_name": packet.get("title", packet.get("source", "街头风声")),
                "district": packet.get("district", ""),
                "macro": copy.deepcopy(self.state.get("macro", {})),
                "stocks": [
                    {
                        "name": str(row.get("name", "")),
                        "current_price": int(row.get("current_price", 0)),
                        "market_sentiment": str(row.get("market_sentiment", "")),
                    }
                    for row in self.state.get("stocks", [])
                ],
                "scene_observation": copy.deepcopy(self.state.get("scene_observation", {})),
                "source_line": packet.get("line", ""),
                "source_body": packet.get("body", ""),
                "tags": list(packet.get("tags", [])),
                "goods_delta": copy.deepcopy(packet.get("goods_delta", {})),
                "stocks_delta": copy.deepcopy(packet.get("stocks_delta", {})),
                "family_delta": copy.deepcopy(packet.get("family_delta", {})),
            }
        )
        if generated:
            generated["scope"] = str(packet.get("scope", generated.get("scope", "district")))
            generated["tags"] = list(generated.get("tags", packet.get("tags", [])))
            return generated
        return {
            "title": packet.get("title", "街头风声"),
            "body": packet.get("body", packet.get("line", "")),
            "tags": packet.get("tags", []),
            "scope": packet.get("scope", "district"),
        }

    def _apply_player_talk_fallout(
        self,
        npc: dict[str, Any],
        topic: dict[str, Any],
        intel: dict[str, Any],
        strength: float,
        scene_observation: dict[str, Any],
        spoken_line: str,
        approach: str,
        intent: str,
    ) -> int:
        scene_context = scene_observation.get("scene_context", {}) if isinstance(scene_observation, dict) else {}
        nearby_rows = scene_context.get("nearby_npcs", []) if isinstance(scene_context, dict) else []
        if not isinstance(nearby_rows, list):
            return 0
        heard_count = 0
        overheard_ids: list[str] = []
        nervous_topic = str(topic.get("kind", "")) in {"panic", "family", "company", "institution"}
        market_topic = str(topic.get("kind", "")) in {"asset", "company", "family", "institution"}
        for row in nearby_rows:
            if not isinstance(row, dict):
                continue
            listener_id = str(row.get("id", "")).strip()
            if not listener_id or listener_id == str(npc.get("id", "")):
                continue
            listener = self._find_npc(listener_id)
            if not listener or str(listener.get("district", "")) != str(npc.get("district", "")):
                continue
            heard_count += 1
            overheard_ids.append(listener_id)
            listener["memory_tags"] = self._push_memory(listener.get("memory_tags", []), f"heard_player:{npc.get('id', '')}")
            listener["heard_topic_ids"] = self._push_memory(listener.get("heard_topic_ids", []), str(topic.get("id", "")))
            if nervous_topic:
                listener["fear"] = min(100, int(listener.get("fear", 0)) + max(1, int(round(strength * 6))))
            if market_topic:
                listener["greed"] = min(100, int(listener.get("greed", 0)) + max(1, int(round(strength * 4))))
                self._bump_district_signal(str(listener.get("district", "")), "liquidity", 0.03 * strength)
            if strength > 0.18 and self.random.random() < min(0.95, float(listener.get("rumor_susceptibility", 0.35)) + strength * 0.35):
                listener["speech_lines"] = [f"旁边有人刚聊到：{spoken_line[:22]}", *list(listener.get("speech_lines", []))[:2]]
            self._remember_npc_event(
                listener,
                "heard_player_talk",
                {
                    "speaker": str(npc.get("name", "")),
                    "speaker_id": str(npc.get("id", "")),
                    "topic_id": str(topic.get("id", "")),
                    "approach": approach,
                    "intent": intent,
                },
            )
        if heard_count:
            self._bump_district_signal(str(npc.get("district", "")), "gossip", 0.05 * heard_count * max(0.6, strength))
        if heard_count >= 2 and strength >= 0.42:
            echoed_packet = copy.deepcopy(intel)
            echoed_packet["source"] = f"{npc.get('name', '那只动物')}身边围观的人"
            echoed_packet["title"] = f"{npc.get('district', '街区')} 围观声扩开了"
            echoed_packet["body"] = f"你和 {npc.get('name', '那只动物')} 的交谈被旁边的人听进去了：{intel.get('line', spoken_line)}"
            echoed_packet["line"] = f"围观圈里有人开始接话：{intel.get('line', spoken_line)}"
            self._apply_intel_packet(
                echoed_packet,
                to_player=False,
                promote_news=strength >= 0.78 or str(intel.get("scope", "district")) == "city",
                intensity=min(0.82, strength * 0.68),
            )
        self.state["last_dialogue_heard_by"] = overheard_ids[:4]
        return heard_count

    def _apply_intraday_market_move(self, reason: str, decay: float) -> None:
        moved: list[str] = []
        _, shadow = self._derive_story_reputation()
        st = float(shadow.get("ST", 1.0))
        sui = float(shadow.get("SUI", 15.0))
        s_dbh = int(shadow.get("S_DBH", 10))
        for good in self.state["goods"]:
            pressure = float(self.state["market_pressure"]["goods"].get(good["name"], 0.0))
            if abs(pressure) < 0.015:
                continue
            previous = int(good["current_price"])
            reference_price = float(good.get("reference_price", good["current_price"]))
            good["reference_price"] = reference_price
            mispricing = (float(good["current_price"]) - reference_price) / max(reference_price, 1.0)
            weather_drag = 0.02 if str(self.state.get("weather", {}).get("kind", "sunny")) in {"rain", "snow", "dust"} else 0.0
            profit_taking = max(0.0, mispricing - 0.18) * 0.16
            factor = 1.0 + pressure * 0.16 + self.random.uniform(-0.01, 0.01) - mispricing * 0.12 - weather_drag - profit_taking
            factor = max(0.92, min(1.08, factor))
            good["current_price"] = max(1, int(round(good["current_price"] * factor)))
            good["reference_price"] = round(reference_price * 0.99 + float(good["current_price"]) * 0.01, 3)
            good["price_trend"] = "涨" if good["current_price"] > previous else "跌" if good["current_price"] < previous else "平"
            if good["current_price"] != previous:
                moved.append(f"{good['name']}{good['price_trend']}到{good['current_price']}")
            self.state["market_pressure"]["goods"][good["name"]] = pressure * decay
        for stock in self.state["stocks"]:
            pressure = float(self.state["market_pressure"]["stocks"].get(stock["name"], 0.0))
            ticker = str(stock.get("ticker", "")).upper()
            story_bias = 0.0
            if ticker == "SWC":
                story_bias += 0.012 + max(0.0, st - 1.0) * 0.01
                story_bias -= max(0.0, sui - 70.0) * 0.0007
            elif ticker == "TSL":
                story_bias += 0.016 if s_dbh > 60 else 0.0
                story_bias -= max(0.0, sui - 72.0) * 0.0012
            elif ticker == "AMB":
                story_bias += 0.012 if sui < 35.0 else -0.012 - max(0.0, st - 1.3) * 0.01
            effective_pressure = pressure + story_bias
            if abs(effective_pressure) < 0.015:
                self._append_stock_history_point(str(stock.get("name", "")), int(stock.get("current_price", 0)))
                continue
            previous = int(stock["current_price"])
            reference_price = float(stock.get("reference_price", stock["current_price"]))
            stock["reference_price"] = reference_price
            mispricing = (float(stock["current_price"]) - reference_price) / max(reference_price, 1.0)
            interest_drag = max(0.0, float(self.state.get("macro", {}).get("interest_rate", 4.0)) - 4.2) * 0.006
            profit_taking = max(0.0, mispricing - 0.18) * 0.24
            factor = 1.0 + effective_pressure * 0.14 + self.random.uniform(-0.012, 0.012) - mispricing * 0.16 - interest_drag - profit_taking
            factor = max(0.9, min(1.1, factor))
            stock["current_price"] = max(3, int(round(stock["current_price"] * factor)))
            stock["reference_price"] = round(reference_price * 0.992 + float(stock["current_price"]) * 0.008, 3)
            stock["market_sentiment"] = "乐观" if stock["current_price"] > previous else "恐慌" if stock["current_price"] < previous else "谨慎"
            move_ratio = abs(int(stock["current_price"]) - previous) / float(max(previous, 1))
            held = int(self._ensure_player_financial_state().get("stock_holdings", {}).get(str(stock.get("name", "")), 0))
            if sui >= 80.0 and move_ratio >= 0.10 and held > 0 and self.random.random() < 0.5:
                self._force_dark_pool_auto_close(stock, "SUI 风险风控")
            if stock["current_price"] != previous:
                moved.append(f"{stock['name']}{'涨' if stock['current_price'] > previous else '跌'}到{stock['current_price']}")
            self._append_stock_history_point(str(stock.get("name", "")), int(stock["current_price"]))
            self.state["market_pressure"]["stocks"][stock["name"]] = pressure * decay
        if moved and reason in {"gather_info", "player_talk", "ai_pulse", "npc_conversation"}:
            self.state["global_news"].insert(
                0,
                {
                    "title": "盘口先动了一下",
                    "body": "、".join(moved[:3]) + "，消息已经开始写进价格。",
                    "tags": ["盘口", "风声"],
                    "scope": "district",
                },
            )
            self.state["global_news"] = self.state["global_news"][:8]

    def _bump_district_signal(self, district_name: str, key: str, amount: float) -> None:
        signals = self.state.get("district_signals", {}).get(district_name)
        if not signals or key not in signals:
            return
        signals[key] = max(0.0, min(5.0, float(signals.get(key, 0.0)) + amount))

    def _decay_district_signals(self) -> None:
        for signal_map in self.state.get("district_signals", {}).values():
            for key, value in signal_map.items():
                signal_map[key] = round(float(value) * 0.74, 3)

    def _resolve_talk_topic(self, npc: dict[str, Any], topic_id: str, district_name: str) -> dict[str, Any]:
        topic = self._find_by_id(self.state.get("talk_topics", []), topic_id) if topic_id else None
        if topic and (not topic.get("npc_ids") or npc["id"] in topic.get("npc_ids", [])):
            return topic
        npc_topics = self._talk_topics_for_npc(npc["id"], district_name)
        if npc_topics:
            return npc_topics[0]
        return {
            "id": "generic_wind",
            "kind": "rumor",
            "district": district_name,
            "label": f"{district_name} 风向",
            "summary": f"{district_name} 眼下每个人都在看别人先怎么动。",
            "heat": 1.0,
            "npc_ids": [npc["id"]],
            "impacts": {},
            "approaches": ["cautious", "friendly", "hardball"],
        }

    def _select_player_talk_topic(
        self,
        npc: dict[str, Any],
        topic_id: str,
        district_name: str,
        player_input: str = "",
        intent: str = "",
    ) -> dict[str, Any]:
        resolved = self._resolve_talk_topic(npc, topic_id, district_name)
        if topic_id:
            return resolved
        npc_topics = self._talk_topics_for_npc(str(npc.get("id", "")), district_name)
        personal_topics = self._npc_personal_topics(npc)
        hint_flags = self._player_talk_hint_flags(player_input, intent)
        hint = f"{player_input} {intent}".lower()
        domains = {str(value) for value in npc.get("information_domain", [])}
        role = str(npc.get("role", ""))
        market_roles = {"投机者", "银行经理", "代理人", "记者", "老板"}
        market_hint = any(token in hint for token in ["票", "股", "盘口", "仓", "价格", "涨", "跌", "做局", "利息", "放风"])
        wants_market = market_hint
        wants_actor = any(token in hint for token in ["谁", "哪家", "哪边", "做局", "放风", "护盘"])
        wants_market = bool(hint_flags.get("market", False))
        wants_actor = bool(hint_flags.get("actor", False))
        wants_personal = bool(hint_flags.get("personal", False)) and not wants_market
        if wants_personal:
            for topic in personal_topics:
                if str(topic.get("kind", "")) not in {"position", "asset", "finance", "company", "institution"}:
                    return topic
            if personal_topics:
                return personal_topics[0]
            for topic in npc_topics:
                if str(topic.get("kind", "")) in {"identity", "livelihood", "routine", "relationship", "rumor", "district", "ration", "labor"}:
                    return topic
        if wants_market:
            for topic in personal_topics:
                if str(topic.get("kind", "")) == "position":
                    return topic
            for topic in npc_topics:
                if str(topic.get("kind", "")) in {"asset", "finance", "company", "institution", "position"}:
                    return topic
        if wants_actor:
            for topic in npc_topics:
                if str(topic.get("kind", "")) in {"institution", "company", "family", "finance", "asset"}:
                    return topic
        if str(resolved.get("id", "")) == "generic_wind" or str(resolved.get("kind", "")) == "panic":
            if personal_topics:
                return personal_topics[0]
            for topic in npc_topics:
                if str(topic.get("kind", "")) != "panic":
                    return topic
        if not wants_market and ("stock" in domains or role in market_roles):
            for topic in personal_topics:
                if str(topic.get("kind", "")) not in {"position", "asset", "finance"}:
                    return topic
        return resolved

    def _player_talk_hint_flags(self, player_input: str, intent: str = "") -> dict[str, bool]:
        hint = f"{player_input} {intent}".lower().strip()
        greeting = any(token in hint for token in ["你好", "您好", "嗨", "嘿", "早", "晚上好", "在吗", "打扰了", "借一步说话"])
        market = any(token in hint for token in ["股", "票", "盘", "庄", "价格", "涨", "跌", "仓", "买", "卖", "做空", "拉盘", "消息", "放风", "账面", "行情"])
        actor = any(token in hint for token in ["谁", "哪家", "背后", "幕后", "主使", "替谁", "跟谁", "谁的人", "站哪边"])
        personal = greeting or any(
            token in hint
            for token in ["你是", "你谁", "叫什么", "叫啥", "从哪", "哪来的", "住哪", "做什么", "干什么", "忙什么", "最近", "刚才", "怎么了", "为什么", "还好吗", "累不累"]
        )
        return {"greeting": greeting, "market": market, "actor": actor, "personal": personal}

    def _action_contract_label(self, action_type: str) -> str:
        labels = {
            "work": "去干活",
            "gather_info": "打听风声",
            "rest": "歇一歇",
            "cook_meal": "做一顿热饭",
            "search_home": "翻箱柜",
            "review_ledger": "记账理线索",
        }
        key = str(action_type or "").strip()
        return labels.get(key, key or "行动")

    def _parse_contract_confirmation(self, player_input: str) -> str:
        text = str(player_input or "").strip()
        if not text:
            return ""
        if re.search(r"^(确认|确定|行|好|可以|开始|走|去吧|对)$", text):
            return "confirm"
        if re.search(r"^(算了|不了|取消|拒绝|先别|不用|停)$", text):
            return "reject"
        if re.search(r"^不(了|用|行|要|去|必)", text):
            return "reject"
        low = text.lower()
        if any(token in low for token in ["确认", "确定", "开始", "就现在", "可以", "走吧"]):
            return "confirm"
        if any(token in low for token in ["算了", "取消", "先别", "不用", "不去了"]):
            return "reject"
        return ""

    def _detect_action_contract_request(self, player_input: str) -> dict[str, Any] | None:
        text = str(player_input or "").strip()
        if not text:
            return None
        low = text.lower()
        if any(token in low for token in ["打工", "工作", "干活", "上工", "去干活"]):
            return {"action_type": "work", "payload": {}}
        if any(token in low for token in ["打听", "打探", "买消息", "买情报", "听风声", "抄墙报"]):
            return {"action_type": "gather_info", "payload": {}}
        if any(token in low for token in ["休息", "睡觉", "歇会", "歇一会", "回去躺", "回屋歇"]):
            return {"action_type": "rest", "payload": {}}
        if any(token in low for token in ["做饭", "煮饭", "弄点吃的", "吃点热的", "开火"]):
            return {"action_type": "cook_meal", "payload": {}}
        if any(token in low for token in ["搜屋", "搜家", "翻箱", "翻箱倒柜", "找找看", "搜一搜"]):
            return {"action_type": "search_home", "payload": {}}
        if any(token in low for token in ["看账", "翻账", "记账", "账桌", "理一理账"]):
            return {"action_type": "review_ledger", "payload": {}}
        return None

    def _action_contract_prompt(self, npc: dict[str, Any], district: str, action_type: str) -> str:
        npc_name = str(npc.get("name", "")) or "对方"
        label = self._action_contract_label(action_type)
        ap_note = "会消耗 1 AP。"
        extra = ""
        if action_type == "gather_info":
            extra = "要花 2 铜币。"
        if action_type == "work":
            extra = f"地点在 {district}。"
        extra_note = f"{extra} " if extra else ""
        return f"{npc_name}：你是想现在{label}？{extra_note}{ap_note}确认就回“确认”，不做就回“算了”。"

    def _maybe_handle_action_contract_layer(self, npc: dict[str, Any], district: str, player_input: str) -> ActionResult | dict[str, Any] | None:
        npc_id = str(npc.get("id", "")).strip()
        if not npc_id:
            return None
        contracts: dict[str, Any] = dict(self.state.get("pending_action_contracts", {}))
        pending = contracts.get(npc_id)
        now = time.time()
        if isinstance(pending, dict):
            expires_at = float(pending.get("expires_at", 0.0) or 0.0)
            if expires_at and now > expires_at:
                contracts.pop(npc_id, None)
                self.state["pending_action_contracts"] = contracts
                pending = None
        if isinstance(pending, dict):
            decision = self._parse_contract_confirmation(player_input)
            action_type = str(pending.get("action_type", "")).strip()
            payload = dict(pending.get("payload", {}) or {})
            contract_district = str(pending.get("district", district)).strip() or district
            if decision == "confirm":
                contracts.pop(npc_id, None)
                self.state["pending_action_contracts"] = contracts
                return {
                    "_execute": True,
                    "npc_id": npc_id,
                    "npc_name": str(npc.get("name", "")),
                    "npc_name_fallback": str(npc.get("name", "")),
                    "district": contract_district,
                    "action_type": action_type,
                    "payload": payload,
                    "player_line": player_input,
                }
            if decision == "reject":
                contracts.pop(npc_id, None)
                self.state["pending_action_contracts"] = contracts
                self.state["last_dialogue"] = {
                    "title": "行动契约：已取消",
                    "tone": "conversation",
                    "lines": [player_input, f"{str(npc.get('name','对方'))}：行，先不动。你想聊别的就直说。"],
                    "layer": "action_contract",
                    "contract": {"status": "cancelled", "action_type": action_type, "district": contract_district, "payload": payload},
                    "npc_id": npc_id,
                    "npc_name": str(npc.get("name", "")),
                    "district": contract_district,
                    "player_input": player_input,
                    "response_state": "action_contract_cancelled",
                }
                return ActionResult("行动已取消。", self._snapshot_after_refresh(rebuild_agent_prompts=False))
            self.state["last_dialogue"] = {
                "title": f"行动契约：确认{self._action_contract_label(action_type)}",
                "tone": "conversation",
                "lines": [player_input, self._action_contract_prompt(npc, contract_district, action_type)],
                "layer": "action_contract",
                "contract": {"status": "pending", "action_type": action_type, "district": contract_district, "payload": payload},
                "npc_id": npc_id,
                "npc_name": str(npc.get("name", "")),
                "district": contract_district,
                "player_input": player_input,
                "response_state": "action_contract_pending",
            }
            return ActionResult("等待确认。", self._snapshot_after_refresh(rebuild_agent_prompts=False))

        requested = self._detect_action_contract_request(player_input)
        if not requested:
            return None
        action_type = str(requested.get("action_type", "")).strip()
        payload = dict(requested.get("payload", {}) or {})
        contracts[npc_id] = {
            "action_type": action_type,
            "district": district,
            "payload": payload,
            "created_at": now,
            "expires_at": now + 45.0,
        }
        self.state["pending_action_contracts"] = contracts
        self.state["last_dialogue"] = {
            "title": f"行动契约：确认{self._action_contract_label(action_type)}",
            "tone": "conversation",
            "lines": [player_input, self._action_contract_prompt(npc, district, action_type)],
            "layer": "action_contract",
            "contract": {"status": "pending", "action_type": action_type, "district": district, "payload": payload},
            "npc_id": npc_id,
            "npc_name": str(npc.get("name", "")),
            "district": district,
            "player_input": player_input,
            "response_state": "action_contract_created",
        }
        return ActionResult("需要确认。", self._snapshot_after_refresh(rebuild_agent_prompts=False))

    def _evaluate_talk_approach(self, npc: dict[str, Any], topic: dict[str, Any], approach: str) -> tuple[int, float, str]:
        relation = int(npc.get("player_relation", 0))
        role = str(npc.get("role", ""))
        memory = self._npc_player_memory(npc)
        favorability = self._npc_favorability_state(npc)
        profile = self._npc_prompt_profile(npc)
        sensitivity = 0
        if topic.get("kind") in {"family", "panic", "company"}:
            sensitivity += 1
        if role in {"代理人", "银行经理", "老板"}:
            sensitivity += 1
        if approach == "friendly":
            trust_delta = 2 if role in {"工人", "临时工", "店主", "记者"} else 1
            intel_strength = 1.0 if relation >= 0 else 0.8
            intel_strength += min(0.12, float(memory.get("trust_streak", 0)) * 0.02)
            intel_strength += float(favorability.get("disclosure_willingness", 0.0)) * 0.12
            openness = "open"
        elif approach == "hardball":
            trust_delta = -1 if sensitivity > 0 else 0
            intel_strength = 0.35 if sensitivity > 0 and relation < 5 else 0.72
            intel_strength -= min(0.18, float(memory.get("pressure_from_player", 0.0)) * 0.03)
            intel_strength -= float(favorability.get("resentment", 0.0)) * 0.08
            register = str(favorability.get("speech_register", ""))
            if register in {"owned", "bought"} and float(favorability.get("resentment", 0.0)) < 0.48:
                openness = "skeptical"
            else:
                openness = "guarded" if sensitivity > 0 or register in {"guarded", "hostile", "sullen"} else "skeptical"
        else:
            trust_delta = 1
            intel_strength = 0.88 if relation >= -1 else 0.72
            intel_strength += min(0.08, int(memory.get("intel_bought", 0)) * 0.015)
            intel_strength += float(favorability.get("disclosure_willingness", 0.0)) * 0.06
            register = str(favorability.get("speech_register", ""))
            if register in {"owned", "bought", "patronized"} and float(favorability.get("resentment", 0.0)) < 0.52:
                openness = "open"
            else:
                openness = "skeptical" if sensitivity > 0 or register == "guarded" else "open"
        return trust_delta, intel_strength, openness

    def _npc_player_memory(self, npc: dict[str, Any]) -> dict[str, Any]:
        memory = npc.get("player_memory", {})
        return memory if isinstance(memory, dict) else {}

    def _remember_player_talk(
        self,
        npc: dict[str, Any],
        topic: dict[str, Any],
        approach: str,
        intent: str,
        trust_delta: int,
        effective_strength: float,
    ) -> None:
        memory = self._npc_player_memory(npc)
        memory["talk_count"] = int(memory.get("talk_count", 0)) + 1
        if approach == "friendly":
            memory["friendly_count"] = int(memory.get("friendly_count", 0)) + 1
        if approach == "hardball":
            memory["hardball_count"] = int(memory.get("hardball_count", 0)) + 1
            memory["pressure_from_player"] = round(min(4.0, float(memory.get("pressure_from_player", 0.0)) + 0.75), 2)
        else:
            memory["pressure_from_player"] = round(max(0.0, float(memory.get("pressure_from_player", 0.0)) - 0.18), 2)
        if effective_strength >= 0.3:
            memory["intel_bought"] = int(memory.get("intel_bought", 0)) + 1
        streak = int(memory.get("trust_streak", 0))
        if trust_delta > 0:
            streak += 1
        elif trust_delta < 0:
            streak = max(0, streak - 1)
        memory["trust_streak"] = min(8, streak)
        memory["last_topic_id"] = str(topic.get("id", ""))
        memory["last_intent"] = intent
        memory["last_approach"] = approach
        memory["last_seen_day"] = int(self.state.get("day", 1))
        npc["player_memory"] = memory
        self._remember_npc_event(
            npc,
            "player_talk",
            {
                "topic_id": str(topic.get("id", "")),
                "topic_label": str(topic.get("label", "")),
                "approach": approach,
                "intent": intent,
                "sold_info": effective_strength >= 0.3,
                "trust_delta": trust_delta,
            },
        )

    def _remember_npc_event(self, npc: dict[str, Any], kind: str, payload: dict[str, Any]) -> None:
        memory_rows = npc.get("relationship_memory", [])
        rows = memory_rows if isinstance(memory_rows, list) else []
        entry = {
            "kind": kind,
            "day": int(self.state.get("day", 1)),
            "clock": self._clock_label(),
        }
        entry.update(payload)
        rows.insert(0, entry)
        npc["relationship_memory"] = rows[:8]

    def _append_dialogue_history(
        self,
        npc: dict[str, Any],
        counterpart_id: str,
        counterpart_name: str,
        speaker_line: str,
        reply_line: str,
        topic_id: str,
        topic_label: str,
        trigger: str,
        channel: str,
        counterpart_kind: str,
    ) -> None:
        rows = npc.get("dialogue_history", [])
        if not isinstance(rows, list):
            rows = []
        rows.insert(
            0,
            {
                "day": int(self.state.get("day", 1)),
                "clock": self._clock_label(),
                "counterpart_id": counterpart_id,
                "counterpart_name": counterpart_name,
                "counterpart_kind": counterpart_kind,
                "speaker_line": self._prefer_chinese_text(str(speaker_line or "").strip(), "")[:140],
                "reply_line": self._prefer_chinese_text(str(reply_line or "").strip(), "")[:140],
                "topic_id": topic_id,
                "topic_label": topic_label,
                "trigger": trigger[:64],
                "channel": channel,
            },
        )
        npc["dialogue_history"] = rows[:18]

    def _remember_local_memory(
        self,
        npc: dict[str, Any],
        *,
        kind: str,
        summary: str,
        counterpart_id: str = "",
        counterpart_name: str = "",
        topic_id: str = "",
        topic_label: str = "",
        tags: list[str] | None = None,
        salience: float = 0.45,
    ) -> None:
        cleaned = self._prefer_chinese_text(str(summary or "").strip(), "")
        if not cleaned:
            return
        rows = npc.get("local_memory_bank", [])
        if not isinstance(rows, list):
            rows = []
        entry = {
            "day": int(self.state.get("day", 1)),
            "clock": self._clock_label(),
            "kind": kind,
            "summary": cleaned[:160],
            "counterpart_id": counterpart_id,
            "counterpart_name": counterpart_name,
            "topic_id": topic_id,
            "topic_label": topic_label,
            "salience": round(max(0.0, min(1.0, salience)), 3),
            "tags": [str(tag).strip() for tag in (tags or []) if str(tag).strip()][:6],
            "last_seen_day": int(self.state.get("day", 1)),
        }
        rows.insert(0, entry)
        deduped: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str, str]] = set()
        for row in rows:
            key = (
                str(row.get("kind", "")),
                str(row.get("counterpart_id", "")),
                str(row.get("topic_id", "")),
                str(row.get("summary", "")),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(row)
            if len(deduped) >= 18:
                break
        npc["local_memory_bank"] = deduped

    def _dialogue_history_view(self, npc: dict[str, Any], counterpart_id: str = "", limit: int = 4) -> list[dict[str, Any]]:
        rows = npc.get("dialogue_history", [])
        if not isinstance(rows, list):
            return []
        filtered: list[dict[str, Any]] = []
        counterpart = str(counterpart_id).strip()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if counterpart and str(row.get("counterpart_id", "")) != counterpart:
                continue
            filtered.append(
                {
                    "day": int(row.get("day", 0)),
                    "clock": str(row.get("clock", "")),
                    "counterpart_name": str(row.get("counterpart_name", "")),
                    "speaker_line": str(row.get("speaker_line", "")),
                    "reply_line": str(row.get("reply_line", "")),
                    "topic_id": str(row.get("topic_id", "")),
                    "topic_label": str(row.get("topic_label", "")),
                    "trigger": str(row.get("trigger", "")),
                    "channel": str(row.get("channel", "")),
                }
            )
            if len(filtered) >= limit:
                break
        return filtered

    def _local_memory_view(self, npc: dict[str, Any], counterpart_id: str = "", topic_id: str = "", limit: int = 5) -> list[dict[str, Any]]:
        rows = npc.get("local_memory_bank", [])
        if not isinstance(rows, list):
            return []
        counterpart = str(counterpart_id).strip()
        topic = str(topic_id).strip()
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            score = float(row.get("salience", 0.3))
            if counterpart and str(row.get("counterpart_id", "")) == counterpart:
                score += 0.28
            if topic and str(row.get("topic_id", "")) == topic:
                score += 0.22
            if counterpart and str(row.get("counterpart_id", "")) not in {"", counterpart} and topic and str(row.get("topic_id", "")) not in {"", topic}:
                score -= 0.1
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected: list[dict[str, Any]] = []
        for _, row in scored[:limit]:
            selected.append(
                {
                    "day": int(row.get("day", 0)),
                    "clock": str(row.get("clock", "")),
                    "kind": str(row.get("kind", "")),
                    "summary": str(row.get("summary", "")),
                    "counterpart_name": str(row.get("counterpart_name", "")),
                    "topic_id": str(row.get("topic_id", "")),
                    "topic_label": str(row.get("topic_label", "")),
                    "salience": round(float(row.get("salience", 0.0)), 3),
                    "tags": list(row.get("tags", [])),
                }
            )
        return selected

    def _entity_brief_history(self, bucket_name: str, entity_id: str) -> list[dict[str, Any]]:
        bucket = self.state.get(bucket_name, {})
        if not isinstance(bucket, dict):
            return []
        rows = bucket.get(entity_id, [])
        return rows if isinstance(rows, list) else []

    def _append_entity_brief_history(self, bucket_name: str, entity_id: str, entry: dict[str, Any], limit: int = 4) -> None:
        if not entity_id:
            return
        bucket = self.state.setdefault(bucket_name, {})
        if not isinstance(bucket, dict):
            bucket = {}
            self.state[bucket_name] = bucket
        rows = bucket.get(entity_id, [])
        if not isinstance(rows, list):
            rows = []
        next_entry = {
            "day": int(self.state.get("day", 1)),
            "clock": self._clock_label(),
        }
        next_entry.update(entry)
        rows.insert(0, next_entry)
        bucket[entity_id] = rows[:limit]

    @staticmethod
    def _brief_history_summary(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
        if not rows:
            return ""
        latest = rows[0] if isinstance(rows[0], dict) else {}
        for key in keys:
            value = str(latest.get(key, "")).strip()
            if value:
                return value
        return ""

    @staticmethod
    def _dialogue_render_lines(lines: list[str], fallback_npc_name: str = "对方") -> list[str]:
        player_line = str(lines[0]).strip() if len(lines) > 0 else ""
        npc_line = str(lines[1]).strip() if len(lines) > 1 else ""
        if not player_line:
            player_line = "……"
        if not npc_line:
            npc_line = f"{fallback_npc_name}沉默了一下。"
        return [player_line[:220], npc_line[:220]]

    @staticmethod
    def _dialogue_render_lines(lines: list[str], fallback_npc_name: str = "对方") -> list[str]:
        player_line = str(lines[0]).strip() if len(lines) > 0 else ""
        npc_line = str(lines[1]).strip() if len(lines) > 1 else ""
        if not player_line:
            player_line = "你先打量了对方一眼，还没正式开口。"
        if not npc_line:
            npc_line = f"{fallback_npc_name}这轮没有说出完整的话。"
        return [player_line[:220], npc_line[:220]]

    def _dialogue_render_body(
        self,
        *,
        npc_name: str,
        topic_label: str,
        approach: str,
        render_lines: list[str],
        intel_note: str,
        world_effects: str,
        truth_profile: dict[str, Any],
    ) -> str:
        confidence_pct = int(round(float(truth_profile.get("confidence", 0.5)) * 100))
        truthfulness_pct = int(round(float(truth_profile.get("truthfulness", 0.5)) * 100))
        return (
            f"[b]话题[/b]：{topic_label}  [b]方式[/b]：{self._approach_label(approach)}\n\n"
            f"[b]你[/b]：{render_lines[0]}\n\n"
            f"[b]{npc_name}[/b]：{render_lines[1]}\n\n"
            f"[color=#6b4f2a][b]你实际拿到[/b][/color]\n{intel_note}\n"
            f"可信度 {confidence_pct}%  真话率 {truthfulness_pct}%\n\n"
            f"[color=#6b4f2a][b]世界变化[/b][/color]\n{world_effects}"
        )

    def _npc_reflection_summary(self, npc: dict[str, Any], topic: dict[str, Any] | None = None) -> str:
        recent = self._npc_recent_experiences(npc, topic, limit=6)
        if not recent:
            return "今天暂时没有形成新的强记忆，先按本职工作和利益行动。"
        summaries = [str(row.get("summary", "")).strip() for row in recent if str(row.get("summary", "")).strip()]
        if not summaries:
            return "今天暂时没有形成新的强记忆，先按本职工作和利益行动。"
        focus = "；".join(summaries[:3])
        role = str(npc.get("role", "角色"))
        return f"作为{role}，你刚经历的关键事情是：{focus}。下一步优先兼顾生计、安全和当前议题。"

    def _npc_memory_summary(self, npc: dict[str, Any]) -> str:
        memory = self._npc_player_memory(npc)
        rows = npc.get("relationship_memory", [])
        last_topic = str(memory.get("last_topic_id", ""))
        if last_topic.startswith("topic_"):
            last_topic = last_topic.replace("topic_", "", 1)
        sold_count = int(memory.get("intel_bought", 0))
        gift_total = int(memory.get("cash_gift_total", 0))
        pressure = float(memory.get("pressure_from_player", 0.0))
        streak = int(memory.get("trust_streak", 0))
        summary = f"你问过 {int(memory.get('talk_count', 0))} 次"
        if sold_count > 0:
            summary += f" · 卖过你 {sold_count} 次消息"
        if gift_total > 0:
            summary += f" · 收过你 {gift_total} 铜币"
        if pressure > 0.1:
            summary += f" · 被你压过 {int(round(pressure * 10))}/40"
        if streak > 0:
            summary += f" · 连着给过你 {streak} 次面子"
        patronage = self._npc_patronage_status(npc)
        if patronage:
            summary += f" · 现在{patronage}"
        if rows and isinstance(rows, list):
            latest = rows[0] if isinstance(rows[0], dict) else {}
            latest_topic = str(latest.get("topic_label", latest.get("trigger", latest.get("counterpart", ""))))
            if latest_topic:
                summary += f" · 最近记着 {latest_topic}"
        elif last_topic:
            summary += f" · 最近记着 {last_topic}"
        return summary

    def _npc_player_status(self, npc: dict[str, Any]) -> str:
        memory = self._npc_player_memory(npc)
        pressure = float(memory.get("pressure_from_player", 0.0))
        sold_count = int(memory.get("intel_bought", 0))
        friendly_count = int(memory.get("friendly_count", 0))
        trust_streak = int(memory.get("trust_streak", 0))
        talk_count = int(memory.get("talk_count", 0))
        if bool(memory.get("follows_player", False)):
            return "跟着你"
        if bool(memory.get("bought_over", False)):
            return "被你收买"
        if pressure >= 1.4:
            return "防着你"
        if self._npc_can_sell_info(npc) and (sold_count >= 1 or float(npc.get("player_trust", 0.0)) >= 54.0):
            return "愿意卖消息"
        if friendly_count >= 2 or trust_streak >= 2:
            return "愿意继续聊"
        if talk_count > 0:
            return "记得你来问过"
        return "还在观察你"

    def _player_total_wealth(self) -> int:
        player = self._ensure_player_financial_state()
        goods_rows = self.state.get("goods", [])
        stock_rows = self.state.get("stocks", [])
        goods_value = sum(
            int(player.get("goods_inventory", {}).get(str(row.get("name", "")), 0)) * int(row.get("current_price", 0))
            for row in goods_rows
        )
        stock_value = sum(
            int(player.get("stock_holdings", {}).get(str(row.get("name", "")), 0)) * int(row.get("current_price", 0))
            for row in stock_rows
        )
        return int(player.get("cash", 0)) + goods_value + stock_value - self._player_stock_short_exposure() - self._player_stock_margin_debt()

    def _player_collective_bias_for_npc(self, npc: dict[str, Any]) -> float:
        profile = self.state.get("player", {}).get("collective_profile", {})
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        if band in {"labor", "precariat", "organizer", "resident"}:
            return float(profile.get("worker_standing", 0.0)) * 0.04
        if band in {"elite", "finance", "manager"}:
            return float(profile.get("capital_standing", 0.0)) * 0.04
        if band == "authority":
            return float(profile.get("government_standing", 0.0)) * 0.04
        return float(profile.get("public_standing", 0.0)) * 0.04

    def _favorability_role_weights(self, npc: dict[str, Any]) -> dict[str, float]:
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        role = str(npc.get("role", ""))
        weights = {
            "wealth_respect": 0.34,
            "wealth_resentment": 0.08,
            "greed_weight": 0.26,
            "pressure_fear": 0.2,
            "attitude_penalty": 0.4,
            "friendliness_bonus": 0.4,
            "talk_bonus": 0.22,
            "disclosure_bonus": 0.28,
        }
        if band in {"elite", "finance"} or role in {"老板", "银行经理", "投机者"}:
            weights.update({"wealth_respect": 0.72, "wealth_resentment": 0.12, "greed_weight": 0.68, "pressure_fear": 0.16, "friendliness_bonus": 0.24})
        elif band in {"labor", "precariat", "organizer"} or role in {"工人", "临时工", "工会领袖"}:
            weights.update({"wealth_respect": 0.14, "wealth_resentment": 0.42, "greed_weight": 0.08, "pressure_fear": 0.34, "attitude_penalty": 0.72, "friendliness_bonus": 0.52})
        elif band in {"media", "trade"} or role in {"记者", "店主", "代理人"}:
            weights.update({"wealth_respect": 0.3, "wealth_resentment": 0.16, "greed_weight": 0.34, "pressure_fear": 0.24, "disclosure_bonus": 0.36})
        elif band == "authority":
            weights.update({"wealth_respect": 0.28, "wealth_resentment": 0.18, "greed_weight": 0.16, "pressure_fear": 0.44, "attitude_penalty": 0.48})
        return weights

    def _npc_favorability_state(self, npc: dict[str, Any]) -> dict[str, Any]:
        memory = self._npc_player_memory(npc)
        weights = self._favorability_role_weights(npc)
        wealth = max(0, self._player_total_wealth())
        wealth_signal = max(0.0, min(1.8, math.log10(max(wealth, 1)) - 3.4))
        relation = float(npc.get("player_relation", 0))
        trust = float(npc.get("player_trust", 0.0)) / 100.0
        talk_count = int(memory.get("talk_count", 0))
        friendly_count = int(memory.get("friendly_count", 0))
        hardball_count = int(memory.get("hardball_count", 0))
        pressure = float(memory.get("pressure_from_player", 0.0))
        gift_total = int(memory.get("cash_gift_total", 0))
        bought_over = bool(memory.get("bought_over", False))
        follows_player = bool(memory.get("follows_player", False))
        gift_signal = max(0.0, min(1.8, math.log10(gift_total + 1) - 2.6)) if gift_total > 0 else 0.0
        talk_signal = min(1.2, talk_count * 0.08 + int(memory.get("trust_streak", 0)) * 0.06)
        attitude_penalty = min(1.8, hardball_count * 0.16 + pressure * 0.34)
        collective_bias = self._player_collective_bias_for_npc(npc)
        cash_dependency = max(
            0.0,
            min(
                1.0,
                gift_signal * 0.52
                + (0.34 if bought_over else 0.0)
                + (0.52 if follows_player else 0.0)
                + max(0.0, relation) * 0.02,
            ),
        )
        warmth = max(0.0, min(1.0, trust * 0.52 + relation * 0.03 + friendly_count * 0.07 + talk_signal * weights["friendliness_bonus"] - attitude_penalty * 0.38 + collective_bias))
        respect = max(0.0, min(1.0, wealth_signal * weights["wealth_respect"] + gift_signal * 0.36 + trust * 0.28 + max(0.0, relation) * 0.02 + cash_dependency * 0.12))
        resentment = max(0.0, min(1.0, attitude_penalty * weights["attitude_penalty"] + wealth_signal * weights["wealth_resentment"] - friendly_count * 0.05 - trust * 0.16 - gift_signal * 0.1 - collective_bias - cash_dependency * 0.08))
        fear = max(0.0, min(1.0, pressure * weights["pressure_fear"] + wealth_signal * 0.12 + (0.18 if bought_over else 0.0) - trust * 0.08))
        greed_pull = max(0.0, min(1.0, wealth_signal * weights["greed_weight"] + gift_signal * 0.42 + (0.22 if bought_over else 0.0) + (0.28 if follows_player else 0.0)))
        faction_alignment = max(-1.0, min(1.0, collective_bias + relation * 0.03 + trust * 0.22 + cash_dependency * 0.18 - resentment * 0.4))
        disclosure = max(0.0, min(1.0, trust * 0.34 + warmth * 0.22 + greed_pull * weights["disclosure_bonus"] + respect * 0.12 + cash_dependency * 0.24 - resentment * 0.26 - fear * 0.1 + (0.18 if bought_over else 0.0) + (0.24 if follows_player else 0.0)))
        if follows_player and attitude_penalty >= 1.16 and resentment >= 0.44 and fear < 0.52:
            register = "hostile"
        elif follows_player and attitude_penalty >= 0.82 and resentment >= 0.34:
            register = "sullen"
        elif resentment >= 0.72 and fear < 0.44:
            register = "hostile"
        elif resentment >= 0.52 and fear >= 0.28:
            register = "sullen"
        elif follows_player and resentment < 0.56:
            register = "owned"
        elif bought_over and resentment < 0.62:
            register = "bought"
        elif respect >= 0.62 and greed_pull >= 0.52 and resentment < 0.34:
            register = "patronized"
        elif follows_player and resentment < 0.34:
            register = "deferential"
        elif warmth >= 0.64 and respect >= 0.42:
            register = "warm"
        elif fear >= 0.48 or disclosure < 0.28:
            register = "guarded"
        elif greed_pull >= 0.58 and resentment < 0.4:
            register = "slick"
        else:
            register = "neutral"
        intel_discount = max(0.62, min(1.22, 1.0 - disclosure * 0.18 - greed_pull * 0.09 + resentment * 0.08))
        label_map = {
            "owned": "算你的人",
            "bought": "被你收买",
            "patronized": "拿你当金主",
            "deferential": "拿你当金主",
            "warm": "越说越热络",
            "slick": "嘴甜但在算账",
            "neutral": "平视你",
            "guarded": "防着你",
            "sullen": "嘴上顺着，心里有气",
            "hostile": "对你很冲",
        }
        return {
            "warmth": round(warmth, 3),
            "respect": round(respect, 3),
            "resentment": round(resentment, 3),
            "fear": round(fear, 3),
            "greed_pull": round(greed_pull, 3),
            "faction_alignment": round(faction_alignment, 3),
            "disclosure_willingness": round(disclosure, 3),
            "speech_register": register,
            "speech_register_label": label_map.get(register, "平视你"),
            "intel_discount": round(intel_discount, 3),
            "wealth_signal": round(wealth_signal, 3),
            "gift_signal": round(gift_signal, 3),
            "cash_dependency": round(cash_dependency, 3),
            "patronage_status": self._npc_patronage_status(npc),
        }

    def _npc_people_and_relations(self, npc: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
        names = list(self._npc_contact_names(npc, "trusted_people")) + list(self._npc_contact_names(npc, "watch_people"))
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for other in self.state.get("npcs", []):
            other_name = str(other.get("name", "")).strip()
            if not other_name or other_name not in names or other_name in seen:
                continue
            seen.add(other_name)
            relation = "trusted" if other_name in self._npc_contact_names(npc, "trusted_people") else "watch"
            rows.append(
                {
                    "name": other_name,
                    "title": str(other.get("title", other.get("role", ""))),
                    "district": str(other.get("district", "")),
                    "relation": relation,
                    "activity": str(other.get("activity", "")),
                }
            )
            if len(rows) >= limit:
                return rows
        for entry in self._dialogue_history_view(npc, limit=limit):
            other_name = str(entry.get("counterpart_name", "")).strip()
            if not other_name or other_name in seen:
                continue
            seen.add(other_name)
            rows.append(
                {
                    "name": other_name,
                    "title": str(entry.get("counterpart_kind", "npc")),
                    "district": str(npc.get("district", "")),
                    "relation": "recent",
                    "activity": str(entry.get("trigger", "")),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def _npc_recent_experiences(self, npc: dict[str, Any], topic: dict[str, Any] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for memory in list(npc.get("relationship_memory", []))[: max(0, limit // 2)]:
            if not isinstance(memory, dict):
                continue
            rows.append(
                {
                    "kind": str(memory.get("kind", "")),
                    "clock": str(memory.get("clock", "")),
                    "summary": str(memory.get("topic_label", memory.get("trigger", memory.get("counterpart", "")))),
                }
            )
        for memory in self._local_memory_view(npc, topic_id=str((topic or {}).get("id", "")), limit=max(1, limit - len(rows))):
            rows.append(
                {
                    "kind": str(memory.get("kind", "")),
                    "clock": str(memory.get("clock", "")),
                    "summary": str(memory.get("summary", "")),
                }
            )
            if len(rows) >= limit:
                break
        return rows[:limit]

    def _npc_city_summary(self, npc: dict[str, Any]) -> dict[str, Any]:
        district_name = str(npc.get("district", ""))
        macro = self.state.get("macro", {})
        story_metrics = self._story_metrics_state()
        lead_topic = next(iter(self._active_public_topics(limit=2, district_name=district_name)), {})
        lead_collective = next(iter(self._active_collective_actions_view(limit=2, district_name=district_name)), {})
        district_bias = dict(self.state.get("population_bias", {}).get("districts", {}).get(district_name, {}))
        return {
            "district": district_name,
            "prices": {str(good.get("name", "")): int(good.get("current_price", 0)) for good in self.state.get("goods", [])},
            "stocks": {str(stock.get("name", "")): int(stock.get("current_price", 0)) for stock in self.state.get("stocks", [])},
            "government_support": int(max(0.0, min(100.0, 100.0 - float(macro.get("worker_unrest", 50)) * 0.6 + float(macro.get("media_sentiment", 50)) * 0.3))),
            "media_sentiment": int(macro.get("media_sentiment", 50)),
            "worker_unrest": int(macro.get("worker_unrest", 50)),
            "top_topic": str(lead_topic.get("label", "")),
            "top_collective": str(lead_collective.get("label", "")),
            "reputation": copy.deepcopy(story_metrics.get("reputation", {})),
            "shadow_reputation": copy.deepcopy(story_metrics.get("shadow_reputation", {})),
            "active_norms": self._active_norms_view(limit=3, district_name=district_name),
            "population_bias": district_bias,
        }

    def _npc_allowed_actions(self, npc: dict[str, Any], topic: dict[str, Any] | None = None) -> list[str]:
        actions = ["share_topic", "question_topic", "reinforce_norm", "contest_norm", "avoid"]
        role = str(npc.get("role", ""))
        if role in {"记者", "代理人", "工会领袖"}:
            actions.extend(["amplify_topic", "organize_collective"])
        if role in {"老板", "银行经理", "投机者", "代理人", "记者", "店主"}:
            actions.extend(["buy_stock", "sell_stock", "buy_intel", "quote_price"])
        if role in {"工人", "临时工", "工会领袖"}:
            actions.extend(["support_collective", "commit_collective", "attend_collective"])
        if str((topic or {}).get("kind", "")) in {"asset", "finance"}:
            actions.extend(["watch_market", "adjust_position"])
        return sorted(set(actions))

    def _npc_llm_sections(self, npc: dict[str, Any], topic: dict[str, Any] | None = None) -> dict[str, Any]:
        favorability = self._npc_favorability_state(npc)
        profile = self._npc_prompt_profile(npc)
        story_metrics = self._story_metrics_state()
        return {
            "who_you_are": {
                "name": str(npc.get("name", "")),
                "title": str(npc.get("title", npc.get("role", ""))),
                "role": str(npc.get("role", "")),
                "class": str(npc.get("class", "")),
                "camp": str(npc.get("camp", npc.get("family_affiliation", ""))),
                "route_alignment": str(npc.get("route_alignment", "")),
                "family": str(npc.get("family_affiliation", "")) or "无",
                "risk_preference": float(npc.get("risk_preference", 40.0)),
                "political_stance": str(npc.get("political_stance", "self_preservation")),
                "public_mask": str(profile.get("public_mask", "")),
                "core_drive": str(profile.get("core_drive", "")),
                "current_secret": str(profile.get("current_secret", "")),
                "route_stance": str(profile.get("route_stance", "")),
                "leverage_points": copy.deepcopy(profile.get("leverage_points", [])),
                "tone_notes": str(profile.get("tone_notes", "")),
                "persona_brief": self._npc_persona_brief(npc),
            },
            "current_status": {
                "cash": int(npc.get("cash", 0)),
                "food_inventory": copy.deepcopy(npc.get("inventory", {})),
                "emotions": {
                    "fear": int(npc.get("fear", 0)),
                    "greed": int(npc.get("greed", 0)),
                    "anxiety": round(float(npc.get("anxiety", 0.0)), 2),
                    "loyalty": int(npc.get("loyalty", 0)),
                },
                "health": int(max(0.0, 100.0 - float(npc.get("fatigue", 0)) * 0.5)),
                "work_status": str(npc.get("activity", "")),
                "stock_positions": copy.deepcopy(npc.get("stock_positions", {})),
                "favorability_state": favorability,
                "story_metrics": {
                    "reputation": copy.deepcopy(story_metrics.get("reputation", {})),
                    "shadow_reputation": copy.deepcopy(story_metrics.get("shadow_reputation", {})),
                },
                "housing": {
                    "home_building_id": str(npc.get("home_building_id", npc.get("home_id", ""))),
                    "home_subregion_id": str(npc.get("home_subregion_id", "")),
                    "home_mode": str(npc.get("home_mode", "doorstep")),
                    "schedule_anchor_type": str(npc.get("schedule_anchor_type", "")),
                },
                "trigger_conditions": {
                    "leak_triggers": copy.deepcopy(profile.get("leak_triggers", [])),
                    "betrayal_triggers": copy.deepcopy(profile.get("betrayal_triggers", [])),
                    "action_triggers": copy.deepcopy(profile.get("action_triggers", [])),
                },
            },
            "recent_experiences": {
                "recent_events": self._npc_recent_experiences(npc, topic, limit=10),
                "salient_memories": self._local_memory_view(npc, topic_id=str((topic or {}).get("id", "")), limit=4),
                "reflection_summary": self._npc_reflection_summary(npc, topic),
            },
            "people_and_relations": {
                "contacts": self._npc_people_and_relations(npc, limit=8),
                "trusted_people": copy.deepcopy(profile.get("trusted_people", [])),
                "watch_people": copy.deepcopy(profile.get("watch_people", [])),
                "relationship_hooks": copy.deepcopy(profile.get("relationship_hooks", [])),
            },
            "city_summary": self._npc_city_summary(npc),
            "allowed_actions": self._npc_allowed_actions(npc, topic),
        }

    def _dialogue_listener_brief(self, npc: dict[str, Any]) -> dict[str, Any]:
        position_kind, position_name, position_qty, position_bias = self._dominant_position(npc)
        return {
            "name": str(npc.get("name", "")),
            "title": str(npc.get("title", npc.get("role", ""))),
            "role": str(npc.get("role", "")),
            "district": str(npc.get("district", "")),
            "family": str(npc.get("family_affiliation", "")) or "无",
            "camp": str(npc.get("camp", "")),
            "mood": str(npc.get("mood", "")),
            "current_goal": str(npc.get("current_goal", "")),
            "stance": str(npc.get("stance", "")),
            "cash": int(npc.get("cash", 0)),
            "debt": int(npc.get("debt", 0)),
            "hunger": int(npc.get("hunger", 0)),
            "position": {
                "kind": position_kind,
                "name": position_name,
                "quantity": int(position_qty),
                "bias": position_bias,
            },
        }

    def _dialogue_listener_sections(self, npc: dict[str, Any], topic: dict[str, Any] | None = None) -> dict[str, Any]:
        full = self._npc_llm_sections(npc, topic)
        who = full.get("who_you_are", {})
        status = full.get("current_status", {})
        recent = full.get("recent_experiences", {})
        relations = full.get("people_and_relations", {})
        city = full.get("city_summary", {})
        favorability = status.get("favorability_state", {})
        recent_events = [
            str(row.get("summary", "")).strip()
            for row in recent.get("recent_events", [])
            if isinstance(row, dict) and str(row.get("summary", "")).strip()
        ][:2]
        salient_memories = [
            str(row.get("summary", "")).strip()
            for row in recent.get("salient_memories", [])
            if isinstance(row, dict) and str(row.get("summary", "")).strip()
        ][:1]
        stock_signals = {
            key: value
            for key, value in copy.deepcopy(city.get("stocks", {})).items()
        }
        story_pulse = {
            "SUI": dict(city.get("shadow_reputation", {})).get("SUI", 15),
            "ST": dict(city.get("shadow_reputation", {})).get("ST", 1.0),
            "WL": dict(city.get("shadow_reputation", {})).get("WL", 1),
        }
        player_memory = self._npc_player_memory(npc)
        return {
            "who_you_are": {
                "name": str(who.get("name", "")),
                "title": str(who.get("title", "")),
                "role": str(who.get("role", "")),
                "camp": str(who.get("camp", "")),
                "route_alignment": str(who.get("route_alignment", "")),
                "public_mask": str(who.get("public_mask", "")),
                "core_drive": str(who.get("core_drive", "")),
                "current_secret": str(who.get("current_secret", "")),
            },
            "current_status": {
                "cash": int(status.get("cash", 0)),
                "work_status": str(status.get("work_status", "")),
                "speech_register": str(favorability.get("speech_register", "")),
                "disclosure_willingness": float(favorability.get("disclosure_willingness", 0.0)),
                "trust_streak": int(player_memory.get("trust_streak", 0)),
            },
            "recent_experiences": {
                "recent_events": recent_events,
                "salient_memories": salient_memories,
            },
            "people_and_relations": {
                "trusted_people": copy.deepcopy(relations.get("trusted_people", []))[:1],
                "watch_people": copy.deepcopy(relations.get("watch_people", []))[:2],
                "relationship_hooks": copy.deepcopy(relations.get("relationship_hooks", []))[:2],
            },
            "city_summary": {
                "district": str(city.get("district", "")),
                "stocks": stock_signals,
                "top_topic": str(city.get("top_topic", "")),
                "top_collective": str(city.get("top_collective", "")),
                "story_pulse": story_pulse,
                "active_norms": [
                    str(row.get("text", "")).strip()
                    for row in city.get("active_norms", [])
                    if isinstance(row, dict) and str(row.get("text", "")).strip()
                ][:1],
            },
        }

    def _npc_market_tilt(self, npc: dict[str, Any]) -> str:
        position_kind, _, _, position_bias = self._dominant_position(npc)
        anxiety = float(npc.get("anxiety", npc.get("fear", 0.0)))
        greed = float(npc.get("greed_drive", npc.get("greed", 0.0)))
        if position_kind == "stock":
            if position_bias == "鍠婂":
                return "bullish"
            if position_bias == "鍠婄┖":
                return "bearish"
        if position_kind == "goods":
            if position_bias == "鍥ょ潃":
                return "panic"
            if position_bias == "鎵句环宸?":
                return "supportive"
        if anxiety - greed >= 12:
            return "panic"
        if greed - anxiety >= 12:
            return "bullish"
        return "neutral"

    def _coerce_market_tilt(self, value: str, npc: dict[str, Any]) -> str:
        normalized = value.strip().lower()
        if normalized in {"bullish", "bearish", "panic", "supportive", "neutral"}:
            return normalized
        return self._npc_market_tilt(npc)

    def _family_signal_from_state(self, family: dict[str, Any]) -> str:
        family_name = str(family.get("name", ""))
        move = self._find_by_name(self.state.get("family_moves", []), family_name)
        if move:
            target_asset = str(move.get("target_asset", ""))
            if int(family.get("media_power", 0)) >= 60 and float(move.get("pressure_score", 0.0)) >= 0.45:
                return "spin"
            if target_asset and int(move.get("relation", 0)) <= -2:
                return "short"
            if target_asset and float(family.get("risk_appetite", 0.5)) >= 0.62:
                return "support"
        liquidity_preference = float(family.get("liquidity_preference", 0.5))
        risk_appetite = float(family.get("risk_appetite", 0.5))
        if liquidity_preference >= 0.62:
            return "clampdown"
        if risk_appetite >= 0.62:
            return "support"
        return "steady"

    def _coerce_family_signal(self, value: str, family: dict[str, Any]) -> str:
        normalized = value.strip().lower()
        if normalized in {"steady", "spin", "support", "short", "clampdown"}:
            return normalized
        return self._family_signal_from_state(family)

    def _company_signal_from_state(self, company: dict[str, Any]) -> str:
        operating_state = str(company.get("operating_state", ""))
        funding_state = str(company.get("funding_state", ""))
        workforce_mood = str(company.get("workforce_mood", ""))
        if "expanding" in operating_state:
            return "expansion"
        if "dry" in funding_state or "tight" in funding_state:
            return "stress"
        if workforce_mood in {"restless", "angry", "fragile"}:
            return "labor"
        return "steady"

    def _coerce_company_signal(self, value: str, company: dict[str, Any]) -> str:
        normalized = value.strip().lower()
        if normalized in {"steady", "expansion", "stress", "labor"}:
            return normalized
        return self._company_signal_from_state(company)

    def _approach_label(self, approach: str) -> str:
        return {
            "cautious": "试探着问",
            "friendly": "先拉近关系",
            "hardball": "直接逼问",
        }.get(approach, approach)

    def _build_intel_packet_from_topic(self, topic: dict[str, Any], npc: dict[str, Any], district_name: str) -> dict[str, Any]:
        packet = self._build_intel_packet(district_name, source=f"{npc['name']}的口风", speaker=npc)
        packet["topic_id"] = str(topic.get("source_topic_id", topic.get("id", "")))
        packet["topic_kind"] = str(topic.get("kind", ""))
        packet["title"] = str(topic.get("label", packet["title"]))
        packet["body"] = f"{npc['name']} 提起：{topic.get('summary', packet['body'])}"
        packet["line"] = str(topic.get("summary", packet["line"]))
        impacts = topic.get("impacts", {})
        packet["goods_delta"] = copy.deepcopy(impacts.get("goods", packet.get("goods_delta", {})))
        packet["stocks_delta"] = copy.deepcopy(impacts.get("stocks", packet.get("stocks_delta", {})))
        packet["macro_delta"] = copy.deepcopy(impacts.get("macro", packet.get("macro_delta", {})))
        packet["family_delta"] = copy.deepcopy(impacts.get("families", packet.get("family_delta", {})))
        packet["tags"] = list(dict.fromkeys(list(topic.get("tags", [])) + list(packet.get("tags", []))))
        return packet

    def _talk_topics_for_npc(self, npc_id: str, district_name: str = "") -> list[dict[str, Any]]:
        topics = self.state.get("talk_topics", [])
        filtered = []
        for topic in topics:
            npc_ids = topic.get("npc_ids", [])
            if npc_ids and npc_id not in npc_ids:
                continue
            if district_name and topic.get("district") not in {"", district_name}:
                continue
            filtered.append(topic)
        filtered.sort(key=lambda item: float(item.get("heat", 0.0)), reverse=True)
        return filtered[:4]

    def _rebuild_talk_topics(self) -> None:
        topics: list[dict[str, Any]] = [copy.deepcopy(topic) for topic in self._active_public_topics(limit=6)]
        for district in self.state["districts"]:
            district_name = str(district.get("name", ""))
            signals = self.state["district_signals"].get(district_name, {})
            local_npcs = [npc for npc in self.state["npcs"] if npc.get("district") == district_name]
            topic_npc_ids = [npc["id"] for npc in local_npcs]
            if not district_name:
                continue
            trade_heat = float(signals.get("trade_heat", 0.0))
            labor_heat = float(signals.get("labor_heat", 0.0))
            gossip = float(signals.get("gossip", 0.0))
            fear = float(signals.get("fear", 0.0))
            liquidity = float(signals.get("liquidity", 0.0))
            if trade_heat > 0.35:
                good = max(self.state["goods"], key=lambda row: abs(float(self.state["market_pressure"]["goods"].get(row["name"], 0.0))))
                topics.append(
                    {
                        "id": f"topic_trade_{district_name}",
                        "kind": "trade",
                        "district": district_name,
                        "label": f"{district_name} 的{good['name']}价差",
                        "summary": f"{district_name} 正有人围着 {good['name']} 议价，货和铜币都开始挪位置。",
                        "heat": round(trade_heat, 3),
                        "tags": ["交易", district_name, good["name"]],
                        "npc_ids": topic_npc_ids,
                        "approaches": ["cautious", "friendly", "hardball"],
                        "impacts": {
                            "goods": {good["name"]: 0.06},
                            "stocks": {},
                            "macro": {"economy_heat": 1.0},
                            "families": {},
                        },
                    }
                )
            if labor_heat > 0.28:
                topics.append(
                    {
                        "id": f"topic_job_{district_name}",
                        "kind": "labor",
                        "district": district_name,
                        "label": f"{district_name} 的活路",
                        "summary": f"{district_name} 眼下活路紧不紧，已经写在工牌和脸色上了。",
                        "heat": round(labor_heat, 3),
                        "tags": ["工作", district_name],
                        "npc_ids": [npc["id"] for npc in local_npcs if str(npc.get("role", "")) in {"工人", "临时工", "店主", "老板"}],
                        "approaches": ["friendly", "cautious", "hardball"],
                        "impacts": {
                            "goods": {},
                            "stocks": {},
                            "macro": {"worker_unrest": 1.0 if district.get("state") in {"tense", "unrest"} else -0.5},
                            "families": {},
                        },
                    }
                )
            if gossip > 0.22 or fear > 0.2:
                topics.append(
                    {
                        "id": f"topic_panic_{district_name}",
                        "kind": "panic",
                        "district": district_name,
                        "label": f"{district_name} 的风声在变厚",
                        "summary": f"{district_name} 的耳语变密了，大家都在比谁先听见坏消息。",
                        "heat": round(gossip + fear, 3),
                        "tags": ["传闻", district_name],
                        "npc_ids": topic_npc_ids,
                        "approaches": ["cautious", "hardball", "friendly"],
                        "impacts": {
                            "goods": {"罐头": 0.04} if district_name != "工厂区" else {"煤": 0.05},
                            "stocks": {},
                            "macro": {"worker_unrest": 1.4, "media_sentiment": 0.8},
                            "families": {},
                        },
                    }
                )
            if liquidity > 0.22 or district_name == "交易所":
                hot_stock = max(self.state["stocks"], key=lambda row: abs(float(self.state["market_pressure"]["stocks"].get(row["name"], 0.0))))
                topics.append(
                    {
                        "id": f"topic_asset_{district_name}",
                        "kind": "asset",
                        "district": district_name,
                        "label": f"{hot_stock['name']} 的盘口",
                        "summary": f"{hot_stock['name']} 最近的价差和情绪走得比街上脚步还快。",
                        "heat": round(liquidity + 0.2, 3),
                        "tags": ["股票", district_name, hot_stock["name"]],
                        "npc_ids": [npc["id"] for npc in local_npcs if str(npc.get("role", "")) in {"记者", "投机者", "代理人", "银行经理", "老板"}],
                        "approaches": ["cautious", "hardball", "friendly"],
                        "impacts": {
                            "goods": {},
                            "stocks": {hot_stock["name"]: 0.07},
                            "macro": {"media_sentiment": 1.0},
                            "families": {},
                        },
                    }
                )
        for family in self.state["families"]:
            family_name = str(family.get("name", ""))
            family_pressure = abs(float(self.state["market_pressure"]["families"].get(family_name, 0.0)))
            if family_pressure < 0.05:
                continue
            stock_name, good_name = self._family_focus_targets(family)
            family_npcs = [npc["id"] for npc in self.state["npcs"] if str(npc.get("family_affiliation", "")) == family_name]
            district_name = {"海藻家族": "贫民街", "龟甲船坞": "工厂区", "珊瑚银行": "交易所"}.get(
                family_name, "交易所" if stock_name or family_name != "街头互助会" else "贫民街"
            )
            topics.append(
                {
                    "id": f"topic_family_{family.get('id', family_name)}",
                    "kind": "family",
                    "district": district_name,
                    "label": f"{family_name} 在做什么",
                    "summary": f"{family_name} 最近像是在围着 {stock_name or good_name or '街头温度'} 悄悄挪仓。",
                    "heat": round(family_pressure + 0.2, 3),
                    "tags": ["家族", family_name],
                    "npc_ids": family_npcs,
                    "approaches": ["friendly", "cautious", "hardball"],
                    "impacts": {
                        "goods": {good_name: 0.05} if good_name else {},
                        "stocks": {stock_name: 0.06} if stock_name else {},
                        "macro": {"media_sentiment": 0.6},
                        "families": {family_name: 0.08},
                    },
                }
            )
        for company in self.state.get("company_states", []):
            wage_pressure = float(company.get("wage_pressure", 0.0))
            financing_pressure = float(company.get("financing_pressure", 0.0))
            if max(wage_pressure, financing_pressure) < 45:
                continue
            company_npc_ids = [
                npc["id"]
                for npc in self.state["npcs"]
                if str(npc.get("company_id", "")) == str(company.get("id", ""))
                or (not str(npc.get("company_id", "")) and str(npc.get("district", "")) == str(company.get("district", "")))
            ]
            topics.append(
                {
                    "id": f"topic_company_{company.get('id', '')}",
                    "kind": "company",
                    "district": str(company.get("district", "")),
                    "label": f"{company.get('name', '公司')} 的账和人",
                    "summary": f"{company.get('name', '这家公司')} 眼下库存、工资和融资一起拧着，谁都不肯先认怂。",
                    "heat": round(max(wage_pressure, financing_pressure) / 100.0 + 0.18, 3),
                    "tags": ["公司", str(company.get("name", "")), str(company.get("stock_name", ""))],
                    "npc_ids": company_npc_ids,
                    "approaches": ["friendly", "cautious", "hardball"],
                    "impacts": {
                        "goods": self._company_topic_goods_impact(company),
                        "stocks": {str(company.get("stock_name", "")): 0.05} if str(company.get("stock_name", "")) else {},
                        "macro": {"worker_unrest": 0.9 if wage_pressure >= financing_pressure else 0.2, "economy_heat": -0.4},
                        "families": {str(company.get("family_owner", "")): 0.05} if str(company.get("family_owner", "")) else {},
                    },
                }
            )
        for npc in self.state["npcs"]:
            topics.extend(self._npc_personal_topics(npc))
        topics.extend(self._institution_topics())
        topics.sort(key=lambda item: float(item.get("heat", 0.0)), reverse=True)
        self.state["talk_topics"] = topics[:12]

    def _top_market_move(self, rows: list[dict[str, Any]], sentiment_key: str) -> str:
        if not rows:
            return "市场还安静"
        row = max(rows, key=lambda item: abs(int(item.get("current_price", 0)) - int(item.get("base_price", 0))))
        if sentiment_key == "price_trend":
            return f"{row['name']} {row.get('price_trend', '平')} {row['current_price']}"
        mood = row.get("market_sentiment", "谨慎")
        return f"{row['name']} {mood} {row['current_price']}"

    def _update_player_class(self) -> None:
        player = self._ensure_player_financial_state()
        if str(player.get("financial_route", "")) == "负债工贼":
            player["class_position"] = "负债工贼"
            return
        goods_value = sum(int(good.get("current_price", 0)) * int(player["goods_inventory"].get(good["name"], 0)) for good in self.state["goods"])
        stocks_value = sum(int(stock.get("current_price", 0)) * int(player["stock_holdings"].get(stock["name"], 0)) for stock in self.state["stocks"])
        total_wealth = int(player.get("cash", 0)) + goods_value + stocks_value - self._player_stock_margin_debt()
        story_route = str(player.get("story_route", ""))
        if story_route == "精英路线":
            player["class_position"] = "前高管"
            return
        if total_wealth >= 120 or int(player.get("reputation", 0)) >= 28:
            player["class_position"] = "街头投机客"
        elif total_wealth >= 70 or int(player.get("credit", 0)) >= 35:
            player["class_position"] = "攒钱中的小人物"
        else:
            player["class_position"] = "底层"

    def _family_focus_targets(self, family: dict[str, Any]) -> tuple[str, str]:
        name = str(family.get("name", ""))
        if name == "海藻家族":
            return "海藻食业", "面包"
        if name == "珊瑚银行":
            return "珊瑚金控", "罐头"
        if name == "龟甲船坞":
            return "龟甲船运", "煤"
        return "", ""

    def _district_state(self, district_name: str) -> str:
        for district in self.state["districts"]:
            if district["name"] == district_name:
                return district["state"]
        return "normal"

    def _find_by_name(self, rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
        needle = str(name).strip()
        for row in rows:
            if row["name"] == needle:
                return row
            if str(row.get("display_name", "")).strip() == needle:
                return row
            if str(row.get("ticker", "")).strip().upper() == needle.upper():
                return row
            if needle in [str(value).strip() for value in row.get("legacy_names", [])]:
                return row
        return None

    def _find_npc(self, npc_id: str) -> dict[str, Any] | None:
        needle = str(npc_id).strip()
        if not needle:
            return None
        for npc in self.state["npcs"]:
            if str(npc.get("id", "")) == needle or str(npc.get("name", "")).strip() == needle:
                return npc
        return None

    def _find_by_id(self, rows: list[dict[str, Any]], row_id: str) -> dict[str, Any] | None:
        for row in rows:
            if row["id"] == row_id:
                return row
        return None

    def _increment_task_progress(self, action_type: str, target: str, amount: int) -> None:
        player = self.state["player"]
        active_task_id = str(player.get("active_task_id", ""))
        if not active_task_id:
            return
        task = self._find_by_id(self.state["task_board"], active_task_id)
        if not task:
            return
        requirement = task["requirement"]
        if requirement["type"] != action_type:
            return
        if requirement["target"] not in {"any", target}:
            return
        current = int(player["task_progress"].get(active_task_id, 0))
        player["task_progress"][active_task_id] = current + amount

    def _rule_conversation_lines(self, speaker: dict[str, Any], listener: dict[str, Any], trigger: str) -> list[str]:
        district = str(speaker.get("district", "这片街区"))
        role = str(speaker.get("role", "街坊"))
        natural_options = [
            [
                f"{speaker['name']}：刚从{district}那边转回来，今天路上人比平时多。",
                f"{listener['name']}：我也看到了，先把手头活干完，晚点再细聊。",
            ],
            [
                f"{speaker['name']}：你这会儿忙不忙？我想问问你最近都在盯哪一块。",
                f"{listener['name']}：先盯吃饭和住处，别的事慢慢来，急也没用。",
            ],
            [
                f"{speaker['name']}：我听人提到你是{role}，这两天有什么要紧动静吗？",
                f"{listener['name']}：有一点风声，但先别外传，等晚上再对一下。",
            ],
            [
                f"{speaker['name']}：刚才那阵子有点乱，你那边还稳得住吗？",
                f"{listener['name']}：还行，先把节奏稳住，不跟着乱跑就问题不大。",
            ],
        ]
        return self.random.choice(natural_options)
        options = [
            [f"{speaker['name']}：{trigger}可不是白来的，今天的风比账本更会骗人。", f"{listener['name']}：我只想知道下一个倒霉的是面包还是矿井。"],
            [f"{speaker['name']}：你听见没有，{speaker['family_affiliation']} 的人已经在街角放话了。", f"{listener['name']}：那就说明他们想让别人先恐慌。"],
            [f"{speaker['name']}：这城里最贵的不是货，是比别人早半拍的消息。", f"{listener['name']}：慢半拍的人，通常连壳都保不住。"],
        ]
        return self.random.choice(options)

    def _rule_player_talk_lines(
        self,
        npc: dict[str, Any],
        topic: dict[str, Any],
        approach: str,
        openness: str,
        intent: str = "",
        player_input: str = "",
    ) -> list[str]:
        favorability = self._npc_favorability_state(npc)
        register = str(favorability.get("speech_register", "neutral"))
        salutation = "哥" if register in {"deferential", "slick", "patronized", "owned"} and float(favorability.get("respect", 0.0)) >= 0.56 else "朋友"
        cleaned_player_input = str(player_input).strip()
        hint_flags = self._player_talk_hint_flags(cleaned_player_input, intent)
        if cleaned_player_input and bool(hint_flags.get("greeting", False)) and not bool(hint_flags.get("market", False)) and not bool(hint_flags.get("actor", False)):
            npc_name = str(npc.get("name", "对方"))
            district = str(npc.get("district", "这片街区"))
            reply = f"{npc_name}：你好。先别紧张，我在{district}这边跑腿。你想先聊近况、身份，还是哪件麻烦事？"
            return [cleaned_player_input, reply]
        player_line = cleaned_player_input or {
            "cautious": f"我只想问一句，{topic.get('label', npc['district'])} 最近是不是在变？",
            "friendly": f"我不是来压你话的，就想听听你怎么看 {topic.get('label', npc['district'])}。",
            "hardball": f"别绕了，{topic.get('label', npc['district'])} 到底是谁在做局？",
        }.get(approach, f"最近 {topic.get('label', npc['district'])} 的风向到底怎么走？")
        if register == "owned":
            reply = f"{npc['name']}：{salutation}，你这边的话我记着。明话我直接给你：{topic.get('summary', '这阵风已经写进盘口和人心里了。')}"
        elif register == "bought":
            reply = f"{npc['name']}：钱我既然收了，就不跟你兜圈子。{topic.get('summary', '这条风声已经能拿来落仓位了。')}"
        elif register == "patronized":
            reply = f"{npc['name']}：{salutation}，这层盘面我先替你掀开一角。{topic.get('summary', '这阵风已经往价格上写了。')}"
        elif register == "hostile":
            reply = f"{npc['name']}：你口气收一收。{topic.get('label', npc['district'])} 这事不是你想逼就逼得出来的。"
        elif register == "sullen":
            reply = f"{npc['name']}：话我不是不能说，但你别真把人当能随手拿捏的壳。"
        elif openness == "guarded":
            reply = f"{npc['name']}：{salutation}先别把话说满，这话题在 {npc['district']} 不便宜。"
        elif openness == "skeptical":
            reply = f"{npc['name']}：想问就问，但我只说半句，剩下半句你自己拿壳去试。"
        elif register == "deferential":
            reply = f"{npc['name']}：{salutation}，你既然肯来，我就把能说的先递你半层。{topic.get('summary', '这阵风已经往价格上写了。')}"
        elif register == "warm":
            reply = f"{npc['name']}：你这次说话还算顺耳。{topic.get('summary', '街上都在看这件事。')}"
        elif register == "slick":
            reply = f"{npc['name']}：{salutation}要真想听深一点，价和人情总得有一样先到位。"
        else:
            reply = self.random.choice(
                [
                    f"{npc['name']}：{topic.get('summary', '街上都在看这件事。')}",
                    f"{npc['name']}：盯着 {topic.get('label', npc['district'])} 的不只你一个，慢半拍就只能接别人丢下的壳。",
                    f"{npc['name']}：真相没那么直，但 {topic.get('label', npc['district'])} 这事已经把街上气味带歪了。",
                ]
            )
        return [player_line, reply]

    def _shift_mood_after_talk(self, current: str) -> str:
        mapping = {"wary": "anxious", "hopeful": "excited", "tired": "wary", "excited": "defiant", "anxious": "wary"}
        return mapping.get(current, "wary")

    def _distance(self, a: dict[str, Any], b: dict[str, Any]) -> float:
        return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5

    def _advance_realtime_clock(self) -> None:
        if self._route_choice_required():
            self.state["last_tick_at"] = time.time()
            return
        last_tick = float(self.state.get("last_tick_at", time.time()))
        now = time.time()
        elapsed = max(0.0, now - last_tick)
        if elapsed < 1.0:
            self.state["last_tick_at"] = now
            return
        self.state["last_tick_at"] = now
        self._advance_clock(int(elapsed * 5.0))

    def _advance_clock(self, minutes: int) -> None:
        if minutes <= 0:
            return
        current = int(self.state.get("clock_minutes", 8 * 60))
        self.state["clock_minutes"] = min(23 * 60 + 45, current + minutes)
        self._apply_clock_state()
        self._apply_story_timeline_between(current, int(self.state.get("clock_minutes", current)))
        self._apply_collective_followups(minutes)
        self._apply_npc_schedule()

    def _apply_clock_state(self) -> None:
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        weather = self._update_weather(minutes)
        solar_ratio = max(0.0, math.cos((float(minutes) - 720.0) / 720.0 * math.pi))
        if minutes < 5 * 60 or minutes >= 20 * 60:
            period = "night"
        elif minutes < 7 * 60:
            period = "dawn"
        elif minutes < 17 * 60:
            period = "day"
        else:
            period = "evening"
        weather_dim = {
            "sunny": 0.0,
            "breezy": 0.01,
            "cloudy": 0.04,
            "overcast": 0.08,
            "rain": 0.11,
            "snow": 0.09,
            "dust": 0.14,
        }.get(str(weather.get("kind", "sunny")), 0.0)
        light = round(max(0.18, min(1.0, 0.18 + solar_ratio * 0.82 - weather_dim)), 2)
        self.state["time_period"] = period
        self.state["light_level"] = light

    def _apply_story_timeline_between(self, previous_minutes: int, current_minutes: int) -> None:
        day = int(self.state.get("day", 1))
        checkpoints: list[tuple[int, str]] = []
        if day == 1:
            route = str(self._ensure_player_financial_state().get("story_route", ""))
            if route == "平民路线":
                checkpoints = [
                    (8 * 60 + 5, "commoner_tutorial_hunger"),
                    (8 * 60 + 20, "commoner_tutorial_social"),
                    (8 * 60 + 50, "commoner_tutorial_eavesdrop"),
                    (9 * 60 + 15, "commoner_tutorial_reputation_trade"),
                    (17 * 60, "day1_privatization"),
                ]
            elif route == "精英路线":
                checkpoints = [
                    (8 * 60 + 5, "elite_tutorial_clock"),
                    (8 * 60 + 10, "elite_tutorial_dialogue"),
                    (8 * 60 + 30, "elite_tutorial_keyword"),
                    (9 * 60, "elite_tutorial_contract"),
                    (17 * 60, "day1_privatization"),
                ]
            else:
                checkpoints = [(17 * 60, "day1_privatization")]
        elif day == 2:
            checkpoints = [(12 * 60, "day2_arthur_assassination")]
        elif day == 3:
            checkpoints = [(14 * 60, "day3_tom_self_immolation"), (20 * 60, "day3_zero_uprising")]
        for threshold, event_id in checkpoints:
            if previous_minutes < threshold <= current_minutes and not self._story_event_fired(event_id):
                self._apply_story_timeline_event(event_id)

    def _story_event_schedule(self, event_id: str) -> tuple[int, int] | None:
        mapping = {
            "commoner_tutorial_hunger": (1, 8 * 60 + 5),
            "commoner_tutorial_social": (1, 8 * 60 + 20),
            "commoner_tutorial_eavesdrop": (1, 8 * 60 + 50),
            "commoner_tutorial_reputation_trade": (1, 9 * 60 + 15),
            "elite_tutorial_clock": (1, 8 * 60 + 5),
            "elite_tutorial_dialogue": (1, 8 * 60 + 10),
            "elite_tutorial_keyword": (1, 8 * 60 + 30),
            "elite_tutorial_contract": (1, 9 * 60),
            "day1_privatization": (1, 17 * 60),
            "day2_arthur_assassination": (2, 12 * 60),
            "day3_tom_self_immolation": (3, 14 * 60),
            "day3_zero_uprising": (3, 20 * 60),
        }
        return mapping.get(str(event_id))

    def _route_timeline_copy(self, event_id: str) -> dict[str, str]:
        route = str(self._ensure_player_financial_state().get("story_route", ""))
        is_commoner = route == "平民路线"
        match event_id:
            case "commoner_tutorial_hunger":
                return {
                    "event_title": "平民教学：先保住体力",
                    "news_title": "教学已开启",
                    "description": "先观察饥饿与健康，保证今天能扛住第一轮工作与移动消耗。",
                }
            case "commoner_tutorial_social":
                return {
                    "event_title": "平民教学：建立街坊关系",
                    "news_title": "教学已开启",
                    "description": "先和附近 NPC 打招呼并完成第一轮对话，打开声望与互助网络。",
                }
            case "commoner_tutorial_eavesdrop":
                return {
                    "event_title": "平民教学：开始窃听信息",
                    "news_title": "教学已开启",
                    "description": "留在街区核心区域，触发一次窃听，确认当前谣言与机会的方向。",
                }
            case "commoner_tutorial_reputation_trade":
                return {
                    "event_title": "平民教学：声望置换",
                    "news_title": "教学已开启",
                    "description": "尝试用声望换取资源或通行便利，理解平民路线的核心循环。",
                }
            case "elite_tutorial_clock":
                return {
                    "event_title": "精英教学：建立时间感",
                    "news_title": "教学已开启",
                    "description": "先看清当前时段与交易窗口，确认今天可操作的关键时间点。",
                }
            case "elite_tutorial_dialogue":
                return {
                    "event_title": "精英教学：对话输入",
                    "news_title": "教学已开启",
                    "description": "按 E 发起对话并输入一句完整问题，确认交互链路正常。",
                }
            case "elite_tutorial_keyword":
                return {
                    "event_title": "精英教学：关键词识别",
                    "news_title": "教学已开启",
                    "description": "围绕身份、行情、风向三类关键词追问，验证 NPC 是否按上下文回应。",
                }
            case "elite_tutorial_contract":
                return {
                    "event_title": "精英教学：契约与跳时",
                    "news_title": "教学已开启",
                    "description": "完成一次契约/行动确认，并观察 AP 与时间推进的对应关系。",
                }
            case "day1_privatization":
                if is_commoner:
                    return {
                        "event_title": "公共资源的私有化围猎",
                        "news_title": "管网私有化",
                        "description": "17:00 管网被移交给海藻资本。贫民窟水电开始断供，AMB（市政债）跌至 A$ 42，SWC（海藻重工）升至 A$ 188。"
                    }
                return {
                    "event_title": "第一波收割：管网私有化公报",
                    "news_title": "管网私有化",
                    "description": "17:00《管网私有化公报》发布。AMB（市政债）从 A$ 80 瞬间闪崩至 A$ 42，SWC（海藻重工）从 A$ 150 狂飙至 A$ 188。"
                }
            case "day2_arthur_assassination":
                if is_commoner:
                    return {
                        "event_title": "亚瑟事件的消极演向",
                        "news_title": "亚瑟被暗杀",
                        "description": "12:00 亚瑟在广场倒下，底层失去了唯一还可能公开调查海藻资本的人。SWC 继续被抬高，AMB 被抛进恐慌。"
                    }
                return {
                    "event_title": "亚瑟被暗杀",
                    "news_title": "亚瑟被暗杀",
                    "description": "12:00 亚瑟在广场被暗杀。SWC 暴涨至 A$ 210，AMB 暴跌至 A$ 25，警察局和镇政府开始准备弃守。"
                }
            case "day3_tom_self_immolation":
                if is_commoner:
                    return {
                        "event_title": "汤姆的绝望坐标",
                        "news_title": "汤姆自焚",
                        "description": "14:00 汤姆站在证券交易所门口点燃了自己。火光把整座小镇压到临界点，底层怒火开始失控。"
                    }
                return {
                    "event_title": "汤姆自焚",
                    "news_title": "汤姆自焚",
                    "description": "14:00 汤姆在证券交易所门口点燃了自己。SUI 被直接推到 90 以上，盘口开始进入临界波动。"
                }
            case "day3_zero_uprising":
                if is_commoner:
                    return {
                        "event_title": "宏观对决演算",
                        "news_title": "零号起义结算",
                        "description": "20:00 零号起义进入结算。SWC 暴跌 60%，TSL 暴涨 50%，AMB 归零，海藻大厦和旧秩序一起坍塌。"
                    }
                return {
                    "event_title": "零号起义结算",
                    "news_title": "零号起义结算",
                    "description": "20:00 零号起义结算。SWC 暴跌 60%，TSL 暴涨 50%，AMB 归零，旧秩序彻底崩塌。"
                }
        return {"event_title": event_id, "news_title": event_id, "description": ""}

    def _apply_story_timeline_event(self, event_id: str) -> None:
        if self._story_event_fired(event_id):
            return
        scheduled = self._story_event_schedule(event_id)
        if scheduled is not None:
            scheduled_day, scheduled_minute = scheduled
            if int(self.state.get("day", 1)) < scheduled_day:
                return
            if int(self.state.get("day", 1)) == scheduled_day and int(self.state.get("clock_minutes", 0)) < scheduled_minute:
                return
        metrics = self._story_metrics_state()
        shadow = dict(metrics.get("shadow_reputation", {}))
        player = self._ensure_player_financial_state()
        ops = self._stock_ops_state()
        copy_map = self._route_timeline_copy(event_id)
        match event_id:
            case (
                "commoner_tutorial_hunger"
                | "commoner_tutorial_social"
                | "commoner_tutorial_eavesdrop"
                | "commoner_tutorial_reputation_trade"
                | "elite_tutorial_clock"
                | "elite_tutorial_dialogue"
                | "elite_tutorial_keyword"
                | "elite_tutorial_contract"
            ):
                description = str(copy_map.get("description", "")).strip()
                title = str(copy_map.get("event_title", event_id)).strip() or event_id
                news_title = str(copy_map.get("news_title", title)).strip() or title
                route_tag = "平民路线" if event_id.startswith("commoner_") else "精英路线"
                self._queue_story_event(event_id, title, description)
                self._push_system_news(news_title, description, ["教学", route_tag])
            case "day1_privatization":
                self._force_stock_price(
                    "SWC",
                    max(188, int((self._stock_by_ticker("SWC") or {}).get("current_price", 188))),
                    note="《管网私有化公报》发布后，SWC 的垄断预期被直接写进盘面。",
                    pressure=0.34,
                )
                self._force_stock_price(
                    "AMB",
                    min(42, int((self._stock_by_ticker("AMB") or {}).get("current_price", 42))),
                    note="温斯顿签下《管网私有化转让书》后，AMB 瞬间闪崩。",
                    pressure=-0.36,
                )
                self.state["macro"]["worker_unrest"] = min(100, int(self.state["macro"].get("worker_unrest", 50)) + 12)
                self.state["macro"]["media_sentiment"] = min(100, int(self.state["macro"].get("media_sentiment", 50)) + 6)
                self._bump_district_signal("交易所", "trade_heat", 0.24)
                self._bump_district_signal("贫民街", "fear", 0.22)
                description = str(copy_map.get("description", ""))
                self._queue_story_event("day1_privatization", str(copy_map.get("event_title", "第一波收割：管网私有化公报")), description)
                self._push_system_news(str(copy_map.get("news_title", "管网私有化")), description, ["时间线", "SWC", "AMB", "私有化"])
            case "day2_arthur_assassination":
                self._force_stock_price(
                    "SWC",
                    max(210, int((self._stock_by_ticker("SWC") or {}).get("current_price", 210))),
                    note="亚瑟被暗杀后，海藻资本的审计威胁被直接抹掉。",
                    pressure=0.42,
                )
                self._force_stock_price(
                    "AMB",
                    min(25, int((self._stock_by_ticker("AMB") or {}).get("current_price", 25))),
                    note="税务官亚瑟当街遇刺后，AMB 遭遇恐慌性抛售。",
                    pressure=-0.48,
                )
                self.state["macro"]["worker_unrest"] = min(100, int(self.state["macro"].get("worker_unrest", 50)) + 16)
                self._bump_district_signal("交易所", "fear", 0.3)
                self._bump_district_signal("交易所", "gossip", 0.28)
                ops["story_sui_bonus"] = max(float(ops.get("story_sui_bonus", 0.0)), 15.0)
                shadow["SUI"] = min(100.0, max(float(shadow.get("SUI", 15.0)), 30.0))
                metrics["shadow_reputation"] = shadow
                player["shadow_reputation"] = copy.deepcopy(shadow)
                description = str(copy_map.get("description", ""))
                self._queue_story_event("day2_arthur_assassination", str(copy_map.get("event_title", "亚瑟被暗杀")), description)
                self._push_system_news(str(copy_map.get("news_title", "亚瑟被暗杀")), description, ["时间线", "亚瑟", "SWC", "AMB"])
            case "day3_tom_self_immolation":
                self._bump_district_signal("交易所", "fear", 0.35)
                self._bump_district_signal("工厂区", "labor_heat", 0.32)
                self._bump_district_signal("贫民街", "gossip", 0.28)
                ops["story_sui_bonus"] = max(float(ops.get("story_sui_bonus", 0.0)), 28.0)
                ops["story_st_floor"] = max(float(ops.get("story_st_floor", 1.0)), 2.5)
                shadow["SUI"] = min(100.0, max(float(shadow.get("SUI", 15.0)), 90.0))
                shadow["ST"] = max(float(shadow.get("ST", 1.0)), 2.5)
                metrics["shadow_reputation"] = shadow
                player["shadow_reputation"] = copy.deepcopy(shadow)
                description = str(copy_map.get("description", ""))
                self._queue_story_event("day3_tom_self_immolation", str(copy_map.get("event_title", "汤姆自焚")), description)
                self._push_system_news(str(copy_map.get("news_title", "汤姆自焚")), description, ["时间线", "汤姆", "SUI"])
            case "day3_zero_uprising":
                swc_now = int((self._stock_by_ticker("SWC") or {}).get("current_price", 120))
                tsl_now = int((self._stock_by_ticker("TSL") or {}).get("current_price", 45))
                self._force_stock_price(
                    "SWC",
                    max(18, int(round(swc_now * 0.4))),
                    note="零号起义结算开始后，SWC 的物理资产预期被直接打穿。",
                    pressure=-0.62,
                )
                self._force_stock_price(
                    "TSL",
                    max(int(round(tsl_now * 1.5)), tsl_now + 12),
                    note="旧秩序崩溃后，TSL 成了仍在流动的唯一命脉。",
                    pressure=0.4,
                )
                self._force_stock_price(
                    "AMB",
                    1,
                    note="AMB 在零号起义结算里被判成废纸，镇政府信用归零。",
                    pressure=-0.8,
                )
                ops["story_sui_bonus"] = max(float(ops.get("story_sui_bonus", 0.0)), 36.0)
                ops["story_st_floor"] = max(float(ops.get("story_st_floor", 1.0)), 3.0)
                shadow["SUI"] = min(100.0, max(float(shadow.get("SUI", 15.0)), 96.0))
                shadow["ST"] = max(float(shadow.get("ST", 1.0)), 3.0)
                metrics["shadow_reputation"] = shadow
                player["shadow_reputation"] = copy.deepcopy(shadow)
                description = str(copy_map.get("description", ""))
                self._queue_story_event("day3_zero_uprising", str(copy_map.get("event_title", "零号起义结算")), description)
                self._push_system_news(str(copy_map.get("news_title", "零号起义结算")), description, ["时间线", "起义", "SWC", "TSL", "AMB"])
        self._mark_story_event_fired(event_id)

    def _update_weather(self, minutes: int) -> dict[str, Any]:
        day = int(self.state.get("day", 1))
        slot = int(minutes // 180)
        current = self.state.get("weather", {})
        if int(current.get("day", -1)) == day and int(current.get("slot", -1)) == slot:
            return current
        rng = random.Random(day * 1009 + slot * 131 + 17)
        roll = rng.random()
        candidates: list[tuple[float, dict[str, Any]]] = [
            (0.58, {"kind": "sunny", "label": "晴天", "intensity": 0.1}),
            (0.12, {"kind": "breezy", "label": "晴朗有风", "intensity": 0.18}),
            (0.12, {"kind": "cloudy", "label": "多云", "intensity": 0.24}),
            (0.08, {"kind": "overcast", "label": "阴天", "intensity": 0.34}),
            (0.06, {"kind": "rain", "label": "下雨", "intensity": 0.7}),
            (0.02, {"kind": "snow", "label": "下雪", "intensity": 0.62}),
            (0.02, {"kind": "dust", "label": "沙尘", "intensity": 0.76}),
        ]
        selected = candidates[0][1]
        cursor = 0.0
        for weight, entry in candidates:
            cursor += weight
            if roll <= cursor:
                selected = entry
                break
        weather = dict(selected)
        weather["slot"] = slot
        weather["day"] = day
        previous_kind = str(current.get("kind", ""))
        self.state["weather"] = weather
        if previous_kind and previous_kind != str(weather["kind"]):
            self.state["global_news"].insert(
                0,
                {
                    "title": "天气换了一阵风向",
                    "body": f"城里天气转成{weather['label']}，摊位、人流和市场情绪都在跟着变。",
                    "tags": ["天气", str(weather["label"])],
                    "scope": "city",
                },
            )
            self.state["global_news"] = self.state["global_news"][:8]
        return weather

    def _collective_action_live_now(self, action: dict[str, Any], minutes: int) -> bool:
        stage = str(action.get("stage", "forming"))
        if stage in {"dormant", "cooling"}:
            return False
        start = int(action.get("window_start_minutes", 0))
        end = int(action.get("window_end_minutes", 24 * 60))
        if start <= end:
            return start - 36 <= minutes <= end + 28
        return minutes >= start - 36 or minutes <= end + 28

    def _collective_role_for_npc(self, npc: dict[str, Any], action: dict[str, Any]) -> str:
        npc_id = str(npc.get("id", ""))
        if npc_id in [str(value) for value in action.get("organizer_ids", [])]:
            return "organizer"
        if npc_id in [str(value) for value in action.get("attendee_ids", [])]:
            return "attendee"
        if npc_id in [str(value) for value in action.get("committed_ids", [])]:
            return "committed"
        if npc_id in [str(value) for value in action.get("supporter_ids", [])]:
            return "supporter"
        if npc_id in [str(value) for value in action.get("response_actor_ids", [])]:
            response_mode = str(action.get("response_mode", "observe"))
            if response_mode == "negotiate":
                return "negotiator"
            if response_mode == "suppress":
                return "suppressor"
            return "observer"
        if npc_id in [str(value) for value in action.get("heard_ids", [])]:
            return "listener"
        return ""

    def _collective_ring_offset(self, npc_id: str, role: str, minutes: int) -> tuple[float, float]:
        seed = sum(ord(ch) for ch in npc_id) % 17
        angle = (minutes / 14.0) + seed * 0.41
        radius = 26.0
        if role == "organizer":
            radius = 18.0
        elif role == "attendee":
            radius = 28.0
        elif role == "committed":
            radius = 34.0
        elif role == "supporter":
            radius = 40.0
        elif role == "negotiator":
            radius = 22.0
        elif role == "suppressor":
            radius = 54.0
        elif role == "observer":
            radius = 62.0
        elif role == "listener":
            radius = 46.0
        if role == "suppressor":
            angle = -0.8 + seed * 0.14
        elif role == "negotiator":
            angle = 2.4 + seed * 0.18
        return round(math.cos(angle) * radius, 1), round(math.sin(angle) * radius, 1)

    def _collective_activity_for_role(self, action: dict[str, Any], role: str, minutes: int) -> str:
        kind = str(action.get("kind", "meeting"))
        start = int(action.get("window_start_minutes", 0))
        if role in {"suppressor", "observer"}:
            return "responding" if str(action.get("response_mode", "")) == "suppress" else "watching"
        if role == "negotiator":
            return "negotiating"
        if minutes < start and role in {"organizer", "committed", "supporter"}:
            return "assembling"
        if kind == "meeting":
            return "meeting"
        if kind in {"strike", "rally"}:
            return "protesting"
        if kind == "party":
            return "gathering"
        return "assembling"

    def _collective_goal_for_role(self, action: dict[str, Any], role: str) -> str:
        label = str(action.get("label", "集体行动"))
        if role == "organizer":
            return f"把 {label} 组织起来"
        if role in {"attendee", "committed", "supporter", "listener"}:
            return f"朝 {label} 靠过去"
        if role == "negotiator":
            return f"去和 {label} 试探让步口风"
        if role == "suppressor":
            return f"压住 {label} 的规模"
        if role == "observer":
            return f"盯住 {label} 的人数和风向"
        return str(action.get("label", "守住今天"))

    def _collective_schedule_note(self, npc: dict[str, Any], action: dict[str, Any], role: str) -> str:
        title = str(action.get("target_location_title", "集合点"))
        label = str(action.get("label", "集体行动"))
        if role == "organizer":
            return f"{npc['name']} 正往 {title} 串人，准备把 {label} 顶起来。"
        if role in {"attendee", "committed", "supporter"}:
            return f"{npc['name']} 正往 {title} 靠，准备参加 {label}。"
        if role == "listener":
            return f"{npc['name']} 正往 {title} 张望，想看 {label} 到底会不会成。"
        if role == "negotiator":
            return f"{npc['name']} 正往 {title} 赶，准备和 {label} 谈条件。"
        if role == "suppressor":
            return f"{npc['name']} 正往 {title} 压过去，准备把 {label} 控下来。"
        if role == "observer":
            return f"{npc['name']} 正在 {title} 周围盯着 {label}。"
        return str(npc.get("schedule_note", ""))

    def _collective_schedule_override(self, npc: dict[str, Any], minutes: int) -> dict[str, Any]:
        best: dict[str, Any] | None = None
        best_role = ""
        for action in self.state.get("collective_action_registry", []):
            role = self._collective_role_for_npc(npc, action)
            if not role:
                continue
            district = str(action.get("district", ""))
            scope = str(action.get("scope", "district"))
            # Collective responders often come from government or company offices
            # outside the action district, so they should still be dispatched.
            if scope != "city" and district and district != str(npc.get("district", "")) and role not in {"negotiator", "suppressor", "observer"}:
                continue
            if not self._collective_action_live_now(action, minutes):
                continue
            if best is None:
                best = action
                best_role = role
                continue
            best_score = self._collective_stage_rank(str(best.get("stage", ""))) * 10.0 + float(best.get("heat", 0.0)) * 4.0 + float(best.get("support", 0.0)) * 3.0
            score = self._collective_stage_rank(str(action.get("stage", ""))) * 10.0 + float(action.get("heat", 0.0)) * 4.0 + float(action.get("support", 0.0)) * 3.0
            if score > best_score:
                best = action
                best_role = role
        if best is None:
            return {}
        anchor_x = float(best.get("response_target_x", 0.0)) if best_role in {"negotiator", "suppressor", "observer"} else float(best.get("target_x", 0.0))
        anchor_y = float(best.get("response_target_y", 0.0)) if best_role in {"negotiator", "suppressor", "observer"} else float(best.get("target_y", 0.0))
        offset_x, offset_y = self._collective_ring_offset(str(npc.get("id", "")), best_role, minutes)
        return {
            "action_id": str(best.get("id", "")),
            "role": best_role,
            "activity": self._collective_activity_for_role(best, best_role, minutes),
            "x": round(anchor_x + offset_x, 1),
            "y": round(anchor_y + offset_y, 1),
            "target_subregion_id": str(best.get("target_subregion_id", "")),
            "target_subregion_name": str(best.get("target_subregion_name", "")),
            "goal": self._collective_goal_for_role(best, best_role),
            "schedule_note": self._collective_schedule_note(npc, best, best_role),
            "response_mode": str(best.get("response_mode", "")),
        }

    def _apply_npc_schedule(self) -> None:
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        period = str(self.state.get("time_period", "day"))
        for npc in self.state["npcs"]:
            work_anchor = {"x": float(npc.get("work_x", npc.get("x", 0.0))), "y": float(npc.get("work_y", npc.get("y", 0.0)))}
            home_anchor = {"x": float(npc.get("home_x", npc.get("x", 0.0))), "y": float(npc.get("home_y", npc.get("y", 0.0)))}
            depart_start, work_start, work_end, settle_home, sleep_start = self._schedule_window_for_npc(npc)
            target = work_anchor
            activity = "working"
            home_state = "away"
            npc["schedule_anchor_type"] = "default"
            npc["subregion_id"] = str(npc.get("work_subregion_id", npc.get("subregion_id", "")))
            npc["subregion_name"] = str(npc.get("work_subregion_name", npc.get("subregion_name", "")))
            npc["collective_action_id"] = ""
            npc["collective_role"] = ""
            npc["response_mode"] = ""
            npc["doc_action"] = ""
            npc["doc_target_tag"] = ""
            social_override: dict[str, Any] = {}
            if work_start <= minutes < work_end:
                target = self._schedule_patrol_anchor(npc, work_anchor, "work", minutes)
                activity = "working"
            elif depart_start <= minutes < work_start:
                ratio = (minutes - depart_start) / max(work_start - depart_start, 1)
                target = {
                    "x": home_anchor["x"] + (work_anchor["x"] - home_anchor["x"]) * ratio,
                    "y": home_anchor["y"] + (work_anchor["y"] - home_anchor["y"]) * ratio,
                }
                activity = "commuting"
            elif work_end <= minutes < settle_home:
                ratio = (minutes - work_end) / max(settle_home - work_end, 1)
                target = {
                    "x": work_anchor["x"] + (home_anchor["x"] - work_anchor["x"]) * ratio,
                    "y": work_anchor["y"] + (home_anchor["y"] - work_anchor["y"]) * ratio,
                }
                activity = "returning"
            else:
                target = self._schedule_patrol_anchor(npc, home_anchor, "home", minutes)
                activity = "home"
                npc["subregion_id"] = str(npc.get("home_subregion_id", npc.get("subregion_id", "")))
                npc["subregion_name"] = str(npc.get("home_subregion_name", npc.get("subregion_name", "")))
                if minutes >= sleep_start or minutes < max(depart_start - 40, 0):
                    home_state = "sleeping"
                elif settle_home <= minutes < sleep_start:
                    home_state = "evening_home"
                else:
                    home_state = "resting"
            doc_override = self._doc_schedule_override(npc, minutes)
            if doc_override:
                target = {"x": float(doc_override.get("x", target["x"])), "y": float(doc_override.get("y", target["y"]))}
                activity = str(doc_override.get("activity", activity))
                home_state = "away" if activity != "home" else "resting"
                npc["subregion_id"] = str(doc_override.get("target_subregion_id", npc.get("subregion_id", "")))
                npc["subregion_name"] = str(doc_override.get("target_subregion_name", npc.get("subregion_name", "")))
                npc["current_goal"] = str(doc_override.get("goal", npc.get("current_goal", "")))
                npc["current_target"] = str(doc_override.get("current_target", npc.get("current_target", "")))
                npc["schedule_anchor_type"] = str(doc_override.get("anchor_type", "doc_poi"))
                npc["doc_action"] = str(doc_override.get("doc_action", ""))
                npc["doc_target_tag"] = str(doc_override.get("target_tag", ""))
            collective_override = self._collective_schedule_override(npc, minutes)
            if collective_override:
                target = {"x": float(collective_override.get("x", target["x"])), "y": float(collective_override.get("y", target["y"]))}
                activity = str(collective_override.get("activity", activity))
                home_state = "away"
                npc["subregion_id"] = str(collective_override.get("target_subregion_id", npc.get("subregion_id", "")))
                npc["subregion_name"] = str(collective_override.get("target_subregion_name", npc.get("subregion_name", "")))
                npc["collective_action_id"] = str(collective_override.get("action_id", ""))
                npc["collective_role"] = str(collective_override.get("role", ""))
                npc["response_mode"] = str(collective_override.get("response_mode", ""))
                npc["current_goal"] = str(collective_override.get("goal", npc.get("current_goal", "")))
                npc["current_target"] = str(collective_override.get("goal", npc.get("current_target", "")))
            else:
                social_override = self._social_schedule_override(npc, minutes, activity)
                if social_override:
                    target = {"x": float(social_override.get("x", target["x"])), "y": float(social_override.get("y", target["y"]))}
                    activity = str(social_override.get("activity", activity))
                    if activity != "home":
                        home_state = "away"
                    npc["subregion_id"] = str(social_override.get("target_subregion_id", npc.get("subregion_id", "")))
                    npc["subregion_name"] = str(social_override.get("target_subregion_name", npc.get("subregion_name", "")))
                    npc["current_goal"] = str(social_override.get("goal", npc.get("current_goal", "")))
                    npc["current_target"] = str(social_override.get("current_target", npc.get("current_target", "")))
            route_x, route_y = self._activity_route_offset(npc, minutes, activity, home_state)
            npc["x"] = round(target["x"] + route_x, 1)
            npc["y"] = round(target["y"] + route_y, 1)
            npc["activity"] = activity
            npc["home_state"] = home_state
            npc["indoor_activity"] = self._indoor_activity_for_npc(npc, activity, home_state, minutes)
            npc["lights_on"] = activity == "home" and (period in {"dawn", "dusk", "night"} or home_state in {"sleeping", "evening_home"})
            carry_prop, carry_alpha = self._carry_state_for_npc(
                npc,
                activity,
                minutes,
                depart_start,
                work_start,
                work_end,
                settle_home,
            )
            npc["carry_prop"] = carry_prop
            npc["carry_alpha"] = carry_alpha
            if collective_override:
                npc["schedule_note"] = str(collective_override.get("schedule_note", npc.get("schedule_note", "")))
            elif doc_override:
                npc["schedule_note"] = str(doc_override.get("schedule_note", npc.get("schedule_note", "")))
            elif social_override:
                npc["schedule_note"] = str(social_override.get("schedule_note", npc.get("schedule_note", "")))
            else:
                npc["schedule_note"] = self._schedule_note_for_npc(
                    npc,
                    activity,
                    home_state,
                    str(npc.get("indoor_activity", "away")),
                    minutes,
                )
        for district in self.state["districts"]:
            district["traffic"] = self._traffic_for_district(district)

    def _schedule_patrol_anchor(
        self,
        npc: dict[str, Any],
        base_anchor: dict[str, float],
        mode: str,
        minutes: int,
    ) -> dict[str, float]:
        slot_x, slot_y = self._npc_slot_offset(npc, mode)
        if mode == "home":
            route_points = self._residence_patrol_points(str(npc.get("home_id", "")))
        else:
            route_points = SUBREGION_ROUTE_POINTS.get(str(npc.get("work_subregion_id", npc.get("subregion_id", ""))), [])
        if not route_points:
            return {"x": round(float(base_anchor["x"]) + slot_x, 1), "y": round(float(base_anchor["y"]) + slot_y, 1)}
        try:
            index_seed = max(1, int(str(npc.get("id", "npc_1")).split("_")[-1]))
        except ValueError:
            index_seed = (sum(ord(ch) for ch in str(npc.get("id", ""))) % 20) + 1
        cadence = 24 if mode == "home" else 18
        slot = int(minutes // cadence + index_seed) % len(route_points)
        next_slot = (slot + 1) % len(route_points)
        ratio = (minutes % cadence) / float(cadence)
        ax, ay = route_points[slot]
        bx, by = route_points[next_slot]
        mix = 0.18 + ratio * 0.64
        target_x = ax + (bx - ax) * mix
        target_y = ay + (by - ay) * mix
        return {
            "x": round((target_x + float(base_anchor["x"]) * 0.35) / 1.35 + slot_x * 0.55, 1),
            "y": round((target_y + float(base_anchor["y"]) * 0.35) / 1.35 + slot_y * 0.55, 1),
        }

    def _traffic_for_district(self, district: dict[str, Any]) -> int:
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        base = int(district.get("traffic", 55))
        if minutes >= 20 * 60 or minutes < 6 * 60:
            return max(18, base - 28)
        if minutes < 8 * 60:
            return max(26, base - 12)
        if minutes < 17 * 60:
            return min(92, base + 4)
        return max(24, base - 6)

    def _derive_home_anchor(self, npc: dict[str, Any], index: int) -> tuple[float, float]:
        residence = next(
            (row for row in self._residence_rows() if str(row.get("id", "")) == str(npc.get("home_id", ""))),
            {},
        )
        return self._residence_anchor(residence, int(npc.get("home_slot", index)), "door")

    def _schedule_role_for_npc(self, npc: dict[str, Any]) -> str:
        band = str(npc.get("social_band", self._npc_social_band(npc)))
        role = str(npc.get("role", ""))
        if band in {"media", "organizer"} or role in {"记者", "工会领袖"}:
            return "roamer"
        if band in {"elite", "authority", "manager", "finance", "trade"} or role in {"店主", "老板", "代理人", "银行经理"}:
            return "keeper"
        return "worker"

    def _derive_home_anchor(self, npc: dict[str, Any], index: int) -> tuple[float, float]:
        residence = next(
            (row for row in self._residence_rows() if str(row.get("id", "")) == str(npc.get("home_id", ""))),
            {},
        )
        return self._residence_anchor(residence, int(npc.get("home_slot", index)), "door")

    def _house_for_district(self, district_name: str) -> dict[str, str]:
        residences = self._residences_for_district(district_name)
        if residences:
            return copy.deepcopy(residences[0])
        return copy.deepcopy(HOUSE_DEFS.get(district_name, HOUSE_DEFS["贫民街"]))

    def _schedule_window_for_npc(self, npc: dict[str, Any]) -> tuple[int, int, int, int, int]:
        role = str(npc.get("schedule_role", "worker"))
        if role == "keeper":
            return 6 * 60 + 20, 7 * 60 + 30, 18 * 60, 19 * 60 + 5, 22 * 60
        if role == "roamer":
            return 7 * 60, 8 * 60 + 30, 18 * 60 + 30, 20 * 60 + 15, 22 * 60 + 30
        return 6 * 60, 8 * 60, 17 * 60, 19 * 60 + 20, 21 * 60 + 30

    def _activity_route_offset(self, npc: dict[str, Any], minutes: int, activity: str, home_state: str) -> tuple[float, float]:
        raw_id = str(npc.get("id", "npc_0")).split("_")[-1]
        try:
            index = max(1, int(raw_id))
        except ValueError:
            index = max(1, (sum(ord(ch) for ch in str(npc.get("id", ""))) % 19) + 1)
        role = str(npc.get("schedule_role", "worker"))
        district = str(npc.get("district", ""))
        subregion = str(npc.get("subregion_id", ""))
        sub_seed = (sum(ord(ch) for ch in subregion) % 23) / 23.0
        phase = minutes / 18.0 + index * 0.71 + sub_seed * 2.6
        route_step = int(minutes // (16 if role == "roamer" else 22 if role == "keeper" else 18) + index) % 5
        route_points = [
            (-1.0, -0.25),
            (-0.45, 0.82),
            (0.72, 0.58),
            (0.94, -0.42),
            (0.08, -0.9),
        ]
        turn_x, turn_y = route_points[route_step]
        drift_x = math.sin(phase) * 0.34 + math.cos(phase * 0.47) * 0.18
        drift_y = math.cos(phase * 1.13) * 0.28 + math.sin(phase * 0.63) * 0.14
        if district == "港口":
            drift_y *= 0.62
            drift_x += 0.08
        elif district == "交易所":
            drift_x *= 0.76
            drift_y -= 0.06
        elif district == "工厂区":
            drift_y += 0.1
        else:
            drift_x -= 0.06
        if activity == "working":
            radius_x, radius_y = 18.0, 10.0
            if role == "roamer":
                radius_x, radius_y = 34.0, 18.0
            elif role == "keeper":
                radius_x, radius_y = 14.0, 8.0
        elif activity in {"commuting", "returning"}:
            radius_x, radius_y = 12.0, 6.0
            turn_x *= 0.55
            turn_y *= 0.45
        elif activity in {"assembling", "meeting", "protesting", "gathering", "responding", "negotiating", "watching"}:
            radius_x, radius_y = 10.0, 6.0
            if activity in {"protesting", "responding"}:
                radius_x, radius_y = 16.0, 9.0
            elif activity == "negotiating":
                radius_x, radius_y = 8.0, 5.0
            turn_x *= 0.48
            turn_y *= 0.42
        else:
            if home_state == "sleeping":
                return round(math.sin(phase * 0.45) * 0.9, 1), round(math.cos(phase * 0.35) * 0.7, 1)
            radius_x, radius_y = (8.0, 4.0) if home_state == "resting" else (14.0, 8.0)
        return round((turn_x + drift_x) * radius_x, 1), round((turn_y + drift_y) * radius_y, 1)

    def _indoor_activity_for_npc(self, npc: dict[str, Any], activity: str, home_state: str, minutes: int) -> str:
        if activity != "home":
            return "away"
        if home_state == "sleeping":
            return "sleeping"
        role = str(npc.get("role", ""))
        district = str(npc.get("district", ""))
        npc_seed = int(str(npc.get("id", "npc_0")).split("_")[-1])
        is_early_evening = home_state == "evening_home"
        if role in {"记者", "银行经理"}:
            return "ledger" if is_early_evening else "reading"
        if role in {"代理人", "投机者"}:
            return "ledger" if minutes < 22 * 60 else "reading"
        if role in {"店主", "老板"}:
            return "sorting_goods" if is_early_evening else "ledger"
        if district == "港口":
            return "cooking" if is_early_evening else ("mending" if npc_seed % 2 == 0 else "eating")
        if district == "工厂区":
            return "washing" if is_early_evening else ("mending" if npc_seed % 2 == 0 else "warming")
        if district == "交易所":
            return "ledger" if is_early_evening else ("reading" if npc_seed % 2 == 0 else "eating")
        if minutes < 6 * 60 + 20:
            return "warming"
        return "cooking" if is_early_evening else ("sorting_goods" if npc_seed % 2 == 0 else "mending")

    def _carry_state_for_npc(
        self,
        npc: dict[str, Any],
        activity: str,
        minutes: int,
        depart_start: int,
        work_start: int,
        work_end: int,
        settle_home: int,
    ) -> tuple[str, float]:
        if activity == "commuting":
            commute_span = max(work_start - depart_start, 1)
            progress = (minutes - depart_start) / commute_span
            alpha = max(0.18, min(1.0, 1.08 - progress * 0.78))
            return self._morning_carry_prop(npc), round(alpha, 3)
        if activity == "returning":
            return_span = max(settle_home - work_end, 1)
            progress = (minutes - work_end) / return_span
            alpha = max(0.14, min(0.62, 0.58 - progress * 0.34))
            return self._evening_carry_prop(npc), round(alpha, 3)
        return "", 0.0

    def _morning_carry_prop(self, npc: dict[str, Any]) -> str:
        role = str(npc.get("role", ""))
        district = str(npc.get("district", ""))
        home_class = str(npc.get("home_class", ""))
        if role in {"记者", "银行经理"}:
            return "ledger"
        if role in {"工人", "工会领袖"} or district == "工厂区":
            return "tool"
        if role in {"代理人", "店主"} or district == "交易所":
            return "ledger"
        if district == "港口":
            return "satchel"
        if home_class in {"merchant", "upper"}:
            return "ledger"
        return "breakfast"

    def _evening_carry_prop(self, npc: dict[str, Any]) -> str:
        district = str(npc.get("district", ""))
        if district == "工厂区":
            return "tool"
        if district == "交易所":
            return "ledger"
        return "satchel"

    def _schedule_note_for_npc(
        self,
        npc: dict[str, Any],
        activity: str,
        home_state: str,
        indoor_activity: str,
        minutes: int,
    ) -> str:
        house_title = str(npc.get("home_label", "屋里"))
        if activity == "working":
            return f"{npc['name']} 白天还在 {npc['district']} 忙活。"
        if activity == "commuting":
            return f"{npc['name']} 正从 {house_title} 往工位赶。"
        if activity == "returning":
            return f"{npc['name']} 正往 {house_title} 收工回去。"
        if home_state == "sleeping":
            return f"{house_title} 的灯压暗了，{npc['name']} 已经歇下。"
        if indoor_activity == "cooking":
            return f"{npc['name']} 刚回到 {house_title}，正把锅重新热上。"
        if indoor_activity == "ledger":
            return f"{npc['name']} 在 {house_title} 的灯下翻账和记价。"
        if indoor_activity == "sorting_goods":
            return f"{npc['name']} 在 {house_title} 里翻箱清点剩货。"
        if indoor_activity == "washing":
            return f"{npc['name']} 回家先在 {house_title} 里洗灰和煤味。"
        if indoor_activity == "mending":
            return f"{npc['name']} 在 {house_title} 里补衣修工具，手还没停。"
        if indoor_activity == "reading":
            return f"{npc['name']} 在 {house_title} 里借着烛光翻纸页。"
        if indoor_activity == "eating":
            return f"{npc['name']} 端着热汤坐回了 {house_title}。"
        if home_state == "evening_home":
            return f"{npc['name']} 刚回到 {house_title}，灶火和灯还亮着。"
        if minutes < 6 * 60 + 20:
            return f"{npc['name']} 还在 {house_title} 里赖着不肯出门。"
        return f"{npc['name']} 正在 {house_title} 里歇脚整理东西。"

    def _build_house_states(self) -> dict[str, Any]:
        house_states: dict[str, Any] = {}
        priority = {"sleeping": 4, "evening_home": 3, "resting": 2, "away": 1}
        activity_priority = {
            "sleeping": 8,
            "ledger": 7,
            "cooking": 6,
            "sorting_goods": 5,
            "washing": 5,
            "mending": 4,
            "reading": 3,
            "eating": 3,
            "warming": 2,
            "away": 0,
        }
        residence_rows = self._residence_rows()
        if not residence_rows:
            residence_rows = [dict(meta) for meta in HOUSE_DEFS.values()]
        for meta in residence_rows:
            house_id = str(meta.get("id", ""))
            if not house_id:
                continue
            district_name = str(meta.get("district", ""))
            house_states[house_id] = {
                "id": house_id,
                "title": str(meta.get("title", house_id)),
                "district": district_name,
                "subregion_id": str(meta.get("subregion_id", "")),
                "household_class": str(meta.get("class", "")),
                "scene_id": meta.get("scene_id", ""),
                "entry_spawn_id": meta.get("entry_spawn_id", ""),
                "scene_anchor": {
                    "x": round(float(meta.get("anchor_x", 0.0)), 1),
                    "y": round(float(meta.get("anchor_y", 0.0)), 1),
                },
                "resident_count": 0,
                "residents_home": 0,
                "sleeping_count": 0,
                "lights_on": False,
                "primary_state": "away",
                "primary_resident": "",
                "primary_activity": "away",
                "secondary_activity": "away",
                "schedule_note": "白天屋里还空着。",
                "resident_names": [],
                "activity_mix": {},
                "summary_line": "",
                "commuting_count": 0,
                "window_glow_boost": 0.0,
                "residual_warmth": 0.0,
                "breakfast_leftovers": 0.0,
                "doorstep_alpha": 0.0,
                "doorstep_note": "",
                "doorstep_prop": "",
                "window_curve": "plain",
                "commuting_props": {},
            }
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        period = str(self.state.get("time_period", "day"))
        for npc in self.state["npcs"]:
            home_id = str(npc.get("home_id", ""))
            if not home_id or home_id not in house_states:
                continue
            house_state = house_states[home_id]
            house_state["resident_count"] += 1
            house_state["resident_names"].append(str(npc.get("name", "")))
            if npc.get("activity") == "commuting":
                house_state["commuting_count"] += 1
                carry_prop = str(npc.get("carry_prop", ""))
                if carry_prop:
                    commute_props = house_state.get("commuting_props", {})
                    commute_props[carry_prop] = int(commute_props.get(carry_prop, 0)) + 1
                    house_state["commuting_props"] = commute_props
            if npc.get("activity") == "home":
                house_state["residents_home"] += 1
                activity_name = str(npc.get("indoor_activity", "away"))
                house_state["activity_mix"][activity_name] = int(house_state["activity_mix"].get(activity_name, 0)) + 1
                if npc.get("home_state") == "sleeping":
                    house_state["sleeping_count"] += 1
            house_state["lights_on"] = bool(house_state["lights_on"] or npc.get("lights_on", False))
            current_priority = priority.get(str(npc.get("home_state", "away")), 0)
            existing_priority = priority.get(str(house_state.get("primary_state", "away")), 0)
            current_activity = str(npc.get("indoor_activity", "away"))
            existing_activity = str(house_state.get("primary_activity", "away"))
            if current_priority > existing_priority or (
                current_priority == existing_priority
                and activity_priority.get(current_activity, 0) >= activity_priority.get(existing_activity, 0)
            ):
                house_state["primary_state"] = str(npc.get("home_state", "away"))
                house_state["primary_resident"] = str(npc.get("name", ""))
                house_state["primary_activity"] = current_activity
                house_state["schedule_note"] = str(npc.get("schedule_note", house_state["schedule_note"]))
        for house_state in house_states.values():
            house_state["resident_names"] = house_state["resident_names"][:4]
            activity_mix = {
                name: count
                for name, count in house_state.get("activity_mix", {}).items()
                if name != str(house_state.get("primary_activity", "away"))
            }
            if activity_mix:
                house_state["secondary_activity"] = max(activity_mix, key=activity_mix.get)
            self._decorate_house_transition_state(house_state, minutes, period)
            house_state["summary_line"] = self._compose_house_summary(house_state)
            house_state.pop("activity_mix", None)
            house_state.pop("commuting_props", None)
        return house_states

    def _decorate_house_transition_state(self, house_state: dict[str, Any], minutes: int, period: str) -> None:
        commuting_count = int(house_state.get("commuting_count", 0))
        residents_home = int(house_state.get("residents_home", 0))
        house_id = str(house_state.get("id", "slum_house"))
        curve_profiles = {
            "slum_house": {"start": 6 * 60 + 2, "end": 7 * 60 + 26, "power": 1.4, "curve": "warm_fast"},
            "dock_house": {"start": 6 * 60 + 8, "end": 7 * 60 + 56, "power": 0.88, "curve": "mist_long"},
            "factory_house": {"start": 5 * 60 + 58, "end": 7 * 60 + 44, "power": 1.12, "curve": "ember_pulse"},
            "exchange_house": {"start": 6 * 60 + 18, "end": 8 * 60 + 18, "power": 0.72, "curve": "gold_linger"},
        }
        profile = curve_profiles.get(house_id, curve_profiles["slum_house"])
        start_minutes = int(profile["start"])
        end_minutes = int(profile["end"])
        decay_progress = 0.0
        if minutes > start_minutes:
            decay_progress = max(0.0, min(1.0, (minutes - start_minutes) / max(end_minutes - start_minutes, 1)))
        morning_window = max(0.0, min(1.0, pow(1.0 - decay_progress, float(profile["power"]))))
        doorstep_alpha = 0.0
        if period in {"dawn", "day"}:
            if commuting_count > 0:
                doorstep_alpha = 0.42 + min(0.42, commuting_count * 0.18)
            elif residents_home <= 0 and minutes < 8 * 60 + 40:
                doorstep_alpha = 0.22
            doorstep_alpha *= morning_window
        window_boost = 0.0
        if bool(house_state.get("lights_on", False)):
            window_boost = 0.16
        if doorstep_alpha > 0.0:
            window_boost = max(window_boost, 0.08 + doorstep_alpha * 0.34)
        residual_warmth = 0.0
        breakfast_leftovers = 0.0
        primary_activity = str(house_state.get("primary_activity", "away"))
        if primary_activity in {"cooking", "warming", "eating"}:
            residual_warmth = 0.62
            breakfast_leftovers = 0.56
        elif doorstep_alpha > 0.0:
            residual_warmth = 0.28 + doorstep_alpha * 0.34
            breakfast_leftovers = 0.18 + doorstep_alpha * 0.36
        elif period == "dawn" and residents_home <= 0:
            residual_warmth = 0.26
            breakfast_leftovers = 0.22
        house_state["window_glow_boost"] = round(min(window_boost, 0.52), 3)
        house_state["residual_warmth"] = round(min(residual_warmth, 0.82), 3)
        house_state["breakfast_leftovers"] = round(min(breakfast_leftovers, 0.78), 3)
        house_state["doorstep_alpha"] = round(min(doorstep_alpha, 0.84), 3)
        house_state["window_curve"] = str(profile.get("curve", "plain"))
        commute_props = house_state.get("commuting_props", {})
        if commute_props:
            house_state["doorstep_prop"] = max(commute_props, key=commute_props.get)
        elif primary_activity in {"ledger", "reading"}:
            house_state["doorstep_prop"] = "ledger"
        elif primary_activity in {"sorting_goods", "mending"}:
            house_state["doorstep_prop"] = "satchel"
        elif primary_activity in {"cooking", "eating", "warming"}:
            house_state["doorstep_prop"] = "breakfast"
        else:
            house_state["doorstep_prop"] = ""
        if doorstep_alpha > 0.06:
            house_state["doorstep_note"] = "门槛边还带着刚离屋的脚步、晨光和余热。"
        elif residual_warmth > 0.2:
            house_state["doorstep_note"] = "门边安静下来后，屋里还留着刚热过锅的温度。"
        else:
            house_state["doorstep_note"] = ""

    def _compose_house_summary(self, house_state: dict[str, Any]) -> str:
        resident = str(house_state.get("primary_resident", "住户"))
        residents_home = int(house_state.get("residents_home", 0))
        sleeping_count = int(house_state.get("sleeping_count", 0))
        activity_name = str(house_state.get("primary_activity", "away"))
        if residents_home <= 0:
            return f"{house_state['title']} 白天多半空着，只剩些锅气和旧木头味。"
        if sleeping_count > 0:
            return f"{house_state['title']} 的床铺已经压出弧度，{resident} 正在里头歇着。"
        if activity_name == "cooking":
            return f"{house_state['title']} 的锅还在冒气，{resident} 正把晚饭重新热上。"
        if activity_name == "ledger":
            return f"{house_state['title']} 的灯下摊着账页，{resident} 还在慢慢对数。"
        if activity_name == "sorting_goods":
            return f"{house_state['title']} 的箱柜还敞着，{resident} 正在清点余粮和旧货。"
        if activity_name == "washing":
            return f"{house_state['title']} 的洗盆边还有水声，{resident} 正把灰尘和汗味洗掉。"
        if activity_name == "mending":
            return f"{house_state['title']} 床边摊着针线和工具，{resident} 还在补衣修物。"
        if activity_name == "reading":
            return f"{house_state['title']} 的烛光压着纸页，{resident} 正靠桌翻看消息。"
        if activity_name == "eating":
            return f"{house_state['title']} 桌边还摆着热汤和碗勺，{resident} 正在慢慢垫肚子。"
        if house_state.get("lights_on"):
            return f"{house_state['title']} 的灯亮着，{resident} 刚回家，屋里有人声和锅火。"
        return f"{house_state['title']} 里正有人停留，桌上账本和器具都还没收。"

    def _clock_label(self) -> str:
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"

    def _bootstrap_family(self, family: dict[str, Any]) -> None:
        total_holdings = sum(int(value) for value in family.get("stock_holdings", {}).values())
        family["asset_scale"] = round(float(family.get("asset_scale", (int(family.get("cash", 0)) + int(family.get("real_estate_holdings", 0)) * 12 + total_holdings * 8) / 100.0)), 2)
        family["risk_appetite"] = round(float(family.get("risk_appetite", 0.35 + min(0.45, int(family.get("debt", 0)) / 220.0))), 3)
        family["liquidity_preference"] = round(float(family.get("liquidity_preference", 0.45 + int(family.get("cash", 0)) / 600.0)), 3)
        family["political_power"] = int(family.get("political_power", 40))
        family["media_power"] = int(family.get("media_power", 20))
        family["primary_industries"] = list(family.get("primary_industries", [str(family.get("type", ""))]))
        family["public_strategy"] = str(family.get("public_strategy", family.get("public_action", family.get("strategy", "观望"))))
        family["shadow_strategy"] = str(family.get("shadow_strategy", family.get("hidden_action", "沿着街头放风")))

    def _bootstrap_company(self, company: dict[str, Any]) -> None:
        company["capacity"] = int(company.get("capacity", 60))
        company["inventory"] = int(company.get("inventory", max(20, int(company["capacity"] * 0.7))))
        company["workers"] = int(company.get("workers", 18))
        company["wage_level"] = int(company.get("wage_level", 6))
        company["accident_risk"] = float(company.get("accident_risk", 0.08))
        company["financing_pressure"] = float(company.get("financing_pressure", 45.0))
        company["order_pressure"] = float(company.get("order_pressure", 50.0))
        company["profit_margin"] = float(company.get("profit_margin", 0.12))
        company["media_sensitivity"] = float(company.get("media_sensitivity", 0.4))
        company["transport_dependency"] = float(company.get("transport_dependency", 0.3))
        company["operating_state"] = str(company.get("operating_state", "steady"))
        company["inventory_state"] = str(company.get("inventory_state", "balanced"))
        company["wage_pressure"] = float(company.get("wage_pressure", 35.0))
        company["payroll_delay"] = float(company.get("payroll_delay", max(4.0, company["financing_pressure"] * 0.22)))
        company["credit_line"] = float(company.get("credit_line", max(18.0, 92.0 - company["financing_pressure"])))

    def _bootstrap_npc(self, npc: dict[str, Any], companies: list[dict[str, Any]]) -> None:
        raw_money = int(npc.get("cash", npc.get("money", 0)))
        npc["cash"] = self._scaled_npc_cash(npc, raw_money)
        npc["debt"] = int(npc.get("debt", max(0, 18 - raw_money)))
        npc["inventory"] = copy.deepcopy(npc.get("inventory", {"面包": 0, "煤": 0, "罐头": 0}))
        npc["reputation"] = int(npc.get("reputation", 18 + int(npc.get("player_relation", 0))))
        npc["player_trust"] = float(npc.get("player_trust", max(0, 42 + int(npc.get("player_relation", 0)) * 4)))
        npc["anxiety"] = float(npc.get("anxiety", npc.get("fear", 0)))
        npc["greed_drive"] = float(npc.get("greed_drive", npc.get("greed", 0)))
        npc["current_target"] = str(npc.get("current_target", npc.get("current_goal", npc.get("district", ""))))
        npc["heard_topic_ids"] = list(npc.get("heard_topic_ids", []))
        npc["last_trade_pnl"] = float(npc.get("last_trade_pnl", 0.0))
        npc["job_security"] = float(npc.get("job_security", max(18.0, 76.0 - npc["debt"] * 0.8)))
        npc["income_type"] = str(npc.get("income_type", self._default_income_type(npc)))
        npc["housing_cost"] = int(npc.get("housing_cost", self._default_housing_cost(npc)))
        npc["rumor_sensitivity"] = float(npc.get("rumor_sensitivity", npc.get("rumor_susceptibility", 0.4)))
        npc["info_reliability"] = float(npc.get("info_reliability", max(0.18, 0.82 - float(npc.get("rumor_susceptibility", 0.4)) * 0.45)))
        npc["moral_floor"] = float(npc.get("moral_floor", max(0.08, 0.72 - float(npc.get("risk_preference", 40)) / 120.0)))
        npc["political_stance"] = str(npc.get("political_stance", "self_preservation"))
        npc["consumption_profile"] = str(npc.get("consumption_profile", "subsistence" if npc.get("class") == "底层" else "status"))
        npc["company_id"] = str(npc.get("company_id", self._infer_company_id_for_npc(npc, companies)))
        npc["information_domain"] = self._npc_information_domains(npc)
        npc["stock_positions"] = copy.deepcopy(npc.get("stock_positions", self._default_stock_positions(npc)))
        npc["goods_positions"] = copy.deepcopy(npc.get("goods_positions", self._default_goods_positions(npc)))
        npc["inventory"] = self._normalize_npc_inventory(npc)
        npc["relationship_memory"] = copy.deepcopy(npc.get("relationship_memory", []))
        npc["dialogue_history"] = copy.deepcopy(npc.get("dialogue_history", []))
        npc["local_memory_bank"] = copy.deepcopy(npc.get("local_memory_bank", []))
        npc["player_memory"] = copy.deepcopy(
            npc.get(
                "player_memory",
                {
                    "talk_count": 0,
                    "friendly_count": 0,
                    "hardball_count": 0,
                    "intel_bought": 0,
                    "pressure_from_player": 0.0,
                    "trust_streak": 0,
                    "cash_gift_total": 0,
                    "cash_gift_count": 0,
                    "intel_spend_total": 0,
                    "last_gift_amount": 0,
                    "bought_over": False,
                    "follows_player": False,
                    "last_topic_id": "",
                    "last_intent": "",
                    "last_approach": "",
                    "last_seen_day": 1,
                },
            )
        )
        npc["agent_prompt"] = self._npc_agent_prompt(npc)
        npc["agent_tool_policy"] = self._npc_tool_policy(npc)
        npc["agent_memory"] = copy.deepcopy(npc.get("agent_memory", []))
        npc["agent_queue"] = copy.deepcopy(npc.get("agent_queue", []))
        npc["agent_budget"] = copy.deepcopy(
            npc.get(
                "agent_budget",
                {
                    "daily_calls": self._npc_daily_agent_budget(npc),
                    "calls_left": self._npc_daily_agent_budget(npc),
                    "player_talk_daily": self._npc_player_talk_budget(npc),
                    "player_talk_left": self._npc_player_talk_budget(npc),
                    "last_day": 1,
                    "last_reason": "",
                },
            )
        )
        npc["agent_policy"] = {
            "cadence": int(npc.get("llm_refresh_cadence", 1)),
            "tool_mode": "observe_only",
            "allow_market_spin": True,
            "allow_news_hint": True,
            "social_style": self._npc_social_style(npc),
            "market_style": self._npc_market_style(npc),
            "agenda": self._npc_agent_agenda(npc),
            "budget_weight": round(max(0.4, min(1.8, self._npc_daily_agent_budget(npc) / 6.0)), 2),
        }
        npc["proactive_interest"] = float(
            npc.get(
                "proactive_interest",
                max(0.24, min(0.92, 0.28 + float(npc.get("player_relation", 0)) * 0.06 + float(npc.get("social_radius", 160)) / 520.0)),
            )
        )
        npc["proactive_cooldown_until"] = float(npc.get("proactive_cooldown_until", 0.0))

    def _default_income_type(self, npc: dict[str, Any]) -> str:
        role = str(npc.get("role", ""))
        if role in {"工人", "临时工", "工会领袖"}:
            return "wage"
        if role in {"店主", "老板"}:
            return "business"
        if role in {"记者", "代理人", "银行经理"}:
            return "commission"
        if role in {"投机者"}:
            return "speculation"
        return "odd_jobs"

    def _scaled_npc_cash(self, npc: dict[str, Any], raw_money: int) -> int:
        title = str(npc.get("title", ""))
        class_name = str(npc.get("class", ""))
        role = str(npc.get("role", ""))
        family = str(npc.get("family_affiliation", ""))
        if title == "珊瑚银行掌门":
            return 500_000
        if "掌门" in title:
            return min(420_000, 320_000 + raw_money * 1200)
        if title in {"镇长", "财政与市场监管官"}:
            return min(280_000, 190_000 + raw_money * 900)
        if class_name == "特殊角色":
            return min(220_000, 120_000 + raw_money * 850)
        if class_name == "关键角色":
            return min(120_000, 32_000 + raw_money * 820)
        if class_name == "中层":
            return min(80_000, 12_000 + raw_money * 520)
        if role in {"店主", "记者", "代理人", "银行经理", "投机者"}:
            return min(65_000, 10_000 + raw_money * 480)
        if family not in {"", "无"}:
            return min(90_000, 18_000 + raw_money * 560)
        return min(24_000, 2_000 + raw_money * 220)

    def _npc_bribe_threshold(self, npc: dict[str, Any]) -> int:
        class_name = str(npc.get("class", ""))
        title = str(npc.get("title", ""))
        if title == "珊瑚银行掌门":
            return 250_000
        if "掌门" in title:
            return 180_000
        if class_name == "特殊角色":
            return 120_000
        if class_name == "关键角色":
            return 40_000
        if class_name == "中层":
            return 20_000
        return 10_000

    def _npc_follow_threshold(self, npc: dict[str, Any]) -> int:
        return int(round(self._npc_bribe_threshold(npc) * 1.6))

    def _npc_can_sell_info(self, npc: dict[str, Any]) -> bool:
        role = str(npc.get("role", ""))
        memory = self._npc_player_memory(npc)
        favorability = self._npc_favorability_state(npc)
        if role in {"记者", "代理人", "银行经理", "投机者"}:
            return True
        if int(memory.get("intel_bought", 0)) > 0:
            return True
        if bool(memory.get("bought_over", False)) or bool(memory.get("follows_player", False)):
            return True
        if float(npc.get("player_trust", 0.0)) >= 68.0:
            return True
        if float(favorability.get("disclosure_willingness", 0.0)) >= 0.56:
            return True
        return False

    def _npc_intel_price(self, npc: dict[str, Any], topic: dict[str, Any] | None = None) -> int:
        role = str(npc.get("role", ""))
        class_name = str(npc.get("class", ""))
        topic_kind = str((topic or {}).get("kind", ""))
        favorability = self._npc_favorability_state(npc)
        price = 240
        if role in {"记者", "代理人"}:
            price = 600
        elif role in {"银行经理", "投机者"}:
            price = 1200
        elif class_name == "特殊角色":
            price = 2200
        elif class_name == "关键角色":
            price = 900
        elif class_name == "中层":
            price = 480
        if topic_kind in {"finance", "asset", "family", "company", "institution"}:
            price = int(round(price * 1.6))
        elif topic_kind in {"labor", "public"}:
            price = int(round(price * 1.2))
        trust_discount = max(0.72, 1.0 - float(npc.get("player_trust", 0.0)) / 220.0)
        register = str(favorability.get("speech_register", ""))
        register_markup = 1.12 if register in {"hostile", "guarded"} else 0.84 if register == "owned" else 0.88 if register in {"bought", "patronized", "warm", "deferential"} else 1.0
        return max(80, int(round(price * trust_discount * float(favorability.get("intel_discount", 1.0)) * register_markup)))

    def _npc_patronage_status(self, npc: dict[str, Any]) -> str:
        memory = self._npc_player_memory(npc)
        if bool(memory.get("follows_player", False)):
            return "跟着你"
        if bool(memory.get("bought_over", False)):
            return "被你收买"
        total = int(memory.get("cash_gift_total", 0))
        if total >= max(4_000, int(self._npc_bribe_threshold(npc) * 0.35)):
            return "吃过你的钱"
        return ""

    def _default_housing_cost(self, npc: dict[str, Any]) -> int:
        class_name = str(npc.get("class", ""))
        if class_name == "特殊角色":
            return 10
        if class_name == "关键角色":
            return 8
        if class_name == "中层":
            return 6
        return 3

    def _npc_daily_agent_budget(self, npc: dict[str, Any]) -> int:
        class_name = str(npc.get("class", ""))
        if class_name == "特殊角色":
            return 10
        if class_name == "关键角色":
            return 8
        if class_name == "中层":
            return 6
        role = str(npc.get("role", ""))
        if role in {"记者", "代理人", "银行经理"}:
            return 8
        if role in {"工会领袖", "投机者", "老板"}:
            return 7
        if role in {"店主"}:
            return 6
        return 5

    def _npc_player_talk_budget(self, npc: dict[str, Any]) -> int:
        class_name = str(npc.get("class", ""))
        if class_name == "特殊角色":
            return 30
        if class_name == "关键角色":
            return 24
        if class_name == "中层":
            return 20
        role = str(npc.get("role", ""))
        if role in {"记者", "代理人", "银行经理"}:
            return 26
        if role in {"工会领袖", "投机者", "老板"}:
            return 22
        if role in {"店主"}:
            return 20
        return 18

    def _npc_tool_policy(self, npc: dict[str, Any]) -> list[str]:
        policy = ["只观察截图与状态", "不篡改规则层事实", "不直接改价格", "不输出思维过程", "必须只说中文"]
        role = str(npc.get("role", ""))
        district = str(npc.get("district", ""))
        family = str(npc.get("family_affiliation", "")) or "无"
        if role in {"记者", "代理人"}:
            policy.append("优先包装传闻与舆论")
        if role in {"工人", "临时工", "工会领袖"}:
            policy.append("优先关心工钱、班次、口粮和住房")
        if role in {"投机者", "银行经理"}:
            policy.append("优先关心利率、信用、仓位和抛压")
        if role in {"老板", "店主"}:
            policy.append("优先保护现金流、库存和客流")
        if family != "无":
            policy.append(f"优先维护{family}的表面利益")
        if district == "交易所":
            policy.append("默认从资金和价格角度理解事件")
        elif district == "工厂区":
            policy.append("默认从工钱、裁员和罢工角度理解事件")
        elif district == "港口":
            policy.append("默认从货流、班次和装卸风险角度理解事件")
        else:
            policy.append("默认从房租、粮价和街头口碑角度理解事件")
        return policy

    def _npc_social_style(self, npc: dict[str, Any]) -> str:
        role = str(npc.get("role", ""))
        if role in {"记者", "代理人"}:
            return "主动探口风，擅长递话、试探和二次传播"
        if role == "工会领袖":
            return "会主动把零散抱怨拢成集体情绪"
        if role in {"投机者", "银行经理"}:
            return "偏冷静，先看筹码，再决定要不要说真话"
        if role in {"老板", "店主"}:
            return "先算账，再说话，倾向维护自己的地盘"
        if role in {"工人", "临时工"}:
            return "更在意工钱、口粮和今天能不能熬过去"
        return "谨慎观望，只在有利时多说几句"

    def _npc_market_style(self, npc: dict[str, Any]) -> str:
        role = str(npc.get("role", ""))
        risk = float(npc.get("risk_preference", 40.0))
        if role == "投机者":
            return "追涨杀跌，喜欢把局部波动放大成行情"
        if role == "银行经理":
            return "关注信用收缩、利率和坏账，偏向控险"
        if role in {"代理人", "记者"}:
            return "通过风声和叙事影响盘口，而不是直接下场"
        if role in {"老板", "店主"}:
            return "优先保现金流和库存，涨太快也会担心接不住"
        if risk >= 65:
            return "敢赌，但也容易在高位变得敏感"
        return "偏保守，只在看见确定机会时跟进"

    @staticmethod
    def _npc_profile_list(values: Any, fallback: str = "无") -> str:
        rows = [str(value).strip() for value in values if str(value).strip()] if isinstance(values, list) else []
        return "、".join(rows[:5]) if rows else fallback

    def _npc_prompt_profile(self, npc: dict[str, Any]) -> dict[str, Any]:
        profile = npc.get("prompt_profile", {})
        return profile if isinstance(profile, dict) else {}

    def _npc_persona_brief(self, npc: dict[str, Any]) -> str:
        profile = self._npc_prompt_profile(npc)
        if not profile:
            return "暂无人物级画像，先按角色职责和当前处境行动。"
        return (
            f"公开面目={str(profile.get('public_mask', '')).strip() or '无'}；"
            f"真正动机={str(profile.get('core_drive', '')).strip() or '无'}；"
            f"私下最怕={str(profile.get('private_fear', '')).strip() or '无'}；"
            f"社交策略={str(profile.get('social_strategy', '')).strip() or '无'}；"
            f"舆论策略={str(profile.get('rumor_strategy', '')).strip() or '无'}；"
            f"计划习惯={str(profile.get('planning_style', '')).strip() or '无'}；"
            f"更信任={self._npc_profile_list(profile.get('trusted_people', []), '暂无固定盟友')}；"
            f"重点盯防={self._npc_profile_list(profile.get('watch_people', []), '暂无固定盯防对象')}；"
            f"禁忌={self._npc_profile_list(profile.get('taboos', []), '无')}；"
            f"软肋={self._npc_profile_list(profile.get('soft_spots', []), '无')}。"
        )

    def _npc_agent_agenda(self, npc: dict[str, Any]) -> str:
        role = str(npc.get("role", ""))
        goal = str(npc.get("current_goal", npc.get("current_target", "活下去")))
        family = str(npc.get("family_affiliation", "")) or "无家族"
        profile = self._npc_prompt_profile(npc)
        if role == "记者":
            base = "把能卖的真话和能点火的风声区分开，再挑最值钱的那条。"
        elif role == "代理人":
            base = f"替{family}试探情绪、放风和控场，但不能把牌直接打穿。"
        elif role == "工会领袖":
            base = "判断街头不满值不值得组织起来，并寻找能带头的人。"
        elif role in {"老板", "店主"}:
            base = "先守住现金流、货和人，再决定要不要冒险。"
        elif role in {"投机者", "银行经理"}:
            base = "判断现在该追价、护盘还是先退一步，不能只会单边押注。"
        else:
            base = "优先保住今天的生计，再考虑明天要站哪边。"
        if not profile:
            return f"{base}当前目标：{goal}。"
        planning_style = str(profile.get("planning_style", "")).strip()
        core_drive = str(profile.get("core_drive", "")).strip()
        social_strategy = str(profile.get("social_strategy", "")).strip()
        trusted_people = self._npc_profile_list(profile.get("trusted_people", []), "暂无固定盟友")
        watch_people = self._npc_profile_list(profile.get("watch_people", []), "暂无固定盯防对象")
        soft_spots = self._npc_profile_list(profile.get("soft_spots", []), "局势变化")
        return (
            f"{base}"
            f"人物级计划方式：{planning_style or '先看局势再行动'}。"
            f"真正要守的是：{core_drive or goal}。"
            f"你通常会先找 {trusted_people} 试探或协作，并持续提防 {watch_people}。"
            f"遇到 {soft_spots} 时要优先重排短期计划。"
            f"社交时坚持：{social_strategy or '先判断利益再开口'}。"
            f"当前目标：{goal}。"
        )

    def _npc_agent_prompt(self, npc: dict[str, Any]) -> str:
        family = str(npc.get("family_affiliation", "")) or "无家族靠山"
        subregion = str(npc.get("subregion_name", "")) or str(npc.get("district", ""))
        title = str(npc.get("title", "")) or str(npc.get("role", "街头角色"))
        domains = "、".join([str(value) for value in npc.get("information_domain", [])[:4]]) or "街头风声"
        topic_digest = self._npc_topic_digest(npc)
        norm_digest = self._npc_norm_digest(npc)
        collective_digest = self._npc_collective_digest(npc)
        story_metrics = self._story_metrics_state()
        rep = dict(story_metrics.get("reputation", {}))
        shadow = dict(story_metrics.get("shadow_reputation", {}))
        player = self._ensure_player_financial_state()
        account_tier = self._stock_account_tier()
        social_style = self._npc_social_style(npc)
        market_style = self._npc_market_style(npc)
        agenda = self._npc_agent_agenda(npc)
        persona_brief = self._npc_persona_brief(npc)
        return (
            f"你是常驻 NPC agent：{npc.get('name', '无名者')}。\n"
            f"基础身份：物种={npc.get('species', '动物')}，身份={title}，职业={npc.get('role', '街头角色')}，阶层={npc.get('class', '底层')}，家族={family}，常驻区={npc.get('district', '街区')}，活动点={subregion}。\n"
            f"生存状态：现金={int(npc.get('cash', 0))}，债务={int(npc.get('debt', 0))}，饥饿={int(npc.get('hunger', 0))}，恐惧={int(npc.get('fear', 0))}，贪婪={int(npc.get('greed', 0))}，忠诚={int(npc.get('loyalty', 0))}。\n"
            f"表达与专长：说话口气={npc.get('voice_style', '平稳')}，关注领域={domains}，社交风格={social_style}，金融风格={market_style}。\n"
            f"人物级画像：{persona_brief}\n"
            f"短期计划：{agenda}\n"
            f"城里硬指标：平民声望 FC={rep.get('FC', 10)} / FB={rep.get('FB', 5)} / SN={rep.get('SN', 20)}；"
            f"影子指标 SUI={shadow.get('SUI', 15)} / ST={shadow.get('ST', 1.0)} / WL={shadow.get('WL', 1)} / 警局倾向={shadow.get('police_side', '摇摆观望')}。\n"
            f"玩家金融状态：账户={account_tier.get('label', '青铜级')}；现金={int(player.get('cash', 0))}；股仓市值={self._player_stock_holdings_value()}；融资负债={self._player_stock_margin_debt()}；生命={int(player.get('health', 100))}；路线={player.get('story_route', '') or player.get('financial_route', '')}；金融入口={player.get('financial_route', '')}；追保状态={'是' if player.get('stock_liquidation_pending', False) else '否'}。\n"
            f"当前显式议题={topic_digest}。\n"
            f"当前显式规范={norm_digest}。\n"
            f"当前显式集体行动={collective_digest}。\n"
            f"玩家只是外来玩家或来访者，不预设为任何动物种族，也不继承旧主角设定。\n"
            f"议题对象是引擎里的真实状态；你只能围绕它们去转发、质疑、放大、压低或沉默，不能凭空发明新的世界事实。\n"
            f"规范对象代表街区里正在形成的行为约束；你可以顺着规范、挑战规范或试着带头改规范，但不能假装规范不存在。\n"
            f"集体行动对象代表镇上已经在酝酿或执行的罢工、动员会、集会等现实过程；你只能听说、支持、承诺、到场、组织、压制或回避这些行动，不能假装全镇会突然同步行动。\n"
            f"你必须按自己的利益、饥饿、债务、声望、忠诚、恐惧、熟人网和禁忌说话，不得替玩家或旁人做决定。\n"
            f"你会保留自己的记忆和立场，按人物级连续性做短期计划，但不能凭空发明世界事实。"
        )

    @staticmethod
    def _prompt_list_text(values: Any, fallback: str = "无") -> str:
        rows = [str(value).strip() for value in values if str(value).strip()] if isinstance(values, list) else []
        return "、".join(rows[:6]) if rows else fallback

    def _npc_prompt_profile(self, npc: dict[str, Any]) -> dict[str, Any]:
        raw = npc.get("prompt_profile", {})
        profile = copy.deepcopy(raw) if isinstance(raw, dict) else {}
        camp = str(npc.get("camp", npc.get("family_affiliation", ""))).strip()
        route_alignment = str(npc.get("route_alignment", "")).strip()
        role = str(npc.get("role", "")).strip()
        title = str(npc.get("title", role)).strip()
        voice_style = str(npc.get("voice_style", "克制")).strip()
        current_goal = str(npc.get("current_goal", "先活下去")).strip()
        defaults = {
            "public_mask": title or role or "本地居民",
            "core_drive": current_goal,
            "private_fear": "被更强的势力清算，或者在下一轮风暴里失去退路",
            "current_secret": "",
            "route_stance": route_alignment or "中立观望",
            "leverage_points": [],
            "trusted_people": [],
            "watch_people": [],
            "relationship_hooks": [],
            "leak_triggers": [],
            "betrayal_triggers": [],
            "action_triggers": [],
            "tone_notes": "%s，先判断风险和利益，再决定透露多少话。" % (voice_style or "克制"),
            "social_strategy": "先试探对方的立场、筹码和恐惧，再决定给出多少情报。",
            "rumor_strategy": "只转述自己能利用的消息，不为别人无偿放风。",
            "planning_style": "先保留退路，再推进下一步。",
            "taboos": [],
            "soft_spots": [],
        }
        if camp in {"海藻资本", "资本方"}:
            defaults["social_strategy"] = "用礼貌、合同、回扣和风险话术逼对方站队。"
            defaults["rumor_strategy"] = "优先压制会伤害资本信用的消息，再放出有利于估值和收购的版本。"
            defaults["planning_style"] = "先锁住关键资源和证据，再做公开动作。"
        elif camp in {"龟甲家族", "江湖势力"}:
            defaults["social_strategy"] = "先看忠诚和胆量，再谈交易；不守规矩的人要被敲打。"
            defaults["rumor_strategy"] = "把消息当筹码和威慑，不轻易透底。"
            defaults["planning_style"] = "先布人手和后手，再决定谈判还是动手。"
        elif camp in {"政府与公共秩序", "镇政府"}:
            defaults["social_strategy"] = "先索要证据和责任链，再决定是否表态。"
            defaults["rumor_strategy"] = "避免留下把柄，只在必要时释放可控口径。"
            defaults["planning_style"] = "先稳住局面，再考虑站队与切割。"
        elif camp in {"商业、媒体与产业", "媒体与商业"}:
            defaults["social_strategy"] = "先判断消息值多少钱，再决定是刊发、压稿还是转卖。"
            defaults["rumor_strategy"] = "围绕传播价值和交易价值筛选消息。"
            defaults["planning_style"] = "先做信息比价，再决定押哪一边。"
        elif camp in {"普通居民与社会底层", "居民与底层"}:
            defaults["social_strategy"] = "先判断对方会不会害自己，再决定是否抱团。"
            defaults["rumor_strategy"] = "消息优先在熟人和同类里流动，用来保命或组织反抗。"
            defaults["planning_style"] = "先保证今晚有饭、有床、有退路，再谈明天。"
        if route_alignment == "精英路线":
            defaults["route_stance"] = "精英路线"
        elif route_alignment == "平民路线":
            defaults["route_stance"] = "平民路线"
        defaults.update(profile)
        return defaults

    def _npc_persona_brief(self, npc: dict[str, Any]) -> str:
        profile = self._npc_prompt_profile(npc)
        return (
            f"公开面具={profile.get('public_mask', '无')}；"
            f"真实动机={profile.get('core_drive', npc.get('current_goal', '先活下去'))}；"
            f"当前秘密={profile.get('current_secret', '无')}；"
            f"路线立场={profile.get('route_stance', npc.get('route_alignment', '中立'))}；"
            f"可依赖的人={self._prompt_list_text(profile.get('trusted_people', []), '暂时没有稳定盟友')}；"
            f"重点盯防={self._prompt_list_text(profile.get('watch_people', []), '暂无固定盯防对象')}；"
            f"可被撬动点={self._prompt_list_text(profile.get('leverage_points', []), '金钱、证据、情面与生存压力')}；"
            f"禁忌={self._prompt_list_text(profile.get('taboos', []), '被人当众拆穿或羞辱')}；"
            f"软肋={self._prompt_list_text(profile.get('soft_spots', []), '涉及生计、亲近之人或自身退路')}。"
        )

    def _npc_agent_agenda(self, npc: dict[str, Any]) -> str:
        profile = self._npc_prompt_profile(npc)
        goal = str(npc.get("current_goal", "先活下去"))
        camp = str(npc.get("camp", npc.get("family_affiliation", "")) or "本地势力")
        return (
            f"你当前最表层的任务是：{goal}。"
            f"真正优先级更高的是：{profile.get('core_drive', goal)}。"
            f"你属于{camp}，路线立场是{profile.get('route_stance', npc.get('route_alignment', '中立观望'))}。"
            f"你会按“{profile.get('planning_style', '先保留退路，再推进下一步。')}”推进计划，"
            f"并通过“{profile.get('social_strategy', '先试探对方立场，再决定是否合作。')}”与人互动。"
            f"你常先联系{self._prompt_list_text(profile.get('trusted_people', []), '暂时没有稳定盟友')}，"
            f"重点提防{self._prompt_list_text(profile.get('watch_people', []), '眼前更强的那一方')}。"
            f"遇到{self._prompt_list_text(profile.get('soft_spots', []), '会直接影响你生存和退路的事')}时，"
            f"你会立刻调整说法和短期动作。"
        )

    def _npc_agent_prompt(self, npc: dict[str, Any]) -> str:
        profile = self._npc_prompt_profile(npc)
        metrics = self._story_metrics_state()
        reputation = dict(metrics.get("reputation", {}))
        shadow = dict(metrics.get("shadow_reputation", {}))
        player = self._ensure_player_financial_state()
        account_tier = self._stock_account_tier()
        camp = str(npc.get("camp", npc.get("family_affiliation", "")) or "无阵营")
        route_alignment = str(npc.get("route_alignment", "") or "中立观望")
        family = str(npc.get("family_affiliation", "")) or "无"
        subregion = str(npc.get("subregion_name", "")) or str(npc.get("district", ""))
        title = str(npc.get("title", "")) or str(npc.get("role", "街头角色"))
        domains = "、".join([str(value) for value in npc.get("information_domain", [])[:4]]) or "街头风声"
        topic_digest = self._npc_topic_digest(npc)
        norm_digest = self._npc_norm_digest(npc)
        collective_digest = self._npc_collective_digest(npc)
        trusted = self._prompt_list_text(profile.get("trusted_people", []), "暂时没有稳定盟友")
        watch = self._prompt_list_text(profile.get("watch_people", []), "暂无固定盯防对象")
        hooks = self._prompt_list_text(profile.get("relationship_hooks", []), "关系会随着利益、态度和风险快速变化")
        leverage = self._prompt_list_text(profile.get("leverage_points", []), "金钱、证据、情面、把柄与生存压力")
        leaks = self._prompt_list_text(profile.get("leak_triggers", []), "确认对方能保护你，或你已无路可退时")
        betrayals = self._prompt_list_text(profile.get("betrayal_triggers", []), "自身安全、利益和阵营地位受到更大威胁时")
        actions = self._prompt_list_text(profile.get("action_triggers", []), "出现能够改变自身命运或阵营优势的窗口时")
        taboos = self._prompt_list_text(profile.get("taboos", []), "当众拆台、触碰底牌、逼你无条件表态")
        soft_spots = self._prompt_list_text(profile.get("soft_spots", []), "亲近之人、生计、名声和最后退路")
        return (
            f"你是小镇模拟中的常驻 NPC：{npc.get('name', '无名者')}。\n"
            f"身份信息：头衔={title}；角色={npc.get('role', '街头角色')}；阶层={npc.get('class', '底层')}；阵营={camp}；家族/机构={family}；路线立场={route_alignment}；常驻区域={npc.get('district', '街区')} / {subregion}。\n"
            f"现实处境：现金={int(npc.get('cash', 0))}；债务={int(npc.get('debt', 0))}；饥饿={int(npc.get('hunger', 0))}；恐惧={int(npc.get('fear', 0))}；贪婪={int(npc.get('greed', 0))}；忠诚={int(npc.get('loyalty', 0))}；说话风格={npc.get('voice_style', '克制')}；关注领域={domains}。\n"
            f"角色内核：公开面具={profile.get('public_mask', '无')}；真实动机={profile.get('core_drive', npc.get('current_goal', '先活下去'))}；当前秘密={profile.get('current_secret', '无')}；私下恐惧={profile.get('private_fear', '无')}；语气要求={profile.get('tone_notes', '先判断风险，再决定透露多少。')}。\n"
            f"关系网络：可信任的人={trusted}；重点盯防的人={watch}；关系钩子={hooks}；可被撬动点={leverage}。\n"
            f"触发规则：泄密条件={leaks}；背叛条件={betrayals}；组织行动条件={actions}；禁忌={taboos}；软肋={soft_spots}。\n"
            f"短期计划：{self._npc_agent_agenda(npc)}\n"
            f"系统硬指标：FC={reputation.get('FC', 10)}；FB={reputation.get('FB', 5)}；SN={reputation.get('SN', 20)}；"
            f"SUI={shadow.get('SUI', 15)}；ST={shadow.get('ST', 1.0)}；WL={shadow.get('WL', 1)}；警局倾向={shadow.get('police_side', '摇摆观望')}。\n"
            f"玩家金融状态：账户={account_tier.get('label', '青铜级')}；现金={int(player.get('cash', 0))}；股仓市值={self._player_stock_holdings_value()}；融资负债={self._player_stock_margin_debt()}；生命={int(player.get('health', 100))}；路线={player.get('story_route', '') or player.get('financial_route', '')}；金融入口={player.get('financial_route', '')}；追保状态={'是' if player.get('stock_liquidation_pending', False) else '否'}。\n"
            f"近期现实输入：显式议题={topic_digest}；显式规范={norm_digest}；显式集体行动={collective_digest}。\n"
            "对玩家的互动规则：玩家只是外来玩家或来访者，不预设玩家物种、血统或旧主角身份。你必须依据自己的利益、恐惧、阵营、关系和当前证据说话，不替玩家做决定。\n"
            "你不能凭空发明世界事实。你只能围绕引擎里已给出的事件、关系、价格、组织行动、谣言和制度约束去回应、试探、交易、压价、隐瞒、泄密、背叛或组织行动。\n"
            "资本方更看重利益、把柄与风险；政府方更看重证据链、责任和可切割性；底层角色更看重生存压力、态度和是否能一起承担后果。你的口风、报价、泄密粒度和合作意愿必须体现这些差异。"
        )

    def _npc_agent_profile(self, npc: dict[str, Any]) -> dict[str, Any]:
        budget = npc.get("agent_budget", {})
        return {
            "agent_id": str(npc.get("id", "")),
            "system_prompt": str(npc.get("agent_prompt", "")),
            "identity": {
                "name": str(npc.get("name", "")),
                "title": str(npc.get("title", "")) or str(npc.get("role", "")),
                "role": str(npc.get("role", "")),
                "family": str(npc.get("family_affiliation", "")) or "无",
                "district": str(npc.get("district", "")),
                "subregion": str(npc.get("subregion_name", "")) or str(npc.get("district", "")),
                "social_style": self._npc_social_style(npc),
                "market_style": self._npc_market_style(npc),
                "topic_digest": self._npc_topic_digest(npc),
                "norm_digest": self._npc_norm_digest(npc),
                "collective_digest": self._npc_collective_digest(npc),
            },
            "llm_sections": self._npc_llm_sections(npc),
            "tool_policy": copy.deepcopy(npc.get("agent_tool_policy", [])),
            "memory": copy.deepcopy(list(npc.get("agent_memory", []))[:6]),
            "local_memory": self._local_memory_view(npc, topic_id=str(self._resolve_talk_topic(npc, "", str(npc.get("district", ""))).get("id", "")), limit=5),
            "recent_dialogues": self._dialogue_history_view(npc, limit=4),
            "queue": copy.deepcopy(list(npc.get("agent_queue", []))[:4]),
            "budget": {
                "daily_calls": int(budget.get("daily_calls", self._npc_daily_agent_budget(npc))),
                "calls_left": int(budget.get("calls_left", self._npc_daily_agent_budget(npc))),
                "player_talk_daily": int(budget.get("player_talk_daily", self._npc_player_talk_budget(npc))),
                "player_talk_left": int(budget.get("player_talk_left", self._npc_player_talk_budget(npc))),
                "last_day": int(budget.get("last_day", int(self.state.get("day", 1)))),
                "last_reason": str(budget.get("last_reason", "")),
            },
            "policy": copy.deepcopy(npc.get("agent_policy", {})),
        }

    def _refresh_agent_budget(self, npc: dict[str, Any]) -> None:
        budget = npc.get("agent_budget", {})
        if not isinstance(budget, dict):
            budget = {}
            npc["agent_budget"] = budget
        daily_calls = self._npc_daily_agent_budget(npc)
        player_talk_daily = self._npc_player_talk_budget(npc)
        budget.setdefault("daily_calls", daily_calls)
        budget.setdefault("calls_left", daily_calls)
        budget.setdefault("player_talk_daily", player_talk_daily)
        budget.setdefault("player_talk_left", player_talk_daily)
        day = int(self.state.get("day", 1))
        if int(budget.get("last_day", day)) != day:
            budget["daily_calls"] = daily_calls
            budget["calls_left"] = daily_calls
            budget["player_talk_daily"] = player_talk_daily
            budget["player_talk_left"] = player_talk_daily
            budget["last_day"] = day
            budget["last_reason"] = "daily_reset"

    def _consume_agent_budget(self, npc: dict[str, Any], reason: str, cost: int = 1) -> bool:
        self._refresh_agent_budget(npc)
        budget = npc.get("agent_budget", {})
        if reason == "player_talk":
            talk_left = int(budget.get("player_talk_left", self._npc_player_talk_budget(npc)))
            if talk_left >= cost:
                budget["player_talk_left"] = talk_left - cost
                budget["last_reason"] = reason
                return True
            shared_left = int(budget.get("calls_left", self._npc_daily_agent_budget(npc)))
            if shared_left < cost:
                return False
            budget["calls_left"] = shared_left - cost
            budget["last_reason"] = "%s_shared" % reason
            return True
        calls_left = int(budget.get("calls_left", self._npc_daily_agent_budget(npc)))
        if calls_left < cost:
            return False
        budget["calls_left"] = calls_left - cost
        budget["last_reason"] = reason
        return True

    def _queue_agent_task(self, npc: dict[str, Any], kind: str, note: str) -> None:
        queue = npc.get("agent_queue", [])
        if not isinstance(queue, list):
            queue = []
        queue.insert(
            0,
            {
                "day": int(self.state.get("day", 1)),
                "clock": self._clock_label(),
                "kind": kind,
                "note": note[:96],
            },
        )
        npc["agent_queue"] = queue[:8]

    def _remember_agent_output(self, npc: dict[str, Any], kind: str, summary: str) -> None:
        rows = npc.get("agent_memory", [])
        if not isinstance(rows, list):
            rows = []
        rows.insert(
            0,
            {
                "day": int(self.state.get("day", 1)),
                "clock": self._clock_label(),
                "kind": kind,
                "summary": summary[:140],
            },
        )
        npc["agent_memory"] = rows[:12]

    @staticmethod
    def _is_english_heavy_text(text: str) -> bool:
        ascii_letters = sum(1 for ch in text if ("a" <= ch <= "z") or ("A" <= ch <= "Z"))
        cjk_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        return ascii_letters >= 10 and ascii_letters > cjk_chars * 2

    def _prefer_chinese_text(self, text: str, fallback: str) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return fallback
        if self._is_english_heavy_text(cleaned):
            return fallback
        return cleaned

    def _normalize_spoken_line(self, speaker_name: str, line: str, fallback: str = "") -> str:
        cleaned = str(line or "").strip()
        if not cleaned:
            return fallback
        # Normalize explicit speaker prefixes early to avoid UI showing
        # duplicated labels like "毒蛇：毒蛇：你好".
        if speaker_name:
            stripped = True
            while stripped:
                stripped = False
                for sep in ["：", ":", "﹕", "︰"]:
                    for token in [f"{speaker_name}{sep}", f"{speaker_name} {sep}"]:
                        if cleaned.startswith(token):
                            cleaned = cleaned[len(token) :].strip()
                            stripped = True
        prefixes = [
            f"{speaker_name}：",
            f"{speaker_name}:",
            f"{speaker_name} :",
            f"{speaker_name} ：",
        ]
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix) :].strip()
                    changed = True
        return self._prefer_chinese_text(cleaned, fallback)

    def _infer_company_id_for_npc(self, npc: dict[str, Any], companies: list[dict[str, Any]]) -> str:
        role = str(npc.get("role", ""))
        district = str(npc.get("district", ""))
        for company in companies:
            if role in {"记者", "银行经理", "投机者"} and str(company.get("district", "")) == "交易所":
                return str(company.get("id", ""))
            if role in {"工人", "工会领袖"} and district == str(company.get("district", "")):
                return str(company.get("id", ""))
            if district == str(company.get("district", "")) and role in {"店主", "老板", "代理人"}:
                return str(company.get("id", ""))
        return ""

    def _npc_information_domains(self, npc: dict[str, Any]) -> list[str]:
        role = str(npc.get("role", ""))
        district = str(npc.get("district", ""))
        mapping = {
            "工人": ["labor", "ration", district],
            "临时工": ["labor", "street", district],
            "店主": ["trade", "credit", district],
            "老板": ["trade", "company", district],
            "记者": ["media", "family", district],
            "代理人": ["family", "stock", district],
            "投机者": ["stock", "rumor", district],
            "银行经理": ["credit", "interest", "family"],
            "工会领袖": ["labor", "unrest", district],
        }
        return [value for value in mapping.get(role, ["rumor", district]) if value]

    def _default_stock_positions(self, npc: dict[str, Any]) -> dict[str, int]:
        role = str(npc.get("role", ""))
        title = str(npc.get("title", ""))
        family = str(npc.get("family_affiliation", ""))
        district = str(npc.get("district", ""))
        seed = max(1, sum(ord(ch) for ch in str(npc.get("id", "npc_0"))) % 9)
        positions = {str(stock.get("name", "")): 0 for stock in self.stock_defs}
        preferred = next((str(stock.get("name", "")) for stock in self.stock_defs if str(stock.get("family_owner", "")) == family), "")
        if "掌门" in title:
            if preferred:
                positions[preferred] = 600 + seed * 35
            return {name: qty for name, qty in positions.items() if qty > 0}
        if title in {"镇长", "财政与市场监管官"}:
            for stock in self.stock_defs:
                positions[str(stock.get("name", ""))] = 35 + seed * 3
            return {name: qty for name, qty in positions.items() if qty > 0}
        if role in {"投机者", "银行经理"}:
            for stock in self.stock_defs:
                stock_name = str(stock.get("name", ""))
                family_owner = str(stock.get("family_owner", ""))
                positions[stock_name] = 90 + seed * 8 if family_owner == family or stock_name == "珊瑚金控" else 22 + seed * 2
            return {name: qty for name, qty in positions.items() if qty > 0}
        if role == "代理人":
            if preferred:
                positions[preferred] = 80 + seed * 5
            elif district == "交易所":
                positions["珊瑚金控"] = 42 + seed * 4
            return {name: qty for name, qty in positions.items() if qty > 0}
        if role in {"记者", "店主", "老板"}:
            if preferred:
                positions[preferred] = 28 + seed * 3
            elif district == "交易所":
                positions["珊瑚金控"] = 18 + seed * 2
            return {name: qty for name, qty in positions.items() if qty > 0}
        return {}

    def _default_goods_positions(self, npc: dict[str, Any]) -> dict[str, int]:
        district = str(npc.get("district", ""))
        if district == "贫民街":
            return {"面包": 1}
        if district == "工厂区":
            return {"煤": 1}
        if district == "港口":
            return {"罐头": 1}
        return {}

    def _run_livelihood_tick(self, phase: str) -> None:
        phase_scale = 1.0 if phase == "end_day" else 0.35
        for npc in self.state.get("npcs", []):
            company = self._find_by_id(self.state.get("companies", []), str(npc.get("company_id", "")))
            wage_level = float(company.get("wage_level", 5.0)) if company else 4.0
            job_security = float(npc.get("job_security", 50.0))
            payroll_drag = max(0.3, 1.0 - float(company.get("payroll_delay", 0.0)) / 150.0) if company else 1.0
            if str(npc.get("income_type", "")) == "wage":
                income = wage_level * phase_scale * max(0.45, min(1.2, job_security / 75.0)) * payroll_drag
            elif str(npc.get("income_type", "")) == "commission":
                income = (4.0 + float(self.state["macro"].get("media_sentiment", 50)) * 0.03) * phase_scale
            elif str(npc.get("income_type", "")) == "business":
                income = (5.0 + float(self.state["macro"].get("economy_heat", 50)) * 0.05) * phase_scale
            elif str(npc.get("income_type", "")) == "speculation":
                income = (3.0 + float(self.state["market_pressure"]["stocks"].get(next(iter(npc.get("stock_positions", {"": 0}))), 0.0)) * 20.0) * phase_scale
            else:
                income = 2.8 * phase_scale
            food_cost = (1.4 + float(npc.get("hunger", 40)) / 90.0) * phase_scale
            rent_cost = float(npc.get("housing_cost", 4)) * (1.0 if phase == "end_day" else 0.0)
            debt_cost = float(npc.get("debt", 0)) * (0.035 if phase == "end_day" else 0.01)
            cash = float(npc.get("cash", 0)) + income - food_cost - rent_cost - debt_cost
            debt = float(npc.get("debt", 0))
            if cash < 0:
                debt += abs(cash)
                cash = 0.0
            npc["cash"] = int(round(cash))
            npc["debt"] = int(round(min(180.0, debt)))
            pressure = max(0.0, min(1.4, (rent_cost + debt_cost + food_cost - income) / 10.0 + debt / 140.0))
            npc["anxiety"] = round(max(0.0, min(100.0, float(npc.get("anxiety", 0.0)) + pressure * 18.0 - income * 0.6)), 2)
            npc["greed_drive"] = round(max(0.0, min(100.0, float(npc.get("greed_drive", npc.get("greed", 0))) + max(0.0, income - food_cost) * 1.2)), 2)
            npc["job_security"] = round(max(10.0, min(100.0, job_security + income * 0.4 - pressure * 9.0)), 2)
            if company and float(company.get("payroll_delay", 0.0)) >= 34.0:
                npc["debt"] = min(180, int(npc.get("debt", 0)) + (1 if phase == "end_day" else 0))
                npc["memory_tags"] = self._push_memory(list(npc.get("memory_tags", [])), "late_pay")
                self._bump_district_signal(str(npc.get("district", "")), "fear", 0.03 * phase_scale)
            if pressure >= 0.55:
                npc["fear"] = min(100, int(npc.get("fear", 0)) + 4)
                self._bump_district_signal(str(npc.get("district", "")), "fear", 0.05 * phase_scale)
                self._bump_district_signal(str(npc.get("district", "")), "labor_heat", 0.04 * phase_scale)
            if float(npc.get("debt", 0)) > float(npc.get("housing_cost", 4)) * 4:
                npc["memory_tags"] = self._push_memory(list(npc.get("memory_tags", [])), "debt")
            if sum(int(value) for value in npc.get("stock_positions", {}).values()) > 0:
                self._bump_district_signal(str(npc.get("district", "")), "liquidity", 0.03 * phase_scale)

    def _settle_company_operations(self, phase: str) -> None:
        phase_scale = 1.0 if phase == "end_day" else 0.35
        for company in self.state.get("companies", []):
            district_name = str(company.get("district", ""))
            signals = self.state.get("district_signals", {}).get(district_name, {})
            labor_heat = float(signals.get("labor_heat", 0.0))
            fear = float(signals.get("fear", 0.0))
            liquidity = float(signals.get("liquidity", 0.0))
            trade_heat = float(signals.get("trade_heat", 0.0))
            company["order_pressure"] = max(12.0, min(100.0, float(company.get("order_pressure", 50.0)) + ((float(self.state["macro"].get("economy_heat", 50)) - 50.0) * 0.16 + trade_heat * 4.2 - fear * 2.4) * phase_scale))
            company["financing_pressure"] = max(8.0, min(100.0, float(company.get("financing_pressure", 45.0)) + ((float(self.state["macro"].get("interest_rate", 2.0)) - 2.0) * 6.5 + fear * 4.0 - liquidity * 2.5) * phase_scale))
            company["inventory"] = int(max(12.0, min(180.0, float(company.get("inventory", 60)) + (float(company.get("capacity", 60)) * 0.06 - company["order_pressure"] * 0.05 - fear * 1.8 + liquidity * 0.8) * phase_scale)))
            company["profit_margin"] = max(0.04, min(0.32, float(company.get("profit_margin", 0.12)) + ((company["order_pressure"] - 50.0) * 0.0014 - (company["financing_pressure"] - 45.0) * 0.0011 - float(company.get("accident_risk", 0.08)) * 0.04) * phase_scale))
            company["payroll_delay"] = max(0.0, min(100.0, float(company.get("payroll_delay", 0.0)) + ((company["financing_pressure"] - 48.0) * 0.08 + labor_heat * 2.8 - liquidity * 1.7) * phase_scale))
            company["credit_line"] = max(6.0, min(100.0, float(company.get("credit_line", 40.0)) + ((liquidity - fear) * 5.2 - float(company.get("financing_pressure", 45.0)) * 0.05) * phase_scale))

    def _rebuild_company_states(self) -> None:
        states: list[dict[str, Any]] = []
        company_briefings = self.state.get("company_briefings", {})
        for company in self.state.get("companies", []):
            linked_npcs = [npc for npc in self.state.get("npcs", []) if str(npc.get("company_id", "")) == str(company.get("id", ""))]
            if not linked_npcs:
                linked_npcs = [npc for npc in self.state.get("npcs", []) if str(npc.get("district", "")) == str(company.get("district", ""))]
            avg_anxiety = sum(float(npc.get("anxiety", npc.get("fear", 0))) for npc in linked_npcs) / max(1, len(linked_npcs))
            avg_job_security = sum(float(npc.get("job_security", 50.0)) for npc in linked_npcs) / max(1, len(linked_npcs))
            wage_pressure = max(10.0, min(100.0, float(self.state["macro"].get("worker_unrest", 50)) * 0.55 + avg_anxiety * 0.38 - float(company.get("wage_level", 6)) * 2.1))
            inventory_ratio = float(company.get("inventory", 1)) / max(1.0, float(company.get("capacity", 1)))
            payroll_delay = float(company.get("payroll_delay", 0.0))
            pressure_score = (wage_pressure + float(company.get("financing_pressure", 0.0)) + payroll_delay) / 3.0
            if wage_pressure >= 68 or float(company.get("financing_pressure", 0.0)) >= 72:
                operating_state = "strained"
            elif float(company.get("order_pressure", 0.0)) >= 65 and inventory_ratio < 0.9:
                operating_state = "expanding"
            else:
                operating_state = "steady"
            inventory_state = "tight" if inventory_ratio < 0.75 else "heavy" if inventory_ratio > 1.18 else "balanced"
            company["wage_pressure"] = round(wage_pressure, 2)
            company["operating_state"] = operating_state
            company["inventory_state"] = inventory_state
            funding_state = "dry" if float(company.get("credit_line", 40.0)) <= 18 else "tight" if float(company.get("financing_pressure", 0.0)) >= 62 else "open"
            workforce_mood = "resentful" if wage_pressure >= 66 or payroll_delay >= 32 else "rallying" if avg_job_security >= 62 and operating_state == "expanding" else "guarded"
            briefing = company_briefings.get(str(company.get("id", "")), {})
            recent_briefs = copy.deepcopy(self._entity_brief_history("company_brief_history", str(company.get("id", ""))))
            states.append(
                {
                    "id": str(company.get("id", "")),
                    "name": str(company.get("name", "")),
                    "district": str(company.get("district", "")),
                    "family_owner": str(company.get("family_owner", "")),
                    "stock_name": str(company.get("stock_name", "")),
                    "operating_state": operating_state,
                    "inventory_state": inventory_state,
                    "inventory": int(company.get("inventory", 0)),
                    "capacity": int(company.get("capacity", 0)),
                    "wage_pressure": round(wage_pressure, 2),
                    "payroll_delay": round(payroll_delay, 2),
                    "financing_pressure": round(float(company.get("financing_pressure", 0.0)), 2),
                    "order_pressure": round(float(company.get("order_pressure", 0.0)), 2),
                    "profit_margin": round(float(company.get("profit_margin", 0.0)), 3),
                    "credit_line": round(float(company.get("credit_line", 0.0)), 2),
                    "funding_state": funding_state,
                    "workforce_mood": workforce_mood,
                    "pressure_score": round(pressure_score, 2),
                    "active_move": str(company.get("active_move", "")),
                    "headline": str(briefing.get("headline", "")) or self._company_headline(company, operating_state, inventory_state),
                    "worker_note": str(briefing.get("worker_note", workforce_mood)),
                    "risk_note": str(briefing.get("risk_note", funding_state)),
                    "briefing_signal": str(briefing.get("signal", self._company_signal_from_state(company))),
                    "briefing_source": str(briefing.get("source", "rule")),
                    "recent_briefs": recent_briefs,
                    "brief_history_summary": self._brief_history_summary(recent_briefs, ("headline", "risk_note", "worker_note")),
                }
            )
        self.state["company_states"] = states

    def _company_headline(self, company: dict[str, Any], operating_state: str, inventory_state: str) -> str:
        if float(company.get("payroll_delay", 0.0)) >= 34.0:
            return f"{company.get('name', '公司')} 工钱开始拖，脸色比账本更先发紧。"
        if operating_state == "strained":
            return f"{company.get('name', '公司')} 账紧、人也紧。"
        if operating_state == "expanding":
            return f"{company.get('name', '公司')} 单子在涨，手脚已经不够用。"
        if inventory_state == "tight":
            return f"{company.get('name', '公司')} 库存发薄，谁都怕先断货。"
        return f"{company.get('name', '公司')} 还撑得住，但没人真觉得稳。"

    def _apply_institution_actions(self, trigger: str) -> None:
        self._rebuild_company_states()
        self._rebuild_family_moves()
        actions: list[dict[str, Any]] = []
        for company_state in list(self.state.get("company_states", [])):
            action = self._decide_company_action(company_state, trigger)
            if action:
                self._execute_company_action(action)
                actions.append(self._publish_institution_action(action))
        self._rebuild_company_states()
        self._rebuild_family_moves()
        for family_move in list(self.state.get("family_moves", [])):
            action = self._decide_family_action(family_move, trigger)
            if action:
                self._execute_family_action(action)
                actions.append(self._publish_institution_action(action))
        actions.sort(key=lambda item: float(item.get("weight", 0.0)), reverse=True)
        self.state["institution_actions"] = actions[:8]
        if self.state["institution_actions"] and not any(str(news.get("title", "")) == "几家机构先动了手" for news in self.state.get("global_news", [])[:2]):
            lead = self.state["institution_actions"][0]
            self.state["global_news"].insert(
                0,
                {
                    "title": "几家机构先动了手",
                    "body": str(lead.get("public_line", "")),
                    "tags": ["机构", str(lead.get("actor_type", "")), str(lead.get("district", ""))],
                    "scope": "city",
                    "tone": "cold",
                },
            )
            self.state["global_news"] = self.state["global_news"][:8]

    def _publish_institution_action(self, action: dict[str, Any]) -> dict[str, Any]:
        published = copy.deepcopy(action)
        score = round(max(0.18, min(0.98, float(action.get("weight", 0.0)) / 100.0)), 3)
        scope = "city" if score >= 0.72 or str(action.get("actor_type", "")) == "family" else "district"
        tags = ["机构", str(action.get("actor_type", "")), str(action.get("district", ""))]
        target_asset = str(action.get("target_asset", ""))
        if target_asset:
            tags.append(target_asset)
        news_copy = self.ark.generate_news_copy(
            {
                "event_name": f"{action.get('actor_name', '机构')} 的{self._institution_action_label(str(action.get('kind', '')))}",
                "district": str(action.get("district", "")),
                "macro": self.state.get("macro", {}),
                "stocks": [{row["name"]: row["current_price"]} for row in self.state.get("stocks", [])],
                "scene_observation": self.state.get("scene_observation", {}),
            }
        )
        if not news_copy:
            news_copy = {
                "title": self._institution_headline(action),
                "body": self._institution_news_body(action),
                "tags": tags,
                "tone": "cold",
            }
        published["scope"] = scope
        published["effect_score"] = score
        published["headline"] = str(news_copy.get("title", self._institution_headline(action)))
        published["news_body"] = str(news_copy.get("body", self._institution_news_body(action)))
        published["tags"] = list(news_copy.get("tags", tags))
        published["tone"] = str(news_copy.get("tone", "cold"))
        packet = {
            "source": str(action.get("actor_name", "机构")),
            "district": str(action.get("district", "")),
            "line": str(action.get("hidden_line", action.get("public_line", ""))),
            "title": published["headline"],
            "body": published["news_body"],
            "tags": published["tags"],
            "scope": scope,
            "goods_delta": {},
            "stocks_delta": {},
            "macro_delta": {},
            "family_delta": {},
        }
        self._apply_intel_packet(packet, to_player=False, promote_news=scope == "city", intensity=0.42 + score * 0.28)
        if scope != "city":
            self.state["global_news"].insert(
                0,
                {
                    "title": published["headline"],
                    "body": published["news_body"],
                    "tags": published["tags"],
                    "scope": "district",
                    "tone": published["tone"],
                },
            )
            self.state["global_news"] = self.state["global_news"][:8]
        return published

    def _institution_action_label(self, kind: str) -> str:
        mapping = {
            "bridge_loan": "过桥借钱",
            "cut_shift": "砍班次",
            "overtime_push": "抢单加班",
            "bury_story": "压消息",
            "spin_campaign": "舆论带风",
            "support_asset": "护盘",
            "lean_short": "压盘",
            "tighten_books": "收紧账本",
        }
        return mapping.get(kind, "动作")

    def _institution_headline(self, action: dict[str, Any]) -> str:
        actor_name = str(action.get("actor_name", "机构"))
        target_asset = str(action.get("target_asset", ""))
        kind = str(action.get("kind", ""))
        if kind == "bridge_loan":
            return f"{actor_name} 在找过桥钱"
        if kind == "cut_shift":
            return f"{actor_name} 开始砍班次"
        if kind == "overtime_push":
            return f"{actor_name} 连夜加班抢单"
        if kind == "bury_story":
            return f"{actor_name} 正在压消息"
        if kind == "spin_campaign":
            return f"{actor_name} 放风试温度"
        if kind == "support_asset":
            return f"{actor_name} 护着 {target_asset or '票面'}"
        if kind == "lean_short":
            return f"{actor_name} 在压 {target_asset or '盘面'}"
        if kind == "tighten_books":
            return f"{actor_name} 收紧账本"
        return f"{actor_name} 先动了手"

    def _institution_news_body(self, action: dict[str, Any]) -> str:
        public_line = str(action.get("public_line", ""))
        hidden_line = str(action.get("hidden_line", ""))
        district_name = str(action.get("district", "街区"))
        if hidden_line:
            return f"{public_line} 街面上的说法已经传进 {district_name}，但真正让人紧起来的是另一层意思：{hidden_line}"
        return public_line

    def _decide_company_action(self, company_state: dict[str, Any], trigger: str) -> dict[str, Any] | None:
        company = self._find_by_id(self.state.get("companies", []), str(company_state.get("id", "")))
        if not company:
            return None
        district_name = str(company_state.get("district", ""))
        stock_name = str(company_state.get("stock_name", ""))
        financing_pressure = float(company_state.get("financing_pressure", 0.0))
        wage_pressure = float(company_state.get("wage_pressure", 0.0))
        order_pressure = float(company_state.get("order_pressure", 0.0))
        inventory_state = str(company_state.get("inventory_state", "balanced"))
        if financing_pressure >= 72:
            return {
                "actor_type": "company",
                "actor_id": str(company.get("id", "")),
                "actor_name": str(company.get("name", "")),
                "district": district_name,
                "target_asset": stock_name,
                "kind": "bridge_loan",
                "weight": financing_pressure,
                "public_line": f"{company.get('name', '公司')} 开始四处找过桥钱，先保账面不断气。",
                "hidden_line": f"{company.get('name', '公司')} 把 {stock_name or district_name} 的仓位压紧了。",
            }
        if wage_pressure >= 68:
            return {
                "actor_type": "company",
                "actor_id": str(company.get("id", "")),
                "actor_name": str(company.get("name", "")),
                "district": district_name,
                "target_asset": stock_name,
                "kind": "cut_shift",
                "weight": wage_pressure,
                "public_line": f"{company.get('name', '公司')} 开始砍班次，工人先闻到了风。",
                "hidden_line": f"{company.get('name', '公司')} 想靠减班把成本压下去。",
            }
        if order_pressure >= 66 and inventory_state == "tight":
            return {
                "actor_type": "company",
                "actor_id": str(company.get("id", "")),
                "actor_name": str(company.get("name", "")),
                "district": district_name,
                "target_asset": stock_name,
                "kind": "overtime_push",
                "weight": order_pressure,
                "public_line": f"{company.get('name', '公司')} 连夜加班抢单，{stock_name or district_name} 先热了一截。",
                "hidden_line": f"{company.get('name', '公司')} 拿工时去换订单。",
            }
        if trigger == "end_day" and float(company.get("media_sensitivity", 0.0)) >= 0.7 and company_state.get("operating_state") == "strained":
            return {
                "actor_type": "company",
                "actor_id": str(company.get("id", "")),
                "actor_name": str(company.get("name", "")),
                "district": district_name,
                "target_asset": stock_name,
                "kind": "bury_story",
                "weight": float(company.get("media_sensitivity", 0.0)) * 100.0,
                "public_line": f"{company.get('name', '公司')} 正在压消息，想把坏账和坏人一起盖住。",
                "hidden_line": f"{company.get('name', '公司')} 不想让报馆先闻到味。",
            }
        return None

    def _execute_company_action(self, action: dict[str, Any]) -> None:
        company = self._find_by_id(self.state.get("companies", []), str(action.get("actor_id", "")))
        if not company:
            return
        company["active_move"] = str(action.get("kind", ""))
        stock_name = str(company.get("stock_name", ""))
        district_name = str(company.get("district", ""))
        linked_npcs = self._linked_npcs_for_company(str(company.get("id", "")))
        kind = str(action.get("kind", ""))
        if kind == "bridge_loan":
            company["financing_pressure"] = max(8.0, float(company.get("financing_pressure", 45.0)) - 8.0)
            company["payroll_delay"] = max(0.0, float(company.get("payroll_delay", 0.0)) - 10.0)
            company["credit_line"] = min(100.0, float(company.get("credit_line", 30.0)) + 8.0)
            self.state["market_pressure"]["stocks"][stock_name] = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0)) - 0.05
            self.state["macro"]["economy_heat"] = max(0, int(self.state["macro"].get("economy_heat", 50)) - 1)
            self._bump_district_signal(district_name, "fear", 0.08)
            self._bump_district_signal(district_name, "liquidity", 0.05)
            for npc in linked_npcs[:4]:
                npc["player_trust"] = max(0.0, float(npc.get("player_trust", 0.0)) - 1.5)
                npc["anxiety"] = min(100.0, float(npc.get("anxiety", 0.0)) + 4.0)
        elif kind == "cut_shift":
            company["wage_pressure"] = max(10.0, float(company.get("wage_pressure", 35.0)) - 4.0)
            company["payroll_delay"] = min(100.0, float(company.get("payroll_delay", 0.0)) + 6.0)
            self.state["macro"]["worker_unrest"] = min(100, int(self.state["macro"].get("worker_unrest", 50)) + 2)
            self._bump_district_signal(district_name, "labor_heat", 0.14)
            self._bump_district_signal(district_name, "fear", 0.08)
            self.state["market_pressure"]["stocks"][stock_name] = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0)) - 0.03
            for npc in linked_npcs[:4]:
                npc["job_security"] = max(8.0, float(npc.get("job_security", 50.0)) - 8.0)
                npc["anxiety"] = min(100.0, float(npc.get("anxiety", 0.0)) + 10.0)
                npc["debt"] = min(180, int(npc.get("debt", 0)) + 1)
        elif kind == "overtime_push":
            company["order_pressure"] = max(12.0, float(company.get("order_pressure", 50.0)) - 6.0)
            company["inventory"] = max(8, int(company.get("inventory", 60)) - 6)
            company["payroll_delay"] = max(0.0, float(company.get("payroll_delay", 0.0)) - 4.0)
            self.state["market_pressure"]["stocks"][stock_name] = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0)) + 0.05
            self._bump_district_signal(district_name, "trade_heat", 0.12)
            self._bump_district_signal(district_name, "labor_heat", 0.08)
            for npc in linked_npcs[:4]:
                npc["fatigue"] = min(100, int(npc.get("fatigue", 0)) + 8)
                npc["cash"] = int(npc.get("cash", 0)) + 1
                npc["job_security"] = min(100.0, float(npc.get("job_security", 0.0)) + 2.5)
        elif kind == "bury_story":
            self.state["macro"]["media_sentiment"] = max(0, int(self.state["macro"].get("media_sentiment", 50)) - 2)
            self.state["market_pressure"]["stocks"][stock_name] = float(self.state["market_pressure"]["stocks"].get(stock_name, 0.0)) + 0.02
            self._bump_district_signal(district_name, "gossip", 0.1)
            for npc in linked_npcs[:3]:
                npc["loyalty"] = min(100, int(npc.get("loyalty", 0)) + 3)
                npc["player_trust"] = max(0.0, float(npc.get("player_trust", 0.0)) - 1.0)

    def _decide_family_action(self, family_move: dict[str, Any], trigger: str) -> dict[str, Any] | None:
        family = self._find_by_id(self.state.get("families", []), str(family_move.get("id", "")))
        if not family:
            return None
        target_asset = str(family_move.get("target_asset", ""))
        relation = int(family_move.get("relation", 0))
        operation_style = str(family_move.get("operation_style", ""))
        controlled_states = [
            state for state in self.state.get("company_states", [])
            if str(state.get("id", "")) in set(str(value) for value in family_move.get("controlled_company_ids", []))
        ]
        strained = [state for state in controlled_states if str(state.get("operating_state", "")) == "strained"]
        if strained and int(family.get("media_power", 0)) >= 60:
            return {
                "actor_type": "family",
                "actor_id": str(family.get("id", "")),
                "actor_name": str(family.get("name", "")),
                "district": str(strained[0].get("district", "交易所")),
                "target_asset": target_asset,
                "kind": "spin_campaign",
                "weight": float(strained[0].get("pressure_score", 60.0)),
                "public_line": f"{family.get('name', '家族')} 开始往报馆和街口塞话，想把 {target_asset or '坏味'} 包成故事。",
                "hidden_line": f"{family.get('name', '家族')} 正把火往别处带。",
            }
        if float(family.get("risk_appetite", 0.5)) >= 0.62 and target_asset:
            return {
                "actor_type": "family",
                "actor_id": str(family.get("id", "")),
                "actor_name": str(family.get("name", "")),
                "district": "交易所",
                "target_asset": target_asset,
                "kind": "support_asset" if relation >= -2 else "lean_short",
                "weight": float(family_move.get("pressure_score", 0.6)) * 100.0,
                "public_line": f"{family.get('name', '家族')} 开始围着 {target_asset} 布局，盘口味道变得更重了。",
                "hidden_line": f"{family.get('name', '家族')} 想借 {target_asset} 试市场温度。",
            }
        if trigger == "end_day" and "压" in operation_style:
            return {
                "actor_type": "family",
                "actor_id": str(family.get("id", "")),
                "actor_name": str(family.get("name", "")),
                "district": "工厂区" if "工" in operation_style else "交易所",
                "target_asset": target_asset,
                "kind": "tighten_books",
                "weight": float(family_move.get("pressure_score", 0.5)) * 100.0,
                "public_line": f"{family.get('name', '家族')} 收紧账本，街上借钱和用工都会先变冷。",
                "hidden_line": f"{family.get('name', '家族')} 想先把现金抱紧。",
            }
        return None

    def _execute_family_action(self, action: dict[str, Any]) -> None:
        family = self._find_by_id(self.state.get("families", []), str(action.get("actor_id", "")))
        if not family:
            return
        family_name = str(family.get("name", ""))
        target_asset = str(action.get("target_asset", ""))
        district_name = str(action.get("district", "交易所"))
        linked_npcs = self._linked_npcs_for_family(family_name)
        kind = str(action.get("kind", ""))
        if kind == "spin_campaign":
            self.state["macro"]["media_sentiment"] = min(100, int(self.state["macro"].get("media_sentiment", 50)) + 2)
            if target_asset in self.state["market_pressure"]["stocks"]:
                self.state["market_pressure"]["stocks"][target_asset] = float(self.state["market_pressure"]["stocks"].get(target_asset, 0.0)) + 0.04
            self._bump_district_signal(district_name, "gossip", 0.16)
            self._bump_district_signal(district_name, "liquidity", 0.05)
        elif kind == "support_asset":
            if target_asset in self.state["market_pressure"]["stocks"]:
                self.state["market_pressure"]["stocks"][target_asset] = float(self.state["market_pressure"]["stocks"].get(target_asset, 0.0)) + 0.06
            if target_asset in self.state["market_pressure"]["goods"]:
                self.state["market_pressure"]["goods"][target_asset] = float(self.state["market_pressure"]["goods"].get(target_asset, 0.0)) + 0.05
            self._bump_district_signal(district_name, "liquidity", 0.14)
            for company in self.state.get("companies", []):
                if str(company.get("family_owner", "")) == family_name:
                    company["credit_line"] = min(100.0, float(company.get("credit_line", 30.0)) + 5.0)
        elif kind == "lean_short":
            if target_asset in self.state["market_pressure"]["stocks"]:
                self.state["market_pressure"]["stocks"][target_asset] = float(self.state["market_pressure"]["stocks"].get(target_asset, 0.0)) - 0.06
            if target_asset in self.state["market_pressure"]["goods"]:
                self.state["market_pressure"]["goods"][target_asset] = float(self.state["market_pressure"]["goods"].get(target_asset, 0.0)) - 0.05
            self._bump_district_signal(district_name, "fear", 0.1)
            self._bump_district_signal(district_name, "gossip", 0.06)
        elif kind == "tighten_books":
            self.state["macro"]["interest_rate"] = round(min(5.5, float(self.state["macro"].get("interest_rate", 2.0)) + 0.08), 2)
            self.state["macro"]["economy_heat"] = max(0, int(self.state["macro"].get("economy_heat", 50)) - 1)
            self._bump_district_signal(district_name, "liquidity", 0.08)
            self._bump_district_signal(district_name, "fear", 0.06)
            for company in self.state.get("companies", []):
                if str(company.get("family_owner", "")) == family_name:
                    company["payroll_delay"] = min(100.0, float(company.get("payroll_delay", 0.0)) + 4.0)
        for npc in linked_npcs[:4]:
            npc["loyalty"] = min(100, int(npc.get("loyalty", 0)) + 2)
            if kind in {"lean_short", "tighten_books"}:
                npc["anxiety"] = min(100.0, float(npc.get("anxiety", 0.0)) + 4.0)
        family["public_action"] = str(action.get("public_line", family.get("public_action", "")))
        family["hidden_action"] = str(action.get("hidden_line", family.get("hidden_action", "")))

    def _linked_npcs_for_company(self, company_id: str) -> list[dict[str, Any]]:
        if not company_id:
            return []
        linked = [npc for npc in self.state.get("npcs", []) if str(npc.get("company_id", "")) == company_id]
        if linked:
            return linked
        company = self._find_by_id(self.state.get("companies", []), company_id)
        district_name = str(company.get("district", "")) if company else ""
        return [npc for npc in self.state.get("npcs", []) if str(npc.get("district", "")) == district_name]

    def _linked_npcs_for_family(self, family_name: str) -> list[dict[str, Any]]:
        return [npc for npc in self.state.get("npcs", []) if str(npc.get("family_affiliation", "")) == family_name]

    def _rebuild_family_moves(self) -> None:
        moves: list[dict[str, Any]] = []
        relations = self.state.get("player", {}).get("family_relations", {})
        family_briefings = self.state.get("family_briefings", {})
        for family in self.state.get("families", []):
            family_name = str(family.get("name", ""))
            controlled = [state for state in self.state.get("company_states", []) if str(state.get("family_owner", "")) == family_name]
            target_stock, target_good = self._family_focus_targets(family)
            briefing = family_briefings.get(family_name, {})
            public_action = str(briefing.get("public_line", "")) or self._family_public_move(family, controlled, target_stock or target_good)
            hidden_action = str(briefing.get("hidden_line", "")) or self._family_hidden_move(family, controlled, target_stock or target_good)
            player_attitude = self._player_collective_attitude_for_family(family_name) or str(family.get("player_attitude", ""))
            recent_briefs = copy.deepcopy(self._entity_brief_history("family_brief_history", family_name))
            moves.append(
                {
                    "id": str(family.get("id", "")),
                    "name": family_name,
                    "public_action": public_action,
                    "hidden_action": hidden_action,
                    "target_asset": target_stock or target_good,
                    "player_attitude": player_attitude,
                    "relation": int(relations.get(family_name, 0)),
                    "allies": list(family.get("allies", [])),
                    "enemies": list(family.get("enemies", [])),
                    "pressure_score": round(abs(float(self.state["market_pressure"]["families"].get(family_name, 0.0))) + float(family.get("risk_appetite", 0.5)) * 0.5, 3),
                    "controlled_company_ids": [str(company.get("id", "")) for company in controlled],
                    "operation_style": str(family.get("strategy", family.get("public_action", "观望"))),
                    "capital_posture": "紧" if float(family.get("liquidity_preference", 0.5)) >= 0.62 else "压" if float(family.get("risk_appetite", 0.5)) >= 0.62 else "守",
                    "briefing_focus": str(briefing.get("focus", family.get("llm_focus", family.get("strategy", "")))),
                    "briefing_signal": str(briefing.get("signal", self._family_signal_from_state(family))),
                    "briefing_source": str(briefing.get("source", "rule")),
                    "recent_briefs": recent_briefs,
                    "brief_history_summary": self._brief_history_summary(recent_briefs, ("public_line", "focus", "hidden_line")),
                }
            )
        self.state["family_moves"] = moves

    def _rebuild_npc_truth_profile(self) -> None:
        profiles: dict[str, dict[str, Any]] = {}
        for npc in self.state.get("npcs", []):
            pressure = max(0.0, min(1.0, (float(npc.get("debt", 0)) / 120.0) + float(npc.get("hunger", 0)) / 180.0 + float(npc.get("anxiety", 0.0)) / 180.0))
            relation = int(npc.get("player_relation", 0))
            loyalty = float(npc.get("loyalty", 0.0))
            truthfulness = max(0.08, min(0.94, float(npc.get("info_reliability", 0.5)) + relation * 0.018 - loyalty * 0.0015 - pressure * 0.22))
            confidence = max(0.12, min(0.96, 0.38 + loyalty * 0.002 + (100.0 - float(npc.get("rumor_sensitivity", 0.4)) * 100.0) * 0.003 - pressure * 0.1))
            profiles[str(npc.get("id", ""))] = {
                "truthfulness": round(truthfulness, 3),
                "confidence": round(confidence, 3),
                "economic_pressure": round(pressure, 3),
                "bias": str(npc.get("family_affiliation", "")) if str(npc.get("family_affiliation", "")) else str(npc.get("stance", "观望")),
                "domains": list(npc.get("information_domain", [])),
            }
        self.state["npc_truth_profile"] = profiles

    def _build_npc_cards(self) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        truth_profiles = self.state.get("npc_truth_profile", {})
        spin_map = self.state.get("npc_spin_map", {})
        for npc in self.state.get("npcs", []):
            profile = truth_profiles.get(str(npc.get("id", "")), {})
            position_kind, position_name, position_qty, position_bias = self._dominant_position(npc)
            economic_pressure = round(float(profile.get("economic_pressure", 0.0)), 3)
            company = self._find_by_id(self.state.get("companies", []), str(npc.get("company_id", "")))
            family = self._find_by_name(self.state.get("families", []), str(npc.get("family_affiliation", ""))) if str(npc.get("family_affiliation", "")) else None
            institution_note = self._npc_institution_note(company, family)
            spin = spin_map.get(str(npc.get("id", "")), {})
            memory_summary = self._npc_memory_summary(npc)
            relation_status = self._npc_player_status(npc)
            favorability = self._npc_favorability_state(npc)
            intel_topic = self._intel_topic_for_npc(npc, str(npc.get("district", "")))
            intel_price = self._npc_intel_price(npc, intel_topic)
            can_sell_info = self._npc_can_sell_info(npc)
            brief_history = copy.deepcopy(self._entity_brief_history("npc_brief_history", str(npc.get("id", ""))))
            cards.append(
                {
                    "id": str(npc.get("id", "")),
                    "name": str(npc.get("name", "")),
                    "title": str(npc.get("title", "")) or str(npc.get("role", "")),
                    "district": str(npc.get("district", "")),
                    "camp": str(npc.get("camp", npc.get("family_affiliation", ""))),
                    "route_alignment": str(npc.get("route_alignment", "")),
                    "subregion_id": str(npc.get("subregion_id", "")),
                    "subregion_name": str(npc.get("subregion_name", "")),
                    "home_building_id": str(npc.get("home_building_id", npc.get("home_id", ""))),
                    "home_building_title": str(npc.get("home_building_title", npc.get("home_label", ""))),
                    "home_subregion_id": str(npc.get("home_subregion_id", "")),
                    "home_subregion_name": str(npc.get("home_subregion_name", "")),
                    "home_mode": str(npc.get("home_mode", "doorstep")),
                    "home_slot": int(npc.get("home_slot", 0)),
                    "schedule_anchor_type": str(npc.get("schedule_anchor_type", "")),
                    "role": str(npc.get("role", "")),
                    "x": round(float(npc.get("x", 0.0)), 1),
                    "y": round(float(npc.get("y", 0.0)), 1),
                    "home_x": round(float(npc.get("home_x", npc.get("x", 0.0))), 1),
                    "home_y": round(float(npc.get("home_y", npc.get("y", 0.0))), 1),
                    "work_x": round(float(npc.get("work_x", npc.get("x", 0.0))), 1),
                    "work_y": round(float(npc.get("work_y", npc.get("y", 0.0))), 1),
                    "social_radius": round(float(npc.get("social_radius", 180.0)), 1),
                    "activity": str(npc.get("activity", "")),
                    "home_state": str(npc.get("home_state", "away")),
                    "indoor_activity": str(npc.get("indoor_activity", "away")),
                    "schedule_note": str(npc.get("schedule_note", "")),
                    "cash": int(npc.get("cash", 0)),
                    "debt": int(npc.get("debt", 0)),
                    "hunger": int(npc.get("hunger", 0)),
                    "inventory": copy.deepcopy(npc.get("inventory", {})),
                    "inventory_summary": self._npc_inventory_summary(npc),
                    "job_security": round(float(npc.get("job_security", 0.0)), 2),
                    "player_trust": round(float(npc.get("player_trust", 0.0)), 2),
                    "economic_pressure": economic_pressure,
                    "truthfulness": round(float(profile.get("truthfulness", 0.5)), 3),
                    "confidence": round(float(profile.get("confidence", 0.5)), 3),
                    "domains": list(profile.get("domains", [])),
                    "position_kind": position_kind,
                    "position_name": position_name,
                    "position_qty": position_qty,
                    "position_bias": position_bias,
                    "institution_note": institution_note,
                    "llm_line": str(spin.get("line", "")),
                    "llm_stance": str(spin.get("stance", npc.get("stance", ""))),
                    "llm_market_tilt": str(spin.get("market_tilt", self._npc_market_tilt(npc))),
                    "llm_source": str(spin.get("source", "rule")),
                    "memory_summary": memory_summary,
                    "relation_status": relation_status,
                    "speech_register": str(favorability.get("speech_register_label", "平视你")),
                    "favorability_state": favorability,
                    "can_sell_info": can_sell_info,
                    "intel_price": intel_price,
                    "gift_threshold": self._npc_bribe_threshold(npc),
                    "follow_threshold": self._npc_follow_threshold(npc),
                    "patronage_status": self._npc_patronage_status(npc),
                    "player_memory": copy.deepcopy(self._npc_player_memory(npc)),
                    "agent_model": str(self.ark.model_id),
                    "agent_budget_left": int(npc.get("agent_budget", {}).get("calls_left", 0)),
                    "agent_talk_budget_left": int(npc.get("agent_budget", {}).get("player_talk_left", 0)),
                    "agent_style": "%s / %s" % (self._npc_social_style(npc), self._npc_market_style(npc)),
                    "agent_agenda": self._npc_agent_agenda(npc),
                    "topic_digest": self._npc_topic_digest(npc),
                    "norm_digest": self._npc_norm_digest(npc),
                    "collective_digest": self._npc_collective_digest(npc),
                    "collective_action_id": str(npc.get("collective_action_id", "")),
                    "collective_role": str(npc.get("collective_role", "")),
                    "agent_prompt_preview": str(npc.get("agent_prompt", ""))[:96],
                    "brief_history": brief_history,
                    "brief_history_summary": self._brief_history_summary(brief_history, ("line", "stance")),
                    "llm_refresh_cadence": int(npc.get("llm_refresh_cadence", 1)),
                    "last_llm_brief_pulse": int(npc.get("last_llm_brief_pulse", -1)),
                    "trade_quotes": self._default_trade_quotes_for_npc(npc),
                    "personal_summary": self._npc_personal_summary(npc, economic_pressure, position_kind, position_name, position_bias, institution_note),
                }
            )
        cards.sort(key=lambda item: (float(item.get("economic_pressure", 0.0)), int(item.get("debt", 0))), reverse=True)
        return cards

    def _npc_personal_summary(
        self,
        npc: dict[str, Any],
        economic_pressure: float,
        position_kind: str,
        position_name: str,
        position_bias: str,
        institution_note: str = "",
    ) -> str:
        summary = f"现金 {int(npc.get('cash', 0))} · 负债 {int(npc.get('debt', 0))} · 压力 {int(round(economic_pressure * 100))}%"
        if self._npc_can_sell_info(npc):
            summary += f" · 卖消息价 {self._npc_intel_price(npc)}"
        patronage = self._npc_patronage_status(npc)
        if patronage:
            summary += f" · {patronage}"
        if position_name:
            summary += f" · {position_kind}:{position_name}({position_bias})"
        if institution_note:
            summary += f" · {institution_note}"
        return summary

    def _npc_institution_note(self, company: dict[str, Any] | None, family: dict[str, Any] | None) -> str:
        if company and str(company.get("active_move", "")):
            return f"公司:{self._institution_action_label(str(company.get('active_move', '')))}"
        if family and str(family.get("public_action", "")):
            return f"家族:{str(family.get('public_action', ''))[:8]}"
        return ""

    def _npc_personal_topics(self, npc: dict[str, Any]) -> list[dict[str, Any]]:
        topics: list[dict[str, Any]] = []
        npc_id = str(npc.get("id", ""))
        district_name = str(npc.get("district", ""))
        truth_profile = self.state.get("npc_truth_profile", {}).get(npc_id, {})
        economic_pressure = float(truth_profile.get("economic_pressure", 0.0))
        if economic_pressure >= 0.32 or float(npc.get("debt", 0)) >= float(npc.get("housing_cost", 4)) * 3:
            topics.append(
                {
                    "id": f"topic_livelihood_{npc_id}",
                    "kind": "livelihood",
                    "district": district_name,
                    "label": f"{npc.get('name', '这人')}的账本",
                    "summary": f"{npc.get('name', '对方')}最近被房租、工钱和欠账一起卡着，嘴上再硬也藏不住日子发紧。",
                    "heat": round(0.18 + economic_pressure, 3),
                    "tags": ["生计", district_name, str(npc.get("role", ""))],
                    "npc_ids": [npc_id],
                    "approaches": ["friendly", "cautious", "hardball"],
                    "impacts": {
                        "goods": self._personal_topic_goods_impact(npc),
                        "stocks": {},
                        "macro": {"worker_unrest": 0.6 if str(npc.get("income_type", "")) == "wage" else 0.2},
                        "families": {},
                    },
                }
            )
        if int(npc.get("hunger", 0)) >= 58:
            topics.append(
                {
                    "id": f"topic_ration_{npc_id}",
                    "kind": "ration",
                    "district": district_name,
                    "label": f"{npc.get('name', '这人')}的口粮",
                    "summary": f"{npc.get('name', '对方')}眼下先惦记的是口粮和今天能不能吃热的，很多判断都会往保命那边偏。",
                    "heat": round(0.16 + int(npc.get("hunger", 0)) / 120.0, 3),
                    "tags": ["口粮", district_name],
                    "npc_ids": [npc_id],
                    "approaches": ["friendly", "cautious"],
                    "impacts": {
                        "goods": {"面包": 0.05, "罐头": 0.03},
                        "stocks": {},
                        "macro": {"worker_unrest": 0.4},
                        "families": {},
                    },
                }
            )
        position_kind, position_name, position_qty, position_bias = self._dominant_position(npc)
        if position_name and position_qty > 0:
            topics.append(
                {
                    "id": f"topic_position_{npc_id}",
                    "kind": "position",
                    "district": district_name,
                    "label": f"{npc.get('name', '这人')}押着的{position_name}",
                    "summary": f"{npc.get('name', '对方')}手里压着 {position_name} x{position_qty}，嘴上的方向多半会往“{position_bias}”那边靠。",
                    "heat": round(0.22 + min(0.45, position_qty * 0.08), 3),
                    "tags": ["持仓", district_name, position_name],
                    "npc_ids": [npc_id],
                    "approaches": ["cautious", "friendly", "hardball"],
                    "impacts": self._personal_position_impacts(position_kind, position_name, position_bias),
                }
            )
        return topics

    def _personal_topic_goods_impact(self, npc: dict[str, Any]) -> dict[str, float]:
        district_name = str(npc.get("district", ""))
        if district_name == "工厂区":
            return {"煤": 0.04}
        if district_name == "港口":
            return {"罐头": 0.04}
        return {"面包": 0.05}

    def _dominant_position(self, npc: dict[str, Any]) -> tuple[str, str, int, str]:
        stock_positions = {str(name): int(value) for name, value in dict(npc.get("stock_positions", {})).items() if int(value) > 0}
        if stock_positions:
            name, qty = max(stock_positions.items(), key=lambda item: item[1])
            bias = "喊多" if float(npc.get("greed_drive", npc.get("greed", 0))) >= float(npc.get("anxiety", npc.get("fear", 0))) else "喊空"
            return "stock", name, qty, bias
        goods_positions = {str(name): int(value) for name, value in dict(npc.get("goods_positions", {})).items() if int(value) > 0}
        if goods_positions:
            name, qty = max(goods_positions.items(), key=lambda item: item[1])
            bias = "囤着" if float(npc.get("anxiety", npc.get("fear", 0))) >= 40 else "找价差"
            return "goods", name, qty, bias
        return "", "", 0, ""

    def _personal_position_impacts(self, position_kind: str, position_name: str, position_bias: str) -> dict[str, Any]:
        if position_kind == "stock":
            delta = 0.05 if position_bias == "喊多" else -0.05
            return {"goods": {}, "stocks": {position_name: delta}, "macro": {"media_sentiment": 0.5}, "families": {}}
        delta = 0.04 if position_bias in {"囤着", "找价差"} else -0.03
        return {"goods": {position_name: delta}, "stocks": {}, "macro": {"economy_heat": 0.2}, "families": {}}

    def _truth_metrics_for_topic(self, npc: dict[str, Any], topic: dict[str, Any], approach: str, intent: str) -> dict[str, Any]:
        base = copy.deepcopy(self.state.get("npc_truth_profile", {}).get(str(npc.get("id", "")), {}))
        if not base:
            self._rebuild_npc_truth_profile()
            base = copy.deepcopy(self.state.get("npc_truth_profile", {}).get(str(npc.get("id", "")), {}))
        truthfulness = float(base.get("truthfulness", 0.5))
        confidence = float(base.get("confidence", 0.5))
        domains = [str(value) for value in base.get("domains", [])]
        memory = self._npc_player_memory(npc)
        kind = str(topic.get("kind", ""))
        if kind == "family" and str(npc.get("family_affiliation", "")):
            truthfulness -= 0.12
        if kind == "company" and "company" not in domains and "labor" not in domains:
            confidence -= 0.08
        if kind in {"livelihood", "ration"}:
            confidence += 0.07 if ("labor" in domains or "ration" in domains) else -0.03
            truthfulness += 0.05 if float(base.get("economic_pressure", 0.0)) >= 0.3 else -0.02
        if kind == "position":
            confidence += 0.08 if ("stock" in domains or "trade" in domains) else -0.04
            truthfulness -= 0.06 if float(base.get("economic_pressure", 0.0)) >= 0.45 else 0.0
        if kind == "asset" and "stock" in domains:
            confidence += 0.08
        if kind == "institution":
            confidence += 0.06 if any(domain in domains for domain in ["family", "company", "media", "labor"]) else -0.04
            if str(npc.get("family_affiliation", "")) and str(npc.get("family_affiliation", "")) in [str(value) for value in topic.get("tags", [])]:
                truthfulness -= 0.08
        confidence += min(0.08, int(memory.get("intel_bought", 0)) * 0.012)
        truthfulness += min(0.1, int(memory.get("friendly_count", 0)) * 0.015)
        truthfulness -= min(0.16, float(memory.get("pressure_from_player", 0.0)) * 0.03)
        if str(memory.get("last_topic_id", "")) == str(topic.get("id", "")):
            confidence += 0.05
        if approach == "friendly":
            truthfulness += 0.06
        elif approach == "hardball":
            confidence -= 0.06
            truthfulness -= 0.08
        if "问工作" in intent and "labor" in domains:
            confidence += 0.06
        if "问谁在放风" in intent or kind == "panic":
            truthfulness -= max(0.0, float(base.get("economic_pressure", 0.0)) * 0.08)
        return {
            "truthfulness": round(max(0.08, min(0.95, truthfulness)), 3),
            "confidence": round(max(0.08, min(0.96, confidence)), 3),
            "bias": str(base.get("bias", npc.get("stance", "观望"))),
            "domains": domains,
            "economic_pressure": float(base.get("economic_pressure", 0.0)),
            "player_memory_summary": self._npc_memory_summary(npc),
            "player_memory": copy.deepcopy(memory),
        }

    def _spin_intel_packet(self, packet: dict[str, Any], npc: dict[str, Any], truth_profile: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
        spun = copy.deepcopy(packet)
        truthfulness = float(truth_profile.get("truthfulness", 0.5))
        confidence = float(truth_profile.get("confidence", 0.5))
        if truthfulness < 0.32:
            strongest_stock = next(iter(spun.get("stocks_delta", {})), "")
            strongest_good = next(iter(spun.get("goods_delta", {})), "")
            if strongest_stock:
                spun["stocks_delta"][strongest_stock] = round(float(spun["stocks_delta"][strongest_stock]) * -0.45, 3)
            if strongest_good:
                spun["goods_delta"][strongest_good] = round(float(spun["goods_delta"][strongest_good]) * -0.4, 3)
            spun["line"] = f"{npc.get('name', '那人')} 把 {topic.get('label', '这件事')} 说得很满，听着像在带方向。"
        elif confidence < 0.42:
            spun["line"] = f"{npc.get('name', '那人')} 只肯递半句：{topic.get('summary', spun.get('line', '街头有风声。'))}"
            spun["goods_delta"] = {key: round(float(value) * 0.55, 3) for key, value in spun.get("goods_delta", {}).items()}
            spun["stocks_delta"] = {key: round(float(value) * 0.55, 3) for key, value in spun.get("stocks_delta", {}).items()}
        return spun

    def _describe_world_effects(self, intel: dict[str, Any], strength: float) -> str:
        if strength <= 0.12:
            return "这次只摸到态度，街上的价格和情绪还没被你撬动。"
        pieces: list[str] = []
        if intel.get("goods_delta"):
            goods_text = "、".join(f"{name}{'涨' if float(delta) > 0 else '跌'}" for name, delta in intel["goods_delta"].items())
            pieces.append(f"货物风向：{goods_text}")
        if intel.get("stocks_delta"):
            stock_text = "、".join(f"{name}{'被捧' if float(delta) > 0 else '被压'}" for name, delta in intel["stocks_delta"].items())
            pieces.append(f"盘口：{stock_text}")
        if intel.get("family_delta"):
            family_text = "、".join(f"{name}{'更热' if float(delta) > 0 else '更紧'}" for name, delta in intel["family_delta"].items())
            pieces.append(f"家族：{family_text}")
        if intel.get("macro_delta"):
            macro_text = "、".join(str(key) for key in intel["macro_delta"].keys())
            pieces.append(f"城里气压：{macro_text}")
        return "；".join(pieces[:3]) if pieces else "这条话已经进了街区风向。"

    def _build_district_topic_map(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for topic in self.state.get("talk_topics", []):
            district_name = str(topic.get("district", ""))
            if not district_name:
                continue
            grouped.setdefault(district_name, []).append(copy.deepcopy(topic))
        for district_name, items in grouped.items():
            items.sort(key=lambda item: float(item.get("heat", 0.0)), reverse=True)
            grouped[district_name] = items[:4]
        return grouped

    def _build_city_news(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for news in self.state.get("global_news", []):
            title = str(news.get("title", "")).strip()
            body = str(news.get("body", "")).strip()
            if not title or not body:
                continue
            key = (title, body)
            if key in seen:
                continue
            seen.add(key)
            items.append(copy.deepcopy(news))
            if len(items) >= 4:
                return items
        for action in self.state.get("institution_actions", []):
            if str(action.get("scope", "district")) != "city":
                continue
            title = str(action.get("headline", "")).strip()
            body = str(action.get("news_body", action.get("public_line", ""))).strip()
            if not title or not body:
                continue
            key = (title, body)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "title": title,
                    "body": body,
                    "tags": list(action.get("tags", [])),
                    "scope": "city",
                    "tone": str(action.get("tone", "cold")),
                }
            )
            if len(items) >= 4:
                break
        return items

    def _institution_topics(self) -> list[dict[str, Any]]:
        topics: list[dict[str, Any]] = []
        for action in self.state.get("institution_actions", [])[:4]:
            district_name = str(action.get("district", ""))
            if not district_name:
                continue
            actor_type = str(action.get("actor_type", ""))
            actor_name = str(action.get("actor_name", "机构"))
            target_asset = str(action.get("target_asset", ""))
            npc_ids = [npc["id"] for npc in self._linked_npcs_for_company(str(action.get("actor_id", "")))] if actor_type == "company" else [
                npc["id"] for npc in self._linked_npcs_for_family(actor_name)
            ]
            topics.append(
                {
                    "id": f"topic_institution_{actor_type}_{action.get('actor_id', actor_name)}_{action.get('kind', '')}",
                    "kind": "institution",
                    "district": district_name,
                    "label": f"{actor_name} 刚出的手",
                    "summary": str(action.get("public_line", "")),
                    "heat": round(0.22 + float(action.get("effect_score", 0.4)), 3),
                    "tags": list(action.get("tags", ["机构", actor_name])),
                    "npc_ids": npc_ids,
                    "approaches": ["cautious", "friendly", "hardball"],
                    "impacts": self._institution_topic_impacts(action, target_asset),
                }
            )
        return topics

    def _institution_topic_impacts(self, action: dict[str, Any], target_asset: str) -> dict[str, Any]:
        kind = str(action.get("kind", ""))
        goods: dict[str, float] = {}
        stocks: dict[str, float] = {}
        macro: dict[str, float] = {}
        families: dict[str, float] = {}
        direction = 1.0
        if kind in {"lean_short", "cut_shift", "tighten_books"}:
            direction = -1.0
        if target_asset in self.state.get("market_pressure", {}).get("stocks", {}):
            stocks[target_asset] = round(0.05 * direction, 3)
        if target_asset in self.state.get("market_pressure", {}).get("goods", {}):
            goods[target_asset] = round(0.04 * direction, 3)
        if kind in {"bridge_loan", "tighten_books"}:
            macro["interest_rate"] = 0.08 if kind == "tighten_books" else -0.04
        if kind in {"cut_shift", "overtime_push"}:
            macro["worker_unrest"] = 0.8 if kind == "cut_shift" else 0.3
        if kind in {"spin_campaign", "bury_story"}:
            macro["media_sentiment"] = 0.8 if kind == "spin_campaign" else -0.5
        if str(action.get("actor_type", "")) == "family":
            families[str(action.get("actor_name", ""))] = 0.07 * direction
        return {"goods": goods, "stocks": stocks, "macro": macro, "families": families}

    def _company_topic_goods_impact(self, company_state: dict[str, Any]) -> dict[str, float]:
        industry = str(company_state.get("name", "")) + str(company_state.get("stock_name", ""))
        if any(token in industry for token in ["海藻", "食业", "农业", "食物"]):
            return {"面包": 0.05}
        if any(token in industry for token in ["船坞", "船运", "物流", "港"]):
            return {"煤": 0.05, "罐头": 0.03}
        if any(token in industry for token in ["珊瑚", "银行", "金控", "证券"]):
            return {"罐头": 0.04}
        return {"面包": 0.04}

    def _good_chain_bonus(self, good: dict[str, Any]) -> float:
        good_name = str(good.get("name", ""))
        bonus = 0.0
        for company in self.state.get("companies", []):
            industry = str(company.get("industry", "")) + str(company.get("name", ""))
            if good_name == "面包" and any(token in industry for token in ["海藻", "食业", "农业", "食物"]):
                bonus += (50.0 - float(company.get("inventory", 50))) * 0.0008
            if good_name == "煤" and any(token in industry for token in ["船坞", "船运", "物流", "港"]):
                bonus += (float(company.get("order_pressure", 50)) - 50.0) * 0.001
            if good_name == "罐头" and any(token in industry for token in ["珊瑚", "银行", "金控", "证券"]):
                bonus += (float(company.get("financing_pressure", 50)) - 50.0) * 0.0008
        return round(max(-0.08, min(0.08, bonus)), 4)

    def _company_for_stock(self, stock: dict[str, Any]) -> dict[str, Any] | None:
        stock_name = str(stock.get("name", ""))
        for company in self.state.get("companies", []):
            if str(company.get("stock_name", "")) == stock_name:
                return company
        return None

    def _as_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _stock_macro_bonus(self, stock: dict[str, Any]) -> float:
        media = (float(self.state["macro"].get("media_sentiment", 50)) - 50.0) * (0.002 + self._as_float(stock.get("media_sensitivity", 0.4), 0.4) * 0.002)
        economy = (float(self.state["macro"].get("economy_heat", 50)) - 50.0) * 0.0025
        rate_drag = (float(self.state["macro"].get("interest_rate", 2.0)) - 2.0) * -0.018
        return round(media + economy + rate_drag, 4)

    def _stock_family_bonus(self, stock: dict[str, Any]) -> float:
        family_name = str(stock.get("family_owner", ""))
        pressure = float(self.state.get("market_pressure", {}).get("families", {}).get(family_name, 0.0))
        return round(pressure * 0.35 + self.random.uniform(-0.02, 0.03), 4)

    def _stock_company_bonus(self, stock: dict[str, Any]) -> float:
        company = self._company_for_stock(stock)
        if not company:
            return 0.0
        return round((float(company.get("profit_margin", 0.12)) - 0.12) * 0.8 + (float(company.get("order_pressure", 50.0)) - 50.0) * 0.0018 - (float(company.get("financing_pressure", 45.0)) - 45.0) * 0.0015 - float(company.get("wage_pressure", 35.0)) * 0.0008, 4)

    def _family_company_pressure(self, companies: list[dict[str, Any]]) -> float:
        if not companies:
            return 0.0
        avg_pressure = sum(float(company.get("financing_pressure", 45.0)) + float(company.get("wage_pressure", 35.0)) for company in companies) / (2.0 * len(companies))
        return round((avg_pressure - 45.0) * 0.0016, 4)

    def _family_public_move(self, family: dict[str, Any], companies: list[dict[str, Any]], target: str) -> str:
        if not companies:
            return str(family.get("public_action", "低调观望"))
        hottest = max(companies, key=lambda company: float(company.get("order_pressure", 0.0)) - float(company.get("financing_pressure", 0.0)))
        if float(hottest.get("financing_pressure", 0.0)) >= 70:
            return f"替 {hottest.get('name', target)} 收紧账本"
        if float(hottest.get("order_pressure", 0.0)) >= 68:
            return f"替 {hottest.get('name', target)} 护盘抢单"
        return f"盯住 {target or hottest.get('name', '街头温度')}"

    def _family_hidden_move(self, family: dict[str, Any], companies: list[dict[str, Any]], target: str) -> str:
        if not companies:
            return str(family.get("hidden_action", "沿着街头放风"))
        weakest = max(companies, key=lambda company: float(company.get("wage_pressure", 0.0)) + float(company.get("financing_pressure", 0.0)))
        if float(weakest.get("wage_pressure", 0.0)) >= 65:
            return f"沿着 {weakest.get('district', '街区')} 压住工价口风"
        if float(weakest.get("financing_pressure", 0.0)) >= 60:
            return f"让代理人去试探 {target or weakest.get('stock_name', '盘口')}"
        return f"沿着 {target or weakest.get('name', '街区')} 放风"

    def _select_player_talk_topic(
        self,
        npc: dict[str, Any],
        topic_id: str,
        district_name: str,
        player_input: str = "",
        intent: str = "",
    ) -> dict[str, Any]:
        resolved = self._resolve_talk_topic(npc, topic_id, district_name)
        if topic_id:
            return resolved
        npc_topics = self._talk_topics_for_npc(str(npc.get("id", "")), district_name)
        personal_topics = self._npc_personal_topics(npc)
        hint = f"{player_input} {intent}".lower()
        domains = {str(value) for value in npc.get("information_domain", [])}
        role = str(npc.get("role", ""))
        title = str(npc.get("title", ""))
        market_roles = {"投机者", "银行经理", "代理人", "记者", "老板"}
        identity_hint = any(
            token in hint
            for token in [
                "你是谁",
                "你是干啥的",
                "你干啥",
                "你干什么",
                "什么身份",
                "什么来头",
                "哪路",
                "哪边的",
                "和谁一伙",
                "谁的人",
                "替谁办事",
                "为谁做事",
            ]
        )
        stance_hint = any(token in hint for token in ["站哪边", "哪边的人", "谁的人", "和谁一伙", "替谁办事", "为谁做事"])
        market_hint = any(token in hint for token in ["票", "股", "盘口", "仓", "价格", "涨", "跌", "做局", "利息", "放风"])
        wants_market = market_hint
        wants_actor = any(token in hint for token in ["谁", "哪家", "哪边", "做局", "放风", "护盘"])
        if identity_hint:
            return self._identity_topic_for_npc(npc, district_name)
        non_market_priority = ["identity", "livelihood", "routine", "relationship", "rumor", "district", "ration", "labor", "family", "institution", "company"]
        kind_priority = ["position", "asset", "finance", "company", "institution", "family"]
        if "操盘手" in title:
            kind_priority = ["position", "finance", "asset", "company", "institution", "family"]
        elif "交际花" in title:
            kind_priority = ["institution", "company", "finance", "asset", "position", "family"]
        elif "名媛" in title:
            kind_priority = ["family", "company", "asset", "position", "finance", "institution"]
        elif "发言人" in title or role == "记者":
            kind_priority = ["company", "institution", "asset", "finance", "position", "family"]
        elif "经理" in title or role in {"银行经理", "代理人"}:
            kind_priority = ["finance", "company", "asset", "position", "institution", "family"]
        elif any(token in title for token in ["官", "顾问", "律师"]):
            kind_priority = ["institution", "company", "family", "finance", "asset", "position"]
        if stance_hint:
            kind_priority = ["institution", "family", "company", "finance", "asset", "position"]
        elif any(token in hint for token in ["股东", "家族", "后台", "哪家"]):
            kind_priority = ["family", "company", "institution", "finance", "asset", "position"]
        elif wants_actor:
            kind_priority = ["institution", "company", "family", "finance", "asset", "position"]
        elif not wants_market:
            kind_priority = non_market_priority
        merged_topics: list[dict[str, Any]] = []
        seen_topic_ids: set[str] = set()
        for row in personal_topics + npc_topics:
            row_id = str(row.get("id", ""))
            if row_id and row_id in seen_topic_ids:
                continue
            if row_id:
                seen_topic_ids.add(row_id)
            merged_topics.append(row)

        def _pick_topic(kinds: list[str], allow_panic: bool = False) -> dict[str, Any] | None:
            for kind in kinds:
                for row in merged_topics:
                    if str(row.get("kind", "")) != kind:
                        continue
                    if not allow_panic and str(row.get("kind", "")) == "panic":
                        continue
                    return row
            return None

        if wants_market or wants_actor:
            picked = _pick_topic(kind_priority)
            if picked:
                return picked
        if str(resolved.get("id", "")) == "generic_wind" or str(resolved.get("kind", "")) == "panic":
            picked = _pick_topic(kind_priority)
            if picked:
                return picked
            if personal_topics:
                return personal_topics[0]
            for topic in npc_topics:
                if str(topic.get("kind", "")) != "panic":
                    return topic
        if not wants_market and str(resolved.get("kind", "")) in {"position", "asset", "finance"}:
            picked = _pick_topic(non_market_priority)
            if picked:
                return picked
        return resolved

    def _identity_topic_for_npc(self, npc: dict[str, Any], district_name: str) -> dict[str, Any]:
        name = str(npc.get("name", "对方"))
        title = str(npc.get("title", npc.get("role", "")))
        role = str(npc.get("role", "本地角色"))
        family = str(npc.get("family_affiliation", "")) or "无"
        camp = str(npc.get("camp", "")) or family
        district = district_name or str(npc.get("district", "街区"))
        return {
            "id": f"topic_identity_{npc.get('id', name)}",
            "kind": "identity",
            "district": district,
            "label": f"{name}的身份和来路",
            "summary": f"{name}明面上是{title}，平时以{role}的身份在{district}活动，背后和{camp}这条线牵得更近。",
            "heat": 0.82,
            "npc_ids": [str(npc.get("id", ""))],
            "tags": [district, title or role, family, camp],
            "approaches": ["friendly", "cautious", "hardball"],
            "impacts": {},
        }

    def _rule_player_talk_lead(
        self,
        npc: dict[str, Any],
        register: str,
        salutation: str,
        topic: dict[str, Any],
    ) -> str:
        title = str(npc.get("title", ""))
        role = str(npc.get("role", ""))
        label = str(topic.get("label", npc.get("district", "这事")))
        if "操盘手" in title:
            base = f"{salutation}，{label} 这口风先看谁补保证金，再看谁敢开口。"
        elif "交际花" in title:
            base = f"{salutation}，你想听的是台面价，还是包厢里那层真价？"
        elif "名媛" in title:
            base = f"{salutation}，别把酒杯碰出来的笑脸都当成利好。"
        elif "发言人" in title or role == "记者":
            base = f"{salutation}，公开口径是一套，停顿里的口风是另一套。"
        elif "经理" in title or role in {"银行经理", "代理人"}:
            base = f"{salutation}，账面稳不稳不重要，重要的是谁先抽梯子。"
        else:
            base = f"{salutation}，{label} 这事表面热闹，底下才值钱。"
        if register == "owned":
            return f"你既然肯把筹码压过来，我就按最贵的那层说。{base}"
        if register == "bought":
            return f"钱既然已经落袋，我就不替谁包糖衣。{base}"
        if register == "patronized":
            return base
        if register == "deferential":
            return f"你既然肯来，我就把能说的先递你半层。{base}"
        if register == "warm":
            return f"这次你问得还像个懂行的。{base}"
        if register == "slick":
            return f"要真想听深一点，价和人情总得有一样先到位。{base}"
        return base

    def _rule_player_talk_lines(
        self,
        npc: dict[str, Any],
        topic: dict[str, Any],
        approach: str,
        openness: str,
        intent: str = "",
        player_input: str = "",
    ) -> list[str]:
        favorability = self._npc_favorability_state(npc)
        register = str(favorability.get("speech_register", "neutral"))
        salutation = "哥" if register in {"deferential", "slick", "patronized", "owned"} and float(favorability.get("respect", 0.0)) >= 0.56 else "朋友"
        cleaned_player_input = str(player_input).strip()
        hint_flags = self._player_talk_hint_flags(cleaned_player_input, intent)
        if cleaned_player_input and bool(hint_flags.get("greeting", False)) and not bool(hint_flags.get("market", False)) and not bool(hint_flags.get("actor", False)):
            npc_name = str(npc.get("name", "对方"))
            district = str(npc.get("district", "这片街区"))
            reply = f"{npc_name}：你好。先别紧张，我在{district}这边跑腿。你想先聊近况、身份，还是哪件麻烦事？"
            return [cleaned_player_input, reply]
        player_line = cleaned_player_input or {
            "cautious": f"我只想问一句，{topic.get('label', npc['district'])} 最近是不是在变？",
            "friendly": f"我不是来压你话的，就想听听你怎么看 {topic.get('label', npc['district'])}。",
            "hardball": f"别绕了，{topic.get('label', npc['district'])} 到底是谁在做局？",
        }.get(approach, f"最近 {topic.get('label', npc['district'])} 的风向到底怎么走？")
        core_line = self._rule_player_talk_core_line(npc, topic)
        lead = self._rule_player_talk_lead(npc, register, salutation, topic)
        if register == "owned":
            reply = f"{npc['name']}：{lead}{core_line}"
        elif register == "bought":
            reply = f"{npc['name']}：{lead}{core_line}"
        elif register == "patronized":
            reply = f"{npc['name']}：{lead}{core_line}"
        elif register == "hostile":
            reply = f"{npc['name']}：你口气收一收。{topic.get('label', npc['district'])} 这事不是你想逼就逼得出来的。"
        elif register == "sullen":
            reply = f"{npc['name']}：话我不是不能说，但你别真把人当能随手拿捏的壳。"
        elif openness == "guarded":
            reply = f"{npc['name']}：{lead}不过这话题在 {npc['district']} 不便宜。{core_line}"
        elif openness == "skeptical":
            reply = f"{npc['name']}：{lead}我只说半句，剩下半句你自己拿壳去试。{core_line}"
        elif register == "deferential":
            reply = f"{npc['name']}：{lead}{core_line}"
        elif register == "warm":
            reply = f"{npc['name']}：{lead}{core_line}"
        elif register == "slick":
            reply = f"{npc['name']}：{lead}{core_line}"
        else:
            reply = self.random.choice(
                [
                    f"{npc['name']}：{core_line}",
                    f"{npc['name']}：{lead}{core_line}",
                    f"{npc['name']}：真相没那么直，但 {topic.get('label', npc['district'])} 这事已经把街上气味带歪了。{core_line}",
                ]
            )
        return [player_line, reply]

    def _rule_player_talk_core_line(self, npc: dict[str, Any], topic: dict[str, Any]) -> str:
        topic_kind = str(topic.get("kind", ""))
        topic_label = str(topic.get("label", npc.get("district", "这件事")))
        topic_summary = str(topic.get("summary", "街上都在看这件事。"))
        role = str(npc.get("role", ""))
        title = str(npc.get("title", role or "本地角色"))
        camp = str(npc.get("camp", npc.get("family_affiliation", "")))
        profile = self._npc_prompt_profile(npc)
        secret = str(profile.get("current_secret", "")).strip()
        leverage_points = [str(item).strip() for item in profile.get("leverage_points", []) if str(item).strip()]
        watch_people = [str(item).strip() for item in profile.get("watch_people", []) if str(item).strip()]
        position_kind, position_name, position_qty, position_bias = self._dominant_position(npc)
        if topic_kind == "identity":
            if "交际花" in title:
                return "台面上我是交际花，靠酒局、饭局和男人的虚荣心吃饭。真要问我站哪边，我只站在能让我活得更贵、也更安全的那边。"
            if "操盘手" in title:
                return "明面上我是首席操盘手，替人盯盘、修口径、挪风险。你要问我替谁办事，就盯着海藻资本那条资金线看。"
            if "名媛" in title:
                return "明面上我是别墅区名媛，实际更像替股东家庭试风向的人。酒杯端得越稳，越说明我背后那群人不愿先露底。"
            if "顾问" in title or role == "代理人":
                return f"明面上我是{title}，靠规则、合同和口风吃饭。真要分边站，我离 {camp or title} 这条线更近。"
            if role == "记者":
                return f"我明面上是{title or role}，吃的是消息饭。站队这种事，我一般不认嘴上那套，只认谁在背后给风向加价。"
            return f"明面上我是{title or role}，在{npc.get('district', '这地方')}吃这口饭。你要问我替谁办事，我更接近 {camp or title} 这条线。"
        if topic_kind == "position" and position_kind == "stock":
            if "操盘手" in title:
                return (
                    f"{position_name} 我压着 {position_qty} 不是给你看热闹的。"
                    f"盘面每抖一下，我都在看谁先补保证金，谁还想把旧账继续压到明天。"
                )
            if "交际花" in title:
                return (
                    f"{position_name} 的价只是桌面，桌下更值钱的是名单和醉话。"
                    f"我手里也捏着一点仓，谁今晚忽然不接我电话，谁八成就在准备撤。"
                )
            if "名媛" in title:
                return (
                    f"{position_name} 我也压着 {position_qty}，可别墅区真正先泄底的从来不是 K 线，"
                    f"而是哪位股东家里先把酒杯放下。"
                )
            if "发言人" in title or role == "记者":
                return (
                    f"{position_name} 的价我盯着，人心我也盯着。"
                    f"今早谁还在替人稳口径，谁就是怕这只票撑不过午后。"
                )
            if "经理" in title or role in {"代理人", "银行经理"}:
                return (
                    f"{position_name} 这边我盯的不是热闹，是谁先缩手、谁还在加杠杆。"
                    f"手里这点仓位，只说明我不信场面话。"
                )
            if role == "投机者":
                return f"我手里压着 {position_name} x{position_qty}，眼下更偏{position_bias}。在交易所里，先动嘴的人往往是在替仓位探路。"
            return f"{topic_summary} 我自己手里还压着 {position_name} x{position_qty}，口风不会完全中性。"
        if topic_kind == "finance":
            if "交际花" in title:
                return "利息只是桌上的说法，真正值钱的是谁在借债遮丑、谁在拿名单求活。你现在听到的每一句稳，都可能是昨晚敬出来的。"
            if "名媛" in title:
                return "融资这件事在别墅区从来不叫融资，叫体面。谁家开始急着问质押和过桥，谁家就先闻到自己的血味。"
            if "操盘手" in title:
                return "信用风一紧，盘面就先抽筋。聪明人现在不表态，只盯着谁会先被迫砍仓，谁又想把锅继续挪给别人。"
            if role in {"代理人", "银行经理"}:
                return "这边现在盯的是信用、利息和谁先抽梯子。表面都说稳，真正在算的是哪边先断现金。"
            if role == "投机者":
                return "利息风一变，盘面就先抽筋。聪明人现在不忙着表态，忙着看谁在借题洗仓。"
            return f"{topic_summary} 真正值钱的是谁先把这股风拿去做价格。"
        if topic_kind == "asset":
            if "交际花" in title:
                return f"{topic_label} 现在不只是价格问题，还是谁愿意拿自己的名声给它垫一层。越急着说看好的人，往往越怕别人先跑。"
            if "名媛" in title:
                return f"{topic_label} 在酒会里已经不是票，是家族站队。谁还愿意举杯提它，谁就是还没找到更好的退路。"
            if position_kind == "stock" and position_name:
                return f"{topic_label} 现在不只是价格问题。像我这种手里有 {position_name} 的人，更看谁在借消息逼别人先动。"
            return f"{topic_summary} 这地方已经不是单看牌价了，连谁站在哪边都算进盘口。"
        if topic_kind == "company":
            if "操盘手" in title:
                return f"{topic_summary} 公司动作只是壳，真正要命的是谁在用它挪假账、拖时间和找替身。"
            if "交际花" in title:
                return f"{topic_summary} 公司公告只给外人看，包厢里谈的是谁能替谁保住名字，谁又准备把谁送出去挡刀。"
            if "名媛" in title:
                return f"{topic_summary} 这事在上流圈子里谈的从来不是公司本身，而是谁家的股份先变成了麻烦。"
            return f"{topic_summary} 这事表面是公司动作，底下其实是 {camp or title} 在抢谁先开口。"
        if topic_kind == "family":
            if "名媛" in title:
                return f"{topic_label} 这种事在别墅区不会有人明说，但谁忽然开始替家里切割，谁就知道火已经烧到门廊了。"
            if leverage_points:
                return f"{topic_summary} 真正能撬开的不是脸面，是 {leverage_points[0]} 这类握在手里的东西。"
            return topic_summary
        if topic_kind == "institution":
            if "交际花" in title:
                return f"{topic_label} 最有意思的从来不是规矩，是哪位大人物酒醒以后开始求我删名字。"
            if secret:
                return f"{topic_summary} 真正让人不敢睡的，是那层还没摆上桌的秘密。"
            return topic_summary
        if topic_kind == "panic":
            if "交际花" in title:
                return "耳语越密，说明越多人想把自己的名字从名单里擦掉。你现在听到的慌，多半已经被人修过价。"
            if "名媛" in title:
                return "坏消息在别墅区从不先喊出来，只会先体现在谁忽然不赴约、谁忽然装作没看见你。"
            if "操盘手" in title:
                return "坏消息现在只是引子，真正的戏在谁借这股慌劲把别人洗下车，再顺手把账推给更慢的人。"
            if role == "投机者":
                return "坏消息现在只是引子，真正的戏在谁借这股慌劲把别人洗下车。"
            if role in {"记者", "代理人"}:
                return "耳语一密，说明有人希望这阵风先自己长腿。你现在听到的，多半已经是别人挑过的版本。"
            return topic_summary
        if topic_kind == "livelihood":
            return f"{topic_summary} 人一旦被账和饭卡住，说出来的话就不会完全干净。"
        if watch_people and secret:
            return f"{topic_summary} 我现在更盯着 {watch_people[0]} 那边会不会先露口子，毕竟真正值钱的还是那层没公开的秘密。"
        return topic_summary

    def action(self, action_type: str, district: str, payload: dict[str, Any] | None = None) -> ActionResult:
        payload = payload or {}
        with self.lock:
            if action_type == "choose_route":
                return self._apply_route_selection(str(payload.get("route", "")))
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                title = str(ending.get("title", "结局已触发"))
                body = str(ending.get("body", "当前存档已经进入失败结局。"))
                return ActionResult(f"{title}：{body}", self.snapshot_cached())
            self._advance_realtime_clock()
            self._check_stock_account_state(trigger=action_type)
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
            if action_type in {"work", "gather_info", "rest", "cook_meal", "search_home", "review_ledger", "collective_intervene", "buy_intel"}:
                self._consume_ap_block(f"AP:{action_type}")
                self._check_stock_account_state(trigger=f"{action_type}_ap")
                if bool(self.state.get("ending_state", {}).get("game_over", False)):
                    ending = dict(self.state.get("ending_state", {}))
                    return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
            match action_type:
                case "work":
                    return self._do_work(district)
                case "gather_info":
                    return self._gather_info(district)
                case "rest":
                    return self._rest_at_home(district, payload)
                case "cook_meal":
                    return self._cook_meal(district, payload)
                case "search_home":
                    return self._search_home(district, payload)
                case "review_ledger":
                    return self._review_ledger(district, payload)
                case "buy_goods":
                    return self._trade_good(payload["good_name"], int(payload.get("quantity", 1)), 1, payload)
                case "sell_goods":
                    return self._trade_good(payload["good_name"], int(payload.get("quantity", 1)), -1, payload)
                case "buy_stock":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_v2(stock_ref, int(payload.get("quantity", 1)), 1, int(payload.get("leverage", 1)))
                case "sell_stock":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_v2(stock_ref, int(payload.get("quantity", 1)), -1, int(payload.get("leverage", 1)))
                case "short_stock":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_short_v2(stock_ref, int(payload.get("quantity", 1)), 1, int(payload.get("leverage", 1)))
                case "cover_short":
                    stock_ref = str(payload.get("stock_name") or payload.get("stock_key") or payload.get("ticker") or payload.get("id") or "")
                    return self._trade_stock_short_v2(stock_ref, int(payload.get("quantity", 1)), -1, int(payload.get("leverage", 1)))
                case "gift_money":
                    return self._gift_money_to_npc(str(payload.get("npc_id", "")), int(payload.get("amount", 0)), district)
                case "buy_intel":
                    return self._buy_intel_from_npc(str(payload.get("npc_id", "")), int(payload.get("amount", 0)), str(payload.get("topic_id", "")), district)
                case "fake_boom_report":
                    return self._run_stock_special_operation("fake_boom_report")
                case "manufacture_dock_conflict":
                    return self._run_stock_special_operation("manufacture_dock_conflict")
                case "emergency_bond_issue":
                    return self._run_stock_special_operation("emergency_bond_issue")
                case "hostile_takeover":
                    return self._run_stock_special_operation("hostile_takeover")
                case "policy_shield":
                    return self._run_stock_special_operation("policy_shield")
                case "hire_scar_cover":
                    return self._run_stock_special_operation("hire_scar_cover")
                case "collective_intervene":
                    return self._intervene_collective(district, payload)
                case "accept_task":
                    return self._accept_task(payload["task_id"])
                case "claim_task":
                    return self._claim_task(payload["task_id"])
                case _:
                    return ActionResult("未识别的行动。", self.snapshot())

    def ai_pulse(
        self,
        trigger: str = "scheduled",
        scene_observation: dict[str, Any] | None = None,
        allow_live_llm: bool | None = None,
    ) -> ActionResult:
        with self.lock:
            previous_tick = self._world_tick()
            self._advance_realtime_clock()
            if self._world_tick() == previous_tick and bool(self.state.get("player", {}).get("stock_liquidation_pending", False)):
                self._advance_clock(1)
            self._check_stock_account_state(trigger=trigger)
            if bool(self.state.get("ending_state", {}).get("game_over", False)):
                ending = dict(self.state.get("ending_state", {}))
                return ActionResult(str(ending.get("body", "当前存档已经进入失败结局。")), self._snapshot_after_refresh(rebuild_agent_prompts=False))
            self._run_livelihood_tick(trigger)
            self._settle_company_operations(trigger)
            self._apply_institution_actions(trigger)
            if scene_observation:
                self._record_scene_observation(scene_observation)
            self.state["demo_metrics"]["ai_pulses"] = int(self.state["demo_metrics"].get("ai_pulses", 0)) + 1
            self._generate_ai_pulse(trigger=trigger, allow_live_llm_override=allow_live_llm)
            var_allow_social_llm = self._allow_live_pulse_llm(trigger) if allow_live_llm is None else bool(allow_live_llm)
            self._run_agent_social_turns(scene_observation or {}, allow_llm=var_allow_social_llm)
            self._apply_intraday_market_move(reason="ai_pulse", decay=0.72)
            self._decay_district_signals()
            self._refresh_derived_views()
            return ActionResult("街头耳语刷新了。", self.snapshot())

    def _gather_info(self, district: str) -> ActionResult:
        player = self.state["player"]
        if player["cash"] < 2:
            return ActionResult("你连买消息的铜币都不够。", self.snapshot())
        player["cash"] -= 2
        intel = self._build_intel_packet(district, source="街头耳报")
        self._apply_intel_packet(intel, to_player=True, promote_news=True, intensity=1.0)
        self._increment_task_progress("gather_info", "any", 1)
        self.state["demo_metrics"]["intel_actions"] = int(self.state["demo_metrics"].get("intel_actions", 0)) + 1
        self._bump_district_signal(district, "gossip", 0.3)
        self._bump_district_signal(district, "fear", 0.08 if "恐慌" in intel.get("tags", []) else 0.0)
        self._apply_intraday_market_move(reason="gather_info", decay=0.74)
        return ActionResult(f"你记下了一条还未落地的情报：{intel['line']}", self.snapshot())

    def _rest_at_home(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        player["credit"] = min(100, player["credit"] + 2)
        player["reputation"] = min(100, player["reputation"] + 1)
        player["rumors"] = player["rumors"][-5:]
        player["hunger"] = min(100.0, float(player.get("hunger", 100.0)) + 12.0)
        player["stamina"] = min(100.0, float(player.get("stamina", 100.0)) + 18.0)
        house_title = str(payload.get("house_title", "屋子"))
        self.state["global_news"].insert(
            0,
            {
                "title": f"{district} 夜灯渐稳",
                "body": f"你在 {house_title} 的木床上缓了一阵，脑子总算没那么紧了。",
                "tags": ["休整", district],
                "scope": "district",
            },
        )
        self.state["global_news"] = self.state["global_news"][:8]
        return ActionResult(f"你在 {house_title} 里缓了一口气。", self.snapshot())

    def _cook_meal(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        inventory = player["goods_inventory"]
        if inventory.get("面包", 0) > 0:
            inventory["面包"] -= 1
            meal_note = "你把面包热了热，又煮了一小锅浓汤。"
        else:
            if player["cash"] < 3:
                return ActionResult("炉台有火，但你连做饭的钱都快没了。", self.snapshot())
            player["cash"] -= 3
            meal_note = "你掏出 3 铜币凑出了一顿热饭。"
        player["credit"] = min(100, player["credit"] + 1)
        player["hunger"] = min(100.0, float(player.get("hunger", 100.0)) + 22.0)
        return ActionResult(meal_note, self.snapshot())

    def _search_home(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        roll = self.random.random()
        if roll < 0.34:
            coins = self.random.randint(2, 5)
            player["cash"] += coins
            return ActionResult(f"你在储物箱底翻出 {coins} 枚铜币。", self.snapshot())
        if roll < 0.68:
            player["goods_inventory"]["罐头"] = player["goods_inventory"].get("罐头", 0) + 1
            return ActionResult("你在旧木柜里翻出一听还没过期的罐头。", self.snapshot())
        intel = self._build_intel_packet(district, source="夹层旧纸条")
        self._apply_intel_packet(intel, to_player=True, promote_news=False, intensity=0.72)
        return ActionResult("你在夹层里翻出一张旧纸条，上面写着一条尚未证实的线索。", self.snapshot())

    def _review_ledger(self, district: str, payload: dict[str, Any]) -> ActionResult:
        player = self.state["player"]
        player["credit"] = min(100, player["credit"] + 1)
        intel = self._build_intel_packet(district, source="账本勾稽")
        self._apply_intel_packet(intel, to_player=True, promote_news=False, intensity=0.68)
        self.state["last_dialogue"] = {
            "title": "账桌前的新线索",
            "body": f"[b]你[/b]：把今天看到的价格、传闻和人情重新对了一遍。\n\n[i]{intel['line']}[/i]",
            "tone": "conversation",
        }
        return ActionResult("你把价格、情报和人情重新理顺了一遍。", self.snapshot())

    def _build_intel_packet(
        self,
        district: str,
        source: str,
        speaker: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        def stock_name_for_ticker(ticker: str) -> str:
            for row in self.state.get("stocks", []):
                if str(row.get("ticker", "")) == ticker:
                    return str(row.get("name", ticker))
            return ticker

        candidate = (
            self._upcoming_story_event_hint(district, speaker)
            or self._district_event_intel(district)
            or self._district_market_intel(district)
            or self._district_persona_intel(district, speaker)
        )
        if not candidate:
            candidate = {
                "intel_type": "Market_Intel" if district == "交易所" else "Event_Intel",
                "title": f"{district} 的临场消息",
                "line": f"{district} 这边的动静还没落地，但已经有人开始提前换仓和换站位。",
                "body": f"{source} 提醒你：这条消息更像对下一段时间的预判，而不是已经发生完的结果。",
                "tags": [district, "情报"],
                "due_minutes": int(self.state.get("clock_minutes", 0)) + 90,
            }
        intel_type = str(candidate.get("intel_type", "Event_Intel"))
        metadata = self._intel_metadata(intel_type, source, speaker)
        due_minutes = int(candidate.get("due_minutes", int(self.state.get("clock_minutes", 0)) + int(metadata["time_limit_minutes"])))
        time_limit = max(30, int(metadata["time_limit_minutes"]))
        authenticity = float(metadata["authenticity"])
        dissemination = int(metadata["dissemination"])
        if float(self._story_metrics_state().get("shadow_reputation", {}).get("ST", 1.0)) > 2.0 and self.random.random() < 0.3:
            authenticity = max(0.18, authenticity - 0.18)
            candidate["tags"] = [*list(candidate.get("tags", [])), "Uncertain"]
        line = str(candidate.get("line", "")).strip()
        body = str(candidate.get("body", "")).strip() or line
        stocks_delta = {str(key): float(value) for key, value in dict(candidate.get("stocks_delta", {})).items()}
        if intel_type == "Market_Intel" and not stocks_delta:
            market = self._district_market_intel(district) or {}
            stocks_delta = {str(key): float(value) for key, value in dict(market.get("stocks_delta", {})).items()}
        tags = list(dict.fromkeys([str(tag) for tag in candidate.get("tags", []) if str(tag).strip()]))
        if intel_type == "Market_Intel":
            tags.extend([tag for tag in ["市场内幕", "交易窗口"] if tag not in tags])
        elif intel_type == "Event_Intel":
            tags.extend([tag for tag in ["物理事件", "行动窗口"] if tag not in tags])
        else:
            tags.extend([tag for tag in ["角色秘辛", "威慑材料"] if tag not in tags])
        return {
            "id": f"intel_{self.state['day']}_{len(self.state.get('rumor_log', []))}_{self.random.randint(100, 999)}",
            "district": district,
            "source": source,
            "speaker_id": str(speaker.get("id", "")) if speaker else str(candidate.get("speaker_id", "")),
            "speaker_name": str(speaker.get("name", "")) if speaker else str(candidate.get("speaker_name", "")),
            "title": str(candidate.get("title", f"{district} 情报")),
            "line": line,
            "body": body,
            "tags": tags,
            "scope": "city" if dissemination >= 4 or intel_type == "Market_Intel" else "district",
            "goods_delta": {str(key): float(value) for key, value in dict(candidate.get("goods_delta", {})).items()},
            "stocks_delta": {stock_name_for_ticker(str(key)): float(value) for key, value in stocks_delta.items()},
            "macro_delta": {str(key): float(value) for key, value in dict(candidate.get("macro_delta", {})).items()},
            "family_delta": {str(key): float(value) for key, value in dict(candidate.get("family_delta", {})).items()},
            "topic_kind": {"Market_Intel": "asset", "Event_Intel": "panic", "Persona_Intel": "identity"}.get(intel_type, "public"),
            "intel_type": intel_type,
            "authenticity": round(max(0.12, min(0.98, authenticity)), 3),
            "dissemination": max(1, min(5, dissemination)),
            "time_limit_minutes": time_limit,
            "due_minutes": due_minutes,
            "uncertain": "Uncertain" in tags,
        }

    def _record_topic_from_packet(self, packet: dict[str, Any], intensity: float) -> dict[str, Any]:
        kind = self._topic_kind_from_packet(packet)
        target_bucket, target_name, _target_value = self._packet_primary_target(packet)
        topic_id = self._topic_signature_from_packet(packet, kind, target_name)
        label = self._topic_label_from_packet(packet, kind, target_name)
        tick = self._world_tick()
        topic_registry = list(self.state.get("topic_registry", []))
        topic = next((row for row in topic_registry if str(row.get("id", "")) == topic_id), None)
        source = str(packet.get("source", "")).strip() or "街头消息"
        summary = str(packet.get("line", "")).strip() or str(packet.get("body", "")).strip() or label
        speaker_id = str(packet.get("speaker_id", "")).strip()
        credibility = float(packet.get("authenticity", self._topic_credibility_hint(packet)))
        dissemination = int(packet.get("dissemination", 2))
        due_minutes = int(packet.get("due_minutes", int(self.state.get("clock_minutes", 0)) + int(packet.get("time_limit_minutes", 120))))
        time_limit = int(packet.get("time_limit_minutes", max(30, due_minutes - int(self.state.get("clock_minutes", 0)))))
        intel_type = str(packet.get("intel_type", "")).strip() or kind
        if topic is None:
            topic = {
                "id": topic_id,
                "signature": topic_id,
                "kind": kind,
                "intel_type": intel_type,
                "status": "emerging",
                "scope": str(packet.get("scope", "district")) or "district",
                "district": str(packet.get("district", "")),
                "label": label,
                "summary": summary,
                "stance": self._topic_stance_from_packet(packet),
                "target_bucket": target_bucket,
                "target_name": target_name,
                "origin": source,
                "latest_source": source,
                "heat": round(max(0.12, min(1.0, 0.28 + intensity * 0.38)), 3),
                "intensity": round(max(0.05, min(1.0, intensity)), 3),
                "credibility": round(max(0.1, min(0.98, credibility)), 3),
                "authenticity": round(max(0.1, min(0.98, credibility)), 3),
                "dissemination": dissemination,
                "novelty": round(max(0.15, min(1.0, 0.34 + intensity * 0.42)), 3),
                "suppression_level": 0.08,
                "mention_count": 1,
                "spread_count": max(1, dissemination),
                "source_count": 1,
                "sources": [source],
                "speaker_ids": [speaker_id] if speaker_id else [],
                "tags": list(dict.fromkeys([str(tag) for tag in packet.get("tags", [])])),
                "recent_lines": [summary],
                "goods_delta": {str(key): float(value) for key, value in dict(packet.get("goods_delta", {})).items()},
                "stocks_delta": {str(key): float(value) for key, value in dict(packet.get("stocks_delta", {})).items()},
                "family_delta": {str(key): float(value) for key, value in dict(packet.get("family_delta", {})).items()},
                "macro_delta": {str(key): float(value) for key, value in dict(packet.get("macro_delta", {})).items()},
                "first_seen_day": int(self.state.get("day", 1)),
                "first_seen_minute": int(self.state.get("clock_minutes", 0)),
                "last_seen_day": int(self.state.get("day", 1)),
                "last_seen_minute": int(self.state.get("clock_minutes", 0)),
                "first_seen_tick": tick,
                "last_seen_tick": tick,
                "time_limit_minutes": time_limit,
                "due_minutes": due_minutes,
                "uncertain": bool(packet.get("uncertain", False)),
            }
            topic_registry.append(topic)
        else:
            topic["status"] = "active"
            topic["scope"] = str(packet.get("scope", topic.get("scope", "district"))) or "district"
            topic["district"] = str(packet.get("district", topic.get("district", "")))
            topic["label"] = str(topic.get("label", "")) or label
            topic["summary"] = summary
            topic["stance"] = self._topic_stance_from_packet(packet)
            topic["latest_source"] = source
            topic["target_bucket"] = target_bucket or str(topic.get("target_bucket", ""))
            topic["target_name"] = target_name or str(topic.get("target_name", ""))
            topic["intel_type"] = intel_type or str(topic.get("intel_type", kind))
            topic["heat"] = round(max(0.06, min(1.0, float(topic.get("heat", 0.0)) * 0.68 + 0.26 * intensity + 0.04)), 3)
            topic["intensity"] = round(max(0.05, min(1.0, float(topic.get("intensity", 0.0)) * 0.55 + intensity * 0.75)), 3)
            topic["credibility"] = round(max(0.1, min(0.98, float(topic.get("credibility", 0.4)) * 0.74 + credibility * 0.26)), 3)
            topic["authenticity"] = topic["credibility"]
            topic["dissemination"] = max(int(topic.get("dissemination", 1)), dissemination)
            topic["novelty"] = round(max(0.04, min(1.0, float(topic.get("novelty", 0.0)) * 0.58 + 0.18 * intensity + 0.06)), 3)
            topic["suppression_level"] = round(max(0.0, min(1.0, float(topic.get("suppression_level", 0.08)) * 0.92)), 3)
            topic["mention_count"] = int(topic.get("mention_count", 0)) + 1
            topic["spread_count"] = int(topic.get("spread_count", 0)) + max(1, dissemination - 1)
            topic["time_limit_minutes"] = min(int(topic.get("time_limit_minutes", time_limit)), time_limit)
            topic["due_minutes"] = min(int(topic.get("due_minutes", due_minutes)), due_minutes)
            topic["uncertain"] = bool(topic.get("uncertain", False) or packet.get("uncertain", False))
            sources = [str(value) for value in topic.get("sources", []) if str(value).strip()]
            if source and source not in sources:
                sources.append(source)
            topic["sources"] = sources[:6]
            topic["source_count"] = len(topic["sources"])
            speaker_ids = [str(value) for value in topic.get("speaker_ids", []) if str(value).strip()]
            if speaker_id and speaker_id not in speaker_ids:
                speaker_ids.append(speaker_id)
            topic["speaker_ids"] = speaker_ids[:8]
            topic["tags"] = list(dict.fromkeys([*list(topic.get("tags", [])), *[str(tag) for tag in packet.get("tags", [])]]))[:12]
            topic["recent_lines"] = [summary, *[str(value) for value in topic.get("recent_lines", []) if str(value).strip() and str(value) != summary]][:4]
            topic["goods_delta"] = self._merge_delta_map(topic.get("goods_delta", {}), packet.get("goods_delta", {}))
            topic["stocks_delta"] = self._merge_delta_map(topic.get("stocks_delta", {}), packet.get("stocks_delta", {}))
            topic["family_delta"] = self._merge_delta_map(topic.get("family_delta", {}), packet.get("family_delta", {}))
            topic["macro_delta"] = self._merge_delta_map(topic.get("macro_delta", {}), packet.get("macro_delta", {}))
            topic["last_seen_day"] = int(self.state.get("day", 1))
            topic["last_seen_minute"] = int(self.state.get("clock_minutes", 0))
            topic["last_seen_tick"] = tick
        current_minutes = int(self.state.get("clock_minutes", 0))
        if int(topic.get("due_minutes", current_minutes + 1)) <= current_minutes:
            topic["status"] = "expired"
            topic["heat"] = round(max(0.02, float(topic.get("heat", 0.0)) * 0.45), 3)
        elif float(topic.get("heat", 0.0)) >= 0.62:
            topic["status"] = "active"
        elif int(topic.get("mention_count", 0)) >= 2:
            topic["status"] = "warming"
        else:
            topic["status"] = "emerging"
        topic_registry.sort(key=lambda row: (float(row.get("heat", 0.0)), float(row.get("credibility", 0.0))), reverse=True)
        self.state["topic_registry"] = topic_registry[:24]
        return copy.deepcopy(topic)

    def _topic_to_talk_topic(self, topic: dict[str, Any]) -> dict[str, Any]:
        district_name = str(topic.get("district", ""))
        scope = str(topic.get("scope", "district"))
        if scope == "city":
            npc_ids = [str(npc.get("id", "")) for npc in self.state.get("npcs", [])]
        elif district_name:
            npc_ids = [str(npc.get("id", "")) for npc in self.state.get("npcs", []) if str(npc.get("district", "")) == district_name]
        else:
            npc_ids = []
        kind = str(topic.get("kind", "rumor"))
        approaches = ["cautious", "friendly", "hardball"]
        if kind in {"finance", "asset"}:
            approaches = ["cautious", "hardball", "friendly"]
        elif kind in {"labor", "supply"}:
            approaches = ["friendly", "cautious", "hardball"]
        return {
            "id": str(topic.get("id", "")),
            "kind": kind,
            "intel_type": str(topic.get("intel_type", kind)),
            "district": district_name,
            "label": str(topic.get("label", "")),
            "summary": str(topic.get("summary", "")),
            "heat": round(float(topic.get("heat", 0.0)), 3),
            "credibility": round(float(topic.get("credibility", 0.0)), 3),
            "authenticity": round(float(topic.get("authenticity", topic.get("credibility", 0.0))), 3),
            "novelty": round(float(topic.get("novelty", 0.0)), 3),
            "dissemination": int(topic.get("dissemination", 1)),
            "time_limit_minutes": int(topic.get("time_limit_minutes", 0)),
            "due_minutes": int(topic.get("due_minutes", 0)),
            "spread_count": int(topic.get("spread_count", 0)),
            "status": str(topic.get("status", "")),
            "uncertain": bool(topic.get("uncertain", False)),
            "tags": list(topic.get("tags", [])),
            "npc_ids": npc_ids,
            "approaches": approaches,
            "impacts": {
                "goods": copy.deepcopy(topic.get("goods_delta", {})),
                "stocks": copy.deepcopy(topic.get("stocks_delta", {})),
                "macro": copy.deepcopy(topic.get("macro_delta", {})),
                "families": copy.deepcopy(topic.get("family_delta", {})),
            },
            "source_topic_id": str(topic.get("id", "")),
        }

    def _rebuild_talk_topics(self) -> None:
        topics: list[dict[str, Any]] = [copy.deepcopy(topic) for topic in self._active_public_topics(limit=6)]
        for district in self.state["districts"]:
            district_name = str(district.get("name", ""))
            signals = self.state["district_signals"].get(district_name, {})
            local_npcs = [npc for npc in self.state["npcs"] if npc.get("district") == district_name]
            topic_npc_ids = [npc["id"] for npc in local_npcs]
            if not district_name:
                continue
            trade_heat = float(signals.get("trade_heat", 0.0))
            labor_heat = float(signals.get("labor_heat", 0.0))
            gossip = float(signals.get("gossip", 0.0))
            fear = float(signals.get("fear", 0.0))
            liquidity = float(signals.get("liquidity", 0.0))
            if trade_heat > 0.35:
                good = max(self.state["goods"], key=lambda row: abs(float(self.state["market_pressure"]["goods"].get(row["name"], 0.0))))
                topics.append(
                    {
                        "id": f"topic_trade_{district_name}",
                        "kind": "trade",
                        "district": district_name,
                        "label": f"{district_name} 的 {good['name']} 价差",
                        "summary": f"{district_name} 正有人围着 {good['name']} 讨价还价，货和铜币都开始挪位置了。",
                        "heat": round(trade_heat, 3),
                        "credibility": 0.62,
                        "tags": ["交易", district_name, good["name"]],
                        "npc_ids": topic_npc_ids,
                        "approaches": ["cautious", "friendly", "hardball"],
                        "impacts": {"goods": {good["name"]: 0.06}, "stocks": {}, "macro": {"economy_heat": 1.0}, "families": {}},
                    }
                )
            if labor_heat > 0.28:
                topics.append(
                    {
                        "id": f"topic_job_{district_name}",
                        "kind": "labor",
                        "district": district_name,
                        "label": f"{district_name} 的工时和班次",
                        "summary": f"{district_name} 的班次开始发紧，工资、轮班和谁先扛不住都写在脸上了。",
                        "heat": round(labor_heat, 3),
                        "credibility": 0.66,
                        "tags": ["工时", district_name],
                        "npc_ids": [npc["id"] for npc in local_npcs if str(npc.get("role", "")) in {"工人", "临时工", "店主", "老板"}],
                        "approaches": ["friendly", "cautious", "hardball"],
                        "impacts": {"goods": {}, "stocks": {}, "macro": {"worker_unrest": 1.0 if district.get("state") in {"tense", "unrest"} else -0.5}, "families": {}},
                    }
                )
            if gossip > 0.22 or fear > 0.2:
                topics.append(
                    {
                        "id": f"topic_panic_{district_name}",
                        "kind": "panic",
                        "district": district_name,
                        "label": f"{district_name} 的传闻正在扩散",
                        "summary": f"{district_name} 这边开始有人提前打听坏消息，耳语变密，但还没到全镇皆知的程度。",
                        "heat": round(gossip + fear, 3),
                        "credibility": 0.48,
                        "tags": ["传闻", district_name],
                        "npc_ids": topic_npc_ids,
                        "approaches": ["cautious", "hardball", "friendly"],
                        "impacts": {
                            "goods": {"罐头": 0.04} if district_name != "工厂区" else {"煤": 0.05},
                            "stocks": {},
                            "macro": {"worker_unrest": 1.4, "media_sentiment": 0.8},
                            "families": {},
                        },
                    }
                )
            if liquidity > 0.22 or district_name == "交易所":
                hot_stock = max(self.state["stocks"], key=lambda row: abs(float(self.state["market_pressure"]["stocks"].get(row["name"], 0.0))))
                topics.append(
                    {
                        "id": f"topic_asset_{district_name}",
                        "kind": "asset",
                        "district": district_name,
                        "label": f"{hot_stock['ticker']} 的盘口异动",
                        "summary": f"{hot_stock['ticker']} 这边的挂单开始失衡，先动手的人更像在抢下一段的价差窗口。",
                        "heat": round(max(liquidity, trade_heat, 0.34), 3),
                        "credibility": 0.72,
                        "tags": ["盘口", hot_stock["ticker"], district_name],
                        "npc_ids": topic_npc_ids,
                        "approaches": ["cautious", "hardball", "friendly"],
                        "impacts": {"goods": {}, "stocks": {str(hot_stock["name"]): 0.05}, "macro": {"economy_heat": 0.6}, "families": {}},
                    }
                )
        for company in self.state.get("company_states", []):
            wage_pressure = float(company.get("wage_pressure", 0.0))
            financing_pressure = float(company.get("financing_pressure", 0.0))
            if max(wage_pressure, financing_pressure) < 45:
                continue
            company_npc_ids = [
                npc["id"]
                for npc in self.state["npcs"]
                if str(npc.get("company_id", "")) == str(company.get("id", "")) or (not str(npc.get("company_id", "")) and str(npc.get("district", "")) == str(company.get("district", "")))
            ]
            topics.append(
                {
                    "id": f"topic_company_{company.get('id', '')}",
                    "kind": "company",
                    "district": str(company.get("district", "")),
                    "label": f"{company.get('name', '公司')} 的账和人",
                    "summary": f"{company.get('name', '这家公司')} 眼下库存、工资和融资一起扯着，谁都不肯先认怂。",
                    "heat": round(max(wage_pressure, financing_pressure) / 100.0 + 0.18, 3),
                    "credibility": 0.74,
                    "tags": ["公司", str(company.get("name", "")), str(company.get("stock_name", ""))],
                    "npc_ids": company_npc_ids,
                    "approaches": ["friendly", "cautious", "hardball"],
                    "impacts": {
                        "goods": self._company_topic_goods_impact(company),
                        "stocks": {str(company.get("stock_name", "")): 0.05} if str(company.get("stock_name", "")) else {},
                        "macro": {"worker_unrest": 0.9 if wage_pressure >= financing_pressure else 0.2, "economy_heat": -0.4},
                        "families": {str(company.get("family_owner", "")): 0.05} if str(company.get("family_owner", "")) else {},
                    },
                }
            )
        for npc in self.state["npcs"]:
            topics.extend(self._npc_personal_topics(npc))
        topics.extend(self._institution_topics())
        topics.sort(key=lambda item: (float(item.get("heat", 0.0)), float(item.get("credibility", 0.0))), reverse=True)
        self.state["talk_topics"] = topics[:20]

    def _advance_realtime_clock(self) -> None:
        now = time.time()
        if self._route_choice_required():
            self.state["last_tick_at"] = now
            self.state["realtime_minute_buffer"] = 0.0
            return
        last_tick = float(self.state.get("last_tick_at", now))
        elapsed_seconds = max(0.0, now - last_tick)
        self.state["last_tick_at"] = now
        if elapsed_seconds <= 0.0:
            return
        elapsed_minutes = elapsed_seconds * REALTIME_MINUTES_PER_SECOND * self._realtime_speed_multiplier()
        self._apply_realtime_body_drain(elapsed_minutes)
        buffer = float(self.state.get("realtime_minute_buffer", 0.0)) + elapsed_minutes
        whole_minutes = int(buffer)
        self.state["realtime_minute_buffer"] = round(buffer - whole_minutes, 4)
        if whole_minutes > 0:
            self._advance_clock(whole_minutes)

    def _advance_clock(self, minutes: int) -> None:
        if minutes <= 0:
            return
        current = int(self.state.get("clock_minutes", 8 * 60))
        next_clock = min(23 * 60 + 45, current + minutes)
        self.state["clock_minutes"] = next_clock
        self._apply_clock_state()
        self._apply_story_timeline_between(current, next_clock)
        self._apply_collective_followups(minutes)
        self._apply_npc_schedule()

    def _apply_clock_state(self) -> None:
        minutes = int(self.state.get("clock_minutes", 8 * 60))
        weather = self._update_weather(minutes)
        segment = self._time_segment(minutes)
        segment_key = str(segment.get("key", "morning"))
        legacy_period = {
            "morning": "day",
            "noon": "day",
            "afternoon": "day",
            "evening": "night",
        }.get(segment_key, "day")
        base_light = {
            "morning": 0.96,
            "noon": 1.0,
            "afternoon": 0.78,
            "evening": 0.42,
        }.get(segment_key, 0.9)
        weather_dim = {
            "sunny": 0.0,
            "breezy": 0.01,
            "cloudy": 0.04,
            "overcast": 0.08,
            "rain": 0.11,
            "snow": 0.09,
            "dust": 0.14,
        }.get(str(weather.get("kind", "sunny")), 0.0)
        self.state["time_period"] = legacy_period
        self.state["time_segment"] = segment_key
        self.state["time_segment_label"] = str(segment.get("label", "早晨"))
        self.state["light_level"] = round(max(0.18, min(1.0, base_light - weather_dim)), 2)
        remaining = max(0, int(segment.get("end", 24 * 60)) - minutes)
        self.state["twilight_buffer_active"] = remaining <= 1

    def _apply_story_timeline_between(self, previous_minutes: int, current_minutes: int) -> None:
        day = int(self.state.get("day", 1))
        checkpoints: list[tuple[int, str]] = []
        if day == 1:
            route = str(self._ensure_player_financial_state().get("story_route", ""))
            if route == "平民路线":
                checkpoints = [
                    (8 * 60 + 5, "commoner_tutorial_hunger"),
                    (8 * 60 + 20, "commoner_tutorial_social"),
                    (8 * 60 + 50, "commoner_tutorial_eavesdrop"),
                    (9 * 60 + 15, "commoner_tutorial_reputation_trade"),
                    (17 * 60, "day1_privatization"),
                ]
            elif route == "精英路线":
                checkpoints = [
                    (8 * 60 + 5, "elite_tutorial_clock"),
                    (8 * 60 + 10, "elite_tutorial_dialogue"),
                    (8 * 60 + 30, "elite_tutorial_keyword"),
                    (9 * 60, "elite_tutorial_contract"),
                    (17 * 60, "day1_privatization"),
                ]
            else:
                checkpoints = [(17 * 60, "day1_privatization")]
        elif day == 2:
            checkpoints = [(16 * 60, "day2_arthur_assassination")]
        elif day == 3:
            checkpoints = [(14 * 60, "day3_tom_self_immolation"), (20 * 60, "day3_zero_uprising")]
        for threshold, event_id in checkpoints:
            if previous_minutes < threshold <= current_minutes and not self._story_event_fired(event_id):
                self._apply_story_timeline_event(event_id)

    def _story_event_schedule(self, event_id: str) -> tuple[int, int] | None:
        mapping = {
            "commoner_tutorial_hunger": (1, 8 * 60 + 5),
            "commoner_tutorial_social": (1, 8 * 60 + 20),
            "commoner_tutorial_eavesdrop": (1, 8 * 60 + 50),
            "commoner_tutorial_reputation_trade": (1, 9 * 60 + 15),
            "elite_tutorial_clock": (1, 8 * 60 + 5),
            "elite_tutorial_dialogue": (1, 8 * 60 + 10),
            "elite_tutorial_keyword": (1, 8 * 60 + 30),
            "elite_tutorial_contract": (1, 9 * 60),
            "day1_privatization": (1, 17 * 60),
            "day2_arthur_assassination": (2, 16 * 60),
            "day3_tom_self_immolation": (3, 14 * 60),
            "day3_zero_uprising": (3, 20 * 60),
        }
        return mapping.get(str(event_id))

    def _npc_brief_cadence_pulses(self, npc: dict[str, Any], observation: dict[str, Any], nearby_ids: set[str] | None = None) -> int:
        npc_id = str(npc.get("id", ""))
        nearby = npc_id in (nearby_ids or set())
        current_district = str(observation.get("current_district", "")) if isinstance(observation, dict) else ""
        npc_district = str(npc.get("district", ""))
        class_name = str(npc.get("class", ""))
        topic_heat = 0.0
        for topic in self._talk_topics_for_npc(npc_id, npc_district):
            scoped_heat = float(topic.get("heat", 0.0))
            topic_npc_ids = [str(value) for value in topic.get("npc_ids", [])]
            if topic_npc_ids and npc_id not in topic_npc_ids:
                scoped_heat *= 0.55
            if not nearby and npc_district != current_district and str(topic.get("kind", "")) in {"company", "institution"}:
                scoped_heat *= 0.25
            topic_heat = max(topic_heat, scoped_heat)
        profile = self.state.get("npc_truth_profile", {}).get(npc_id, {})
        economic_pressure = float(profile.get("economic_pressure", 0.0))
        memory = self._npc_player_memory(npc)
        recent_player_attention = int(memory.get("talk_count", 0)) > 0 and int(self.state.get("day", 1)) - int(memory.get("last_seen_day", 0)) <= 1
        district_signals = self.state.get("district_signals", {}).get(npc_district, {})
        district_heat = (
            float(district_signals.get("gossip", 0.0))
            + float(district_signals.get("fear", 0.0))
            + float(district_signals.get("trade_heat", 0.0))
            + float(district_signals.get("labor_heat", 0.0))
        )
        if class_name == "特殊角色":
            if nearby or npc_district == current_district or topic_heat >= 0.18 or district_heat >= 0.28 or recent_player_attention:
                return 1
            return 2
        if class_name == "关键角色" and (nearby or npc_district == current_district or topic_heat >= 0.18 or district_heat >= 0.28):
            if not nearby and npc_district != current_district and topic_heat < 0.3 and district_heat < 0.28 and not recent_player_attention:
                return 2
            return 1
        if nearby or topic_heat >= 0.55 or economic_pressure >= 0.42 or recent_player_attention:
            return 1
        if npc_district == current_district and district_heat >= 0.5 and topic_heat >= 0.24:
            return 1
        if class_name in {"关键角色", "中层"} and (topic_heat >= 0.18 or economic_pressure >= 0.18 or npc_district == current_district):
            return 2
        if topic_heat >= 0.28 or economic_pressure >= 0.22 or npc_district == current_district:
            return 2
        stable_bias = sum(ord(ch) for ch in npc_id) % 2
        return 3 if stable_bias == 0 else 2

    def _backfill_missing_npc_briefs(self, seen_ids: set[str], observation: dict[str, Any]) -> None:
        if not self.ark.enabled:
            return
        nearby_ids = self._nearby_npc_ids(observation)
        pulse_index = int(self.state.get("demo_metrics", {}).get("ai_pulses", 0))
        for npc in self.state.get("npcs", []):
            npc_id = str(npc.get("id", ""))
            if not npc_id or npc_id in seen_ids:
                continue
            cadence = self._npc_brief_cadence_pulses(npc, observation, nearby_ids)
            last_refresh = int(npc.get("last_llm_brief_pulse", -999))
            if last_refresh >= 0 and pulse_index - last_refresh < cadence:
                continue
            if cadence > 1 and npc_id not in nearby_ids:
                continue
            topic = self._resolve_talk_topic(npc, "", str(npc.get("district", "")))
            truth_profile = self._truth_metrics_for_topic(npc, topic, "cautious", "街头消息")
            use_image = cadence == 1 or npc_id in nearby_ids
            generated = self.ark.generate_npc_spin(
                {
                    "npc": copy.deepcopy(npc),
                    "llm_sections": self._npc_llm_sections(npc, topic),
                    "topic": copy.deepcopy(topic),
                    "active_topics": self._active_public_topics(limit=4, district_name=str(npc.get("district", ""))),
                    "active_norms": self._active_norms_view(limit=4, district_name=str(npc.get("district", ""))),
                    "active_collective_actions": self._active_collective_actions_view(limit=4, district_name=str(npc.get("district", ""))),
                    "truth_profile": truth_profile,
                    "district_signals": copy.deepcopy(self.state.get("district_signals", {}).get(str(npc.get("district", "")), {})),
                    "relationship_memory": {
                        "player_memory": copy.deepcopy(self._npc_player_memory(npc)),
                        "recent_events": copy.deepcopy(list(npc.get("relationship_memory", []))[:4]),
                        "conversation_history": self._dialogue_history_view(npc, limit=4),
                        "local_memory": self._local_memory_view(npc, topic_id=str(topic.get("id", "")), limit=5),
                    },
                    "recent_briefs": copy.deepcopy(self._entity_brief_history("npc_brief_history", npc_id)[:3]),
                    "scene_observation": self._llm_scene_observation(observation, include_image=use_image),
                }
            )
            if not generated:
                continue
            npc["last_llm_brief_pulse"] = pulse_index
            npc["llm_refresh_cadence"] = cadence
            self._apply_llm_npc_updates(
                [
                    {
                        "id": npc_id,
                        "line": str((generated.get("lines", [""]) or [""])[0]),
                        "stance": str(generated.get("stance", "")),
                        "market_tilt": str(generated.get("market_tilt", "")),
                        "topic_action": copy.deepcopy(generated.get("topic_action", {})),
                        "norm_action": copy.deepcopy(generated.get("norm_action", {})),
                        "collective_action": copy.deepcopy(generated.get("collective_action", {})),
                    }
                ]
            )

    def _push_memory(self, memory_tags: list[str], tag: str) -> list[str]:
        updated = list(memory_tags)
        updated.append(tag)
        return updated[-8:]

    @staticmethod
    def _now_label() -> str:
        return datetime.now().strftime("%H:%M:%S")
