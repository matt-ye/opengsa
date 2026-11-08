# 剩餘手寫卡的處理決定（2026-11-08）

研究批次合併後還剩 61 張手寫卡。使用者逐組決定如下。

| 組 | 張數 | 狀況 | 決定 |
|---|---|---|---|
| 各校研究生合成卡（university-scholarships） | 19 | 網址幾乎都是學務處首頁，標題把多個方案合成一個名稱。部分名稱（中央「松果」、淡江「熊貓講座」、逢甲「築夢」、輔仁「耕莘」等）在流程讀到的頁面裡都沒出現，是否真有這些方案未確認 | 下架（本 PR） |
| 重複卡 | 2 | Azure for Students 和農業部農漁民子女就學金，在 topology-discovered 和其他類別各有一張 | 撤下 topology-discovered 那張（本 PR） |
| 學生軟體與生活優惠（student-perks） | 13 | 官方頁讀得到，但萃取流程是為獎學金設計的，抽不出產品頁的優惠內容 | 保留，網站與 RSS 標示「萃取方式待補」（本 PR） |
| 急難救助（emergency-relief-aid） | 12 | 網址多半是首頁 | 改成方案頁網址後重跑流程（另一個 PR） |
| 指到具體方案的（企業、中小學、醫學、電腦學會） | 15 | 有的網址是首頁，有的是方案頁，都沒抽出候選 | 改網址後重跑流程（另一個 PR） |

## 先前「待人工判斷」的 5 張

研究批次時，成大急難、成大優秀研究生、鴻海高中職組、長庚耕心、元智有庠這 5 張的網址也產生了新候選。逐一比對後，新候選都是同一個網站上的其他方案（例如成大首頁抽到的是葉文冠教授紀念獎學金），不能拿來取代。其中成大優秀研究生、長庚、元智屬於上面的合成卡，已下架；成大急難和鴻海高中職組要改網址重跑。

## 撤下的卡

university-scholarships：cand-univ-nthu-0001a12b、cand-univ-nycu-0002a12b、cand-univ-ncku-0003a12b、cand-univ-nccu-0004a12b、cand-univ-ncu-0005a12b、cand-univ-nsysu-0006a12b、cand-univ-nchu-0007a12b、cand-univ-ntnu-0009a12b、cand-univ-ntust-000ba12b、cand-univ-ntut-000ca12b、cand-univ-cgu-000da12b、cand-univ-tmu-000ea12b、cand-univ-cmu-0010a12b、cand-univ-fju-0011a12b、cand-univ-scu-0012a12b、cand-univ-tku-0013a12b、cand-univ-fcu-0014a12b、cand-univ-yzu-0015a12b、cand-univ-ndhu-0018a12b。

topology-discovered-scholarships：cand-perk-azure-for-students、cand-gov-moa-farmers-aid。

卡片內容留在 git 歷史。沒有其他卡在用的來源，排程掃描會停掉。

## 順手修的問題

撤卡時，沒有其他卡在用的來源只會被設成停用。手寫卡的來源設定（標題、選擇器）沒驗證過：卡撤掉後，提交流程不再把它當成手寫來源排除；有人提交同一個網址時，流程會重新啟用這份設定，把學校首頁命名成那個方案。現在撤手寫卡時，它的來源另外標成 `automation: not_enabled`，提交流程會排除這類來源。
