# OpenGSA 安全政策（Security Policy）

OpenGSA 致力於為臺灣碩博士生與高等教育研究人員提供透明、安全且嚴謹的獎助與權益資訊。為確保本專案使用者與資料來源的隱私與安全，特訂定本安全與漏洞揭露政策。

---

## 1. 支援版本（Supported Versions）

| 版本 / 分支 | 支援狀態 | 說明 |
| :--- | :---: | :--- |
| `main` 分支 | :white_check_mark: 支援中 | 主要穩定開發分支 |
| GitHub Pages 公開預覽 | :white_check_mark: 支援中 | 靜態展示成品 |
| 歷史功能分支 / PR 草稿 | :x: 不支援 | 請回報至最新 `main` 或預覽版本 |

---

## 2. 核心資料安全與隱私防護邊界

本專案自架構設計即嚴守以下安全邊界：

1. **嚴禁任何真實個資（Zero PII Policy）**：
   - 專案倉庫與公開討論區嚴禁提交真實學生之姓名、學號、身分證號、銀行帳號、薪資單、所得清單或私人申訴信函。
   - 所有驗證案例一律使用合成情境（Synthetic Personas，如 P1 職能治療所博士生、P2 碩士生等）。
2. **外部模型資料零洩漏防護（Zero-Exfiltration Guard）**：
   - 依據版權與隱私條款，受限來源（如教務處 `hash_only` 來源）在程式碼層級設有硬體級 `_guard_hash_only` 防護，外送位元組嚴格為 0（`hash_only_bytes_sent = 0`），絕不送往任何外部 LLM API。
3. **金鑰與機敏憑證隔離**：
   - 本地開發與 CI 排程嚴禁硬編碼任何 API Key。所有推論憑證一律由 GitHub Repository Secrets 管理，且排程預設關閉推論（`model_mode=off`），防止非預期額度消耗。
4. **防提示詞注入（Prompt Injection Defense）**：
   - 外部爬取之未受信任來源資料一律封裝於 `<untrusted_source_data>` 邊界標籤中，並經二次確定性規則與逐字子字串（Substring Matching）精確驗證，防止解析器遭對抗性輸入操控。

---

## 3. 安全漏洞回報流程（Reporting a Vulnerability）

若您在 OpenGSA 專案中發現任何潛在之安全漏洞、未預期的機敏資訊洩漏、API 金鑰暴露或隱私問題：

1. **請勿公開張貼**：請不要在公開的 GitHub Issue、PR 或 Discussions 中討論未修復的漏洞細節。
2. **回報管道**：
   - **GitHub 專屬私人漏洞回報（建議）**：請至本 Repo 之 **Security** 頁籤，點選 **"Report a vulnerability"** 提交私密諮詢（Private Vulnerability Advisory）。
   - **維護者私密聯繫**：若無法使用 GitHub 安全諮詢，請透過主要維護者之公開聯繫方式進行私密通報。
3. **回報內容建議包含**：
   - 漏洞類型（如：XSS、敏感資訊暴露、Regex 拒絕服務、解析器防護穿透等）。
   - 重現步驟或概念驗證（PoC）。
   - 潛在影響評估與建議修補方案。

---

## 4. 回應時限與處理承諾（SLA）

- **確認回報**：我們將在 **48 小時** 內確認收到您的漏洞回報。
- **評估與驗證**：在 **7 個工作天** 內完成漏洞之技術評估與修復規劃。
- **公開發布**：修復補丁將在驗證完成後合併至 `main` 分支並發布公告；在修復完成前，雙方遵循負責任揭露原則（Responsible Disclosure）。
