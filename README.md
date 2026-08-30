# JobMatch - 多平台職缺與商機自動化監控系統

JobMatch 是一個基於 Python 與 GitHub Actions 的多平台商機採集與 AI 自動化評分監控系統。系統會定期採集台灣主要求職與接案平台之最新動態，經由 AI 篩選後，將高價值商機即時推播至 Telegram，並自動更新數據儀表板。

## 🌟 主要功能

- **多來源採集**：支援 PTT (SOHO/CodeJob/Soft_Job 等板)、104 人力銀行、小雞上工、Tasker 出任務、Dcard 求職板。
- **AI 智能評估**：針對案件的自動化程度、報酬與時效進行多維度綜合評分。
- **即時通知**：評估符合門檻之高價值商機，第一時間透過 Telegram Bot 推播通知。
- **自動化維運 (0 成本)**：透過 GitHub Actions 定時執行巡邏任務，並透過 GitHub Pages 自動發布最新視覺化數據。

## ⚙️ 部署與 GitHub Secrets 設定

本專案已完全適應 GitHub Actions 自動化運轉。部署至 GitHub 後，請於 Repository 的 `Settings` ➔ `Secrets and variables` ➔ `Actions` 新增以下 Secrets：

| Secret 名稱 | 說明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot 的 API Token |
| `TELEGRAM_CHAT_ID` | 接收通知的 Telegram Chat ID |
| `AI_API_KEY` | 用於 AI 評估分析之 API Key |

## ⏱️ 定時抓取與手動觸發

1. **自動定時**：預設由 GitHub Actions 每小時自動執行巡邏掃描。
2. **手動觸發**：可前往 GitHub Repository 的 `Actions` 標籤頁，選擇 `JobMatch Automated Monitor` 並點擊 `Run workflow` 隨時發起抓取。

---
*License: Private / Personal Automation Tool*

