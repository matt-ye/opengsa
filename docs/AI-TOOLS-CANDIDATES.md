# 臺北／新竹AI工具補助：候選管線推進

基準：main 042fff5，PR #16～#19均已合併。本輪不再合併舊PR，而是建立新分支供覆核。10筆pilot與空的人工處置台帳保持不變；新增的是[data/candidates/ai-tools-115.json](../data/candidates/ai-tools-115.json)兩筆待審快照。

## 已完成

- 在來源台帳新增兩個公開正文profile：臺北`.wysiwyg .content`、新竹`#mainContainer`，具必要標記、HTTPS白名單與robots檢查；不登入、不下載申請表或PDF。本輪台帳16筆、11筆啟用、5筆停用。
- 專用確定性規則依正文取年度、一般／加額分支、地方及購買限制、兼領／重複補助、年度收件上限；分支標題與金額一起取證，避免把特定對象90%金額寫入一般青年。
- 新增研究工具分類、tool_subscription與local範圍；可認列支出的expense_period與申請起訖分開，候選轉pilot時保留。尚未將候選發布到第一至三頁。
- 沿用application_method的紙本／電子／親簽／收件判準。臺北只填正文確認的書面、送達；新竹填電子及親簽，紙本遞交仍未知。不把舊版紙本附件或8/14通道變更混入當期受理起日。
- 檢核新增分支／金額配對、缺分支覆蓋率、地方條件與年度截止缺漏、支出期間證據及倒置檢查。缺年度不以今天年份補值；缺購買日、條件完成日及經費狀態時，不因年度上限未到就回傳open。
- 候選來源、application_method、expense_period與證據納入覆核內容雜湊。N/A仍需明示依據；未抓到結果日期、未確認紙本遞交，均不能自動寫不適用。

新增的model_usage是既有scanner實際輸出的用量欄位，已補入候選根層Schema的選填型別，避免真實掃描bundle因該欄位而不合契約。這不授權啟用模型。

## 實際掃描與限制

最終候選生成該輪：4次HTTP（含兩份robots）、兩份HTML變更、模型0次、official_data_modified=false、promotion_ready=0。profile檢查及前一輪試跑另有請求，沒有混稱整輪只有4次。全部未使用API或付費服務，沒有原始文件長期存放。

兩筆檢核結果皆passed_with_gaps、errors為空；摘錄各113／110字。臺北年度上限2026/11/10，新竹2026/11/30；個人適用期限可能更早。本批皆unknown受理狀態，沒有自動核准P1（臺大職能治療博士五年級候選人）。P1尚缺年齡、設籍、購買、課程或其他特定條件，博士候選人身分不能替代。

新竹頁面同時列年齡修訂與出生日期區間，需人工核對採認基準；「線上送件」未直接證明後續核銷完全免紙本。臺北郵寄／親送的具體程序仍需補正式依據。這些待查事項沒有被N/A掩蓋。

可重現方式：先依data/scan-sources.json挑出taipei-ai-tools與hsinchu-ai-tools建立ignored work/中的局部config，再使用scanner原有參數：

```powershell
python scripts/scan_sources.py --config work/ai-tools-config.json --state work/ai-tools-state.json --output work/ai-tools-report
```

模型環境維持OPENGSA_MODEL_MODE=off。每次都應讀取報告的來源狀態、bundle_schema_errors及逐欄檢核；失敗不取代舊正式資料。只有重新完成獨立人工覆核、資料PR及Pages部署，卡片才會更新。

## 本輪驗收

依使用者順序執行Node、Python、資料檢查及`python scripts/build_site.py _site`。套件目前81項Python、37項Node；新增測試涵蓋：年度及金額變動、跨分支誤接、遺漏分支、支出／受理／通道修訂日分流、個人相對期限、缺年度不補猜、候選來源與摘錄上限。所有網路規則測試採明示合成內容，不偽造人工核准。

排程模型仍off；成本未知API仍catalog-only；hash_only不外送。候選JSON不在公開網站成品清單，正式pilot仍10筆，人工台帳無新增假覆核。
