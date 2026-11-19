# GitHub Pages 公開網站

2026-11-07使用者核可：公開網址改為 https://opengsa.mattye.dev/ （GitHub Pages自訂網域，經Cloudflare代理；.dev瀏覽器強制HTTPS，DNS only在憑證發出前會中斷，2026-11-07實測約一小時），舊 github.io 網址由GitHub轉址；加入Cloudflare Web Analytics並整合至mattye.dev後台；維持noindex。取代下方2026-10-29「不修改DNS」之限制，該段保留為當時紀錄。

網站建置讀 `scripts/build_site.py` 的 `load_full_library` 聚合的各 bundle，卡片數量以 README 的資料規模區塊（`scripts/readme_counts.py` 依資料產生）為準，不在這裡寫死。卡片是自動整理的來源摘要，不標成人工核准。未知與 Issue 回報規則見 [RADAR-VIEW.md](RADAR-VIEW.md)。

2026-10-29使用者核可：PR #1合併規劃與原型，PR #2上架公開預覽供分享回饋。目的網址為 https://matt-ye.github.io/opengsa/ ，不修改個人首頁或DNS。正式服務及資料覆核門檻仍依[目前計畫](TODO.md)。

## 發布內容

由`scripts/build_site.py`重用離線匯出器，只產生：

- `index.html`：內嵌程式與資料快照，標示合成示範及待覆核草稿；`<main>`尾端另有純HTML方案索引，不執行JS也讀得到每一筆方案。
- `p/<方案代號>/index.html`：每個方案一頁，附官方來源；代號用`opportunity_id`（不含來源版本雜湊，來源改版網址不變），同代號重複時加首個來源id區分。
- `sitemap.xml`、`robots.txt`：sitemap列首頁與全部方案頁；robots.txt只補`Sitemap:`，線上實際內容由Cloudflare代管規則合併產生。
- `feed.xml`、`feed-deadlines.xml`：全庫最新動態與截止倒數兩個 RSS（`scripts/build_feed.py`）。
- `assets/opengsa-social-preview.jpg`：已核可的專案縮圖，供Open Graph分享使用。
- `.nojekyll`：靜態成品標記。

**首頁效能（2026-11-19）**：首頁一次載入全部方案（2026-11 約 240 張卡），為了不卡頓：
- **只畫看得到的**：只畫目前選的檢視（甘特或卡片）；第二、三頁切過去時才畫，日期表展開時才畫（`prototype.js` 的 `detailStale`、`planStale`、`tableStale`）。
- **分批顯示**：卡片清單與第三頁的方案卡一次畫 50 張，按「顯示更多」再畫下一批。
- **搜尋框延遲 200 毫秒**：停止輸入後才重畫。
- **不內嵌每欄出處**：`build_site.py` 拿掉內嵌資料的 `field_evidence`（首頁程式不讀它，約 500 KB）；方案頁 `p/` 照常列出官方來源。

同一台桌機實測，開頁時的 DOM 元素從 31,830 降到 5,674，載入完成從約 2.1 秒降到約 0.7 秒。卡片數再大幅增加時，先看甘特圖的列數（目前仍一次畫全部）。

不發布repo目錄、私人資產、PDF、測試樣本或本機工具。輸出目錄若非空會停止，避免把前次留下的其他檔案一起發布；重建請選新的空目錄或先確認舊成品後清理。

```powershell
python -m pip install -r requirements-dev.txt
python scripts/check_data.py
python scripts/check_provenance.py
python scripts/scan_sources.py --check-config
python -m unittest discover -s tests -v
node --test tests/prototype.test.cjs
python scripts/build_site.py dist/site
python -m http.server 8771 --bind 127.0.0.1 --directory dist/site
```

瀏覽 http://127.0.0.1:8771/ 。Python 3.10以上、Node內建test runner；CI固定Python 3.13／Node 24。建置與測試依requirements-dev.txt安裝；網站無新增框架或外部字型。

## 工作流程

`.github/workflows/pages.yml`在PR中只執行資料檢查、全部Python測試、Node測試及建置；來源掃描測試全用合成離線資料，不部署PR或取用部署權限。推送main或在main手動執行時，檢查通過才上傳`dist/site`並由另一個job部署。

部署job採GitHub Pages官方OIDC流程，只取得`pages:write`與`id-token:write`；不需新增私人API key或PAT。Action固定完整commit SHA，checkout不留存憑證，部署使用github-pages環境並避免同時發布。

首次將repo的Pages來源設為GitHub Actions。官方依據：[自訂Pages工作流程](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。這是網站建置及發布流程；pages.yml沒有schedule，不抓取獎學金來源。來源巡檢由獨立的 [scan-sources.yml](SCANNER.md) 負責：週一到週六排程，週一那輪開每週的資料 PR，排程不呼叫模型；另提供受成本限制的手動模型／provider audit。`model-catalog.yml` 每週日更新模型型號清單。不建立D1或送出訂閱通知。

## 分享與回饋

頁首與頁尾連到GitHub公開Issue回饋表，需GitHub帳號；沒有匿名回饋資料庫。提供操作、版面、公開來源更正與功能建議分類，提醒勿提交個資、私人申訴或未遮蔽附件。平台不自動建立Issue，也不代學生送申請。

分享縮圖使用專案圖，不用個人照片。2026-11-18使用者核可正式上線：拿掉「預覽」字樣，首頁與全部方案頁開放索引；未經來源查證的方案也上架，但頁面要標示並附官方來源。Cloudflare對`Google-Extended`的封鎖維持不動（屬mattye.dev整個zone）。

個人條件、勾選、待辦與會議輸入只留本次瀏覽記憶體，重整後重設。Cloudflare Web Analytics僅統計瀏覽量（`spa:false`，每次載入一筆）：不使用Cookie或localStorage，送出位置已移除查詢參數；2026-11-07攔截實測，網址中的搜尋、學位與已選項目皆未出現在送出內容。Google Analytics（`G-GEFSZXE0RE`，資源「個人網站流量」下的串流「OpenGSA」）會使用Cookie辨識回訪瀏覽器，統計瀏覽量與外連點擊；2026-11-07攔截實測：載入時的第一筆page_view一律帶原始網址（含搜尋條件），`page_location`、`send_page_view:false`與關閉加強型評估都擋不住，只有串流的「遮蓋資料」有效。因此串流必須維持：遮蓋網址查詢參數開啟，鍵為`q, cat, deg, id, mode, picks, tab, view, compare`（值變成`(redacted)`，鍵名仍會送出）；加強型評估關閉。程式另把其餘事件的網址與外連`link_url`去掉查詢參數。新增網址參數時要先到GA4後台加鍵，`tests/test_build_site.py`會擋下遺漏。

2026-11-18使用者核可GA4事件（`docs/design/prototype.js`的`track()`）：`select_content`（開啟方案詳情）、`official_source_click`（點官方來源）、`rss_subscribe`（開啟或複製RSS）、`share`（複製分享連結，不送連結本身）、`pick_add`／`pick_remove`（加入或移出我的清單）、`tutorial_begin`／`tutorial_complete`（導覽）、`filter_apply`（只送篩選鍵名，不送選了什麼）、`tab_view`（點頁籤）。參數只能是網站自己的固定值：方案代號、類別、feed種類、頁籤名、導覽名、篩選鍵名；`tests/test_build_site.py`會擋下未核可的事件名與帶輸入值的呼叫。網站目前沒有匯出功能，所以沒有`export`事件。Key events：`official_source_click`、`rss_subscribe`。GitHub Pages託管與Cloudflare仍可能保留連線紀錄，頁尾連結雙方隱私聲明。

## 驗收與回復

- 檢查及建置成功，部署顯示成功後，實際網址須回應200並能操作四分頁、篩選、甘特圖及研討會試算。
- 分享圖片可讀，回饋表及原始碼連結正確；手機不產生整頁橫向溢出。
- 不能把來源草稿、事件基準估算或合成示範呈現成已核定資料。
- 發布失敗保留GitHub先前成功版本；回復可revert有問題的main commit，通過檢查後重新部署。停止公開則停用repo的Pages，不影響個人首頁。
- 本次發布不等於20筆正式資料、至少5筆全國方案及5筆仍受理機會的正式服務驗收。
