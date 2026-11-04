# 研究生與學生專用：10 大免費大語言模型（LLM）API Key 申請全攻略與實踐指南

> **本指南定位**：專為大專院校在校學生、碩博士研究生與學術研究人員整理的**正規合規、零成本（或高額免費額度）之大語言模型 API Key 申請指南**。
>
> 內容涵蓋 OpenGSA 與相關學術專案實測驗證之主流 AI API 供應商。所有服務均支援標準 **OpenAI 相容協議（OpenAI-compatible REST API）** 或提供官方 SDK，讓學生無需每月支付高昂訂閱費（如 ChatGPT Plus 或 Claude Pro），即可將頂尖開源與商用模型（如 Llama 3.3 70B、DeepSeek R1、Qwen 2.5、Gemini 2.0/1.5 Flash）無縫整合至論文研讀、文獻摘要、結構化資訊萃取與研究程式碼開發中。
>
> ⚠️ **重要除役避坑公告**：原本社群廣泛討論之 **GitHub Models**（微軟 Azure 提供之免費 API）已於 **2026 年 7 月 30 日正式終止服務除役（HTTP 410 Gone）**，其模型目錄與 API 端點均已全面關閉。請同學切勿再參考過期網路教學，直接使用本指南收錄之現行有效服務。

---

## 1. 10 大免費 AI API 供應商橫向評比總覽

依「**串接難易度、推論速度、免綁卡程度與學術實用性**」分級評比：

### 【第一梯隊：無痛主力推薦（最推、免綁卡、標準 OpenAI 端點、速度極快）】

| 供應商 (Provider) | 官方申請入口 | 信用卡需求 | 免費額度與速率限制 | 主力推薦模型 | 核心優勢與適用場景 |
|---|---|:---:|---|---|---|
| **1. Groq Cloud** | [console.groq.com](https://console.groq.com/) | **免綁卡** | • 30 RPM / 14,400 RPD<br>• ~6,000–8,000 TPM | Llama 3.3 70B<br>Qwen 2.5 32B | **極致推論速度**（自研 LPU 架構，每秒 200~300+ Tokens），最適合即時互動、串流輸出與批次文獻初篩。 |
| **2. Google AI Studio** | [aistudio.google.com](https://aistudio.google.com/) | **免綁卡** | • 15 RPM / 1,500 RPD<br>• 1,000,000 TPM | Gemini 1.5 Flash<br>Gemini 2.0 Flash<br>Gemini 1.5 Pro | **超長上下文窗口**（高達 1M~2M Tokens），可直接餵入整本碩博士論文 PDF、書籍或大型代碼庫。 |
| **3. Cerebras Inference** | [cloud.cerebras.ai](https://cloud.cerebras.ai/) | **免綁卡** | • 30 RPM<br>• 每日高達 100 萬 Tokens | Llama 3.3 70B<br>Llama 3.1 8B | **全球最快推論速度**（晶圓級引擎 WSE-3，每秒高達 1,800~2,000+ Tokens），高通量數據萃取首選。 |

---

### 【第二梯隊：高額度／大模型／多模型聚合備援（標準端點、備援首選）】

| 供應商 (Provider) | 官方申請入口 | 信用卡需求 | 免費額度與速率限制 | 主力推薦模型 | 核心優勢與適用場景 |
|---|---|:---:|---|---|---|
| **4. OpenRouter** | [openrouter.ai](https://openrouter.ai/) | **免綁卡** | • 每日 20~50 次免費請求<br>• 標註 `:free` 模型完全免費 | 16+ 款標籤模型<br>DeepSeek R1 :free<br>Gemma 2 :free | **模型聚合中樞**，一次配置即可無縫切換數十種全球最新模型，並具備自動 Fallback 容錯路由。 |
| **5. SambaNova Cloud** | [cloud.sambanova.ai](https://cloud.sambanova.ai/) | **免綁卡** | • 免費開發者 Tier<br>• 充足免費呼叫頻率 | Llama 3.3 70B<br>**Llama 3.1 405B** | **頂級大參數量模型免費跑**（SN40L 自研晶片驅動），免費用 405B 超大模型進行深度學術邏輯推論。 |
| **6. SiliconFlow 國際站** | [cloud.siliconflow.com](https://cloud.siliconflow.com/) | **免綁卡** | • 註冊送免費額度<br>• 特定 7B 模型永久免費 | Qwen 2.5 7B/72B<br>DeepSeek V3/R1 | **開源模型支持極為即時**，對繁體中文與東亞語言理解極佳，API 響應非常穩定。 |
| **7. NVIDIA NIM** | [build.nvidia.com](https://build.nvidia.com/) | **免綁卡** | • 註冊即贈 **1,000 Credits**<br>• 每調用約扣 1 點 | Llama 3.3 70B<br>DeepSeek R1<br>Mistral Large | **企業級加速微服務**，模型種類極為豐富（包含 Nemotron 等頂尖開源權重），推論穩定且延遲低。 |
| **8. Mistral AI** | [console.mistral.ai](https://console.mistral.ai/) | **免綁卡** (需手機驗證) | • 免費 Experiment Tier<br>• 1 RPM / 依各模型限額 | Mistral Small<br>Codestral 22B | **歐洲頂尖開源勢力**，Codestral 在程式代碼生成與除錯表現優異，原生支援 80+ 種語言。 |

---

### 【第三梯隊：特定生態系專用備援（有眉角／需視架構使用）】

| 供應商 (Provider) | 官方申請入口 | 信用卡需求 | 免費額度與速率限制 | 主力推薦模型 | 串接眉角與適用場景 |
|---|---|:---:|---|---|---|
| **9. Cloudflare Workers AI** | [dash.cloudflare.com](https://dash.cloudflare.com/) | **免綁卡** | • 每日 **10,000 Neurons**<br>• 約數萬至十萬 Tokens | Llama 3.3 70B<br>DeepSeek R1 Distill<br>bge 向量嵌入 | **眉角**：REST API 強制要求在 URL 中拼接 `ACCOUNT_ID`，外部工具配置較繁瑣；有冷啟動。<br>**適用**：原生跑在 Cloudflare Workers 的 Serverless 背景任務（如 `lit-search-worker`）。 |
| **10. Hugging Face Inference** | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | **免綁卡** | • 社群共享免費頻率<br>• 產生 Access Token (read) | Qwen 2.5 72B<br>數萬款開源微調模型 | **眉角**：大模型冷啟動頻繁（常遇 HTTP 503 Model Loading 排隊），70B 易超載。<br>**適用**：需要調用冷門特定開源微調小模型（7B/8B）或專業 Embedding 向量模型時。 |

---

## 2. 各供應商詳細申請步驟與程式碼範例

### 2.1 Groq Cloud
- **官方網站**：[https://console.groq.com/](https://console.groq.com/)
- **申請資格**：任何 Email 均可註冊（支援 Google / GitHub 一鍵登入），無需綁定任何信用卡。
- **獲取 Key 步驟**：
  1. 登入後點擊左側導覽列的 **API Keys**。
  2. 點擊 **Create API Key**，輸入名稱（例如 `student-research`）後立即複製保存。
- **OpenAI SDK 配置範例**：
  ```python
  from openai import OpenAI

  client = OpenAI(
      base_url="https://api.groq.com/openai/v1",
      api_key="gsk_..."  # 填入您的 Groq API Key
  )

  response = client.chat.completions.create(
      model="llama-3.3-70b-versatile",
      messages=[{"role": "user", "content": "請用繁體中文摘要以下這篇論文的研究貢獻：..."}]
  )
  print(response.choices[0].message.content)
  ```

---

### 2.2 Google AI Studio (Gemini API)
- **官方網站**：[https://aistudio.google.com/](https://aistudio.google.com/)
- **申請資格**：一般 Google 帳號（個人 Gmail 或學校 `.edu.tw` 信箱均可），完全免信用卡。
- **獲取 Key 步驟**：
  1. 進入 Google AI Studio，同意服務條款。
  2. 點擊左上方 **Get API key** $\to$ **Create API key in new project**。
- **免費層說明**：
  - 選擇 **Free tier (Prompt data may be reviewed by human reviewers)**。
  - 對於 `gemini-1.5-flash` 或 `gemini-2.0-flash-exp`，提供高達每分鐘 15 次請求、每日 1,500 次請求。
  - **適用亮點**：支援直接上傳完整 PDF 或影音，上下文長達 100 萬字元，是閱讀長篇文獻的神器。

---

### 2.3 Cerebras Inference
- **官方網站**：[https://cloud.cerebras.ai/](https://cloud.cerebras.ai/)
- **申請資格**：免費註冊。
- **特色**：目前全球推論輸出速度天花板（~2,000 tokens/sec）。對於需要處理數百篇文獻標題與摘要（TIAB Screening）的研究人員，原本需要跑半小時的萃取任務，在 Cerebras 上數十秒即可完成。
- **OpenAI 相容端點**：
  - Base URL: `https://api.cerebras.ai/v1`

---

### 2.4 OpenRouter
- **官方網站**：[https://openrouter.ai/](https://openrouter.ai/)
- **申請資格**：GitHub 或 Google 帳號直接登入。
- **使用秘訣**：
  - 搜尋模型時過濾 **Free** 標籤，模型 ID 後方帶有 `:free`（例如 `deepseek/deepseek-r1:free`、`meta-llama/llama-3.3-70b-instruct:free`）。
  - 無需儲值任何金額，即可每日免費調用 20~50 次。若未來稍微儲值 $1 美元，免費模型的每日頻率上限將會大幅放寬至數百次。
- **OpenAI 相容端點**：
  - Base URL: `https://openrouter.ai/api/v1`

---

### 2.5 SambaNova Cloud
- **官方網站**：[https://cloud.sambanova.ai/](https://cloud.sambanova.ai/)
- **申請資格**：開發者信箱免費註冊。
- **特色**：由專門為大型模型設計的 SN40L 晶片集群驅動。
- **可用模型**：`Meta-Llama-3.3-70B-Instruct`、甚至參數量高達 405B 的 `Meta-Llama-3.1-405B-Instruct`。
- **OpenAI 相容端點**：
  - Base URL: `https://api.sambanova.ai/v1`

---

### 2.6 SiliconFlow 國際站 (矽基流動)
- **官方網站**：[https://cloud.siliconflow.com/](https://cloud.siliconflow.com/)
- **申請資格**：信箱註冊驗證。
- **使用注意**：OpenGSA 專案使用國際站 `region=com`（端點為 `https://api.siliconflow.com/v1`），同一組金鑰請勿跨區試探。
- **永久免費模型**：包括 `Qwen/Qwen2.5-7B-Instruct`、`THUDM/glm-4-9b-chat` 等，適合一般常規文本分類、實體辨識（NER）與格式轉換任務。

---

### 2.7 NVIDIA NIM (API Catalog)
- **官方網站**：[https://build.nvidia.com/](https://build.nvidia.com/)
- **申請資格**：免費註冊 NVIDIA 開發者帳號（信箱驗證即可）。
- **免費點數與額度**：新用戶註冊後，帳戶自動贈送 **1,000 API Credits**。
- **OpenAI 相容端點**：
  - Base URL: `https://integrate.api.nvidia.com/v1`
  - 支援模型：`meta/llama-3.3-70b-instruct`、`deepseek-ai/deepseek-r1` 等。

---

### 2.8 Mistral AI (La Plateforme)
- **官方網站**：[https://console.mistral.ai/](https://console.mistral.ai/)
- **申請資格**：信箱註冊並通過手機 SMS 驗證碼檢查。
- **推薦模型**：`codestral-latest`（程式開發強項）、`mistral-small-latest`。
- **OpenAI 相容端點**：
  - Base URL: `https://api.mistral.ai/v1`

---

### 2.9 Cloudflare Workers AI（串接特點與注意事項）
- **官方網站**：[https://dash.cloudflare.com/](https://dash.cloudflare.com/)
- **申請資格**：免費註冊 Cloudflare 帳號，無須輸入信用卡。每日高達 10,000 Neurons 免費額度。
- **⚠️ 串接難點評析（為什麼大家常覺得難串？）**：
  1. **非標準單一 Base URL**：一般供應商的 Base URL 是固定的（如 `https://api.groq.com/openai/v1`），但 Cloudflare 的 REST API 端點強制把您的使用者 `ACCOUNT_ID` 寫在路徑中間：
     `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1`
     許多只允許輸入 Base URL 的通用軟體或外掛會配置失敗。
  2. **模型 ID 帶有 `@cf/` 前綴**：例如 `@cf/meta/llama-3.3-70b-instruct`，部分 SDK 或正則檢查會誤報格式錯誤。
  3. **冷啟動延遲**：免費層若一段時間未調用，初次加載模型常需等待數秒至十秒。
- **實用建議**：如果您正在撰寫原生 Cloudflare Worker（使用內建 `env.AI.run()` 綁定，如 `lit-search-worker`），體驗極佳且零延遲；但若是本機 Python 腳本或外接軟體，建議優先選用 Groq 或 Cerebras，省去配置 Account ID 的繁瑣。

---

### 2.10 Hugging Face Serverless Inference API（串接特點與注意事項）
- **官方網站**：[https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
- **申請資格**：免費註冊帳號，產生 `read` 權限 Token。
- **端點**：支援 OpenAI 相容協定 `https://api-inference.huggingface.co/v1`。
- **⚠️ 串接難點評析**：
  1. **冷啟動頻繁（HTTP 503 Model Loading）**：免費 Serverless API 的模型並非常駐。若該模型目前沒人在線使用，請求會直接報錯 `503 Model is loading`，需要客戶端撰寫輪詢或等待重試。
  2. **70B 等超大模型容量經常受限**：免費層的運算資源優先提供給 7B~14B 輕量模型，70B 容易遭遇排隊限制。
- **實用建議**：建議申請一組 Token 作為「特定開源微調小模型（如特定領域 NER、分類）」或「向量嵌入（如 BAAI/bge-m3）」的備援，但不建議作為通用大模型問答的第一主力。

---

## 3. 學生與研究人員使用最佳實踐 (Best Practices)

### 3.1 零外洩原則：API Key 安全保管
1. **絕不寫死在程式碼中**：永遠將 Key 放置在專案根目錄的 `.env` 檔案中，並確保 `.gitignore` 包含 `.env`。
   ```bash
   # .env 範例
   GROQ_API_KEY="gsk_..."
   GEMINI_API_KEY="AIzaSy..."
   ```
2. **在 GitHub Actions 中使用 Repository Secrets**：
   - 進入 GitHub Repo $\to$ Settings $\to$ Secrets and variables $\to$ Actions。
   - 新增金鑰（如 `OPENGSA_GROQ_API_KEY`），工作流程式碼以 `${{ secrets.OPENGSA_GROQ_API_KEY }}` 引用，絕不讓 Key 出現在 Git Commit 紀錄中。

### 3.2 避免 429 速率限制（Rate Limits）的因應技巧
- **指數退避機制（Exponential Backoff）**：遭遇 HTTP 429（Too Many Requests）時，切勿連續高頻重試，應等待 $2^n$ 秒（例如 2s、4s、8s）再發起重試。
- **多 Provider 動態備援池（Failover Pool）**：
  - 參考 OpenGSA 專案實作之 `ProviderFailoverPool` 架構：優先調用速度極快之 Groq；若遇 429 或暫態中斷，自動降級切換至 Google Gemini、Cerebras 或 OpenRouter，確保長時間自動化批次腳本不中斷。

---

## 4. 結語與專案宣告

OpenGSA 專案秉持「**把時間留給研究，把獎助檢索交給 OpenGSA**」之理念，所有自動化管線在正式排程中均恪遵安全合規邊界（排程預設關閉推論 `model_mode=off`，僅在手動審查與合成基準中進行最小量驗證）。

希望本份指南能協助臺灣大專院校與碩博士研究生，在面對龐大的文獻閱讀與研究課題時，充分善用頂尖全球雲端運算資源，節省寶貴開銷，專注於真正的創新研究！
