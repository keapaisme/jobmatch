import yaml
from dotenv import load_dotenv
import time
import os
import re
import argparse
from scrapers.ptt import PTTScraper
from scrapers.job104 import Job104Scraper
from scrapers.xiao_ji import XiaoJiScraper
from scrapers.tasker import TaskerScraper
from scrapers.dcard import DcardScraper
from notifier.telegram_bot import TelegramNotifier
from notifier.line_notify import LineNotifier
from evaluator.ai_scorer import AIScorer
from evaluator.keyword_manager import KeywordManager
from storage.db import DatabaseManager
from storage.export_dashboard import export_dashboard_data

load_dotenv('.env')

SEEN_FILE = "seen_urls.txt"

def load_seen_urls():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_seen_url(url):
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CATEGORY_PRIORITY = {
    "one_time_ritual": 0,
    "data_automation": 1,
    "ai_planning":     2,
    "japanese_niche":  3,
}

CATEGORY_EMOJI = {
    "one_time_ritual": "💍",
    "data_automation": "⚡",
    "ai_planning":     "🤖",
    "japanese_niche":  "🇯🇵",
}

def match_keywords(post, config):
    title = post["title"]
    title_lower = title.lower()
    global_exclude = config.get("global_exclude", [])
    keywords_dict = config.get("keywords", {})
    min_wage = config.get("min_hourly_wage", 300)

    if any(ex.lower() in title_lower for ex in global_exclude):
        return None

    hourly_match = re.search(r'(?:時薪|\$/?hr|nt\$?\s*\d+/hr)\s*[:：]?\s*(\d+)', title_lower)
    if hourly_match:
        wage = int(hourly_match.group(1))
        if wage < min_wage:
            return None

    if "104" in post["source"]:
        salary_type = post.get("salary_type", "")
        salary_low = post.get("salary_low", 0)
        if salary_type == "01":
            return None
        elif salary_type == "00":
            if salary_low > 0 and salary_low < min_wage:
                return None
        elif salary_type == "02":
            if salary_low > 0 and salary_low < (min_wage * 8):
                return None

    matched_results = []
    for category, rules in keywords_dict.items():
        includes = rules.get("include", [])
        excludes = rules.get("exclude", [])
        if any(ex.lower() in title_lower for ex in excludes):
            continue
        if any(inc.lower() in title_lower for inc in includes):
            priority = CATEGORY_PRIORITY.get(category, 99)
            matched_results.append((priority, category))

    if matched_results:
        matched_results.sort(key=lambda x: x[0])
        return matched_results[0][1]
    return None


def _quadrant_to_coords(x_score, y_score):
    """
    將四象限 XY 座標 (-10~+10) 映射至 Dashboard 座標系:
    - dashboard X 軸: 商業價值/預算 (0~100)
    - dashboard Y 軸: 急迫性時效 (-2.0~+2.0)
    """
    budget_x = int(round((x_score + 10) / 20 * 100))       # -10~+10 → 0~100
    urgency_y = round(y_score / 10 * 2.0, 1)               # -10~+10 → -2.0~+2.0
    # 合成 Opportunity Score (0~100)
    opp_score = int(round((x_score + 10 + y_score + 10) / 40 * 100))
    return budget_x, urgency_y, opp_score


def run_once():
    print("🚀 啟動副業訊息差監控系統...")
    config = load_config()

    telegram = TelegramNotifier()
    # Initialize optional notifiers
    line_cfg = config.get("line", {})
    line_notifier = LineNotifier(token=line_cfg.get("token")) if line_cfg.get("token") else None
    im_cfg = config.get("imessage", {})
    im_notifier = None
    if im_cfg.get("recipient"):
        # Import lazily to avoid issues on non‑mac platforms
        from notifier.imessage_notifier import IMessageNotifier
        im_notifier = IMessageNotifier(recipient=im_cfg.get("recipient"))

    eval_config = config.get("evaluator", {})
    ai_api_key = os.getenv("AI_API_KEY") or eval_config.get("ai_api_key")
    ai_scorer = AIScorer(
        api_key=ai_api_key,
        api_url=eval_config.get("ai_api_url"),
        model=eval_config.get("model", "deepseek-chat")
    )
    keyword_manager = KeywordManager(config.get("keywords", {}), eval_config)
    db = DatabaseManager()

    ptt_scraper    = PTTScraper(config["targets"]["ptt"]["boards"])
    job104_scraper  = Job104Scraper(config["targets"]["job104"]["keywords"])
    xiaoji_scraper  = XiaoJiScraper(config["targets"]["xiao_ji"]["categories"])
    tasker_scraper  = TaskerScraper()
    dcard_scraper   = DcardScraper(config["targets"]["dcard"]["forums"])

    seen_urls = load_seen_urls()
    print("✅ 系統初始化完成，背景抓取中...")

    # 1. 抓取資料
    posts = []
    posts.extend(ptt_scraper.fetch_latest_posts())
    posts.extend(job104_scraper.fetch_latest_posts())
    posts.extend(xiaoji_scraper.fetch_latest_posts())
    posts.extend(tasker_scraper.fetch_latest_posts())
    posts.extend(dcard_scraper.fetch_latest_posts())

    # 2. 初步關鍵字篩選 + SQLite 三重防重去重
    candidate_posts = []
    seen_candidate_urls = set()
    for post in posts:
        url = post.get("url", "")
        post_id = post.get("id") or url
        content = post.get("content", post.get("title", ""))

        # 舊有 seen_urls.txt 去重
        if url in seen_urls or url in seen_candidate_urls:
            continue

        # 新 SQLite MD5 指紋去重
        if db.is_seen(post_id, url, content):
            continue

        matched_category = match_keywords(post, config)
        if matched_category:
            seen_candidate_urls.add(url)
            post_copy = dict(post)
            post_copy["category"] = matched_category
            candidate_posts.append(post_copy)

    # 3. 批次 AI 四象限評分
    evaluated_posts = ai_scorer.evaluate_batch(candidate_posts, config.get("keywords", {}))

    # 4. 依象限篩選、存入資料庫、推播
    found_count = 0
    allowed_quadrants = eval_config.get("allowed_quadrants", ["Q1", "Q2"])

    for post in evaluated_posts:
        url = post["url"]
        post_id = post.get("id") or url
        content = post.get("content", post.get("title", ""))
        category = post["category"]
        quadrant = post.get("quadrant", "Q3")
        x_score = post.get("x_score", 0)
        y_score = post.get("y_score", 0)

        # 記錄防重
        seen_urls.add(url)
        save_seen_url(url)
        db.mark_seen(post_id, url, content, post.get("source", ""))
        keyword_manager.record_result(category, quadrant)

        # 映射至 Dashboard 座標
        dash_x, dash_y, opp_score = _quadrant_to_coords(x_score, y_score)

        vector = {
            "urgency": round((y_score + 10) / 20, 2),
            "budget": round((x_score + 10) / 20, 2),
            "skill_fit": 0.8 if quadrant in ["Q1", "Q4"] else 0.5,
            "low_competition": 0.75,
            "freshness": 0.95
        }

        # 寫入 SQLite 資料庫
        db.save_opportunity(
            post_id=post_id,
            title=post["title"],
            url=url,
            source=post.get("source", ""),
            score=opp_score,
            x_score=dash_x,
            y_score=dash_y,
            vector_json=str(vector),
            ai_reason=f"四象限 {quadrant} | X:{x_score:+d}(自動化) Y:{y_score:+d}(報酬) | 商機座標 Dash-X:{dash_x} Dash-Y:{dash_y:+.1f}"
        )

        # 僅推播符合允許象限的案件
        if quadrant in allowed_quadrants:
            found_count += 1
            emoji = CATEGORY_EMOJI.get(category, "🎯")
            display_category = f"{emoji} {category.upper()}"
            print(f"🔥 [{quadrant}] X:{x_score:+d} Y:{y_score:+d} | {display_category} -> {post['title']}")

            eval_result = {
                "score": opp_score,
                "x_score": x_score,
                "y_score": y_score,
                "category": category,
                "coordinates": {"x_budget": dash_x, "y_urgency": dash_y},
                "vector": vector,
                "reason": f"四象限 {quadrant}：X:{x_score:+d}(自動化程度) / Y:{y_score:+d}(報酬/資訊差)"
            }
            telegram.send_opportunity(post, eval_result)
            # Optional LINE notification
            if line_notifier:
                try:
                    line_notifier.send(post, eval_result)
                except Exception as e:
                    print(f"[LINE] 發送失敗: {e}")
            # Optional iMessage notification
            if im_notifier:
                try:
                    im_msg = f"{post.get('title', '')} (X:{x_score}, Y:{y_score}) {post.get('url', '')}"
                    im_notifier.send_message(im_msg)
                except Exception as e:
                    print(f"[iMessage] 發送失敗: {e}")
            time.sleep(1)

    # 5. 關鍵字動態演化
    keyword_manager.run_evolution_cycle()
    print(f"\n✅ 掃描完成。共發現 {found_count} 個高價值商機。")

    # 6. 心跳包
    if found_count == 0:
        telegram.send_heartbeat("🟢 巡邏正常 (無新案件)")

    # 7. 匯出 SQLite → dashboard_data.json
    export_dashboard_data()
    print("🚀 Dashboard 數據已匯出完畢。")

    # 8. 每次巡邏完最後一筆推播：發送儀表板圖表連結
    if found_count > 0:
        dash_url = os.getenv("GITHUB_PAGES_URL", "https://keapaisme.github.io/jobmatch")
        telegram.send_message(f"📊 點此查看 <a href='{dash_url}/dashboard.html'>數據可視化</a>")

def main():
    parser = argparse.ArgumentParser(description="Job Finder 監控系統")
    parser.add_argument("--watch", action="store_true", help="持續輪詢爬蟲並同步 Dashboard")
    parser.add_argument("--interval", type=int, default=21600, help="輪詢間隔秒數，預設 6 小時（21600 秒）")
    args = parser.parse_args()

    if not args.watch:
        run_once()
        return

    interval = max(30, args.interval)
    print(f"🔁 持續監控模式已啟動，每 {interval} 秒（約 {interval//3600} 小時）掃描一次。按 Ctrl+C 停止。")
    while True:
        started_at = time.time()
        try:
            run_once()
        except Exception as exc:
            print(f"❌ 本輪掃描失敗，下一輪繼續：{exc}")
        elapsed = time.time() - started_at
        sleep_for = max(0, interval - elapsed)
        print(f"⏳ 下一輪掃描將於 {sleep_for:.0f} 秒後開始...\n")
        try:
            time.sleep(sleep_for)
        except KeyboardInterrupt:
            print("\n🛑 持續監控已停止。")
            break

if __name__ == "__main__":
    main()
