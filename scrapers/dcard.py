"""
scrapers/dcard.py - Dcard 接案/徵人板爬蟲 v1.2
變更簡述：整合 utils.exif_logger Web EXIF 履歷記錄器。針對 Cloudflare 403 防禦進行靜默捕獲與履歷寫入，
          徹底排除主控台紅字報錯，保持終端機輸出乾淨無噪音。
"""
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.exif_logger import log_request_exif

class DcardScraper:
    API_BASE = "https://www.dcard.tw/service/api/v2"
    WEB_BASE = "https://www.dcard.tw"

    def __init__(self, forums=None):
        # Dcard 板名（alias）
        self.forums = forums or ["job", "part_time_job", "money"]
        self.session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.dcard.tw/"
        }

    def fetch_latest_posts(self):
        all_posts = []
        for forum in self.forums:
            url = f"{self.API_BASE}/forums/{forum}/posts?popular=false&limit=30"
            try:
                r = self.session.get(url, headers=self.headers, timeout=10)
                # 紀錄 Web EXIF 履歷
                log_request_exif(f"Dcard-{forum}", url, response=r)
                
                if r.status_code == 200:
                    posts = r.json()
                    for p in posts:
                        title = p.get("title", "")
                        pid = p.get("id", "")
                        link = f"{self.WEB_BASE}/f/{forum}/p/{pid}"
                        all_posts.append({
                            "source": f"Dcard-{forum}",
                            "title": title,
                            "url": link,
                            "salary_type": "",
                            "salary_low": 0
                        })
                elif r.status_code == 403:
                    # 靜默處理 Cloudflare 403，履歷已記錄，不洗終端機畫面
                    pass
                time.sleep(2)
            except Exception as e:
                log_request_exif(f"Dcard-{forum}", url, error_msg=e)
                # 不印出噪音報錯，保持終端機乾淨
                pass
        return all_posts
