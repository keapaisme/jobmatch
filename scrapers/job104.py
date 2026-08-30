import requests
import time
from utils.exif_logger import log_request_exif

class Job104Scraper:
    def __init__(self, keywords):
        self.keywords = keywords
        # 104 API 必須帶有 Referer，且建議帶上一般的 User-Agent
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.104.com.tw/jobs/search/"
        }

    def fetch_latest_posts(self):
        """抓取 104 兼職/外包 職缺"""
        all_posts = []
        for kw in self.keywords:
            # 隱藏進度輸出避免洗畫面
            # 改用 104 真正的底層 API
            url = "https://www.104.com.tw/jobs/search/api/jobs"
            
            # 104 的 API 參數
            params = {
                "ro": "2",          # ro=2 代表兼職/打工/外包 (ro=1是全職)
                "keyword": kw,      # 搜尋關鍵字
                "expansionType": "area,spec,com,job,wf,wktm",
                "mode": "s",
                "jobsource": "2018indexpoc",
                "page": 1           # 只抓第一頁最新職缺
            }
            
            try:
                res = requests.get(url, headers=self.headers, params=params, timeout=10)
                log_request_exif(f"104 ({kw})", res.url if hasattr(res, 'url') else url, response=res)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("data", [])
                    
                    for job in jobs:
                        title = job.get("jobName", "")
                        link = job.get("link", {}).get("job", "")
                        if link.startswith("//"):
                            link = "https:" + link
                            
                        company = job.get("custName", "未知公司")
                        
                        # 解析薪資 (用來做二次過濾)
                        salary_low = job.get("salaryLow", 0)
                        salary_high = job.get("salaryHigh", 0)
                        # 00 = 時薪, 01 = 月薪, 02 = 日薪, 03 = 按件計酬
                        salary_type = job.get("period", "")
                        
                        all_posts.append({
                            "source": f"104 ({company})",
                            "title": title,
                            "url": link,
                            "salary_low": int(salary_low) if str(salary_low).isdigit() else 0,
                            "salary_type": salary_type
                        })
                else:
                    print(f"[錯誤] 104 API 回傳狀態碼異常: {res.status_code}")
                time.sleep(2) # 友善爬蟲
            except Exception as e:
                print(f"[錯誤] 爬取 104 (關鍵字: {kw}) 失敗: {e}")
                
        return all_posts
