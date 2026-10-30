# API、模型與額度查核

查核日：2026-10-30（臺北）。已確認8組Repository Secrets存在；不讀出值、不寫入Git、不放在網站。所有API只供手動操作或本機評測，排程仍為`model_mode=off`。模型與端點的唯一設定在[model-providers.json](../data/model-providers.json)，非永久可用清單。

## 這次實際確認到哪裡

官方文件用來確認端點、政策與模型退役；帳戶可讀的模型目錄另用手動Actions查核。**目錄成功、驗證成功、JSON推論成功、免費資格及金鑰效期分別記錄**；未知金額是`null`，不填0。

| Provider／Repository Secret | 目前預設模型 | 本次目錄數 | 實測與成本狀態 |
|---|---|---:|---|
| Groq／`OPENGSA_MODEL_API_KEY` | `qwen/qwen3.8-27b` | 11 | 一次合成JSON通過，23輸入＋6輸出＝29 tokens；依使用者免費帳戶設定允許手動小量推論 |
| Gemini／`OPENGSA_GEMINI_API_KEY` | `gemini-3.5-flash-lite` | 60 | 目錄有此模型；初版誤因`models/`前綴顯示不存在，已修正並核對原報告。帳戶免費方案與推論未驗證，僅查目錄 |
| NVIDIA／`OPENGSA_NVIDIA_API_KEY` | `openai/gpt-oss-20b` | 85 | 舊Llama 3.3預設不在本次目錄，改為目錄中模型；剩餘credits及推論未驗證 |
| SambaNova／`OPENGSA_SAMBANOVA_API_KEY` | `Meta-Llama-3.3-70B-Instruct` | 6 | 模型存在；帳戶tier及推論未驗證 |
| Cerebras／`OPENGSA_CEREBRAS_API_KEY` | `gpt-oss-120b` | 2 | 模型存在；免費資格及推論未驗證，不再預設已退役Llama 3.3 |
| OpenRouter／`OPENGSA_OPENROUTER_API_KEY` | `google/gemma-4-26b-a4b-it:free` | 401 | 其中16個目錄模型同時為`:free`且輸入／輸出價0；key metadata可讀。首次Nemotron回應HTTP 200但JSON不符（187 tokens）；調整模型與JSON參數後遇429，停止重試。Gemma尚未通過推論驗收 |
| SiliconFlow／`OPENGSA_SILICONFLOW_API_KEY` | `Qwen/Qwen2.5-7B-Instruct` | 81 | 使用者確認國際站`cloud.siliconflow.com`；端點`api.siliconflow.com/v1`，region=com。模型存在；國際站免費資格及推論未驗證，不套用中國站宣傳額度 |
| Mistral／`OPENGSA_MISTRAL_API_KEY` | `mistral-small-latest` | 55 | 模型存在；帳戶tier及推論未驗證 |

目錄數為觀察值，可能含影像、語音或嵌入模型，不代表全部適用結構化萃取。公開模型目錄也可能不要求有效key，故不能據此宣稱8把key皆已驗證成功。本次總計3次合成推論嘗試，僅Groq通過；沒有傳送獎學金原文或學生資料。

查核證據：[首次跨Provider查核](https://github.com/matt-ye/opengsa/actions/runs/41031333796)、[SiliconFlow國際站目錄](https://github.com/matt-ye/opengsa/actions/runs/41031646742)、[OpenRouter單獨檢查](https://github.com/matt-ye/opengsa/actions/runs/41031650656)。原始安全報告為14天Actions artifact，未把帳戶資訊當成正式網站資料；本文件保留摘要，artifact到期不表示模型永久可用。

## 額度與效期：撤換舊handoff的固定宣稱

- Gemini 1.5 Flash已退役，不再使用；「免費1,500 RPD」不能套在新模型或本帳戶。[官方變更紀錄](https://ai.google.dev/gemini-api/docs/changelog)、[目前額度](https://ai.google.dev/gemini-api/docs/rate-limits)、[相容端點](https://ai.google.dev/gemini-api/docs/openai)。
- Groq限額依模型、組織及tier不同。本次回應headers顯示requests limit 1000、tokens limit 8000，是當次觀察，不能概括為每個模型每日／每分鐘皆相同。[官方限流與headers說明](https://console.groq.com/docs/rate-limits)。
- NVIDIA「1,000點」未確認到本帳戶可用餘額，故不據此啟用推論。[官方快速開始](https://docs.api.nvidia.com/nim/re/docs/api-quickstart)。
- Cerebras模型依退役公告及本次目錄更新，不能沿用`llama-3.3-70b`。[官方退役資訊](https://inference-docs.cerebras.ai/support/deprecation)。
- OpenRouter本次metadata先顯示free daily limit50／remaining50，第二次顯示used1／remaining49；不代表所有帳戶永久相同，429也不能推定必然是日額度耗盡。[官方限制說明](https://openrouter.ai/docs/api_reference/limits)。
- SiliconFlow官方國際站提供模型價格與帳戶限制查詢，不以目錄可見推定模型免費。[官方國際站開始說明](https://docs.siliconflow.com/en/userguide/quickstart)。
- SambaNova一年到期是使用者提供的key條件，實際日期尚未提供；不從Secret更新日猜到期日。[官方key與URL說明](https://docs.sambanova.ai/docs/en/get-started/api-keys-urls)。其餘「未設固定期限」也不保證服務、免費方案或額度永久有效；Mistral效期依key設定及組織政策核對。[官方key管理](https://docs.mistral.ai/admin/identity-access/api-keys)。

## 手動操作與安全邊界

Actions → **Scan public sources** → Run workflow：

1. 查模型目錄：`operation=provider_audit`、`audit_scope=單一provider或all`、`probe=false`。報告只保留模型ID、狀態與數字額度，不留key、原始錯誤內容或完整HTTP headers。
2. 小量合成推論：另選`probe=true`，每個符合成本政策的provider最多一次、輸出最多160 tokens。其他provider即使指定probe，仍跳過推論；要啟用須先確認官方及本帳戶免費／credits條件，再PR修改成本政策。
3. 正文萃取：`operation=scan`、在main選單一`model_provider`，`model_mode=audit/extract/both`。排程強制off；無key、成本未確認、401／402／403、429或解析失敗，退回規則結果，不自動轉用其他provider或付費模型。每次最多6次模型請求，不重試429。

通用key目前明確對應既有Groq端點，不拿來試其他服務。全域`OPENGSA_MODEL_BASE_URL`／`OPENGSA_MODEL_NAME`只套Groq，其他provider使用自身預設；可用`OPENGSA_<PROVIDER>_MODEL`本機覆寫模型。SiliconFlow區域需明示，不跨區嘗試同一把key。端點白名單、禁止帶key重新導向、快取包含端點與模型、受限來源`_guard_hash_only`共同限制外送。`hash_only_bytes_sent`必須維持0。

每月或遇404／模型退役時，先重新查官方文件及目錄；額度或計費不明時維持catalog-only。手動audit不是定期計費監控；本次沒有新增自動key輪替或通知服務。
