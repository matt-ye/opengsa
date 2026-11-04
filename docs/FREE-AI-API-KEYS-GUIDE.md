# 研究生與學生專用：11 大免費大語言模型（LLM）API Key 申請全攻略與實踐指南

> **本指南定位**：專為大專院校在校學生、碩博士研究生與學術研究人員整理的**正規合規、零成本（或高額免費額度）之大語言模型 API Key 申請指南**。
>
> 內容涵蓋 OpenGSA 與相關學術專案實測驗證之 **11 組主流 AI API 供應商**。所有服務均支援標準 **OpenAI 相容協議（OpenAI-compatible REST API）** 或提供官方 SDK，讓學生無需每月支付高昂訂閱費（如 ChatGPT Plus 或 Claude Pro），即可將頂尖開源與商用旗艦模型（如 GPT-4o、Claude 3.5 Sonnet、Llama 3.3 70B、DeepSeek R1、Qwen 2.5、Gemini 2.0/1.5 Flash）無縫整合至論文研讀、文獻摘要、結構化資訊萃取與研究程式碼開發中。

---

## 1. 11 大免費 AI API 供應商橫向評比總覽

| 供應商 (Provider) | 官方申請入口 | 信用卡需求 | 免費額度與速率限制 | 主力推薦模型 | 核心優勢與適用場景 |
|---|---|:---:|---|---|---|
| **1. Groq Cloud** | [console.groq.com](https://console.groq.com/) | **免綁卡** | • 30 RPM / 14,400 RPD<br>• ~6,000–8,000 TPM | Llama 3.3 70B<br>Qwen 2.5 32B | **極致推論速度**（自研 LPU 架構，每秒 200~300+ Tokens），最適合即時互動、串流輸出與批次文獻初篩。 |
| **2. Google AI Studio** | [aistudio.google.com](https://aistudio.google.com/) | **免綁卡** | • 15 RPM / 1,500 RPD<br>• 1,000,000 TPM | Gemini 1.5 Flash<br>Gemini 2.0 Flash<br>Gemini 1.5 Pro | **超長上下文窗口**（高達 1M~2M Tokens），可直接餵入整本碩博士論文 PDF、書籍或大型代碼庫。 |
| **3. GitHub Models** | [github.com/marketplace/models](https://github.com/marketplace/models) | **免綁卡** | • 15 RPM / 150 RPD<br>• 個人 GitHub PAT 即用 | **GPT-4o**<br>**Claude 3.5 Sonnet**<br>Llama 3.3 70B | **唯一能免費調用 GPT-4o 與 Claude 3.5 的官方管道**，微軟 Azure 提供算力，論文深度論證與高階寫作首選。 |
| **4. Cloudflare Workers AI** | [dash.cloudflare.com](https://dash.cloudflare.com/) | **免綁卡** | • 每日 **10,000 Neurons** 免費<br>• 支援 Serverless 綁定 | Llama 3.3 70B<br>DeepSeek R1 Distill<br>bge 向量嵌入 | **邊緣運算與全球低延遲**，支援 OpenAI 相容 REST API，自帶向量嵌入與語音 Whisper，最適合背景自動化 Worker。 |
| **5. Hugging Face Inference** | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | **免綁卡** | • 社群免費請求頻率<br>• 產生 Access Token (read) | Qwen 2.5 72B<br>DeepSeek 系列<br>數萬開源專屬模型 | **開源生態最前線**，全球最新論文發布之開源權重通常數小時內即可在 Serverless API 隨插即用。 |
| **6. NVIDIA NIM** | [build.nvidia.com](https://build.nvidia.com/) | **免綁卡** | • 註冊即贈 **1,000 Credits**<br>• 每調用約扣 1 點 | Llama 3.3 70B<br>DeepSeek R1<br>Mistral Large | **企業級加速微服務**，模型種類極為豐富（包含 Nemotron 等頂尖開源權重），推論穩定且延遲低。 |
| **7. SambaNova Cloud** | [cloud.sambanova.ai](https://cloud.sambanova.ai/) | **免綁卡** | • 免費開發者 Tier<br>• 充足免費呼叫頻率 | Llama 3.3 70B<br>**Llama 3.1 405B** | **頂級大參數量模型免費跑**（SN40L 自研晶片驅動），免費用 405B 超大模型進行深度學術邏輯推論。 |
| **8. Cerebras Inference** | [cloud.cerebras.ai](https://cloud.cerebras.ai/) | **免綁卡** | • 30 RPM<br>• 每日高達 100 萬 Tokens | Llama 3.3 70B<br>Llama 3.1 8B | **全球最快推論速度**（晶圓級引擎 WSE-3，每秒高達 1,800~2,000+ Tokens），高通量數據萃取首選。 |
| **9. OpenRouter** | [openrouter.ai](https://openrouter.ai/) | **免綁卡** | • 每日 20~50 次免費請求<br>• 標註 `:free` 模型完全免費 | 16+ 款標籤模型<br>DeepSeek R1 :free<br>Gemma 2 :free | **模型聚合中樞**，一次配置即可無縫切換數十種全球最新模型，並具備自動 Fallback 容錯路由。 |
| **10. SiliconFlow 國際站** | [cloud.siliconflow.com](https://cloud.siliconflow.com/) | **免綁卡** | • 註冊送免費額度<br>• 特定 7B 模型永久免費 | Qwen 2.5 7B/72B<br>DeepSeek V3/R1 | **開源模型支持極為即時**，對繁體中文與東亞語言理解極佳，API 響應非常穩定。 |
| **11. Mistral AI** | [console.mistral.ai](https://console.mistral.ai/) | **免綁卡** (需手機驗證) | • 免費 Experiment Tier<br>• 1 RPM / 依各模型限額 | Mistral Small<br>Codestral 22B | **歐洲頂尖開源勢力**，Codestral 在程式代碼生成與除錯表現優異，原生支援 80+ 種語言。 |

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

### 2.3 GitHub Models (微軟 Azure 支援)
- **官方網站**：[https://github.com/marketplace/models](https://github.com/marketplace/models)
- **申請資格**：任何 GitHub 帳號均可免費加入 Public Preview。
- **獲取 Key 步驟**：
  1. 在個人 GitHub Settings $\to$ Developer settings $\to$ Personal access tokens (Tokens classic) 產生一組具備基礎權限的 PAT。
  2. 將 PAT 作為 API Key 傳入。
- **OpenAI SDK 呼叫範例**：
  ```python
  from openai import OpenAI

  client = OpenAI(
      base_url="https://models.inference.ai.azure.com",
      api_key="ghp_..."  # 填入您的 GitHub Personal Access Token
  )

  response = client.chat.completions.create(
      model="gpt-4o",  # 或 "claude-3-5-sonnet", "meta-llama-3.3-70b-instruct"
      messages=[{"role": "user", "content": "請評估這篇研究的實驗設計與對照組設定是否嚴謹：..."}]
  )
  print(response.choices[0].message.content)
  ```

---

### 2.4 Cloudflare Workers AI
- **官方網站**：[https://dash.cloudflare.com/](https://dash.cloudflare.com/)
- **申請資格**：免費註冊 Cloudflare 帳號，無須輸入信用卡。
- **免費額度**：每日高達 **10,000 Neurons**（神經元運算額度，約等同數萬至十萬 Tokens）。
- **獲取 Key 步驟**：
  1. 進入 Cloudflare Dashboard $\to$ 右上角 **My Profile** $\to$ **API Tokens**。
  2. 點擊 **Create Token** $\to$ 使用範本 **Workers AI (Read)** $\to$ 建立金鑰。
  3. 取得您的 **Account ID**（於左側 Workers & Pages 總覽可見）。
- **OpenAI 相容端點**：
  ```python
  from openai import OpenAI

  ACCOUNT_ID = "your_cloudflare_account_id"
  API_TOKEN = "your_cloudflare_api_token"

  client = OpenAI(
      base_url=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1",
      api_key=API_TOKEN
  )

  response = client.chat.completions.create(
      model="@cf/meta/llama-3.3-70b-instruct",
      messages=[{"role": "user", "content": "請將以下英文論文摘要翻譯為學術繁體中文：..."}]
  )
  print(response.choices[0].message.content)
  ```

---

### 2.5 Hugging Face Serverless Inference API
- **官方網站**：[https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
- **申請資格**：免費註冊 Hugging Face 帳號。
- **獲取 Key 步驟**：
  1. 進入 Settings $\to$ Access Tokens。
  2. 建立新 Token（Role 選擇 `read` 即可）。
- **OpenAI SDK 呼叫範例**：
  ```python
  from openai import OpenAI

  client = OpenAI(
      base_url="https://api-inference.huggingface.co/v1",
      api_key="hf_..."
  )

  response = client.chat.completions.create(
      model="Qwen/Qwen2.5-72B-Instruct",
      messages=[{"role": "user", "content": "請從文本中萃取關鍵字：..."}]
  )
  print(response.choices[0].message.content)
  ```

---

### 2.6 NVIDIA NIM (API Catalog)
- **官方網站**：[https://build.nvidia.com/](https://build.nvidia.com/)
- **申請資格**：免費註冊 NVIDIA 開發者帳號（信箱驗證即可）。
- **免費點數與額度**：
  - 新用戶註冊後，帳戶自動贈送 **1,000 API Credits**。
  - 每次推論通常消耗 1 點左右，足夠完成數百篇文獻之深度問答與萃取。
- **OpenAI 相容端點**：
  - Base URL: `https://integrate.api.nvidia.com/v1`
  - 支援模型：`meta/llama-3.3-70b-instruct`、`deepseek-ai/deepseek-r1` 等。

---

### 2.7 SambaNova Cloud
- **官方網站**：[https://cloud.sambanova.ai/](https://cloud.sambanova.ai/)
- **申請資格**：開發者信箱免費註冊。
- **特色**：由專門為大型模型設計的 SN40L 晶片集群驅動。
- **可用模型**：`Meta-Llama-3.3-70B-Instruct`、甚至參數量高達 405B 的 `Meta-Llama-3.1-405B-Instruct`。
- **OpenAI 相容端點**：
  - Base URL: `https://api.sambanova.ai/v1`

---

### 2.8 Cerebras Inference
- **官方網站**：[https://cloud.cerebras.ai/](https://cloud.cerebras.ai/)
- **申請資格**：免費註冊。
- **特色**：目前全球推論輸出速度天花板（~2,000 tokens/sec）。對於需要處理數百篇文獻標題與摘要（TIAB Screening）的研究人員，原本需要跑半小時的萃取任務，在 Cerebras 上數十秒即可完成。
- **OpenAI 相容端點**：
  - Base URL: `https://api.cerebras.ai/v1`

---

### 2.9 OpenRouter
- **官方網站**：[https://openrouter.ai/](https://openrouter.ai/)
- **申請資格**：GitHub 或 Google 帳號直接登入。
- **使用秘訣**：
  - 搜尋模型時過濾 **Free** 標籤，模型 ID 後方帶有 `:free`（例如 `deepseek/deepseek-r1:free`、`meta-llama/llama-3.3-70b-instruct:free`）。
  - 無需儲值任何金額，即可每日免費調用 20~50 次。若未來稍微儲值 $1 美元，免費模型的每日頻率上限將會大幅放寬至數百次。
- **OpenAI 相容端點**：
  - Base URL: `https://openrouter.ai/api/v1`

---

### 2.10 SiliconFlow 國際站 (矽基流動)
- **官方網站**：[https://cloud.siliconflow.com/](https://cloud.siliconflow.com/)
- **申請資格**：信箱註冊驗證。
- **使用注意**：OpenGSA 專案使用國際站 `region=com`（端點為 `https://api.siliconflow.com/v1`），同一組金鑰請勿跨區試探。
- **永久免費模型**：包括 `Qwen/Qwen2.5-7B-Instruct`、`THUDM/glm-4-9b-chat` 等，適合一般常規文本分類、實體辨識（NER）與格式轉換任務。

---

### 2.11 Mistral AI (La Plateforme)
- **官方網站**：[https://console.mistral.ai/](https://console.mistral.ai/)
- **申請資格**：信箱註冊並通過手機 SMS 驗證碼檢查。
- **推薦模型**：`codestral-latest`（程式開發強項）、`mistral-small-latest`。
- **OpenAI 相容端點**：
  - Base URL: `https://api.mistral.ai/v1`

---

## 3. 學生與研究人員使用最佳實踐 (Best Practices)

### 3.1 零外洩原則：API Key 安全保管
1. **絕不寫死在程式碼中**：永遠將 Key 放置在專案根目錄的 `.env` 檔案中，並確保 `.gitignore` 包含 `.env`。
   ```bash
   # .env 範例
   GROQ_API_KEY="gsk_..."
   GEMINI_API_KEY="AIzaSy..."
   CF_ACCOUNT_ID="..."
   CF_API_TOKEN="..."
   ```
2. **在 GitHub Actions 中使用 Repository Secrets**：
   - 進入 GitHub Repo $\to$ Settings $\to$ Secrets and variables $\to$ Actions。
   - 新增金鑰（如 `OPENGSA_GROQ_API_KEY`），工作流程式碼以 `${{ secrets.OPENGSA_GROQ_API_KEY }}` 引用，絕不讓 Key 出現在 Git Commit 紀錄中。

### 3.2 避免 429 速率限制（Rate Limits）的因應技巧
- **指數退避機制（Exponential Backoff）**：遭遇 HTTP 429（Too Many Requests）時，切勿連續高頻重試，應等待 $2^n$ 秒（例如 2s、4s、8s）再發起重試。
- **多 Provider 動態備援池（Failover Pool）**：
  - 參考 OpenGSA 專案實作之 `ProviderFailoverPool` 架構：優先調用速度極快之 Groq；若遇 429 或暫態中斷，自動降級切換至 Google Gemini、Cloudflare 或 Cerebras，確保長時間自動化批次腳本不中斷。

### 3.3 結構化 JSON 輸出技巧
在進行文獻資訊萃取時，請在 System Prompt 中明確要求輸出標準 JSON，並啟用各供應商的 `response_format={"type": "json_object"}`，以確保後續 Pandas / Python 能夠直接解析：
```python
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": "You are a research assistant. Output JSON only."},
        {"role": "user", "content": "從以下文本萃取獎助金額與申請期限：..."}
    ]
)
```

---

## 4. 結語與專案宣告

OpenGSA 專案秉持「**把時間留給研究，把獎助檢索交給 OpenGSA**」之理念，所有自動化管線在正式排程中均恪遵安全合規邊界（排程預設關閉推論 `model_mode=off`，僅在手動審查與合成基準中進行最小量驗證）。

希望本份指南能協助臺灣大專院校與碩博士研究生，在面對龐大的文獻閱讀與研究課題時，充分善用頂尖全球雲端運算資源，節省寶貴開銷，專注於真正的創新研究！
