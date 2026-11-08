# OpenGSA

**Grant Scholarships Award**

![OpenGSA 專案主視覺：研究與安心生活](docs/assets/opengsa-social-preview.jpg)

**把時間留給研究，把獎助檢索交給 OpenGSA。**

整理臺灣碩博士生的獎學金、研究獎勵、出國補助、就學與生活支持，以及 RA／TA 權益與求助入口，讓學生看懂資格、掌握期限並查到正式依據。

先有安心研究的生活，才有探索與成長的可能。讓獎助資訊透明，讓學生有選擇，讓權益有依據。

---

## 🚀 最新專案狀態 (Latest Status)

> **公開預覽網站即時發布中**：**[https://opengsa.mattye.dev/](https://opengsa.mattye.dev/)**  
> **全庫方案覆蓋規模**：**224 筆來源摘要**（部分是早期手寫卡，尚待用現行流程重新查核；來源沒載明時程的標示為未判定，不補值）  
> **測試防線**：Python 單元測試與前端整合測試由 GitHub Actions 每次執行

### 1. 全庫八大獎助資源板塊 (224 筆來源摘要)
OpenGSA 目前收錄跨越教育階段、公部門、民間企業與高等教育學府的完整資源光譜：
1. **研究生、校內與民間獎助（來源審核中，163 筆）**：國科會博士生研究獎學金、教育部產學博班、校長獎學金、傑出論文成果獎，以及各校公告的校內外獎學金與民間基金會獎助等。
2. **K-12 各級教育與公部門助學 (8 筆)**：學產基金、教育部清寒弱勢助學、地方政府急難救助金等（[專題報告](docs/K12-SCHOLARSHIP-LANDSCAPE-AND-SOURCE-CHAINS.md)）。
3. **學生身分軟硬體、雲端與 AI Perks (13 筆)**：GitHub Student Pack、Notion AI、JetBrains、AWS Educate 等（[專題報告](docs/STUDENT-SOFTWARE-HARDWARE-AND-AI-PERKS.md)）。
4. **企業、民間基金會與學會獎助 (5 筆)**：台積電、鴻海獎學鯨、行天宮、宗倬章、各專門學會獎助等（[專題報告](docs/ENTERPRISE-SCHOLARSHIP-LANDSCAPE-AND-SOURCE-CHAINS.md)）。
5. **醫學與特定專業出國/論文獎助 (1 筆)**：臺大醫學院學生出國補助辦法、醫學院研究生優秀著作獎（[專題報告](docs/MED-SCHOLARSHIPS-AUDIT.md)）。
6. **全台跨校大專校院代表性研究生獎助 (19 筆)**：清華、交大、成大、政大、中央、中山、中興、中正、師大、臺北大學等 24 所代表性高教學府（[專題報告](docs/TAIWAN-UNIVERSITIES-SCHOLARSHIP-EXPANSION.md)）。
7. **中央跨部會法定助學、算力與全國學會論文獎 (3 筆)**：原民會、農業部、勞動部、退輔會就學補助，Azure for Students 算力點數，資訊學會 (IICM)、人工智慧學會 (TAAI)、電腦學會 (CSROC) 碩博士最佳論文獎。
8. **全台急難救助與變故支持 (12 筆)**：學校、地方縣市、單親特境與國際生急難救助等（清單見 `data/candidates/emergency-relief-aid.json`）。

---

### 2. 全台 78 所公私立大學校院名冊盤查 (U001～U078)
- 盤查全台 78 所大專校院學務處生輔組、助學系統與博碩士研究生加碼機制。
- 建立全量來源台帳：[`data/source-expansion/university-source-inventory.json`](data/source-expansion/university-source-inventory.json)，編配代碼 **`U001`～`U078`**。
- 詳見專題調研：[全台大專校院獎助擴展報告](docs/TAIWAN-UNIVERSITIES-SCHOLARSHIP-EXPANSION.md)。

---

### 3. 臺大 11 個學院出國出訪補助深度調研
- 盤查文學院、理學院、社會科學院、醫學院、工學院、生物資源暨農學院、管理學院、公共衛生學院、電機資訊學院、法律學院、生命科學院及國際事務處 (OIA) 的出國研修、國際會議發表與出訪獎助。
- 梳理各院設置辦法、補助額度（1.5 萬至 6 萬元）、受理截點（固定梯次 vs 隨到隨審）與出國成果報告義務。
- 詳見專題報告：[臺大 11 學院暨校級出國出訪補助全景](docs/NTU-COLLEGE-OVERSEAS-GRANTS.md)。

---

### 4. 通用資訊鏈（Universal Source Chains）五節點拓撲
OpenGSA 解決過去獎助資訊「只有單一網址、缺漏法源母法與申請系統」的斷鏈痛點，建立五節點標準拓撲：
$$\text{Anchor (母法設置辦法)} \xrightarrow{\text{rule}} \text{Call (當期徵件公告)} \xrightarrow{\text{portal}} \text{Form (申請表件/系統)} \xrightarrow{\text{intake}} \text{Intake (生輔組/系所窗口)} \xrightarrow{\text{result}} \text{Result (名冊公示)}$$

- **大專校院資訊鏈批次**：[`data/source-chain-batches/batch-university.json`](data/source-chain-batches/batch-university.json)（120 份文件節點、96 條邊）。
- **全庫拓撲擴展與掃描稽核報告**：[全庫 236 方案拓撲擴展與 Actions 掃描稽核](docs/TOPOLOGY-EXPANSION-AND-SCAN-AUDIT.md)。
- **通用拓撲架構規格書**：[全庫跨資源通用資訊鏈架構規劃](docs/UNIVERSAL-SOURCE-CHAIN-TOPOLOGY.md)（定義高教型、公部門法定型、企業雙軌型、學生 Perks 型與研討會型五大原型）。
- **離線資訊鏈地圖**：[資訊鏈互動樹狀圖](docs/source-chains/source-chain-map.html) · [Obsidian Canvas](docs/source-chains/source-chain-map.canvas)。

---

### 5. 四分頁職責重新定位與輕量 URL 狀態同步
- **Tab 1（獎助探索與快篩）**：支援卡片清單與全域甘特圖切換；升級**全教育階段學歷篩選**（大學部、高中職、國中小幼兒、碩博）與**出國出訪綜合總覽**，卡片附一鍵【⭐ 收藏至個人時程】與【📄 查看完整條文】（[篩選升級說明](docs/FILTER-EXPANSION-AND-VISIBILITY.md)）。
- **Tab 2（方案詳情與條件比對）**：支援全庫 128 筆來源摘要獨立切換；新增**雙方案並排比對（Side-by-Side）**，精確比對資格、給付、兼領限制與期限。
- **Tab 3（我的時程與行動規劃）**：專屬個人時間軸，專注渲染收藏方案，附待辦核銷進度統計與研討會個人補助試算。
- **Tab 4（權益防線與法規指南）**：提供雙軌五級救濟地圖、各校 TA/RA 給付行情比對與從屬性自測工具（[權益頁說明](docs/RIGHTS-PAGE-UPDATE.md)）。
- **輕量 URL 狀態同步（State in URL）**：`URLSearchParams` 雙向同步分頁、搜尋字、篩選、比對清單，支援深層連結與頁首「📋 分享此畫面」一鍵複製。

---

### 6. GitHub Actions 來源巡檢
- **排程掃描**：週一到週六 09:17（UTC+8，GitHub 不保證準時），週日沒有排程。每輪接著上一輪的位置往下讀，請求數有上限（`data/scan-sources.json` 的 `max_requests`），不分軌道，模型固定關閉。沒有變動的來源用 ETag／Last-Modified 判斷，仍會發出請求。
- **手動時間重萃（`temporal_replay`）**：只由 owner 手動觸發。`gov`、`enterprise`、`other` 分軌和增量閘門（未異動來源判定 `SKIP_UNCHANGED`，0 HTTP）都只在這裡生效，排程不經過。
- **產出**：掃描結果是待審提案，存成 Actions artifact；排程不會改動網站資料。

---

### 7. 主動推播通知、首頁彈窗與 Follow.it 整合
OpenGSA 支援標準 RSS 2.0 / Atom 1.0 訂閱頻道，隨 GitHub Pages 自動建置。首頁頂端提供 **`[📡 訂閱推播]`** 按鈕與原生 `<dialog>` 小視窗，支援一鍵複製、直接開啟 XML 與免裝閱讀器的外部託管訂閱：
- **首頁「📡 訂閱推播」小視窗**：點擊即可開啟原生彈窗，提供雙軌 Feed 複製、閱讀器訂閱指引與 Follow.it 串接。
- **免裝軟體 · Email 訂閱（透過 Follow.it）**：整合 [Follow.it](https://follow.it/) 代管轉發，使用者可直接以電子郵件或 Telegram 接收推播，OpenGSA 伺服器零個資儲存。
- **最新獎助公告頻道**：[`feed.xml`](https://opengsa.mattye.dev/feed.xml)（全庫 128 筆來源摘要最新動態）
- **截止倒數專刊頻道**：[`feed-deadlines.xml`](https://opengsa.mattye.dev/feed-deadlines.xml)（即將於近期截止之方案警訊）
- 詳見專案規格書：[RSS 電子報與主動推播通知架構](docs/RSS-FEEDS-AND-NOTIFICATION-ARCHITECTURE.md)。

---

### 8. 全教育階段身分篩選、出國交流總覽與 K-12 可見度升級
徹底解決學位選單過濾過窄導致 K-12 與大專方案隱沒，以及出國獎學金割裂分散之痛點：
- **全教育階段 8 大維度覆蓋**：學歷選單支援全部學歷、大學部/大專、高中職/五專、國中/國小/幼兒，並保留碩博與博士候選人。
- **出國出訪與境外交流總覽 (all_abroad)**：一鍵聚合國際會議發表 7 筆 + 境外留學研修 10 筆 + 旅費補助，共 19 筆出國獎助。
- **各級教育與弱勢扶助總覽 (all_k12)**：直達學產基金、高職免學費等基礎就學扶助。
- **情境快速篩選列 (Persona Bar)**：新增「境」（出國交流）與「助」（弱勢扶助）專屬情境按鈕。
- 詳見專題手冊：[主動推播通知與全教育階段篩選升級全景手冊](docs/PROACTIVE-NOTIFICATIONS-AND-FILTER-VISIBILITY-GUIDE.md) · [篩選器擴充規格書](docs/FILTER-EXPANSION-AND-VISIBILITY.md)。

---

### 9. 國際頂級會議專屬獎助（Top Conference Travel Grants）診斷與同義詞搜尋升級
深入排查碩博士生頂尖研討會出國差旅獎助未顯示之四大根因（資料庫未收錄、radarView 隔離、搜尋缺少同義詞、相對期限無實體色帶），並完成升級：
- **前端搜尋同義詞字典全面擴充**：搜尋引擎支援 `頂會`、`頂級會議`、`Top Conference`、`Travel Grant`、`差旅補助`、`出國開會`、`NeurIPS`、`CVPR`、`SIGGRAPH`、`ICML`，100% 精確命中研討會與出國補助。
- **頂會專屬獎助基準清冊**：建立 [`data/top-conference-travel-grants.json`](data/top-conference-travel-grants.json)，完整收錄 12 項頂級會議獎助（NeurIPS Scholar Award, CVPR Travel Grant, ICML, ICLR, ACL, SIGGRAPH, SIGCOMM, CHI, INFOCOM, Google/MSR Travel Grants 與各大學院系頂會專款加碼）。
- **研究生赴頂會發表四步連環攻防策略**：詳見專題報告：[國際頂級會議專屬學生獎助未顯示診斷與全景架構報告](docs/TOP-CONFERENCE-TRAVEL-GRANTS-AND-DISCOVERY-DIAGNOSIS.md)。

---

### 10. 公私立大專校院生輔組資訊鏈五節點閉環拓撲深化
打通全台 78 所大專校院學務處生輔組與校園助學系統孤島，將 24 所代表性大學資訊鏈由 3 節點升級為完整的五節點閉環拓撲：
$$\text{Anchor (母法設置辦法)} \xrightarrow{\text{rule}} \text{Call (生輔組徵件公告)} \xrightarrow{\text{portal}} \text{Form (助學系統/表件)} \xrightarrow{\text{intake}} \text{Intake (系所/生輔組窗口)} \xrightarrow{\text{result}} \text{Result (名冊公示與撥款)}$$
- **更新大專校院拓撲批次**：[`data/source-chain-batches/batch-university.json`](data/source-chain-batches/batch-university.json)（**120 份文件節點、96 條流轉邊**）。
- **全台 78 校名冊對接**：[`data/source-expansion/university-source-inventory.json`](data/source-expansion/university-source-inventory.json)（涵蓋國立頂大、國立科大、私立綜合大學、醫學大學與私立科大）。
- 詳見專案規格書：[全台公私立大專校院生輔組資訊鏈深化拓撲規格書](docs/UNIVERSITY-ASSISTANCE-OFFICES-DEEP-CHAIN.md)。

---

### 11. 學生身分福利（Student Perks）第二梯次擴展調研
深化學術寫作、科學運算、雲端部署與大專生軌道交通生活福利：
- **擴展基準台帳**：[`data/student-perks-baseline.json`](data/student-perks-baseline.json) 正式擴展至 **40 項代表性核心方案**。
- **新增 12 項高價值福利**：Overleaf Professional (LaTeX 雲端協作)、Grammarly for Education、EndNote & Zotero、Wolfram Mathematica & Alpha Pro、DigitalOcean ($200 額度)、Namecheap 免費域名、GitKraken / Docker Desktop、台灣高鐵大學生 5/75 折優惠、Miro for Education 視覺白板等。
- 詳見深度報告：[全球與臺灣學生身分軟硬體、雲端與生活福利第二梯次擴展調研報告](docs/STUDENT-PERKS-EXPANSION-SURVEY.md)。

---

### 12. 全站四分頁 RWD 響應式升級、甘特圖 64px 緊湊化與 Toutour 情境感知子導覽
全面解決甘特圖可視空間侷促、首頁底部懸空死空白與各頁子導覽需求，遵循使用者自研之 `Toutour` 10 大反模式審查規範與 `Cinematic UI` 電影分鏡美學，完成五重防線升級：
- **甘特圖 64px 緊湊列高與自適應擴展**：列高從 110px 壓縮至 **64px**（桌面）/ **56px**（手機），單屏可見方案翻倍（6~8 筆）；高度自適應佔滿螢幕（78vh 桌面 / 76vh 手機），手機左欄收窄至 108px 釋出 30% 日期軸空間。
- **徹底消滅首頁底部死空白**：收斂 `.screen` 與 `footer` 的垂直 padding，右欄 Flex 垂直撐滿，卡片緊貼頁尾，徹底告別中空懸空的視覺斷層。
- **Toutour 情境感知 5 大導覽體系**：提供 `global`（全站 4 步總覽）及 `search`、`detail`、`timeline`、`rights` 四大分頁專屬子導覽；點擊頁首 `❓ 快速指南` 或按 `?` 鍵時自動感知所在分頁精準彈出，每頁嚴格 $\le 4$ 步，支援頂部選單自由切換。
- **其餘分頁 RWD 深度優化**：Tab 2 工具列小螢幕彈性分組與防空白、Tab 3 個人甘特圖緊湊化、Tab 4 四大主題改為手機版橫向無縫捲動膠囊（Segmented Scroll）。
- **全站鍵盤快捷鍵矩陣與動態微回饋**：`?`（喚起當前分頁指南）、`/`（聚焦搜尋框）、`1`～`4`（切換四分頁）、`Esc`（退出彈窗）；跨頁收藏即時浮動 Toast。
- 詳見專案手冊：[快速上手指南、全站四分頁 RWD 響應式升級與 Toutour 子導覽手冊](docs/UI-UX-ONBOARDING-AND-ROADMAP-TODO.md)。

---

## 參與與回報

- **[開啟公開預覽網站](https://opengsa.mattye.dev/)**
- **[提供使用回饋](https://github.com/matt-ye/opengsa/issues/new?template=preview-feedback.yml)**
- **[回報新獎助來源](https://github.com/matt-ye/opengsa/issues/new?template=resource-source.yml)**（歡迎提供各大學、企業或基金會之公開獎助依據）

---

<details>
<summary>點擊展開過往歷史版本與研究紀錄（PR #1～#49）</summary>

- **2026-11-04 全庫四大批次來源萃取與時程政策整併（PR #50～#53）**：全庫萃取架構上線，204 筆候選方案與政策達成 1-to-1 精確覆蓋。
- **2026-11-03 時間重萃與甘特圖投影（PR #42～#48）**：母頁 HTML＋子頁＋公告 PDF 無損彙整；跨 Chunk Map-Reduce 合成並對接甘特圖 Layout A。
- **2026-11-02 權益頁重大更新與雙按鈕（PR #40、PR #41）**：第四頁改為「重點總覽／聘任與給付／法規與保障／求助與自測」，頁首新增回饋與回報按鈕。
- **2026-11-02 原始來源逐項檢核閉包（PR #37、PR #38）**：485 個原始 URL 完整檢核，256 個可讀、111 個受限，57 個來源進待審建卡，累計 912 HTTP、模型 0。
- **2026-11-01 資訊鏈基線與甘特圖 Layout A（PR #31、PR #32）**：左欄選取管理與資格篩選，時間控制集中圖表工具列；甘特圖全局顯示已有名額範例。
- **2026-10-31 來源掃描與進階驗證防線（PR #24～#27）**：scanner-2 / document-ir-2 整合，15 項對抗測試，HTML 表格脈絡與局部重萃。
- **2026-10-30 候選審查工作台與雙軌模型架構（PR #20）**：候選預覽工作台、8 組 API 查核、排程維持 `model_mode=off`。
- **2026-10-29 MVP 介面與公開預覽啟動（PR #1、PR #2）**：建立四分頁原型與 GitHub Pages 自動部署流程。

</details>
