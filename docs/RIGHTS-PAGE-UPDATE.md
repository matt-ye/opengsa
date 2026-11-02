# 權益與求助：主題分頁、給付表與連結查核

2026-11-02使用者核可實作；本變更供PR覆核，不自行合併或部署。承接PR40的頁首回報按鈕，採堆疊PR，先以PR40分支為base；PR40合併後再改回main。正式pilot10筆、64筆pending候選、真人覆核台帳、新來源排程與模型設定均不改；PR34不動。

## 內容放置

| 次分頁 | 內容 |
|---|---|
| 重點總覽（預設） | 三張跳轉摘要卡、第一頁／研討會入口、三份GitHub完整文件，不堆疊所有長表 |
| 聘任與給付 | 五類查核路徑、七列制度給付比較、國科會分支詳細表、校務基金獎勵金及工讀入口 |
| 法規與保障 | 法源層級、工作型態矩陣及官方保障連結 |
| 求助與自測 | 現有從屬性整理工具及五類可平行選擇的求助窗口 |

五類聘任路徑以臺大為例，學院／系所仍待逐案查核；EMITA可與教務處等核定管道重疊。給付明分原則區間、方案標準、計畫最低要求、增核、支給上限與法定最低工資；不以博士候選人身分推定應領上限或專任標準。完整方案與榮譽種子仍留在ACADEMIC-CAREER-AND-ASSISTANTSHIPS.md；本次未逐項確認該文件§1–3與§5。

## 頁內導向契約

四個主要功能頁籤維持原樣，第四頁用原生主題按鈕切換。所有頁內目標ID唯一且存在；跨主題自動顯示目標群組，連到收合details時先展開。首次載入具體fragment也走相同解析，不錯回第一頁。路由切換採立即捲動，避免平滑捲動尚未結束時連續點擊導向錯位；標題留固定導覽高度。

本輪驗證：Python unittest 221項、Node prototype 49項通過；check_data、scan_sources --check-config、公開網站及審查預覽建置通過。Chrome 390px／320px無整頁橫向溢出，手機四主題為2×2，寬表格區域水平捲動；直接載入給付、自測與研討會fragment，以及自測勾選／重設均已測試。

第四頁14個頁內連結均列入Chrome逐一點測；網站建置測試另驗全部靜態fragment及GitHub文件路徑，CI不會連線外站。外站狀態僅代表本次查核，不保證永久可用；學校登入／robots政策與自動掃描範圍不因手動查看改變。

## 外部連結逐項紀錄

舊最低工資網址29025回傳410，改官方問答7121；未將失效連結當正常。EMITA改用官方files附件。下列GitHub文件均用Contents API確認main已有檔案；頁面上標明規劃資料與待查內容。

| 連結 | 本輪結果／界線 |
|---|---|
| [學術階段、出國補助、榮譽推薦與五類聘任路徑（規劃文件） ↗](https://github.com/matt-ye/opengsa/blob/main/docs/ACADEMIC-CAREER-AND-ASSISTANTSHIPS.md) | GitHub Contents API確認main檔案存在；規劃內容不當官方依據。 |
| [官方來源、版本與適用限制台帳 ↗](https://github.com/matt-ye/opengsa/blob/main/docs/RIGHTS-SOURCES.md) | GitHub Contents API確認main檔案存在；規劃內容不當官方依據。 |
| [工作身分、研究產出與救濟說明 ↗](https://github.com/matt-ye/opengsa/blob/main/docs/RIGHTS-AND-LEGAL-FRAMEWORK.md) | GitHub Contents API確認main檔案存在；規劃內容不當官方依據。 |
| [教務處 FAQ Q1、Q3（PDF） ↗](https://www.aca.ntu.edu.tw/WebUPD/aca/SecretariatService/教學助理業務常見Q%26A_24081312354518131.pdf) | 可讀；標題／內容對應連結用途。 |
| [115-1 通識 TA 說明 ↗](https://cge.ntu.edu.tw/News_Content_n_68409_s_264301.html) | 可讀；標題／內容對應連結用途。 |
| [培訓入口 ↗](https://cbe.ntu.edu.tw/archives/15) | 可讀；標題／內容對應連結用途。 |
| [實施計畫（PDF） ↗](https://cbe.ntu.edu.tw/files/0ada7b2f164e1adc) | 可讀；標題／內容對應連結用途。 |
| [辦法第4條（PDF） ↗](https://www.dlc.ntu.edu.tw/wp-content/uploads/教務處教學助理制度獎勵金實施辦法.pdf) | 可讀；標題／內容對應連結用途。 |
| [上限標準表（PDF） ↗](https://ord.ntu.edu.tw/WebUPD/ordntu/pm/國立臺灣大學計畫兼任助理及研究獎助生每月支給上限標準表_23121516034949938.pdf) | 可讀；標題／內容對應連結用途。 |
| [勞動部最低工資問答 ↗](https://www.mol.gov.tw/1607/28690/2282/2284/2290/7121/) | 可讀；標題／內容對應連結用途。 |
| [研究人力約用注意事項 ↗](https://law.nstc.gov.tw/LawContent.aspx?id=FL028686) | 可讀；標題／內容對應連結用途。 |
| [官方沿革](https://law.nstc.gov.tw/LawContentSource.aspx?id=FL028686) | 可讀；標題／內容對應連結用途。 |
| [國科會措施入口](https://www.nstc.gov.tw/folksonomy/list/ced2afbb-f4d4-48b3-909f-247d5fbbe2f5?l=ch) | 可讀；標題／內容對應連結用途。 |
| [113年7月15日原函](https://www.nstc.gov.tw/nstc/attachments/0a7ca0b3-2bb4-4d00-a175-45246024cf08) | HEAD 200；Content-Disposition為對應PDF，octet-stream非壞鏈；本輪未重新解析全文，既有依據見RIGHTS-SOURCES.md。 |
| [FAQ第2題](https://www.nstc.gov.tw/nstc/attachments/e3c16203-1b68-49bd-bf5d-ba1d12f6976e) | HEAD 200；Content-Disposition為對應PDF，octet-stream非壞鏈；本輪未重新解析全文，既有依據見RIGHTS-SOURCES.md。 |
| [生輔組相關辦法入口 ↗](https://advisory.ntu.edu.tw/CMS/Page/211) | 人工網頁查核可讀且用途對應；自動掃描仍維持人工，不據此解除robots限制。 |
| [研究生獎勵金實施辦法 ↗](https://sec.ntu.edu.tw/001/Upload/18/relfile/9760/24895/71247f3a-7b42-474b-962d-02481279dfef.pdf) | 可讀；標題／內容對應連結用途。 |
| [教育部獎助生權益保障指導原則 ↗](https://edu.law.moe.gov.tw/LawContent.aspx?id=GL001889) | 可讀；標題／內容對應連結用途。 |
| [勞動部兼任助理勞動權益保障指導原則 ↗](https://laws.mol.gov.tw/FLAW/PrintFLAWDAT0202.aspx?id=FL077250) | 本輪查詢逾時；不標通過，旁列可讀的勞動部官方PDF備援。 |
| [官方PDF備援](https://www.mol.gov.tw/1607/28162/28296/28428/28430/28438/28440/29148/) | 可讀；標題／內容對應連結用途。 |
| [最低工資法第5條](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030028) | 可讀；標題／內容對應連結用途。 |
| [勞基法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030001) | 可讀；標題／內容對應連結用途。 |
| [勞工退休金條例第7、14條](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030020) | 可讀；標題／內容對應連結用途。 |
| [臺大人事室薪資標準 ↗](https://www.personnel.ntu.edu.tw/News_n_101162_sms_79140.html) | 可讀；標題／內容對應連結用途。 |
| [實踐大學國科會計畫兼任助理標準 ↗](https://rd.usc.edu.tw/p/406-1048-4836,r147.php?Lang=zh-tw) | 可讀；標題／內容對應連結用途。 |
| [臺大學生申訴專區 ↗](https://advisory.ntu.edu.tw/CMS/Page/252) | 人工網頁查核可讀且用途對應；自動掃描仍維持人工，不據此解除robots限制。 |
| [勞動部勞資爭議資源與分流 ↗](https://www.mol.gov.tw/1607/28690/89680/) | 可讀；標題／內容對應連結用途。 |
| [智財局正式說明](https://www.tipo.gov.tw/tw/copyright/701-21249.html) | 可讀；標題／內容對應連結用途。 |
| [勞動部僑外生退休金說明](https://www.mol.gov.tw/1607/28690/2282/2302/2304/81139/?cprint=pt) | 可讀；標題／內容對應連結用途。 |
