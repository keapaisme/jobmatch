import sys
import requests
import yaml
import os
import json

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None, config_path=None):
        if bot_token and chat_id:
            self.bot_token = bot_token
            self.chat_id = chat_id
        else:
            # 1️⃣ 先嘗試從環境變數取得（.env 會在 main.py 中載入）
            env_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            env_chat = os.getenv("TELEGRAM_CHAT_ID", "")
            if env_token and env_chat:
                self.bot_token = env_token
                self.chat_id = env_chat
                # 從環境變數已取得，直接跳過讀 config.yaml
                self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
                return
            # 2️⃣ 若環境變數未設定，回退讀取 config.yaml
            if config_path is None:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            tg = cfg.get("telegram", {})
            self.bot_token = tg.get("bot_token", "")
            self.chat_id = tg.get("chat_id", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text, reply_markup=None):
        """發送訊息到 Telegram"""
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            print(f"[模擬發送] (尚未設定 Token):\n{text}\n")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print("[成功] 訊息已推播至 Telegram")
                return True
            else:
                print(f"[錯誤] Telegram 推播失敗: {response.text}")
                return False
        except Exception as e:
            print(f"[錯誤] Telegram 發生異常: {e}")
            return False

    def delete_message(self, message_id: int) -> bool:
        """刪除 Telegram 聊天畫面中的特定訊息 v1.7"""
        if not self.bot_token or not self.chat_id:
            return False
        url = f"{self.base_url}/deleteMessage"
        try:
            r = requests.post(url, json={"chat_id": self.chat_id, "message_id": message_id}, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def send_opportunity(self, source, title=None, url=None, category=None, quadrant=None, x_score=None, y_score=None):
        """
        發送極簡格式四象限通知 v1.9
        格式：
        [標題] ([X座標], [Y座標]) ─ [詳細]
        👎 不要 | 👍 保留
        """
        if isinstance(source, dict) and isinstance(title, dict):
            post = source
            eval_result = title
            title_text = post.get("title", "")
            url_text = post.get("url", "#")
            x_val = eval_result.get("x_score", 0)
            y_val = eval_result.get("y_score", 0)
            cat = eval_result.get("category", "AI_PLANNING")
        else:
            title_text = title
            url_text = url
            x_val = x_score
            y_val = y_score
            cat = category

        # 座標顯示正負符號
        x_str = f"+{x_val}" if x_val >= 0 else str(x_val)
        y_str = f"+{y_val}" if y_val >= 0 else str(y_val)

        msg = f"{title_text} ({x_str}, {y_str}) ─ <a href='{url_text}'>詳細</a>"
        return self.send_message(msg)

    def send_heartbeat(self, message="🫧 巡邏正常 (無新案件)"):
        """發送零機會時的心跳回報訊號 (帶有極簡狀態文字，確保觸發手機推播) v1.4"""
        return self.send_message(message)

    def process_user_feedbacks(self, config_path="config.yaml", gcs_bucket=None):
        """
        批次處理使用者反饋 v1.8 (GCS 佇列模式)
        Cloud Run 守護程式負責即時刪除訊息並將反饋寫入 GCS feedback_queue.jsonl
        main.py 巡邏時呼叫此函式，從 GCS 撈回批次處理並發送學習報告
        """
        disliked_keywords = []
        liked_categories  = []

        # --- 優先從 GCS 佇列讀取 (Cloud Run 已部署時) ---
        if gcs_bucket:
            try:
                import subprocess
                cmd = ["gcloud", "storage", "cat", f"gs://{gcs_bucket}/feedback_queue.jsonl"]
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
                
                if res.returncode == 0 and res.stdout.strip():
                    lines = res.stdout.strip().splitlines()
                    for line in lines:
                        try:
                            entry = json.loads(line)
                            if entry.get("action") == "dislike":
                                kw = entry.get("keyword", "").strip()
                                if kw and kw not in disliked_keywords:
                                    disliked_keywords.append(kw)
                            elif entry.get("action") == "like":
                                cat = entry.get("category", "").strip()
                                if cat and cat not in liked_categories:
                                    liked_categories.append(cat)
                            elif entry.get("action") == "dev_request":
                                # 收到手機端遠端開發請求，在背景啟動 Mac 的臨時通道
                                dev_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "dev_tunnel.py")
                                subprocess.Popen([sys.executable, dev_script])
                                print("📡 [遠端開發] 已於 Mac 背景啟動臨時 SSH 通道腳本。")
                        except Exception:
                            pass
                    
                    if lines:
                        # 建立臨時空檔案並上傳以清空佇列
                        temp_path = "/tmp/empty_feedback.jsonl"
                        with open(temp_path, "w", encoding="utf-8") as f:
                            f.write("")
                        clear_cmd = ["gcloud", "storage", "cp", temp_path, f"gs://{gcs_bucket}/feedback_queue.jsonl"]
                        subprocess.run(clear_cmd, capture_output=True)
                        print(f"📥 [GCS 佇列] 成功撈回 {len(lines)} 筆反饋，GCS 佇列已清空")
            except Exception as e:
                print(f"[GCS 佇列] 讀取失敗，略過: {e}")

        # --- Fallback：GCS 未部署時，直接用 getUpdates (舊模式) ---
        else:
            try:
                r = requests.get(f"{self.base_url}/getUpdates", timeout=8)
                if r.status_code != 200:
                    return
                updates = r.json().get("result", [])
                if not updates:
                    return
                max_update_id = 0
                for u in updates:
                    max_update_id = max(max_update_id, u.get("update_id", 0))
                    cb = u.get("callback_query")
                    if not cb:
                        continue
                    try:
                        requests.post(f"{self.base_url}/answerCallbackQuery",
                                      json={"callback_query_id": cb["id"]}, timeout=3)
                    except Exception:
                        pass
                    data = cb.get("data", "")
                    if data.startswith("dislike|"):
                        kw = data.split("|", 1)[1].strip()
                        if kw and kw not in disliked_keywords:
                            disliked_keywords.append(kw)
                    elif data.startswith("like|"):
                        cat = data.split("|", 1)[1].strip()
                        if cat and cat not in liked_categories:
                            liked_categories.append(cat)
                if max_update_id > 0:
                    try:
                        requests.get(f"{self.base_url}/getUpdates?offset={max_update_id + 1}", timeout=5)
                    except Exception:
                        pass
            except Exception:
                return

        # --- 共用：寫入黑名單 + 發送學習報告 ---
        new_added = []
        if disliked_keywords and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            current_excludes = set(cfg.get("global_exclude", []))
            for kw in disliked_keywords:
                if kw not in current_excludes:
                    current_excludes.add(kw)
                    new_added.append(kw)
            if new_added:
                cfg["global_exclude"] = list(current_excludes)
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.dump(cfg, f, allow_unicode=True)

        if new_added or liked_categories:
            dislike_str = ", ".join(new_added)
            like_str = ", ".join(liked_categories)
            summary_msg = "📝 <b>【反饋學習報告完成】</b>\n\n"
            if new_added:
                summary_msg += f"🚫 <b>新增黑名單 ({len(new_added)}個)：</b> {dislike_str}\n"
            if liked_categories:
                summary_msg += f"🔥 <b>權重已加強 ({len(liked_categories)}個)：</b> {like_str}\n"
            summary_msg += "\n💡 <i>系統已於本機自動更新黑名單，未來不再推播類似案件。</i>\n"
            dash_url = os.getenv("GITHUB_PAGES_URL", "https://keapaisme.github.io/jobmatch")
            summary_msg += f"📊 點此查看 <a href='{dash_url}/dashboard.html'>數據可視化</a>"
            
            self.send_message(summary_msg)
            print(f"📝 [批次反饋學習] 新增黑名單 {new_added}，加強權重 {liked_categories}")
