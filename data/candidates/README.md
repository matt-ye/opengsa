# 待覆核候選快照

`ai-tools-115.json`為2026-10-30從兩個官方公開HTML正文取得的具名候選，採candidate Schema；不是網站正式總表。兩筆都是pending、passed_with_gaps、promotion_ready=false；不得把檔案存在視為完成獨立人工覆核。

| 候選 | 本次萃取 | 未解決事項 |
|---|---|---|
| 臺北市青年AI工具補助 | 一般4,000元／低收及中低收加額8,000元；支出期間8/1–10/31；年度最晚收件11/10；書面且以送達為準 | 個人條件最後達成日、相對一個月期限、經費餘額；郵寄／親送尚無本次正文證據；申請起日未知，不拿支出起日代填 |
| 新竹市AI領航數位工具補助 | 一般50%上限3,000元；特定及文化語言保存者各90%上限6,000元；購買期間4/2–10/31；受理期間4/2–11/30；線上、親簽上傳 | 購買日、月費／年費相對期限、經費餘額及年齡基準；未明示免紙本遞交者保留unknown；8/14電子申辦調整不當成首次開放日 |

數字與年度從正文解析，不依目前年份填入。每份來源revision的各分支證據摘錄合計上限120字；本次臺北113字、新竹110字，摘錄不改寫，空白依既有解析器正規化。其餘證據以雜湊及定位保留，原HTML與PDF不入庫。這不是全文快照；後續獨立覆核須在來源允許範圍重新取得完整正文，來源版本不同則重新掃描。

`application_method.mode`對應handoff所稱delivery_method；`handwritten_signature`對應must_be_signed的三態／不適用判斷；`paper_delivery`另外表示是否須實際遞交紙本。沿用既有契約，沒有另外維護不同步的application_process副本。`expense_period`只記可認列支出期間，與學生收件步驟分開。

`check_data.py`額外檢查本目錄候選bundle的Schema、來源URL、摘錄預算與待審邊界；不在CI重新連外，也不以短證據重新宣告完整原文核驗通過。合成測試放tests，不放本目錄；正式人工處置仍在data/scan-reviews.json，目前沒有本批核准紀錄。

官方依據：[臺北市計畫](https://youth.gov.taipei/services/05eb79e5-46b5-41e5-b1fd-0519d782b04a/0ecc1836-dd0d-4085-a34f-003609f00796)、[新竹市申辦說明](https://dgservice.hccg.gov.tw/serviceNotice.do?id=1323&rule=guest)。操作與驗收見[候選推進紀錄](../../docs/AI-TOOLS-CANDIDATES.md)。
