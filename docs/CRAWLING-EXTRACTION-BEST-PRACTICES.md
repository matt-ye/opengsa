# 爬取與欄位萃取的官方最佳實務查核

查核日期：2026-10-31。只採工具作者、供應商官方文件及協定標準；以下是來源摘要與 OpenGSA 的工程判斷，沒有本輪推論或解析器跑分。不把套件預設當成本專案已核可行為。

## 1. 查核結果與採用方向

| 主題 | 官方依據 | 對 OpenGSA 的建議（工程判斷，尚待實作部分依規劃文件） |
|---|---|---|
| 模型 Token 與能力 | [Gemini Token 文件](https://ai.google.dev/gemini-api/docs/tokens) 說明請求計數及模型輸入／輸出能力查詢 | 計完整請求，保留輸出與安全餘裕；不同模型上限分別記錄，不以固定字元截斷代替 Token 檢查 |
| 共用 context 與輸出開銷 | [Claude context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)、[token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting) 說明指令、訊息、工具與輸出都影響 context，並提供預先計數 | 依供應商核對推理／輸出保留；估計與實際用量分開記錄。此文件不選用 Claude、不新增 key 或執行 API |
| 結構化分段 | [Unstructured Chunking](https://docs.unstructured.io/open-source/core-functionality/chunking) 先按文件元素分割，保留章節與表格；超長元素才細分，並可設定 overlap | 借鑑結構優先方法，以現有解析器實作；不因此引入套件。表頭、註腳、身分及跨條例外另列驗收 |
| 結構化輸出 | [Gemini Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) 支援 JSON Schema，且明確要求應用程式繼續驗證值與語意 | 各欄位任務使用小型明確 Schema；不同 provider 支援範圍不同；JSON 正確不等於資格、日期與金額正確 |
| 節流 | [Scrapy AutoThrottle](https://docs.scrapy.org/en/latest/topics/autothrottle.html) 依延遲調整節流，錯誤回應不應促使更快下載 | 維持現有主機間隔／上限；記錄失敗及延期。借鑑原則，沒有安裝或切換 Scrapy |
| HTTP 重新驗證 | [Scrapy HTTP cache](https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#module-scrapy.downloadermiddlewares.httpcache) 支援 ETag、Last-Modified 重新驗證 | 保留條件請求及來源雜湊；不得直接啟用會保存原始 body 的檔案快取。父頁與附件版本分開追蹤 |
| robots 與授權 | [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) 定義爬取規則、錯誤與快取，並明示 robots 不是存取授權 | robots、條款／授權、登入限制分開記錄；本專案維持更保守的既有策略，沒有放寬不明 robots 的處置 |
| 爬蟲框架設定 | [Crawlee BasicCrawlerOptions](https://crawlee.dev/js/api/basic-crawler/interface/BasicCrawlerOptions) 提供 respectRobotsTxtFile、同站延遲及 retryOnBlocked 等選項 | 導入框架不能照搬預設；尤其不得啟用本專案未核可的防護繞過或 session 輪替。現階段繼續使用既有 Fetcher |
| 正文清理 | [Defuddle 作者 README](https://github.com/kepano/defuddle/blob/main/README.md) 說明從 HTML／DOM 擷取主內容並清理雜訊 | 只評估解析取得的 HTML；必須比對是否漏條文、表格、腳註與附件，並保持原定位。原始 TS 專案與 Python 移植各自核對版本、維護者及授權 |

沒有任何上述來源證明「所有模型都應固定使用同一 chunk 大小」「分成五組一定省 Token」或「某解析器對本專案保證零漏失」。這些都必須以本批人工核對樣本測量。完整可送入的 context 也不保證模型能正確理解長距離例外。

## 2. 建議的爬取與萃取邊界

先辨識來源與存取限制，再取得 HTML／API／PDF，接著解析、分段、萃取及核驗。每層都有獨立狀態：能連線、能取得正文、欄位有證據、判斷完整、人工核准分開計數。

來源可提供官方 API、RSS 或替代下載頁，但必須核對具體端點、資料集版本、提供者、授權、限制、更新日、格式及實際回應；資料開放授權不等於請求不限量，也不能自動免除替代主機的存取檢查。

RSS 適合發現公告，通常不足以確認全部資格；常態法規可作制度基準，但無法替代當期徵件。HTTP 成功而正文空白不直接推定 JavaScript SPA；需排查 selector、iframe、編碼、跳轉或非預期頁面。403 不直接推定 WAF，逾時不等同 404／410。

檢核必須確認欄位的對象、年度、分支、單位與條件，不能只確認數字或關鍵字存在。來源與模型文字皆視為不可信輸入；來源內指令不能改變允許欄位、預算、外送範圍或發布門檻。

## 3. PR #25 的可採用方向與待補證事項

<a id="pr25"></a>

已讀 [PR #25](https://github.com/matt-ye/opengsa/pull/25) 的研究文件（查核 head：`2beef58`）。下列是整合註記，不修改其分支、不代替全面 PR 審查；其中「實測通過」尚不能直接匯入正式來源台帳。

可採用：存取層／解析層分離、官方 API／RSS／公開替代下載優先、Defuddle 定位於正文清理，以及生輔組維持人工查核的決策。

| PR #25 內容 | 本輪判斷與需要補齊的證據 |
|---|---|
| 全國法規 Open Data 取得全文的案例 | 缺具體資料集頁、下載/API URL、請求方式、回應雜湊、取得時間及抽樣核對；先列「候選替代路徑」，不繼承通過標記。報告所列法規版本／條數需重新核對 |
| 「API 無抓取頻率限制、不受網頁 robots 拘束」 | 無法由開放授權直接推導。逐端點檢查政策、限制與預算；API 也不是全面免查存取條款 |
| 秘書室兼任上限表替代 PDF | 缺完整父頁與檔案 URL、版本、檔案雜湊、條文／表格定位及重現紀錄。上限、下限、專任／兼任、學歷／在學身分須分開，不承接報告內未核驗數字 |
| 工具可省 50%–90% Token、BS4 精確率 100% 且零漏失 | 未附 corpus、版本、tokenizer、計算基準與結果，不列為已測效能。改以表格／例外召回率、證據率與實際 Token 做對照實驗 |
| 校內鏡像與 SHA-256 核對 | 相同原始雜湊可證明位元組一致；雜湊不同不直接代表條文不同，同源／授權／最新有效性也不能只靠雜湊證明 |
| 生輔組「無可用自動路徑」 | 目前保守維持人工查核；沒有找到替代路徑不代表證明永遠不存在。人工文件匯入仍需來源、可公開範圍與版本驗證，不能假設工作台已支援任意私人 PDF 匯入 |
| 舊基準 101 Python、12／7 候選 | PR #25 沿用 PR #24 較早快照。整合時須保留 #24 最新 110 Python、8／11 及穩定化修正，不將研究摘要覆蓋回舊狀態 |

PR #24 與 #25 仍未合併，PR #25 包含來源盤查的較早共同歷史。建議先審 #24，再整理 #25 的研究增量與補證；本 PR 僅新增規劃與來源查核，不合併或啟用其替代路徑。

## 4. 後續可重現實驗

先以既有來源及合成案例測試：完整條文、HTML 表格、跨頁 PDF、後段例外、重複金額、年度混用及受限來源。

記錄工具／模型版本、設定、原始文件 revision、輸入範圍與清理前後 Token；只保留允許的結構化輸出、定位、雜湊與短證據，原文仍在記憶體處理。比較固定截斷、結構分段、指定欄位三種策略，保留人工核對的驗證集，不預填任何模型勝出或節省百分比。

實作規格與分期驗收見 [欄位與長文本規劃](FIELD-SCOPED-EXTRACTION-PLAN.md)。
