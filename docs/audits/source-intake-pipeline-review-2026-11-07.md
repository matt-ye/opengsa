# 新來源到上架流程審查（2026-11-07）

範圍：main `dbe0e98`。未改資料、未觸發 workflow、未連外部來源網站。實跑都在 repo 副本，傳輸換成讀本機假頁，假頁只用 `scholarship.opengsa-synthetic.example`。重現腳本在 [`source-intake-e2e-2026-11-07/`](source-intake-e2e-2026-11-07)。

## 結論

**這條流程目前無法自動跑通。** 11 步中沒有任何一段能從使用者提交一路接到上架。

- **斷點：** 提交後沒有任何程式接手（第 1→3 步）；通過審核也不影響上架（第 10→11 步）；提案套用後 CI 和建置都會失敗（第 11 步）。
- **能用的部分：** 單一乾淨頁面的抓取、規則萃取和提案產生都實跑成功（第 6、8、9 步）。
- **最大的功能缺口：** 第 5 步。索引頁的資源列舉不出來，索引頁本身反而會變成一張卡。

標記說明：**已實跑**＝這次在副本實際執行；**實況**＝讀 GitHub Actions 的真實紀錄或 artifact；**僅讀碼**＝只讀程式。

## 1. 逐步對照

| # | 步驟 | 狀態 | 負責 | 輸入 → 輸出 | 下一步接得上嗎 | 依據 |
|---|---|---|---|---|---|---|
| 1 | 使用者提交 | 手動（只有表單） | `.github/ISSUE_TEMPLATE/resource-source.yml` | 人填 → 公開 Issue | **斷裂**：沒有 `on: issues`，也沒有腳本解析表單 | 僅讀碼：`scan-sources.yml:3-56`、`pages.yml:3-8` |
| 2 | 審核 | **不存在** | 無 | 無 | 沒有標籤、狀態或紀錄檔。`scan-reviews.json` 只審候選，不審提交 | 僅讀碼：`AGENTS.md:27` 明訂不自動建卡 |
| 3 | 新來源輸入 | 手動，無工具 | 手改 `data/scan-sources.json` | profile＋`allowed_hosts` | 手改後可接第 6 步。`propose_radar_update.py:41` 帶進的新 profile 一律 `enabled:False` | 已實跑（代替維護者手改），`--check-config` 通過 |
| 4 | 資訊鏈探索 | 手動，**斷裂** | `source_chains.py`（`source_chains` job）；`expand_sources.py`（無 workflow） | 手寫 registry → `work/` 的 JSON | **接不上**：輸出留在 artifact，沒有匯入程式；登記項要手填 `program_key`、`scope` | 已實跑：3 次請求，找到子連結。`source_chains.py:485-486`、`SOURCE-CHAINS-AND-TIMELINE.md:87` |
| 5 | 資源列舉 | **實質不存在** | `expand_sources.py:194-198` 只跟 `policy` 連結 | 索引頁 → 0 筆 | 見下方「索引頁實測」 | 已實跑 |
| 6 | fetch／抓本文 | 自動（已登記且輪到時） | `scan_sources.py` 的 `Fetcher` | URL → 記憶體內文字區塊 | 同一輪可接第 7、8 步。**新來源不保證輪得到**，見第 2 節 | 已實跑＋實況 |
| 7 | 整理待粹資訊 | 自動，但只限單一文件 | `html_document`、`document_ir` | 區塊 → 記憶體 | **跨文件斷裂**：資訊鏈找到的辦法不會併入同一筆萃取 | 已實跑：expand 把辦法變成第二張卡 |
| 8 | 粹取 | 自動（規則）＋手動（時間軌） | `extract_candidates.py`；`run_temporal_action.py` | 區塊 → 候選；候選 → 時間提案 | 候選可接第 9 步。**時間軌順序顛倒**：只讀 `source-review.json`，要先上 main 才能跑 | 已實跑：`run_temporal_action.py:114`、`yml:67` |
| 9 | 資訊彙整 | 自動（僅 scan 成功時） | `propose_radar_update.py` | 候選 → artifact（`repo/`、patch） | **斷裂**：只留 14 天 artifact，權限 `contents: read`，不開 PR。時間提案另外一份，也沒有匯入程式 | 已實跑：`yml:58-59,194-204` |
| 10 | 審核 | 手動，**斷裂** | `build_review_workspace.py` | 候選＋處置 → `pilot-proposal.json` | **與上架無關**，見下方「審核閘門實測」 | 已實跑 |
| 11 | 上架 | 手動，**會失敗** | 人工套用 → PR → `pages.yml` | `data/` → 網站 | 沒有套用程式；套用後 CI 紅燈、建置失敗 | 已實跑 |

### 索引頁實測

表單明確允許交「轉知頁、索引」（`resource-source.yml:22`）。假頁列了三筆獎助公告：

- **`expand_sources`：** 三個連結只留一個，0 張卡，也沒有往下抓。
  - 原因 1：`source_chains.py:66` 的關鍵字沒有「獎助學金」「論文獎」，另外兩個連結被濾掉。
  - 原因 2：留下的連結角色是 `related_call`，而 `expand_sources.py:194` 只跟 `policy`。
- **`scan`（通用 profile）：** 索引頁本身變成一張卡，狀態 `passed_with_gaps`。這個狀態在提案閘門內（`propose_radar_update.py:18`），所以會進提案。

### 審核閘門實測

- **未審核也能上架：** 候選狀態 `pending`、`promotion_ready: false`，修掉建置問題後照樣上網站和 RSS。
- **駁回無效：** 把「駁回」寫進 `data/scan-reviews.json` 後重建，卡片仍在網站與 RSS。`build_site.py`、`radar_metadata.py`、`build_feed.py` 都不讀這個台帳。
- **核准只動 pilot：** 核准流程本身可以跑通，產出 `pilot-proposal.json`，但網站的卡片清單來自候選檔（`build_site.py:88,97`），不是來自核准結果。

### 第 11 步的兩個硬傷

套用合成來源的提案後（基準 main 全部通過）：

1. **`build_site.py` 直接失敗：** `Candidate preview violates the pilot contract: ... checked_on is after snapshot`。原因是 `build_site.py:64-65,74` 把日期寫死成 2026-11-06。**今後任何新抓的候選都會讓建置失敗**，`check_data.py` 卻不會擋（它一樣回報 PASS）。
2. **`unittest` 有 10 項失敗：** 測試寫死總數，例如 `tests/test_feed.py:52`（254）、`tests/test_temporal_tracks.py:37`（64）、`tests/test_time_policy.py:25`（64）、`tests/test_verify_candidate_sources.py:51`（256）。

## 2. 離線實跑結果

假頁內容清楚：有資格、金額、申請期間、兼領限制、申請方式、結果公告，另連一份設置辦法。全程 16 次請求，都打在假網域。

| 階段 | 結果 |
|---|---|
| `scan_sources.py`（只掃合成來源） | 成功，1 筆候選，`passed_automated_checks` |
| `propose_radar_update.py` | 成功，64 → 65 筆，既有資訊鏈程式與規則數未變 |
| 手動套用後 `check_data`、`check_provenance`、`--check-config` | 通過 |
| 手動套用後 `unittest` | **失敗**：10 項 |
| 手動套用後 `build_site.py` | **失敗**：見上 |
| 只在副本把寫死日期改掉後 `build_site.py` | 成功，卡片進網站與 RSS（255 筆） |
| `run_temporal_action.py`（model off） | 成功，抓到 3/1 起、4/15 止 |
| 手動把時間提案蓋到 `data/` | 成功，網站才出現 `time_dates` |
| `build_review_workspace.py` 駁回、核准 | 都成功 |
| `source_chains.py` | 成功，但輸出無處可接 |
| `expand_sources.py` → 提案 | 成功，但同一方案變成 2 張卡 |
| 來源改截止日後重掃 → 提案 | 成功，舊卡被新版取代，總數不變 |

**結論的邊界：** 第 3、10、11 步的人工動作是我代做的，所以「成功」的階段不代表自動。

### 乾淨頁面也看得到的品質問題

檢核回報 `passed_automated_checks`、`missing_fields` 為空，但候選其實漏了很多：

| 欄位 | 假頁寫的 | 候選結果 |
|---|---|---|
| 申請起日 | 115年3月1日 | `unknown` |
| 學生截止日 | 115年4月15日 | 學生步驟 `unknown`；日期掛在 `actor: unit`（單位） |
| 兼領限制 | 同一學年度不得同時領取 | `unknown` |
| 申請方式 | 電子郵件 | `unknown` |

時間軌能把日期修正為 `fixed_window`，但沒有匯入程式，所以照常流程上架的卡會是 `procedure_only`。

### 排程實況（真實紀錄）

| Run | 日期 | 結果 | 待審 | 說明 |
|---|---|---|---|---|
| 41018618653 | 10-30 | 失敗 exit 2 | - | 舊版 state 不相容 |
| 41599746341 | 11-03 | 失敗 exit 2 | - | 同上 |
| 41990601168 | 11-05 | 成功 | 5 | 快取重建 |
| 42184228627 | 11-06 | 成功 | 12 | 變更 2；提案接受 2、**扣下 10** |
| 42349789801 | 11-07 | **失敗 exit 1** | 12 | 20 次請求用完，0 份成功，170 個來源因額度跳過；因失敗而沒有提案 |

### 對既有發現的複核

- **「scan 只寫 `work/`」：** 成立（已實跑）。
- **「`temporal_replay` 寫死 `source-review.json`」：** 成立（已實跑）。
- **F3「佇列滿 24 筆後卡死」：** 邏輯成立。真實 `scan()`＋真實設定＋假傳輸，第 6 輪起 HTTP 0、全部 `review_backlog_full`，合成來源排在最後，**11 輪內都沒被讀到**。**但時程要修正：** 實況目前 12 筆，還沒卡死。真實來源失敗多、變更少，累積比模擬慢。今天的失敗是另一個原因：額度被失敗來源用光。
- **新發現（已實跑＋實況）：** 待審項目只有當輪能取得內文。下一輪它就變成 `needs_context`，被提案閘門扣下（`scan_sources.py:476-483` 的 `allow_network_refetch=False`、`propose_radar_update.py:24`）。真實資料：11-06 有 10/12 被扣，11-07 是 12/12。**錯過當輪提案就只能靠頁面再次變更。**

## 3. 聲稱已完成但做不到的項目

| 位置 | 聲稱 | 實際 | 依據 |
|---|---|---|---|
| `README.md:138` | 回報新獎助來源 | 連到不存在的 `source-submission.yml`（實際是 `resource-source.yml`；網站頁首的連結正確） | 僅讀碼 |
| `README.md:68-74`、`scan-sources.yml:53` | 四軌排程，週日整併 | cron 沒有週日；排程只進 `scan` job（`yml:130`），它不分軌。分軌只在手動的 `temporal_replay`（`yml:67`） | 僅讀碼 |
| `README.md:74` | 增量閘門落實排程 | 閘門只在 replay，排程不經過 | 僅讀碼 |
| `README.md:18` | 1-to-1 精確時程覆蓋、覆蓋率 100% | 190/256 手寫（查核文件已載）；本次另見時間軌不回寫 | 既有查核＋已實跑 |
| [#57](https://github.com/matt-ye/opengsa/pull/57) | 全庫 202 筆依軌道「萃取」與上架 | 內文自述 Track 1–3 全是 `SKIP_UNCHANGED`（0 HTTP），並未抓取或萃取 | PR 內文 |
| [#62](https://github.com/matt-ye/opengsa/pull/62) | 通用資訊鏈落地（501 文件／334 連線） | 產生腳本沒有任何抓取程式；這些批次不在 `source-chain-index.json` 的 `bundles`，只有自己的測試讀 | 僅讀碼 |
| `AGENTS.md:78` | 每週二、五掃描 | 已是一週六次（`yml:54-56`），文件未同步 | 僅讀碼 |

**未找到的東西：** repo 文件和我讀過的 PR 中，沒有看到「11 步全自動」的明文。相反地，`SCANNER.md:11`、`REVIEW-WORKSPACE.md:78`、`RADAR-VIEW.md:36`、`AGENTS.md:27` 都明寫不自動。其他代理在對話中怎麼告訴使用者，我查不到，**未確認**。文件沒掛上的是：這些限制從未被整理成「整條流程還斷在哪」。

## 4. 修復工作（依依賴順序，只列不做）

| 順序 | 工作 | 大小 | 依賴 |
|---|---|---|---|
| 0 | **使用者決策**：未審核的卡要不要上網站？（現況：上，並標示待查證）駁回是否下架？誰可核准提交？ | 決策 | - |
| 1 | `build_site.py` 日期改從資料計算；測試的總數改由資料推導 | S | - |
| 2 | 把本次合成流程改成 CI 測試，防止斷鏈復發 | S–M | 1 |
| 3 | 修 `README.md:138` 連結與排程描述 | S | - |
| 4 | 待審項目保存可重用的內文，或重試時重抓，解決 `needs_context` 永久扣留 | M | 1 |
| 5 | 額度與佇列調整：失敗來源不佔滿額度；佇列改成不阻擋其他來源 | M | 4 |
| 6 | 提交入口：`issues` 事件加「核可」標籤，解析表單，驗證網址，產生 profile 提案。**要注意公開輸入不可自動進 `allowed_hosts`** | M | 0 |
| 7 | 單一來源管線：核可後只跑該來源，不等游標輪轉 | M | 1、6 |
| 8 | 資源列舉：分辨索引頁與公告，擴充連結關鍵字，追 `related_call`；索引頁不得成卡 | L | 7 |
| 9 | 跨文件彙整：公告、辦法併成同一方案，不各成一卡；資訊鏈輸出接進萃取 | L | 8 |
| 10 | 時間軌併入同一輪，提案一起產出；修正日期角色（學生／單位）與檢核漏報 | M | 7 |
| 11 | 自動開資料 PR：套用提案、跑檢查、開 PR（需寫入權限，應限定此 job） | M | 1、10 |
| 12 | 審核閘門接上網站與 RSS，依第 0 項的決定 | M | 0、11 |

順序理由：第 1、2 項最先做，因為不修的話，任何新來源都過不了 CI，後面的工作都無法驗證。第 8、9 項工程最大，也決定資料品質。

## 未涵蓋

- **真實網站：** 假頁結構乾淨，真實表現只會更差，比例未確認。
- **PDF 與附件路徑：** 這次只測 HTML。
- **模型模式：** `extract`、`audit`、`both` 未跑，排程也固定 off。
- **GitHub 端：** Actions 權限與快取行為只讀設定和紀錄，沒有實際觸發；網站畫面只查建置產物的內容，沒有開瀏覽器。
- **190 筆手寫資料：** 依指示未重查。
- **`feat/reextract-hand-authored` 分支：** 依指示未動；它若改了相關程式，本報告不反映。
- **本報告未經第二位代理複驗。** 請以腳本重跑為準。

## 修復進度

| 順序 | 工作 | 狀態 | PR |
|---|---|---|---|
| 1 | 建置日期與測試總數改由資料決定 | 已合併 | [#87](https://github.com/matt-ye/opengsa/pull/87) |
| 2 | 合成流程改成 CI 測試，尚未打通的環節標成已知斷點 | 已合併 | [#89](https://github.com/matt-ye/opengsa/pull/89) |
| 6 | 提交入口：owner 加標籤後驗證網址 | 已合併 | [#90](https://github.com/matt-ye/opengsa/pull/90) |
| 7 | 單一來源管線：核可後只跑該來源並產生提案 | 已合併 | [#91](https://github.com/matt-ye/opengsa/pull/91) |
| 8 | 資源列舉：入口頁往下找公告與附件，索引頁不成卡 | 已合併 | [#92](https://github.com/matt-ye/opengsa/pull/92) |
| 新增 | 新卡取代同網址、同方案的手寫卡；認不出是同方案就交給人判斷 | 已合併 | [#93](https://github.com/matt-ye/opengsa/pull/93) |
| 9 | 公告和它連到的辦法、附件歸成同一方案，欄位不拼接 | 已合併 | [#94](https://github.com/matt-ye/opengsa/pull/94) |
| 新增 | 手寫卡整批送進流程：實跑 183 個來源，3 張可取代，結果見 [hand-replacement-run-2026-11-07.md](hand-replacement-run-2026-11-07.md) | 已合併 | [#95](https://github.com/matt-ye/opengsa/pull/95) |
| 新增 | 撤下來源讀不到的 126 張手寫卡 | 已合併 | [#96](https://github.com/matt-ye/opengsa/pull/96) |
| 3 | README 與文件的排程描述改成實際行為；拿掉「覆蓋率 100%」 | 已合併 | [#97](https://github.com/matt-ye/opengsa/pull/97) |
| 4 | 待審卡片帶上來源脈絡與檢查結果 | 已合併 | [#98](https://github.com/matt-ye/opengsa/pull/98) |
| 5 | 每輪請求上限暫調 50、停掉讀不到的來源、失敗退避 | 已合併 | [#99](https://github.com/matt-ye/opengsa/pull/99) |
| 10 | 時間紀錄與卡片同一輪產生，沒抽到的欄位明列 | 已合併 | [#100](https://github.com/matt-ye/opengsa/pull/100) |
| 11 | 提案自動變成資料 PR，檢查在推之前跑完 | 已合併 | [#102](https://github.com/matt-ye/opengsa/pull/102) |
| 12 | 駁回的卡下架並記下問題來源 | 已合併 | [#103](https://github.com/matt-ye/opengsa/pull/103) |
| 新增 | 擴大檢索台灣來源，抽查後修通用萃取（金額、學制、國籍、分類、標題），清單見 [research-sources-2026-11-07.json](research-sources-2026-11-07.json) | 已合併 | [#104](https://github.com/matt-ye/opengsa/pull/104)、[#105](https://github.com/matt-ye/opengsa/pull/105) |
