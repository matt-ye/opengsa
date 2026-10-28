> 文件性質：規劃參考／研究日快照。repo 初始化已核可；目前分期及授權邊界以 [目前計畫](../PLAN.md) 為準。文內「本次／本輪／尚未建 repo」描述的是原規劃階段，不代表目前 repo 尚不存在；來源條件仍須逐案重查。

# OpenGSA：臺灣研究生獎助與權益資訊專案

**Grant Scholarships Award**

完整繁體中文 Codex handoff｜規劃版 v1.2｜研究基準日：2026-10-28（Asia/Taipei）

**最新規劃順序**：先確認資源類別與關鍵字，再完成來源台帳、檢索清單與排程矩陣，之後用視覺化流程圖逐項確認架構；完整規劃確認前不寫產品程式。詳見同目錄的《OpenGSA-taxonomy-sources-plan-zh-TW.md》。本文件第 13 節技術選型僅保留為先前架構提案，須在上述流程完成後重新確認，不能視為已核准實作。

**PDF 來源補充**：三份原先遠端讀取失敗的臺大彙整表，現已由使用者提供的本機副本完成辨識；詳見分類文件第 12 節。新增「申請者、受益者、受獎者、款項受領主體」區分，避免把教師／團隊計畫、TA 單位補助誤列為學生可直接申請的獎學金；各項現行辦法與內嵌連結仍待逐項覆核。

**理念與參考網站補充**：詳見同目錄《OpenGSA-mission-FAO-review-zh-TW.md》。建議主 Slogan：「把時間留給研究，把獎助檢索交給 OpenGSA。」新增財務安定、資訊透明、防止以獎助不當控制學生、依法／依辦法／依契約查明應得給付與保密求助原則。已透過使用者瀏覽器有限查看臺大 FAO，保留其多維查詢、歷史與收藏入口，改良申請路徑、逐條資格、來源角色及版本呈現；不設所有教授一律應付的通用最低獎助額。新增功能依規劃另定優先序，不代表開始實作。

**必要標籤需求**：每項獎助提供來源、身分、年級限制、兼領及清寒限定五組 tag；來源區分資助與轉知，兼領支援附條件及待確認，清寒限定與清寒優先分開。標籤由適用年度的證據與資格資料產生，未知不等於不限，亦不得與資格引擎矛盾；詳見分類文件第 13 節。

## 0. 本文件的授權範圍與使用方式

**這是一份待使用者確認的規劃，現在不得建立、初始化、修改或推送任何 repo，也不得部署、購買網域、設定排程、寄送通知或聯絡第三人。** 本次僅交付此規劃文件。後續 Codex 必須先取得使用者對實作的確認，再依本文件開始工作。

產品名稱依使用者指定定為 **OpenGSA**，英文全名為 **Grant Scholarships Award**；repo 名稱提案為 `opengsa`。名稱、商標、repo 與網域可用性尚未查核，也未註冊；本次更名不代表開始建立 repo。

文件中「已查核」僅指下列來源支持的特定事實；「產品決策」是建議採用的設計；「待查」不得轉寫成肯定結論。官方內容會變動，實作上線前必須重查。前一段 ChatGPT 對話中的助理答案無法完整讀取，不能作為資格或法規證據。

## 1. 產品目標與服務對象

讓在臺灣就讀的碩博士生，不必逐一翻找機關、學校、學院與系所公告，就能回答：

1. 我有哪些獎學金、研究獎勵、論文獎、出國研究或國際會議補助值得查？
2. 哪些已知條件符合、哪些明確不符、哪些需要補資料或詢問承辦？
3. 最早必須在哪一層完成什麼程序？有哪些不能兼領、續領、核銷或返還義務？
4. 擔任 RA／TA 時，如何辨識學習與勞動的分際，查找工資、工時、保險、勞退及爭議處理依據？
5. 資料由誰發布、適用哪一年、何時生效、何時最後確認、出了錯如何更正？

服務涵蓋碩士、博士、博士候選人、延修生、逕博生；身分欄位能表達本國生、外籍生、僑生、港澳生與陸生，不預設所有方案對所有身分開放。全臺服務是產品方向，首版資料覆蓋範圍必須明示，不能宣稱已蒐羅全臺所有方案。

核心原則：**以官方證據解釋資格；保留未知；資格、受理狀態、資料可靠度分開顯示。** 「符合已知條件」不等於獲獎、錄取、核准或法律認定。

成功指標（產品目標，非既有成效）：至少 8 位不同學制與領域學生試用，其中至少 6 位可於 5 分鐘內找到一個相關方案、說出待補條件，並辨識其正確送件期限；高風險錯誤，如錯標開放、錯用年級限制、錯用工資生效日，在發布驗收樣本中為 0。

## 2. MVP 範圍與完成定義

### 首版必做

| 功能 | 最低交付 |
|---|---|
| 獎助搜尋 | 類別、學制、學校、領域、年級、受理狀態篩選；繁中關鍵字及臺／台、國科會／科技部等別名搜尋 |
| 詳情頁 | 金額與單位、對象、條件、文件、申請方式、各層截止、兼領與返還、官方連結、核對日期、異動紀錄 |
| 資格比對 | 不用登入；逐條理由、缺漏問題、人工認定事項；可查看未符合原因 |
| 截止提醒 | 收藏、站內近期截止、下載個別或合併 `.ics`；公開方案更新 RSS；清楚說明匯入與訂閱差異 |
| 權益入口 | 學習／勞動分流、契約、工資、工時休假、保險勞退、申訴與調解；條文與版本連結 |
| 法規與工資歷程 | 依日期查版本，區分公布、生效及未生效；提供新舊差異摘要 |
| 資料維護 | 每筆可追溯來源；Git 變更審查；更正入口；過期與來源失效標記 |
| 開放下載 | 結構化 JSON、方便閱讀的 CSV、schema 說明、版本與授權清單 |
| 覆蓋透明度 | 公布已收錄機關、學校、類別、年度、缺漏與最後人工核對時間 |

首版資料驗收目標：至少 30 筆「特定年度／梯次的獎助機會」，其中至少 12 筆全國性方案，其餘涵蓋至少 6 所學校，包含公立、私立與科技大學；獎學金、研究／論文獎勵、出國研究、國際會議四類均至少 3 筆。已截止資料可以收錄，但至少 5 筆須為發布當日經人工確認仍受理的機會。另交付至少 8 篇權益指南及其官方依據。這是後續蒐集目標，本規劃並未完成這 30 筆盤點。

臺大醫學院與職能治療博士案例列為優先試點，但不得以其他系所期限冒充職能治療系所期限。

### 延後到後續版本

Email／推播、帳號與跨裝置同步、私人日曆訂閱、全校網爬取、英文介面、歷史薪資精算、申訴案件追蹤、申請文件管理、學校正式 API 串接。MVP 不提供自動申請、代送申訴、勝訴率或錄取率預測。AI 可協助草擬抽取結果，不能單獨批准資格、期限、工資或法律內容。

## 3. 使用流程與頁面文案

1. 首頁選「找獎助」「查助理權益」「查法規／最低工資」。不要求先填完整個資。
2. 找獎助：輸入必要條件 → 結果卡 → 展開理由／待補資訊 → 官方申請入口 → 收藏／行事曆。
3. 結果卡同時顯示三組標籤，例如「資格待確認／受理中／官方全文待覆核」。已截止不能用綠色「可申請」包裝。
4. 申請時程顯示「學生送件 → 指導教授 → 系所 → 學院 → 學校 → 主辦機關」，只列該方案真正需要的步驟。某一步完成不代表整案完成。
5. 權益查詢先詢問實際工作情形與事件日期；提供應核對事項與合適窗口，不僅依「RA」「TA」「獎助生」名稱作分類。
6. 詳情頁固定提供「資料有誤／來源失效」入口；預填公開資料 ID 與欄位，提示勿在公開 issue 張貼身分證、薪資單、帳戶或申訴個案內容。

正常文案：「依目前已知資料，你符合 3 項條件；尚需確認是否曾領取相斥獎學金。」「校內期限已過；下一年度尚未公告。」「這是學院送件期限，學生截止時間仍待系所確認。」

禁止文案：「你一定能領」「候選人都能申請人社獎」「五年級所有博士獎學金都不能申請」「官網找不到＝學校違法」。

## 4. 資料模型與 schema 契約

以下為實作規格，後續需轉成可執行 JSON Schema（2020-12）並驗證所有資料。採 UTF-8、穩定字串 ID、ISO 8601 日期；金額為整數或十進位字串，禁止浮點金額。`null` 表示未知，不能代表不限、0、否或不適用。

### 4.1 共通欄位

所有公開實體必有 `id`、`schema_version`、`record_version`、`created_at`、`updated_at`、`review_status`、`evidence_ids[]`。`record_version` 是資料修訂序號；不同於法規版號或方案年度。審查狀態為 `draft | reviewed | disputed | archived`。

每個會影響判斷的事實都要有 `claims[]`：`field_path`（JSON Pointer）、`state`（`known | unknown | conflicting | not_applicable`）、`evidence_ids[]`、`verified_at`、`reviewer`、`note`。資料值存在原欄位，claims 提供逐欄溯源。禁止只掛一個首頁連結就宣稱全部欄位已核對。

### 4.2 主實體

| 實體 | 必要欄位與用途 |
|---|---|
| `Organization` | `id, name_zh, aliases[], kind, parent_id, official_domains[]`；學校→學院→系所層級，別名保留原始稱呼，代碼須有來源 |
| `Program` | `id, title, aliases[], category, organizer_ids[], jurisdiction, description, canonical_url, lifecycle_status`；一個長期制度，類別 `scholarship | research_award | paper_award | overseas_research | conference | other_aid` |
| `Opportunity` | `program_id, cycle_label, cycle_year, cycle_kind, round, application_year, academic_year, activity_year, benefit_period, rule_set_id, procedure_ids[], deadline_ids[], benefits[], documents[], application_url, contact_ids[], compatibility_rules[], obligations[], source_coverage`；一個年度／梯次的可申請機會 |
| `RuleSet` | `version, opportunity_id, effective_from, effective_to, assessment_basis, rules, manual_checks[], evidence_ids[], verification_complete`；只存該期規則，不跨年度覆寫 |
| `Procedure` | `opportunity_id, applicable_org_ids[], applicant_scope, steps[]`；步驟含 `id, actor, action, depends_on[], deadline_id, required, official_endpoint`，各校路徑獨立 |
| `Deadline` | `opportunity_id, procedure_step_id, scope_org_id, audience, kind, value, precision, timezone, original_text, rule_expression, cutoff_semantics, status, supersedes_id, evidence_ids[]` |
| `Source` | `url, publisher_id, title, source_type, authority_tier, published_at, modified_at, first_seen_at, last_checked_at, last_success_at, last_content_reviewed_at, next_check_at, retrieval_status, access_level, license, terms_url, robots_checked_at, automation_policy` |
| `Evidence` | `source_id, source_revision, locator, excerpt, content_sha256, retrieved_at, verification_method, reuse_basis, snapshot_ref`；定位到條／項、PDF 頁碼、附件名或網頁段落；全文快照可空 |
| `LegalVersion` | `document_key, title, issuer_id, legal_kind, jurisdiction, version_label, promulgated_at, amended_at, effective_from, effective_to, commencement_state, commencement_evidence_ids[], articles[], supersedes_id, transition_rules[], evidence_ids[]` |
| `WageStandard` | `jurisdiction, currency, basis, amount, effective_from, effective_to, covered_population, legal_version_ids[], evidence_ids[]`；月與時薪各一筆，適用條件不可省略 |
| `RightsGuide` | `topic, plain_summary, question_tree, applicability, legal_version_ids[], route_ids[], checked_at, reviewer`；說明與法律文本分開 |
| `SupportRoute` | `issue_type, organization_id, territory, audience, role, official_url, contact, hours, filing_rules[], evidence_ids[]`；區分詢問、校內申訴、勞檢、調解、其他救濟 |
| `ChangeEvent` | `entity_id, from_version, to_version, changed_fields[], detected_at, verified_at, severity, reason, evidence_ids[], reviewer`；期限／金額／資格／生效日是重大異動 |

欄位補充：

- `cycle_kind` 為 `calendar_year | academic_year | named_cycle`；年度數值以西元儲存並保留民國原文。例如「115 學年度」不能直接當成 2026-01-01～12-31。
- `benefits[]` 含 `kind, currency, amount_min, amount_max, unit, duration, quota, reimbursement_basis, total_cap, payment_conditions`；每月 4 萬與一次 4 萬不同，部分補助不能寫成保證全額。
- `documents[]` 含 `name, required, applies_when_rule_id, issuer, submit_step_id, template_source_id`；資料平台只列清單，不接收使用者的證件或論文。
- `compatibility_rules[]` 含 `other_program_ids / funding_category, restriction_type, overlap_basis, period, resolution, evidence_ids`；涵蓋不得申請、不得同時領取、不得同費用重複核銷、擇一或僅頒獎不發獎金。未知相容性不得標成可兼領。
- `obligations[]` 含續領評量、在學／全職要求、成果繳交、核銷、返國／畢業、停止發放及返還條件，各附時間基準及來源。
- `Source.retrieval_status` 為 `ok | official_index_only | blocked | not_found | transient_error`；官方頁面可找到但附件尚未讀到，不能填 `全文已核對`。
- `verification_method` 為 `official_fulltext | official_search_excerpt | official_written_reply | manual_transcription`。搜尋摘要只能支持實際出現的資訊，不能填補未讀到的資格細則。
- `source_coverage` 列出已取得／缺少的公告、辦法、附件、校內與系所程序，並有 `critical_fields_complete`。

### 4.3 Profile：只在使用者裝置內處理

必備欄位：`profile_version, as_of, school_id, college_id, department_id, degree, study_year, study_year_at[], candidate_status, candidate_obtained_at`。

選填欄位：`enrollment_status, enrollment_date, admission_type, full_time_student, full_time_paid_job, citizenship, admission_identity, domestic_household_registration, research_topics[], official_field_classification, grades, publication_facts[], language_proofs[], prior_awards[], current_funding[], expected_graduation_date, overseas_plan, conference_plan`。

每個可能隨時間變動的值可附 `valid_at / valid_from / valid_to`。`prior_awards` 與 `current_funding` 要有方案、核定梯次、領取起訖與款項性質。未知清單與「確認沒有」分開，例如 `{ status: "unknown", items: [] }`。

國籍、入學身分、戶籍是不同欄位；博士五年級不能推定入學日、休學經驗或過往領獎。育兒、弱勢、身心障礙等延長／加額條件預設不蒐集，使用者需要時才在本機選擇「有適用例外待確認」；不要求診斷或證明上傳。

### 4.4 比對輸出

`MatchResult` 必含：`opportunity_id, data_revision, rule_set_version, profile_as_of, evaluated_at, criteria_status, application_status, evidence_status, rule_results[], missing_fields[], manual_questions[], applicable_procedure_id, next_required_step, actionable_deadline_id, funding_conflicts[], explanation`。

- `criteria_status`：`matches_known_rules | fails_known_rule | needs_information | needs_manual_review`。
- `application_status`：`not_open | open | closed | rolling | unannounced | suspended | unknown`。
- `evidence_status`：`current | stale | conflicting | incomplete`。
- 每條 `rule_results[]` 有 `rule_id, outcome(pass/fail/unknown), expected, actual, evaluated_for_date, evidence_ids, explanation`。
- 多種問題可同時存在；即使因明確條件而不符，仍保留其他未知及衝突，不把它們刪掉。

## 5. 資格比對的可執行邏輯

使用可審查的決定式規則，不用 LLM 給資格分數。規則 AST 支援 `all`、`any`、`not` 與葉節點；葉節點支援 `eq, in, gte, lte, exists, before, on_or_before, overlaps`。欄位型別、日期粒度及比較對象須經 schema 驗證；禁止任意程式碼或 `eval`。

葉節點必要欄位為 `id, field, op, value, assessed_at, evidence_ids, message`；`assessed_at` 可引用 `deadline:<id>`、固定日期或 `benefit_period`。涉及人工裁量的內容放 `manual_checks`，不得任意化成 true。

示例（只示範教育部年級條件，不代表完整方案）：

```json
{
  "id": "moe-doctoral-year-limit",
  "field": "study_year",
  "op": "in",
  "value": [1, 2, 3],
  "assessed_at": "2026-09-01",
  "evidence_ids": ["ev-ntu-moe-115-year"],
  "message": "115年9月須為博士班一至三年級"
}
```

三值邏輯：`all` 有 fail 即 fail，全 pass 才 pass，其餘 unknown；`any` 有 pass 即 pass，全 fail 才 fail，其餘 unknown；`not(unknown)` 仍 unknown。`exists` 遇到未知值回 unknown；文件已知尚未備齊，應呈現「需補文件」，除非已超過補件期限或規則明定，不能直接當成不具資格。

整體判斷順序：

1. 選出正確年度、梯次、適用學校路徑與規則版本。
2. 確認該規則在資格認定日有效；未知版本不能借用去年的限制。
3. 評估客觀條件、兼領／既往領獎限制，再列出人工認定事項。
4. 有可靠且適用的硬性 fail → `fails_known_rule`；關鍵來源有衝突或需裁量 → `needs_manual_review`；其餘有缺值 → `needs_information`；所有必要條件有證據且通過才給 `matches_known_rules`。
5. 另算受理與證據狀態。只有當期受理、適用路徑確認、關鍵來源完整且新鮮的資料，才可列入「目前可準備申請」；文字仍不得保證獲獎。

領域判斷須分開「系所／學程所屬領域」「論文主題」「主辦機關學門認定」。職能治療研究可能含社會議題，但不能僅憑關鍵字斷言符合人社方案。過往得獎名單只能作探索線索，不能替代本期資格規則。

## 6. 截止、程序與提醒

### 日期儲存與推導

- `Deadline.kind` 為 `fixed | relative | rolling | unknown`；`precision` 為 `datetime | date | month | unknown`；`value` 只填與粒度相符的值。
- `timezone` 預設 `Asia/Taipei`，以來源明載為優先；保存原始「115年11月26日下午5時」及標準化值。
- 日期而未寫時刻，不能補成 23:59。當天顯示「今日截止，時刻待確認」，只在日期過後確定已截止；ICS 使用全天日期事件，另註時間未明。
- `cutoff_semantics` 為 `inclusive | exclusive | unknown`；「前」「止」的邊界若未能確定，臨界時刻顯示待確認，不虛構多一秒的送件空間。
- 相對期限要存規則，例如「會議首日所屬月份之前一個月之首日」，並區分國科會彙送與學校／系所送件。必要的假日順延要使用有來源、適用該主管機關的日曆，不能只用週末推算。
- 未公告次年度只能顯示「尚未公告」；歷年月份可用來排定維護者查核，不能生成一個假的截止日期。
- 網頁不見、抓取失敗不能推論方案停辦；到期顯示依時間計算，資料新鮮度另行標記。

### 使用者提醒

MVP 以站內清單、收藏與 `.ics` 為主。提供 30／14／7／3／1 天的建議提醒，允許使用者修改；沒有精確截止時刻的事件不可產生看似精確的倒數。預設以適用申請路徑中「下一個尚未完成、學生必須掌握的有效期限」提醒，同時顯示後續各層期限。

ICS 依 [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html) 產生：穩定且不含個資的 `UID`、`DTSTAMP`、`SEQUENCE`，明確時刻可轉 UTC；更改期限沿用 UID 並增加 SEQUENCE。取消事件輸出取消狀態，保留異動說明。處理中文字、換行、跳脫及折行；不放使用者國籍、薪資或個案資訊。

下載後匯入的 ICS 是快照，不會自動更新。公開日曆訂閱的刷新由日曆軟體控制，不能承諾即時；VALARM 也不保證每個用戶端執行。介面必須明示這兩點，並提供回站核對連結。MVP 不在使用者關閉網站後自行發送背景通知。

後續若做 Email／推播，先另行確認服務需求：明確訂閱與退訂、最少資料、通知紀錄、重試與去重鍵 `subscription + deadline + revision + offset`；重大更正通知不受一般截止提醒去重誤擋。本次不建立任何實際通知或排程。

## 7. 法規、最低工資與 RA／TA 權益

### 法規版本化

法規、法規命令、行政規則、函釋、校規與一般公告要標示不同類型與位階，不統稱法律。保存修正與生效證據；新版本生效前，舊版仍可為現行有效版本。條文分階段施行時，以 `articles[]` 各自的有效區間處理，不只放一個整部法的生效日。

版本選擇依事件日、勞務提供日、資格認定日及過渡條款；資料何時抓到則由 `retrieved_at` 記錄。有效期間統一用 `[effective_from, effective_to)`；未知生效日保留 null 及 `commencement_state=unknown`，不得自動套用最新公布全文。

每版保留官方全文連結、文號、條號定位、內容雜湊、差異摘要與審核人。允許公開重製的文件才保存全文；否則保留必要證據與連結。更正抽取錯誤產生資料修訂，不偽裝成官方修法。

實際例子：[個人資料保護法官方頁](https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=I0050021) 在本次查核時標示部分修正條文尚未生效。系統不能僅依「最新修正日期」認定全部新條文都已施行。

### 工資資料

經查 [勞動部 1140148807 號公告](https://laws.mol.gov.tw/FLAW/FLAWDOC03.aspx?datatype=etype&ecase=%E5%8B%9E%E5%8B%95%E6%A2%9D+2&ecode=N00000&edate=20251021&eno=1140148807)，2026-01-01 起每月最低工資為新臺幣 29,500 元，每小時為 196 元。來源與生效日應跟著數值儲存，不能寫死在畫面。

月薪與時薪不得直接互除產生另一種法定標準。最低工資適用對象依 [最低工資法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030028) 判斷；研究獎助金、全時月薪、部分工時工資也不能混為一談。未生效的新年度公告獨立顯示；本文件未建立 2027 年數值的正式資料紀錄。

MVP 若提供工資檢核，只做適用性已確認的單一時薪與正常工時比較，列出計算假設；不以月領總額低於 29,500 元就判斷部分工時助理違法，也不計算複雜加班費或追討金額。

### 權益指南最低八篇

1. 學習關係與僱傭關係如何區分：實際指揮監督、報酬對價、工作內容與書面文件。
2. 聘僱契約、雇主是誰、工作範圍、薪資及出勤紀錄。
3. 最低工資、薪資明細與經費來源的關係。
4. 工時、休息、加班、例假與請假應查哪些條文。
5. 勞保、就保、職災保險與勞退：分開檢查適用對象、投保／提繳及各自窗口，不用「有保險」一欄取代。
6. 同一人兼具獎助生與受僱身分時，如何分辨不同活動與款項。
7. 國際學生的入學、居留、工作許可與勞動保障分別查核；細則未核對前只提供官方查詢入口。
8. 校內權益爭議、勞動申訴／檢查、調解及其他救濟的分流與證據準備。

分流依據包括 [教育部獎助生權益保障指導原則](https://edu.law.moe.gov.tw/LawContent.aspx?id=GL001889) 與 [勞動部兼任助理勞動權益保障指導原則](https://laws.mol.gov.tw/FLAW/FLAWDAT0202.aspx?id=FL077250)。不能只因簽了「學習型」文件就忽略實際勞務情形；問答結果只能提示應核對的關係與程序。

申訴分流至少包含：校內承辦／研究生業務、學生申訴評議窗口、勞務提供地地方勞工行政機關、勞檢／調解窗口。勞資爭議調解路徑參考 [勞動部說明](https://www.mol.gov.tw/1607/28690/89680/)，臺大校內程序參考 [學生申訴專區](https://advisory.ntu.edu.tw/CMS/Page/252)。詢問或協調不能被描述成一定會停止法定期限；救濟期限與起算事件未查清時，直接標明待專業確認，禁止自動產生訴願或申訴倒數。

## 8. 官方來源登錄與可信度

### 分級與衝突處理

| 層級 | 來源 | 可支持的內容 |
|---|---|---|
| A1 | 主管機關法規庫、正式公報、正式方案／核定文件 | 法規、制度及當期規定；仍須確認效力、附件與適用年度 |
| A2 | 主辦機關當期徵件公告與正式附件 | 當期條件、主辦期限與申請程序 |
| B1 | 學校／學院／系所對所屬學生的正式公告 | 該校、院、系所的收件程序、推薦與內部期限 |
| B2 | 官方 FAQ、簡報或承辦書面回覆 | 輔助解釋；範圍與法源另核對；私人回覆先取得可公開同意 |
| C | 學生組織、基金會正式網站、新聞、社群或第三方整理 | 自辦方案可為第一手來源；轉述他人規則則僅供發現線索 |

可信度、文件新鮮度、全文是否讀到是三個維度，不製造看似精確的可信度百分比。不能單靠 `.gov.tw` 或 `.edu.tw` 判斷有效性。基金會自己的獎助公告可是一手來源，不能因非政府就直接當不可信。

衝突先比對是否其實是不同年度、不同身分、不同送件層級。國科會期限與臺大校內期限不同，通常是程序差異，兩者都保留；同一期同一資格真的矛盾時標記 `disputed`，暫停肯定資格推薦並交人工查明。一般摘要不能擅自覆蓋正式規範，校內公告亦不能被預設為有權改寫上位法。

### 首批來源清單（研究日已查得；非每一附件都已全文核對）

| ID | 官方來源與直接連結 | 本次用途／查核界線 |
|---|---|---|
| S01 | [教育部獎助學金專區](https://www.moe.gov.tw/Content_List.aspx?n=DBDDB8DC17D0D8C4) | 全國資料發現入口；各子方案仍要逐案查核 |
| S02 | [115 年國科會博士生研究獎學金試辦方案](https://www.nstc.gov.tw/sci/ch/detail/24ad4e4a-bd37-4ba0-9955-5b2e2ffd5ac6) | 找到當年度官方頁與附件名稱；方案 PDF 尚待全文擷取與人工核對 |
| S03 | [臺大校級博士獎學金一覽](https://www.aca.ntu.edu.tw/w/aca/GAADService_24102208484895715) | 已讀網頁；115 年國科會申請年級不限；教育部限一至三年級 |
| S04 | [臺大校級博士生獎學金](https://www.aca.ntu.edu.tw/w/aca/GAADService_21071211271211713) | 已讀網頁；校內程序、各方案限制、當期資料與版本落差 |
| S05 | [臺大博士生獎學金設置辦法，114-04-23 版 PDF](https://www.aca.ntu.edu.tw/WebUPD/aca/GAADRules/國立臺灣大學博士生獎學金設置辦法1140423.pdf) | 已讀 PDF；第三條舊生依國科會各年度規定；後續不可當成所有年度同一規則 |
| S06 | [國科會人社博士候選人論文獎勵作業要點](https://law.nstc.gov.tw/LawContent.aspx?id=FL039061) | 已讀全文；115-01-23 修正；候選人、系所領域、論文領域等條件分開 |
| S07 | [臺大 115 年人社論文獎勵公告](https://www.aca.ntu.edu.tw/w/aca/GAADNews_26020916123732454) | 已讀官方公告；2026-02-09 發布、3/24 中午 12 時校內截止；有函轉校內各系所之附件名稱 |
| S08 | [臺大醫學院 115 學年度研究生優秀著作獎公告](https://rd.mc.ntu.edu.tw/bomrd/ntu2/news_txt.asp?pno=7296) | 官方搜尋可讀公告內容：2026-10-28 發布、11/26 17:00 截止；直接頁面存取曾失敗，附件細則未核對，須標 `official_index_only` |
| S09 | [醫學院研發分處表單／辦法頁](https://rd.mc.ntu.edu.tw/bomrd/ntu2/form0.asp?LTPno=52&ntPno=&pno=27) | 官方索引與入口；本次擷取不完整，最新著作獎辦法與表單待確認，不能以舊年表單補入本期資格 |
| S10 | [國科會研究生出席國際學術會議作業要點](https://law.nstc.gov.tw/LawContent.aspx?id=FL038260) | 已讀全文；在學、非在職專班、論文與推薦、相對彙送期限、年度次數限制 |
| S11 | [116 年度千里馬申請須知](https://www.nstc.gov.tw/folksonomy/rfpDetail/fb285d89-02c6-4a01-a256-580b4c434822?l=ch) | 已讀公告；115 年申請／116 年出國，不能混成年份相同 |
| S12 | [國科會 115 申請、116 出國頁](https://www.nstc.gov.tw/sci/ch/detail/9fea56ff-9a28-4304-abb3-192109491942) | 官方資料支持 2026-07-31 中午 12 時機關線上送出及後續函送步驟 |
| S13 | [臺大千里馬校內公告](https://www.aca.ntu.edu.tw/w/aca/GAADNews_26051910555788878) | 已讀公告；臺大學生線上申請至 2026-07-29 08:00，早於機關期限 |
| S14 | [教育部獎助生權益保障指導原則](https://edu.law.moe.gov.tw/LawContent.aspx?id=GL001889) | 已讀；學習與勞動分際、校內權益機制 |
| S15 | [勞動部兼任助理勞動權益保障指導原則](https://laws.mol.gov.tw/FLAW/FLAWDAT0202.aspx?id=FL077250) | 官方全文；僱傭關係綜合判斷 |
| S16 | [勞動基準法](https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=N0030001) | 工資、工時、休假及申訴等條文的版本來源；指南發布前逐條核對 |
| S17 | [最低工資法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030028) | 已讀適用對象、月與時薪及工資最低標準相關條文 |
| S18 | [勞動部最低工資 1140148807 號公告](https://laws.mol.gov.tw/FLAW/FLAWDOC03.aspx?datatype=etype&ecase=%E5%8B%9E%E5%8B%95%E6%A2%9D+2&ecode=N00000&edate=20251021&eno=1140148807) | 2026 工資數值與生效證據 |
| S19 | [勞工退休金條例](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030020) | 已讀官方頁；適用對象、雇主提繳等細節需按個案身分與版本核對 |
| S20 | [勞工職業災害保險及保護法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0050031) | 官方版本來源；不得與一般勞保混成一項 |
| S21 | [勞動部：發生勞資爭議怎麼辦](https://www.mol.gov.tw/1607/28690/89680/) | 勞務提供地地方主管機關調解及相關資源 |
| S22 | [臺大學生申訴專區](https://advisory.ntu.edu.tw/CMS/Page/252) | 校內官方入口；須再核對最新辦法與個案適用條件 |
| S23 | [個人資料保護法](https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=I0050021) | 個資及部分條文未生效標示；不可只抓最新全文當現行法 |
| S24 | [著作權法](https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=J0070017) | 第 9 條等；官方網站上的其他素材不因此一律可重製 |
| S25 | [政府資料開放授權條款第 1 版](https://data.gov.tw/license) | 僅在資料明確依該條款釋出時適用，保留顯名及來源要求 |
| S26 | [臺大醫學院職能治療博士班修業進度官方文件](https://www.mc.ntu.edu.tw/manage/upload/fp/f_20250820160641092.pdf) | 學校／醫學院／系所博士班對應線索；不是任何獎助方案的資格依據 |
| S27 | [臺大教育部博士獎學金第二梯次 PDF](https://www.aca.ntu.edu.tw/WebUPD/aca/GAADService/1151015_教育部博獎第二梯申請.pdf) | 已讀；仍限一至三年級；11/9 是學院送推薦名單，不能當成學生統一截止 |

## 9. 更新頻率、人工審查與資料品質

以下是上線後的維護提案；本次未啟用排程。

| 類型 | 自動查核建議頻率 | 人工與異常處理 |
|---|---|---|
| 主辦機關／學校公告索引 | 每日一次 | 新徵件與新附件進待審；避免每次輪詢所有歷史文件 |
| 受理中獎助的關鍵頁／附件 | 每日一次；14 天內截止可每 12 小時 | 重大異動 1 個工作日內處理；未核定前不自動發布新資格或期限 |
| 未公告下一期的既有方案 | 每週一次，歷年公告季每日一次 | 只提高查核頻率，不推算截止日 |
| 法規庫、最低工資與新公告 | 每日查公告索引；既有全文每週比對 | 生效日、過渡規定、條文差異需人工確認；生效前再查一次 |
| 申訴窗口與聯絡方式 | 每月一次 | 重大變更即查；連續失效時顯示替代官方入口 |
| 已截止歷史方案 | 每月連結檢查；每季盤點 | 不刪歷史、不誤標為當期；新年度另建 Opportunity |

HTTP 200 不等於內容已人工核對。`last_checked_at`、`last_success_at` 與 `last_content_reviewed_at` 分開保存。重大頁面 hash 改變時，舊結論顯示「來源異動待覆核」；不能以網站導覽列或訪客數變動當成修法。

新鮮度門檻：受理中關鍵來源超過 48 小時未成功確認，或發現實質異動尚未處理，標示待重查；其他現行法規超過 7 天未成功查核、窗口超過 35 天未查核，也標示過期。這是資訊品質標記，不代表法律失效。

高風險欄位（資格、金額、截止、生效、兼領、返還、救濟程序）至少一位非原編輯者覆核。志工量能不足就維持待審、縮小覆蓋或延後發布，不降低核對門檻。自動抓取只建立候選差異，不自動合併高風險內容。

同一制度由多校轉貼時，以 Program 去重、年度／梯次與路徑分流；不同系所的截止不合併。疑似重複只建議合併，維護者確認並保留舊 ID 轉址。重要更正保留公開紀錄及受影響欄位。

## 10. 爬取合規、隱私與安全

優先使用官方開放資料、API、RSS、公開 HTML 與正式附件；再考慮少量人工轉錄。來源登錄先記錄使用條款、授權、robots 與存取限制，再決定允許自動抓取、僅人工維護或只提供連結。

遵守 [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) 的 robots 規則；robots 不是著作權授權，也不是存取授權。保守預設：robots 暫時無法取得或條款有疑義時先停止自動抓取，轉人工處理；未禁止也仍須檢查條款及可重製範圍。

爬取規格：每網域同時 1 個請求、預設至少間隔 5 秒，依站方更嚴限制調整；使用可辨識 bot 名稱與專案聯絡頁；ETag／Last-Modified 條件請求；429 尊重 Retry-After，5xx 指數退避且設嘗試上限。只抓已登錄白名單來源，限制轉址次數、檔案大小與解析時間。停止要求收到後先停抓再處理。

不得繞過登入、CAPTCHA、付費牆、封鎖或技術限制，不使用學生帳號掃描校務系統、不猜測未公開附件路徑。搜尋可見的個人領獎名單不納入個人資料庫；PDF 如含學號、簽名或私用聯絡方式，不直接複製進公開 repo。

只保留必要摘要、欄位、短證據及來源，全文快照須有重製依據；雜湊不能取代授權，也不能單獨證明當時的完整內容。撤下違規素材時，連 Git 歷史、公開附件與發布包一併評估移除，留下不含受限內容的更正說明。

Profile 預設僅在記憶體處理，使用者選擇「記住此裝置」才存本機；提供清除與本機匯出。個人條件不放 URL、公開 issue、遙測、錯誤日誌或日曆事件。MVP 不啟用第三方追蹤，也不把資料傳給 LLM。網站託管仍可能產生存取紀錄，隱私說明需如實揭露託管商、保留期限與處理方式，不能宣稱零資料痕跡。

來源文字一律當資料，不執行其中程式或指令。清理 HTML、限制外連協定、避免 XSS；爬蟲阻擋本機／私有網段及轉址後的 SSRF。公開 PR 不執行不可信下載內容、不拿到 secrets，CI 最小權限；鎖定依賴、檢查授權與漏洞，設定安全問題私下回報方式。

## 11. 無障礙與可用性

驗收目標採 [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/)。提供語意 HTML、正確標題層級、跳到主要內容、鍵盤全流程、可見且不被遮住的焦點、表單標籤與錯誤提示。正常文字對比至少 4.5:1、大字 3:1、關鍵非文字元件 3:1；狀態不能只用顏色。

支援 200% 文字放大及 320 CSS px 寬度重排；複雜表格有清楚標頭及可讀替代呈現。互動目標依 AA 例外與 24×24 CSS px 最小要求處理，主要操作以 44×44 為設計目標。篩選更新要適度告知結果數，不搶焦點、不連續播報整頁。

標記 `lang=zh-Hant-TW`，外文片段另標語言。完整日期同時呈現西元、必要時附民國，不只寫「下週」。減少動態、支援 prefers-reduced-motion、沒有強制拖曳或懸停才顯示的必要內容。

官方 PDF 可能不可及，提供自行整理的 HTML 重點、原文定位與連結；不能因 OCR 成功就宣稱附件本身無障礙。基礎列表、詳情與官方連結在 JavaScript 關閉時仍可讀；個人比對需要 JavaScript 時顯示清楚說明及人工篩選替代。

## 12. 開源授權與社群治理

建議授權組合（待使用者確認）：

- 程式碼、測試與建置腳本：[MIT](https://opensource.org/license/mit)。
- 團隊原創指南、原創摘要與可授權的資料編輯部分：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh-hant)。
- 政府開放資料：保留原本的 [政府資料開放授權條款](https://data.gov.tw/license) 或其他指定授權及顯名聲明。
- 法律、命令、公文等依著作權法第 9 條檢查其性質；官方網站上的圖片、新聞素材、私人基金會文件與資料庫編排不能一概當作可重授權。

每筆 Source／Evidence 記錄 `license`、`reuse_basis` 與署名；無明確重製依據的第三方附件僅提供連結。整包資料匯出附授權清單與第三方例外，不將所有來源文件套上 MIT 或 CC BY。純事實本身與團隊的摘要、編排分開說明。

未來 repo 必備 README、CONTRIBUTING、CODE_OF_CONDUCT、SECURITY、資料編輯政策、隱私與授權說明、第三方來源清單、issue／PR 範本。貢獻者需聲明提交內容具有適當權利；採 DCO 簽署可作為輕量流程，暫不要求額外 CLA。

維護角色：產品維護者決定範圍；資料編輯者抽取與撰寫；覆核者檢查重大欄位；法律／勞動顧問於有爭議內容協助審閱。角色可以兼任，但重大內容不能自己編、自己作唯一覆核。商業贊助與推廣方案需揭露，不影響資格排序或來源判斷。

## 13. 技術架構：先用靜態網站與 Git 資料

產品決策：**單一 repo、Astro 靜態輸出、TypeScript、結構化 JSON 與 Markdown、GitHub Actions 驗證及產生資料差異。** Astro 的 [Content Collections](https://docs.astro.build/en/guides/content-collections/) 可配合結構化內容與型別驗證；實作時使用當時穩定版、相容的 Node LTS，記錄版本並提交 lockfile，不使用 preview 或無鎖定版本。

```text
官方來源 → 允許的抓取／人工整理 → 候選資料與差異
                                   ↓
                             schema 與證據檢查
                                   ↓
                              人工覆核與合併
                                   ↓
                    公開 JSON／CSV／RSS／ICS＋靜態網站
                                   ↓
                    瀏覽器本機 Profile → 決定式資格比對
```

JSON 是單一資料來源；CSV、搜尋索引與網站皆由建置產生。schema 以 JSON Schema 為唯一權威，TypeScript 型別由它產生；Astro 接收已驗證資料，不維護另一套手寫欄位定義。schema 驗證器優先使用現有相容套件，例如 Ajv；正式選版時依穩定版文件確認。

資格引擎為純函式，可在瀏覽器與測試共用；時間由呼叫端注入，避免測試依賴當下時鐘。首批少量資料採瀏覽器本機篩選與關鍵字搜尋，不先加搜尋服務、向量資料庫、帳號或常駐後端。資料量或效能量測真的超出需求，再考慮索引方案。

MVP 的收藏與 Profile 不送伺服器。公開 RSS／ICS 是靜態端點；個人選取的 ICS 在本機生成。公開訂閱僅按方案或學校類別提供，不攜帶個人資格。

部署預設 GitHub Pages 或同等可匯出靜態託管；在使用者確認部署以前，只交付本機可預覽的建置。定時抓取可用 GitHub Actions，但這類排程可能延遲，不能拿來承諾準時提醒；有失敗面板、最後成功時間、手動重跑與維護者責任人。

未來資料庫升級門檻：多人同時編輯頻繁衝突、審核隊列明顯無法用 PR 管理，或確定需要私人訂閱。屆時提出資料移轉與隱私設計，不在首版先架設。

建議目錄（僅提案，本次沒有建立）：

```text
data/organizations/ programs/ opportunities/ sources/ evidence/ laws/ wages/ routes/
content/rights/
schema/
src/pages/ components/ lib/
scripts/ingest/ validate/ export/
tests/fixtures/ unit/ e2e/
docs/decisions/ data-policy/
```

## 14. 首個資格篩選案例：臺大職能治療博士五年級

### 14.1 已知、未知與測試假設

合成測試條件（僅供規則測試，不代表特定個人的學籍）：國立臺灣大學、職能治療所博士班、五年級、已取得博士候選人資格。產品應保留使用者原始系所稱呼；依 S26 可建立「醫學院職能治療學系博士班」的官方別名對應，仍須確認系統正式代碼。

測試 Profile 使用虛構 ID，不含姓名、學號與聯絡資訊。**不能從此推定使用者是本國籍、全職、無收入、無其他獎學金或有第一作者論文。** 一般經濟困難描述不能直接當成低收入戶資格證據。

```json
{
  "id": "fixture-ntu-ot-phd5-candidate",
  "profile_version": 1,
  "as_of": "2026-10-28",
  "school_id": "ntu",
  "college_id": "ntu-medicine",
  "department_id": "ntu-occupational-therapy",
  "degree": "phd",
  "study_year": 5,
  "study_year_at": [],
  "candidate_status": true,
  "candidate_obtained_at": null,
  "citizenship": null,
  "admission_identity": null,
  "enrollment_status": null,
  "full_time_student": null,
  "full_time_paid_job": null,
  "research_topics": null,
  "prior_awards": { "status": "unknown", "items": [] },
  "current_funding": { "status": "unknown", "items": [] },
  "publication_facts": null,
  "conference_plan": null,
  "overseas_plan": null
}
```

測試時鐘固定為 `2026-10-28T12:00:00+08:00`，僅為可重現測試時間，不宣稱這是查核當下時刻。需要判斷「115 年 9 月年級」時，原始 Profile 因缺歷史資訊應追問；另設擴充 fixture 明確填入 `study_year_at[{date:"2026-09-01",value:5}]`，這是測試補充值，不是使用者另行確認的事實。

### 14.2 真實方案的預期輸出

| 測試 | 來源支持的事實 | 預期結果與理由 |
|---|---|---|
| T01 醫學院 115 學年度研究生優秀著作獎 | S08 官方搜尋可讀公告指出本日發布、2026-11-26 17:00 截止；最新附件尚未完整核對 | `criteria=needs_manual_review`、`application=open`、`evidence=incomplete`；顯示「公告顯示受理中；完整資格待覆核」。不能只因五年級或候選人就通過；作者序、發表日期、學籍、推薦與重複得獎等應先讀本期辦法，再詢問使用者，不把舊年限制當成本期事實 |
| T02 國科會人社博士候選人論文獎勵，115 年 | S06 同時要求符合的系所領域、論文主題與候選人等條件；S07 臺大 3/24 12:00 截止 | `criteria=needs_manual_review`、`application=closed`；職能治療系所與題目是否落在規定範圍須官方確認；已取得候選人資格也尚缺取得日期，不能證明 3/24 前已有資格；不得顯示現在可申請 |
| T03 臺大 115 學年度國科會博士生研究獎學金 | S03 說明年級不限，S04 有就業、身分、兼領與校內評選限制；S02 原方案附件待覆核 | `criteria=needs_manual_review`、`application=unknown`、`evidence=incomplete`；年級這一條不能 fail。職能治療系所當期截止、是否補徵／候補、先前受獎與其他條件待查；不能用別系期限或一般月份推定目前可送件 |
| T04 臺大教育部博士生獎學金，115 學年度含第二梯 | S04／S27 限 115 年 9 月一至三年級 | 原始 Profile：`needs_information`，要求確認 9 月年級；加入 9/1 五年級 fixture：`fails_known_rule`。即使有第二梯，也不因候選人身分免除年級限制。學生期限未核對前 `application=unknown`，不把學院 11/9 送件日作為學生截止 |
| T05 國科會研究生出席國際會議 | S10 允許符合資格的碩博士生，另有在學、非在職專班、論文與推薦等條件 | `criteria=needs_information`、`application=unknown`；未有會議日期不能算相對期限；五年級與候選人不是自動排除條件，仍需確認今年是否已獲補助 |
| T06 千里馬，115 申請／116 出國 | S11–S13；臺大 2026-07-29 08:00 截止，國科會機關線上 7/31 12:00；有戶籍、在學、推薦、畢業前完成及既往補助限制 | `criteria=needs_information`、`application=closed`；五年級不構成此資料所列的獨立排除條件，但畢業前完成研究等尚未知。2027 年出國不代表 2027 年才申請 |
| T07 RA／TA 權益 | 目前不知道是否擔任助理、雇主、實際工作與報酬 | 不給「適用最低工資」或「違法」結論；先引導分流與確認事實，仍可閱讀完整權益入口 |

上述是首批回歸案例，不是使用者可申請的完整清單。尤其 T01 的受理資訊與資格完整度必須同時顯示；來源未覆核前，不能升級為肯定資格推薦。

### 14.3 行政公告疑義的證據設計

S07 證明臺大校級有公開 115 年人社獎勵公告，頁面並列出「函轉校內各系所」附件名稱。這能反駁「臺大完全沒有公布」的絕對說法，**不能證明職能治療系所有無收文、何時收文、是否完成通知，也不能直接證明行政瑕疵。**

資料平台可記錄 `published_at, first_seen_at, issuing_org, forwarding_document_ref, recipient_scope, delivery_evidence_state`；頁面發布時間、爬蟲首次看到、行政送達時間分開。標準狀態為「已找到校級公告」「系所轉知情形待確認」，不能自動產生失職標籤。

若使用者日後要求個案處理，另查函文全文、受文範圍、系所收文／轉知紀錄、適用通知義務及影響；本專案不公開個人指控，也不在本次聯絡校方。

## 15. 測試策略與必要邊界案例

| 測試層 | 必驗內容 |
|---|---|
| Schema／資料完整性 | 所有 ID 與引用有效；年度、金額單位、日期粒度合法；已覆核關鍵欄位必有證據；未知不得用 0／false 取代 |
| 規則單元測試 | all／any／not 三值表；未知領獎史、候選人取得日、歷史年級；人工裁量；兼領與期間重疊；退學／休學／畢業情況 |
| 日期測試 | 民國與西元、學年度與出國年度、截止前／後與邊界未知、只有日期、時區跨日、閏年、相對月份與假日順延 |
| 法規測試 | 公布尚未生效、部分條文生效、過渡條款、舊事件套舊版、相同文件抽取修正與真正修法的區別 |
| 爬取回歸 | 官方 HTML、PDF、Big5／UTF-8、掃描附件與 OCR 待覆核、附件替換但 URL 不變、登入頁偽裝 200、403／404／429／5xx；以可合法保存且去個資的 fixture 測試 |
| 提醒／輸出 | ICS 可被至少兩種行事曆成功匯入；UID 穩定、更新 SEQUENCE、取消、中文、UTC 轉換、全天期限；RSS 與 CSV／JSON 一致 |
| 端到端 | 填 Profile→比對→查看理由與證據→收藏→下載 ICS；清除資料後重載無殘留；資料改版後收藏引用仍有效 |
| 無障礙 | axe 類自動檢查無嚴重／重大問題；人工鍵盤、NVDA＋Firefox 或 Chrome、放大／重排、狀態播報檢查 |
| 安全與隱私 | 不可信 HTML／URL、SSRF、個資不得進查詢字串／log／公開檔、公共 PR 無 secrets、依賴及授權檢查 |

特別回歸斷言：

1. T01–T07 全部符合表列結果；缺資料不自動通過。
2. 加入「人社相關論文題目」仍不能自動滿足人社方案對系所領域的要求。
3. 年級五年級不能被舊版「博士新生」規則誤殺於 115 年國科會方案。
4. T06 在 7/29 08:00 後不能因主辦期限尚未到而繼續顯示臺大學生可送件；精確臨界值按來源已確認的邊界語意處理。
5. 2026 工資測試：已確認適用的單純時薪案例 195 元應提示低於該期 196 元標準，196 元不提示低於；這不判斷整份契約是否合法。另用明確虛構的未來工資測試，證明生效前不覆蓋現值，不能拿虛構數值上站。
6. 來源抓取失敗不自動改成停辦；官方摘要仍存在也不能掩蓋附件未讀。
7. 任何公開輸出不得含測試使用者真實個資或未授權文件。

CI 必跑 schema、型別、規則／日期／輸出單元測試與網站建置；主要使用流程用 Playwright，關鍵頁做自動無障礙檢查。離線 fixture 為可重現基礎；實站連結與抓取檢查獨立執行，外站暫時失效不阻止純程式修補，但阻止該筆資料升級為已確認。

## 16. 里程碑與發布驗收

以下工作量以 1 位工程維護者加資料覆核支援估算，約 5–6 週；是規劃估計，不是既定承諾，等待官方回覆不計入可保證時程。

| 階段 | 預估 | 交付與通過門檻 |
|---|---|---|
| M0 規劃確認 | 使用者確認後開始 | 名稱暫案、MVP、授權與權責確認；才允許建立 repo；先檢查目標位置與既有規範 |
| M1 資料契約 | 第 1 週 | schema、來源政策、首批 10 筆機會、T01–T07 fixture；所有未知與衝突能表達，資料引用驗證通過 |
| M2 可閱讀原型 | 第 2 週 | 搜尋、詳情、來源、版本、覆蓋頁；至少 30 筆機會與 8 篇指南完成編輯，未核對者明確待審 |
| M3 比對與提醒 | 第 3 週 | 決定式引擎、時間與程序、收藏、ICS／RSS；核心回歸測試、個資不外傳驗證通過 |
| M4 維護與品質 | 第 4 週 | 2–3 個已允許來源的抓取試點、候選差異、人工審核、失效與更正流程；法規與工資歷程可重現 |
| M5 使用者測試與候選版 | 第 5–6 週 | 完成 8 人試用、無障礙人工測試、修正高風險錯誤；先交可預覽版本與驗收報告，未獲部署授權不公開部署 |

正式 MVP 發布須全部達成：

- [ ] 30 筆獎助機會達到第 2 節的全國性、學校與類別覆蓋門檻，且發布當日至少 5 筆已覆核仍受理；不以來源頁數灌水。
- [ ] 公開每一筆的年度、路徑、來源、最後人工核對時間與缺漏；核心欄位有逐欄證據，無證據的肯定結論為 0。
- [ ] 8 篇權益指南都有官方依據與日期適用說明；爭議或未覆核內容不偽裝現行法律結論。
- [ ] T01–T07、規則三值、校內／機關雙期限、法規生效與工資邊界案例通過。
- [ ] 期限與資格重大更正可追溯，來源失效、資料過期、未公告與停辦的標記彼此不同。
- [ ] ICS 在至少兩種日曆測試，清楚標示匯入不會自動更新；網站不承諾關閉後發送提醒。
- [ ] 主流程鍵盤與讀屏可完成；自動無障礙重大／嚴重問題為 0；已知限制列入驗收報告，未修正的 AA 阻斷問題不得宣告通過。
- [ ] Profile 留在裝置，清除與匯出有效；公開檔案、URL、log 與通知無個資。
- [ ] 全部離線驗證、型別檢查、測試、建置與公開輸出一致性檢查通過；一般手機測試下 5,000 筆模擬機會的本機篩選在 1 秒內完成，測試設備與測量方式記錄於報告。
- [ ] LICENSE、資料與第三方授權、貢獻、安全、隱私、更正、覆蓋政策完整；不能把第三方文件統一重授權。
- [ ] 至少兩位能接手的維護者明確接受責任，或揭露單一維護者的量能限制並縮小更新承諾；重大欄位覆核責任有具名承接者。
- [ ] 使用者試用至少 6/8 人達成第 1 節任務目標，高風險判斷錯誤為 0。
- [ ] 部署／公開發布的授權範圍已確認，發布資料是當日重新查核的版本；不是直接使用本文件日期的快照。

## 17. 後續 Codex 可直接接手的執行指令

> 本任務目前只核准規劃。先確認使用者是否已明確同意開始實作；沒有同意就停在閱讀與規劃，不能建立或修改 repo。
>
> 取得實作授權後，閱讀目標 workspace 的 AGENTS.md 與相關規範，確認既有檔案、名稱及使用者選定位置。採本文件的 MVP、資料契約與驗收規格，先完成 M1 資料與 fixture，再逐步實作網站、比對、日曆與維護流程。不要先部署或建立訂閱寄送服務。
>
> 每筆真實資料先查官方當期公告、正式附件與適用院系所程序。S02／S08／S09 等缺少全文或附件的項目，保留待覆核；不得用搜尋摘要、往年辦法、其他系所期限或模型記憶補成完整條件。將問題列入資料待辦，不編造答案。
>
> 必須保持資格、受理、證據三軸狀態，並讓每項資格理由可追溯到來源與規則版號。確保臺大職能治療博士五年級案例不因舊年度限制而被誤排除，也不因候選人資格而被誤判為任何方案皆符合。
>
> 每個里程碑交付可執行預覽、資料缺漏、檢查結果及下一步。完成候選版後依第 16 節逐項驗收；對未完成項目如實報告，不宣稱全臺完整、法律認定或通知必達。取得必要發布授權後才對外部署。

---

本規劃已完成官方來源初查、需求與架構設計；尚未完成全臺方案蒐集、所有附件全文核對、個人完整資格審查、repo 建置、通知排程或部署。
