"""
evaluator/keyword_manager.py - 錦標賽金字塔與動態演化引擎 v1.1
變更簡述：實作 14 天冷啟動保護期 (保護長尾高價詞)，目標收斂至 80 個【黃金戰鬥關鍵字】。
          當超越容量時，發動 44% 末位錦標賽淘汰機制（免疫保護期內新詞）。
"""

import json
import os
import time

STATE_FILE = "keywords_state.json"
DEFAULT_GOLDEN_CAPACITY = 80
DEFAULT_PURGE_RATIO = 0.44  # 44% 錦標賽淘汰率
FOURTEEN_DAYS_SECONDS = 14 * 24 * 3600
SEVEN_DAYS_SECONDS = 7 * 24 * 3600

class KeywordManager:
    def __init__(self, config_keywords, eval_config=None):
        self.config_keywords = config_keywords
        self.eval_config = eval_config or {}
        self.golden_capacity = self.eval_config.get("golden_capacity", DEFAULT_GOLDEN_CAPACITY)
        self.purge_ratio = self.eval_config.get("purge_ratio", DEFAULT_PURGE_RATIO)
        self.cold_start_seconds = self.eval_config.get("cold_start_days", 14) * 24 * 3600
        self.state = self._load_state()

    def _load_state(self):
        """讀取動態關鍵字狀態，若無則初始化"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[警告] 讀取關鍵字狀態失敗，重新初始化: {e}")

        # 初始化狀態
        initial_state = {
            "last_weekly_renewal": time.time(),
            "keyword_scores": {}
        }
        # 載入預設關鍵字 (依據類別給予差別化基礎分數，高價值類別保護不被初始化淘汰)
        now = time.time()
        category_initial_scores = {
            "one_time_ritual": 30,
            "data_automation": 25,
            "ai_planning": 20,
            "japanese_niche": 18
        }

        for cat, rules in self.config_keywords.items():
            base_score = category_initial_scores.get(cat, 15)
            for kw in rules.get("include", []):
                initial_state["keyword_scores"][kw] = {
                    "score": base_score,
                    "category": cat,
                    "created_at": now
                }

        self._save_state(initial_state)
        return initial_state

    def _save_state(self, state=None):
        """儲存狀態至 JSON"""
        state = state or self.state
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def record_result(self, keyword, quadrant):
        """依據案件落點象限增減關鍵字積分"""
        scores = self.state["keyword_scores"]
        now = time.time()
        if keyword not in scores:
            scores[keyword] = {"score": 15, "category": "general", "created_at": now}

        current_score = scores[keyword]["score"]

        # 積分演化規則
        if quadrant == "Q1":
            delta = 3   # ★ Q1 黃金肥羊區：大加分
        elif quadrant in ["Q2", "Q4"]:
            delta = 1   # Q2/Q4 有價值或微型區：小加分
        else:  # Q3
            delta = -2  # Q3 垃圾區：扣分

        scores[keyword]["score"] = current_score + delta
        self._save_state()

    def run_evolution_cycle(self):
        """執行動態演化週期：每週趨勢注入 + 14天保護期下發動 44% 錦標賽末位淘汰"""
        scores = self.state["keyword_scores"]
        now = time.time()

        # 1. 檢查每週趨勢重置 (Weekly Renewal)
        last_renewal = self.state.get("last_weekly_renewal", 0)
        if now - last_renewal >= SEVEN_DAYS_SECONDS:
            print("✨ 觸發每週趨勢重置 (Weekly Renewal)...")
            self._apply_weekly_renewal()
            self.state["last_weekly_renewal"] = now
            self._save_state()

        # 2. 檢查容量 (超越黃金容量 80 時，發動 44% 錦標賽末位淘汰)
        if len(scores) > self.golden_capacity:
            print(f"🏆 關鍵字池達到 {len(scores)} 個 (超越黃金容量 {self.golden_capacity})，發動 44% 錦標賽末位淘汰...")
            self._purge_tournament_bottom()

    def _purge_tournament_bottom(self):
        """實作 44% 錦標賽淘汰，免除 14 天內長尾保護期關鍵字"""
        scores = self.state["keyword_scores"]
        now = time.time()

        eligible_items = []
        protected_count = 0

        for kw, data in scores.items():
            created_at = data.get("created_at", 0)
            if (now - created_at) < self.cold_start_seconds:
                protected_count += 1
            else:
                eligible_items.append((kw, data))

        if not eligible_items:
            print(f"🛡️ 所有關鍵字都在 14 天保護期內 ({protected_count} 個)，本次跳過淘汰。")
            return

        eligible_items.sort(key=lambda item: item[1]["score"])
        purge_count = max(1, int(len(eligible_items) * self.purge_ratio))
        purged_items = eligible_items[:purge_count]

        for kw, data in purged_items:
            print(f"🗑️ [錦標賽淘汰 44%] 關鍵字: '{kw}' (積分: {data['score']})")
            del scores[kw]

        print(f"✅ 錦標賽完成：淘汰 {len(purged_items)} 個劣質詞，保護中 {protected_count} 個長尾詞，當前剩餘 {len(scores)} 個關鍵字。")
        self._save_state()

    def _apply_weekly_renewal(self):
        """每週注入新鮮趨勢關鍵字 (避免同溫層陷阱)"""
        now = time.time()
        trend_candidates = [
            ("n8n", "data_automation"),
            ("Claude3.5", "ai_planning"),
            ("求婚佈置", "one_time_ritual"),
            ("自動化流程", "data_automation"),
            ("日本代溝通", "japanese_niche")
        ]

        scores = self.state["keyword_scores"]
        for kw, cat in trend_candidates:
            if kw not in scores:
                scores[kw] = {
                    "score": 18,
                    "category": cat,
                    "created_at": now
                }
                print(f"✨ [每週趨勢注入] 新關鍵字: '{kw}' (享有 14 天冷啟動保護期)")

        self._save_state()

    def get_active_keywords(self):
        """取得當前有效關鍵字清單"""
        return list(self.state["keyword_scores"].keys())
