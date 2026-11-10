# 候選出處查核（2026-11-07）

> 獨立代理的唯讀查核。先看「程式審查」的結論，再看各批次細節。

## 程式審查

## OpenGSA 管線出處審查（唯讀）

範圍：`D:\Codex_Projects\OpenGSA-wt-roster`（HEAD f61221a，另有未追蹤的 `scripts/verify_candidate_sources.py`、`tests/test_verify_candidate_sources.py`）。未連網、未改 repo、未動 git。

方法：讀 workflow 與程式碼；對真實 `data/` 跑規則；以 mock transport 跑真實的 `scan()`、`html_document()`、`refetch_and_extract_candidates()`、`build_review_report()`、`write_proposal()`（僅寫到 scratch）。腳本在 scratch：`rules.py`、`rules2.py`、`led1.py`、`sim.py`、`sim2.py`、`sim3.py`。也實跑了 `check_data.py`、`scan_sources.py --check-config`、`verify_candidates.py`（三者都不寫檔）。未跑完整 unittest。

候選分類沿用 `candidate-provenance.md`：手寫 190 筆（enterprise 85、k12 25、perks 28、medical 2、emergency 18、topology 8、university 24），萃取 66 筆（source-review 64、ai-tools-115 2）。

### 結論

1. 沒有任何 CI 步驟把候選內容或雜湊與來源比對。**repo 既有的 `scripts/verify_candidates.py` 離線重跑就會擋下這批資料**（enterprise、medical CLI 實跑 exit 1；source-review exit 0），但它不在 CI 內。規則層：189/190 手寫報錯，66 筆萃取 0 誤判。
2. 離線沒有「真實萃取的證明」，只有弱交叉證據：候選 revision 能否在其他已提交的抓取台帳找到。手寫 190 筆命中 0；source-review 64/64 命中；ai-tools 1/2 命中。台帳本身也是提交進 repo 的資料，原文未存，雜湊無法重算。
3. 自動掃描**無法**更新 190 筆手寫資料。scan 只提案併入 `source-review.json`；`temporal_replay` 只讀 `source-review.json`。排程會在 5 次成功後卡死在 `review_backlog_full`（模擬值，前提見 F3）。
4. `all_pending`、`track:all` 目前是 no-op：0 來源、0 HTTP。

### 發現（嚴重度由高到低）

#### 已確認

**F1. CI 沒跑證據驗證，只驗形狀與自報值｜信心：高**
- `.github/workflows/pages.yml:31-32,34,36,39,41`：CI 只跑 `check_data.py`、`scan_sources.py --check-config`、unittest、node test、`build_site.py`、`build_review_workspace.py`。`verify_candidates.py` 不在其中（`grep` workflow、`check_data.py`、`build_site.py` 皆無）。
- 實測：`python scripts/verify_candidates.py data/candidates/enterprise-scholarships.json` 得 85/85 `failed_automated_checks`、exit 1（`verify_candidates.py:838-839`）；`medical-scholarships.json` exit 1；`source-review.json` exit 0。
- 情境：任何代理手寫一份 bundle，CI 全綠，push main 即部署（`pages.yml:43,49`）。

**F2. 候選閘門的每一項都只看形狀或自報值｜信心：高**

| 檢查 | 位置 | 實際驗什麼 | 為何沒擋 |
|---|---|---|---|
| Schema | `check_data.py:102-104`；`schema/candidate.schema.json` | revision_id 只要非空字串；雜湊只要 64 hex；`extraction_method` 是 enum；`verification` 由資料自帶 | 編造值合規 |
| 來源 profile 綁定 | `check_data.py:109-112` | sid 在 `scan-sources.json`、URL 相符 | 登記簿由同一批 builder 自己寫（`build_topology_discovered_bundle.py:145-146`、`build_emergency_relief_expansion.py:720`、`build_taiwan_universities_expansion.py:1212`）。137 個通用 profile 使這項成立 |
| evidence_mode、摘錄額度 | `check_data.py:114-118,121-125` | 每 revision 摘錄不超過 120 字 | 每筆一個編造 revision，額度形同不存在 |
| 重複 id、promotion_ready | `check_data.py:119-120,123` | 唯一性、未宣稱核准 | 不涉出處 |
| excerpt 雜湊 | 只在 `verify_candidates.py:284`，`check_data` 沒有 | - | 9 筆（enterprise 7、perks 2）excerpt_sha256 連自身摘錄都對不上，照樣上線 |
| 時間觀察 | `check_data.py:138-140`；`time_policy.py:66-91` | 只驗 source-review 一份；`http_requests` 為 0 合法（`time_policy.py:72`）；雜湊只驗 regex（`:39,:43`）；attempted_urls 不需含該筆 URL | 8 份其他觀察檔 `check_data` 不驗 |
| 指紋不符 | `time_policy.py:82-83` | `continue`，靜默跳過 | topology 8 筆指紋全錯（`build_topology_discovered_bundle.py:193` 自造雜湊）也零錯誤 |
| 網站建置 | `build_site.py:90` | 同 `validate_candidate_snapshot` | 同上 |
| 不安全判定 | `time_policy.py:19-25`、`radar_metadata.py:37-48` | 讀資料自帶的 `verification.checks`、`field_evidence` | 手寫 190 筆 unsafe=0；`known.benefit` 164 筆、`known.audience` 26 筆被當成已知 |

`check_data.py:166-167` 自己就印「schema/source/excerpt bounds only」，這不是隱藏缺陷而是 CI 從未補上下一層。

驗證器本身無 blocks 時也驗不了內容（`verify_candidates.py:291,297-319` 的 block 比對只在 `in_memory_blocks` 存在時跑），repo 不存原文，所以連它也只能驗內部一致性。

**F3. 排程掃描會永久卡死在待審上限｜信心：高（程式行為與模擬）；現況未確認（快取看不到）**
- `scan_sources.py:360`：沒看過的文件一律 `changed`（`baseline_missing` 只是報告欄位，`:388`），每筆都進 pending（`:370-371`）。
- `scan_sources.py:332-333`：pending ≥ 24 時，每個來源在送請求前就丟 `review_backlog_full`。
- `scan_sources.py:380`：這個狀態不設 `deferred_index`；`:504-505`：無成功文件則 exit 1。
- 解除途徑只有一條：在 `data/scan-reviews.json` 提交文件層級處置（`:457-462`），帶候選層級或 `applied` 的不算（`:458`）。目前 reviews 為 0 筆。
- 模擬（空狀態、無人審）：run 1-5 待審 5、10、15、20、24；run 6 起 HTTP 0、182 個來源全 `review_backlog_full`、exit 1。只碰過 24/182 個來源。

**F4. 排程與 replay 都碰不到 190 筆手寫資料｜信心：高**
- 寫入端：scan 只寫 `work/`（`scan_sources.py:465-472,492-497`），`official_data_modified` 寫死 False（`:390`）；`propose_radar_update.py:23,35` 只產 `data/candidates/source-review.json` 的提案，輸出在 artifact，不 commit（`.github/workflows/scan-sources.yml:196-204`，權限 `contents: read`，`:58-59`）。
- replay 讀取端：`temporal_reextract.py:444,548`、`run_temporal_action.py:114` 都寫死 `source-review.json`；`run_temporal_action.py:39-41` 拒絕其他 bundle 的 source id。
- emergency 18、medical 2 的 profile 是 `enabled:false`，scan 也不讀（`scan_sources.py:318`）。
- 所以：手寫資料**沒有任何自動路徑會被取代**。就算人工套用提案，也只是在 `source-review.json` 新增，手寫卡片留著，同一 URL 兩張卡（`build_site.py:50-51` 直接串接，且 id 不同不觸發重複檢查）。

**F5. 通用 profile 的產出不可用，且錯誤值能通過驗證｜信心：高（程式行為）；真實網站比例未確認（合成頁）**

`scan_sources.py:205`：`pdf_include: []` 使 `any()` 恆假，加上 `max_pdfs: 0`（`:276`），永遠不追 PDF。`:271`：`required_markers: []` 時只要文字 ≥ 80 字就過。`body_selector: body`：只移除 script/style/nav/footer/form/noscript（`:212`），`div` 類的頁首、側欄都留下。`extract_candidates.py:2887-2929` 的通用分支：標題來自 profile、identity 是 placeholder（`:2919`）、學生步驟固定 unknown。

合成頁實測（profile 用 `perk-tableau-for-students`）：

| 頁面 | scan 狀態 | verification | 抽到的值 | 提案是否接受 |
|---|---|---|---|---|
| 公告頁：正文 20,000 元、申請 115/10/1-11/30；側欄另一方案 8,000 元、截止 113/10/31 | changed | passed_with_gaps | **金額 8,000（側欄，錯）**；截止 2024-10-31（側欄）與 2026-11-30，actor 都是 `unit`；學生截止 unknown；起日 None；identity placeholder | 是 |
| 基金會首頁（無獎助內容） | changed | passed_with_gaps | 全 unknown | 是 |
| 軟 404（HTTP 200「頁面不存在」） | changed | passed_with_gaps | 全 unknown | 是 |
| 登入牆 | changed | passed_with_gaps | 全 unknown | 是 |
| 多方案索引表 | changed | passed_with_gaps | 金額 30,000（第一列）；兩個日期掛同一筆 | 是 |
| JS 空殼 | required_marker_missing | - | - | - |

結論：通用 profile 只能產生「頁面可讀」訊號。正確情況下學生欄位幾乎全空；有內容時會把鄰近文字綁到 profile 標題上（無法核對頁面是否為該方案），驗證器因數值確實在區塊內而放行。passed_with_gaps 在提案白名單內（`propose_radar_update.py:18,24`）。

**F6. `all_pending`／`track:all`／`auto` 在 workflow 中是 no-op；完整一輪要 8-9 次手動明列｜信心：高**
見下方 Q3 專節。

**F7. 手寫硬日期以「已確認」發布｜信心：高**
`cand-ntu-med-publication-115-7296a12b` 截止 2026-11-26T17:00+08:00：`radar_metadata.py:89-91` 給 `certainty: confirmed`，也進 `feed-deadlines.xml`（`build_feed.py:103-123`）。此筆 revision 是 placeholder 雜湊（`medical-scholarships.json:466`），`pilot.json` 記載該時間來自官方搜尋摘要。距今 19 天，是 190 筆中唯一會影響學生行動的硬日期。手寫 190 筆中，共 156 筆帶時間規則投影到網站（submission_mode 分布：recurring 77、continuous 48、procedure_only 29、reference 2、event_relative 1、deadline_only 1、undetermined 32）；產生 `time_dates` 的只有這一筆。

**F8. 測試主動鎖住現況｜信心：高**
見 Q1 清單。最糟的是 `test_temporal_reextract.py:265` 名為 `..._pipeline_integrity`，實際只斷言手寫觀察檔的數量。

**F9. 自我認證：快照冒充存取審查｜信心：高**
`temporal_reextract.py:453-457`：`radar-proposal-snapshots.json` 內 `candidate_snapshot` 的 URL 自動得 `content_verified: True`。該檔由候選反推（`propose_radar_update.py:97-100`），等於候選證明自己可讀。目前影響 2 個 URL（`cm.nsysu.edu.tw/p/404-1024-380732.php`、`foxconnfoundation.org/news/80479d881F20`）。在 `original-source-verification` 沒有 content_verified 也會被 replay 放行。

**F10. 提案合併依 URL 刪除萃取候選｜信心：高（程式與模擬）**
`propose_radar_update.py:28`：新候選 URL 相同就移除舊候選。source-review 與手寫 bundle 共用 `research.google/outreach/phd-fellowship`、`aws.amazon.com/education/awseducate`、`education.github.com/pack`。通用 profile 重掃這些 URL 時，提案會用貧乏的通用候選取代原本證據完整的卡片（模擬 run 1：64+5 只得 67）。僅影響待審提案，需人工套用才生效。

**F11. 舊待審的結構化內容會遺失｜信心：高**
`scan_sources.py:482` `allow_network_refetch=False`，跨 run 的 pending 無 blocks，退回 stub、`needs_context`，被提案過濾（模擬 run 6：24 筆全 withheld）。結構化成果只存在該次 run 的 artifact，保留 14 天（`scan-sources.yml:191,203`）。

**F12. 截止 RSS 無日期過濾｜信心：高；與出處無直接關係**
`build_feed.py:103-123` 不比對今天，`:117` 一律標 `[即將截止]`。實測 `cand-discovery-r317-a4bb5884`（2024-12-01）也掛此標籤。`test_feed.py:99` 鎖定此前綴。另 `build_feed.py:76` 讀 `benefit.text`（schema 欄位是 summary），`:111` 讀 `rec.time_dates`（只存在 radar metadata），皆為死路徑。

#### 懷疑（未能完全證實）

**S1. Action 失敗不存快取，可能形成活鎖｜信心：中**
`scan-sources.yml:144-148` 用 `actions/cache`；我所知其 post 步驟預設只在 job 成功時存（repo 內無該 action 原始碼，離線無法核實）。`scan_sources.py:473-491` 與 `yml:196` 的步驟在 state 寫入後才跑、無 try/except，若其中確定性拋例外，state 不會保存，下次從同一處重來、再次失敗。5 種頁面與 6 輪 mock 都沒觸發，所以這只是風險，沒有找到實際觸發資料。

**S2. 動態頁面吃掉待審額度｜信心：中**
`body_selector: body` 使頁面計數器、日期都進 semantic hash（`:356`）。每次都算 changed、產生新 revision，舊 revision 不會被覆蓋（`:370-371`）。模擬 3 個動態頁、無人審：run 137（約 23 週）觸頂。實際有多少動態頁，離線無法確定。

**S3. 通用 profile 的實際可讀率很低｜信心：中**
`work/discovery/candidate-sources.json`（今日 13:58 產生，未重跑；Fetcher 放寬了 allowed_hosts）：137 個通用 profile 只有 44 個回 200，39 個 404、23 個 transport_error、14 個 url_not_allowed。enterprise 85 筆只有 6 個 200，38 個 404。transport_error 可能含 runner 環境因素；200 也不代表內容相符。

**S4. `(start+1)` 游標與 PDF 主來源｜信心：低**
`scan_sources.py:380` 只記 html。預算若恰好耗盡在 PDF 主來源（目前只有索引 10）或附件，游標會略過它到下一個 html。模擬 18 輪涵蓋 182/182，未見永久飢餓。

**S5. 網站狀態的基準日寫死｜信心：中**
`build_site.py:64-65,74` 寫死 2026-11-06；`build_review_workspace.py:66-67` 以此算 application state。`prototype.js:56` 只有 `as_of===today` 才採用，故瀏覽器端應會重算，但未完整追完前端分支。

### Q1 CI 實際跑什麼

| 步驟 | 位置 | 實質 |
|---|---|---|
| `check_data.py` | `pages.yml:31` | 見 F2。`glob` 掃 9 份 bundle，temporal 只驗 source-review |
| `--check-config` | `pages.yml:32` | 預算上限、URL 唯一與白名單、profile 欄位存在（`scan_sources.py:409-431`）。空 `required_markers` 合法 |
| unittest | `pages.yml:34` | 真實 bundle 只驗數量與投影 |
| node test | `pages.yml:36` | 前端邏輯 |
| `build_site.py` | `pages.yml:39`；`build_site.py:29-38,90` | 寫死 8 份 bundle（不含 ai-tools），故 256 vs 254 |
| `build_review_workspace.py` | `pages.yml:41` | 只處理 source-review |

唯一會拒絕編造的規則全在 `verify_candidate()`，它只在有 in-memory blocks 的萃取路徑與單元測試中被呼叫。

#### 鎖住現況的測試

| 測試 | 斷言 | 問題 |
|---|---|---|
| `tests/test_build_site.py:28,79,85`（方法名 `test_all_254_...`） | 254 | 移除手寫資料即失敗 |
| `tests/test_feed.py:51,94` | 254 | 同上 |
| `tests/test_verify_candidate_sources.py:51`（未追蹤） | 256 | 同上 |
| `tests/test_temporal_reextract.py:203-223` | k12 25 筆；recurring 14、procedure_only 6、continuous 3、reference 2、undetermined 0 | 期望值來自手寫資料 |
| `tests/test_temporal_reextract.py:225-243` | perks 28；continuous 27、recurring 1 | 同上 |
| `tests/test_temporal_reextract.py:245-263` | enterprise 85；recurring 62、procedure_only 23 | 同上 |
| `tests/test_temporal_reextract.py:265-319` | 總 204；undetermined 0；gov>40、other>50、enterprise>90 | 名稱含 pipeline_integrity，實無 pipeline。undetermined 0 會獎勵編造時間 |
| `tests/test_feed.py:99` | 標題前綴 `[即將截止]` | 見 F12 |
| `tests/test_universal_source_chains.py:53-55` | batch 內計數等於 registry 自述 | 兩者同一 builder 寫，自我比對 |
| `tests/test_temporal_tracks.py:37-40`、`test_temporal_action.py:139`、`test_temporal_reextract.py:195` | 64；30/7/27 | source-review 硬編碼，非錯誤資料但會擋更新 |

`tests/test_verify_university_roster.py:102-105`（university 無日期）是有用的護欄，但只防日期，不驗來源。

### Q2 離線證明與規則

#### 目前有沒有證明

沒有可重算的證明。`run-2026-11-01.json`（revision 340、raw 310）與 `original-source-verification.json`（revision 256 + parent 76、raw 245）是唯二成規模的抓取台帳，但只含雜湊，原文未存；也都是 repo 內資料，由能寫 bundle 的同一類流程寫入。scan 的 state 只在 Actions cache，不進 repo，往後掃描也不留永久台帳。

#### revision_id 命中率

| bundle | n | run-11-01 | orig-verif | candidates-11-01 | discovery-refresh | source-chains | batch-01 | ref-windows | audits（最高） | run+orig | 全台帳 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| source-review | 64 | 22 | 52 | 22 | 7 | 24 | 18 | 3 | 5 | **54** | **64** |
| ai-tools-115 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | **1** |
| enterprise | 85 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| k12 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| perks | 28 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| medical | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| emergency | 18 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| topology | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| university | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |

台帳已排除 `radar-proposal-snapshots.json`（由候選反推，source-review 命中 64 是循環）與各手寫觀察檔。source-chain-batches 的 k12/enterprise/perks 等批次也未命中候選 revision。

其他比對：temporal `raw_sha256` 在抓取台帳的命中：source-review 17/64，其他全部 0。evidence 區塊雜湊命中：source-review 198/295、ai-tools 46/48，手寫 0/192。temporal `attempted_urls` 含該筆 URL：source-review 23/64（舊批次已被覆寫），其餘 0，故不可作規則。

唯一未命中的萃取筆：`cand-hsinchu-ai-tools-a5cde54c`（observed 2026-10-30）。ai-tools-115 不上站，同 URL 的 `cand-hsinchu-ai-tools-5067a675` 在 source-review 有命中。

#### 規則測試表

「旗標」= 判為非萃取。誤判上限 66（source-review 64 + ai-tools 2）。手寫上限 190。

| 規則 | enterprise | k12 | perks | medical | emergency | topology | univ | 手寫合計 | source-review | ai-tools | 誤判 | 評語 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| R14 重跑 `verify_candidate(blocks=None)` 有 error | 85 | 25 | 28 | 1 | 18 | 8 | 24 | **189** | 0 | 0 | **0** | 最佳：語意規則、用既有碼 |
| R14b 重跑翻轉 evidence_supported | 85 | 25 | 28 | 1 | 18 | 8 | 24 | 189 | 0 | 0 | 0 | 同上 |
| R14 或 R3 | 85 | 25 | 28 | 2 | 18 | 8 | 24 | **190** | 0 | 0 | **0** | 全中且零誤判 |
| R5 無 hash_only 且 evidence ≤ 2 | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 0 | 0 | 0 | 可被多寫幾筆繞過 |
| R7 observed_at 為整點字面值 | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 0 | 0 | 0 | 容易偽裝 |
| R8 checked_at 為整點字面值 | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 0 | 0 | 0 | 容易偽裝 |
| R13 locator 非 extractor 格式（如 `benefit`、`給付標準`） | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 0 | 0 | 0 | 容易偽裝 |
| R6 evidence < 2 且 coverage_ok=true | 85 | 25 | 28 | 0 | 0 | 8 | 0 | 146 | 0 | 0 | 0 | 與 `verify_candidates.py:697-698` 矛盾 |
| R3 prepared_document_sha == revision_id | 0 | 0 | 0 | 2 | 18 | 0 | 24 | 44 | 0 | 0 | 0 | 精準但涵蓋窄 |
| R4 block_sha == prepared 或 revision | 0 | 0 | 0 | 0 | 18 | 8 | 0 | 26 | 0 | 0 | 0 | 同上 |
| R12 雜湊模板命中 | 0 | 0 | 0 | 0 | 18 | 8 | 24 | 50 | 0 | 0 | 0 | 直接證明編造 |
| R11 summary 有金額但 items 空 | 0 | 0 | 0 | 0 | 18 | 0 | 20 | 38 | 0 | 0 | 0 | 涵蓋窄 |
| R18 excerpt 雜湊對不上自身摘錄 | 7 | 0 | 2 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 精準但少 |
| R1b revision 不在全台帳 | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 0 | **1** | 1 | 唯一真正對外比對 |
| R1 不在 run+orig | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 10 | 2 | 12 | 誤判過多 |
| R2 excerpt_sha == block_sha（任一 short_excerpt） | 85 | 25 | 28 | 2 | 0 | 0 | 24 | 164 | 2 | 2 | **4** | **任務舉例的這條不能用**：短區塊整段被摘錄時真實管線也相等（如「(一)18歲以上…」「線上申辦」） |
| R2b 全部 short_excerpt 相等 | 85 | 25 | 28 | 2 | 0 | 0 | 24 | 164 | 2 | 2 | 4 | 同上 |
| R9 verifier_version 為 1.1.0／1.5.0 | 85 | 25 | 28 | 0 | 18 | 8 | 0 | 164 | 0 | 2 | 2 | 註：`verifier-1.5.0` 從未存在於 `verify_candidates.py`（`git log -S` 只見 emergency commit，現行為 1.4.0），這本身是編造證據 |
| R14c 翻轉 coverage_ok 或 evidence_supported | 85 | 25 | 28 | 1 | 18 | 8 | 24 | 189 | 0 | 1 | 1 | 舊 bundle 的版本差異會誤判 |
| R17 無區塊雜湊在任一台帳 | 85 | 25 | 28 | 2 | 18 | 8 | 24 | 190 | 30 | 0 | 30 | 不可用 |
| R19 evidence 只有一個頂層欄位 | 85 | 25 | 28 | 0 | 18 | 8 | 24 | 188 | 22 | 0 | 22 | 不可用 |
| R10 prepared_document_sha 缺 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 | 不可用 |

零誤判且涵蓋 190 的組合：**R14 ∪ R3**（有語意基礎）、R6 ∪ R3 ∪ R4（純出處形狀）、R5／R7／R8／R13（單條但易偽裝）。所有規則都是偵測「這批」的指紋，不是出處證明；下一位作者若直接呼叫 `make_field_evidence` 式雜湊並補齊欄位，R3/R4/R5/R7/R8/R13 都會失效，只有對外台帳比對（R1b）還有意義，前提是台帳寫入受保護。

R14 誤判為 0 的前提：以現行 schema 與 verifier 重跑。verifier 規則變更可能改變此結果。

### Q3 掃描行為

#### 誰能讀寫

| 操作 | 讀 | 可更新 | 位置 |
|---|---|---|---|
| `scan` | `scan-sources.json` 中啟用的 182 個 profile（含 169 個只屬手寫 bundle），不讀任何候選 bundle | 只寫 `work/`；提案只改 `source-review.json` | `scan_sources.py:318,465-472`；`propose_radar_update.py:23,35`；`yml:196` |
| `temporal_replay` | 只有 source-review 的 64 筆 | 只寫 `work/temporal-action/`；提案是 `temporal-observations.proposed.json` | `temporal_reextract.py:444`；`run_temporal_action.py:112-115,301`；`yml:121-127` |

scan 輸出**不能**取代手寫資料（見 F4）。source-review 64 筆中有 45 筆的 profile 是 `enabled:false`，scan 也不會更新它們，只有 replay 不看 enabled（`temporal_reextract.py:446,500`）。

另外 `yml:53-56` 註解宣稱三軌排程，但 `scan_sources.py` 沒有 track 概念，三個 cron 只是一週六次、同一游標。

#### 排程週期

條件：182 來源、145 主機、每輪 20 HTTP、5 份變更、24 待審、Mon–Sat 六次。每個新主機的第一個請求要先花 1 次 robots（`:137-139`，每輪重查），所以穩態約每輪 10 份。

| 情境 | 輪數 | 換算 | 備註 |
|---|---:|---:|---|
| 穩態：全部已有基準且未變 | **18** | 3.0 週 | 模擬，無重導、無錯誤（實際會更慢） |
| 冷啟動，每輪都把待審清空 | **37** | 6.2 週 | `changed` 上限每輪 5（`:330`），不是 HTTP 上限在限制；要提交約 180 筆處置 |
| 冷啟動，無人審（目前的預設現實） | **永不完成** | run 6 起卡死 | 只碰過 24/182 |
| 穩態 + 3 個動態頁，無人審 | run 137 卡死 | 約 23 週 | S2 |

- changed 上限：**不卡死**，只是降速；`deferred_index` 會回到下一個（`:380-381,387`）。
- `review_backlog_full`：**卡死**，見 F3。
- 持久化：`yml:144-148` 用 run-id 新 key 加前綴還原，`next_source_index` 存在 state，成功的 run 會前進。exit 1 的 run 不存（S1），但卡死時 state 本來就不變。
- 永久飢餓：沒有發現可用來源被游標永久跳過（模擬涵蓋 182/182）。真正永久的是設定層面：87 個 disabled profile（含 emergency 18、medical 2、source-review 45 筆）永遠不掃；以及 F3 卡死後的其餘 158 個來源。

#### 手動 dispatch

| 輸入 | 實際結果 | 位置 |
|---|---|---|
| `all_pending`，schedule_track 預設 auto | **不是全部**：依今日星期解析（週六得 other，27 筆） | `yml:91` 傳 auto；`run_temporal_action.py:59` 只在 `not track` 時才轉 all |
| `all_pending` + track=all、`track:all`、`auto` | 全部 SKIP，**0 來源、0 HTTP** | `temporal_tracks.py:334-339`；64 筆 mode 全 resolved，run=0 |
| 其中要跑 refinement | workflow 無輸入可開（CLI 有 `--include-refinement`，`yml:109-113` 不傳）；開了也只有 15 筆、14 sid、2 次 | `run_temporal_action.py:362` |
| force_recheck | CLI 與 workflow 都沒有入口 | `run_temporal_action.py:105,366-377` |
| 明列 source id + `incremental_only=true`（預設） | 過濾成 0 筆 | `run_temporal_action.py:125-127` |
| 明列 source id + `incremental_only=false` | **唯一能重新抓的方式** | `yml:112` |

完整一輪需要：明列全部 58 個 sid、關 incremental。單次上限 8 sid、8 URL（`temporal_reextract.py:481`）、20 HTTP。依檔案順序切 8 批需 **9 次**（第一批 12 URL，4 個被截斷）；重排使每批 ≤ 8 URL 則最少 **8 次**（62 URL）。每批最少 12-15 HTTP，假設無重導。

不能累積：workflow 不傳 `--baseline`（`yml:109-113`），每次都比對已提交的 `data/temporal-observations.json`，`merged` 只含該次批次（`run_temporal_action.py:286-297`）。8 份 artifact 要在 14 天內人工合併。且這只涵蓋 64/256 筆，**190 筆無任何 dispatch 方式**。

#### 通用 profile

有 137 個（`body_selector` 為 body 系、`required_markers` 空，`pdf_include` 空者 178 個）。見 F5：基本上不可用，只能作為頁面可讀與變動訊號。

### Q4 其他自我認證與編造路徑

#### 寫入 `data/candidates/*` 或 `data/*temporal-observations.json` 的腳本（完整清單）

| 腳本 | 寫入 | 來源 | 可重跑？ |
|---|---|---|---|
| `build_emergency_relief_expansion.py` | `:1016-1017`、`:1036-1037`；另 `scan-sources.json:720`、registry `:1134` | 字面值，HTTP 0 | **可**，`:1138` 無防護 |
| `build_topology_discovered_bundle.py` | `:243-245`、`:263-265`；另 `scan-sources.json:145`、chain `:366-368` | 複製 k12 候選（`:150`）加字面值 | **可**，`:371` 無防護 |
| `build_taiwan_universities_expansion.py` | `:1500-1501`、`:1520-1521`；另 `scan-sources.json:1212`；**`scripts/build_site.py:1525-1537`；`tests/test_build_site.py:1541-1549`** | 字面值 | 只被 `:11` 一行 `raise SystemExit` 擋住 |

沒有腳本寫 source-review、k12、enterprise、perks、medical、ai-tools 候選，也沒有腳本直接寫 `data/temporal-observations.json` 與 k12／perks／enterprise／medical／ai-tools 觀察檔（走人工或 agent 複製，或如 candidate-provenance 所述無生成器）。寫 `work/` 的有守衛：`temporal_reextract.py:442,541`、`run_temporal_action.py:112`、`propose_radar_update.py:138`、`expand_sources.py:232`、`source_chains.py:485`、`verify_original_sources.py:227`、`prepare_candidates.py:82`。

`extract_candidates.py` 的 `--output` 無路徑守衛，可被指向 `data/candidates/`（真實管線輸出，風險低）。`audit_sources.py:163`、`close_source_verification.py:123`、`export_expansion_report.py:133,141`、`audit_time_policies.py:105,120` 寫台帳或 docs，其中 run 與 verification 台帳正是 R1b 的依據，能重寫它們就能偽造命中。

#### 字面日期、now、硬編值

| 位置 | 內容 | 風險 | 信心 |
|---|---|---|---|
| `build_site.py:64-65,74` | `generated_at`、`as_of`、`observed_at` 2026-11-06 字面值；`:67-69,76-77` 寫死 model_enabled、model_calls 0、official_data_modified False、published False（建置時的記憶體物件） | 見 S5；旗標是自報，不反映實況 | 高 |
| `build_topology_discovered_bundle.py:200,235,257,289-347` | observed_at 字面值；`:193` 自造指紋 | 指紋錯使 8 筆意外失效（temporal_pass 0） | 高 |
| `build_emergency_relief_expansion.py:899,932,974,1008,1030,1069,1097` | 全字面 | 含 verifier-1.5.0 | 高 |
| `run_temporal_action.py:263` | `document_raw_sha256 or "0"*64` | 通過 `time_policy.py:43` 的 regex。依現有呼叫（`temporal_reextract.py:607`）實務到不了 | 中 |
| `run_temporal_action.py:108` | `apply_verified_model_rules=True` 預設，模型通過引文核驗的主張併入提案（`:244-276`） | AGENTS 2026-11-03 寫「模型意見獨立待審，不自動套用」；可能後續另有核可，未逐條追完。僅影響 artifact | 中 |
| `extract_candidates.py:2993,3100` | observed_at 缺值用 now | scan 恆給值，實務到不了 | 中 |
| `review_candidates.py:220` | as_of 回退 2026-10-29 | bundle 恆有 as_of | 低 |
| `build_feed.py:86,88` | pubDate 回退 now | 把未知時間呈現為最新 | 低 |
| `temporal_model.py:138` | `checked_on: 2026-11-03` 字面值 | 模型上限檢查日永不更新 | 低 |
| `temporal_reextract.py:453-457` | 見 F9 | - | 高 |
| 觀察檔 `observed_at: 2026-11-04T00:00:00`（k12、perks、enterprise、medical、university、topology、ai-tools） | `status: replayed` 但 HTTP 0 | ai-tools 也是，所以 R 規則不能用 http=0 區分 | 高 |

`parser_sha256`：k12、perks、enterprise、topology、ai-tools 觀察檔都是 `dff305dd…`，它確實存在於真實觀察。所以 parser 欄位看似真實但沒有證明力（複製而來）。

### 未能確定

- Actions cache 目前的 state：pending 是否已滿、排程是否真的跑過、最近一次 run 結果。若舊狀態已有 17-19 筆待審，卡死會比模擬更早。
- `actions/cache` 的 post-if 預設與快取逐出（依既有知識，repo 內無原始碼）。
- 真實網站上通用 profile 的表現：F5 用合成頁，S3 用既有結果未重跑。
- 手寫內容是否正確：本審查只論出處，部分金額可能恰好正確。
- k12／perks／enterprise／medical 雜湊的衍生方式（承接前次未定）。
- 抓取台帳本身的真實性：無法離線重算，R1b 只能證明「與已提交台帳一致」。
- `extract_policy`（replay）對通用頁的品質：只測了 scan 的通用分支；replay 另有 `temporal_reextract.py:251` 的規則，只作用於 source-review。
- 前端是否完全以今天重算所有狀態（S5）。
- 完整 unittest 未在本次重跑；CI 綠燈採用你提供的既定事實。


## 各批次出處

## Candidate bundle provenance audit (read-only, repo D:\Codex_Projects\OpenGSA-wt-roster)

Method: read generators in scripts/, recomputed hashes from data, counted fields (helper scripts an.py, an2.py, an3.py, bf.py in this scratch folder). No network.

### Summary table

| Bundle | n | Verdict | Decisive evidence | Specific claims lacking real evidence |
|---|---|---|---|---|
| enterprise-scholarships | 85 | hand-authored (no generator; text copied from hand ledger) | data/enterprise-scholarship-sources-baseline.json is a ledger with no fetch; candidate benefit.summary == f"{benefit_type}（估值：{value_estimate}）" for 85/85; grep scripts/ finds only readers (build_universal_source_chains.py:291, build_site.py:33); data/enterprise-temporal-observations.json:3 http_requests 0 | 85 amounts (summary); 0 dated deadlines |
| k12-scholarships | 25 | hand-authored (same) | data/k12-scholarship-sources-baseline.json; candidate summary is a prefix of baseline benefit_summary 25/25, URL in baseline official_portals 25/25; k12-temporal-observations.json http_requests 0 | 24 amounts; 0 dates |
| student-perks | 28 | hand-authored (same) | data/student-perks-baseline.json; summary == f"{benefit_type}（估值：{value_estimate}）" 28/28; URL == baseline official_url 28/28; baseline as_of is 2026-11-06, later than the candidates' generated_at 2026-11-04 and its own commit time (bef663e, 2026-11-04) | 27 amounts; 0 dates |
| medical-scholarships | 2 | hand-authored, fabricated revision hash on one | data/candidates/medical-scholarships.json:466 revision_id 7296a12bc0b98e1a8f673123456789abcdef0123456789abcdef0123456789ab (placeholder pattern); that source (rd.mc.ntu.edu.tw ...pno=7296) is manual_only/403 in data/source-expansion/run-2026-11-01.json (R263); data/pilot.json notes the 115/11/26 time came only from an official search snippet; docs/archive/MED-SCHOLARSHIPS-AUDIT.md says sources are enabled:false with 0 external requests; no generator script | 2 (1 absolute deadline 2026-11-26T17:00+08, 1 relative 28-day rule); 0 amounts |
| emergency-relief-aid | 18 | hand-authored | scripts/build_emergency_relief_expansion.py:425 INDICATOR_SCHEMES literals (benefit_summary, deadline_text); :751 rev_id = sha256(f"{sid}-20261106-{url}"); :906 prepared_document_sha256 = rev_id; :917 source_block_sha256 = rev_id; :916 excerpt = benefit_summary[:100]; :1023 http_requests 0 | 18 amounts; 17 free-text relative deadlines ("3個月內", value null); 0 absolute dates |
| topology-discovered-scholarships | 8 | hand-authored, cloned template | scripts/build_topology_discovered_bundle.py:159 rev = sha256(url+"_rev_115"); :160 raw = sha256(url+"_raw_115"); :162 deepcopy(k12 candidate[0]) with a few fields overwritten (degrees master/phd and identity "適用教育階段：preschool" remain on an indigenous-student scholarship); :187 block hash = raw; :215 value "2026-10-15" literal for all 8; :250 http_requests 0 | 8 amounts; 8 dates (identical 2026-10-15 in data/topology-discovered-temporal-observations.json; candidate schedule value null) |
| source-review | 64 | extracted (control) | extract_candidates.py:829-846 block_sha = evidence_digest(block text), separate from excerpt sha; data/temporal-observations.json:3 http_requests 53; data/source-expansion/run-2026-11-01.json:12 http_requests 634; 61/64 candidate URLs have status read in that run; revision_id matches no template | 0 found. 21 amounts (benefit.items, all with benefit.* evidence), 9 candidate deadlines + 1 application_start (all with schedule.* evidence), 35 dated temporal rules. Caveat: 288/295 evidence entries are hash_only, 7 have excerpts, not re-checkable offline |
| ai-tools-115 | 2 | extracted | commit 693f3c1 adds ai_tool_rules.py and extract_candidates changes; run record has preflight_read for both URLs (B0, 4 HTTP); ai-tools-temporal-observations.json http_requests 0 is a replay, not a fetch | 0 found (2 amounts, 2 deadlines, 1 application_start backed by evidence) |
| university-scholarships (reference, already known) | 24 | hand-authored | build_taiwan_universities_expansion.py:1223 rev = sha256(f"rev-{sid}-20261105") matches 24/24; :1388-1389 excerpt hash == block hash of invented string; :1506 http_requests 0 | 20 amounts; 0 dates (cleaned in bcb7e64) |

### 1. Generators
- enterprise, k12, student-perks, medical: no generator in scripts/ or in git history (git log --all -S on distinctive ids and filenames finds only data commits ae6878a, d74d4bb, 956012a, 8d666e6 and readers). Those commits change only data, temporal_tracks.py, tests (medical also build_site.py).
- emergency-relief-aid: build_emergency_relief_expansion.py (literals, no HTTP; http_requests 0 at :1023, :1028, :1100).
- topology-discovered: build_topology_discovered_bundle.py (literals in schemes_def, no HTTP).
- source-review: scan_sources/extract_candidates pipeline; ai-tools-115: extract_candidates + ai_tool_rules.
- grep for http_requests/urlopen/fetch in the emergency, topology, university builders hits only the literal 0.

### 2. Hash derivation (tested by data)
- university: revision_id = sha256("rev-{sid}-20261105") 24/24; prepared_document_sha256 == revision_id 24/24.
- emergency: revision_id = prepared_document_sha256 = source_block_sha256 = sha256("{sid}-20261106-{url}") 18/18; excerpt_sha256 = sha256(benefit_summary[:100]).
- topology: revision_id = sha256(url+"_rev_115"); prepared_document_sha256 = source_block_sha256 = sha256(url+"_raw_115"); excerpt_sha256 = sha256(ben[:100]); temporal raw_sha256 = same raw.
- medical: prepared_document_sha256 == revision_id == temporal raw_sha256 (2/2); one value is the placeholder pattern; the other (40192a8b...) differs from the run record's fetched revision for the same URL (023a790e..., R380), so it was not taken from the fetched page. Its derivation is not determinable (matches no tested template).
- k12 / perks / enterprise: revision_id matches none of the tested templates (url, sid, cid, program_key, title, observed date forms, prefixes rev-/raw-, suffixes _rev/_raw/_rev_115, separators, up to 3-part permutations). candidate_id suffix == revision_id[:8] (25/25 k12). prepared_document_sha256 != revision_id. Derivation UNDETERMINED: no generator, no fetched document in repo to hash.
- excerpt_sha256 == source_block_sha256: true for every short_excerpt entry in enterprise/k12/perks/medical/university (and for hash_only by design, extract_candidates.py:836-837). In the real pipeline the block hash covers the whole block and the excerpt hash only the fragment (extract_candidates.py:829-846, verify_candidates.py:304), so equality for these means the "block" is exactly the short excerpt string, as the university builder does explicitly at :1388-1389. In emergency/topology the two differ because block hash is set to rev/raw.
- verify_candidates.py checks excerpts against in-memory blocks only when blocks are supplied; none are stored, so verification.checks in these bundles cannot be reproduced. All carry identical verifier_version and checked_at stamps per bundle (verifier-1.1.0 / 2026-11-04T00:00:00Z; emergency verifier-1.5.0 / 2026-11-06T10:00:00Z).

### 3. Field counts (an3.py; money regex = digits + 元/萬/千/%/NT$/$ etc.)
| bundle | n | has url | cand deadline value | app_start value | temporal rule dated | amount in summary | benefit.items amount | other_conditions | field_evidence entries | evidence mode | verification.status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| enterprise | 85 | 85 | 0 | 0 | 0 | 85 | 0 | 85 | 85 (benefit.summary only) | short_excerpt 85 | passed_automated_checks 85 |
| k12 | 25 | 25 | 0 | 0 | 0 | 24 | 0 | 25 | 25 (benefit.summary only) | short_excerpt | passed_automated_checks 25 |
| perks | 28 | 28 | 0 | 0 | 0 | 27 | 0 | 28 | 28 (benefit.summary only) | short_excerpt | passed_automated_checks 28 |
| medical | 2 | 2 | 1 | 0 | 1 | 0 | 0 | 2 | 4 (identity, deadline) | short_excerpt | passed_with_gaps 2 |
| emergency | 18 | 18 | 0 | 0 | 0 | 18 | 0 | 18 | 18 (benefit.summary only) | short_excerpt | passed_with_gaps 18 |
| topology | 8 | 8 | 0 | 0 | 8 (all 2026-10-15) | 8 | 0 | 8 | 8 (benefit.summary only) | short_excerpt | passed_automated_checks 8 |
| university | 24 | 24 | 0 | 0 | 0 | 20 | 0 | 24 | 24 (eligibility.identity only) | short_excerpt | passed_with_gaps 24 |
| source-review | 64 | 64 | 9 | 1 | 35 | 21 | 21 | 4 | 295 over ~70 field paths | hash_only 288, short_excerpt 7 | passed_with_gaps 50, passed_automated_checks 14 |
| ai-tools-115 | 2 | 2 | 2 | 1 | n/a (replay) | 2 | 2 | 2 | 48 | hash_only 41, short_excerpt 7 | passed_with_gaps 2 |

All bundles: extraction_method deterministic_rule for every evidence entry. verification.checks (same 7 keys everywhere): schema_valid, evidence_supported, date_and_amount_units_valid, no_year_or_branch_mixing, negation_and_roles_valid, no_unresolved_conflicts are true for every candidate in every bundle; coverage_ok is true for enterprise/k12/perks/topology and false for medical/emergency/university/ai-tools and 50 source-review. So every hand-authored bundle claims evidence_supported=true.

Eligibility text: enterprise/k12/perks/emergency/topology (164 candidates) carry identity.text, other_conditions and degrees but field_evidence covers only benefit.summary, so eligibility is unbacked for all 164. Enterprise identity text is a template "優秀或清寒在學學生（適用：{target_audience}），查驗方式：{verification_method}" and other_conditions[0] copies the benefit text. Topology and k12 carry degrees ["master","phd"] even for preschool subsidies, a default rather than an extraction.

### 4. HTTP and run records
- *-temporal-observations.json top-level http_requests: temporal-observations.json (source-review) 53; ai-tools, emergency, enterprise, k12, medical, perks, topology, university all 0 with attempted_urls [] (all records status "replayed").
- data/source-expansion/run-2026-11-01.json summary.http_requests 634 (485 inventory + 56 child + 20 lead URLs). Overlap with candidate URLs (normalised for scheme/www/trailing slash): enterprise 2 of 85 (faos.org.tw/apply/student and research.google/outreach/phd-fellowship read), k12 2 of 25 (ht.org.tw required_marker_missing; foxconnfoundation.org read), student-perks 2 of 28 (education.github.com/pack, aws educate; read, also in temporal attempted_urls), medical 2 of 2 (oia page read but its fetched revision differs from candidate revision; rd page manual_only/403), emergency 2 of 18 (advisory.ntu.edu.tw manual_only; oia.ntu.edu.tw read), topology 0 of 8, university 0 of 24, source-review 61 of 64 read, ai-tools 2 of 2 preflight_read. A handful of landing pages were fetched, but no candidate field is tied to those fetches (revisions differ or are not stored).
- docs/archive/SOURCE-EXPANSION-RUN.md (2026-11-01) predates the hand-authored bundles (created 2026-11-04 to 11-06) and states public candidates were not modified.

### 5. source-review control
Genuinely extracted by evidence: 53 HTTP in temporal observations; hashes follow evidence_digest of real blocks; 61/64 URLs read in the run; evidence paths specific and varied (eligibility.*, benefit.items/N, schedule.steps/N/deadline, application_method/N); 50 fail coverage_ok, which a template would not do. Limits: mostly hash_only, original text not stored, 62 distinct URLs for 64 candidates. Not re-fetched here (no network), so "extracted" rests on code path, run record and data shape, not on re-verification.

### 6. Undetermined
- How k12/perks/enterprise/medical revision_id and prepared_document_sha256 values were computed.
- Whether the baseline ledgers (k12, enterprise, perks) were compiled from real page reads; the repo shows no fetch for them.
- Whether any hand-authored amount is nonetheless correct; this audit covers provenance only.
- candidate-urls.json: 254 distinct (bundle,url) rows covering 256 candidates; every candidate in every bundle has source_metadata.url (85/25/28/2/18/8/64/2/24).
