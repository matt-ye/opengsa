> 已封存（2026-11-10）：記錄 2026-11-05 當時的狀態，不代表現況。現行規則見 AGENTS.md，現行規劃見 docs/TODO.md。

# 臺大醫學院獎助來源遺漏盤查與補正報告 (Medical Scholarships Audit & Recovery)

**更新日期**：2026-11-05  
**作業目標**：依使用者指示盤查過去 PR 遺留之醫學院獎助來源，修復「臺大醫學院學生出國補助」與「臺大醫學院研究生優秀著作獎」於全庫候選清單中缺漏之問題，並建立獨立資料集與時程觀測政策。

---

## 一、 問題定位與歷史盤查

1. **臺大醫學院學生出國補助**：
   - **來源網址**：`https://www.mc.ntu.edu.tw/oia/Fpage.action?muid=1961&fid=1296`
   - **方案名稱**：國立臺灣大學醫學院醫學生出席國際會議及海外實習服務交換獎學金（臺大醫學院國際會議獎學金）
   - **遺漏原因**：早期版本於 `data/scan-sources.json` 中將該 URL 列入 `deferred_sources`（標記為「HTML僅導覽，正文需動態渲染」），且 `data/conference-programs.json`（ID: `ntu-med-oia`）與 `docs/CONFERENCE-SOURCES.md` 雖有獨立計算規則（會議前四週 28 天送達），但未及時於 PR #37 / #38 轉為結構化候選卡（candidate card）。
   - **時程特性**：`event_relative`（錨定活動 `conference_start`，學生於會前 28 日曆天送達醫學院國際事務中心）。

2. **臺大醫學院115學年度研究生優秀著作獎**：
   - **來源網址**：`https://rd.mc.ntu.edu.tw/bomrd/ntu2/news_txt.asp?pno=7296`
   - **方案名稱**：國立臺灣大學醫學院115學年度研究生優秀著作獎
   - **遺漏原因**：原先存在於 `data/pilot.json`（ID: `ntu-med-publication-115`），但歷史擴展階段伺服器回傳 HTTP 403 阻擋，導致未匯入 `data/candidates/source-review.json`。
   - **時程特性**：`fixed_window`（截止時間為 115/11/26 17:00 前向研發分處送件）。

---

## 二、 修復與資料架構補正

1. **來源設定與許可清單更新 ([`data/scan-sources.json`](../../data/scan-sources.json))**：
   - 將 `www.mc.ntu.edu.tw` 與 `rd.mc.ntu.edu.tw` 增補至 `allowed_hosts`。
   - 移除 `deferred_sources` 中的醫學院暫緩項，在 `sources` 增設 `ntu-med-oia` 與 `ntu-med-publication` 合規來源設定（`enabled: false`，維持排程關閉與 0 外部請求）。

2. **新增獨立候選清冊 ([`data/candidates/medical-scholarships.json`](../../data/candidates/medical-scholarships.json))**：
   - 遵循 `candidate.schema.json` 規格，建立：
     - `cand-ntu-med-oia-conference-40192a8b`
     - `cand-ntu-med-publication-115-7296a12b`
   - 保持獨立檔案避免改動 `source-review.json` 觸發 `source-chain-index.json` 之快照雜湊校驗。

3. **新增時程觀測紀錄 ([`data/medical-temporal-observations.json`](../../data/medical-temporal-observations.json))**：
   - 對齊 `time-policy-1` 規格：
     - `cand-ntu-med-oia-conference-40192a8b`: `submission_mode: event_relative`，無造假日期。
     - `cand-ntu-med-publication-115-7296a12b`: `submission_mode: deadline_only`，收錄官方截止日時戳。

4. **全庫整併與網站建置更新 ([`scripts/build_site.py`](../../scripts/build_site.py))**：
   - `load_full_library()` 聚合 5 大清冊，全庫正式升級為 **204 筆候選方案**。
   - 網站生成之 `index.html` 正式納入上述兩項醫學院獎助，第一頁「找獎助」搜尋「醫學院」、「出國」或「國際會議」均能精確檢索。

---

## 三、 測試與驗收結果

- `python scripts/check_data.py`：**PASS**（6 個候選清冊全部通過結構與範圍檢查）。
- `python scripts/scan_sources.py --check-config`：**PASS**（離線設定查核無誤）。
- `python scripts/audit_all_action_tracks.py`：**PASS 100%**（49 gov + 57 other + 98 enterprise = 204 方案）。
- `python -m unittest tests/test_build_site.py`：**PASS**（7 項網站發布邊界與 204 方案幾何投影測試）。
- `node --test tests/prototype.test.cjs`：**PASS**（54 項前端核心交互測試）。
- `python -m unittest discover -s tests -v`：**PASS**（275 項單元測試 100% 通過）。
