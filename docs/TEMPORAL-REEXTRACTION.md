# 時間重萃與逐項呈現檢核

2026-11-03，本輪接續PR43。來源仍為64筆待審摘要／58組暫定方案，沒有擴大485個原始URL的掃描範圍。成果另開PR，不自動合併／部署。候選資格、正式pilot、真人台帳、新增來源排程與模型設定未改。

## 結果與可用範圍

- 已逐筆產生[64項處置與甘特形式](audits/temporal-reextraction-2026-11-03.md)，另有[機器可讀報告](audits/temporal-reextraction-2026-11-03.json)。
- 最新觀察60項成功重讀並重萃，4項保留原因：2項須先重做存取審查、1項重新導向超出台帳允許網址、1項重試時微批預算耗盡。最後一項本輪初讀曾成功；不能把「最新重試未完成」說成從未讀到，也不能把它算最新重萃成功。
- 最終投影32項已有可分型的時點／規則／制度參考，32項仍待補。分類數不等於正確率、目前可申請數或完整資訊鏈數。
- 分型：固定申請期3、單一學生截止1、個人條件＋年度上限2、活動相對3、週期規則3、文字規則5、單位／行政時點10、跨年度需分開2、制度參考3、待補32。單位範例與歷史底帶是另一層，不與這組數量相加。
- 新讀文學院8份公告PDF，保留2026年9／10月的明確截止時點。段落尚未充分辨識學生／院系收件角色，先列為單位時點，不畫成學生申請長條。每條規則可直接前往其PDF證據。
- 不為了提高完整率補猜：公告日、會議／購買／給付期間不冒充申請起訖；不同年度時點不合成單一區間；學年度標題與月日不自行拼成年月日。

## 這輪修正

1. HTML表格同列、申請時間標籤後的相鄰節點、同頁短PDF續行，先作有邊界的文字準備；不跨頁、表格列或新標題拼接。新增共用`labelled_date_clause`，一般候選萃取器也使用，版本升至`extractor-1.8.0`。
2. 日期必須緊鄰申請／收件標籤，不能任抓該段第一個日期。測試覆蓋「前方公告日＋無年份截止」「會議期間＋月日截止」「購買／給付期間」等反例。最後再次查核並撤回了較寬鬆規則誤抓的公告日／活動日期。
3. 缺年份的月日保留文字規則，不生成ISO日期。明示全年／常態受理、依單位另訂與隨到隨審有不同類型；**支援這些類型不代表本批已確認有全年受理項目**。
4. 同頁不同年度而尚未能分梯次的資料，列「多階段時間規則」，顯示原年份與待核原因，抑制單一申請長條及自動座標。真正單一跨年申請窗口不被這個防護誤擋。
5. 三頁共用時間投影：學生起訖可畫長條、學生截止可畫標記、行政日期畫單位標記、相對／週期規則用規則卡；缺資訊時顯示原因及來源入口。每項時間規則顯示檢核日期。重萃不自動宣稱目前受理中。

## 儲存、版本及來源邊界

[`data/temporal-observations.json`](../data/temporal-observations.json)是獨立、仍待審的時間觀察表：以candidate ID作索引，綁定完整candidate fingerprint、母頁URL與原文hash；規則另有revision及定位。附件有自己的URL／hash／revision，並綁母頁hash。不是把舊候選資格的證據換成新來源版本。

原候選或來源版本／欄位內容改變時，fingerprint不符就不使用這份觀察；不將資料默默重新綁定。母頁及附件來源混用、版本不符或候選來源檢核失敗，均不得增加可見事實。多個不同截止不採最早／最晚值代替完整程序。

原文全在記憶體，沒有PDF／HTML副本與模型外送。台帳僅存正規化時間、定位、hash、診斷欄位與請求歷程。候選來源屬`hash_only`仍不儲存引文。下載方式、資格、給付、相容性等欄位沒有因本輪時間重萃而核准。

本輪累計200HTTP／16微批／模型0，包括robots、重新導向、失敗及規則修正後的重查。原先160上限，發現母頁只有附件入口後擴為200，沿原計數累加；微批仍最多8個母頁／20HTTP／180秒，同站至少3秒。4項保留並非全都是robots禁止；生輔組人工限制沒有解除。未啟用模型、付費端點或新排程。

## 重現及日後操作

以下命令只產生`work/`待審產物；請保留`--previous`完整累計，不能在同輪省略它來重置請求數。

```powershell
python scripts/temporal_reextract.py --source-id discovery-r193 --output work/time-batch-01
python scripts/temporal_reextract.py --source-id discovery-r194 --previous work/time-batch-01/temporal-observations.json --output work/time-batch-02
python scripts/temporal_reextract.py --follow-attachments --source-id discovery-r193 --previous work/time-batch-02/temporal-observations.json --output work/time-batch-03
```

母頁先重讀，只追同一公告直接連結的同站公告／辦法PDF，每來源至多一份；不追申請表、名單、表單或任意站外連結，不遞迴下載。不支持或受阻就保留處置原因。多分支來源不套用單一附件的共同日期。

`--retry-unclassified`僅供解析器修正後重跑尚未分型項目一次；`--recheck`須明列來源ID供問題復核，兩者都保留歷程及累計額度。既有本輪台帳已達200，不能再用它發出請求；下一輪應另記範圍與預算。本輪多次規則修正屬校準，沒有宣稱為盲測或模型評測。

審查後才由資料PR納入時間觀察JSON；scanner／Actions沒有自動覆寫這份檔案。正常候選掃描已共用更嚴格的日期標籤規則，但**附件時間重萃目前仍是手動CLI**；不把此功能寫成已排程全自動補鏈。

```powershell
python scripts/audit_time_policies.py
python scripts/check_data.py
node --test tests/prototype.test.cjs
python -m unittest discover -s tests -v
python scripts/build_site.py _site
python scripts/build_review_workspace.py --output work/review-time
```

`audit_time_policies.py`只讀取已存結構化資料，零來源GET；可以低成本重建64項清單。`check_data.py`增加候選綁定、請求台帳與時間來源證據檢查。網站建置測試以真正輸出資料跑64項前端投影、日期幾何、跨年度防護及受理篩選。

## 下一批有價值的工作

1. 先處理32筆待補及2筆跨年度：按附件／多分支頁／工具驗證入口／角色不明分流，逐批開新請求台帳；不整批反覆重讀已知只有附件的母頁。
2. 對8份PDF補申請人、收件人及時間角色的同段／表格語意，再決定哪些是學生截止，不能僅因找到了日期就升級。
3. 經隔離來源驗證後，才將手動附件重萃串入既有待審artifact流程；保留HTTP與快取成本、robots與來源版本防護。
4. 導覽仍由未來圓形`?`主動啟動；本輪不加導覽、不開索引或處理mattye.dev部署。
