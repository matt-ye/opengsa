# 公開來源掃描與候選覆核

2026-11-01全來源第一輪另見[擴展結果與重現方式](SOURCE-EXPANSION-RUN.md)：367原始URL均有處置，56新子來源、22份待審快照，634HTTP／模型0。原19筆正式候選池與16個排程profile不變，新profile停用；擴展資料在`data/source-expansion/`，不自動進公開網站。新增`expand_sources.py`有界續跑與`propose_radar_update.py`離線資料patch／三頁預覽；scan完成後保留14天提案artifact，權限仍唯讀，不自動開、合併或發布資料PR。下列19筆數字為既有基線。

2026-11-01最新：19筆以extractor-1.5.0完整重萃，12筆自動檢核通過、7筆有缺漏，仍全部pending；新增通用指令、`--full-replay`及隔離外部驗證。來源profile仍16筆／13啟用，未增加正式排程目標。[最新結果與限制](GENERALIZABLE-EXTRACTION.md)優先於下列歷史階段描述。

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

成卡門檻（萃取器 1.11.0，2026-11-08 使用者決定網站上的卡都要能由流程產出）：頁面標題要看得出是獎助方案，內文要有申請資格或申請對象的句子。獎學金來源只認獎學金類字眼和碩博士在學資格，維持原規則；急難救助、中小學與家庭來源（`living`）另認急難、慰助、濟助、助學金、就學金、扶助、幼兒園等字，資格認家戶或學生身分的申請對象句；學生優惠來源（`ai`）標題提到學生或教育就算，資格找學生加上免費、折扣、驗證等字，找不到時以寫明對象的頁面標題為據，卡片寫「適用對象與驗證方式請看來源」。只有學生優惠來源會把頁面標題當成可引用的區塊，其他來源的版本雜湊不變。附件表格、說明表、QA 與資源列表不成卡；同站同標題（忽略開頭年度）只留網頁那張。

萃取器 1.12.0 再提高適應性：
- **標題：** 從 h1、`og:title`、`<title>` 依序取第一個看得出是方案的。都看不出時，找「名稱：」「福利名稱：」這類欄位，短名稱附上網站名稱。學生優惠頁有多個候選小標題時，取重複出現最多的那個，接在產品名後面。
- **資格：** 寫在「申請資格」小標題下的段落也算。`living` 來源也認「得…申請」「向區公所申請」的寫法。獎學金來源也認大學部學生、醫學生和英文的 eligible students。
- **索引頁：** `living` 與 `ai` 來源的頁面本身寫了申請對象，就不因導覽列有獎學金連結而被當成索引頁。
- **標題清理：** 去掉表情符號、檔案編號（01-1、02_）和結尾日期（115.6.30）。
- **不成卡：** 只寫類別的標題（「急難救助」）、切結書與應繳文件說明。
- **同站去重：** 一個標題包含另一個時視為同一方案。
- **金額：** 單位分不清（例如「至多 50,000 元」沒寫一次或每月）時不填，避免整張卡被檢核擋下。

時間與資格分開：缺必要學校、候選人或年級條件時不當符合；未結構化限制仍需人工核對。網站依臺北今天重算可確認窗口，舊快照的open不直接冒充今日開放；推定／未知起日不當正式開放日。結果確定程度、補送角色、結構化金額、國籍／就業／否定條件在候選轉pilot時保留。

## 自動開資料 PR

`scripts/open_data_pr.py` 把提案變成資料 PR，由 `scan-sources.yml` 和 `source-intake.yml` 的 `data-pr` job 執行，只有這個 job 有寫入權限。檢查階段不帶權杖；提案只能改 `data/` 和 `docs/source-chains/`；只推 `data/` 開頭的分支；不會合併，合併才是上架。公開提交的新網域不進 `allowed_hosts`，要排程巡檢由維護者另外加。

巡檢範圍（2026-11-08 使用者決定網站上的卡要持續巡檢）：
- 網域已在 `allowed_hosts` 的新卡，來源在提案時就直接啟用，跟著排程輪流巡檢。
- 新網域的來源維持停用，等維護者把網域加進 `allowed_hosts`。
- 同一網址已有啟用的來源時不重複啟用。
- `tests/test_scan_coverage.py` 檢查網域已核可的每張流程卡都在巡檢中。

每輪最多 5 份變動文件，所以第一次巡完約 200 個來源要約 40 輪。之後沒變動的來源會很快略過。

repo 設定 `can_approve_pull_request_reviews` 關閉時 Actions 開不了 PR，會改留比較連結，由維護者自己開（這樣 CI 也會跑）。

通知走固定的「待審資料收件匣」Issue（2026-11-08 使用者決定，只用於排程掃描）：每輪有新提案或提案沒過檢查時，bot 在這張 Issue 留言，內容是 PR 連結或比較連結加上提案摘要。留言才會推播，改 Issue 內文不會。第一次開 Issue 時提及 repo 擁有者，擁有者就會自動訂閱。沒有提案或沒有變動時不留言。流程是：手機收到推播，點連結開 PR，CI 跑完，看過後合併。

## 上架與駁回（2026-11-08 使用者決定）

提案前會去掉重複：同一份文件只留一張，同網站同標題只留一張；標題只是頁面或專區名稱、條文片段、心得或得獎名單的不成卡，申請表、報告書、流程圖與修正對照表也不成卡。這些都列在提案摘要的 `dropped_not_distinct`。

通用萃取路徑不認識文件結構，只填分得清的值，其他留白讓讀者看來源：整份文件只有一個像獎助的金額才填（捐款、基金、所得上限不算）；文件也提到大學或高中職時不填學制；提到外籍生或僑生時不填國籍。分類也不預設成博士：標題明說只給博士才歸博士研究，提到急難或出國研修的各歸其類，其他獎學金歸生活／學費。公告標題會去掉網站名稱、公告分類和轉知字樣，截止日留著。

- **未審的卡直接上網站**，重點是快。卡片列出來源；不確定的欄位不猜，連到來源網站。
- **駁回的卡下架**：`python scripts/dismiss_candidate.py --candidate-id ... --reason ... --problem-source extraction`。寫進台帳後，網站與 RSS 下一次建置就不顯示。卡片留在候選檔，原因和 `problem_source`（`source_page`、`extraction`、`wrong_url`、`not_a_program`、`other`）留在台帳，之後用來改進萃取腳本。
- **目前只有 repo owner 核准提交與駁回。** 讓核准更方便是未來規劃，這輪不做。

## 人工台帳與PR匯出

[data/scan-reviews.json](../data/scan-reviews.json)依[台帳Schema](../schema/scan-reviews.schema.json)版本1.1.0驗證。目前正式reviews為空；舊合成紀錄已移入明示測試fixture。

每筆處置需revision_id、source_id、action、reviewer、reason、reviewed_on；action為noted／dismissed／applied；dismissed可另記problem_source。日期有效且不可在未來，覆核者需不同於原編輯者。applied另需candidate_id及candidate_sha256（由scripts.review_candidates.candidate_fingerprint計算），綁定實際候選內容；錯來源、缺日期、改內容、只有gaps或無上下文不核准。

noted／dismissed是文件層級佇列處置；帶candidate_id的處置只影響該候選，不清整份文件。applied不自動清除同一文件其他分支，須完成全文件判讀後另以文件層級處置結案。

`review_candidates.py --export-pr-draft work/reviewed-pilot.json`只匯出經完整自動檢核及獨立人工核准、內容雜湊相符者；禁止直接覆寫data/pilot.json。候選與資料集as_of不同時拒絕匯出，須明確更新整體快照與受理狀態，不能把新觀察日期改成舊快照日。資料PR仍由維護者審查，不自動建立或合併。

## 排程與失敗保留

- Actions週一至週六09:17（臺北），GitHub不保證準時；main手動scan可執行，模型預設off。Pages部署另由pages.yml執行，PR只離線檢查及建置，不取得來源Secrets。
- 每輪最多50次HTTP（2026-11-08使用者決定的暫時值，原為20；含robots／轉向／重試／附件）、5份變更、24份待審；至少3秒主機間隔、一次一請求。待審滿只擋新增，其他來源照常檢查，該文件下一輪仍算變更；不覆蓋未審候選；已進資料庫的版本自動離開佇列；同一網址出現新版本時，新版本取代舊版本。當輪抽好的結構化候選（不是原文）存在 state，下一輪直接沿用；還沒抽到的項目在保留的 6 次請求與 30 秒內重抓，3 次都抽不到就移出佇列並忘掉雜湊，下次輪到重新當成變更，內文已改就等掃描產生新版本。時間紀錄用同一份內文當輪產出（`temporal-records.json`），和卡片一起進提案，不多發請求；手動 `temporal_replay` 仍用來重查舊卡。
- HTTPS白名單逐次檢查重新導向、TLS正常驗證；不登入、不下載名單或帶session／token連結。robots每輪重查，404不等於轉載授權；禁止路徑不以代理、換IP或偽裝瀏覽器繞過。
- 連續失敗的來源輪到時略過（第1次失敗不略過，之後1、3，最多4次），略過不花請求，成功即清除；只有真的花了請求而失敗才計入。連續失敗3次以上列在報告上提醒。傳輸失敗重試後當輪暫停該主機。
- 403／429暫停主機；傳輸失敗／5xx共用最多一次重試，Retry-After延後下輪。HTML上限2MB；PDF10MB／50頁，文字抽取20秒；Linux子程序限CPU／768MB，Windows無相同記憶體硬上限。加密、掃描圖或解析問題轉人工，不做OCR。
- 新請求啟動預算180秒、單次逾時23秒、workflow10分鐘。故障保留舊正式資料及候選，不當停辦。舊版雜湊或304沒有完整原文可用時，不重新宣稱內容通過。

離線測試與建置指令見[資料契約](DATA-CONTRACT.md)；本輪驗收見[可靠性紀錄](RELIABILITY-AUDIT.md)。依據：[GitHub排程事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[RFC9309](https://www.rfc-editor.org/rfc/rfc9309.html)、[教務處聲明](https://www.aca.ntu.edu.tw/w/aca/Privacy)、[pypdf限制](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)。

## 申辦方式與欄位適用性更新（2026-10-30）

候選及pilot新增application_method與field_applicability，紙本遞交、親簽上傳及截止判準分開。N/A須有理由、引用及完整上下文；缺來源仍待確認，不以N/A隱藏日期或必要資格。第二頁顯示整體與各步驟方式，第三頁同步給付摘要及申辦方式；覆核與資料PR部署後才更新公開內容。詳見[判斷與更新流程](APPLICATION-PROCESS.md)。

## 地方AI工具補助候選

臺北／新竹兩個公開正文profile及具名候選已接入，僅規則萃取、不修改pilot。購買／訂閱支出期間與申請期限分開，年度上限不代表個人仍可申請；分支與缺漏需覆核。細節見[候選推進](AI-TOOLS-CANDIDATES.md)。


## 來源資訊鏈的手動掃描（PR31）

`data/source-chain-sources.json`為有限補鏈配置，`data/source-chains.json`為待審文件／關係／事件快照，依`schema/source-chains.schema.json`驗證；不修改既有完整候選／正式pilot。HTML／文字PDF已支持，其他格式與未讀連結明示延期；全文不存repo，hash_only沒有摘錄。新手動operation=source_chains無Secrets／模型，不自動回存或發布。地方／梯次、實際／歷史／預估分別呈現，完整說明見[SOURCE-CHAINS-AND-TIMELINE.md](SOURCE-CHAINS-AND-TIMELINE.md)。

## 來源狀態檔（status/）

排程掃描後，`status` job 會把每個來源的狀態寫成 `status/pipeline.csv` 和 `status/pipeline.json`。兩份資料相同，只是格式不同，正在並行比較哪種比較好用。

- CSV 一列一個來源，欄位有 `source_id`、`host`、`enabled`、`status`、`failures`、`pending`、`attachments`、`revision`。`status` 的值是 `ok`（上次讀到）、`not_checked`（還沒輪到）、`disabled`，或上次失敗的原因。
- JSON 多了完整網址，還有資訊鏈：每個來源連到的附件，各自的狀態與內容雜湊。
- 檔案裡沒有執行時間，只有內容雜湊的前 12 碼。來源沒有變，檔案就不會變，也就不會產生提交。
- 這兩個檔案只由 bot 寫入，人工修改會在下一輪被蓋掉。用 `GITHUB_TOKEN` 推送的提交不會觸發網站重新部署。
- GitHub 只把 512 KB 以下的 CSV 顯示成表格。實測 269 個來源時，CSV 是 17 KB（每列約 64 位元組），JSON 是 76 KB（每個來源約 284 位元組）。照這個比例，1000 個來源大約是 CSV 65 KB、JSON 290 KB。
