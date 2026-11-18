# OpenGSA 正式上線計畫：取消 noindex 與 GA4 事件

2026-11-18 規劃。本文件只是計畫，**沒有改任何網站設定**；每個階段都要使用者核可後另開 PR。
審核依據是 2026-11-18 的 main（`aab94f9`）建置產物與線上站，工具為 YAEO（`seo-aeo-audit` skill）。

延續 [docs/archive/TEMPORAL-UX-AND-DISCOVERY-ROADMAP.md](archive/TEMPORAL-UX-AND-DISCOVERY-ROADMAP.md) §10 的原則：先讓內容可讀、可引用，再開放索引。網址已改為 `https://opengsa.mattye.dev/`，該文件提到的 `/opengsa/` 子路徑不再適用。

## 1. 結論

- **可以分兩步上線。** 第一步只開放首頁索引，修掉 3 個 error 即可；第二步再產生每個方案的實體頁，那才是搜尋流量的主要來源。
- **最大的問題不在 noindex。** 205 筆方案全部只存在內嵌 JSON，由 JS 畫出來；HTML 正文裡一筆方案名稱都沒有。取消 noindex 後，搜尋引擎能收錄的只有首頁的介紹文字。
- **GA4 事件要沿用現有的隱私做法。** 不送任何使用者輸入或篩選值，送出前要用攔截請求驗證。

## 2. 審核結果

### 2.1 自動檢核

| 層級 | 代碼 | 級別 | 狀況 |
|---|---|---|---|
| L1 | `L1-NOINDEX` | info | `build_site.py` 輸出 `noindex, nofollow`，測試也釘住這行 |
| L2 | `L2-FAKE-HEADING` | error | 「我的專屬申請清單」用 `<p>`／`<div>` 當區塊標題 |
| L2 | `L2-HEADING-SKIP` | warn | h1 直接跳 h3（「我的選項」） |
| L2 | `L2-JSONLD-MISSING` | info（noindex 降級） | 沒有任何結構化資料；取消 noindex 後會升為 warn |
| L2 | `L2-BILINGUAL-CONCAT` | info | 3 組中英並存的元素對 |
| L2 | `L2-FEW-INTERNAL-LINKS` | info | 單頁站，只有 2 個內部連結，屬正常 |
| SITE | `SITE-SITEMAP-MISSING` | error | 沒有 sitemap |
| SITE | `SITE-ROBOTS-MISSING` | error | 建置產物沒有 robots.txt；線上的 robots.txt 是 Cloudflare 代管產生的 |
| SITE | `SITE-LLMSTXT-MISSING` | info | 不建議為此補做，見 §3.3 |

### 2.2 檢核器沒抓到、但最重要的一項

`seo-check.mjs` 沒有報 `L2-CLIENT-RENDERED`，因為首頁有約 1.2 萬字的介紹與介面文字。實際比對：

- 內嵌 JSON 有 205 筆方案（生活與學雜費 125、研究工具 22、博士研究 21、緊急救助 11、其他 26）。
- 剝掉 `<script>` 之後，HTML 正文裡出現的方案名稱：**0 筆**。

也就是說，取消 noindex 後搜尋結果只會有一個首頁，「OO 獎學金 申請」這類查詢找不到任何一筆方案。`?id=` 深連結的 canonical 都指回首頁，所以也不會被當成獨立頁面收錄。

### 2.3 線上連線檢核（`agent-check.mjs`）

| 代碼 | 級別 | 狀況 |
|---|---|---|
| `AGENT-SITEMAP-UNREACHABLE` | error | `/sitemap.xml`、`/sitemap-index.xml` 都是 404 |
| `AGENT-LLMSTXT-UNREACHABLE` | warn | `llms.txt` 404 |
| `AGENT-404-NO-POINTER` | info | 404 頁沒有回首頁的連結 |
| `AGENT-MD-NEGOTIATION` | info | 首頁約 95% 不是正文 |

404 狀態碼正確，robots.txt 可取得。

### 2.4 效能（PageSpeed Insights，2026-11-18）

| | 效能 | SEO | LCP | TBT |
|---|---|---|---|---|
| 手機 | 74 | 66 | 2.2s | **1.0s（差）** |
| 桌機 | 93 | 66 | 0.6s | 0.2s |

SEO 66 分主要是 noindex 造成的。首頁 HTML 未壓縮約 2.1 MB（gzip 約 284 KB），手機 TBT 偏高應與解析大份內嵌 JSON 有關，未逐項確認。沒有真實使用者資料（流量不足）。

### 2.5 robots.txt 現況

線上 robots.txt 由 Cloudflare 的代管設定產生，屬於 mattye.dev 整個 zone，不在這個 repo：

- 一般搜尋：允許（`Content-Signal: search=yes,ai-train=no`）。
- 訓練型爬蟲（GPTBot、ClaudeBot、CCBot 等）：封鎖。
- 檢索型（OAI-SearchBot、PerplexityBot、Claude-User）：沒有特別列出，依 `*` 規則允許。
- `Google-Extended`、`GoogleOther`、`Baiduspider`：封鎖。

`Google-Extended` 影響 Google 的 AI 功能能否使用網站內容，範圍隨 Google 政策調整過，要開放前需回查官方文件當日說明。改這項會同時影響 mattye.dev，見 D3。

## 3. 上線步驟

### 3.1 需要使用者決定

| # | 決定 | 建議 |
|---|---|---|
| D1 | 「正式上線」是否拿掉標題與頁首的「公開預覽」字樣 | 拿掉「預覽」，保留「非資格核定，請以官方公告為準」 |
| D2 | 第一步開放索引的範圍 | 只開首頁；方案頁等 §3.4 完成後再開 |
| D3 | Cloudflare 是否解除 `Google-Extended` 封鎖 | 先不動。這是 mattye.dev 整個 zone 的設定，影響個人網站，宜另案評估 |
| D4 | GA4 事件清單（§3.5）與 key events | 依表核可；這會擴大 AGENTS.md 先前核可的追蹤範圍 |
| D5 | 方案實體頁是否收錄「未經來源查證」的卡片 | 不收錄，只為已查證的方案產生實體頁 |

### 3.2 PR 1：開放首頁索引（D1、D2 核可後）

1. `build_site.py` 移除 `noindex, nofollow`；同步更新 `tests/test_build_site.py` 第 100 行的斷言，改為斷言沒有 noindex。
2. 產生 `sitemap.xml`（目前只有首頁）。`lastmod` 用內容實際異動日，不用掃描日。
3. 產生 `robots.txt` 並加上 `Sitemap:` 一行。⚠ Cloudflare 代管 robots 與原站檔案如何合併**未確認**，部署後要實際取回檢查。
4. 修 `L2-FAKE-HEADING` 與 `L2-HEADING-SKIP`：標籤改成 `<h2>`，class 不動。
5. 加 JSON-LD：`WebSite`、`WebPage`，`publisher` 用 Matt Ye（公開署名只用 Matt Ye，見 AGENTS.md）。只放頁面上看得到的內容。
6. 首頁 HTML 直接輸出一份方案索引：方案名稱、類別、官方來源連結，放在可收合的區塊，JS 載入後可沿用。這是讓搜尋引擎第一次讀到方案名稱的最低成本做法。
7. 404 頁加回首頁連結（info，順手做）。
8. 更新 DEPLOYMENT.md、DECISION-LOG.md 的 noindex 描述。

驗收：
- YAEO 的 error 歸零。
- 不執行 JS 的 HTML 裡看得到方案名稱。
- 線上 `/sitemap.xml` 回 200。
- 線上 robots.txt 有 `Sitemap:` 且仍允許一般搜尋。

### 3.3 不做的事

- **llms.txt**：Google 明言不使用，大型實測 97% 零抓取；唯一明顯的讀者是編碼代理，不是 OpenGSA 的使用者。
- **FAQPage**：FAQ rich result 已於 2026-05-07 停止顯示（見 archive 路線圖 §10.2）。
- **為了分數改設定**：例如補空的 `.well-known` 目錄。

### 3.4 PR 3（之後）：方案實體頁

這是搜尋流量的主要來源，也是 archive 路線圖的 S2。範圍較大，另行規劃：

- 依穩定方案 ID 產生 `/p/<id>/` 實體 HTML：唯一 title、description、canonical；正文先給精簡答案（是什麼、適用範圍、受理方式、最後核對時間、官方來源）。
- JSON-LD 只轉出可見且有證據的內容；實際金錢補助可評估 `MonetaryGrant`，申請期不標成 `Event`。
- 首頁 `?id=` 深連結改連到實體頁，sitemap 列出全部實體頁。
- 依 D5，未查證卡片不產生實體頁或標 noindex。
- GA4「遮蓋資料」清單要隨新網址參數一起更新（`tests/test_build_site.py` 會擋下遺漏）。

### 3.5 PR 2：GA4 事件（D4 核可後，可與 PR 1 並行）

現況：只有 `page_view` 與程式自送的外連 `click`。串流的「遮蓋資料」與「加強型評估關閉」維持不變，規則見 DEPLOYMENT.md。

| 事件 | 觸發時機 | 參數 | Key event |
|---|---|---|---|
| `select_content` | 開啟方案詳情 | `content_type=opportunity`、`item_id`（方案 ID）、`category` | |
| `official_source_click` | 點方案的官方來源連結 | `item_id`、`link_domain` | ✓ |
| `click`（既有） | 其他外連 | `link_url`（已去查詢參數）、`link_domain` | |
| `rss_subscribe` | 開啟或複製 RSS 網址 | `feed`（`all`／`deadlines`） | ✓ |
| `share` | 複製分享連結 | `method=copy_link` | |
| `export` | 匯出清單 | `format` | ✓ |
| `pick_add`／`pick_remove` | 加入或移出我的清單 | `item_id` | |
| `tutorial_begin`／`tutorial_complete` | 開始或完成導覽 | `tour` | |
| `filter_apply` | 套用篩選 | `filter_key`（只送 `cat`、`deg` 這類鍵名） | |
| `tab_view` | 切換頁籤 | `tab`（固定四個值之一） | |

隱私規則：

- **不送任何值來自使用者輸入的參數**：搜尋字串、篩選值、比較組合、分享連結本身都不送。頁尾承諾的是「不記錄你輸入的搜尋與篩選內容」。
- 方案 ID 與類別是網站自己的固定值，不是個人資料，可以送。
- `filter_apply` 只送鍵名；如果之後要看「哪個類別最常被篩」，需另行核可並更新頁尾文字。

GA4 後台：

- 要在報表裡看到 `item_id`、`feed`、`filter_key` 這些參數，要先建立自訂維度。
- 標記上表的 key events。

驗收：

- 本機與正式站都用帶測試值的網址操作每一個事件，攔截 `/g/collect`，確認沒有任何測試值。
- GA4 DebugView 或即時報表看得到事件。
- 事件名稱與參數加入 `tests/test_build_site.py` 的斷言。

### 3.6 上線後

1. Search Console：確認 `opengsa.mattye.dev` 已在某個 property 底下（mattye.dev 是網域資源還是網址前置字元資源，**未確認**），提交 sitemap，用網址檢查要求建立索引。
2. Bing Webmaster Tools：匯入或新增，ChatGPT 搜尋大量依賴 Bing 索引。
3. 重跑 YAEO 三支腳本與 PSI，結果附在 PR。
4. 觀察 2～4 週再判斷成效。收錄與排名有延遲，AI 引用的單次量測雜訊很大，不要用一兩天的數字下結論。

## 4. 建議順序

1. 使用者決定 D1～D5。
2. PR 1（開放首頁索引）與 PR 2（GA4 事件）並行。兩者都改 `build_site.py` 的 head 區段，後合併的要先同步 main。
3. 合併、部署、上線後檢查。
4. 規劃 PR 3（方案實體頁）。

## 5. 未確認事項

- Cloudflare 代管 robots.txt 與原站 robots.txt 的合併行為。
- mattye.dev 在 Search Console 的資源類型，是否已涵蓋子網域。
- 手機 TBT 1.0s 的確切來源。
- `Google-Extended` 目前的實際作用範圍（需回查官方文件）。
