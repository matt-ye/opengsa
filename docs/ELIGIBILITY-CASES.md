# 合成資格情境與比對驗收

本文件定義 P1（博士五年級候選人）及 P1-A～P3 邊界變體之規則比對與申請時間視窗行為。可執行實作位於 [`scripts/evaluate_deadlines.py`](../scripts/evaluate_deadlines.py)，並由 [`tests/test_extraction_verification_deadlines.py`](../tests/test_extraction_verification_deadlines.py) 自動回歸驗證。所有日期均固定於 `Asia/Taipei`，確保結果可重現。

> **重要提醒**：規則比對結果僅反映已記錄條件與合成輸入之對應關係，**不代表官方資格已核定**；未提供之個人條件一律維持 `unknown`，絕不補猜。

## P1：博士五年級候選人

虛構 ID `SYNTH-NTU-OT-PHD5`；觀察日 `2026-10-28`；臺大（`NTU`）、醫學院職能治療學系博士班、五年級（`year_of_study=5`）、已取得博士候選人資格（`is_phd_candidate=True`）。只有當日觀察，**不推定 `2026-09-01` 或更早期限時的年級／候選人狀態**。

國籍、入學管道、在職與就業、在學註冊細節、清寒證明、候選人取得日 (`candidate_passed_on`)、現有獎助、著作、會議、國外研究、預計畢業及工作事實全為 `unknown`。不得加入姓名、學號、收入或真實帳戶。

執行 `python scripts/evaluate_deadlines.py` 對 `data/pilot.json` 10 筆樣本之實測結果與預期完全一致：

| 資料 ID | criteria 實測與預期 | application 實測與預期 | 理由與邊界驗證 |
|---|---|---|---|
| `ntu-tuition-115-1` | `needs_information` | `closed` | 需減免身分類別；不得套大學部 9/4 |
| `ntu-emergency-policy` | `needs_information` | `unknown` | 缺事故與適用項目；不把一般困難當低收入戶資格 |
| `ntu-nstc-phd-115` | `needs_information` | `unknown` | 五年級不是本期年級排除；仍缺就業、其他獎助與管道資訊 |
| `ntu-moe-phd-115-round2` | `needs_information` | `unknown` | 需要115年9月基準年級；目前10月五年級觀察不能代填9月基準 |
| `ntu-med-publication-115` | `needs_manual_review` | `open`（摘要觀察） | 完整辦法未讀 (`evidence_status=incomplete`)；候選人身分不能替代作者序等未知條件 |
| `ntu-president-114` | `needs_information` | `closed` | 畢業與學位考試條件未確認 |
| `nstc-grad-conference-policy` | `needs_information` | `unknown` | 缺會議日期、接受函、校內截止及當年已領紀錄 |
| `nstc-abroad-116-ntu` | `needs_information` | `closed` | 國籍設籍、申請時點在學與其他條件未知；以學生截止 7/29 08:00 判定，不套機關 7/31 12:00 期限 |
| `ntu-yuanxue-115-ordinary` | `needs_information` | `closed` | 截止日前候選人資格取得日與指定國科會申請結果未知 |
| `ntu-ta-policy` | `needs_information` | `unknown` | 此入口由單位申請；學生需查聘任，非一鍵申請獎學金 |

## 邊界變體（已納入單元測試驗證）

| 情境 | 增加的合成事實 | 實測與預期行為 |
|---|---|---|
| `P1-A` | 明示 `2026-09-01` 也是博士五年級 (`year_assessed_at_2026_09_01=5`) | 教育部115博獎年級規則判 `not_met`；**國科會115不限年級維持 `needs_information`，不得連帶被排除** |
| `P1-B` | 明示 `2026-01-30` 之後（如 `2026-05-01`）才通過候選人資格 | 遠學115一般補助判 `not_met` (`candidate_acquired_after_application_window`)，不能把10月候選人身分回填到1月 |
| `P1-C` | 只知道當年經濟拮据 (`economic_difficulty_informal=True`) | 清寒限定方案維持 `needs_information`，不能自動通過 |
| `P1-D` | 一方案 `allowed`，另一方案明示同期間 `prohibited`／`conditional` | `evaluate_compatibility_pair()` 不判 `allowed`；回傳 `prohibited` 或 `conditional` 並提示核對雙方來源與期間 |
| `P1-E` | 只知道某系所網站未搜尋到公告 | 學生窗口維持 `unknown`，不得推論沒有轉發、無法申請、方案停辦或行政違法 |
| `P2` 一般碩士生 | `SYNTH-MASTER`；NTU、碩二 (`degree="master"`)、當日觀察，其餘未知 | 博士專屬方案（國科會博獎、教育部博獎、遠學、國科會千里馬）全部判 `not_met`；會議／校長獎／急難維持 `needs_information` |
| `P3` 外籍博士生 | `SYNTH-INTL-PHD`；非中華民國國籍 (`nationality="international"`)、NTU博二 (`year_of_study=2`)、未知入學管道 | 教育部本國籍方案判 `not_met` (`nationality_not_met`)；**國科會核配方案維持 `needs_information`（須確認逕博／國際處管道，不一律排除）** |

## 日期與申請時間判斷邊界

- **無會議日期**：不生成期限，回傳 `unknown` (`missing_conference_start`)。若合成會議首日為 `2027-03-15`，國科會機構彙送基準為 `2027-02-01`、臺大學生校內基準為 `2027-01-31T17:00:00+08:00`、接受函補送為 `2027-02-15`，並標記 `calendar_status=unverified`；不算成 `2/13` 或固定前30天。
- **跨年與閏月**：會議首日 `2027-01-10` → 國科會機構基準 `2026-12-01`、臺大學生基準 `2026-11-30T17:00:00+08:00`；閏年 `2028-03-15` 四週前補送為 `2028-02-16`（跨越 `2028-02-29`）；FAOS 會前兩個曆月對 `2027-04-30` 為 `2027-02-28`（閏年 `2028-04-30` 為 `2028-02-29`）。
- **醫學院與 FAOS 分流**：醫學院國際事務為會前 28 天送件且無接受函事後補送 (`acceptance_supplement=null`)；FAOS 為會前兩個曆月由學校提出，學生校內截止維持 `unknown`，不套用會前60天或國科會補送規則。
- **碩博學費減免（僅日期無時間）**：`2026-08-13` 為 `date`，當日評估標記 `same_day_time_unconfirmed=true`（若傳入當日具體時分則回傳 `unknown`），嚴禁倒數到 `23:59` 午夜。
- **國科會赴外研究臺大路徑（多層日時分流）**：學生 `2026-07-29T08:00:00+08:00`、機關 `2026-07-31T12:00:00+08:00`、學校備函 `2026-08-06` 分開；於 `2026-07-30` 評估時，因學生截止已過，學生受理狀態必為 `closed`，絕不因機關 7/31 尚未到期而誤判 `open`。
- **教育部第二梯（僅有學院期限）**：`2026-11-09` 為學院送校期限，學生向系所截止未知時，於 `2026-10-28` 維持 `unknown` (`student_deadline_unknown`)，不把 `11/9` 當成學生截止日。
- **法規生效日**：公布日、修正日與生效日各自保留；僅有修正日時 `effective_from` 維持 `null`，不自動將修正日複製為生效日。
