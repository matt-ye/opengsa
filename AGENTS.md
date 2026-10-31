# OpenGSA 工作規則

- 2026-10-30 最新核可：候選審查工作台、第一至三頁未發布預覽、下載人工處置意向、當次來源版本核驗後匯出資料 PR 草稿；PR #20 另獲准並已合併。來源缺漏與個人條件未填分開。工具不代填真人核准、不寫正式總表／人工台帳、不自動提交或發布資料。操作見 docs/REVIEW-WORKSPACE.md；排程模型維持 off。

- 先讀 README.md 與 docs/PLAN.md；最新已接受決策優先於 docs/reference/HANDOFF.md 中的歷史階段提案。
- 目前核可repo、規劃／資料基礎及四分頁互動原型，使用者已接受v0.6作為MVP介面基礎；v0.7補固定篩選卡與本次研討會試算。第一至三頁共用選項，第四頁獨立維護。2026-10-29另核可合併PR1、透過PR2上架GitHub Pages公開預覽；正式資料契約、獨立覆核及正式服務發布門檻仍待完成，不啟用來源掃描排程或通知。
- 維持繁體中文文件。來源、資格與期限不猜測；所有候選資料標示查核程度。
- 真實個資、登入內容、原始私人附件與本機路徑不得入庫；合成測試案例須明示。
- 重大資料變更需獨立覆核；未覆核保留待審，不假稱通過驗收。
- 不建立高於目前需求的服務、資料庫或 AI 推薦；技術選型在開始實作前再核對。
- docs/OPERATIONS-PLAN.md是整體維運提案，有限來源掃描依SCANNER.md已獲後續核可；D1、推論呼叫與Secrets變更仍未核可。公開預覽部署依docs/DEPLOYMENT.md，本機API資產評估不得加入公開repo。
- docs/INGESTION-POC.md及docs/examples/ingestion-sources.proposed.json是首批來源／Actions設計，不是已實作的爬蟲；不得把提案直接當啟用資料掃描workflow的授權。pages.yml只驗證並部署公開成品。
- v0.8研討會個人列可加入甘特圖並跨頁共用，資料僅本次記憶體；conference-programs.json為待覆核方案／來源台帳，不含個人輸入，不把機構期限、準備建議或接受通知當作官方學生起訖／補助結果。
- 2026-10-29使用者另要求實作自動爬取；已核可範圍擴至SCANNER.md的有限公開GET、每週二／五09:17（臺北）低頻掃描及待覆核報告。此決策取代前述掃描未啟用的歷史描述；仍不啟用模型、D1、私人API、通知或自動改寫正式資料。每次檢查robots，教務處依轉載條款只存雜湊／定位，研發處/WebUPD/不下載。
- 2026-10-29使用者另核可「規則＋LLM API」雙軌資料萃取（補漏 extract）與盤查（audit），並授權以本機既有環境變數金鑰對非受限（short_excerpt）來源作小量實測與基準評測；Actions 僅設計預設關閉（model_mode=off）之手動模型選項，排程仍維持模型關閉。此決策更新前述不呼叫模型的本機測試限制；教務處等 hash_only 來源仍嚴禁送往外部 API，新增 GitHub Secrets、排程自動呼叫模型、付費服務、D1、通知與自動改寫正式資料仍未核可。

- 2026-10-30最新核可：使用者已自行存入8組OPENGSA_ Repository Secrets，並授權整輪可靠性優化、官方API／模型目錄查核與小量手動合成推論，要求整理成一個PR供審查。SiliconFlow為國際站cloud.siliconflow.com，region=com；同一key不得跨區試探。這取代上述Secrets／手動推論未核可描述；排程仍model_mode=off，不啟用付費、D1、訂閱或自動改寫正式資料。API成本未確認者只查目錄；429不連續重試。最新操作見docs/API-AUDIT.md、docs/SCANNER.md，法律摘要見docs/RIGHTS-AND-LEGAL-FRAMEWORK.md。既有擴展文件屬搜尋種子，不把未查證網址或金額當成已支援來源。正式台帳不得有合成人工覆核者。
