# 來源 URL 逐項盤查（2026-10-31）

這是來源與入口盤查，不是可申請清單。來源層級、匯入結果與限制見 [本輪報告](SOURCE-COVERAGE-AUDIT.md)。完整 JSON 見 [來源紀錄](../data/audits/source-coverage-2026-10-31.json)。

changed 為具名scanner已解析；parsed_html_discovery_only只驗入口／連結發現；parsed_pdf只代表文字可解析。主機暫停是沿用本輪限制，不宣稱每個URL皆直接收到該錯誤。

| # | 來源 | 角色 | 掃描／探測 | 候選檢核 | 出處 |
|---|---|---|---|---|---|
| 1 | [工學院](<http://www.eng.ntu.edu.tw/tc/news.aspx?pn=2&mid=9&cid=80&key=>) | discovery_or_reference | http_seed_requires_verified_https_replacement | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 2 | [法律學院](<http://www.law.ntu.edu.tw/index.php/%E7%8D%8E%E5%AD%B8%E9%87%91-%E5%BE%B5%E6%89%8D%E5%85%AC%E5%91%8A>) | discovery_or_reference | http_seed_requires_verified_https_replacement | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 3 | [生輔組首頁](<https://advisory.ntu.edu.tw/>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 4 | [臺大學生急難慰助金實施辦法](<https://advisory.ntu.edu.tw/CMS/GetFile/1359>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | data/pilot.json |
| 5 | [https://advisory.ntu.edu.tw/CMS/HTML/118](<https://advisory.ntu.edu.tw/CMS/HTML/118>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | data/scan-sources.json、data/pilot.json、docs/TAXONOMY-AND-SOURCES.md |
| 6 | [教育部學產基金急難慰問](<https://advisory.ntu.edu.tw/CMS/HTML/122>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 7 | [行天宮社會急難扶助金](<https://advisory.ntu.edu.tw/CMS/HTML/123>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 8 | [勵學獎學金實際連結](<https://advisory.ntu.edu.tw/CMS/HTML/184>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 9 | [https://advisory.ntu.edu.tw/CMS/Page/174](<https://advisory.ntu.edu.tw/CMS/Page/174>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | data/scan-sources.json、data/pilot.json、docs/TAXONOMY-AND-SOURCES.md |
| 10 | [就學貸款](<https://advisory.ntu.edu.tw/CMS/Page/176>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 11 | [不利處境助學金（原弱勢助學金）](<https://advisory.ntu.edu.tw/CMS/Page/180>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 12 | [急難慰問救助總入口](<https://advisory.ntu.edu.tw/CMS/Page/186>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 13 | [獎助學金總說明](<https://advisory.ntu.edu.tw/CMS/Page/21>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 14 | [生輔組相關辦法入口](<https://advisory.ntu.edu.tw/CMS/Page/211>) | discovery_or_reference | robots_not_plain_rules（沿用主機暫停） | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/design/wireframes.html |
| 15 | [臺大學生申訴專區](<https://advisory.ntu.edu.tw/CMS/Page/252>) | discovery_or_reference | robots_not_plain_rules（沿用主機暫停） | 未作候選欄位檢核 | docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/reference/HANDOFF.md、docs/design/wireframes.html |
| 16 | [生輔組獎學金公告一覽](<https://advisory.ntu.edu.tw/CMS/Scholarship?pageId=232>) | discovery_or_reference | robots_not_plain_rules（沿用主機暫停） | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 17 | [機構入口](<https://aiacademy.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 18 | [校外常見獎補助資源表（11509彙整）](<https://ann.cc.ntu.edu.tw/nasattach/97000/45637_5195881007.pdf>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 19 | [校內獎補助資源表（11509臺大彙整）](<https://ann.cc.ntu.edu.tw/nasattach/97000/45638_6230009973.pdf>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 20 | [校內研究計畫資源表（11509臺大彙整）](<https://ann.cc.ntu.edu.tw/nasattach/97000/45639_8879372011.pdf>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 21 | [官方方案](<https://aws.amazon.com/education/awseducate/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 22 | [Google 官方部落格](<https://blog.google/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 23 | [臺灣官方公告](<https://blog.google/intl/zh-tw/products/explore-get-answers/back-to-school-2026/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 24 | [共同教育中心公告索引](<https://cge.ntu.edu.tw/News_n_68409_sms_66659.html>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 25 | [新創專區](<https://cloud.google.com/startup>) | discovery_or_reference | transport_error | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 26 | [生命科學院](<https://cols.ntu.edu.tw/regulations-student.html>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 27 | [公共衛生學院](<https://coph.ntu.edu.tw/web/admissions/admissions_affairs.jsp?cp_id=CP1653651195215>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 28 | [社會科學院](<https://coss.ntu.edu.tw/News_n_10821_sms_19598.html>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 29 | [CC BY 4.0](<https://creativecommons.org/licenses/by/4.0/deed.zh-hant>) | supporting_documentation | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 30 | [政府資料開放授權條款第 1 版](<https://data.gov.tw/license>) | supporting_documentation | robots_unavailable | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 31 | [新竹市AI領航青年數位工具補助](<https://dgservice.hccg.gov.tw/serviceNotice.do?id=1323&rule=guest>) | enabled_candidate_profile | changed | passed_with_gaps | data/scan-sources.json、docs/PR18-RESOURCE-REVIEW.md |
| 32 | [Content Collections](<https://docs.astro.build/en/guides/content-collections/>) | supporting_documentation | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 33 | [學生啟用流程](<https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/enable-copilot/set-up-for-students>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 34 | [獎助生權益保障指導原則](<https://edu.law.moe.gov.tw/LawContent.aspx?id=GL001889>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/reference/HANDOFF.md、docs/design/wireframes.html |
| 35 | [Pack個別福利](<https://education.github.com/pack>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 36 | [臺大電資學院優秀博士生獎學金評選辦法](<https://eecs.ntu.edu.tw/uploads/asset/data/6875c5db1d41c829c9b3c899/%E9%9B%BB%E8%B3%87%E5%AD%B8%E9%99%A2%E5%84%AA%E7%A7%80%E5%8D%9A%E5%A3%AB%E7%94%9F%E7%8D%8E%E5%AD%B8%E9%87%91%E8%A9%95%E9%81%B8%E8%BE%A6%E6%B3%95_114.pdf>) | enabled_candidate_profile | changed | passed_with_gaps | data/scan-sources.json |
| 37 | [電機資訊學院](<https://eecs.ntu.edu.tw/zh_tw/Studentinformation/stu1>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 38 | [台灣就業通產業新尖兵](<https://elite.taiwanjobs.gov.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 39 | [Joint Masters](<https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters>) | discovery_or_reference | overseas_degree_placeholder_deferred | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 40 | [官方FAQ](<https://help.openai.com/en/articles/10139500-researcher-access-program-faq>) | discovery_or_reference | http_403_host_paused | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 41 | [生化科學研究所副本](<https://ibs.ntu.edu.tw/uploads/download/tw/%E5%9C%8B%E7%AB%8B%E8%87%BA%E7%81%A3%E5%A4%A7%E5%AD%B8%E7%A0%94%E7%A9%B6%E7%94%9F%E7%8D%8E%E5%8B%B5%E9%87%91%E5%AF%A6%E6%96%BD%E8%BE%A6%E6%B3%951090929.pdf>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md |
| 42 | [主辦獎項網站](<https://innoaward.taiwan-healthcare.org/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 43 | [計畫FAQ](<https://iservice.nchc.org.tw/nchc_service/nchc_service_qa.php?target=16>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 44 | [個人資料保護法官方頁](<https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=I0050021>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 45 | [著作權法](<https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=J0070017>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 46 | [勞動基準法](<https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=N0030001>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 47 | [勞動基準法](<https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030001>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 48 | [勞工退休金條例](<https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030020>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/reference/HANDOFF.md、docs/design/wireframes.html |
| 49 | [最低工資法](<https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030028>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/reference/HANDOFF.md、docs/design/wireframes.html |
| 50 | [勞工職業災害保險及保護法](<https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0050031>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 51 | [國科會專題研究計畫研究人力約用注意事項原文](<https://law.nstc.gov.tw/LawContent.aspx?id=FL028686>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、docs/RIGHTS-SOURCES.md、docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/design/wireframes.html |
| 52 | [國科會國際會議作業要點原文](<https://law.nstc.gov.tw/LawContent.aspx?id=FL038260>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、data/pilot.json、data/conference-programs.json、docs/CONFERENCE-SOURCES.md、docs/reference/HANDOFF.md、docs/INGESTION-POC.md |
| 53 | [國科會人社博士候選人論文獎勵作業要點](<https://law.nstc.gov.tw/LawContent.aspx?id=FL039061>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 54 | [國科會博士生赴國外研究（千里馬）作業要點原文](<https://law.nstc.gov.tw/LawContent.aspx?id=FL039188>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、data/pilot.json、data/conference-programs.json |
| 55 | [110.12.28版](<https://law.nstc.gov.tw/LawContentHistory.aspx?hid=101161&id=FL028686>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md |
| 56 | [108.5.17版](<https://law.nstc.gov.tw/LawContentHistory.aspx?hid=91075&id=FL028686>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md |
| 57 | [官方沿革](<https://law.nstc.gov.tw/LawContentSource.aspx?id=FL028686>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 58 | [勞動部兼任助理勞動權益保障指導原則](<https://laws.mol.gov.tw/FLAW/FLAWDAT0202.aspx?id=FL077250>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 59 | [勞動部 1140148807 號公告](<https://laws.mol.gov.tw/FLAW/FLAWDOC03.aspx?datatype=etype&ecase=%E5%8B%9E%E5%8B%95%E6%A2%9D+2&ecode=N00000&edate=20251021&eno=1140148807>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 60 | [兼任助理勞動權益保障指導原則列印版](<https://laws.mol.gov.tw/FLAW/PrintFLAWDAT0202.aspx?id=FL077250>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/design/wireframes.html |
| 61 | [文學院](<https://liberal.ntu.edu.tw/web/student/student.jsp?dm_id=DM1656910432608>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 62 | [管理學院](<https://management.ntu.edu.tw/AboutCoM/LawsCoM>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 63 | [https://my.ntu.edu.tw/fao/search.aspx](<https://my.ntu.edu.tw/fao/search.aspx>) | discovery_or_reference | login_only_manual | 未作候選欄位檢核 | data/scan-sources.json、docs/TAXONOMY-AND-SOURCES.md |
| 64 | [機構入口](<https://ocf.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 65 | [https://oia.ntu.edu.tw/](<https://oia.ntu.edu.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | data/scan-sources.json |
| 66 | [國際處 Joint Seed Funding](<https://oia.ntu.edu.tw/cooperation-with-ntu/international-funding/joint-seed-funding>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 67 | [國際處研究計畫](<https://oia.ntu.edu.tw/cooperation-with-ntu/international-funding/tukuc-research-grant>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 68 | [優惠條款](<https://one.google.com/offer/studentoffer8?hl=zh-TW>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 69 | [OpenAI Researcher Program](<https://openai.com/researcher-access-program/>) | discovery_or_reference | http_403_host_paused | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 70 | [MIT](<https://opensource.org/license/mit>) | supporting_documentation | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 71 | [臺大計畫兼任助理與獎助生每月支給上限規定](<https://ord.ntu.edu.tw/WebUPD/ordntu/pm/%E5%9C%8B%E7%AB%8B%E8%87%BA%E7%81%A3%E5%A4%A7%E5%AD%B8%E8%A8%88%E7%95%AB%E5%85%BC%E4%BB%BB%E5%8A%A9%E7%90%86%E5%8F%8A%E7%A0%94%E7%A9%B6%E7%8D%8E%E5%8A%A9%E7%94%9F%E6%AF%8F%E6%9C%88%E6%94%AF%E7%B5%A6%E4%B8%8A%E9%99%90%E6%A8%99%E6%BA%96%E8%A1%A8_23121516034949938.pdf>) | disabled_profile | robots_denied | 未作候選欄位檢核 | data/scan-sources.json、docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 72 | [https://ord.ntu.edu.tw/robots.txt](<https://ord.ntu.edu.tw/robots.txt>) | discovery_or_reference | crawl_policy_reference | 未作候選欄位檢核 | data/scan-sources.json |
| 73 | [臺大遠學計畫](<https://ord.ntu.edu.tw/w/ordntu/GW_20072012192817260>) | enabled_candidate_profile | changed | passed_with_gaps | data/scan-sources.json、data/pilot.json、docs/examples/ingestion-sources.proposed.json、docs/TAXONOMY-AND-SOURCES.md、docs/INGESTION-POC.md |
| 74 | [基金會獎項頁](<https://pan.itri.org.tw/datadetailTab?SiteID=1&MmmID=1310654304506445452>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 75 | [醫學院研發分處表單／辦法頁](<https://rd.mc.ntu.edu.tw/bomrd/ntu2/form0.asp?LTPno=52&ntPno=&pno=27>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 76 | [臺大醫學院研發分處：參與學術會議／補助與報銷申請](<https://rd.mc.ntu.edu.tw/bomrd/ntu2/form0.asp?pno=25&LTPno=47>) | discovery_or_reference | http_403_host_paused（沿用主機暫停） | 未作候選欄位檢核 | data/conference-programs.json、docs/CONFERENCE-SOURCES.md |
| 77 | [115學年度醫學院研究生優秀著作獎公告線索](<https://rd.mc.ntu.edu.tw/bomrd/ntu2/news_txt.asp?pno=7296>) | discovery_or_reference | http_403_host_paused（沿用主機暫停） | 未作候選欄位檢核 | data/pilot.json、docs/reference/HANDOFF.md |
| 78 | [國科會計畫兼任助理標準](<https://rd.usc.edu.tw/p/406-1048-4836%2Cr147.php?Lang=zh-tw>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 79 | [113.10.24轉知公告](<https://rd.web.shu.edu.tw/%E5%9C%8B%E7%A7%91%E6%9C%83%E4%BF%AE%E6%AD%A3%E3%80%8C%E5%9C%8B%E5%AE%B6%E7%A7%91%E5%AD%B8%E5%8F%8A%E6%8A%80%E8%A1%93%E5%A7%94%E5%93%A1%E6%9C%83%E8%A3%9C%E5%8A%A9%E5%B0%88%E9%A1%8C%E7%A0%94%E7%A9%B6/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md |
| 80 | [生輔組目前連結的秘書室PDF](<https://sec.ntu.edu.tw/001/Upload/18/relfile/9760/24895/71247f3a-7b42-474b-962d-02481279dfef.pdf>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 81 | [原秘書室04-038.pdf](<https://sec.ntu.edu.tw/001/Upload/relfile/9760/24895/04-038.pdf>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md |
| 82 | [資格、獎勵與流程](<https://serv.gcis.nat.gov.tw/AOCAI/courses/youth>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 83 | [國際處學海築夢頁](<https://studyabroad.ntu.edu.tw/internship/moe-overseas-internships/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 84 | [課程辦理原則修正入口](<https://tcnr.wda.gov.tw/News_Content.aspx?n=9CDFC65181CC2AEA&s=3CB8C51B711D842C&sms=68798FA6FAE753EC>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 85 | [臺大博士生獎學金設置辦法，114-04-23 版 PDF](<https://www.aca.ntu.edu.tw/WebUPD/aca/GAADRules/%E5%9C%8B%E7%AB%8B%E8%87%BA%E7%81%A3%E5%A4%A7%E5%AD%B8%E5%8D%9A%E5%A3%AB%E7%94%9F%E7%8D%8E%E5%AD%B8%E9%87%91%E8%A8%AD%E7%BD%AE%E8%BE%A6%E6%B3%951140423.pdf>) | discovery_or_reference | changed | passed_automated_checks / passed_automated_checks | docs/reference/HANDOFF.md |
| 86 | [研究生校長獎設置辦法](<https://www.aca.ntu.edu.tw/WebUPD/aca/GAADRules/%E5%9C%8B%E7%AB%8B%E8%87%BA%E7%81%A3%E5%A4%A7%E5%AD%B8%E7%A0%94%E7%A9%B6%E7%94%9F%E6%A0%A1%E9%95%B7%E7%8D%8E%E8%A8%AD%E7%BD%AE%E8%BE%A6%E6%B3%95_23040710344382101.pdf>) | discovery_or_reference | changed | passed_automated_checks | data/pilot.json |
| 87 | [115學年度教育部博獎第二梯次申請訊息](<https://www.aca.ntu.edu.tw/WebUPD/aca/GAADService/1151015_%E6%95%99%E8%82%B2%E9%83%A8%E5%8D%9A%E7%8D%8E%E7%AC%AC%E4%BA%8C%E6%A2%AF%E7%94%B3%E8%AB%8B.pdf>) | discovery_or_reference | changed | passed_with_gaps | data/pilot.json、docs/reference/HANDOFF.md |
| 88 | [教務處教學助理制度獎勵金實施辦法](<https://www.aca.ntu.edu.tw/WebUPD/aca/SecretariatService/%E6%95%99%E5%8B%99%E8%99%95%E6%95%99%E5%AD%B8%E5%8A%A9%E7%90%86%E5%88%B6%E5%BA%A6%E7%8D%8E%E5%8B%B5%E9%87%91%E5%AF%A6%E6%96%BD%E8%BE%A6%E6%B3%95%E6%A2%9D%E6%96%87-%E5%85%AC%E5%91%8A%E7%89%88.pdf>) | discovery_or_reference | changed | passed_automated_checks | data/pilot.json |
| 89 | [教學助理申請須知](<https://www.aca.ntu.edu.tw/WebUPD/aca/SecretariatService/TA%E7%94%B3%E8%AB%8B%E9%A0%88%E7%9F%A5_26071416413942730.pdf>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | data/pilot.json |
| 90 | [臺大 115 年人社論文獎勵公告](<https://www.aca.ntu.edu.tw/w/aca/GAADNews_26020916123732454>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 91 | [臺大116年度國科會博士生赴國外研究校內公告](<https://www.aca.ntu.edu.tw/w/aca/GAADNews_26051910555788878>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | data/pilot.json、docs/reference/HANDOFF.md |
| 92 | [國科會國際會議補助：臺大學生程序](<https://www.aca.ntu.edu.tw/w/aca/GAADService_21071211044877383>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、data/conference-programs.json、docs/examples/ingestion-sources.proposed.json、docs/CONFERENCE-SOURCES.md、docs/INGESTION-POC.md |
| 93 | [臺大校級博士生獎學金](<https://www.aca.ntu.edu.tw/w/aca/GAADService_21071211271211713>) | enabled_candidate_profile | changed | passed_with_gaps / passed_with_gaps | data/scan-sources.json、data/pilot.json、docs/examples/ingestion-sources.proposed.json、docs/PILOT-REVIEW.md、docs/reference/HANDOFF.md、docs/INGESTION-POC.md |
| 94 | [臺大研究生校長獎](<https://www.aca.ntu.edu.tw/w/aca/GAADService_23060908295960368>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、data/pilot.json、docs/examples/ingestion-sources.proposed.json、docs/INGESTION-POC.md |
| 95 | [臺大教育部博士生獎學金](<https://www.aca.ntu.edu.tw/w/aca/GAADService_24102208484895715>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | data/pilot.json、docs/reference/HANDOFF.md、docs/INGESTION-POC.md |
| 96 | [https://www.aca.ntu.edu.tw/w/aca/Privacy](<https://www.aca.ntu.edu.tw/w/aca/Privacy>) | discovery_or_reference | crawl_policy_reference | 未作候選欄位檢核 | data/scan-sources.json |
| 97 | [臺大教務處教學助理制度獎勵金實施辦法](<https://www.aca.ntu.edu.tw/w/aca/SecretariatService_21070717324321514>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、data/pilot.json、docs/TAXONOMY-AND-SOURCES.md |
| 98 | [生物資源暨農學院](<https://www.bioagri.ntu.edu.tw/bulletin.php>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 99 | [Scholarships](<https://www.chevening.org/scholarships/>) | discovery_or_reference | overseas_degree_placeholder_deferred | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 100 | [Scholarships &amp; Funding](<https://www.daad.de/en/studying-in-germany/scholarships/>) | discovery_or_reference | overseas_degree_placeholder_deferred | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 101 | [臺大工學院研究生獎助學金專區](<https://www.eng.ntu.edu.tw/tc/scholarship.aspx>) | disabled_profile | robots_not_plain_rules | 未作候選欄位檢核 | data/scan-sources.json |
| 102 | [傑出人才發展基金會：優秀學生出國開會補助](<https://www.faos.org.tw/Application/ApplicatStud.html>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、data/conference-programs.json、docs/CONFERENCE-SOURCES.md、docs/INGESTION-POC.md |
| 103 | [臺灣公民赴美獎助](<https://www.fulbright.org.tw/zh-hant/awards-to-the-u-s/>) | discovery_or_reference | overseas_degree_placeholder_deferred | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 104 | [政府住宅補助資訊索引](<https://www.gov.tw/News_Content_26_586833>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 105 | [新竹市政府公告](<https://www.hccg.gov.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 106 | [平台入口](<https://www.junyiacademy.org/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 107 | [臺大醫學院職能治療博士班修業進度官方文件](<https://www.mc.ntu.edu.tw/manage/upload/fp/f_20250820160641092.pdf>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 108 | [醫學院](<https://www.mc.ntu.edu.tw/ntucm/Index.action>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 109 | [https://www.mc.ntu.edu.tw/oia/Fpage.action?muid=1961&amp;fid=1296](<https://www.mc.ntu.edu.tw/oia/Fpage.action?muid=1961&fid=1296>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | data/scan-sources.json、data/conference-programs.json、docs/CONFERENCE-SOURCES.md |
| 110 | [教育部獎助專區](<https://www.moe.gov.tw/Content_List.aspx?n=DBDDB8DC17D0D8C4>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md、docs/reference/HANDOFF.md |
| 111 | [最低工資的意義](<https://www.mol.gov.tw/1607/28162/28166/28180/28182/28188/29025/>) | discovery_or_reference | http_410 | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/design/wireframes.html |
| 112 | [官方PDF備援](<https://www.mol.gov.tw/1607/28162/28296/28428/28430/28438/28440/29148/>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 113 | [勞動部正式說明](<https://www.mol.gov.tw/1607/28690/2282/2302/2304/81139/?cprint=pt>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/design/wireframes.html |
| 114 | [勞動部勞資爭議入口](<https://www.mol.gov.tw/1607/28690/89680/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/reference/HANDOFF.md、docs/design/wireframes.html |
| 115 | [國網中心官網](<https://www.nchc.org.tw/>) | discovery_or_reference | transport_error | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 116 | [國科會](<https://www.nstc.gov.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 117 | [博士生費用增核入口](<https://www.nstc.gov.tw/folksonomy/list/ced2afbb-f4d4-48b3-909f-247d5fbbe2f5?l=ch>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 118 | [116 年度千里馬申請須知](<https://www.nstc.gov.tw/folksonomy/rfpDetail/fb285d89-02c6-4a01-a256-580b4c434822?l=ch>) | discovery_or_reference | http_410 | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 119 | [原函PDF](<https://www.nstc.gov.tw/nstc/attachments/0a7ca0b3-2bb4-4d00-a175-45246024cf08>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 120 | [博士生增核FAQ PDF](<https://www.nstc.gov.tw/nstc/attachments/e3c16203-1b68-49bd-bf5d-ba1d12f6976e>) | discovery_or_reference | parsed_pdf | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 121 | [115 年國科會博士生研究獎學金試辦方案](<https://www.nstc.gov.tw/sci/ch/detail/24ad4e4a-bd37-4ba0-9955-5b2e2ffd5ac6>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 122 | [國科會116年度博士生赴國外研究公告](<https://www.nstc.gov.tw/sci/ch/detail/9fea56ff-9a28-4304-abb3-192109491942>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | data/pilot.json、docs/reference/HANDOFF.md |
| 123 | [Inception官方定位](<https://www.nvidia.com/en-us/startups/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 124 | [專任研究助理參考表入口](<https://www.personnel.ntu.edu.tw/News_Content_Create_1_n_64102_state_F5D336F102ACBC68_s_70764_sms_62508.html>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md |
| 125 | [人事室薪資標準](<https://www.personnel.ntu.edu.tw/News_n_101162_sms_79140.html>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/RIGHTS-SOURCES.md、docs/design/wireframes.html |
| 126 | [RFC 5545](<https://www.rfc-editor.org/rfc/rfc5545.html>) | supporting_documentation | html_body_missing | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 127 | [RFC 9309](<https://www.rfc-editor.org/rfc/rfc9309.html>) | supporting_documentation | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 128 | [理學院](<https://www.science.ntu.edu.tw/student-affairs/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 129 | [中研院115年度人文社會科學博士候選人培育計畫公告](<https://www.sinica.edu.tw/news_content/56/3434>) | enabled_candidate_profile | changed | passed_with_gaps | data/scan-sources.json、docs/TAXONOMY-AND-SOURCES.md |
| 130 | [經濟部商業發展署](<https://www.sme.gov.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 131 | [智財局論文著作權說明](<https://www.tipo.gov.tw/tw/copyright/701-21249.html>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/RIGHTS-AND-LEGAL-FRAMEWORK.md、docs/design/wireframes.html |
| 132 | [台積電博士獎學金專案](<https://www.tsmc.com/chinese/careers/phd_fellowship>) | disabled_profile | http_403_host_paused | 未作候選欄位檢核 | data/scan-sources.json |
| 133 | [TWCC](<https://www.twcc.ai/>) | discovery_or_reference | robots_denied | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 134 | [WCAG 2.2 AA](<https://www.w3.org/TR/WCAG22/>) | supporting_documentation | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/HANDOFF.md |
| 135 | [吳健雄學術基金會](<https://www.wcs.org.tw/news-4.php>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 136 | [最新公告](<https://www.wda.gov.tw/News_Content.aspx?n=31&s=19491&sms=10306>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 137 | [新北市青年局官網](<https://www.youth.ntpc.gov.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 138 | [當期公告](<https://www.youth.ntpc.gov.tw/youth/ch/app/news/view?id=104&module=headnews&serno=e4415b82-9eca-45ca-aee5-d91edc32610f>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 139 | [臺北市青年AI工具補助](<https://youth.gov.taipei/services/05eb79e5-46b5-41e5-b1fd-0519d782b04a/0ecc1836-dd0d-4085-a34f-003609f00796>) | enabled_candidate_profile | changed | passed_automated_checks | data/scan-sources.json、docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 140 | [青年局入口](<https://youth.kcg.gov.tw/>) | discovery_or_reference | html_no_meaningful_body_or_dynamic_content | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md、docs/reference/AI-TOOL-SUBSIDIES.md |
| 141 | [桃園市青年局官網](<https://youth.tycg.gov.tw/>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/reference/AI-TOOL-SUBSIDIES.md |
| 142 | [計畫公告](<https://youth.tycg.gov.tw/News_Content.aspx?n=5622&s=1617472>) | discovery_or_reference | parsed_html_discovery_only | 未作候選欄位檢核 | docs/PR18-RESOURCE-REVIEW.md |
| 143 | [基金會獎項頁](<https://yzhsu.feg.com.tw/Programs.html?selectID=0591395e-8a94-433b-8e07-9732c431856d>) | discovery_or_reference | robots_not_plain_rules | 未作候選欄位檢核 | docs/TAXONOMY-AND-SOURCES.md |
| 144 | [中研院博士候選人培育計畫](<https://daas.sinica.edu.tw/pages/2798>) | discovery_or_reference | transport_error | 未作候選欄位檢核 | data/scan-sources.json |
| 145 | [臺大電資學院優秀研究生獎助學金](<https://eecs.ntu.edu.tw/w/eecsntu/scholarship_list>) | discovery_or_reference | http_404 | 未作候選欄位檢核 | data/scan-sources.json |
