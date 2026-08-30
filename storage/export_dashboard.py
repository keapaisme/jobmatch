import sqlite3
import json
import os
import subprocess

DB_PATH = os.path.join(os.path.dirname(__file__), "opportunities.db")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "dashboard_data.json")

def export_dashboard_data():
    if not os.path.exists(DB_PATH):
        print("尚未發現 opportunities.db 資料庫。")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 統計指標
    cursor.execute("SELECT COUNT(*) FROM seen_posts")
    total_seen = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM opportunities WHERE score >= 80")
    high_value_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM feedback_log")
    feedback_count = cursor.fetchone()[0]

    # 2. 抓取高價值與一般商機清單 (最新 50 筆)
    cursor.execute("""
        SELECT post_id, title, url, source, score, x_budget_score, y_urgency_score, vector_json, ai_reason, created_at 
        FROM opportunities ORDER BY id DESC LIMIT 50
    """)
    rows = cursor.fetchall()

    opportunities_list = []
    for r in rows:
        opportunities_list.append({
            "post_id": r[0],
            "title": r[1],
            "url": r[2],
            "source": r[3],
            "score": r[4],
            "x_budget": r[5],
            "y_urgency": r[6],
            "vector": json.loads(r[7].replace("'", '"')) if r[7] else {},
            "ai_reason": r[8],
            "created_at": r[9]
        })

    # 3. 抓取誤判回報案例
    cursor.execute("SELECT post_id, title, content_snippet, reported_reason, meta_intent, created_at FROM feedback_log ORDER BY id DESC LIMIT 20")
    fb_rows = cursor.fetchall()
    feedback_list = []
    for fb in fb_rows:
        feedback_list.append({
            "post_id": fb[0],
            "title": fb[1],
            "content_snippet": fb[2],
            "reason": fb[3],
            "meta_intent": fb[4],
            "created_at": fb[5]
        })

    # 載入動態關鍵字狀態，依分類整理
    keywords_by_cat = {}
    state_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keywords_state.json")
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            kw_scores = state_data.get("keyword_scores", {})
            for kw, info in kw_scores.items():
                cat = info.get("category", "other")
                if cat not in keywords_by_cat:
                    keywords_by_cat[cat] = []
                keywords_by_cat[cat].append(kw)
            
            # 對每個類別下的關鍵字排序
            for cat in keywords_by_cat:
                keywords_by_cat[cat] = sorted(keywords_by_cat[cat])
        except Exception as e:
            print("無法讀取 keywords_state.json:", e)

    data = {
        "updated_at": os.popen("date '+%Y-%m-%d %H:%M:%S'").read().strip(),
        "stats": {
            "total_seen": total_seen,
            "high_value_count": high_value_count,
            "deduplicated_count": total_seen - len(opportunities_list),
            "feedback_count": feedback_count
        },
        "opportunities": opportunities_list,
        "feedback_logs": feedback_list,
        "keywords": keywords_by_cat
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ [資料庫匯出成功] 真實數據已寫入 {OUTPUT_JSON}")
    conn.close()

    # 即時同步至 GCS (強制設定 no-cache 快取標頭，確保前端取得 100% 即時最新資料)
    sync_to_gcs()

def sync_to_gcs():
    try:
        cmd = [
            "gcloud", "storage", "cp", OUTPUT_JSON,
            "gs://job-finder-dashboard-live/storage/dashboard_data.json",
            "--cache-control=no-cache, no-store, must-revalidate"
        ]
        # 必須等待上傳完成，避免 main.py 結束時 GCS 還是舊資料。
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("⚡ [GCS 即時同步完成] 本輪爬蟲資料已上線")
    except Exception as e:
        print(f"❌ GCS 同步錯誤: {e}")

if __name__ == "__main__":
    export_dashboard_data()
