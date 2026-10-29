# 公開來源自動掃描與結構化候選管線

2026-10-29使用者要求開始處理自動爬取，並進一步要求完成「爬取結果 → 結構化獎助資料 → 檢核 → 申請時間判斷 → 候選差異覆核報告」管線。本版實作公開GET、正文／文字PDF萃取、增量雜湊、記憶體內結構化萃取 (`scripts/extract_candidates.py`)、六面向獨立檢核 (`scripts/verify_candidates.py`)、學生窗口申請時間與 P1 資格判斷 (`scripts/evaluate_deadlines.py`)，以及候選差異覆核報告 (`scripts/review_candidates.py`)。模型 Adapter 預設關閉，且爬蟲或模型絕不直接覆寫 `data/pilot.json`。

## 已實作範圍

| 掃描目標 | 處理方式 | 限制 |
|---|---|---|
| 臺大博士生獎學金、研究生校長獎、國科會會議校內程序 | 教務處正文選擇器、必要標記、最多一份匹配辦法PDF、記憶體結構化拆分與檢核 | 教務處要求轉載先聯繫；本版只保留雜湊、欄位類型、URL與定位，零原文摘錄外流，且嚴格禁止送往外部模型 |
| 臺大遠學 | 正文分區、獨立下載區發現與一般補助結構化擷取 | 研發處robots禁止`/WebUPD/`，附件只報受限，不下載、不從殘句猜測附件內容 |
| 國科會研究生國際會議作業要點 | 法規正文容器、條款標記、事件相對規則與三層期限分流 | 法規變更只交待覆核，不自動認定修正日等於生效日或重算學生期限 |
| 傑出人才發展基金會出國開會 | 公開HTML、必要標記、會前兩個曆月機構期限與學生校內期限留未知 | 必要短證據每份合計最多120字，資格與機構／學生期限仍須人工核對 |

共六個正文目標，涵蓋原四組試點及新增FAOS。實際設定在[scan-sources.json](../data/scan-sources.json)；舊`examples/ingestion-sources.proposed.json`保留為歷史提案，不由程式載入。醫學院國際事務正文需動態渲染、FAO需登入，均列deferred，不假稱已支援。

## 如何執行及看結果

```powershell
python -m pip install -r requirements-dev.txt
python scripts/scan_sources.py
python scripts/review_candidates.py --candidates work/scanner/report/candidates.json --output-dir work/scanner/report
```

需Python 3.10以上及Node，CI使用Python 3.13／Node 24。網路採Node內建HTTPS單次GET，明確`rejectUnauthorized: true`，不設定忽略憑證或降級HTTP；Python負責解析、結構化萃取、獨立檢核與報告。Node與Python的憑證驗證實作不同，任一HTTPS驗證失敗皆轉錯誤，不以不驗證TLS作備援。

- 本機觀察狀態：`work/scanner/state.json`，只含雜湊、HTTP驗證資訊、附件清單與未覆核候選。它是上次觀察值，**不是上次核准資料**。
- 掃描與結構化覆核報告（位於 `work/scanner/report/`）：
  - `summary.md`、`scan-report.json`、`candidates.json`：每頁狀態、版權／robots限制、短證據或雜湊、正文區塊／PDF頁碼定位。
  - `structured-candidates.json`：依 [`schema/candidate.schema.json`](../schema/candidate.schema.json) (`1.0.0-candidate`) 產生的結構化候選（已拆分制度分支與學年度、附帶逐欄證據、獨立檢核結果與學生窗口時間狀態）。
  - `review-diff.json` 與 `review-summary.md`：分列（一）來源變更與上下文狀態、（二）結構化萃取結果、（三）獨立檢核與學生申請時間／P1資格判斷、（四）與 `data/pilot.json` 的欄位差異及 `data/scan-reviews.json` 人工處置狀態。
- GitHub：[Scan public sources](https://github.com/matt-ye/opengsa/actions/workflows/scan-sources.yml)可手動執行，也排定**臺北時間週二、週五09:17**低頻掃描。排程可能延遲或被平台停用，不保證即時通知。
- 每次執行的Summary可直接看掃描與候選覆核表，報告artifact保留14天；下載artifact需GitHub登入。沒有發Email、建立Issue、代送申請或自動合併資料PR。

首次建立基準會出現多份changed，單輪最多五份，因此可能需要再執行一次處理延後項目。這是首次觀察，不代表官方今天修改。未變更時仍檢查母頁的已知PDF（可用ETag／Last-Modified），同URL附件更新不會只因母頁未改就漏掉。

## 結構化候選欄位、獨立檢核與人工覆核

1. **記憶體內完整上下文 vs 無上下文退回 (`needs_context`)**：
   - `candidates.json` 僅保存短證據（每段 `<=50` 字、每份合計 `<=120` 字）或雜湊 (`hash_only`)，不足以單獨推導完整結構化欄位。
   - 因此 `scan_sources.py` 與 `review_candidates.py` 會在單輪允許範圍內使用記憶體中的完整區塊 (`in_memory_full_blocks`) 執行確定性規則解析；若在 `--no-refetch` 或來源失敗時無記憶體全文，萃取器會建立 `needs_context` 候選骨架，將未知欄位保留為 `null`／`unknown`，**絕不從雜湊或殘句猜測答案**。
2. **六面向獨立檢核 (`scripts/verify_candidates.py`)**：
   - 自動檢查：（1）`schema/candidate.schema.json` 格式、（2）逐欄證據支持与防模型捏造（且 `hash_only` 強制 `excerpt: null`）、（3）日期精度（`Asia/Taipei`、純日期不自造 `23:59`、法規修正日不自動當生效日）與金額單位完整性、（4）不同學年度或互斥分支（教育部 vs 國科會博獎、遠學一般 vs 配合補助）不混成單筆、（5）否定條件（非在職、不得重複請領）與申請角色分流（機關彙送日、學院推薦日不當學生截止日）、（6）來源衝突攔截。
   - **忽略 Agent 自信宣告**：即使模型 Adapter 注入 `self_verified=true` 或 `confidence=1.0`，檢核器一律忽略並強制剔除；未經非原編輯者 (`independent_reviewer != editor`) 人工覆核前，一律維持 `review.status = "pending"` 且 `promotion_ready = false`。
3. **人工覆核與處置台帳 (`data/scan-reviews.json`)**：
   - 處理完候選後，維護者在[scan-reviews.json](../data/scan-reviews.json)提交紀錄：`revision_id`、`action`（`noted`／`applied`／`dismissed`）、`reviewer`、`reason`、`reviewed_on`。
   - 只有通過自動檢核且完成非原編輯者獨立覆核的候選，才會由維護者另開資料 PR 更新 `data/pilot.json`。

## 存取、成本與失敗處理

- 每輪最多20次HTTP，包含robots、重新導向、重試及附件；每主機間隔至少3秒，同時只有一個請求。robots有更長Crawl-delay時採更長間隔。
- 僅設定中的HTTPS主機、標準443埠；逐次檢查重新導向。登入、名冊、獲獎名單、學號、身分證及帶token／session的連結不取回。
- 每輪重新取robots。404視為沒有提供規則，**不當成轉載授權**；403／429、5xx、無法解析或無法連線時停止該路徑。保守解析所有適用Disallow（支援星號與結尾符號），不自動使用Allow例外。
- 403／429暫停該主機，不換IP、登入、偽裝瀏覽器或用第三方代理繞過。5xx最多再試一次，若有Retry-After則留待下次，不立即重試。
- HTML上限2MB；PDF最多10MB／50頁，純記憶體抽字，子程序最長20秒。Linux子程序另限CPU與768MB記憶體；Windows沒有同等記憶體硬上限。加密、空文字、超限、掃描圖與解析問題轉人工，不做OCR。
- 新請求啟動預算180秒，每次請求另有23秒外部逾時；工作流程10分鐘上限。故障保留該文件先前狀態與未覆核候選，不當成下架或停辦。
- 不存原始HTML／PDF、不上傳原檔、無大量全文cache；raw資料只在處理記憶體。短證據跳過聯絡資料並限制長度，教務處只存雜湊且禁止送往外部模型。Cache及artifact不含學生個人條件。
- 模型 Adapter 預設關閉（呼叫0次），不使用私人API、Secrets、D1或付費擷取備援；無金鑰時以 `MockModelAdapter` 離線驗證。

## 驗證與維護

離線測試涵蓋四組各五種合成情境、正文範圍、下載區、文字PDF、附件同URL變更、條款／robots、304、白名單、限流、預算、故障保留、設定改版、cache遺失、處置去重，以及新增之候選 Schema、年度／梯次／分支拆分、學生與機關期限分流、否定資格、未知兼領、金額單位、事件相對日期（跨年／閏月／例假日待核）、證據不足不猜測、來源衝突、模型捏造攔截與 P1 博士五年級候選人情境。目前 **49 項 Python 測試與 23 項 Node 原型測試** 全部通過。

依據：[GitHub排程事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[Robots協定RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)、[教務處隱私與版權聲明](https://www.aca.ntu.edu.tw/w/aca/Privacy)、[pypdf抽字及記憶體說明](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)。
