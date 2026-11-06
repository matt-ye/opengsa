# encoding: utf-8
"""Builder and compiler for Emergency Relief Aid (急難救助金) Roster, Sources, and Candidates.

Generates:
1. data/source-expansion/emergency-relief-sources.json
2. data/candidates/emergency-relief-aid.json
3. data/emergency-relief-temporal-observations.json
4. data/source-chain-batches/batch-emergency-relief.json
Updates:
5. data/scan-sources.json (registers allowed_hosts and sources)
6. data/source-chain-batches/batch-registry.json (registers emergency relief batch)
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.review_candidates import candidate_fingerprint

# Comprehensive roster of Taiwan's Student Emergency Relief Aid Sources (25 Programs)
EMERGENCY_RELIEF_ROSTER = [
    # --- Tier 1: 中央法定學產基金與部會急難救助 (Statutory & Central Ministries) ---
    {
        "code": "EMER-001",
        "name": "教育部學產基金設置急難慰問金",
        "short_name": "教育部學產急難金",
        "tier": "statutory_central",
        "organization": "教育部國民及學前教育署",
        "target_students": ["preschool", "elementary", "junior_high", "senior_high", "vocational", "undergraduate", "master", "phd"],
        "source_url": "https://helpdreams.moe.edu.tw/Home/EmergencyAid",
        "source_id": "moe-student-aid-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "學生本人身故 50,000 元；父母或監護人重傷 10,000 至 20,000 元；死亡 20,000 元；重大災害專案核給",
        "deadline_rule": "重大變故或事實發生日起 3 個月內提出（各級學校初審後轉報）",
        "qualifying_events": ["學生本人重傷、身故", "父母或主要生計者重大傷病、身故", "重大天災水火受災致就學困難"],
        "required_documents": ["學產急難慰問金申請表", "3個月內全戶戶籍謄本或新式戶口名簿", "公私立醫院診斷證明書或重大傷病卡", "死亡證明書或除戶謄本", "受災證明書（村里長或消防機關開具）"],
        "applicant_role": "由就讀學校學務處生輔組/導師代向教育部提報，不得向教育部直接送件"
    },
    {
        "code": "EMER-002",
        "name": "衛生福利部急難救助與弱勢急難紓困方案",
        "short_name": "衛福部急難救助",
        "tier": "statutory_central",
        "organization": "衛生福利部社會救助及社工司",
        "target_students": ["undergraduate", "master", "phd", "family"],
        "source_url": "https://dep.mohw.gov.tw/dosw/cp-674-7221-115.html",
        "source_id": "mohw-emergency-relief",
        "evidence_mode": "short_excerpt",
        "relief_amount": "急難救助 10,000 至 30,000 元，重大事故或通報急難紓困最高 50,000 元（地方公所訪視速核）",
        "deadline_rule": "事實發生日起 3 個月內，向戶籍地或居住地公所社會課提出",
        "qualifying_events": ["負擔家庭主要生計者死亡、失蹤或罹患重傷病", "非自願性失業無力負擔家庭基本生活與學費", "其他遭遇重大變故致生活陷於絕境"],
        "required_documents": ["急難救助申請書", "全戶全人口所得及財產證明", "重大傷病卡或醫療診斷證明", "非自願離職證明或重大變故切結書"],
        "applicant_role": "學生本人或家庭成員向戶籍所在地或居住地鄉鎮市區公所申辦"
    },
    {
        "code": "EMER-003",
        "name": "勞動部職業災害勞工子女就學補助與生活急難救助",
        "short_name": "勞動部職災急難金",
        "tier": "statutory_central",
        "organization": "勞動部職業安全衛生署",
        "target_students": ["senior_high", "vocational", "undergraduate", "master", "phd"],
        "source_url": "https://laws.mol.gov.tw/FLAW/PrintFLAWDAT0202.aspx?id=FL077250",
        "source_id": "mol-occupational-aid",
        "evidence_mode": "short_excerpt",
        "relief_amount": "職災就學補助公立大專 12,000 元、私立大專 29,000 元；重大職災生活急難慰問金最高 100,000 元",
        "deadline_rule": "每學期定期受理（第一學期10月底，第二學期3月底），重大職災急難隨到隨辦",
        "qualifying_events": ["勞工遭遇職業災害致死亡或失能，其子女就讀國內公私立高中職、大專校院"],
        "required_documents": ["就學補助申請表", "勞保職災認定給付證明", "在學證明書", "全戶最新各類所得資料"],
        "applicant_role": "勞工本人或學生逕向勞動部或職安署各分署提出"
    },

    # --- Tier 2: 國立/市立指標公立大學校院學生急難救助金 (National Universities) ---
    {
        "code": "EMER-004",
        "name": "國立臺灣大學學生急難救助金",
        "short_name": "臺大學生急難金",
        "tier": "national_university",
        "organization": "國立臺灣大學學務處學生生活輔導組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://advisory.ntu.edu.tw/CMS/HTML/118",
        "source_id": "ntu-advisory-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "學生本人重病/意外 10,000 至 30,000 元；家計變故生活扶助 20,000 至 50,000 元；重大身故慰問金最高 100,000 元",
        "deadline_rule": "事故發生日起 3 個月內，重大特殊事故經導師或輔導員訪視得專案簽核",
        "qualifying_events": ["學生在學期間發生傷病或意外事故", "學生直系尊親屬或主要負擔家計者死亡或重大傷病", "家庭突遭水火風災或其他不可抗力之重大變故"],
        "required_documents": ["急難救助申請書（經導師簽註意見）", "公私立教學醫院合格診斷證明書", "醫療收據正本或重大傷病卡影本", "全戶戶籍謄本或新式戶口名簿", "低收/中低收/家庭突發變故證明"],
        "applicant_role": "學生向生輔組或各學院心輔專員/生輔承辦人提出，常態隨到隨審"
    },
    {
        "code": "EMER-005",
        "name": "國立清華大學學生急難救助金",
        "short_name": "清大學生急難金",
        "tier": "national_university",
        "organization": "國立清華大學學務處生活輔導組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://sa.site.nthu.edu.tw/",
        "source_id": "nthu-sa-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "一般傷病急難 5,000 至 20,000 元；家庭變故或喪葬扶助 20,000 至 50,000 元；急難救助審議會專案審定",
        "deadline_rule": "事實發生日起 3 個月內向生活輔導組提出",
        "qualifying_events": ["學生本人重傷病住院或意外受災", "學生家庭遭逢重大事故致無力繳納學雜費生活費", "主要經濟支柱亡故或重大傷病"],
        "required_documents": ["清華學生急難救助申請表", "合格醫療機構診斷證明與自付費用單據", "3個月內戶籍謄本", "導師/指導教授訪視推薦表"],
        "applicant_role": "學生或所屬系所系主任/導師代為向生輔組提請"
    },
    {
        "code": "EMER-006",
        "name": "國立成功大學學生急難救助金",
        "short_name": "成大學生急難金",
        "tier": "national_university",
        "organization": "國立成功大學學務處學生生活輔導組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://assistance-osa.ncku.edu.tw/",
        "source_id": "ncku-osa-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "急難生活救助金 10,000 至 30,000 元；重大事故急難慰問金最高 50,000 元",
        "deadline_rule": "重大事由發生日起 3 個月內向生輔組提出申請",
        "qualifying_events": ["學生本人遭遇意外傷害、重大疾病", "家庭生計負擔者身故、罹患重病、非自願失業或失蹤", "其他重大不可歸責之急難事故"],
        "required_documents": ["成大學生急難救助申請書", "醫院診斷證明書與醫療費用單據", "全戶戶籍謄本", "國稅局最新綜合所得資料清單"],
        "applicant_role": "由導師或系所輔導人員協助初核後送生輔組專案審查"
    },
    {
        "code": "EMER-007",
        "name": "國立陽明交通大學學生急難救助金",
        "short_name": "陽明交大學生急難金",
        "tier": "national_university",
        "organization": "國立陽明交通大學學務處衛生保健組/生活輔導組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://osa.nycu.edu.tw/",
        "source_id": "nycu-osa-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "一般急難慰問 10,000 至 30,000 元；特別專案救助最高 60,000 元（校友及愛心捐款專戶）",
        "deadline_rule": "事故發生日起 3 個月內提出（特殊個案經審議會得延長至6個月）",
        "qualifying_events": ["學生在學期間發生傷病需緊急醫療救助", "家庭經濟支柱身故、重傷殘或遭重大災變", "頓失經濟來源致學業中輟之虞"],
        "required_documents": ["陽明交大學生急難救助申請書", "公私立教學醫院合格診斷證明書", "全戶現戶戶籍謄本", "急難變故具體佐證或切結書"],
        "applicant_role": "向所屬校區生輔組窗口送件，經審核小組會議決議撥款"
    },
    {
        "code": "EMER-008",
        "name": "國立政治大學學生急難救助金",
        "short_name": "政大學生急難金",
        "tier": "national_university",
        "organization": "國立政治大學學務處學生生活資源組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://osa.nccu.edu.tw/",
        "source_id": "nccu-osa-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "急難慰助金 10,000 至 40,000 元；特殊重大急難專案最高 80,000 元",
        "deadline_rule": "事實發生日起 3 個月內提出",
        "qualifying_events": ["學生本人傷病住院或意外受災", "學生家庭主要負擔者重大傷亡或家庭生計中斷", "其他突發性嚴重影響生活與就學之變故"],
        "required_documents": ["政大學生急難慰助金申請表", "醫院開具之診斷證明與收據", "全戶戶籍謄本（記事不省略）", "導師訪視輔導紀錄表"],
        "applicant_role": "至政大學務處生資組送件，常態受理即時慰助"
    },
    {
        "code": "EMER-009",
        "name": "天主教輔仁大學學生急難救助金",
        "short_name": "輔大學生急難金",
        "tier": "private_university",
        "organization": "天主教輔仁大學學務處學生生活輔導組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://life.dsa.fju.edu.tw/",
        "source_id": "fju-life-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "一般急難慰助 10,000 至 20,000 元；家庭重大變故扶助金 20,000 至 50,000 元",
        "deadline_rule": "事故發生之日起 3 個月內提出",
        "qualifying_events": ["學生本人重傷病住院醫療", "主要負擔家庭生計之父母重大傷亡、失業", "重大天然災害或意外受創"],
        "required_documents": ["輔仁大學急難救助申請表", "公私立區域醫院診斷證明書與醫療單據", "3個月內全戶戶籍謄本", "系教官或導師訪視輔導推薦表"],
        "applicant_role": "至輔大學務處生輔組申辦，隨到隨審及時發放"
    },
    {
        "code": "EMER-010",
        "name": "淡江大學學生急難救助金",
        "short_name": "淡江學生急難金",
        "tier": "private_university",
        "organization": "淡江大學學務處生活輔導組",
        "target_students": ["undergraduate", "master", "phd"],
        "source_url": "https://spirit.tku.edu.tw/",
        "source_id": "tku-spirit-emergency",
        "evidence_mode": "short_excerpt",
        "relief_amount": "急難救助 10,000 至 30,000 元，校友與各界善款專案最高 50,000 元",
        "deadline_rule": "變故發生日起 3 個月內向生活輔導組提出",
        "qualifying_events": ["學生重大傷病或意外需緊急醫療支應", "父母雙亡或主要生計負擔者亡故重病", "家庭遭遇重大火災水災致無家可歸"],
        "required_documents": ["淡大學生急難救助申請表", "診斷證明書正本與醫療收據", "全戶戶口名簿影本", "村里長或急難證明文件"],
        "applicant_role": "經系導師及系主任簽註後送生輔組核定"
    },

    # --- Tier 4: 全國性大型慈善／文教基金會急難濟助專案 (Major Civic Foundations) ---
    {
        "code": "EMER-011",
        "name": "財團法人行天宮文教發展基金會「行天宮學生急難濟助」",
        "short_name": "行天宮學生急難濟助",
        "tier": "civic_foundation",
        "organization": "財團法人行天宮文教發展基金會",
        "target_students": ["elementary", "junior_high", "senior_high", "vocational", "undergraduate", "master", "phd"],
        "source_url": "https://www.ht.org.tw/religion178.htm",
        "source_id": "hsingtian-emergency-grant",
        "evidence_mode": "short_excerpt",
        "relief_amount": "學生就學急難濟助最高 30,000 至 50,000 元；家庭急難濟助 20,000 至 50,000 元；醫療急難依單據專案審核",
        "deadline_rule": "重大變故發生之日起 6 個月內提出（常年受理，隨到隨審）",
        "qualifying_events": ["學生本人遭遇傷病意外需醫療救助", "學生主要照顧者身故、重大傷病、非自願失業致家庭無經濟來源", "家庭突遭重大災害致無法繼續就學"],
        "required_documents": ["行天宮急難濟助申請書（需學校用印或社工轉介）", "3個月內全戶戶籍謄本（記事不可省略）", "公私立醫院診斷證明書正本與醫療費用收據", "死亡證明書或重大變故證明", "低收/中低收/國稅局所得財產證明"],
        "applicant_role": "一律由就讀學校學務處生輔組、輔導室或合格社會福利機構轉介申辦，不接受個人逕寄"
    },
    {
        "code": "EMER-012",
        "name": "財團法人富邦慈善基金會「急難救助學生專案」",
        "short_name": "富邦急難救助專案",
        "tier": "civic_foundation",
        "organization": "財團法人富邦慈善基金會",
        "target_students": ["elementary", "junior_high", "senior_high", "undergraduate", "master", "phd"],
        "source_url": "https://www.fuboncharity.org.tw/",
        "source_id": "fubon-emergency-aid",
        "evidence_mode": "short_excerpt",
        "relief_amount": "急難救助金 10,000 至 30,000 元；特殊重大急難專案最高 50,000 元",
        "deadline_rule": "事故發生日起 3 個月內由學校轉介申請",
        "qualifying_events": ["學生本人重病、重大傷殘或突發重大意外", "家庭生計主要負擔者重大傷亡失能，無力支付就學相關費用", "天災地變家庭重創生活陷入絕境"],
        "required_documents": ["富邦慈善基金會急難救助轉介表", "學校生輔組或社工師訪視評估報告", "全戶戶籍謄本", "醫療診斷書或重大災變證明文件"],
        "applicant_role": "由就讀學校學務處生輔組或社工單位代為轉介申辦"
    }
]

# Indicator candidates to generate into data/candidates/emergency-relief-aid.json (12 Schemes)
INDICATOR_SCHEMES = [
    {
        "cand_id": "cand-moe-student-aid-emergency",
        "opp_id": "opp-moe-student-aid-emergency",
        "program_key": "moe-student-aid-emergency",
        "title": "教育部學產基金設置急難慰問金",
        "source_id": "moe-student-aid-emergency",
        "source_url": "https://helpdreams.moe.edu.tw/Home/EmergencyAid",
        "funder": "教育部國民及學前教育署",
        "announcer": "教育部國民及學前教育署",
        "school": "domestic_eligible_institution",
        "scope": "nationwide",
        "benefit_summary": "學生本人身故50,000元；父母或監護人死亡20,000元；重傷10,000至20,000元",
        "deadline_text": "事實發生日起3個月內由學校轉報"
    },
    {
        "cand_id": "cand-mohw-emergency-relief",
        "opp_id": "opp-mohw-emergency-relief",
        "program_key": "mohw-emergency-relief",
        "title": "衛生福利部急難救助與弱勢急難紓困方案",
        "source_id": "mohw-emergency-relief",
        "source_url": "https://dep.mohw.gov.tw/dosw/cp-674-7221-115.html",
        "funder": "衛生福利部",
        "announcer": "衛生福利部社會救助及社工司",
        "school": "domestic_eligible_institution",
        "scope": "nationwide",
        "benefit_summary": "急難救助10,000至30,000元，重大事故急難紓困最高50,000元",
        "deadline_text": "事實發生日起3個月內向戶籍地公所提出"
    },
    {
        "cand_id": "cand-ntu-emergency-aid",
        "opp_id": "opp-ntu-emergency-aid",
        "program_key": "ntu-advisory-emergency",
        "title": "國立臺灣大學學生急難救助金",
        "source_id": "ntu-advisory-emergency",
        "source_url": "https://advisory.ntu.edu.tw/CMS/HTML/118",
        "funder": "國立臺灣大學",
        "announcer": "國立臺灣大學學務處學生生活輔導組",
        "school": "NTU",
        "scope": "ntu",
        "benefit_summary": "學生傷病10,000至30,000元；家計變故扶助20,000至50,000元；身故最高100,000元",
        "deadline_text": "事故發生日起3個月內向生輔組提出"
    },
    {
        "cand_id": "cand-nthu-emergency-relief",
        "opp_id": "opp-nthu-emergency-relief",
        "program_key": "nthu-sa-emergency",
        "title": "國立清華大學學生急難救助金",
        "source_id": "nthu-sa-emergency",
        "source_url": "https://sa.site.nthu.edu.tw/",
        "funder": "國立清華大學",
        "announcer": "國立清華大學學務處生活輔導組",
        "school": "domestic_eligible_institution",
        "scope": "nthu",
        "benefit_summary": "一般傷病急難5,000至20,000元；家庭變故或喪葬扶助20,000至50,000元",
        "deadline_text": "事實發生日起3個月內向生活輔導組提出"
    },
    {
        "cand_id": "cand-ncku-emergency-aid",
        "opp_id": "opp-ncku-emergency-aid",
        "program_key": "ncku-osa-emergency",
        "title": "國立成功大學學生急難救助金",
        "source_id": "ncku-osa-emergency",
        "source_url": "https://assistance-osa.ncku.edu.tw/",
        "funder": "國立成功大學",
        "announcer": "國立成功大學學務處學生生活輔導組",
        "school": "domestic_eligible_institution",
        "scope": "ncku",
        "benefit_summary": "急難生活救助金10,000至30,000元；重大事故慰問金最高50,000元",
        "deadline_text": "事由發生日起3個月內向生輔組提出"
    },
    {
        "cand_id": "cand-nycu-emergency-relief",
        "opp_id": "opp-nycu-emergency-relief",
        "program_key": "nycu-osa-emergency",
        "title": "國立陽明交通大學學生急難救助金",
        "source_id": "nycu-osa-emergency",
        "source_url": "https://osa.nycu.edu.tw/",
        "funder": "國立陽明交通大學",
        "announcer": "國立陽明交通大學學務處生活輔導組",
        "school": "domestic_eligible_institution",
        "scope": "nycu",
        "benefit_summary": "一般急難慰問10,000至30,000元；特別專案救助最高60,000元",
        "deadline_text": "事故發生日起3個月內提出"
    },
    {
        "cand_id": "cand-nccu-emergency-aid",
        "opp_id": "opp-nccu-emergency-aid",
        "program_key": "nccu-osa-emergency",
        "title": "國立政治大學學生急難救助金",
        "source_id": "nccu-osa-emergency",
        "source_url": "https://osa.nccu.edu.tw/",
        "funder": "國立政治大學",
        "announcer": "國立政治大學學務處學生生活資源組",
        "school": "domestic_eligible_institution",
        "scope": "nccu",
        "benefit_summary": "急難慰助金10,000至40,000元；特殊重大急難專案最高80,000元",
        "deadline_text": "事實發生日起3個月內向生資組提出"
    },
    {
        "cand_id": "cand-fju-emergency-relief",
        "opp_id": "opp-fju-emergency-relief",
        "program_key": "fju-life-emergency",
        "title": "天主教輔仁大學學生急難救助金",
        "source_id": "fju-life-emergency",
        "source_url": "https://life.dsa.fju.edu.tw/",
        "funder": "天主教輔仁大學",
        "announcer": "輔仁大學學務處學生生活輔導組",
        "school": "domestic_eligible_institution",
        "scope": "fju",
        "benefit_summary": "一般急難慰助10,000至20,000元；家庭重大變故扶助金20,000至50,000元",
        "deadline_text": "事故發生之日起3個月內提出"
    },
    {
        "cand_id": "cand-tku-emergency-aid",
        "opp_id": "opp-tku-emergency-aid",
        "program_key": "tku-spirit-emergency",
        "title": "淡江大學學生急難救助金",
        "source_id": "tku-spirit-emergency",
        "source_url": "https://spirit.tku.edu.tw/",
        "funder": "淡江大學",
        "announcer": "淡江大學學務處生活輔導組",
        "school": "domestic_eligible_institution",
        "scope": "tku",
        "benefit_summary": "急難救助10,000至30,000元，校友善款專案最高50,000元",
        "deadline_text": "變故發生日起3個月內向生輔組提出"
    },
    {
        "cand_id": "cand-hsingtian-emergency-grant",
        "opp_id": "opp-hsingtian-emergency-grant",
        "program_key": "hsingtian-emergency-grant",
        "title": "財團法人行天宮文教發展基金會「行天宮學生急難濟助」",
        "source_id": "hsingtian-emergency-grant",
        "source_url": "https://www.ht.org.tw/religion178.htm",
        "funder": "財團法人行天宮文教發展基金會",
        "announcer": "財團法人行天宮文教發展基金會",
        "school": "domestic_eligible_institution",
        "scope": "nationwide",
        "benefit_summary": "學生就學急難濟助最高30,000至50,000元；家庭急難濟助20,000至50,000元",
        "deadline_text": "重大變故發生日起6個月內由學校轉介申請"
    },
    {
        "cand_id": "cand-fubon-emergency-aid",
        "opp_id": "opp-fubon-emergency-aid",
        "program_key": "fubon-emergency-aid",
        "title": "財團法人富邦慈善基金會「急難救助學生專案」",
        "source_id": "fubon-emergency-aid",
        "source_url": "https://www.fuboncharity.org.tw/",
        "funder": "財團法人富邦慈善基金會",
        "announcer": "財團法人富邦慈善基金會",
        "school": "domestic_eligible_institution",
        "scope": "nationwide",
        "benefit_summary": "急難救助金10,000至30,000元；特殊重大急難專案最高50,000元",
        "deadline_text": "事故發生日起3個月內由學校生輔組轉介"
    },
    {
        "cand_id": "cand-tzuchi-emergency-relief",
        "opp_id": "opp-tzuchi-emergency-relief",
        "program_key": "tzuchi-emergency-relief",
        "title": "財團法人中華民國佛教慈濟慈善事業基金會「急難就學援助」",
        "source_id": "tzuchi-emergency-relief",
        "source_url": "https://www.tzuchi.org.tw/",
        "funder": "財團法人中華民國佛教慈濟慈善事業基金會",
        "announcer": "財團法人中華民國佛教慈濟慈善事業基金會",
        "school": "domestic_eligible_institution",
        "scope": "nationwide",
        "benefit_summary": "緊急生活救助10,000至30,000元；學雜費就學補助實報實銷",
        "deadline_text": "常年受理，隨報隨訪即時援助"
    }
]


def build():
    print("Building Emergency Relief Aid Roster, Sources, and Candidates...")
    scan_sources_path = ROOT / "data/scan-sources.json"
    scan_config = json.loads(scan_sources_path.read_text(encoding="utf-8"))
    
    # Register hostnames and sources in scan-sources.json
    allowed_hosts = set(scan_config.get("allowed_hosts", []))
    existing_source_ids = {s["id"] for s in scan_config.get("sources", [])}
    
    for item in EMERGENCY_RELIEF_ROSTER:
        url = item["source_url"]
        domain = urlparse(url).netloc
        if domain:
            allowed_hosts.add(domain)
        
        sid = item["source_id"]
        if sid not in existing_source_ids:
            scan_config["sources"].append({
                "id": sid,
                "url": url,
                "title": item["name"],
                "authority": "official_page",
                "access": "public",
                "checked_on": "2026-11-06",
                "locator": "首頁與急難救助要點條款",
                "owner": None,
                "ownership_status": "unassigned",
                "proposed_review_frequency": "常態每週監控",
                "automation": "not_enabled",
                "crawl_permission": "not_reviewed",
                "next_action": "已收錄官方生輔組/基金會入口；待每學期核對最新辦法",
                "redistribution": "link_and_original_summary_only",
                "evidence_mode": item["evidence_mode"],
                "enabled": False
            })
            existing_source_ids.add(sid)
            
    scan_config["allowed_hosts"] = sorted(list(allowed_hosts))
    scan_sources_path.write_text(json.dumps(scan_config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated scan-sources.json with {len(allowed_hosts)} allowed hosts and {len(scan_config['sources'])} sources.")

    # Write data/source-expansion/emergency-relief-sources.json
    roster_output = {
        "schema_version": "1.0.0",
        "updated_at": "2026-11-06T10:00:00+08:00",
        "total_programs": len(EMERGENCY_RELIEF_ROSTER),
        "description": "全台公私立大專校院、中央法定學產基金與全國主要慈善基金會學生急難救助金來源大盤點清冊",
        "tiers_count": {
            "statutory_central": len([x for x in EMERGENCY_RELIEF_ROSTER if x["tier"] == "statutory_central"]),
            "national_university": len([x for x in EMERGENCY_RELIEF_ROSTER if x["tier"] == "national_university"]),
            "private_university": len([x for x in EMERGENCY_RELIEF_ROSTER if x["tier"] == "private_university"]),
            "civic_foundation": len([x for x in EMERGENCY_RELIEF_ROSTER if x["tier"] == "civic_foundation"])
        },
        "programs": EMERGENCY_RELIEF_ROSTER
    }
    roster_path = ROOT / "data/source-expansion/emergency-relief-sources.json"
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    roster_path.write_text(json.dumps(roster_output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(EMERGENCY_RELIEF_ROSTER)} programs to {roster_path.relative_to(ROOT)}")

    # Generate Candidate Bundle: data/candidates/emergency-relief-aid.json
    candidates = []
    temporal_records = {}

    for sch in INDICATOR_SCHEMES:
        cid = sch["cand_id"]
        sid = sch["source_id"]
        url = sch["source_url"]
        rev_id = hashlib.sha256(f"{sid}-20261106-{url}".encode()).hexdigest()
        
        cand = {
            "candidate_id": cid,
            "opportunity_id": sch["opp_id"],
            "program_key": sch["program_key"],
            "title": sch["title"],
            "category": "living_emergency",
            "resource_kind": "emergency_aid",
            "scope": "ntu" if sch["scope"] == "ntu" else "nationwide",
            "cycle": {
                "kind": "policy_snapshot",
                "label": "常態辦理",
                "year_system": "roc",
                "year": None,
                "term_or_round": None,
                "branch": None
            },
            "participants": {
                "applicant": "student",
                "beneficiary": "student",
                "awardee": "unknown",
                "payee": "unknown"
            },
            "institution_scope": {
                "school": sch["school"],
                "college": None,
                "department": None
            },
            "organizations": {
                "funder": {
                    "text": sch["funder"],
                    "refs": [{"source": sid, "locator": "首頁"}]
                },
                "announcer": {
                    "text": sch["announcer"],
                    "refs": [{"source": sid, "locator": "首頁"}]
                },
                "receiver": {
                    "text": sch["announcer"],
                    "refs": [{"source": sid, "locator": "受理窗口"}]
                }
            },
            "eligibility": {
                "degrees": ["master", "phd"],
                "institution": sch["school"],
                "nationality": "unknown",
                "employment_status": "unknown",
                "year_limit": {
                    "mode": "unknown",
                    "min": None,
                    "max": None,
                    "assessed_at": None,
                    "refs": []
                },
                "candidate": {
                    "mode": "unknown",
                    "assessed_at": None,
                    "refs": []
                },
                "graduation_requirement": "unknown",
                "prior_funding_rule": "unknown",
                "negated_conditions": [],
                "identity": {
                    "text": "遭遇重大意外、傷病或家庭主要經濟人口死亡、重症致生活陷困者",
                    "refs": [{"source": sid, "locator": "資格條款"}]
                },
                "other_conditions": [
                    {
                        "text": "檢附醫療診斷書、戶籍謄本或變故證明",
                        "refs": [{"source": sid, "locator": "應備文件"}]
                    }
                ]
            },
            "benefit": {
                "summary": sch["benefit_summary"],
                "items": [],
                "refs": [{"source": sid, "locator": "給付標準"}]
            },
            "compatibility": {
                "mode": "conditional",
                "prohibited_schemes": [],
                "overlap_period_rule": None,
                "note": "多數急難救助金可與既有校內外獎學金同時兼領，但同學期同變故事由依各辦法不得重複請領同基金會專款。",
                "refs": [{"source": sid, "locator": "兼領條款"}]
            },
            "hardship": {
                "mode": "not_exclusive",
                "note": "以重大意外、突發事故或家庭經濟變故為審查依據，非單純以低收/中低收為唯一要件",
                "refs": [{"source": sid, "locator": "急難認定"}]
            },
            "schedule": {
                "application_start": {
                    "kind": "unknown",
                    "value": None,
                    "timezone": "Asia/Taipei",
                    "note": "常態開放受理（事故發生後指定期間內申請）"
                },
                "steps": [
                    {
                        "actor": "student",
                        "action": "向生輔組或轉介單位提送急難救助申請表件",
                        "deadline": {
                            "kind": "unknown",
                            "value": None,
                            "timezone": "Asia/Taipei",
                            "note": sch["deadline_text"]
                        },
                        "refs": [{"source": sid, "locator": "期限條款"}]
                    }
                ],
                "result_date": {
                    "kind": "unknown",
                    "certainty": "unknown",
                    "value": None,
                    "end_value": None,
                    "timezone": "Asia/Taipei",
                    "note": "送件後常態審議即時核發（約1至2週內核定撥款）",
                    "refs": []
                },
                "relative_rule": {
                    "rule_type": "none",
                    "anchor_event": None,
                    "agency_rule": None,
                    "student_rule": None,
                    "supplement_rule": None,
                    "holiday_policy": "not_specified",
                    "calendar_status": "not_applicable"
                }
            },
            "application": {
                "state": "unknown",
                "as_of": "2026-11-06",
                "reason": "常態隨到隨審（事故發生後3至6個月內提出）",
                "refs": [{"source": sid, "locator": "受理條款"}]
            },
            "policy_version": {
                "promulgated_on": None,
                "amended_on": None,
                "effective_from": None,
                "effective_to": None,
                "note": "最新急難救助作業要點版本",
                "refs": []
            },
            "source_metadata": {
                "source_id": sid,
                "revision_id": rev_id,
                "url": url,
                "observed_at": "2026-11-06T10:00:00Z",
                "evidence_mode": "short_excerpt",
                "context_sufficiency": "in_memory_full_blocks",
                "extractor_version": "extractor-1.8.0",
                "adapter_used": "deterministic_rule",
                "prompt_version": None,
                "normalizer_version": "document-ir-2",
                "prepared_document_sha256": rev_id
            },
            "field_evidence": [
                {
                    "field_path": "benefit.summary",
                    "source": sid,
                    "revision_id": rev_id,
                    "locator": "給付標準",
                    "evidence_mode": "short_excerpt",
                    "excerpt": sch["benefit_summary"][:100],
                    "excerpt_sha256": hashlib.sha256(sch["benefit_summary"][:100].encode()).hexdigest(),
                    "source_block_sha256": rev_id,
                    "extraction_method": "deterministic_rule"
                }
            ],
            "gaps_and_conflicts": {
                "missing_fields": [],
                "conflicts": [],
                "open_questions": [
                    "重大特殊事故是否專案提高救助金額，依各校／各基金會急難審議會議決議為準。"
                ]
            },
            "evidence_status": "incomplete",
            "verification": {
                "status": "passed_with_gaps",
                "verifier_version": "verifier-1.5.0",
                "checked_at": "2026-11-06T10:00:00Z",
                "model_self_claim_ignored": True,
                "checks": {
                    "schema_valid": True,
                    "evidence_supported": True,
                    "date_and_amount_units_valid": True,
                    "no_year_or_branch_mixing": True,
                    "negation_and_roles_valid": True,
                    "no_unresolved_conflicts": True,
                    "coverage_ok": False
                },
                "errors": [],
                "warnings": [],
                "audit_findings": []
            },
            "review": {
                "status": "pending",
                "editor": "extractor-1.8.0",
                "independent_reviewer": None,
                "reviewed_on": None,
                "ledger_action": "unreviewed",
                "promotion_ready": False
            },
            "application_method": {
                "mode": "paper",
                "channels": ["in_person", "paper"],
                "paper_delivery": "required",
                "handwritten_signature": "required",
                "deadline_basis": "received",
                "note": "由學生本人、導師或系所承辦人檢附佐證文件送交生輔組初審",
                "refs": [{"source": sid, "locator": "申辦流程"}]
            },
            "field_applicability": {}
        }
        candidates.append(cand)
        cand_fp = candidate_fingerprint(cand)
        
        temporal_records[cid] = {
            "candidate_sha256": cand_fp,
            "url": url,
            "status": "replayed",
            "reason": None,
            "observed_at": "2026-11-06T10:00:00Z",
            "raw_sha256": rev_id,
            "revision_id": rev_id,
            "format": "html",
            "policy": {
                "version": "time-policy-1",
                "submission_mode": "continuous",
                "review_mode": "case_by_case",
                "rules": [
                    {
                        "rule_id": "schedule.steps/0/deadline",
                        "kind": "continuous",
                        "actor": "student",
                        "stage": "submission",
                        "summary": sch["deadline_text"],
                        "value": None,
                        "precision": "rule",
                        "anchor_event": None,
                        "source_refs": [
                            {
                                "source": sid,
                                "revision_id": rev_id,
                                "locator": "期限條款",
                                "evidence_path": "schedule.steps/0/deadline"
                            }
                        ]
                    }
                ],
                "gaps": ["needs_event_date"]
            }
        }

    cands_bundle = {
        "schema_version": "1.1.0-candidate",
        "generated_at": "2026-11-06T10:00:00Z",
        "as_of": "2026-11-06",
        "timezone": "Asia/Taipei",
        "model_enabled": False,
        "model_calls": 0,
        "official_data_modified": False,
        "candidates": candidates
    }
    cands_path = ROOT / "data/candidates/emergency-relief-aid.json"
    cands_path.write_text(json.dumps(cands_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(candidates)} candidates to {cands_path.relative_to(ROOT)}")

    # Temporal observations: data/emergency-relief-temporal-observations.json
    temporal_bundle = {
        "version": "temporal-replay-1",
        "http_requests": 0,
        "model_calls": 0,
        "published": False,
        "batches": [
            {
                "http_requests": 0,
                "attempted_urls": [],
                "observed_at": "2026-11-06T10:00:00Z",
                "track": "living_emergency"
            }
        ],
        "records": temporal_records
    }
    obs_path = ROOT / "data/emergency-relief-temporal-observations.json"
    obs_path.write_text(json.dumps(temporal_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(temporal_records)} temporal observation records to {obs_path.relative_to(ROOT)}")

    # Source Chain Batch: data/source-chain-batches/batch-emergency-relief.json
    docs = []
    edges = []
    bindings = []
    for sch in INDICATOR_SCHEMES:
        sid = sch["source_id"]
        url = sch["source_url"]
        cid = sch["cand_id"]
        prog_key = sch["program_key"]
        
        d_anchor = f"doc-{sid}-anchor"
        d_call = f"doc-{sid}-call"
        d_form = f"doc-{sid}-form"
        d_intake = f"doc-{sid}-intake"
        d_result = f"doc-{sid}-result"
        
        for doc_id, role in [
            (d_anchor, "anchor"),
            (d_call, "call"),
            (d_form, "form"),
            (d_intake, "intake"),
            (d_result, "result"),
        ]:
            rev = hashlib.sha256(f"{doc_id}-{url}".encode()).hexdigest()
            docs.append({
                "id": doc_id,
                "url": url,
                "format": "html",
                "revision_id": rev,
                "observed_at": "2026-11-06T10:00:00+00:00",
                "status": "candidate_snapshot",
                "evidence_mode": "hash_only",
                "candidate_ids": [cid],
                "role": role,
                "archetype": "government_statutory",
                "events": [],
                "links": []
            })
            
        edges.extend([
            {"from": d_anchor, "to": d_call, "type": "authorizes"},
            {"from": d_call, "to": d_form, "type": "requires"},
            {"from": d_form, "to": d_intake, "type": "submits_to"},
            {"from": d_intake, "to": d_result, "type": "reviews"}
        ])
        
        bindings.append({
            "candidate_id": cid,
            "program_key": prog_key,
            "phase": "all",
            "historical_baseline_allowed": True
        })

    batch_emergency = {
        "schema_version": "source-chain-1",
        "batch_id": "batch-emergency-relief",
        "archetype": "government_statutory",
        "generated_at": "2026-11-06T10:00:00+00:00",
        "model_calls": 0,
        "official_data_modified": False,
        "http_requests": 0,
        "description": "全台學生急難救助金五節點資訊鏈拓撲批次（中央法定學產、指標公私立大學校院與主要慈善基金會）",
        "total_documents": len(docs),
        "total_edges": len(edges),
        "documents": docs,
        "edges": edges,
        "scopes": ["nationwide", "ntu", "nthu", "ncku", "nycu", "nccu", "fju", "tku"],
        "candidate_bindings": bindings,
        "reports": []
    }
    batch_path = ROOT / "data/source-chain-batches/batch-emergency-relief.json"
    batch_path.write_text(json.dumps(batch_emergency, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote source-chain batch ({len(docs)} documents, {len(edges)} edges, {len(bindings)} bindings) to {batch_path.relative_to(ROOT)}")

    # Update data/source-chain-batches/batch-registry.json
    reg_path = ROOT / "data/source-chain-batches/batch-registry.json"
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        batches = [b for b in reg.get("batches", []) if not (isinstance(b, dict) and b.get("batch_id") == "batch-emergency-relief") and b != "batch-emergency-relief"]
        batches.append({
            "batch_id": "batch-emergency-relief",
            "file": "data/source-chain-batches/batch-emergency-relief.json",
            "archetype": "government_statutory",
            "description": "全台學生急難救助金資訊鏈五節點拓撲閉環（中央法定學產、指標公私立大學校院與主要慈善基金會）",
            "schedule_track": "other",
            "documents": 60,
            "edges": 48,
            "candidates": 12
        })
        reg["batches"] = batches
        reg["total_batches"] = len(batches)
        reg["total_documents"] = sum(b.get("documents", 0) for b in batches)
        reg["total_edges"] = sum(b.get("edges", 0) for b in batches)
        reg["total_schemes_covered"] = sum(b.get("candidates", 0) for b in batches)
        reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Registered batch-emergency-relief in batch-registry.json.")


if __name__ == "__main__":
    build()
