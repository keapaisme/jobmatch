import requests
from bs4 import BeautifulSoup
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.exif_logger import log_request_exif

class PTTScraper:
    def __init__(self, boards):
        self.boards = boards
        self.base_url = "https://www.ptt.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": "over18=1" # 繞過年齡限制
        }
        
        # 設定重試機制，避免連線中斷 (Connection reset by peer)
        self.session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def fetch_latest_posts(self):
        """抓取指定看板的最新文章"""
        all_posts = []
        for board in self.boards:
            url = f"{self.base_url}/bbs/{board}/index.html"
            try:
                # 隱藏進度輸出避免洗畫面
                res = self.session.get(url, headers=self.headers, timeout=10)
                log_request_exif(f"PTT-{board}", url, response=res)
                res.raise_for_status() # 檢查狀態碼
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 抓取文章列表
                for entry in soup.find_all("div", class_="r-ent"):
                    title_elem = entry.find("div", class_="title").find("a")
                    if not title_elem:
                        continue # 文章可能被刪除
                    
                    title = title_elem.text.strip()
                    link = self.base_url + title_elem["href"]
                        
                    all_posts.append({
                        "source": f"PTT-{board}",
                        "title": title,
                        "url": link
                    })
                time.sleep(2) # 友善爬蟲，避免被鎖 IP
            except requests.exceptions.RequestException as e:
                print(f"[錯誤] 爬取 PTT {board} 連線失敗: {e}")
            except Exception as e:
                print(f"[錯誤] 爬取 PTT {board} 發生未知的錯誤: {e}")
                
        return all_posts
