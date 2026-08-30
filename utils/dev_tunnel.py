"""
utils/dev_tunnel.py - On-demand 臨時遠端開發通道 v1.0
功能：
  1. 啟動 pinggy.io 隧道將本機 port 22 對外暴露
  2. 即時擷取分配到的公網 Host 與 Port
  3. 透過 Telegram 發送給使用者，供 iPhone 捷徑連線使用
  4. 保持執行，60 分鐘後自動關閉以策安全
"""
import subprocess
import time
import re
import os
import sys
import yaml

def get_config():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f), path
    return {}, path

def send_telegram_notification(msg: str):
    config, _ = get_config()
    tg = config.get("telegram", {})
    token = tg.get("bot_token", "")
    chat_id = tg.get("chat_id", "")
    if not token or not chat_id:
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        # 如果 requests 尚未載入，fallback 用 urllib
        import urllib.request
        import json
        req = urllib.request.Request(
            url, 
            data=json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def start_tunnel():
    print("📡 正在向 pinggy.io 要求臨時開發通道...")
    send_telegram_notification("📡 <b>[遠端開發]</b> 正在向公網伺服器申請臨時加密通道，請稍候約 5 秒...")

    # 執行 ssh 連線要求公網轉發 (pinggy 支援 443 port 穿透防火牆)
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
        "-p", "443", "-R", "0:localhost:22", "tcp@free.pinggy.io"
    ]
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_url = None
    tunnel_port = None
    start_time = time.time()

    # 讀取輸出尋找 tcp:// 網址
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        print("PINGGY:", line.strip())
        
        # 尋找類似 tcp://vgpdh-118-161-13-152.run.pinggy-free.link:33395 的字眼
        match = re.search(r"tcp://([^:]+):(\d+)", line)
        if match:
            tunnel_url = match.group(1)
            tunnel_port = match.group(2)
            break
        
        # 逾時判定 (15秒沒拿到就退出)
        if time.time() - start_time > 15:
            break

    if tunnel_url and tunnel_port:
        import getpass
        username = getpass.getuser()
        success_msg = (
            "📡 <b>【臨時遠端開發通道已開通】</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 <b>主機 (Host)：</b> <code>{tunnel_url}</code>\n"
            f"🔌 <b>端口 (Port)：</b> <code>{tunnel_port}</code>\n"
            f"👤 <b>帳號 (User)：</b> <code>{username}</code>\n\n"
            "💡 <i>請將上方主機與端口複製並填入您的 iPhone 捷徑設定中即可成功連線！</i>\n"
            "⏰ <i>通道有效時間為 60 分鐘，逾時將自動中斷以保護安全。</i>"
        )
        send_telegram_notification(success_msg)
        print(f"✅ 通道成功開通！Host: {tunnel_url}, Port: {tunnel_port}")
        
        # 保持執行 60 分鐘後關閉
        try:
            time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            proc.terminate()
            send_telegram_notification("🔒 <b>[遠端開發]</b> 臨時通道已安全關閉。")
    else:
        fail_msg = "❌ <b>[遠端開發]</b> 通道開通失敗，請確認 Mac 連網正常或稍後再試。"
        send_telegram_notification(fail_msg)
        proc.terminate()

if __name__ == "__main__":
    start_tunnel()
