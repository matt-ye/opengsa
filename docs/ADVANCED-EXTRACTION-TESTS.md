# 萃取進階測試與來源重驗

2026-10-31，接續 PR #27 的文件準備整合。範圍維持既有13個來源profile、17份文件、19筆候選；沒有擴張來源、人工核准或發布。

## 找到並修正

| 問題 | 修正與驗證 |
|---|---|
| 行內標籤拆散金額、否定及日期 | 依段落、清單、儲存格與br切段，接回行內文字；span／strong／em／a變體得到相同句子，不自行插空白 |
| 相同內容的表格／資料列定位碰撞 | 依DOM物件身分定位；兩張相同表格各兩列仍有四個位置 |
| 遠學兩種補助共用的擇一限制遺失 | 保留明確同時指涉兩分支的條款；四種連接詞均保留限制，配合補助專屬金額不混入一般補助 |
| 同長度陣列內已知金額變unknown未攔截 | 遞迴檢查列項，不只比較長度；依序保守比對，重排造成疑義交人工確認 |
| 局部重萃保留舊受理狀態 | 程序、時程與N/A適用性共同納入計畫，依合併結果及原as_of重算 |
| 隱私過濾移掉限制，模型仍可能自稱完整 | 正文或表格脈絡遭過濾即延期，只回報unit ID；純聯絡段也採保守延期，不放寬原過濾邊界 |
| 模型非正常結束卻接受有效JSON | 只接受finish_reason=stop；tool_calls、未知、缺值、length拒絕，不存為成功快取 |
| 未明示共用context／錯誤審核日期仍放行 | shared_context須為布林，reviewed須為true及日期須有效；缺正確計數器仍延期 |
| 縮短句尾未重新計數 | 切點再用同一counter量測，不假設Token數隨字數單調增加 |

版本為scanner-2、document-ir-2、extractor-1.4.1、prompt-1.2.1。來源revision、準備雜湊或normalizer版本不合即要求完整重掃；舊計畫與核准不能沿用。本輪完整重掃後才更新待審快照。

## 驗證範圍

新增`tests/test_extraction_adversarial.py`共15項測試，除上表外涵蓋：

- br、巢狀清單、註解的順序與不重複輸出。
- 固定亂數種子的中文、emoji、組合字元與三種預算；分段可還原全部字元，位元組與整包預算均通過。
- 候選、欄位範圍或Prompt改變使快取失效；相同任務才可命中。
- 來源只變章節脈絡或normalizer版本仍需重新準備。
- 第一段成功、第二段429時整項延期，不回傳部分聲稱。

模型及計數器都是明示的合成替身，不是模型準確率、真實Token數或provider比較。環境入口尚未接上已查核能力與相容tokenizer，本輪沒有真實推論；下一步才以人工標準答案做小量模型評測。

## 實際來源

透過正式scan、受限Fetcher、萃取與獨立檢核入口分六批掃描，每批最多7次HTTP。沿用每輪20次、180秒、每站至少3秒、最多5份變更文件限制。robots禁止附件另列拒絕，不算讀取成功。

- 17份已允許文件重新準備為1,056單位；19筆仍pending。
- 維持8通過／11有缺漏，0錯誤；對照前版五組欄位，修正遠學後無已知欄位退步。
- 全批32次HTTP；診斷2次、修正追驗2次、給付欄位CLI重萃2次，本輪合計38次，並未放大單次預算。
- 遠學指定給付重萃為replayed_pending_review；原始HTML／PDF只留記憶體。
- 模型呼叫0次、人工核准0筆；正式pilot仍10筆，真人台帳仍空。通過不代表全部欄位經人類核實。

[機器可讀驗收](../data/audits/advanced-extraction-2026-10-31.json)保留版本、批次請求、前後候選指紋及文件manifest雜湊／計數；完整安全manifest是本機產物，避免repo每輪重複大量逐單位metadata。

## 重跑

```powershell
python -m unittest tests.test_extraction_adversarial -v
python -m unittest discover -s tests -v
node --test tests/prototype.test.cjs
python scripts/check_data.py
python scripts/scan_sources.py --check-config
python scripts/build_site.py _site
python scripts/build_review_workspace.py --candidates data/candidates/source-review.json --output work/advanced-review-new

# 明確 --refresh 才連外，輸出仍待審
python scripts/prepare_candidates.py --source-id ntu-yuanxue --group benefit --refresh --output-dir work/advanced-benefit-new
```

全套140項Python、38項Node、資料／來源設定及公開網站與審查工作台建置通過。瀏覽器互動驗收仍暫緩，沒有宣稱完成畫面檢查。PDF複雜版面／OCR、登入與禁止來源、真實模型計數器仍是既有界線。
