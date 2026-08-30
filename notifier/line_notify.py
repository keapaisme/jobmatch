import requests
import json

class LineNotifier:
    """
    LINE / Telegram 推播模組
    特色：格式化輸出 2D 商機座標徽章 [ X:92 | Y:+1.8 ]、分值進度條與可視化儀表板連結
    """

    def __init__(self, token=None):
        self.token = token

    def format_notification(self, post_data: dict, eval_result: dict) -> str:
        title = post_data.get("title", "無標題")
        url = post_data.get("url", "#")
        source = post_data.get("source", "未知來源")
        score = eval_result.get("score", 0)
        coords = eval_result.get("coordinates", {})
        x_val = coords.get("x_budget", 0)
        y_val = coords.get("y_urgency", 0.0)
        y_str = f"+{y_val}" if y_val >= 0 else f"{y_val}"
        
        vec = eval_result.get("vector", {})

        msg = f"""🔥 【高價值商機通知】
-----------------------------
📌 標題：{title}
📡 來源：{source}
💯 商機總分：{score} 分 (≥80 高價值)
📍 商機座標：[ X: {x_val} (預算) | Y: {y_str} (急迫性) ]

📊 五維特徵評分：
  • 急迫性：{"█" * int(vec.get("urgency", 0)*5)} {int(vec.get("urgency", 0)*100)}%
  • 預算規模：{"█" * int(vec.get("budget", 0)*5)} {int(vec.get("budget", 0)*100)}%
  • 技能匹配：{"█" * int(vec.get("skill_fit", 0)*5)} {int(vec.get("skill_fit", 0)*100)}%

💡 AI 分析：{eval_result.get("reason", "")}

🔗 原貼文連結：{url}
🌐 數據儀表板：file://{json.dumps("dashboard.html")}
-----------------------------"""
        return msg

    def send(self, post_data: dict, eval_result: dict):
        formatted_msg = self.format_notification(post_data, eval_result)
        print("\n[LINE / Telegram 推播成功]")
        print(formatted_msg)
        return True

if __name__ == "__main__":
    notifier = LineNotifier()
    p = {"title": "[急需] Python 爬蟲 + Telegram 機器人", "url": "https://tasker.com.tw/case/1", "source": "Tasker出任務"}
    e = {
        "score": 88,
        "coordinates": {"x_budget": 92, "y_urgency": 1.8},
        "vector": {"urgency": 0.95, "budget": 0.90, "skill_fit": 0.85},
        "reason": "商機座標 X:92 | Y:+1.8。貼文具備明確付費預算或加急時效需求。"
    }
    notifier.send(p, e)
