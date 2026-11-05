# 目前計畫與已接受決策

## 2026-11-05 RSS 2.0 / Atom 主動推播通知架構與雙軌 Feed 上線（PR #65）

- **官方獎助發放單位 RSS 調研與全景台帳收錄**（[架構規格書](RSS-FEEDS-AND-NOTIFICATION-ARCHITECTURE.md)）：
  - 盤查國科會 (NSTC)、農業部 (MOA)、勞動部 (MOL)、原民會 (CIP)、教育部 (MOE) 與各大專校院生輔組 RSS。
  - 深度對比臺大電子報平台 (`epaper.ntu.edu.tw`)，確立維持 OpenGSA 零個資、零資料庫、純靜態架構，以標準 RSS/Atom 取代傳統 SMTP 發信清單。
- **雙軌 RSS 2.0 Feed 產出與管線整合**：
  - 建立 `scripts/build_feed.py`，隨站建置 `feed.xml`（236 方案）與 `feed-deadlines.xml`（截止倒數）。
  - 單元測試套件擴充至 **281 項 PASS**，嚴格校驗 RFC 822 時間格式與防洩漏邊界。

---

## 2026-11-05 拓撲探針新資源進庫、全庫通用資訊鏈六大批次與 GitHub Actions 全庫掃描驗證（PR #61～#64）

- **全庫方案規模正式擴充至 236 方案**（[專案總稽核報告](TOPOLOGY-EXPANSION-AND-SCAN-AUDIT.md)）：
  - 成功整合四大歷史批次、醫學院特定方案、跨校大專校院方案與拓撲探針新方案，達成全庫 **236 筆候選方案與 236 筆時程觀測政策 1-to-1 精確覆蓋**（`undetermined = 0`，覆蓋率 100%）。
  - 公開站（`https://matt-ye.github.io/opengsa/`）已即時發布 236 方案公開預覽，全部 236 筆時程均具備甘特圖投影與合約校驗。
- **通用資訊鏈 6 大批次全盤落地實施**（[架構規格說明書](UNIVERSAL-SOURCE-CHAIN-TOPOLOGY.md)）：
  - 登錄全庫 6 批次（`batch-k12`, `batch-student-perks`, `batch-enterprise`, `batch-med`, `batch-university`, `batch-topology-discovered`）。
  - 全庫建構 **525 份文件節點**、**350 條指向邊**，精確關聯 **175 方案**。
- **拓撲探針掃描 8 筆高價值資源完成模組化隔離整合**：
  - 原民會大專校院原住民族學生獎助學金 (`cand-gov-cip-indigenous-scholarship`)
  - 農業部農漁民子女就學助學金 (`cand-gov-moa-farmers-aid`)
  - 勞動部失業勞工子女就學補助 (`cand-gov-mol-unemployed-workers-aid`)
  - 退輔會榮民子女就學補助及清寒獎助金 (`cand-gov-vac-veterans-aid`)
  - Microsoft Azure for Students 學生雲端算力與點數 (`cand-perk-azure-for-students`)
  - 中華民國資訊學會最佳碩博士論文獎 IICM (`cand-ent-iicm-thesis-award`)
  - 中華民國人工智慧學會最佳論文獎 TAAI (`cand-ent-taai-thesis-award`)
  - 中華民國電腦學會最佳碩博士論文獎 CSROC (`cand-ent-csroc-thesis-award`)
- **GitHub Actions 公共來源全庫掃描與部署驗證**：
  - `Scan public sources`（Run ID: [42029629014](https://github.com/matt-ye/opengsa/actions/runs/42029629014)）順利執行完畢，0 錯誤、0 額外 API 開銷。
  - GitHub Pages（Run ID: [42029433102](https://github.com/matt-ye/opengsa/actions/runs/42029433102)）即時完成編譯並部署上線。
- **測試防線**：278 項 Python 單元測試 PASS、54 項前端整合測試 PASS，正式台帳 0 篡改。

---

## 2026-11-05 跨校獎助擴展、臺大11學院出國補助調研與通用資訊鏈拓撲規劃（PR #58～#60）

- **全庫方案發布規模突破至 236 方案**：
  - 成功整合四大歷史批次、醫學院特定方案與跨校大專校院方案，達成全庫 **236 筆候選方案與 236 筆時程觀測政策 1-to-1 精確覆蓋**（`undetermined = 0`，覆蓋率 100%）。
  - 公開站（`https://matt-ye.github.io/opengsa/`）已即時發布 236 方案公開預覽，全部 236 筆時程均具備甘特圖投影與合約校驗。
- **臺大 11 個學院暨校級 OIA 出國出訪補助深度調研**（[專題報告](NTU-COLLEGE-OVERSEAS-GRANTS.md)）：
  - 盤查文學院、理學院、社會科學院、醫學院、工學院、生物資源暨農學院、管理學院、公共衛生學院、電機資訊學院、法律學院、生命科學院及國際事務處（OIA）之出國研修、國際會議發表與出訪獎助。
  - 梳理各院設置辦法（Anchor）、徵件公告（Call）、申請表件（Form）、初審窗口（Intake）與出國報告核銷（Result）。
  - 確立優先申請國科會/教育部之 Precedence Principle 與返國成果報告義務。
- **全台 78 所大專校院名冊盤查與來源總表**（[擴展專案報告](TAIWAN-UNIVERSITIES-SCHOLARSHIP-EXPANSION.md)）：
  - 盤點全台 78 所公私立大學（國立大學 26 所、國立科大 12 所、私立大學 22 所、私立醫科 5 所、私立科大 12 所、市立大學 1 所）。
  - 建立全量來源台帳 `data/source-expansion/university-source-inventory.json`，編配標準來源代碼 **`U001`～`U078`**。
  - 提煉 24 筆跨校代表性方案（`data/candidates/university-scholarships.json`）。
- **五節點標準資訊鏈拓撲批次建置**（[規格說明書](UNIVERSITY-SOURCE-CHAINS.md)）：
  - 建立 `data/source-chain-batches/batch-university.json`，涵蓋 72 份文件節點與 48 條指向邊，完整定義 Anchor ➔ Call ➔ Form ➔ Intake ➔ Result 五層流轉。
  - 產出建構腳本 `scripts/build_university_source_chains.py`。
  - 嚴格守護正式台帳指紋：`data/pilot.json`、`data/source-inventory.json` 與 `data/source-chains.json` 零竄改。
- **跨資源通用資訊鏈架構規劃**（[架構規劃書](UNIVERSAL-SOURCE-CHAIN-TOPOLOGY.md)）：
  - 針對全庫公部門、學生 Perks、企業基金會、研討會等異質資源，定義五大拓撲原型（Higher Ed, Government, Corporate Dual-Track, Student Perks, Conference Grants）。
  - 制定 Universal Source Chain Schema v2.0，作為下個 PR 跨來源拓撲通用化實作的基礎。
- **GitHub Actions 巡檢軌道與增量保護**：
  - 大學來源歸入 `schedule_track: "other"`，每週三、週六 09:17 自動執行。
  - 增量閘門在公開入口無變更時直接標記 `SKIP_UNCHANGED`（0 HTTP / 0 Token），嚴格維持 `model_mode=off`。

---

## 2026-11-04 UI/UX 四分頁功能重新定位與 URL 狀態同步（PR #55）
- **四分頁功能定位與動線劃分**：
  - **Tab 1（獎助探索與快篩）**：聚焦漏斗頂端快速發現，支援卡片清單與全域甘特圖切換，卡片附一鍵【⭐ 收藏至個人時程】與【📄 查看完整條文】。
  - **Tab 2（方案詳情與條件比對）**：新增獨立搜尋列與全庫方案切換（不再受限於第一頁篩選）；新增「雙方案並排比對（Side-by-Side）」功能，並排比對資格、金額、兼領與期限。
  - **Tab 3（我的時程與行動規劃）**：純粹化個人專屬時間軸，專注渲染使用者收藏的項目；提供「一鍵收藏目前篩選方案」引導；待辦清單附進度統計。
  - **Tab 4（權益防線與法規指南）**：維持雙軌五級救濟地圖與各校 TA/RA 給付行情比對。
- **輕量 URL 狀態同步（State in URL）**：
  - 原生 `URLSearchParams` 雙向同步 `tab`, `q`, `cat`, `deg`, `mode`, `view`, `id`, `compare`, `picks`；支援深層連結（Deep-linking）與 F5 重整不遺失。
  - 採稀疏編碼（預設值不寫入），不編碼敏感清寒標記以保護隱私。
  - 頁首新增「📋 分享此畫面」一鍵複製純淨分享連結。
- **「臺大醫學院研究生優秀著作獎」可見度與檢索**：
  - 擴充同義詞查詢（搜尋「論文」、「著作」、「醫學院」或「成果獎」均精確命中）。
  - 深層連結 `?id=ntu-med-publication-115` 自動以真實草稿模式開啟該獎項詳情。
- **測試驗證全數通過**：275 項 Python 單元測試 PASS、54 項 Node 測試 PASS、資料台帳 0 竄改。

---

## 2026-11-04 全庫四大批次來源萃取與時程政策整併（PR #50～#53）
- 詳見 [全庫萃取架構與管線說明](FULL-LIBRARY-EXTRACTION-PLAN.md)。
- 完成四大批次全庫萃取：
  - Batch 1: K-12 公部門與法定助學 25 方案
  - Batch 2: 學生福利與 AI 特惠 28 方案
  - Batch 3: 企業、基金會與學會獎助 85 方案
  - Batch 4: AI 工具 2 方案 + 既有 64 方案
- 三軌排程路由、三層增量比對閘門與動態備援池架構上線；275 項單元測試、54 項線框測試 PASS；正式 pilot 與人工審核欄位零竄改，候選維持待審。

---

## 2026-11-04 多層來源資訊鏈（Source Chains）全庫架構整合
- 跨教育階段與民間資助之深度調研報告收齊落盤：
  - [K-12 獎助全景與五層法源資訊鏈](K12-SCHOLARSHIP-LANDSCAPE-AND-SOURCE-CHAINS.md)：25 方案法律母法、要點、地方大學平台、初審代收。
  - [學生身分軟硬體、AI與學習資源優惠全景](STUDENT-SOFTWARE-HARDWARE-AND-AI-PERKS.md)：28 方案六大福利支柱與 6 種查驗途徑。
  - [企業、基金會與學會獎助全景與雙軌申辦鏈](ENTERPRISE-SCHOLARSHIP-LANDSCAPE-AND-SOURCE-CHAINS.md)：85 方案生輔組薦送 vs 線上直申。
  - [UI/UX 導覽教學與易用性升級調研](UI-UX-ONBOARDING-AND-SKILLS-STUDY.md) 及 [開源資助與生態系贊助策略](OPEN-SOURCE-GRANTS-AND-OPENAI-STRATEGY.md)。

---

## 過往階段與已接受決策

<details>
<summary>點擊展開過往歷史里程碑（PR #16～#49）</summary>

- **2026-11-03 四階段時間重萃與甘特圖整合（PR #45～#48）**：最外層三軌排程路由（週二五 gov / 週一四 enterprise / 週三六 other）；8 組 API 動態備援池；母頁 HTML＋子頁＋公告 PDF 無損彙整；跨 Chunk Map-Reduce 合成並對接甘特圖 Layout A。
- **2026-11-03 時間投影契約 v1 與既有規則顯示（PR #42）**：以獨立投影契約轉接原候選欄位，不重抓來源、不改 pending 或受理核定。
- **2026-11-02 權益頁重大更新與雙按鈕（PR #40、PR #41）**：第四頁改為「重點總覽／聘任與給付／法規與保障／求助與自測」，補齊五類聘任查核路徑；頁首新增「提供回饋」與「提供獎助來源」按鈕。
- **2026-11-02 64 筆雷達可用性改善（PR #39）**：補工具／AI／算力快捷入口，方案來源依文字/名稱分類，新增公告年份推估淺色參考帶。
- **2026-11-02 原始來源逐項檢核閉包（PR #37、PR #38）**：485 個原始 URL 完整檢核，256 個可讀、111 個受限，57 個來源進待審建卡，累計 912 HTTP、模型 0。
- **2026-11-01 資訊鏈基線與甘特圖 Layout A（PR #31、PR #32）**：左欄選取管理與資格篩選，時間控制集中圖表工具列；甘特圖全局顯示已有名額範例。
- **2026-10-31 來源掃描與進階驗證防線（PR #24～#27）**：scanner-2 / document-ir-2 整合，15 項對抗測試，HTML 表格脈絡與局部重萃。
- **2026-10-30 候選審查工作台與雙軌模型架構（PR #20）**：候選預覽工作台、8 組 API 查核、排程維持 `model_mode=off`。

</details>
