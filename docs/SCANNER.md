# 公開來源自動掃描第一版

2026-10-29使用者要求開始處理自動爬取。本版實作公開GET、正文／文字PDF萃取、增量雜湊與待覆核報告；沒有接入模型，也不改寫網站正式資料。原[管線設計](INGESTION-POC.md)中完整資格結構化、獨立Agent、候選資料PR仍是後續工作，不能把關鍵字線索當完整申請資料。

## 已實作範圍

| 掃描目標 | 處理方式 | 限制 |
|---|---|---|
| 臺大博士生獎學金、研究生校長獎、國科會會議校內程序 | 教務處正文選擇器、必要標記及最多一份匹配辦法PDF | 教務處要求轉載先聯繫；本版只保留雜湊、欄位類型、URL與定位，不輸出原文摘錄 |
| 臺大遠學 | 正文分區及獨立下載區發現 | 研發處robots禁止`/WebUPD/`，附件只報受限，不下載 |
| 國科會研究生國際會議作業要點 | 法規正文容器及條款標記 | 法規變更只交待覆核，不自動認定生效或重算學生期限 |
| 傑出人才發展基金會出國開會 | 公開HTML與必要標記 | 必要短證據每份合計最多120字，資格與機構／學生期限仍須人工核對 |

共六個正文目標，涵蓋原四組試點及新增FAOS。實際設定在[scan-sources.json](../data/scan-sources.json)；舊`examples/ingestion-sources.proposed.json`保留為歷史提案，不由程式載入。醫學院國際事務正文需動態渲染、FAO需登入，均列deferred，不假稱已支援。

## 如何執行及看結果

```powershell
python -m pip install -r requirements-ingestion.txt
python scripts/scan_sources.py
```

需Python 3.10以上及Node，CI使用Python 3.13／Node 24。網路採Node內建HTTPS單次GET，明確`rejectUnauthorized: true`，不設定忽略憑證或降級HTTP；Python負責解析與報告。Node與Python的憑證驗證實作不同，任一HTTPS驗證失敗皆轉錯誤，不以不驗證TLS作備援。

- 本機觀察狀態：`work/scanner/state.json`，只含雜湊、HTTP驗證資訊、附件清單與未覆核候選。它是上次觀察值，**不是上次核准資料**。
- 報告：`work/scanner/report/summary.md`、`scan-report.json`與`candidates.json`。包含每頁狀態、版權／robots限制、短證據或雜湊、正文區塊／PDF頁碼定位。
- GitHub：[Scan public sources](https://github.com/matt-ye/opengsa/actions/workflows/scan-sources.yml)可手動執行，也排定**臺北時間週二、週五09:17**低頻掃描。排程可能延遲或被平台停用，不保證即時通知。
- 每次執行的Summary可直接看狀態表，報告artifact保留14天；下載artifact需GitHub登入。沒有發Email、建立Issue、代送申請或自動合併資料PR。

首次建立基準會出現多份changed，單輪最多五份，因此可能需要再執行一次處理延後項目。這是首次觀察，不代表官方今天修改。未變更時仍檢查母頁的已知PDF（可用ETag／Last-Modified），同URL附件更新不會只因母頁未改就漏掉。

## 候選欄位與覆核

每份候選保留source_id、URL、觀察時間、parser及設定雜湊、原始與語義雜湊、短證據／雜湊與定位。`facts`只分類期限、資格、金額、兼領及版本字句；`normalized_value`一律null、`review_status=pending`、`extraction_scope=keyword_evidence_only_not_complete_record`。不從一句日期猜學生截止，也不將新舊年度、金額或分支合成一筆。

逐筆開啟官方來源並核對年度、梯次、適用身分、各層送件及兼領；必要時由另一位覆核者查核。人工把可靠資料另作正式資料PR，本掃描器不執行該步。

處理完候選後，在[scan-reviews.json](../data/scan-reviews.json)提交紀錄：revision_id、action（noted／applied／dismissed）、reviewer、reason、reviewed_on。這是維護者提交的處置紀錄，不是掃描器給的核定；applied代表人員已另行處理資料，不會觸發自動套用。下次執行才將相同候選移出待辦，cache遺失重建時也不重複送同一revision。

待覆核佇列最多24份，滿時停止新增掃描並提示，不自動捨棄舊候選。狀態使用GitHub Cache減少重複工作；Cache可能過期／被逐出，非永久資料庫，遺失時報`baseline_missing`並重新觀察，不能用它承諾完整歷史版本。正式核准資料與處置紀錄才由Git保存。

## 存取、成本與失敗處理

- 每輪最多20次HTTP，包含robots、重新導向、重試及附件；每主機間隔至少3秒，同時只有一個請求。robots有更長Crawl-delay時採更長間隔。
- 僅設定中的HTTPS主機、標準443埠；逐次檢查重新導向。登入、名冊、獲獎名單、學號、身分證及帶token／session的連結不取回。
- 每輪重新取robots。404視為沒有提供規則，**不當成轉載授權**；403／429、5xx、無法解析或無法連線時停止該路徑。保守解析所有適用Disallow（支援星號與結尾符號），不自動使用Allow例外，因此可能比網站允許範圍更保守。條款限制另依來源設定處理。
- 403／429暫停該主機，不換IP、登入、偽裝瀏覽器或用第三方代理繞過。5xx最多再試一次，若有Retry-After則留待下次，不立即重試。
- HTML上限2MB；PDF最多10MB／50頁，純記憶體抽字，子程序最長20秒。Linux子程序另限CPU與768MB記憶體；Windows沒有同等記憶體硬上限。加密、空文字、超限、掃描圖與解析問題轉人工，不做OCR。
- 新請求啟動預算180秒，每次請求另有23秒外部逾時；工作流程10分鐘上限。故障保留該文件先前狀態與未覆核候選，不當成下架或停辦。
- 不存原始HTML／PDF、不上傳原檔、無大量全文cache；raw資料只在處理記憶體。短證據跳過聯絡資料並限制長度，教務處只存雜湊。Cache及artifact不含學生個人條件。
- 目前模型呼叫0次，不使用私人API、Secrets、D1或付費擷取備援。GitHub公開repo的Actions與額度仍依帳號／平台條款，不承諾永遠免費。

網站來源、PDF及任何疑似指令都只是資料；沒有exec、動態工具調用或LLM執行權。Markdown報告跳脫HTML及表格分隔，避免來源字串被當成頁面標記。

## 驗證與維護

離線測試涵蓋四組各五種合成情境，以及正文範圍、下載區、文字PDF、附件同URL變更、條款／robots、304、白名單、限流、預算、故障保留、設定改版、cache遺失及處置去重。37項Python測試與23項原型測試通過；live試跑結果另見PR及Actions紀錄。

每次新增來源先調整白名單、選擇器、必要標記、附件規則與權利模式，再加離線測試及小量實測。選擇器／設定雜湊改變會強制重取並產生新版候選，不沿用304繞過新檢查。

要停止排程，停用此workflow或刪除schedule；公開預覽的`pages.yml`保持獨立。恢復時先人工檢查來源條款與實測。請勿為了讓檢查全綠而刪除必要標記或放寬robots。

依據：[GitHub排程事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[Robots協定RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)、[教務處隱私與版權聲明](https://www.aca.ntu.edu.tw/w/aca/Privacy)、[pypdf抽字及記憶體說明](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)。
