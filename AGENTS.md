# OpenGSA 工作規則

- 先讀 README.md 與 docs/PLAN.md；最新已接受決策優先於 docs/reference/HANDOFF.md 中的歷史階段提案。
- 目前核可repo、規劃／資料基礎及四分頁互動原型，使用者已接受v0.6作為MVP介面基礎；v0.7補固定篩選卡與本次研討會試算。第一至三頁共用選項，第四頁獨立維護。2026-10-29另核可合併PR1、透過PR2上架GitHub Pages公開預覽；正式資料契約、獨立覆核及正式服務發布門檻仍待完成，不啟用來源掃描排程或通知。
- 維持繁體中文文件。來源、資格與期限不猜測；所有候選資料標示查核程度。
- 真實個資、登入內容、原始私人附件與本機路徑不得入庫；合成測試案例須明示。
- 重大資料變更需獨立覆核；未覆核保留待審，不假稱通過驗收。
- 不建立高於目前需求的服務、資料庫或 AI 推薦；技術選型在開始實作前再核對。
- docs/OPERATIONS-PLAN.md是維運討論提案，未核可來源掃描排程、建立D1、推論呼叫或Secrets變更；公開預覽部署依docs/DEPLOYMENT.md，本機API資產評估不得加入公開repo。
- docs/INGESTION-POC.md及docs/examples/ingestion-sources.proposed.json是首批來源／Actions設計，不是已實作的爬蟲；不得把提案直接當啟用資料掃描workflow的授權。pages.yml只驗證並部署公開成品。
