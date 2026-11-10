# OpenGSA

**Grant Scholarships Award**

![OpenGSA 專案主視覺：研究與安心生活](docs/assets/opengsa-social-preview.jpg)

**把時間留給研究，把獎助檢索交給 OpenGSA。**

整理臺灣碩博士生的獎學金、研究獎勵、出國補助、就學與生活支持，以及 RA／TA 權益與求助入口，讓學生看懂資格、掌握期限並查到正式依據。

先有安心研究的生活，才有探索與成長的可能。讓獎助資訊透明，讓學生有選擇，讓權益有依據。

---

## 🚀 最新專案狀態 (Latest Status)

> **公開預覽網站即時發布中**：**[https://opengsa.mattye.dev/](https://opengsa.mattye.dev/)**  
<!-- data-counts:start -->
> **全庫方案覆蓋規模**：**203 筆來源摘要**，其中 202 筆由萃取流程產生、1 筆是尚未由流程取代的手寫卡；排程巡檢中的來源 199 個。來源沒載明時程的標示為未判定，不補值。  

| 類別 | 筆數 |
|---|---|
| 生活／學費 | 123 |
| 研究工具／算力 | 22 |
| 博士研究 | 21 |
| 急難支持 | 11 |
| 成果獎 | 8 |
| 境外研究 | 7 |
| 國際會議 | 6 |
| 聘任入口 | 5 |
<!-- data-counts:end -->
> **測試防線**：Python 單元測試與前端整合測試由 GitHub Actions 每次執行

### 1. 資料規模

上方的筆數與類別表由 `scripts/readme_counts.py` 依資料產生；資料 PR 套用時自動更新，CI 檢查是否一致。還沒做的事列在 [docs/TODO.md](docs/TODO.md)。

---

### 2. 全台 78 所大專校院名冊（U001～U078）
- 名冊與全量來源台帳：[`data/source-expansion/university-source-inventory.json`](data/source-expansion/university-source-inventory.json)，編碼 `U001`～`U078`。
- 哪些學校已有卡片、哪些還沒有，以資料實算為準，不在這裡寫死筆數；下一步（先做沒有卡的學校）見 [docs/TODO.md](docs/TODO.md) 的第 2 階段。
- 調研報告：[全台大專校院獎助擴展調研](docs/TAIWAN-UNIVERSITIES-SCHOLARSHIP-EXPANSION.md)（調研當時的快照）。

---

### 3. 臺大各學院出國出訪補助調研
- 盤查臺大各學院與國際事務處的出國研修、國際會議發表補助：設置辦法、補助額度、受理時點與成果報告義務。
- 調研報告：[臺大學院暨校級出國出訪補助](docs/NTU-COLLEGE-OVERSEAS-GRANTS.md)。報告內的建卡建議尚未實作，也不在 TODO；要做時先列進 [docs/TODO.md](docs/TODO.md)。

---

### 4. 資訊鏈（Source Chains）
OpenGSA 把一個方案的出處拆成節點：母法設置辦法（Anchor）、當期公告（Call）、申請表件或系統（Form）、受理窗口（Intake）、結果公告（Result），用邊記錄它們之間的關係，讓每個欄位能追溯到原文。

- 目前有文件節點的批次只有 `batch-conference.json` 與 `batch-01.json`；大專校院、K-12、學生福利、企業、急難救助、拓撲探索各批次已隨對應卡片撤下而清空。實際數量以 `data/source-chain-batches/` 內的檔案為準。
- 設計：[大專校院生輔組資訊鏈深化拓撲](docs/UNIVERSITY-ASSISTANCE-OFFICES-DEEP-CHAIN.md)（歷史設計）、[通用資訊鏈拓撲](docs/archive/UNIVERSAL-SOURCE-CHAIN-TOPOLOGY.md)（已封存）。
- 離線地圖：[資訊鏈互動樹狀圖](docs/source-chains/source-chain-map.html) · [Obsidian Canvas](docs/source-chains/source-chain-map.canvas)。

---

### 5. 四分頁介面
- **Tab 1（獎助探索與快篩）**：卡片清單與全域甘特圖切換，依學歷、類別、身分篩選，附出國出訪總覽與收藏（[篩選說明](docs/FILTER-EXPANSION-AND-VISIBILITY.md)）。
- **Tab 2（方案詳情與條件比對）**：單一方案詳情，以及雙方案並排比對資格、給付、兼領限制與期限。
- **Tab 3（我的時程與行動規劃）**：個人時間軸，只顯示收藏的方案。
- **Tab 4（權益防線與法規指南）**：聘任與給付、法規與保障、求助與自測；內容與依據見 [權益與法規框架](docs/RIGHTS-AND-LEGAL-FRAMEWORK.md)。
- **網址同步**：分頁、搜尋字、篩選與比對清單同步到網址參數，可分享深層連結。

---

### 6. GitHub Actions 排程
- **來源巡檢**（`scan-sources.yml`）：週一到週六 09:17（臺北，GitHub 不保證準時），週日沒有巡檢。每輪接著上一輪的位置往下讀；請求數、變動文件數、待審數都有上限（`data/scan-sources.json` 的 `max_requests`、`max_changed_documents`、`max_pending_candidates`，目前 50／10／60）。排程不分軌道，模型固定關閉。沒有變動的來源用 ETag／Last-Modified 判斷，仍會發出請求。
- **資料 PR 每週彙整**：週一那輪把整週累積的待審提案開成一個資料 PR，由 owner 審閱後合併；機器人不會自己合併。週二到週六只掃描、累積待審，不開 PR。PR 開出後會在收件匣 Issue 留言通知。
- **狀態檔**：每輪寫 `status/pipeline.csv`、`status/pipeline.json`（來源狀態）；`model-catalog.yml` 每週日 09:47 更新 `status/model-catalog.json`（只查模型清單，不呼叫模型）。
- **來源提交**：Issue 經 owner 加上 `source-approved` 標籤後，`source-intake.yml` 才會跑單一來源的管線。
- **手動時間重萃（`temporal_replay`）**：只由 owner 手動觸發。`gov`、`enterprise`、`other` 分軌和增量閘門（未異動來源判定 `SKIP_UNCHANGED`，0 HTTP）只在這裡生效，排程不經過。
- **網站部署**：`pages.yml` 沒有排程，只在 PR 與推送到 main 時檢查與發布。

---

### 7. 主動推播通知、首頁彈窗與 Follow.it 整合
OpenGSA 支援標準 RSS 2.0 / Atom 1.0 訂閱頻道，隨 GitHub Pages 自動建置。首頁頂端提供 **`[📡 訂閱推播]`** 按鈕與原生 `<dialog>` 小視窗，支援一鍵複製、直接開啟 XML 與免裝閱讀器的外部託管訂閱：
- **首頁「📡 訂閱推播」小視窗**：點擊即可開啟原生彈窗，提供雙軌 Feed 複製、閱讀器訂閱指引與 Follow.it 串接。
- **免裝軟體 · Email 訂閱（透過 Follow.it）**：整合 [Follow.it](https://follow.it/) 代管轉發，使用者可直接以電子郵件或 Telegram 接收推播，OpenGSA 伺服器零個資儲存。
- **最新獎助公告頻道**：[`feed.xml`](https://opengsa.mattye.dev/feed.xml)（全庫來源摘要最新動態）
- **截止倒數專刊頻道**：[`feed-deadlines.xml`](https://opengsa.mattye.dev/feed-deadlines.xml)（即將於近期截止之方案警訊）
- 詳見專案規格書：[RSS 電子報與主動推播通知架構](docs/RSS-FEEDS-AND-NOTIFICATION-ARCHITECTURE.md)。

---

### 8. 篩選與出國交流總覽
- 學歷選單涵蓋全部學歷、大學部／大專、高中職／五專、國中小幼兒，並保留碩博。
- 「出國出訪與境外交流」總覽把國際會議、境外研究與旅費補助聚在一起；各類別的筆數以上方生成表為準。
- 說明文件：[篩選器擴充規格](docs/FILTER-EXPANSION-AND-VISIBILITY.md) · [主動推播與篩選升級手冊](docs/PROACTIVE-NOTIFICATIONS-AND-FILTER-VISIBILITY-GUIDE.md)（兩份都停在 2026-11-05 前後的狀態）。

---

### 9. 國際頂級會議出國獎助
- 基準清冊：[`data/top-conference-travel-grants.json`](data/top-conference-travel-grants.json)，收錄各頂尖會議的學生差旅獎助，項目數以檔案為準。
- 診斷報告（已封存）：[頂級會議獎助未顯示診斷](docs/archive/TOP-CONFERENCE-TRAVEL-GRANTS-AND-DISCOVERY-DIAGNOSIS.md)。2026-11-10 查證多數無法確認，金額與期限一律視為未確認，見該文件頂端的查證紀錄。

---

### 10. 學生身分福利（Student Perks）調研
- 基準台帳：[`data/student-perks-baseline.json`](data/student-perks-baseline.json)，項目數以檔案內 `total_perks_count` 為準。
- 調研報告：[學生身分軟硬體、雲端與生活福利調研](docs/STUDENT-PERKS-EXPANSION-SURVEY.md)。對應的卡片已撤下，目前只保留台帳與調研。

---

## 參與與回報

- **[開啟公開預覽網站](https://opengsa.mattye.dev/)**
- **[提供使用回饋](https://github.com/matt-ye/opengsa/issues/new?template=preview-feedback.yml)**
- **[回報新獎助來源](https://github.com/matt-ye/opengsa/issues/new?template=resource-source.yml)**（歡迎提供各大學、企業或基金會之公開獎助依據）

---

<details>
<summary>點擊展開過往歷史版本與研究紀錄（PR #1～#53，數字為各日當時的快照）</summary>

- **2026-11-04 全庫四大批次來源萃取與時程政策整併（PR #50～#53）**：全庫萃取架構上線（當日全庫 204 筆；該說法的「1-to-1 精確覆蓋」後來經稽核不成立，見 [docs/audits/source-intake-pipeline-review-2026-11-07.md](docs/audits/source-intake-pipeline-review-2026-11-07.md)）。
- **2026-11-03 時間重萃與甘特圖投影（PR #42～#48）**：母頁 HTML＋子頁＋公告 PDF 無損彙整；跨 Chunk Map-Reduce 合成並對接甘特圖 Layout A。
- **2026-11-02 權益頁重大更新與雙按鈕（PR #40、PR #41）**：第四頁改為「重點總覽／聘任與給付／法規與保障／求助與自測」，頁首新增回饋與回報按鈕。
- **2026-11-02 原始來源逐項檢核閉包（PR #37、PR #38）**：485 個原始 URL 完整檢核，256 個可讀、111 個受限，57 個來源進待審建卡，累計 912 HTTP、模型 0。
- **2026-11-01 資訊鏈基線與甘特圖 Layout A（PR #31、PR #32）**：左欄選取管理與資格篩選，時間控制集中圖表工具列；甘特圖全局顯示已有名額範例。
- **2026-10-31 來源掃描與進階驗證防線（PR #24～#27）**：scanner-2 / document-ir-2 整合，15 項對抗測試，HTML 表格脈絡與局部重萃。
- **2026-10-30 候選審查工作台與雙軌模型架構（PR #20）**：候選預覽工作台、8 組 API 查核、排程維持 `model_mode=off`。
- **2026-10-29 MVP 介面與公開預覽啟動（PR #1、PR #2）**：建立四分頁原型與 GitHub Pages 自動部署流程。

</details>
