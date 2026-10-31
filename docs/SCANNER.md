# 公開來源掃描與候選覆核

> 後續整合更新：本批已接上統一文件準備、Token預算分段及局部規則重萃，現行能力／未完成項目與實際驗收見[文件準備整合](PREPARED-EXTRACTION.md)。舊階段提案或測試數量不代表最新整合狀態。

PR #20 已合併；具名候選新增[審查工作台與資料 PR 草稿](REVIEW-WORKSPACE.md)。Actions `operation=review_workspace` 僅產生 repo 候選池的離線審查 artifact，與 `scan`／`provider_audit` 分流；不重新抓來源、不注入金鑰或模型，不改變原有低頻掃描排程。重新核驗及意向匯出由本機 CLI 執行。

更新：2026-10-30，以PR #20合併後狀態及本輪審查工作台為基準。有限公開GET、增量差異、規則萃取、可選手動LLM、獨立檢核、申請時間及P1資格比對已串接。**只產生待覆核報告，不直接改寫網站資料**。模型排程固定off；API設定、觀察值及限制見[API查核](API-AUDIT.md)。

## 來源台帳與最近實測（2026-10-31）

[scan-sources.json](../data/scan-sources.json)共16個profile：13啟用、3停用。最新實掃將13個來源17份文件整理為19筆待審候選，12 passed_automated_checks、7 passed_with_gaps，0人工核准。[完整來源驗收與成本](SOURCE-COVERAGE-AUDIT.md)、[145個網址逐項清單](SOURCE-LINKS-2026-10-31.md)。

| 群組 | 狀態 |
|---|---|
| 臺大博士獎學金、校長獎、TA | 正文及允許PDF可處理，教務處hash_only；公告／辦法／年度申請說明分開。博士申請附件部分年度與給付對象仍待核 |
| 臺大遠學 | 正文可解析，/WebUPD/附件受限，coverage明確保留缺漏 |
| 國科會會議、千里馬、研究人力 | 正文可解析；專任學歷級別、每月最低標題與金額聯合取證，不當全體學生普遍給付 |
| FAOS | 本輪成功；機關期限與學生期限分開，缺個人會議日期不當開放 |
| 中研院候選人 | 官方公告修復失效網址，限定人社計畫；完整金額及各所截止待核 |
| 電資學院 | 官方連結的primary PDF已啟用；制度快照，必要給付欄位有缺漏 |
| 臺北／新竹AI工具 | 正文與程序解析，個人條件、受理狀態與來源缺漏分開；新竹年齡採認疑點保留 |
| 台積電、工學院、兼任上限表 | 分別403、robots非有效規則、/WebUPD/禁止，三個profile保持停用 |

生輔組robots無有效規則，使用者確認無另行授權，維持人工查核；FAO不帶登入session掃描。首頁／索引完成連結發現不代表下層方案全部接入。舊輪觀察值保留於可靠性及AI工具候選文件，不作為本輪全部來源可用的保證。

primary PDF宣告format=pdf；附件候選另需parent_url及profile的known_attachment_urls，覆核時仍須從當次父頁重新發現並通過robots。PDF相容字NFKC正規化，無OCR或全文長期保存。來源的hash_only仍不得外送模型。

## 執行與輸出

需Python 3.10以上、Node；CI使用Python 3.13／Node24。

```powershell
python -m pip install -r requirements-dev.txt
python scripts/scan_sources.py --check-config
python scripts/scan_sources.py
python scripts/review_candidates.py --candidates work/scanner/report/candidates.json --output-dir work/scanner/report
```

`--check-config`離線驗證來源預算、啟用項目必要設定／唯一URL及處置台帳；不連網、不寫檔。真實掃描才讀取robots與允許的HTTPS目標。

- `work/scanner/state.json`：觀察雜湊、HTTP驗證資訊、附件清單、待審佇列及下一輪來源游標；不是正式核准資料。變更／請求預算用完會輪替，避免永遠只掃前幾頁。
- `scan-report.json`／`summary.md`：各文件狀態與失敗原因；`candidates.json`：來源變更線索。
- `structured-candidates.json`：有版本候選Schema、逐欄證據、金額／資格／日期與檢核結果。
- `review-diff.json`／`review-summary.md`：來源上下文、候選內容、學生及上層期限、P1（臺大職能治療博士五年級候選人）比對、與pilot差異及人工處置。
- `model-usage.json`：外部呼叫、tokens、快取及hash_only外送0 bytes等統計。

檔案均在ignored work/；Actions只上傳報告artifact14天、cache觀察狀態。原始HTML／PDF只在記憶體，不進Git、Pages或artifact。個人研討會及資格輸入不進scanner。

## 萃取、日期與檢核

完整原文於記憶體依HTML／PDF取得，再規則優先萃取；不以profile預填當年度日期、金額、年級或可兼領。只有常態月日時不展開成今年，修正日不等於生效日，機構／學院送件日不等於學生期限。缺完整上下文時維持unknown／needs_context；既有拒絕不能因重新驗證洗成通過。原始內容版本已不同時要求重新掃描，不沿用舊核准。

候選契約為1.1.0-candidate；獨立檢核包括Schema、證據、日期／金額單位、年度分支、否定條件／角色、衝突及coverage。起日、結果與截止日均需逐欄依據與年度錨點；passed_with_gaps不具正式匯出資格。模型自稱核准或信心分數無效；模型交叉盤查不取代獨立人工覆核。

對short_excerpt，每份來源revision的各分支合計最多120字證據／audit引文；超出欄位降為hash_only，保留定位及原區塊雜湊，需回來源覆核。hash_only來源則所有欄位無原文，禁止送任何外部API。兩種限制只針對證據摘錄，不等於原創摘要或結構化數字可以不查證。

時間與資格分開：缺必要學校、候選人或年級條件時不當符合；未結構化限制仍需人工核對。網站依臺北今天重算可確認窗口，舊快照的open不直接冒充今日開放；推定／未知起日不當正式開放日。結果確定程度、補送角色、結構化金額、國籍／就業／否定條件在候選轉pilot時保留。

## 人工台帳與PR匯出

[data/scan-reviews.json](../data/scan-reviews.json)依[台帳Schema](../schema/scan-reviews.schema.json)版本1.1.0驗證。目前正式reviews為空；舊合成紀錄已移入明示測試fixture。

每筆處置需revision_id、source_id、action、reviewer、reason、reviewed_on；action為noted／dismissed／applied。日期有效且不可在未來，覆核者需不同於原編輯者。applied另需candidate_id及candidate_sha256（由scripts.review_candidates.candidate_fingerprint計算），綁定實際候選內容；錯來源、缺日期、改內容、只有gaps或無上下文不核准。

noted／dismissed是文件層級佇列處置；帶candidate_id的處置只影響該候選，不清整份文件。applied不自動清除同一文件其他分支，須完成全文件判讀後另以文件層級處置結案。

`review_candidates.py --export-pr-draft work/reviewed-pilot.json`只匯出經完整自動檢核及獨立人工核准、內容雜湊相符者；禁止直接覆寫data/pilot.json。候選與資料集as_of不同時拒絕匯出，須明確更新整體快照與受理狀態，不能把新觀察日期改成舊快照日。資料PR仍由維護者審查，不自動建立或合併。

## 排程與失敗保留

- Actions週二／五09:17（臺北），GitHub不保證準時；main手動scan可執行，模型預設off。Pages部署另由pages.yml執行，PR只離線檢查及建置，不取得來源Secrets。
- 每輪最多20次HTTP（含robots／轉向／重試／附件）、5份變更、24份待審；至少3秒主機間隔、一次一請求。待審滿則停新增，不覆蓋未審候選。
- HTTPS白名單逐次檢查重新導向、TLS正常驗證；不登入、不下載名單或帶session／token連結。robots每輪重查，404不等於轉載授權；禁止路徑不以代理、換IP或偽裝瀏覽器繞過。
- 403／429暫停主機；傳輸失敗／5xx共用最多一次重試，Retry-After延後下輪。HTML上限2MB；PDF10MB／50頁，文字抽取20秒；Linux子程序限CPU／768MB，Windows無相同記憶體硬上限。加密、掃描圖或解析問題轉人工，不做OCR。
- 新請求啟動預算180秒、單次逾時23秒、workflow10分鐘。故障保留舊正式資料及候選，不當停辦。舊版雜湊或304沒有完整原文可用時，不重新宣稱內容通過。

離線測試與建置指令見[資料契約](DATA-CONTRACT.md)；本輪驗收見[可靠性紀錄](RELIABILITY-AUDIT.md)。依據：[GitHub排程事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[RFC9309](https://www.rfc-editor.org/rfc/rfc9309.html)、[教務處聲明](https://www.aca.ntu.edu.tw/w/aca/Privacy)、[pypdf限制](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)。

## 申辦方式與欄位適用性更新（2026-10-30）

候選及pilot新增application_method與field_applicability，紙本遞交、親簽上傳及截止判準分開。N/A須有理由、引用及完整上下文；缺來源仍待確認，不以N/A隱藏日期或必要資格。第二頁顯示整體與各步驟方式，第三頁同步給付摘要及申辦方式；覆核與資料PR部署後才更新公開內容。詳見[判斷與更新流程](APPLICATION-PROCESS.md)。

## 地方AI工具補助候選

臺北／新竹兩個公開正文profile及具名候選已接入，僅規則萃取、不修改pilot。購買／訂閱支出期間與申請期限分開，年度上限不代表個人仍可申請；分支與缺漏需覆核。細節見[候選推進](AI-TOOLS-CANDIDATES.md)。
