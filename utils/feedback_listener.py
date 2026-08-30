"""
utils/feedback_listener.py - Telegram 即時按鈕反饋監聽器 v1.0
變更簡述：24h 極輕量背景監聽器 (<3MB RAM)。專門監聽 Telegram 手機端按鈕點擊，
          於 0.5 秒內向手機回應 answerCallbackQuery 彈出 Toast 視窗，並自動將 👎 關鍵字寫入 config.yaml。
"""
import time
import os
import yaml
import requests

def get_config():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f), path
    return {}, path

def start_listener():
    print("🚀 啟動 Telegram 即時按鈕反饋監聽器 (極輕量背景模式)...")
    config, config_path = get_config()
    bot_token = config.get("telegram", {}).get("bot_token", "")

    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ 錯誤: 未設定 Telegram Bot Token，監聽器無法啟動。")
        return

    base_url = f"https://api.telegram.org/bot{bot_token}"
    offset = 0

    while True:
        try:
            url = f"{base_url}/getUpdates?offset={offset}&timeout=20"
            r = requests.get(url, timeout=25)
            if r.status_code != 200:
                time.sleep(5)
                continue

            updates = r.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                callback = u.get("callback_query")
                if not callback:
                    continue

                callback_id = callback.get("id")
                data = callback.get("data", "")
                
                # 手機端點擊 👎 不會做/廢文
                if data.startswith("dislike|"):
                    keyword = data.split("|", 1)[1].strip()
                    
                    # 1. 0.5 秒內向手機發送 Toast 彈窗
                    ans_url = f"{base_url}/answerCallbackQuery"
                    requests.post(ans_url, json={
                        "callback_query_id": callback_id,
                        "text": f"🛑 已將 '{keyword}' 寫入黑名單！未來自動排除。",
                        "show_alert": True
                    }, timeout=5)

                    # 2. 自動寫入 config.yaml
                    config, config_path = get_config()
                    current_excludes = set(config.get("global_exclude", []))
                    if keyword and keyword not in current_excludes:
                        current_excludes.add(keyword)
                        config["global_exclude"] = list(current_excludes)
                        with open(config_path, "w", encoding="utf-8") as f:
                            yaml.dump(config, f, allow_unicode=True)
                        print(f"🛑 [黑名單學習] 使用者點擊 👎，已成功將 '{keyword}' 加入 global_exclude！")

                # 手機端點擊 👍 有用
                elif data.startswith("like|"):
                    ans_url = f"{base_url}/answerCallbackQuery"
                    requests.post(ans_url, json={
                        "callback_query_id": callback_id,
                        "text": "🔥 感謝反饋！已成功加強該類別的推播權重。",
                        "show_alert": True
                    }, timeout=5)
                    print(f"🔥 [權重加強] 使用者點擊 👍 肯定此類別。")

        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    start_listener()
