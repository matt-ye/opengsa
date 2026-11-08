# 資料管理決策紀錄

記錄流程狀態與資料要放在哪裡、為什麼這樣選，以及日後要改版時從哪裡開始。新決策加在最上面；舊決策被取代時保留原文，並註明被哪一筆取代。

## 2026-11-08：流程狀態表放 repo，CSV 與 JSON 並行測試

**狀態：** 已決定，尚未實作。等審查報告第 3、4、5、10–12 項修完才動工。

### 問題

使用者想要一張隨 GitHub Actions 更新的表格，看得到每個來源的抓取、萃取、審核與上架狀態，並問這應該放 repo 還是用資料庫管理。規模約數百到一千多個來源；掃描排程約每週六次。

### 決定

1. 狀態放 repo，由 Action 更新，現階段不用資料庫。
2. 同時產生兩種格式，由同一份資料寫出：
   - **CSV：** 一個來源一行。GitHub 會把 CSV 顯示成表格，diff 也看得出哪個來源變了。
   - **JSON：** 可能較適合多來源與長資訊鏈的文件。CSV 一行放不下巢狀結構時，就要靠它。
3. 並行測試約一個月，比較 diff 可讀性、檔案大小、資訊鏈能否表達、GitHub 能否顯示，再決定留一種或兩種都留。

使用者原話：「可以做，用 CSV，等這輪修完再動工。json 可能是為了多來源、資訊鍊長的文件的設計，可兩個併行測試看看效果。」

### 考慮過的方案

| 方案 | 適合 | 不適合 | 結論 |
|---|---|---|---|
| repo 內狀態檔 | 累積每個來源的最新狀態，有歷史可查 | 需要即時跨來源查詢或多方同時寫入 | **採用** |
| Action 的 job summary | 看單次執行的報告 | 不能累積，也不能事後修改；每個 step 上限 1 MiB | 可搭配使用，不當正本 |
| Artifact | 跨 run 暫存 | 有保存期限，上傳後不可修改 | 不採用 |
| 專用 data 分支 | 隔離 commit 噪音，避開 PR 衝突 | 要多管一條分支和 checkout 步驟 | 暫不採用；衝突變多時改用 |
| Issue 或 Projects 看板 | 異常才開單（Upptime 的做法） | 上千列的全表 | 不當全表；之後可用於異常通知 |
| SQLite 搭配 Datasette | 事後查詢 commit 歷史（git-history） | 屬於分析工具，不是寫入端 | 暫不採用；需要分析歷史時再加 |
| Cloudflare D1 等託管資料庫 | 即時查詢、多方寫入 | 要多維護 Worker 和 token | 暫不採用 |

### 實作時要遵守

- **不放執行時間。** 檔案裡有時間戳就會每次都產生 commit。內容有變才 commit，單次執行的資訊放 job summary。
- **只讓 bot 寫這些檔案。** 人和 PR 都不動它，以降低和 PR 分支衝突的機率。這點是推論，還沒有實際驗證。
- **權限與並行。** job 設 `permissions: contents: write`，並沿用 concurrency group `public-source-scan`。
- **不會循環，也不會部署。** 用 `GITHUB_TOKEN` push 不會建立新的 workflow run（`workflow_dispatch` 和 `repository_dispatch` 例外）。如果日後網站要顯示這張表，部署要另外處理。

### 何時重新考慮

沒有找到有依據的數字門檻，**換資料庫的量化條件未確認**。比較合理的訊號是需求改變：

- 需要跨來源即時查詢，例如網站上要讓人查狀態。
- 需要多方同時寫入，或 `concurrency` 排隊已影響排程。
- 狀態檔和 PR 的衝突多到影響合併。這時先改用專用 data 分支，不必直接上資料庫。
- 接近下面的硬限制。

目前已確認的硬限制：

| 限制 | 數值 |
|---|---|
| GitHub 單檔 | 50 MiB 警告，100 MiB 封鎖 |
| GitHub repo 大小 | 建議 1 GB 以下，強烈建議不超過 5 GB |
| Cloudflare D1 單一資料庫 | Free 500 MB，Paid 10 GB |
| GitHub 顯示 CSV 表格的檔案上限 | [512 KB](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files)，超過就不顯示成表格 |

512 KB 是 CSV 方案最先碰到的限制：以 1000 個來源計算，每行平均要低於約 500 位元組。網址多或欄位長時可能超過，所以 CSV 只放短欄位，詳細內容放 JSON。實際大小要等實作後再量。

### 要改版時從哪裡開始

1. 先看並行測試的比較結果，它們會寫在本文件。
2. 看狀態檔的 commit 數和檔案大小，判斷問題是噪音、衝突還是查詢需求。
3. 衝突或噪音問題先試專用 data 分支；查詢需求才考慮資料庫。
4. 狀態檔由掃描 workflow（`.github/workflows/scan-sources.yml`）更新，產生位置以實作 PR 為準，實作後要回填到這裡。

### 案例與查核範圍

- **已確認：** Simon Willison 的 git scraping（排程抓取、有變才 commit）；Upptime（Action 把回應時間 commit 進 repo，事件開 Issue）。
- **未確認：** Open States 與 City Scrapers 的 README 沒寫如何追蹤狀態；資料品質工具的做法沒有查。

### 來源

- [Git scraping](https://simonwillison.net/2020/Oct/9/git-scraping/)
- [Upptime](https://github.com/upptime/upptime)
- [git-history](https://github.com/simonw/git-history)
- [GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token)
- [Workflow concurrency](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#concurrency)
- [Job summary](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#adding-a-job-summary)
- [Workflow 資料儲存](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/storing-and-sharing-data-from-a-workflow)
- [GitHub 大型檔案](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [D1 限制](https://developers.cloudflare.com/d1/platform/limits/)

## 2026-11-08：卡片上架、駁回與核准

**狀態：** 已決定，尚未實作；由審查報告第 11、12 項處理。

使用者原話：

> 未審的卡可以直接上沒關係，重點是快，列出來源，不確定的部分 就直接導向來源網站
> 駁回的卡可以下架，進一步確認問題來源，可能可幫助改寫優化粹取腳本
> 目前由我核准提交，不過要怎麼讓這件事更方便是未來要規劃的

- **未審的卡：** 可以上網站，要列出來源；不確定的欄位不猜，直接導向來源網站。
- **駁回的卡：** 下架，並記錄原因與問題來源，之後用來改進萃取腳本。
- **核准者：** 目前只有使用者本人。讓核准更方便留待未來規劃。
- **上線方式（2026-11-08 決定）：** 仍由使用者合併資料 PR 才上線，不開自動合併，也不讓 Actions 自己開 PR。合併時卡片可以還沒逐張審過。為了讓這件事快一點，每輪有新提案時 bot 會在「待審資料收件匣」Issue 留言推播，使用者點連結開 PR、等 CI、合併。

## 2026-11-08：掃描請求上限暫時調高到 50

**狀態：** 已決定，尚未實作；由審查報告第 5 項處理。寫下本紀錄時，設定值仍是 20。

`data/scan-sources.json` 的 `max_requests` 是每輪對公開網站的請求上限，不是模型 API 額度，所以多幾把 API 也不會增加。原本是 20，`scripts/scan_sources.py` 的驗證也擋在 20 以內。使用者原話：「可以暫時調高至50」。

同網域間隔與 robots 規則不變。11-07 的排程失敗是失敗來源吃光 20 次請求，所以調高額度的同時，仍要修「失敗來源不能吃光額度」。
