"""
scrapers/tasker.py - Tasker 出任務接案平台爬蟲 v1.0
說明：爬取 tasker.com.tw/cases 頁面的案件，
      鎖定 AI/設計/自動化/寫作等可遠端完成的外包案。
"""
import requests
from bs4 import BeautifulSoup
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.exif_logger import log_request_exif

class TaskerScraper:
    BASE_URL = "https://www.tasker.com.tw"

    def __init__(self, categories=None):
        # Tasker 類別路徑：/cases?category_id=xxx 或直接 /cases
        # 先爬全部，讓主程式關鍵字過濾決定
        self.categories = categories or ["all"]
        self.session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0",
            "Referer": self.BASE_URL
        }

    def fetch_latest_posts(self):
        all_posts = []
        url = f"{self.BASE_URL}/cases"
        try:
            r = self.session.get(url, headers=self.headers, timeout=10)
            log_request_exif("Tasker出任務", url, response=r)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # 案件卡片：a.li-case → h2.li-title 為標題
            for a in soup.find_all("a", class_="li-case"):
                h2 = a.find("h2", class_="li-title")
                if not h2:
                    continue
                title = h2.text.strip()
                href = a.get("href", "")
                link = self.BASE_URL + href if href.startswith("/") else href

                # 取預算金額（span 含 $ 符號）
                price_spans = a.find_all("span", string=re.compile(r"\$[\d,]+"))
                price_text = " ~ ".join([s.text.strip() for s in price_spans]) if price_spans else ""

                all_posts.append({
                    "source": "Tasker出任務",
                    "title": title,
                    "url": link,
                    "salary_text": price_text,
                    "salary_type": "project",  # Tasker 以專案總價計費
                    "salary_low": 0
                })
            time.sleep(2)
        except Exception as e:
            print(f"[錯誤] Tasker 爬取失敗: {e}")
        return all_posts
