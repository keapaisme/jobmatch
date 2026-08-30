"""
scrapers/xiao_ji.py - 小雞上工 接案任務爬蟲 v1.0
說明：爬取 chickpt.com.tw/cases 頁面的接案任務，
      鎖定「文書處理/多媒體/電腦」等可遠端完成的任務。
"""
import requests
from bs4 import BeautifulSoup
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.exif_logger import log_request_exif

class XiaoJiScraper:
    BASE_URL = "https://www.chickpt.com.tw"

    def __init__(self, categories=None):
        # 預設監控對接案有意義的類別
        self.categories = categories or ["電腦", "多媒體", "文書處理", "課業"]
        self.session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0",
            "Referer": self.BASE_URL
        }

    def fetch_latest_posts(self):
        all_posts = []
        seen_links = set()
        for cat in self.categories:
            url = f"{self.BASE_URL}/cases?category={cat}"
            try:
                r = self.session.get(url, headers=self.headers, timeout=10)
                log_request_exif(f"小雞上工-{cat}", url, response=r)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")

                # 案件標題在 h2.job-info-title，外層 a 含連結
                for li in soup.find_all("li"):
                    a = li.find("a", href=re.compile(r"/job-"))
                    if not a:
                        continue
                    h2 = a.find("h2", class_="job-info-title")
                    if not h2:
                        continue
                    title = h2.text.strip()
                    link = self.BASE_URL + a.get("href") if a.get("href","").startswith("/") else a.get("href","")
                    
                    # 內部去重，避免跨類別重複抓取
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    
                    # 取薪資
                    salary_tag = a.find("span", class_="salary")
                    salary_text = salary_tag.text.strip() if salary_tag else ""

                    all_posts.append({
                        "source": f"小雞上工-{cat}",
                        "title": title,
                        "url": link,
                        "salary_text": salary_text,
                        "salary_type": "piece",  # 小雞以按件/單次為主
                        "salary_low": 0           # 字串薪資，主程式不做數值過濾
                    })
                time.sleep(2)
            except Exception as e:
                print(f"[錯誤] 小雞上工 ({cat}) 爬取失敗: {e}")
        return all_posts
