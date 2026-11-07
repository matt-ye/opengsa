# 合成測試與歷史反例

`source-intake/`是`tests/test_source_intake_e2e.py`的假頁與假傳輸，機構與網域都是虛構的，只在測試的repo副本內使用，不進正式資料。

synthetic-scan-reviews.json保留舊版產生的合成處置紀錄，revision雜湊與覆核者均不代表真實人工核准。此目錄不供scanner載入，也不發布到網站。正式處置台帳為data/scan-reviews.json，目前reviews為空；新的測試以SYNTH角色與合成正文驗證核准門檻。
