# OpenGSA 相似專案研究：Open States、changedetection.io、CourtListener 與近似專案

查核日期：2026-11-08。方法：以 GitHub API 與網頁實際讀取各 repo 的 README、原始碼目錄與檔案內容。凡文件或程式碼沒寫的，一律標「未確認」。星數與授權為查核當日讀到的值。

## 一、結論摘要

1. 三個原列參照專案都真實存在且仍在維護，但性質不同。Open States 與 CourtListener 是「為每個資料來源寫一支專屬爬蟲」的模式，changedetection.io 是「監看任意網址、偵測內容改變」的通用工具。三者都不是獎助學金專案，OpenGSA 只能借做法，不能直接套用。
2. 搜尋結果中沒有找到成熟的開源獎助學金彙整專案。GitHub 上找到的獎學金爬蟲或彙整 repo 多半是 0 到 1 顆星的個人作品、多數沒有授權，不列入參照。這是「找不到」，不是湊數。
3. 比較貼近的是公部門資訊爬取社群（City Scrapers）與補助資料標準（CommonGrants、360Giving），它們分別對應 OpenGSA 的「排程與健康狀態」「資料模型與欄位」。
4. 最值得借的四件事：抓取層先以內容雜湊判斷「沒變就跳過」；爬蟲對意外輸入採「刻意脆弱」、寧可失敗不寫入壞資料；每筆輸出強制帶來源網址並以 JSON Schema 檢查；PDF 先抽文字、抽不到才走 OCR。
5. 不該學的：偽裝瀏覽器或輪換 User-Agent、用 VPN 繞過封鎖、引入整套資料庫與 Web 服務、不同來源各寫一支客製爬蟲的規模化假設。

## 二、原列三個參照專案

### 2.1 Open States（openstates-scrapers）

基本資料：repo 為 https://github.com/openstates/openstates-scrapers ，授權 GPL-3.0，最後推送 2026-11-05，923 顆星。依賴的核心函式庫 openstates-core（https://github.com/openstates/openstates-core ）授權 MIT，最後推送 2026-10-30。文件在 https://github.com/openstates/documentation （CC-BY-4.0，最後推送 2026-04-02）。

用途：抓美國各州議會的法案、投票、議員、委員會與會議資料。

| 面向 | 已查證內容 | 來源 |
|---|---|---|
| 來源管理與提交 | 每州一個 Python 模組，內有 `__init__.py`（含 `legislative_sessions` 屆期清單）與 `bills.py`、`events.py` 等。`jurisdiction_configs.json` 逐州列出要跑的 people 爬蟲。來源由貢獻者寫程式碼加入，沒有「使用者提交網址」的機制。 | https://github.com/openstates/openstates-scrapers/blob/main/jurisdiction_configs.json ；https://github.com/openstates/openstates-scrapers/tree/main/scrapers/wa |
| 抓取排程與額度 | `scripts/instrumented_scout.py` 逐州跑 spatula 的 `scout`，由 `.github/workflows/scrape.yml` 每日 10:00 UTC 觸發，結果 commit 到另一個 repo `openstates/scraper-artifacts`。底層請求設定在 openstates-core 的 `settings.py`：預設每分鐘 60 次請求、逾時 60 秒、重試 3 次、重試間隔 10 秒。文件列出 `--rpm`、`--timeout`、`--retries`、`--retry_wait`、`--fastmode`（用快取並關閉節流）。 | https://github.com/openstates/openstates-scrapers/blob/main/.github/workflows/scrape.yml ；https://github.com/openstates/openstates-core/blob/main/openstates/settings.py ；https://github.com/openstates/documentation/blob/main/docs/contributing/scrapers.md |
| 失效與異動偵測 | 沒有網址存活檢查機制的文件。處理方式是「爬蟲每天跑，網站改版就讓爬蟲報錯」。openstates-core 的 `Scraper` 有可選的 `http_resilience_mode`：連續失敗 3 次後暫停 120 秒再繼續（預設關閉）。匯入階段會回報 insert / update / noop 的筆數，可用來看有無實際變動。 | https://github.com/openstates/openstates-core/blob/main/openstates/scrape/base.py ；https://github.com/openstates/openstates-core/blob/main/openstates/importers/base.py |
| PDF 與附件 | 法案本文抽取由獨立步驟處理：文件說明另有 text-extraction 流程，取樣原始 PDF 後抽文字，並以輸出位元組數作為第一道檢查，再人工對照原檔。該 repo（openstates/text-extraction）本次以 API 查詢回 404，因此其目前狀態與授權「未確認」。爬蟲層只記錄文件連結與 `media_type`（`scrapers/utils/media.py` 只依網址副檔名猜測 MIME，不下載）。核心函式庫有 `file_archiving_enabled` 旗標，實際行為「未確認」。 | https://github.com/openstates/documentation/blob/main/docs/contributing/text-extraction.md ；https://github.com/openstates/openstates-scrapers/blob/main/scrapers/utils/media.py |
| 萃取與結構化 | 爬蟲輸出 Bill、VoteEvent 等物件，寫成每物件一個 JSON 檔，並以 jsonschema（Draft3Validator）驗證。schema 規定 `sources` 至少一筆且每筆是 URI。 | https://github.com/openstates/openstates-core/blob/main/openstates/scrape/schemas/common.py ；https://github.com/openstates/openstates-core/blob/main/openstates/scrape/base.py |
| 審核與資料品質 | 官方文件明確寫出「刻意脆弱的爬蟲」原則：遇到未預期輸入就丟例外，因為壞資料進資料庫後難以偵測與清除，爬蟲中斷則可立即告警。文件也說不鼓勵用快照 HTML 寫單元測試，品質靠「輸出 schema 驗證 + 每晚實跑 + 共用工具函式測試」。人工審核資料的流程「未確認」。 | https://github.com/openstates/documentation/blob/main/docs/contributing/testing-scrapers.md |
| 資料儲存與狀態追蹤 | 抓取輸出為 JSON 檔，另以匯入器載入 Postgres。匯入器以內容雜湊去除完全相同的重複物件。spatula 的輸出放在日期與編號資料夾下，便於比較不同次執行。 | https://github.com/openstates/documentation/blob/main/docs/contributing/scrapers.md ；https://github.com/openstates/openstates-core/blob/main/openstates/importers/base.py |

相關套件：spatula（https://github.com/jamesturk/spatula ，MIT，官方 repo 已搬到 Codeberg，GitHub 為鏡像，最後推送 2025-11-22），內建 CSV、JSON、XML、PDF、Excel 的頁面處理器。scrapelib（https://github.com/jamesturk/scrapelib ，BSD-2-Clause，最後推送 2026-11-03），提供可設定的節流、重試與簡單快取。

對 OpenGSA 的重點：它的資料量與團隊規模遠大於 OpenGSA，可借的是原則（失敗優先於髒資料、sources 必填、輸出 schema 驗證），不是架構。

### 2.2 changedetection.io

基本資料：https://github.com/dgtlmoon/changedetection.io ，授權 Apache-2.0，最後推送 2026-11-06，35,615 顆星。有付費託管版本，開源版與託管版功能相同。

用途：監看任意網頁、JSON API 或 PDF 的內容變化並通知。README 的使用情境清單含「政府部門更新」「PDF 文字變更」。

| 面向 | 已查證內容 | 來源 |
|---|---|---|
| 來源管理與提交 | 以「watch」為單位，每個網址一筆，可加標籤，透過網頁介面或 REST API（`docs/api-spec.yaml`）新增。是使用者自助提交，沒有審核關卡。 | https://github.com/dgtlmoon/changedetection.io/blob/master/README.md ；https://github.com/dgtlmoon/changedetection.io/blob/master/docs/api-spec.yaml |
| 抓取排程與額度 | 每個 watch 有 `time_between_check`，可沿用全域設定或個別覆寫；README 說明可依時區、星期與時段限定檢查時間。工作以優先權佇列加非同步 worker 處理，同一 watch 已在處理中則延後重排（`worker.py`）。每個 watch 可設不同代理。「每網域最短間隔」與「遵守 robots.txt」在我檢視的 `worker.py`、`content_fetchers/requests.py`、`flask_app.py` 中搜尋不到，標「未確認」（未逐檔讀完全部程式碼）。 | https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/model/Watch.py ；https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/worker.py |
| 失效與異動偵測 | 先算原始內容的 MD5 校驗碼，若與上次相同、watch 設定沒被編輯、且過濾設定雜湊也沒變，就丟出 `checksumFromPreviousCheckWasTheSame` 跳過後續處理。抓取錯誤寫入 `last_error`；若 CSS/XPath 過濾器找不到目標，會累計 `consecutive_filter_failures`，達設定門檻才通知。回應是 HTML 但抽不出文字時另有專屬錯誤訊息。 | https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/processors/text_json_diff/processor.py ；https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/worker.py |
| PDF 與附件 | PDF 用外部工具 `pdftohtml`（可用環境變數 `PDF_TO_HTML_TOOL` 更換）轉成 HTML 再比對，並把整份文件的 MD5 校驗碼附在內容裡；若抓取器只拿到瀏覽器的 PDF 檢視頁而非原檔，會明確報錯並建議改用基本 HTTP 抓取器。 | 同上 processor.py（`preprocess_pdf`、`PDFNotAvailableFromFetcher`） |
| 萃取與結構化 | 提供 CSS、XPath、JSONPath、jq、正規表示式的過濾、忽略與擷取。另有選用的 LLM 功能（`changedetectionio/llm/`）：以自然語言規則判斷「這次差異是否重要」，並產生變更摘要；可接 OpenAI、Gemini、Anthropic、Ollama 等。README 稱成本為「每次檢查不到一分錢」，這是官方宣稱，未獨立驗證。 | https://github.com/dgtlmoon/changedetection.io/blob/master/README.md |
| 審核與資料品質 | 沒有人工審核閘門；品質機制是條件式觸發（價格高低、關鍵字出現與否）與 LLM 規則。 | 同上 README |
| 資料儲存與狀態追蹤 | 每個 watch 一個資料夾與 `watch.json`，以原子寫入（寫暫存檔再改名，可選 fsync）儲存；快照歷史有 `history.txt` 索引，超過 20KB 的快照以 brotli 壓縮（門檻可由環境變數調整）。 | https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/store/file_saving_datastore.py ；https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/model/Watch.py |

對 OpenGSA 的重點：它回答的是「頁面變了沒」，不回答「變了的內容是不是獎學金資訊」，也沒有證據鏈或審核閘門。它的校驗碼跳過與連續失敗門檻最值得借。整套服務（Flask、佇列、Playwright）對只有靜態網站加 GitHub Actions 的 OpenGSA 太重。

### 2.3 CourtListener（含 Juriscraper、Doctor）

基本資料：https://github.com/freelawproject/courtlistener ，由 Free Law Project 維護，最後推送 2026-11-07，1,062 顆星。授權：GitHub API 回 NOASSERTION，但 README 與 `LICENSE.txt` 標頭寫明 Affero GPL（AGPL）；以 README 為準。爬蟲函式庫 Juriscraper（https://github.com/freelawproject/juriscraper ）授權 BSD-2-Clause，最後推送 2026-11-06。文件轉文字微服務 Doctor（https://github.com/freelawproject/doctor ）授權 BSD-2-Clause，最後推送 2026-11-06。

用途：蒐集美國法院判決書、口頭辯論與 PACER 資料並提供檢索。

| 面向 | 已查證內容 | 來源 |
|---|---|---|
| 來源管理與提交 | 每個法院一支 Juriscraper 爬蟲，需在 `__init__.py` 註冊。貢獻流程要求先聯絡維護者認領、避免重工，並附 `tests/examples` 的範例檔與產生的 `.compare.json`。維基有法院網站清單。 | https://github.com/freelawproject/juriscraper/blob/main/CONTRIBUTING.md |
| 抓取排程與額度 | `cl_scrape_opinions` 有 `--rate` 參數，預設 30，意為「走完所有要求的法院需要幾分鐘」，也就是把請求攤平到時間軸上。Juriscraper 預設 User-Agent 為 `Juriscraper`，另有一個模仿瀏覽器的 `chrome_user_agent` 選項供檢查瀏覽器標頭的網站使用。 | https://github.com/freelawproject/courtlistener/blob/main/cl/scrapers/management/commands/cl_scrape_opinions.py ；https://github.com/freelawproject/juriscraper/blob/main/juriscraper/AbstractSite.py |
| 失效與異動偵測 | 兩層去重。第一層是「站台雜湊」：Juriscraper 產生頁面雜湊，`DupChecker` 與資料庫 `UrlHash` 表比對，沒變就整個中止本次爬取（全量爬取時忽略）。第二層是「內容雜湊」：下載後算 SHA-1，並可退而用 download_url 比對；連續遇到重複達門檻（預設 5）就停止。遇到壞內容或無效文件時不更新站台雜湊，確保下次重試。 | https://github.com/freelawproject/courtlistener/blob/main/cl/scrapers/DupChecker.py ；cl_scrape_opinions.py（同上） |
| PDF 與附件 | 先不用 OCR 抽文字，若抽不到內容且判斷需要 OCR，才呼叫 Doctor 的 OCR 服務，並在紀錄上標 `extracted_by_ocr`。程式註解說明原因：對大型文件全程 OCR 太昂貴。Doctor 底層使用 pdftotext、tesseract、ghostscript。 | https://github.com/freelawproject/courtlistener/blob/main/cl/scrapers/tasks.py ；https://github.com/freelawproject/doctor |
| 萃取與結構化 | 爬蟲各自解析欄位，基底類別統一輸出平行陣列（案名、日期、下載網址等）。 | https://github.com/freelawproject/juriscraper/blob/main/juriscraper/AbstractSite.py |
| 審核與資料品質 | 基底類別 `_check_sanity` 檢查：各欄位長度一致、必要欄位有值、日期是日期物件且不是 22 世紀、案名不是空白，違反則丟 `InsanityException`；無結果只發警告。測試用範例檔加預期輸出（`.compare.json`）比對。人工審核流程「未確認」。 | juriscraper AbstractSite.py ；CONTRIBUTING.md |
| 資料儲存與狀態追蹤 | Django + PostgreSQL，另有 Elasticsearch 與 Celery。有 `refresh_scrapers_status_view` 指令更新物化視圖 `scrapers_mv_latest_opinion`，用來查各爬蟲最近一筆資料（用途依指令說明文字推得，管理介面細節未確認）。另有 back-scrape 指令回補歷史。 | https://github.com/freelawproject/courtlistener/tree/main/cl/scrapers/management/commands |

注意：`cl/lib/ratelimiter.py` 是限制對外 API 使用者的速率，不是限制爬取速率，不可混為一談。

對 OpenGSA 的重點：兩層雜湊與「失敗時不更新雜湊」這個細節，完全貼合「入口頁沒細節、要往下一層找 PDF」的流程；OCR 分級也可直接借概念。但整個系統（Django、ES、Celery、AGPL）不適合搬。

## 三、更接近的專案

### 3.1 City Scrapers（City Bureau）

- 主 repo：https://github.com/City-Bureau/city-scrapers ，授權 MIT，最後推送 2026-11-05。核心套件 https://github.com/City-Bureau/city-scrapers-core ，MIT，最後推送 2026-10-28。範本 https://github.com/City-Bureau/city-scrapers-template ，MIT，最後推送 2026-08-26。
- 用途：以社群志工協作的方式，每日爬芝加哥公部門的公開會議資訊，輸出 JSON，並提供範本讓其他地區自建。這是「公部門資訊爬取社群」的典型範例。
- 已查證做法：
  - 抓取層設定 `ROBOTSTXT_OBEY = True`、停用 cookie、開啟 AutoThrottle（起始延遲、最大延遲、目標並行數由環境變數控制，Cron 工作流程設為 1.5 秒、30 秒、3.0）；User-Agent 寫明專案名稱與聯絡網址。來源：`city_scrapers/settings/base.py`、`.github/workflows/cron.yml`。
  - 排程跑在 GitHub Actions：`cron.yml` 每日 08:12 UTC，另有每日 07:12 UTC 的 `archive.yml`，以 Wayback 中介層把每筆項目的來源頁與最多 3 個附件連結送去網路存檔。
  - 每筆輸出（`Meeting` 項目）有 `source` 與 `links` 欄位；`ValidationPipeline` 以 jsonschema 檢查並在結束時產生驗證報告。來源：city-scrapers-core 的 `items.py`、`pipelines/validation.py`。
  - `DiffPipeline` 載入上次結果，本次沒再出現的項目標記為取消，而非直接刪除。來源：`pipelines/diff.py`。
  - 健康狀態：`StatusExtension` 對每支爬蟲產生狀態徽章，抓到 0 筆即標為 failing。來源：`extensions/status.py`。
  - 新增爬蟲走 PR；`parse-spiders.yml` 在 PR 檢查爬蟲檔，成功後 `sync-airtable.yml` 把爬蟲清單同步到 Airtable 的待辦表（用途依檔名與參數推得，Airtable 表結構未確認）。
- 注意：Cron 工作流程內建 OpenVPN 連線以變更出口 IP，這是不該學的部分，見第五節。

### 3.2 Simpler.Grants.gov 與 CommonGrants（美國 HHS）

- Simpler.Grants.gov：https://github.com/HHS/simpler-grants-gov ，美國政府作品，LICENSE.md 載明於美國屬公共領域並以 CC0 1.0 全球放棄權利，最後推送 2026-11-07，212 顆星。它是 Grants.gov 的現代化重做，不做網頁爬取，而是每小時從既有 Grants.gov 資料庫以 ELT 抽取、載入暫存表、標記刪除、逐表轉換（`documentation/api/legacy-transforms.md`）。狀態、類別等欄位以查表常數定義（`documentation/api/lookup-values.md`）。
- CommonGrants：https://github.com/HHS/simpler-grants-protocol ，GitHub 標 NOASSERTION，LICENSE.md 與上者相同載明公共領域與 CC0，最後推送 2026-11-06。這是補助資料交換標準，`OpportunityBase` 模型含：狀態（forecasted、open、closed、custom）、說明、資金、資助者、關鍵日期（postDate、closeDate、otherDates）、可接受申請者類型、`source`（網址）、`customFields`。來源：`lib/core/lib/core/models/opportunity/base.tsp`、`status.tsp`、`timeline.tsp`。
- 與 OpenGSA 的關係：沒有解決「怎麼抓」，但提供「補助資訊卡該有哪些欄位、日期如何建模、狀態如何列舉」的現成設計，且有 `source` 與 `customFields` 擴充點。

### 3.3 360Giving Data Standard（英國）

- https://github.com/ThreeSixtyGiving/standard ，最後推送 2026-11-05。文件授權為 CC BY 4.0（LICENSE.md）；程式碼授權與 GitHub 判定皆為 NOASSERTION，「未確認」。
- 權威來源是 JSON Schema（`schema/360-giving-schema.json`），另有 codelists 資料夾。這是英國資助方公開補助資料的標準，偏向「已核准的補助紀錄（誰給誰多少錢）」，不是「徵件公告」，與 OpenGSA 的卡片只有部分重疊。價值在於示範「以 JSON Schema 加 codelist 管理詞彙」。

### 3.4 civic-scraper（Big Local News），僅作反例記錄

- https://github.com/biglocalnews/civic-scraper ，Apache-2.0（LICENSE 檔頭），最後推送 2026-09-11，但 README 明言「不再公開維護」，保留作為爬蟲框架的參考。不建議採用，只供閱讀其下載附件與中繼資料的設計。

### 3.5 找不到的部分

- 獎學金或補助的開源彙整專案：以 GitHub 關鍵字（scholarship aggregator、scholarship scraper、funding opportunities scraper 等）與一次網路搜尋查過，只找到 0 到 1 顆星的個人專案（例如 beepboopshru/scholarship-scraper、shahbazehmad/scholarship-hub），多半無授權或剛建立，未讀其內容，不列為參照。也沒找到台灣獎助學金相關開源專案。這不代表不存在，只代表本次查不到。
- 其他國家的政府補助資料標準，僅找到上述 CommonGrants 與 360Giving，未再擴大。

## 四、OpenGSA 可借用的具體做法

下表的「步驟」對應 OpenGSA 流程：使用者提交來源、審核、新來源輸入、資訊鏈探索、資源列舉、抓取本文、整理待粹資訊、萃取、資訊彙整、審核、上架。

| # | 做法 | 對應步驟 | 來自 | 檔案或文件頁 | 適用限制 |
|---|---|---|---|---|---|
| 1 | 抓取前先比對內容雜湊，沒變就跳過下游處理；雜湊同時納入「抽取設定」，設定改了就強制重跑。 | 抓取本文、整理待粹資訊 | changedetection.io | `changedetectionio/processors/text_json_diff/processor.py`（原始內容 MD5 與過濾設定雜湊的跳過條件） | 只能判斷「頁面字節變了」，網頁含日期、廣告、計數器時會誤報，需先去除雜訊再算雜湊。 |
| 2 | 兩層去重：入口頁（站台）雜湊 + 每個附件內容雜湊；遇到壞內容時不更新雜湊，下一輪自動重試。 | 資訊鏈探索、資源列舉、抓取本文 | CourtListener | `cl/scrapers/DupChecker.py`；`cl_scrape_opinions.py`（`update_site_hash` 的處理） | OpenGSA 若用 JSON 存雜湊，需自行處理併發寫入；入口頁常動態更新，會降低節省比例。 |
| 3 | 「連續遇到 N 筆已知重複就停止列舉」作為每輪請求上限之外的自然停損。 | 資源列舉 | CourtListener | `DupChecker.py`（`dup_threshold` 預設 5） | 只適用依時間倒序的清單頁；清單若非依時間排序，會提早停止而漏抓。 |
| 4 | 把請求攤平到時間軸，而不是一次爆衝：以「完成全部來源需要幾分鐘」來設定節奏。 | 抓取排程與額度（資源列舉、抓取本文） | CourtListener | `cl_scrape_opinions.py` 的 `--rate` 參數 | GitHub Actions 單次有時間上限，且每輪請求數要自行設硬上限；本專案原本的同網域間隔仍須保留。 |
| 5 | 遵守 robots.txt、關閉 cookie、AutoThrottle，並在 User-Agent 寫明專案名稱與聯絡網址。 | 抓取排程與額度 | City Scrapers | `city_scrapers/settings/base.py` | AutoThrottle 是 Scrapy 功能，若 OpenGSA 不用 Scrapy，需自行實作等效邏輯（延遲依回應時間調整）。 |
| 6 | 連續失敗門檻與暫停：連續 3 次失敗暫停一段時間，或過濾目標連續找不到達門檻才通知，避免單次抖動就告警。 | 失效偵測、來源健康度 | Open States、changedetection.io | `openstates-core/openstates/scrape/base.py`（`_max_consecutive_failures`）；`changedetectionio/worker.py`（`consecutive_filter_failures`） | 門檻值是各專案自訂，需用 OpenGSA 實測資料決定，不可直接沿用數字。 |
| 7 | 「刻意脆弱」：抽取遇到未預期的值（新的身分別、無法解析的日期）就中止並標示來源待人工處理，不要用預設值硬塞。 | 萃取、資訊彙整 | Open States | `docs/contributing/testing-scrapers.md`（Intentionally Fragile Scrapers） | OpenGSA 若以 LLM 萃取，這個原則要改成「欄位無證據就留空並進審核佇列」，不能照搬例外機制。 |
| 8 | 輸出強制 `sources` 至少一筆且為 URI，違反即不通過。這直接對應「卡片要附來源證據」。 | 萃取、審核、上架 | Open States | `openstates-core/openstates/scrape/schemas/common.py` | 這只保證「有網址」，不保證「網址內容真的支持該欄位」，後者仍需人工或第二道檢查。 |
| 9 | 基底類別的合理性檢查：欄位長度一致、必要欄位非空、日期不可荒謬（如 22 世紀）。獎助學金可類推為：截止日不早於公告日、金額為正、截止日不在過去太久。 | 萃取後、審核前 | CourtListener | `juriscraper/AbstractSite.py` 的 `_check_sanity` | 規則需依獎助學金情境重寫；Juriscraper 的欄位本身不適用。 |
| 10 | PDF 分級抽取：先試純文字抽取，抽不到內容才進 OCR，並在紀錄上標「是否經 OCR」，供審核時提高警覺。 | 抓取本文、整理待粹資訊 | CourtListener | `cl/scrapers/tasks.py`（`extract_opinion_content`）；Doctor README | OCR 需 tesseract 等工具，GitHub Actions 可裝但要看執行時間；掃描檔品質差時金額與日期誤認率高（本次未實測），務必進人工審核。 |
| 11 | 在文本上附整份文件的校驗碼，使「同一份 PDF 換了網址」或「同網址換了內容」都能被辨識。 | 抓取本文、資訊彙整 | changedetection.io | `processor.py` 的 `preprocess_pdf` | 只用於比對，不能取代網址；政府網站常重新輸出同內容 PDF，會有假異動。 |
| 12 | 保存來源頁快照到網路存檔（或自建快照），供證據連結在原網址失效後仍可追溯。 | 抓取本文、上架（證據保存） | City Scrapers | `city_scrapers/middleware.py`（`CityScrapersWaybackMiddleware`）；`settings/archive.py` | 取決於外部存檔服務的可用性與條款，本次未查其使用限制；需確認可否對台灣政府網站大量送存。另請注意該程式只抽樣最多 3 個連結。 |
| 13 | 本輪不再出現的項目標記為「已不見／取消」並保留，不直接刪除。 | 資訊彙整、上架（下架判斷） | City Scrapers | `city-scrapers-core/city_scrapers_core/pipelines/diff.py` | 入口頁暫時打不開也會造成「不見」，需先排除抓取失敗再下判斷（與做法 6 合用）。 |
| 14 | 每個來源的健康狀態：本輪抓到 0 筆即標為 failing，並可用徽章公開顯示。 | 來源管理、營運監看 | City Scrapers | `city-scrapers-core/city_scrapers_core/extensions/status.py` | 對本來就偶爾沒有新公告的來源會誤判，建議改為「連續多輪 0 筆」才標示。 |
| 15 | 日期與狀態欄位的建模：狀態用有限列舉加自訂值（open、closed、forecasted、custom），日期用 postDate、closeDate、otherDates，另保留 `source` 與 `customFields`。 | 萃取、資訊彙整 | CommonGrants | `lib/core/lib/core/models/opportunity/base.tsp`、`status.tsp`、`timeline.tsp` | 以美國聯邦補助為設計對象，沒有「定額獎學金」「續領條件」「在學身分限制」等台灣常見欄位，需自行擴充；本次只讀了模型原始碼，未驗證其 API 實作。 |
| 16 | 結構變更前先看輸出差異：每次執行存成有日期的資料夾，以便比對兩次執行結果。 | 抓取、整理、審核 | Open States（spatula） | `docs/contributing/scrapers.md`（Running Spatula Scrapers） | OpenGSA 已是 git 內 JSON，直接用 git diff 即可，不必另建資料夾。 |
| 17 | 新來源的貢獻流程：先認領避免重工，提交時附範例檔與預期輸出做回歸測試。可轉成「新來源提交需附一份樣本頁與預期欄位」。 | 使用者提交來源、審核、新來源輸入 | CourtListener（Juriscraper） | `CONTRIBUTING.md`（Contributing Workflow、`tests/examples`） | 範例檔會隨網站改版過期，只能驗證解析邏輯，不能驗證網站現況。 |

## 五、不該學的部分

1. 偽裝與繞過：Juriscraper 提供模仿 Chrome 的 User-Agent 選項、Open States 核心的熔斷機制在暫停後會輪換 User-Agent（程式註解寫明）、City Scrapers 的 Cron 工作流程以 OpenVPN 連線。這些與 OpenGSA「遵守 robots、同網域間隔」的原則衝突，且對公開網站有被視為規避封鎖的風險。OpenGSA 應維持誠實的 User-Agent 與聯絡方式。
2. 整套服務堆疊：CourtListener 的 Django、Elasticsearch、Celery，changedetection.io 的 Flask 與瀏覽器自動化，Open States 的 Postgres 匯入，都假設有常駐主機與資料庫。OpenGSA 是靜態網站加 GitHub Actions，不應為了照抄而增加營運負擔。
3. 每個來源一支客製爬蟲：Open States 與 CourtListener 靠大量志工維護數百支爬蟲，文件也承認多數故障來自網站改版。OpenGSA 的來源是異質的學校、基金會與政府頁面，若走這條路，維護成本會高於收益；較適合「通用抓取 + 規則化萃取 + 人工審核」。
4. 沒有審核關卡的設計：changedetection.io 是監看工具，改變即通知，沒有「資料可信才上架」的概念；Open States 對爬蟲的「不鼓勵測試」策略也建立在有成熟匯入與驗證管線的前提上，OpenGSA 不應把它當成降低驗證的理由。
5. 授權傳染：Open States scrapers 為 GPL-3.0、CourtListener 為 AGPL，直接複製程式碼會對 OpenGSA（MIT）的授權造成限制。這兩者只適合借鑑概念、重新實作，不要複製程式碼。changedetection.io（Apache-2.0）、City Scrapers 與 spatula（MIT）、scrapelib 與 Juriscraper 與 Doctor（BSD-2-Clause）相對寬鬆，但引用時仍須保留授權聲明。
6. 依賴官方託管服務或付費代理：changedetection.io 的 README 推銷付費訂閱與代理服務；與 OpenGSA 的零成本目標不符。
7. 把「官方宣稱的低成本」當成事實：changedetection.io 對 LLM 成本的說法是行銷用語，OpenGSA 的長期文件已正確地要求先實測；本報告不替它背書。

## 六、本次未確認事項

- Open States 的 text-extraction repo 目前是否存在與其授權（API 回 404）。
- Open States 與 CourtListener 的人工資料審核流程。
- changedetection.io 是否有同網域最短間隔與 robots.txt 處理（只檢視了三個檔案）。
- changedetection.io 同時並行抓取的上限值。
- Simpler.Grants.gov 在資料品質與審核上的做法（只讀了資料轉換與查表兩份文件）。
- 360Giving 標準的程式碼授權。
- 網路存檔服務對大量送存的限制。
- 所有專案實際部署成本。

## 七、主要來源網址清單

- https://github.com/openstates/openstates-scrapers
- https://github.com/openstates/openstates-core
- https://github.com/openstates/documentation
- https://github.com/jamesturk/spatula
- https://github.com/jamesturk/scrapelib
- https://github.com/dgtlmoon/changedetection.io
- https://github.com/freelawproject/courtlistener
- https://github.com/freelawproject/juriscraper
- https://github.com/freelawproject/doctor
- https://github.com/City-Bureau/city-scrapers
- https://github.com/City-Bureau/city-scrapers-core
- https://github.com/City-Bureau/city-scrapers-template
- https://github.com/HHS/simpler-grants-gov
- https://github.com/HHS/simpler-grants-protocol
- https://github.com/ThreeSixtyGiving/standard
- https://github.com/biglocalnews/civic-scraper
- OpenGSA 原文件：https://github.com/matt-ye/opengsa/blob/main/docs/LONG-TERM-ARCHITECTURE-AND-OPERATIONS.md
