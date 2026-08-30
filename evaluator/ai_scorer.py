"""
evaluator/ai_scorer.py - 批次 AI 四象限評分引擎 v1.0
變更簡述：實作 Option B 批次 AI 評分機制。針對單次爬取之所有案件，批次計算 X 軸 (自動化/輕鬆度: -10~+10)
          與 Y 軸 (淨報酬/資訊差: -10~+10)，並歸類至 Q1~Q4 象限。包含離線啟發式 (Heuristic) 備援評分演算法。
"""

import json
import re
import os
# Use AI_CORE middleware for LLM calls
from llm.chat import ask_ai

class AIScorer:
    def __init__(self, api_key=None, api_url=None, model="deepseek-chat"):
        # API key and url are kept for fallback but not used directly when AI_CORE is available
        self.api_key = api_key
        self.api_url = api_url or "https://api.deepseek.com/v1/chat/completions"
        self.model = model
        # Ensure AI_CORE is importable – assume repo root is in PYTHONPATH or add it dynamically
        if "AI_CORE" not in os.getenv("PYTHONPATH", ""):
            import sys, pathlib
            core_path = pathlib.Path(__file__).parents[4] / "AI_CORE"
            sys.path.append(str(core_path))

    def evaluate_batch(self, posts, keywords_config):
        """
        批次評估所有案件，傳回帶有 (X, Y) 座標與象限標籤的案件列表
        """
        if not posts:
            return []

        # 若未設定 API Key，自動切換至高精準度的離線啟發式評分引擎
        if not self.api_key or self.api_key == "YOUR_AI_API_KEY":
            return self._heuristic_evaluate_batch(posts, keywords_config)

        try:
            return self._llm_evaluate_batch(posts, keywords_config)
        except Exception as e:
            print(f"[警告] AI 批次評估異常，降級啟動離線啟發式評分: {e}")
            return self._heuristic_evaluate_batch(posts, keywords_config)

    def _heuristic_evaluate_batch(self, posts, keywords_config):
        """
        離線啟發式評分演算法：依據案件標題、來源與薪資結構計算 (X, Y)
        """
        evaluated_posts = []

        for post in posts:
            title = post.get("title", "")
            title_lower = title.lower()
            category = post.get("category", "")
            
            x_score = 0  # X 軸：自動化/輕鬆度 (-10 難/人工 ➔ +10 易/腳本/AI)
            y_score = 0  # Y 軸：淨報酬/資訊差 (-10 低薪 ➔ +10 高價/儀式感/急件)

            # === X 軸權重計算 (自動化程度) ===
            if category == "data_automation" or any(k in title_lower for k in ["爬蟲", "轉檔", "vba", "excel", "自動化", "整理資料", "建檔"]):
                x_score += 8  # 可用 Python 腳本秒級處理
            elif category == "ai_planning" or any(k in title_lower for k in ["ppt", "簡報", "排版", "ai", "chatgpt", "notion"]):
                x_score += 6  # 可用 AI 工具 (Gamma/Claude) 高效產出
            
            if any(k in title_lower for k in ["到場", "現場", "面交", "拍照", "體力"]):
                x_score -= 6  # 需實體到場，難度提升

            # === Y 軸權重計算 (淨報酬/資訊差) ===
            if category == "one_time_ritual" or any(k in title_lower for k in ["婚禮", "求婚", "約會", "紀念日", "告白", "驚喜"]):
                y_score += 9  # 一次性儀式感，情緒付費，極高資訊差
            elif category == "japanese_niche" or any(k in title_lower for k in ["急", "急件", "特急", "代打電話", "商務"]):
                y_score += 7  # 燃眉之急，無法比價
            elif any(k in title_lower for k in ["論件計酬", "每件", "專案"]):
                y_score += 5  # 按件計酬，具溢價空間

            # 邊界約束 [-10, 10]
            x_score = max(-10, min(10, x_score))
            y_score = max(-10, min(10, y_score))

            # 決定四象限
            quadrant = self._determine_quadrant(x_score, y_score)

            post_copy = dict(post)
            post_copy["x_score"] = x_score
            post_copy["y_score"] = y_score
            post_copy["quadrant"] = quadrant
            evaluated_posts.append(post_copy)

        return evaluated_posts

    def _determine_quadrant(self, x, y):
        """判斷四象限"""
        if x > 0 and y > 0:
            return "Q1"  # ★ Q1: 高報酬 / 高自動化 (黃金肥羊區)
        elif x <= 0 and y > 0:
            return "Q2"  # Q2: 高報酬 / 高難度 (硬幹備選區)
        elif x > 0 and y <= 0:
            return "Q4"  # Q4: 低報酬 / 高自動化 (微型雞肋區)
        else:
            return "Q3"  # Q3: 低報酬 / 低難度 (垃圾絕對拋棄區)

    def _llm_evaluate_batch(self, posts, keywords_config):
        """Use AI_CORE's ask_ai middleware to evaluate the batch.
        The function builds a prompt identical to the previous implementation
        and lets AI_CORE handle provider routing, token usage and error handling.
        """
        prompt = (
            "你是一個副業接案與資訊差評估專家。請評估以下案件列表，並給予每筆案件 (X, Y) 座標分數 (-10 到 +10)：\n"
            "X軸 (自動化/輕鬆度): -10(需現場人工體力) 到 +10(可用Python/AI秒級處理)\n"
            "Y軸 (淨報酬/資訊差): -10(低薪/被嚴格比價) 到 +10(婚禮/求婚儀式感/特急/無比價空間)\n\n"
            "請嚴格回傳 JSON 陣列格式，如：[{\"id\": 0, \"x\": 8, \"y\": 9}, ...]\n\n"
            f"案件列表:\n{json.dumps([{'id': i, 'title': p['title']} for i, p in enumerate(posts)], ensure_ascii=False)}"
        )

        # ask_ai returns (content, usage). We only need content.
        try:
            content, _ = ask_ai(prompt, model=self.model)
        except Exception as e:
            # If AI_CORE fails, fallback to heuristic evaluation.
            print(f"[警告] AI_CORE ask_ai 失敗，使用離線啟發式: {e}")
            return self._heuristic_evaluate_batch(posts, keywords_config)

        # Parse the JSON returned by the LLM.
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            raise ValueError("LLM 回傳非合法 JSON 格式")
        scores = json.loads(json_match.group(0))
        score_map = {item["id"]: (item["x"], item["y"]) for item in scores}

        evaluated_posts = []
        for i, post in enumerate(posts):
            x_score, y_score = score_map.get(i, (0, 0))
            post_copy = dict(post)
            post_copy["x_score"] = x_score
            post_copy["y_score"] = y_score
            post_copy["quadrant"] = self._determine_quadrant(x_score, y_score)
            evaluated_posts.append(post_copy)
        return evaluated_posts
