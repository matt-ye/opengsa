# GitHub Pages公開預覽

2026-11-01雷達版建置改讀19筆候選快照作可讀摘要，預設文件檢視，另可彙整13組方案；不把原候選標成人工核准。正式pilot與真人台帳不變，舊文「僅10筆來源草稿／合成預設」為歷史階段。未知與Issue回報規則見[RADAR-VIEW.md](RADAR-VIEW.md)。本版仍需PR合併與main部署後才生效。

2026-10-29使用者核可：PR #1合併規劃與原型，PR #2上架公開預覽供分享回饋。目的網址為 https://matt-ye.github.io/opengsa/ ，不修改個人首頁或DNS。正式服務及資料覆核門檻仍依[目前計畫](PLAN.md)。

## 發布內容

由`scripts/build_site.py`重用離線匯出器，只產生：

- `index.html`：內嵌程式與資料快照，清楚標示公開預覽、合成示範及待覆核草稿。
- `assets/opengsa-social-preview.jpg`：已核可的專案縮圖，供Open Graph分享使用。
- `.nojekyll`：靜態成品標記。

不發布repo目錄、私人資產、PDF、測試樣本或本機工具。輸出目錄若非空會停止，避免把前次留下的其他檔案一起發布；重建請選新的空目錄或先確認舊成品後清理。

```powershell
python -m pip install -r requirements-dev.txt
python scripts/check_data.py
python scripts/scan_sources.py --check-config
python -m unittest discover -s tests -v
node --test tests/prototype.test.cjs
python scripts/build_site.py dist/site
python -m http.server 8771 --bind 127.0.0.1 --directory dist/site
```

瀏覽 http://127.0.0.1:8771/ 。Python 3.10以上、Node內建test runner；CI固定Python 3.13／Node 24。建置與測試依requirements-dev.txt安裝；網站無新增框架或外部字型。

## 工作流程

`.github/workflows/pages.yml`在PR中只執行資料檢查、全部Python測試、Node測試及建置；來源掃描測試全用合成離線資料，不部署PR或取用部署權限。推送main或在main手動執行時，檢查通過才上傳`dist/site`並由另一個job部署。

部署job採GitHub Pages官方OIDC流程，只取得`pages:write`與`id-token:write`；不需新增私人API key或PAT。Action固定完整commit SHA，checkout不留存憑證，部署使用github-pages環境並避免同時發布。

首次將repo的Pages來源設為GitHub Actions。官方依據：[自訂Pages工作流程](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。這是網站建置及發布流程；pages.yml沒有schedule，不抓取獎學金來源。另核可的[scan-sources.yml](SCANNER.md)獨立低頻掃描，排程不呼叫模型；另提供受成本限制的手動模型／provider audit，不建立D1或送出訂閱通知。

## 分享與回饋

頁首與頁尾連到GitHub公開Issue回饋表，需GitHub帳號；沒有匿名回饋資料庫。提供操作、版面、公開來源更正與功能建議分類，提醒勿提交個資、私人申訴或未遮蔽附件。平台不自動建立Issue，也不代學生送申請。

分享縮圖使用專案圖，Open Graph URL固定公開預覽位置，不用個人照片。預覽加上noindex／nofollow，暫不主動進搜尋索引；這不是存取控制，任何知道網址的人都能瀏覽及分享。

個人條件、勾選、待辦與會議輸入只留本次瀏覽記憶體，重整後重設；沒有分析追蹤程式。GitHub Pages託管仍可能保留連線紀錄，頁尾連結[GitHub隱私聲明](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)。

## 驗收與回復

- 檢查及建置成功，部署顯示成功後，實際網址須回應200並能操作四分頁、篩選、甘特圖及研討會試算。
- 分享圖片可讀，回饋表及原始碼連結正確；手機不產生整頁橫向溢出。
- 不能把來源草稿、事件基準估算或合成示範呈現成已核定資料。
- 發布失敗保留GitHub先前成功版本；回復可revert有問題的main commit，通過檢查後重新部署。停止公開則停用repo的Pages，不影響個人首頁。
- 本次發布不等於20筆正式資料、至少5筆全國方案及5筆仍受理機會的正式服務驗收。
