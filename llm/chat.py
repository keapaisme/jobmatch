"""
llm/chat.py - 輕量 AI API 呼叫模組 v1.0
變更簡述：替代本機 AI_CORE 私有模組，使用環境變數 AI_API_KEY 直接呼叫 OpenAI 相容 API。
         支援 DeepSeek / OpenAI / 任意相容端點，無需本地 AI_CORE 安裝。
"""
import os
import json
import requests


def ask_ai(prompt: str, model: str = None, system: str = None) -> tuple:
    """
    呼叫 AI API，回傳 (content, usage)

    Args:
        prompt: 使用者提示
        model:  模型名稱（可覆寫，預設讀 AI_MODEL 環境變數，再 fallback 至 deepseek-chat）
        system: 系統提示（可選）

    Returns:
        tuple[str, dict]: (content, usage_dict)

    Raises:
        ValueError: AI_API_KEY 未設定時
        requests.HTTPError: API 回傳非 2xx 時
    """
    api_key = os.getenv("AI_API_KEY", "").strip()
    api_url = os.getenv("AI_API_URL", "https://api.deepseek.com/v1/chat/completions")
    if not model:
        model = os.getenv("AI_MODEL", "deepseek-chat")

    if not api_key:
        raise ValueError("[llm.chat] AI_API_KEY 環境變數未設定，無法呼叫 AI API")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }

    resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    return content, usage
