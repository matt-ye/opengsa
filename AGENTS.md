# AGENTS.md · 開發規則

> 給 Claude Code、Codex 與人類協作者的規則；`CLAUDE.md` 只負責引用本檔。
> 開工前先讀 [`README.md`](README.md)（專案介紹與資料規模）和 [`docs/TODO.md`](docs/TODO.md)（目前的規劃與已定案的決定）。
> 2026-11-07 以前的逐日核可紀錄在 [`docs/DECISION-LOG.md`](docs/DECISION-LOG.md)，只供查考；跟本檔衝突時以本檔為準。

## 1. 資料不可編造

- **卡片只能由萃取流程產生。** 不得手寫或用腳本寫定卡片內容、雜湊與 `field_evidence`。CI 用 `scripts/check_provenance.py` 把關，手寫卡基準清單只減不增。
- **不猜。** 來源、資格、金額、期限讀不到就標「未確認」或導向來源網站。不從往年資料、模型推論或其他卡片補值。
- 撤卡用 `scripts/retire_candidates.py`，不要手動刪卡片檔。
- 新卡與更新都經過提案（`propose_radar_update.py`）和資料 PR。不直接改 `data/candidates/`。

## 2. 來源、隱私與密鑰

- 遵守 robots；被擋、要登入、受限的來源不繞過、不換身分重試。
- 來源原文只放記憶體，不進 repo、PR、Issue 或 log；評測快取只放 `work/`。
- 標成 `hash_only` 的來源，原文一律不送到外部模型。
- 真實個資、登入後內容、私人附件、本機路徑不得入庫。測試用的合成資料要明示。
- API key 只放 GitHub Secrets 或本機環境變數，不進 repo、PR、Issue；輸出與 log 不得帶出 key。
- 公開署名只用 Matt Ye。

## 3. 模型

- 排程掃描不呼叫模型。要在排程或資料流程裡用模型，先取得使用者同意。
- 只用確認免費的供應商（`data/model-providers.json` 的 `inference_policy` 為 `user_reported_free` 或 `zero_price_free_only`）。
- **型號以 `status/model-catalog.json` 為準**，不憑記憶填。打 API 發現型號不對時，手動執行一次 `model-catalog` workflow 更新清單。
- 模型的輸出一定要過規則驗證（出處要對得上原文），沒過就丟掉。規劃見 [`docs/AGENTIC-EXTRACTION-ARCHITECTURE.md`](docs/AGENTIC-EXTRACTION-ARCHITECTURE.md)。
- 遇到 429 不要連續重試。SiliconFlow 用國際站（`cloud.siliconflow.com`，region=`com`），同一把 key 不跨區試探。

## 4. 合併、上架與排程

- **只有使用者能決定合併。** 合併資料 PR 就是上架。不開自動合併；Actions 不自己開 PR。
- 資料 PR 每週彙整一次（週一）；收件匣 Issue「待審資料收件匣」負責通知。
- 改動以下項目前先跟使用者確認：workflow 的權限與排程、`data/scan-sources.json` 的上限與 `allowed_hosts`、模型開關、`AGENTS.md`。
- 不建立超出目前需求的服務、資料庫或推薦功能。

## 5. Git

- 不直接 commit 到 `main`：開分支 → 開 PR → 使用者同意後合併。分支名 `<類型>/<主題>`，例如 `feat/weekly-digest`、`fix/chain-test`、`docs/agents-cleanup`。
- 合併用 `gh pr merge <n> --merge`，不 squash、不 rebase。
- `main` 有更新時，把 `main` merge 進自己的分支；已 push 的分支不要 rebase。
- 不要 `git push --force`、不要 `git reset --hard origin/main`。
- 同時跑多個任務時，用 `git worktree` 各開一個資料夾。
- 一個 PR 做一件事；疊在別的 PR 上時，合併前先把 base 改成 `main`，CI 才會跑。

## 6. PR 與 commit

- PR 說明照 [`.github/pull_request_template.md`](.github/pull_request_template.md) 寫：先說這個 PR 做什麼、為什麼，再列變更、驗證、影響。
- **不要貼使用者的原話或原始指令**；整理成「計畫」與「實際做了什麼」再寫。
- **沒驗證過就寫「未驗證」**，不要寫成已完成。
- commit message 用繁體中文：第一行寫做了什麼（可加 `feat:`、`fix:`、`docs:` 等類型），內文寫為什麼。一個 commit 做一件事。

## 7. 提交前要跑的檢查

```bash
python -m unittest discover -s tests
node --test tests/prototype.test.cjs
python scripts/check_data.py
python scripts/check_provenance.py
python scripts/scan_sources.py --check-config
python scripts/readme_counts.py
```

- 改萃取規則前後各跑一次 `python scripts/evaluate_pages.py`（加 `--offline` 只用快取），不能有退步。
- README 的資料規模區塊由 `scripts/readme_counts.py --write` 產生，不手改。
- 網站新增網址參數前，要先到 GA4 後台的「遮蓋資料」加鍵，否則搜尋條件會原樣送出（見 `docs/DEPLOYMENT.md`）。
