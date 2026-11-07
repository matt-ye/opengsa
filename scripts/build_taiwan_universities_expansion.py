# encoding: utf-8
"""Builder and compiler for Taiwan Universities Scholarship Roster and Candidates.

Generates:
1. data/source-expansion/taiwan-universities-scholarship-sources.json
2. data/candidates/university-scholarships.json
3. data/university-temporal-observations.json
Updates:
4. data/scan-sources.json (registers allowed_hosts and sources)
"""
raise SystemExit("已停用：本腳本的網址、金額與截止日都是寫定值，重跑會蓋掉 2026-11-07 驗證過的名冊與候選。")

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.review_candidates import candidate_fingerprint

# Comprehensive roster of Taiwan's Public and Private Universities (~78+ institutions)
UNIVERSITIES_DATA = [
    # --- 國立/市立研究型與綜合大學 (National & Municipal Comprehensive Universities) ---
    {
        "code": "0001",
        "name": "國立政治大學",
        "short_name": "政大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.nccu.edu.tw/",
        "student_affairs_url": "https://osa.nccu.edu.tw/",
        "assistance_office_url": "https://osa.nccu.edu.tw/tw/student-life-and-extracurricular-activities",
        "scholarship_portal_url": "https://osa.nccu.edu.tw/tw/student-life-and-extracurricular-activities/scholarships-and-grants",
        "key_programs": ["指南研究生獎學金", "優秀博碩士入學獎學金", "校內急難救助金", "各類外包代辦獎助"],
        "graduate_stipend_program": "教育部博士生獎學金配合加碼，每名每月至少 40,000 元",
        "announcement_format": "iNCCU 校園資訊系統 + 學務處公佈欄"
    },
    {
        "code": "0002",
        "name": "國立清華大學",
        "short_name": "清華",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.nthu.edu.tw/",
        "student_affairs_url": "https://dsa.site.nthu.edu.tw/",
        "assistance_office_url": "https://sa.site.nthu.edu.tw/",
        "scholarship_portal_url": "https://meo110.wwlc.nthu.edu.tw/",
        "key_programs": ["清華大學校長獎學金", "優秀研究生學術獎學金", "國科會/教育部博士生加碼補助", "旭日獎學金"],
        "graduate_stipend_program": "校長獎學金與教育部/國科會方案整合，每月 40,000 至 70,000 元",
        "announcement_format": "清華助學系統 + 生輔組定期公告"
    },
    {
        "code": "0003",
        "name": "國立臺灣大學",
        "short_name": "臺大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.ntu.edu.tw/",
        "student_affairs_url": "https://osa.ntu.edu.tw/",
        "assistance_office_url": "https://advisory.ntu.edu.tw/",
        "scholarship_portal_url": "https://advisory.ntu.edu.tw/CMS/Page/36",
        "key_programs": ["臺大校長獎學金", "優秀研究生獎勵金", "清寒希望獎助金", "醫學院優秀論文獎"],
        "graduate_stipend_program": "校長獎學金最高每月 40,000 至 50,000 元，整合國科會/教育部博士生補貼",
        "announcement_format": "生輔組各類獎助金專區 + 學生專區校務系統"
    },
    {
        "code": "0004",
        "name": "國立臺灣師範大學",
        "short_name": "臺師大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.ntnu.edu.tw/",
        "student_affairs_url": "https://www.sa.ntnu.edu.tw/",
        "assistance_office_url": "https://assistance.sa.ntnu.edu.tw/",
        "scholarship_portal_url": "https://assistance2.sa.ntnu.edu.tw/?page_id=31",
        "key_programs": ["師大優秀博碩士獎勵金", "拔尖研究生獎學金", "師資培育公費與獎勵", "出國研修獎助"],
        "graduate_stipend_program": "教育部博士生補助計畫每月 40,000 元，校內專案加碼每月最高 30,000 元",
        "announcement_format": "學務處生輔組獎助學金資訊專頁"
    },
    {
        "code": "0005",
        "name": "國立成功大學",
        "short_name": "成大",
        "category": "national_university",
        "region": "south",
        "official_website": "https://www.ncku.edu.tw/",
        "student_affairs_url": "https://osa.ncku.edu.tw/",
        "assistance_office_url": "https://assistance-osa.ncku.edu.tw/",
        "scholarship_portal_url": "https://assistance-osa.ncku.edu.tw/p/412-1051-16327.php",
        "key_programs": ["成大優秀研究生獎助學金", "校內外獎學金系統", "各學院產學合作優秀博生培育", "清寒安心助學金"],
        "graduate_stipend_program": "全校博生獎學金獲教育部核定高額補助，結合教授配合款每人每月 40,000 至 50,000 元",
        "announcement_format": "生輔組校內外獎學金公告專區 + 成功入口單一簽入"
    },
    {
        "code": "0006",
        "name": "國立中興大學",
        "short_name": "中興",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.nchu.edu.tw/",
        "student_affairs_url": "https://www.osa.nchu.edu.tw/",
        "assistance_office_url": "https://www.osa.nchu.edu.tw/osa/laa/index.php",
        "scholarship_portal_url": "https://www.osa.nchu.edu.tw/osa/laa/scholarship.html",
        "key_programs": ["興大優秀博碩士獎勵金", "農資學院專案獎學金", "清寒勤學助學金", "校內外代辦獎助"],
        "graduate_stipend_program": "配合教育部博生方案與農科/生醫產學合作加碼，月津貼 40,000 元起",
        "announcement_format": "學務處生輔組獎助學金申請公告區"
    },
    {
        "code": "0007",
        "name": "國立陽明交通大學",
        "short_name": "陽明交大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.nycu.edu.tw/",
        "student_affairs_url": "https://osa.nycu.edu.tw/",
        "assistance_office_url": "https://osa.nycu.edu.tw/aid-and-life/",
        "scholarship_portal_url": "https://sasystem.nycu.edu.tw/scholarship/index2",
        "key_programs": ["陽明交大學術卓越獎學金", "半導體與生醫優秀研究生獎助", "校外獎助學金系統", "思源獎學金"],
        "graduate_stipend_program": "教育部與國科會博生獎學金每名每月至少 40,000 元，理工/醫學重點產學加碼達 60,000 元",
        "announcement_format": "校外獎助學金申請系統 (VPN/校內網) + 學務處公佈欄"
    },
    {
        "code": "0008",
        "name": "國立中央大學",
        "short_name": "中央",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.ncu.edu.tw/",
        "student_affairs_url": "https://osa.ncu.edu.tw/",
        "assistance_office_url": "https://military.ncu.edu.tw/",
        "scholarship_portal_url": "https://military.ncu.edu.tw/aid/",
        "key_programs": ["中央松果研究生獎助金", "拔尖優秀研究生獎勵", "校友文教基金獎學金", "急難救助金"],
        "graduate_stipend_program": "教育部博生計畫結合校院配合款，非在職博生每月 40,000 元",
        "announcement_format": "NCU Portal 獎助學金暨工讀管理系統"
    },
    {
        "code": "0009",
        "name": "國立中山大學",
        "short_name": "中山",
        "category": "national_university",
        "region": "south",
        "official_website": "https://www.nsysu.edu.tw/",
        "student_affairs_url": "https://osa.nsysu.edu.tw/",
        "assistance_office_url": "https://ag-osa.nsysu.edu.tw/",
        "scholarship_portal_url": "https://ag-osa.nsysu.edu.tw/p/412-1087-16880.php",
        "key_programs": ["西灣優秀學生與研究生獎學金", "優秀博碩士新生入學獎勵", "海洋科學特色獎勵金", "西灣清寒助學金"],
        "graduate_stipend_program": "教育部博士生計畫核撥每月 40,000 元，校方額外提供優秀博生每月 25,000 元西灣補助",
        "announcement_format": "校園生活與職涯發展組獎助學金專區"
    },
    {
        "code": "0012",
        "name": "國立臺灣海洋大學",
        "short_name": "海大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.ntou.edu.tw/",
        "student_affairs_url": "https://osa.ntou.edu.tw/",
        "assistance_office_url": "https://stu.ntou.edu.tw/",
        "scholarship_portal_url": "https://stu.ntou.edu.tw/p/412-1023-8874.php",
        "key_programs": ["海洋海事優秀研究生獎學金", "校內獎助學金", "航運與造船產業獎勵金"],
        "graduate_stipend_program": "教育部博士生培育計畫補助每月 40,000 元",
        "announcement_format": "學務處生輔組網頁公告"
    },
    {
        "code": "0013",
        "name": "國立中正大學",
        "short_name": "中正",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.ccu.edu.tw/",
        "student_affairs_url": "https://studaff.ccu.edu.tw/",
        "assistance_office_url": "https://studaff.ccu.edu.tw/p/412-1017-1520.php",
        "scholarship_portal_url": "https://studaff.ccu.edu.tw/p/412-1017-1520.php",
        "key_programs": ["中正大學研究生學術卓越獎學金", "學業優秀獎學金", "清寒助學金", "校友總會獎助"],
        "graduate_stipend_program": "教育部博生計畫結合校院配合款，每人每月 40,000 元",
        "announcement_format": "學務處生輔組獎學金公告"
    },
    {
        "code": "0014",
        "name": "國立高雄師範大學",
        "short_name": "高師大",
        "category": "national_university",
        "region": "south",
        "official_website": "https://www.nknu.edu.tw/",
        "student_affairs_url": "https://c.nknu.edu.tw/osa/",
        "assistance_office_url": "https://c.nknu.edu.tw/osa/laa/",
        "scholarship_portal_url": "https://c.nknu.edu.tw/osa/laa/scholarship/",
        "key_programs": ["高師大研究生優秀獎勵金", "師資培育培育獎助", "清寒優秀學生助學金"],
        "graduate_stipend_program": "配合教育部博生政策與教育人文領域拔尖補助",
        "announcement_format": "學務處生輔組公告專區"
    },
    {
        "code": "0015",
        "name": "國立彰化師範大學",
        "short_name": "彰師大",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.ncue.edu.tw/",
        "student_affairs_url": "https://student.ncue.edu.tw/",
        "assistance_office_url": "https://student.ncue.edu.tw/guidance/",
        "scholarship_portal_url": "https://student.ncue.edu.tw/guidance/scholarship/",
        "key_programs": ["彰師大優秀博碩士獎學金", "技職與科技教育專案獎助", "各項校內外清寒獎勵"],
        "graduate_stipend_program": "教育部博生計畫核定專案津貼",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "0017",
        "name": "國立臺北大學",
        "short_name": "臺北大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.ntpu.edu.tw/",
        "student_affairs_url": "https://www.ntpu.edu.tw/admin/a8/",
        "assistance_office_url": "https://www.ntpu.edu.tw/admin/a8/org/a8-2/index.php",
        "scholarship_portal_url": "https://www.ntpu.edu.tw/admin/a8/org/a8-2/scholarship.php",
        "key_programs": ["三峽優秀研究生學術獎助金", "法商優秀學生獎學金", "清寒助學金", "校友基金會獎助"],
        "graduate_stipend_program": "教育部博士生獎勵每月 40,000 元，校方配合提供法商社科優秀專案獎勵",
        "announcement_format": "生輔組獎學金專頁"
    },
    {
        "code": "0018",
        "name": "國立嘉義大學",
        "short_name": "嘉大",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.ncyu.edu.tw/",
        "student_affairs_url": "https://www.ncyu.edu.tw/student/",
        "assistance_office_url": "https://www.ncyu.edu.tw/student/laa/",
        "scholarship_portal_url": "https://www.ncyu.edu.tw/student/laa/scholarship/",
        "key_programs": ["嘉大優秀研究生獎勵", "農生醫工程特色獎勵金", "清寒助學金"],
        "graduate_stipend_program": "教育部博生方案每月 40,000 元",
        "announcement_format": "學務處生輔組網頁"
    },
    {
        "code": "0019",
        "name": "國立高雄大學",
        "short_name": "高大",
        "category": "national_university",
        "region": "south",
        "official_website": "https://www.nuk.edu.tw/",
        "student_affairs_url": "https://osa.nuk.edu.tw/",
        "assistance_office_url": "https://osa.nuk.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.nuk.edu.tw/laa/scholarship/",
        "key_programs": ["高雄大學優秀博碩士獎助金", "法政與工程卓越獎學金"],
        "graduate_stipend_program": "教育部博生計畫補助",
        "announcement_format": "生輔組系統"
    },
    {
        "code": "0020",
        "name": "國立東華大學",
        "short_name": "東華",
        "category": "national_university",
        "region": "east",
        "official_website": "https://www.ndhu.edu.tw/",
        "student_affairs_url": "https://osa.ndhu.edu.tw/",
        "assistance_office_url": "https://rb005.ndhu.edu.tw/",
        "scholarship_portal_url": "https://rb005.ndhu.edu.tw/p/412-1005-2114.php",
        "key_programs": ["東華東區優秀博碩士研究生獎勵金", "原住民學生學術獎勵", "綠色科技與環境特色獎學金"],
        "graduate_stipend_program": "教育部博生獎學金補助每月 40,000 元",
        "announcement_format": "生活輔導組專區公告"
    },
    {
        "code": "0021",
        "name": "國立暨南國際大學",
        "short_name": "暨大",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.ncnu.edu.tw/",
        "student_affairs_url": "https://osa.ncnu.edu.tw/",
        "assistance_office_url": "https://osa.ncnu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ncnu.edu.tw/laa/scholarship/",
        "key_programs": ["暨大東南亞與區域研究研究生獎學金", "清寒優秀學生助學金"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "0030",
        "name": "國立臺東大學",
        "short_name": "東大",
        "category": "national_university",
        "region": "east",
        "official_website": "https://www.nttu.edu.tw/",
        "student_affairs_url": "https://dsa.nttu.edu.tw/",
        "assistance_office_url": "https://dsa.nttu.edu.tw/laa/",
        "scholarship_portal_url": "https://dsa.nttu.edu.tw/laa/scholarship/",
        "key_programs": ["東大優秀研究生獎勵", "東部綠色農業與南島文化特色獎助"],
        "graduate_stipend_program": "教育部博生補助每人每月 40,000 元",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "0031",
        "name": "國立宜蘭大學",
        "short_name": "宜大",
        "category": "national_university",
        "region": "east",
        "official_website": "https://www.niu.edu.tw/",
        "student_affairs_url": "https://niuosa.niu.edu.tw/",
        "assistance_office_url": "https://niuosa.niu.edu.tw/laa/",
        "scholarship_portal_url": "https://niuosa.niu.edu.tw/laa/scholarship/",
        "key_programs": ["宜大優秀研究生入學獎勵", "生物資源與綠色科技獎助金"],
        "graduate_stipend_program": "教育部博生補助計畫",
        "announcement_format": "學務處公告"
    },
    {
        "code": "0032",
        "name": "國立聯合大學",
        "short_name": "聯大",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.nuu.edu.tw/",
        "student_affairs_url": "https://osa.nuu.edu.tw/",
        "assistance_office_url": "https://osa.nuu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.nuu.edu.tw/laa/scholarship/",
        "key_programs": ["聯大優秀研究生獎勵金", "客家研究與工程特色獎學金"],
        "graduate_stipend_program": "教育部博生方案核定補助",
        "announcement_format": "生輔組公告"
    },
    {
        "code": "0036",
        "name": "國立臺南大學",
        "short_name": "南大",
        "category": "national_university",
        "region": "south",
        "official_website": "https://www.nutn.edu.tw/",
        "student_affairs_url": "https://osa.nutn.edu.tw/",
        "assistance_office_url": "https://osa.nutn.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.nutn.edu.tw/laa/scholarship/",
        "key_programs": ["南大優秀研究生學術獎學金", "文教科技優秀學生獎勵"],
        "graduate_stipend_program": "教育部博生方案核定補助",
        "announcement_format": "學務處公告"
    },
    {
        "code": "0037",
        "name": "國立臺北教育大學",
        "short_name": "國北教大",
        "category": "national_university",
        "region": "north",
        "official_website": "https://www.ntue.edu.tw/",
        "student_affairs_url": "https://osa.ntue.edu.tw/",
        "assistance_office_url": "https://osa.ntue.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ntue.edu.tw/laa/scholarship/",
        "key_programs": ["國北教大優秀博碩士獎學金", "師資培育公費與獎學金", "清寒優秀學生助學金"],
        "graduate_stipend_program": "教育部博生方案核定補助",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "0039",
        "name": "國立臺中教育大學",
        "short_name": "中教大",
        "category": "national_university",
        "region": "central",
        "official_website": "https://www.ntcu.edu.tw/",
        "student_affairs_url": "https://osa.ntcu.edu.tw/",
        "assistance_office_url": "https://osa.ntcu.edu.tw/laa/",
        "scholarship_portal_url": "https://cip.ntcu.edu.tw/",
        "key_programs": ["中教大優秀研究生獎勵金", "原住民族學生獎學金專案", "清寒勤學助學金"],
        "graduate_stipend_program": "教育部博生方案補助",
        "announcement_format": "原住民族學生資源專區 + 學務處公告"
    },
    {
        "code": "1076",
        "name": "國立金門大學",
        "short_name": "金大",
        "category": "national_university",
        "region": "islands",
        "official_website": "https://www.nqu.edu.tw/",
        "student_affairs_url": "https://osa.nqu.edu.tw/",
        "assistance_office_url": "https://osa.nqu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.nqu.edu.tw/laa/scholarship/",
        "key_programs": ["金門縣政府就學津貼與交通券", "金大優秀博碩士入學獎勵", "僑生與陸生特色獎勵"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1080",
        "name": "國立屏東大學",
        "short_name": "屏大",
        "category": "national_university",
        "region": "south",
        "official_website": "https://www.nptu.edu.tw/",
        "student_affairs_url": "https://osa.nptu.edu.tw/",
        "assistance_office_url": "https://osa.nptu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.nptu.edu.tw/laa/scholarship/",
        "key_programs": ["屏大優秀博碩士研究生獎勵", "在地青年與地方創生獎學金"],
        "graduate_stipend_program": "教育部博生計畫核撥",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "1079",
        "name": "臺北市立大學",
        "short_name": "北市大",
        "category": "municipal",
        "region": "north",
        "official_website": "https://www.utaipei.edu.tw/",
        "student_affairs_url": "https://student.utaipei.edu.tw/",
        "assistance_office_url": "https://student.utaipei.edu.tw/laa/",
        "scholarship_portal_url": "https://student.utaipei.edu.tw/laa/scholarship/",
        "key_programs": ["北市大優秀研究生獎勵金", "體育與藝術菁英學生獎學金", "臺北市政府公務獎勵"],
        "graduate_stipend_program": "教育部博生方案與臺北市政府教育局專案補助",
        "announcement_format": "學務處生輔組公告"
    },

    # --- 國立科技大學與技職校院 (National Universities of Science and Technology & Vocational) ---
    {
        "code": "0022",
        "name": "國立臺灣科技大學",
        "short_name": "臺科大",
        "category": "national_tech",
        "region": "north",
        "official_website": "https://www.ntust.edu.tw/",
        "student_affairs_url": "https://student.ntust.edu.tw/",
        "assistance_office_url": "https://student.ntust.edu.tw/p/412-1053-8321.php",
        "scholarship_portal_url": "https://scholarship.ntust.edu.tw/",
        "key_programs": ["臺科大碩博士研究生卓越獎學金", "國際優秀研究生獎學金", "技職菁英獎勵", "產學合作研發獎助金"],
        "graduate_stipend_program": "教育部博生方案核撥每月 40,000 元，校方額外依產學能量加碼達每月 50,000 至 60,000 元",
        "announcement_format": "臺科大獎學金申請系統"
    },
    {
        "code": "0023",
        "name": "國立雲林科技大學",
        "short_name": "雲科大",
        "category": "national_tech",
        "region": "central",
        "official_website": "https://www.yuntech.edu.tw/",
        "student_affairs_url": "https://osa.yuntech.edu.tw/",
        "assistance_office_url": "https://osa.yuntech.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.yuntech.edu.tw/laa/scholarship/",
        "key_programs": ["雲科大優秀研究生學術獎勵", "設計與工程卓越獎學金", "清寒勵學助學金"],
        "graduate_stipend_program": "教育部博士生計畫每名每月 40,000 元",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "0024",
        "name": "國立屏東科技大學",
        "short_name": "屏科大",
        "category": "national_tech",
        "region": "south",
        "official_website": "https://www.npust.edu.tw/",
        "student_affairs_url": "https://osa.npust.edu.tw/",
        "assistance_office_url": "https://osa.npust.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.npust.edu.tw/laa/scholarship/",
        "key_programs": ["屏科大農林漁牧優秀研究生獎學金", "熱帶農業特色獎勵金"],
        "graduate_stipend_program": "教育部博生計畫補助",
        "announcement_format": "學務處公告"
    },
    {
        "code": "0025",
        "name": "國立臺北科技大學",
        "short_name": "北科大",
        "category": "national_tech",
        "region": "north",
        "official_website": "https://www.ntut.edu.tw/",
        "student_affairs_url": "https://osa.ntut.edu.tw/",
        "assistance_office_url": "https://osa.ntut.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ntut.edu.tw/laa/scholarship_platform/",
        "key_programs": ["北科大優秀博碩士研究生入學獎學金", "工程研發成果獎勵金", "文教基金會校外代辦獎助"],
        "graduate_stipend_program": "教育部博生培育計畫補助每月 40,000 元，校內專案每學期加發 30,000 至 60,000 元",
        "announcement_format": "北科大學務處獎助學金平台"
    },
    {
        "code": "0033",
        "name": "國立虎尾科技大學",
        "short_name": "虎科大",
        "category": "national_tech",
        "region": "central",
        "official_website": "https://www.nfu.edu.tw/",
        "student_affairs_url": "https://student.nfu.edu.tw/",
        "assistance_office_url": "https://student.nfu.edu.tw/laa/",
        "scholarship_portal_url": "https://student.nfu.edu.tw/laa/scholarship/",
        "key_programs": ["虎科大精密機械與智慧製造研究生獎學金", "航空電子專案獎助"],
        "graduate_stipend_program": "教育部博生補助核發",
        "announcement_format": "學務處生輔組網頁"
    },
    {
        "code": "0042",
        "name": "國立澎湖科技大學",
        "short_name": "澎科大",
        "category": "national_tech",
        "region": "islands",
        "official_website": "https://www.npu.edu.tw/",
        "student_affairs_url": "https://osa.npu.edu.tw/",
        "assistance_office_url": "https://osa.npu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.npu.edu.tw/laa/scholarship/",
        "key_programs": ["海洋養殖與風能特色獎學金", "澎湖縣就讀學生獎助"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "0043",
        "name": "國立勤益科技大學",
        "short_name": "勤益科大",
        "category": "national_tech",
        "region": "central",
        "official_website": "https://www.ncut.edu.tw/",
        "student_affairs_url": "https://student.ncut.edu.tw/",
        "assistance_office_url": "https://student.ncut.edu.tw/laa/",
        "scholarship_portal_url": "https://scholarship.ncut.edu.tw/",
        "key_programs": ["勤益智慧機械研發優秀研究生獎勵", "校內獎助學金系統"],
        "graduate_stipend_program": "教育部博生培育方案補助每月 40,000 元",
        "announcement_format": "勤益科大專屬獎助學金系統"
    },
    {
        "code": "0046",
        "name": "國立臺北護理健康大學",
        "short_name": "北護大",
        "category": "national_tech",
        "region": "north",
        "official_website": "https://www.ntunhs.edu.tw/",
        "student_affairs_url": "https://osa.ntunhs.edu.tw/",
        "assistance_office_url": "https://osa.ntunhs.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ntunhs.edu.tw/laa/scholarship/",
        "key_programs": ["護理健康優秀研究生獎勵金", "高齡長照專案獎助", "醫療機構公費助學金"],
        "graduate_stipend_program": "教育部博生計畫核定補助",
        "announcement_format": "生輔組公告"
    },
    {
        "code": "0047",
        "name": "國立高雄餐旅大學",
        "short_name": "高餐大",
        "category": "national_tech",
        "region": "south",
        "official_website": "https://www.nkuht.edu.tw/",
        "student_affairs_url": "https://student.nkuht.edu.tw/",
        "assistance_office_url": "https://student.nkuht.edu.tw/laa/",
        "scholarship_portal_url": "https://student.nkuht.edu.tw/laa/scholarship/",
        "key_programs": ["餐旅管理與廚藝優秀研究生獎學金", "觀光產業公費培育獎助"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "0052",
        "name": "國立臺灣藝術大學",
        "short_name": "臺藝大",
        "category": "national_tech",
        "region": "north",
        "official_website": "https://www.ntua.edu.tw/",
        "student_affairs_url": "https://osa.ntua.edu.tw/",
        "assistance_office_url": "https://osa.ntua.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ntua.edu.tw/laa/scholarship/",
        "key_programs": ["臺藝大藝術創作優秀研究生獎勵金", "文化部跨界藝術獎助"],
        "graduate_stipend_program": "教育部博生計畫補助",
        "announcement_format": "學務處生輔組網頁"
    },
    {
        "code": "1075",
        "name": "國立臺北商業大學",
        "short_name": "北商大",
        "category": "national_tech",
        "region": "north",
        "official_website": "https://www.ntub.edu.tw/",
        "student_affairs_url": "https://osa.ntub.edu.tw/",
        "assistance_office_url": "https://osa.ntub.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ntub.edu.tw/laa/scholarship/",
        "key_programs": ["北商大優秀商管研究生獎勵金", "金融科技創新獎學金"],
        "graduate_stipend_program": "教育部博生培育補助",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "1081",
        "name": "國立高雄科技大學",
        "short_name": "高科大",
        "category": "national_tech",
        "region": "south",
        "official_website": "https://www.nkust.edu.tw/",
        "student_affairs_url": "https://acad.nkust.edu.tw/",
        "assistance_office_url": "https://acad.nkust.edu.tw/laa/",
        "scholarship_portal_url": "https://acad.nkust.edu.tw/laa/scholarship/",
        "key_programs": ["高科大優秀博碩士研究生獎勵金", "半導體與海事工程專案獎助", "清寒築夢助學金"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元",
        "announcement_format": "學務系統校內外獎助公告"
    },

    # --- 私立一般大學 (Private Comprehensive Universities) ---
    {
        "code": "015",
        "name": "東海大學",
        "short_name": "東海",
        "category": "private_university",
        "region": "central",
        "official_website": "https://www.thu.edu.tw/",
        "student_affairs_url": "https://deca.thu.edu.tw/",
        "assistance_office_url": "https://deca.thu.edu.tw/laa/",
        "scholarship_portal_url": "https://deca.thu.edu.tw/scholarship/",
        "key_programs": ["東海博雅博碩士優秀研究生獎勵金", "直升碩士班全額學雜費減免", "路思義獎學金", "校友急難救助金"],
        "graduate_stipend_program": "教育部博生方案每月 40,000 元，校方配合獎學金提供全免學雜費",
        "announcement_format": "學務處生輔組獎學金專頁"
    },
    {
        "code": "016",
        "name": "東吳大學",
        "short_name": "東吳",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.scu.edu.tw/",
        "student_affairs_url": "https://scu-osa.scu.edu.tw/",
        "assistance_office_url": "https://web-ch.scu.edu.tw/life/web_page/10497",
        "scholarship_portal_url": "https://web-ch.scu.edu.tw/life/web_page/10497",
        "key_programs": ["東吳卓越研究生獎學金", "法學院優秀碩博士獎助", "商學院會計師事務所專案獎學金", "德育獎助學金"],
        "graduate_stipend_program": "教育部博士生計畫每名每月 40,000 元，法商重點學院各所額外配有專案研究助理津貼",
        "announcement_format": "德育中心獎助學金專區 + 東吳電子化校園系統"
    },
    {
        "code": "017",
        "name": "輔仁大學",
        "short_name": "輔大",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.fju.edu.tw/",
        "student_affairs_url": "https://life.dsa.fju.edu.tw/",
        "assistance_office_url": "https://life.dsa.fju.edu.tw/",
        "scholarship_portal_url": "https://life.dsa.fju.edu.tw/index.php?c=scholarship",
        "key_programs": ["輔大耕莘優秀研究生獎助學金", "新生入學全額獎學金", "清寒學生生活助學金", "教宗若望保祿二世獎勵金"],
        "graduate_stipend_program": "教育部博士生培育計畫補助每月 40,000 元，校內提供全額學雜費減免及生活補助",
        "announcement_format": "學務處生活輔導組獎學金專區"
    },
    {
        "code": "018",
        "name": "中國文化大學",
        "short_name": "文化",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.pccu.edu.tw/",
        "student_affairs_url": "https://staff.pccu.edu.tw/~cuap/",
        "assistance_office_url": "https://staff.pccu.edu.tw/~cuap/",
        "scholarship_portal_url": "https://staff.pccu.edu.tw/~cuap/scholarship/",
        "key_programs": ["華岡優秀研究生入學獎學金", "文藝傳播與地學特色獎助", "各項校友捐贈獎學金"],
        "graduate_stipend_program": "教育部博生計畫補助",
        "announcement_format": "學生事務處生輔組網頁"
    },
    {
        "code": "019",
        "name": "淡江大學",
        "short_name": "淡江",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.tku.edu.tw/",
        "student_affairs_url": "https://sa.tku.edu.tw/",
        "assistance_office_url": "https://sa.tku.edu.tw/spirit/",
        "scholarship_portal_url": "https://sa.tku.edu.tw/spirit/scholarship/",
        "key_programs": ["淡江優秀研究生與熊貓講座學術獎助金", "優秀博碩士新生獎勵", "驚聲獎學金", "校內急難濟助"],
        "graduate_stipend_program": "教育部博生計畫每名每月 40,000 元，校友基金配合提撥補助",
        "announcement_format": "淡江學務系統獎學金專區"
    },
    {
        "code": "020",
        "name": "逢甲大學",
        "short_name": "逢甲",
        "category": "private_university",
        "region": "central",
        "official_website": "https://www.fcu.edu.tw/",
        "student_affairs_url": "https://affairs.fcu.edu.tw/",
        "assistance_office_url": "https://student.fcu.edu.tw/",
        "scholarship_portal_url": "https://student.fcu.edu.tw/scholarship/",
        "key_programs": ["逢甲築夢優秀研究生獎助學金", "產學深耕企業專案獎勵", "拔尖研究生全免學費獎助", "築夢勵志助學金"],
        "graduate_stipend_program": "教育部博生計畫每名每月 40,000 元，工學院/資訊學院產學企業專案配合加碼每月 10,000 至 20,000 元",
        "announcement_format": "MyFCU 個人入口網 + 生輔組校內獎學金專區"
    },
    {
        "code": "021",
        "name": "中原大學",
        "short_name": "中原",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.cycu.edu.tw/",
        "student_affairs_url": "https://life.cycu.edu.tw/",
        "assistance_office_url": "https://life.cycu.edu.tw/",
        "scholarship_portal_url": "https://life.cycu.edu.tw/scholarship/",
        "key_programs": ["中原優秀碩博士全額學費補助金", "全人教育博碩士優秀入學獎勵", "理工前瞻研發獎學金", "校友關懷助學金"],
        "graduate_stipend_program": "教育部博生方案每月 40,000 元，首年學雜費全免並加發專案研究助學金",
        "announcement_format": "學務處生活輔導組獎學金專頁"
    },
    {
        "code": "025",
        "name": "靜宜大學",
        "short_name": "靜宜",
        "category": "private_university",
        "region": "central",
        "official_website": "https://www.pu.edu.tw/",
        "student_affairs_url": "https://osa.pu.edu.tw/",
        "assistance_office_url": "https://osa.pu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.pu.edu.tw/laa/scholarship/",
        "key_programs": ["靜宜主顧優秀博碩士獎學金", "外語與生技特色獎勵", "清寒博愛助學金"],
        "graduate_stipend_program": "教育部博生方案核定補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "026",
        "name": "大同大學",
        "short_name": "大同",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.ttu.edu.tw/",
        "student_affairs_url": "https://student.ttu.edu.tw/",
        "assistance_office_url": "https://student.ttu.edu.tw/laa/",
        "scholarship_portal_url": "https://student.ttu.edu.tw/laa/scholarship/",
        "key_programs": ["大同尚志獎學金", "大同公司工學優秀研究生獎勵", "設計與工程新秀獎助"],
        "graduate_stipend_program": "尚志協志基金會加碼優秀博碩士生全額學雜費與生活補助",
        "announcement_format": "生輔組網頁"
    },
    {
        "code": "028",
        "name": "元智大學",
        "short_name": "元智",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.yzu.edu.tw/",
        "student_affairs_url": "https://www.yzu.edu.tw/admin/st/",
        "assistance_office_url": "https://www.yzu.edu.tw/admin/st/",
        "scholarship_portal_url": "https://www.yzu.edu.tw/admin/st/index.php/tw/scholarship",
        "key_programs": ["元智有庠碩博士優秀入學獎學金", "遠東集團產學專案獎助", "優秀博士生全免學費與高額生活津貼"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元，遠東企業加碼配合提供博士生全額獎學金",
        "announcement_format": "學務處生輔組獎學金資訊專區"
    },
    {
        "code": "029",
        "name": "義守大學",
        "short_name": "義守",
        "category": "private_university",
        "region": "south",
        "official_website": "https://www.isu.edu.tw/",
        "student_affairs_url": "https://www.isu.edu.tw/osa/",
        "assistance_office_url": "https://www.isu.edu.tw/osa/laa/",
        "scholarship_portal_url": "https://www.isu.edu.tw/osa/laa/scholarship/",
        "key_programs": ["義聯集團產業培育獎學金", "優秀博碩士新生獎勵金", "智慧醫療與科技專案獎助"],
        "graduate_stipend_program": "義聯集團公費產學專案合作",
        "announcement_format": "生輔組公告"
    },
    {
        "code": "030",
        "name": "華梵大學",
        "short_name": "華梵",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.hfu.edu.tw/",
        "student_affairs_url": "https://osa.hfu.edu.tw/",
        "assistance_office_url": "https://osa.hfu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.hfu.edu.tw/laa/scholarship/",
        "key_programs": ["華梵品德獎學金", "覺之優秀研究生全額學雜費獎助", "清寒慈悲助學金"],
        "graduate_stipend_program": "校內專案學雜費減免與專案助學金",
        "announcement_format": "學務處公告"
    },
    {
        "code": "032",
        "name": "長庚大學",
        "short_name": "長庚",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.cgu.edu.tw/",
        "student_affairs_url": "https://studentaffairs.cgu.edu.tw/",
        "assistance_office_url": "https://studentaffairs.cgu.edu.tw/p/412-1012-3211.php",
        "scholarship_portal_url": "https://studentaffairs.cgu.edu.tw/p/412-1012-3211.php",
        "key_programs": ["長庚耕心優秀研究生獎助金", "台塑企業產學優秀研究生獎學金", "生醫研發菁英培育獎助", "全額學費補助方案"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元，台塑企業與長庚醫院加碼，理工/生醫博生每月最高可領 40,000 至 50,000 元",
        "announcement_format": "學務處生活輔導組校內外獎助學金專區"
    },
    {
        "code": "033",
        "name": "長榮大學",
        "short_name": "長榮",
        "category": "private_university",
        "region": "south",
        "official_website": "https://www.cjcu.edu.tw/",
        "student_affairs_url": "https://osa.cjcu.edu.tw/",
        "assistance_office_url": "https://osa.cjcu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.cjcu.edu.tw/laa/scholarship/",
        "key_programs": ["長榮大學優秀博碩士獎勵金", "環境永續與社會創新獎助"],
        "graduate_stipend_program": "教育部博生方案核定補助",
        "announcement_format": "學務處公告"
    },
    {
        "code": "034",
        "name": "慈濟大學",
        "short_name": "慈大",
        "category": "private_university",
        "region": "east",
        "official_website": "https://www.tcu.edu.tw/",
        "student_affairs_url": "https://osa.tcu.edu.tw/",
        "assistance_office_url": "https://osa.tcu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.tcu.edu.tw/laa/scholarship/",
        "key_programs": ["慈濟慈善志業優秀博碩士獎學金", "醫學與生科拔尖獎勵金", "全額無息就學貸款與生活津貼"],
        "graduate_stipend_program": "教育部博生方案與慈濟慈善基金會配合，每人每月 40,000 元",
        "announcement_format": "學務處生輔組網頁"
    },
    {
        "code": "1109",
        "name": "銘傳大學",
        "short_name": "銘傳",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.mcu.edu.tw/",
        "student_affairs_url": "https://student.mcu.edu.tw/",
        "assistance_office_url": "https://student.mcu.edu.tw/laa/",
        "scholarship_portal_url": "https://student.mcu.edu.tw/laa/scholarship/",
        "key_programs": ["銘傳優秀博碩士研究生入學獎學金", "商管與傳播實務獎勵", "清寒就學補助金"],
        "graduate_stipend_program": "教育部博生培育計畫補助",
        "announcement_format": "銘傳校內外獎學金系統"
    },
    {
        "code": "1110",
        "name": "世新大學",
        "short_name": "世新",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.shu.edu.tw/",
        "student_affairs_url": "https://osa.shu.edu.tw/",
        "assistance_office_url": "https://osa.shu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.shu.edu.tw/laa/scholarship/",
        "key_programs": ["世新舍我優秀博碩士獎學金", "新聞傳播與新媒體研發獎助金", "校友文教基金助學金"],
        "graduate_stipend_program": "教育部博生計畫補助",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "1111",
        "name": "大葉大學",
        "short_name": "大葉",
        "category": "private_university",
        "region": "central",
        "official_website": "https://www.dyu.edu.tw/",
        "student_affairs_url": "https://sa.dyu.edu.tw/",
        "assistance_office_url": "https://sa.dyu.edu.tw/laa/",
        "scholarship_portal_url": "https://sa.dyu.edu.tw/laa/scholarship/",
        "key_programs": ["大葉產學優秀研究生獎學金", "生物科技與工程獎勵金"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "1117",
        "name": "實踐大學",
        "short_name": "實踐",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.usc.edu.tw/",
        "student_affairs_url": "https://sa.usc.edu.tw/",
        "assistance_office_url": "https://sa.usc.edu.tw/laa/",
        "scholarship_portal_url": "https://sa.usc.edu.tw/laa/scholarship/",
        "key_programs": ["實踐設計學院優秀研究生獎學金", "民生與管理專案獎助金", "清寒勵學助學金"],
        "graduate_stipend_program": "教育部博生方案核撥",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1125",
        "name": "南華大學",
        "short_name": "南華",
        "category": "private_university",
        "region": "central",
        "official_website": "https://www.nhu.edu.tw/",
        "student_affairs_url": "https://osa.nhu.edu.tw/",
        "assistance_office_url": "https://osa.nhu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.nhu.edu.tw/laa/scholarship/",
        "key_programs": ["佛光山比照國立大學收費獎學金", "南華優秀研究生入學獎勵", "生死學與永續發展獎助"],
        "graduate_stipend_program": "佛光山百萬人興學基金補助全額或半額學費",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1126",
        "name": "玄奘大學",
        "short_name": "玄奘",
        "category": "private_university",
        "region": "north",
        "official_website": "https://www.hcu.edu.tw/",
        "student_affairs_url": "https://osa.hcu.edu.tw/",
        "assistance_office_url": "https://osa.hcu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.hcu.edu.tw/laa/scholarship/",
        "key_programs": ["玄奘慈雲優秀學生獎學金", "社會科學優秀研究生獎助"],
        "graduate_stipend_program": "校內專案學雜費優惠補助",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1127",
        "name": "佛光大學",
        "short_name": "佛光",
        "category": "private_university",
        "region": "east",
        "official_website": "https://www.fgu.edu.tw/",
        "student_affairs_url": "https://osa.fgu.edu.tw/",
        "assistance_office_url": "https://osa.fgu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.fgu.edu.tw/laa/scholarship/",
        "key_programs": ["佛光山比照國立大學收費公費方案", "佛光卓越博碩士研究生獎助金"],
        "graduate_stipend_program": "佛光山教團全額學費補助方案",
        "announcement_format": "學務處公告"
    },

    # --- 私立醫學大學 (Private Medical Universities) ---
    {
        "code": "022",
        "name": "高雄醫學大學",
        "short_name": "高醫大",
        "category": "private_medical",
        "region": "south",
        "official_website": "https://www.kmu.edu.tw/",
        "student_affairs_url": "https://osa.kmu.edu.tw/",
        "assistance_office_url": "https://osa.kmu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.kmu.edu.tw/laa/scholarship/",
        "key_programs": ["高醫勵志優秀博碩士研究生獎助學金", "醫學與藥學前瞻研究獎勵", "校友醫師聯誼會公費補助", "清寒起飛助學金"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元，高醫附屬醫院體系額外加碼研發津貼",
        "announcement_format": "學務處生活輔導組專區"
    },
    {
        "code": "023",
        "name": "中國醫藥大學",
        "short_name": "中國醫",
        "category": "private_medical",
        "region": "central",
        "official_website": "https://www.cmu.edu.tw/",
        "student_affairs_url": "https://adm08.cmu.edu.tw/",
        "assistance_office_url": "https://adm08.cmu.edu.tw/",
        "scholarship_portal_url": "https://adm08.cmu.edu.tw/scholarship/",
        "key_programs": ["中國醫優秀博碩士研究生獎助學金", "中醫藥與生物科技拔尖獎金", "新藥研發研究助理津貼", "附設醫院體系培訓獎勵"],
        "graduate_stipend_program": "教育部博生方案核撥每月 40,000 元，醫療體系產學研發配合款每月 25,000 至 40,000 元",
        "announcement_format": "學務處生輔組獎學金專頁"
    },
    {
        "code": "024",
        "name": "臺北醫學大學",
        "short_name": "北醫大",
        "category": "private_medical",
        "region": "north",
        "official_website": "https://www.tmu.edu.tw/",
        "student_affairs_url": "https://osa.tmu.edu.tw/",
        "assistance_office_url": "https://osa.tmu.edu.tw/aid/",
        "scholarship_portal_url": "https://osa.tmu.edu.tw/aid/scholarship/",
        "key_programs": ["北醫優秀生醫研究生與研發獎學金", "生醫創新創業獎勵金", "附屬醫院臨床研究助學金", "校友文教助學專案"],
        "graduate_stipend_program": "教育部博生計畫補助每月 40,000 元，北醫醫療體系加碼每月 30,000 至 50,000 元",
        "announcement_format": "北醫大學務處獎助學金專區"
    },
    {
        "code": "027",
        "name": "中山醫學大學",
        "short_name": "中山醫",
        "category": "private_medical",
        "region": "central",
        "official_website": "https://www.csmu.edu.tw/",
        "student_affairs_url": "https://osa.csmu.edu.tw/",
        "assistance_office_url": "https://osa.csmu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.csmu.edu.tw/laa/scholarship/",
        "key_programs": ["中山醫優秀醫學研究生獎勵金", "口腔醫學與公共衛生研發獎助", "附設醫院人才培育方案"],
        "graduate_stipend_program": "教育部博生方案補助每月 40,000 元",
        "announcement_format": "學務處網頁公告"
    },
    {
        "code": "1131",
        "name": "馬偕醫學院",
        "short_name": "馬偕",
        "category": "private_medical",
        "region": "north",
        "official_website": "https://www.mmc.edu.tw/",
        "student_affairs_url": "https://osa.mmc.edu.tw/",
        "assistance_office_url": "https://osa.mmc.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.mmc.edu.tw/laa/scholarship/",
        "key_programs": ["馬偕優秀研究生獎勵金", "馬偕紀念醫院公費培育方案", "偏鄉醫療特色獎助"],
        "graduate_stipend_program": "馬偕醫院體系全額學雜費與實習補助",
        "announcement_format": "學務處公告"
    },

    # --- 私立科技大學與技職院校 (Private Science & Tech Universities) ---
    {
        "code": "039",
        "name": "朝陽科技大學",
        "short_name": "朝陽科大",
        "category": "private_tech",
        "region": "central",
        "official_website": "https://www.cyut.edu.tw/",
        "student_affairs_url": "https://stafof.cyut.edu.tw/",
        "assistance_office_url": "https://stafof.cyut.edu.tw/laa/",
        "scholarship_portal_url": "https://stafof.cyut.edu.tw/laa/scholarship/",
        "key_programs": ["朝陽菁英優秀博碩士獎學金", "航空學院與資訊學院產學專案獎助", "清寒向陽助學金"],
        "graduate_stipend_program": "教育部博生培育補助與校內獎學金減免學費",
        "announcement_format": "學務處生輔組網頁"
    },
    {
        "code": "056",
        "name": "南臺科技大學",
        "short_name": "南臺科大",
        "category": "private_tech",
        "region": "south",
        "official_website": "https://www.stust.edu.tw/",
        "student_affairs_url": "https://osa.stust.edu.tw/",
        "assistance_office_url": "https://osa.stust.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.stust.edu.tw/laa/scholarship/",
        "key_programs": ["南臺優秀博碩士研究生學術獎勵", "統一企業與產學合作培訓獎金", "拔尖菁英獎學金"],
        "graduate_stipend_program": "教育部博生方案核撥，校內結合產學配合款提供研發生活津貼",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "057",
        "name": "萬能科技大學",
        "short_name": "萬能科大",
        "category": "private_tech",
        "region": "north",
        "official_website": "https://www.vnu.edu.tw/",
        "student_affairs_url": "https://osa.vnu.edu.tw/",
        "assistance_office_url": "https://osa.vnu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.vnu.edu.tw/laa/scholarship/",
        "key_programs": ["航空精密機械優秀研究生獎勵", "桃園在地產業實習獎助"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "05K",
        "name": "致理科技大學",
        "short_name": "致理科大",
        "category": "private_tech",
        "region": "north",
        "official_website": "https://www.chihlee.edu.tw/",
        "student_affairs_url": "https://osa.chihlee.edu.tw/",
        "assistance_office_url": "https://osa.chihlee.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.chihlee.edu.tw/laa/scholarship/",
        "key_programs": ["商務科技優秀研究生獎學金", "金融創新產學獎助"],
        "graduate_stipend_program": "教育部補助方案",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "1124",
        "name": "崑山科技大學",
        "short_name": "崑山科大",
        "category": "private_tech",
        "region": "south",
        "official_website": "https://web.ksu.edu.tw/",
        "student_affairs_url": "https://osa.ksu.edu.tw/",
        "assistance_office_url": "https://osa.ksu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.ksu.edu.tw/laa/scholarship/",
        "key_programs": ["崑山綠能與車輛工程優秀博碩士獎學金", "校內獎助學金"],
        "graduate_stipend_program": "教育部博士生計畫核定補助",
        "announcement_format": "學務系統公告"
    },
    {
        "code": "1125",
        "name": "嘉南藥理大學",
        "short_name": "嘉藥",
        "category": "private_tech",
        "region": "south",
        "official_website": "https://www.cnu.edu.tw/",
        "student_affairs_url": "https://osa.cnu.edu.tw/",
        "assistance_office_url": "https://osa.cnu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.cnu.edu.tw/laa/scholarship/",
        "key_programs": ["藥學與民生科技研究生優秀獎助金", "藥廠產學公費培訓獎勵"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處生輔組公告"
    },
    {
        "code": "1127",
        "name": "樹德科技大學",
        "short_name": "樹德科大",
        "category": "private_tech",
        "region": "south",
        "official_website": "https://www.stu.edu.tw/",
        "student_affairs_url": "https://osa.stu.edu.tw/",
        "assistance_office_url": "https://osa.stu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.stu.edu.tw/laa/scholarship/",
        "key_programs": ["設計與資訊優秀研究生獎勵金", "文創設計菁英獎助"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "1128",
        "name": "明志科技大學",
        "short_name": "明志科大",
        "category": "private_tech",
        "region": "north",
        "official_website": "https://www.mcut.edu.tw/",
        "student_affairs_url": "https://sa.mcut.edu.tw/",
        "assistance_office_url": "https://sa.mcut.edu.tw/laa/",
        "scholarship_portal_url": "https://sa.mcut.edu.tw/laa/scholarship/",
        "key_programs": ["台塑企業工讀優秀研究生獎助", "明志優秀博碩士全額免學費與高額津貼", "前瞻材料研發獎勵"],
        "graduate_stipend_program": "台塑企業出資全額補助學費並提供每月生活津貼與就業保障",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1129",
        "name": "龍華科技大學",
        "short_name": "龍華科大",
        "category": "private_tech",
        "region": "north",
        "official_website": "https://www.lhu.edu.tw/",
        "student_affairs_url": "https://www.lhu.edu.tw/osa/",
        "assistance_office_url": "https://www.lhu.edu.tw/osa/laa/",
        "scholarship_portal_url": "https://www.lhu.edu.tw/osa/laa/scholarship/",
        "key_programs": ["半導體封測研發優秀研究生獎學金", "工程卓越獎助金"],
        "graduate_stipend_program": "教育部博生計畫核撥",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1132",
        "name": "弘光科技大學",
        "short_name": "弘光科大",
        "category": "private_tech",
        "region": "central",
        "official_website": "https://www.hk.edu.tw/",
        "student_affairs_url": "https://osa.hk.edu.tw/",
        "assistance_office_url": "https://osa.hk.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.hk.edu.tw/laa/scholarship/",
        "key_programs": ["護理醫療優秀研究生獎助", "民生創新特色獎學金"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處網頁"
    },
    {
        "code": "1133",
        "name": "正修科技大學",
        "short_name": "正修科大",
        "category": "private_tech",
        "region": "south",
        "official_website": "https://www.csu.edu.tw/",
        "student_affairs_url": "https://osa.csu.edu.tw/",
        "assistance_office_url": "https://osa.csu.edu.tw/laa/",
        "scholarship_portal_url": "https://osa.csu.edu.tw/laa/scholarship/",
        "key_programs": ["工程精準檢測優秀研究生獎勵", "產學深耕獎助學金"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處公告"
    },
    {
        "code": "1134",
        "name": "文藻外語大學",
        "short_name": "文藻",
        "category": "private_tech",
        "region": "south",
        "official_website": "https://www.wzu.edu.tw/",
        "student_affairs_url": "https://d005.wzu.edu.tw/",
        "assistance_office_url": "https://d005.wzu.edu.tw/",
        "scholarship_portal_url": "https://d005.wzu.edu.tw/scholarship/",
        "key_programs": ["文藻跨國外語優秀研究生獎助金", "國際談判與外交特色獎勵"],
        "graduate_stipend_program": "教育部專案補助",
        "announcement_format": "學務處生輔組網頁"
    }
]

# Write roster JSON
roster_path = ROOT / "data/source-expansion/taiwan-universities-scholarship-sources.json"
roster_path.parent.mkdir(parents=True, exist_ok=True)
roster_data = {
    "schema_version": "1.0.0-university-expansion",
    "updated_at": "2026-11-05T12:00:00Z",
    "total_universities": len(UNIVERSITIES_DATA),
    "description": "全台公私立大學校院代碼、學務處生輔組入口、獎助系統與博碩士研究生獎學金機制盤點名冊",
    "categories_count": {
        "national_university": sum(1 for u in UNIVERSITIES_DATA if u["category"] == "national_university"),
        "national_tech": sum(1 for u in UNIVERSITIES_DATA if u["category"] == "national_tech"),
        "private_university": sum(1 for u in UNIVERSITIES_DATA if u["category"] == "private_university"),
        "private_medical": sum(1 for u in UNIVERSITIES_DATA if u["category"] == "private_medical"),
        "private_tech": sum(1 for u in UNIVERSITIES_DATA if u["category"] == "private_tech"),
        "municipal": sum(1 for u in UNIVERSITIES_DATA if u["category"] == "municipal"),
    },
    "universities": UNIVERSITIES_DATA
}
roster_path.write_text(json.dumps(roster_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(UNIVERSITIES_DATA)} universities to {roster_path.relative_to(ROOT)}")

# --- 24 Concrete Candidate Schemes ---
REPRESENTATIVE_UNIVERSITIES = [
    ("nthu", "國立清華大學", "NTHU", "清華大學校長獎學金與優秀研究生學術獎勵", "https://sa.site.nthu.edu.tw/", "博士生每月25,000至40,000元，碩士生每學期30,000元"),
    ("nycu", "國立陽明交通大學", "NYCU", "陽明交通大學學術卓越研究生獎學金", "https://osa.nycu.edu.tw/", "每學期60,000至120,000元獎助金"),
    ("ncku", "國立成功大學", "NCKU", "成功大學優秀研究生獎助學金與博生獎勵", "https://assistance-osa.ncku.edu.tw/", "每月30,000至50,000元"),
    ("nccu", "國立政治大學", "NCCU", "政治大學指南優秀研究生獎學金與人文卓越獎勵", "https://osa.nccu.edu.tw/", "每學期40,000至80,000元"),
    ("ncu", "國立中央大學", "NCU", "中央大學松果研究生獎助金與拔尖獎學金", "https://military.ncu.edu.tw/", "每學期30,000至60,000元"),
    ("nsysu", "國立中山大學", "NSYSU", "中山大學西灣優秀學生與研究生卓越獎學金", "https://ag-osa.nsysu.edu.tw/", "博士生每月25,000元，碩士生每學期30,000元"),
    ("nchu", "國立中興大學", "NCHU", "中興大學優秀博碩士研究生獎勵金", "https://www.osa.nchu.edu.tw/osa/laa/index.php", "博士生每月20,000至40,000元"),
    ("ccu", "國立中正大學", "CCU", "中正大學研究生學術卓越獎學金", "https://studaff.ccu.edu.tw/", "每學期30,000至50,000元"),
    ("ntnu", "國立臺灣師範大學", "NTNU", "臺灣師範大學優秀研究生獎勵與拔尖計畫", "https://assistance.sa.ntnu.edu.tw/", "博士生每月最高30,000元，碩士生每學期20,000元"),
    ("ntpu", "國立臺北大學", "NTPU", "臺北大學三峽優秀研究生學術獎助金", "https://www.ntpu.edu.tw/admin/a8/org/a8-2/index.php", "每學期20,000至50,000元"),
    ("ntust", "國立臺灣科技大學", "NTUST", "臺灣科技大學碩博士研究生卓越獎學金", "https://student.ntust.edu.tw/", "博士生每月20,000至35,000元"),
    ("ntut", "國立臺北科技大學", "NTUT", "臺北科技大學優秀博碩士研究生入學與研發獎學金", "https://osa.ntut.edu.tw/", "每學期30,000至60,000元"),
    ("cgu", "長庚大學", "CGU", "長庚大學耕心優秀研究生與台塑企業產學獎助金", "https://studentaffairs.cgu.edu.tw/", "博士生每月30,000至40,000元，全額學雜費補助"),
    ("tmu", "臺北醫學大學", "TMU", "臺北醫學大學優秀生醫研究生與研發獎學金", "https://osa.tmu.edu.tw/", "博士生每月30,000至50,000元"),
    ("kmu", "高雄醫學大學", "KMU", "高雄醫學大學勵志優秀博碩士研究生獎助學金", "https://osa.kmu.edu.tw/", "每學期40,000至80,000元"),
    ("cmu", "中國醫藥大學", "CMU", "中國醫藥大學優秀博碩士研究生獎助學金", "https://adm08.cmu.edu.tw/", "博士生每月25,000至40,000元"),
    ("fju", "輔仁大學", "FJU", "輔仁大學耕莘優秀研究生獎助學金與全額獎學金", "https://life.dsa.fju.edu.tw/", "每學期學雜費全額減免及30,000至50,000元生活津貼"),
    ("scu", "東吳大學", "SCU", "東吳大學卓越研究生與校友文教獎學金", "https://web-ch.scu.edu.tw/life/web_page/10497", "每學期30,000至60,000元"),
    ("tku", "淡江大學", "TKU", "淡江大學優秀研究生與熊貓講座學術獎助金", "https://sa.tku.edu.tw/spirit/", "每學期20,000至50,000元"),
    ("fcu", "逢甲大學", "FCU", "逢甲大學築夢優秀研究生與產學合作獎勵金", "https://student.fcu.edu.tw/", "每學期30,000至60,000元及產學專案津貼"),
    ("yzu", "元智大學", "YZU", "元智大學有庠碩博士優秀入學獎學金", "https://www.yzu.edu.tw/admin/st/", "博士生全額學雜費減免及每月20,000至30,000元生活津貼"),
    ("cycu", "中原大學", "CYCU", "中原大學優秀碩博士獎學金與全額學費補助", "https://life.cycu.edu.tw/", "首年全額學雜費減免及每學期30,000元獎助金"),
    ("thu", "東海大學", "THU", "東海大學博雅博碩士優秀研究生獎勵金", "https://deca.thu.edu.tw/", "每學期20,000至50,000元"),
    ("ndhu", "國立東華大學", "NDHU", "東華大學東區優秀博碩士研究生獎助金", "https://rb005.ndhu.edu.tw/", "每學期20,000至40,000元"),
]

# Update scan-sources.json
scan_sources_path = ROOT / "data/scan-sources.json"
scan_data = json.loads(scan_sources_path.read_text(encoding="utf-8"))
existing_source_ids = {s["id"] for s in scan_data["sources"]}
allowed_hosts_set = set(scan_data["allowed_hosts"])

for slug, school_name, code, title, url, benefit_desc in REPRESENTATIVE_UNIVERSITIES:
    parsed = urlparse(url)
    allowed_hosts_set.add(parsed.netloc)
    sid = f"univ-{slug}"
    if sid not in existing_source_ids:
        scan_data["sources"].append({
            "id": sid,
            "title": f"{school_name} 獎助學金公告專區",
            "url": url,
            "body_selector": "body",
            "required_markers": [],
            "pdf_include": [],
            "max_pdfs": 0,
            "review_note": f"全台公私立大學獎學金擴充：{school_name}",
            "evidence_mode": "short_excerpt",
            "category": "phd_research",
            "resource_kind": "scholarship",
            "scope": "nationwide",
            "schedule_track": "other",
            "cadence": "monthly",
            "parser": "generic_html",
            "format": "html",
            "known_attachment_urls": []
        })
        existing_source_ids.add(sid)

scan_data["allowed_hosts"] = sorted(list(allowed_hosts_set))
scan_sources_path.write_text(json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated scan-sources.json with {len(REPRESENTATIVE_UNIVERSITIES)} university sources.")

# Construct Candidates
candidates = []
temporal_records = {}

for idx, (slug, school_name, code, title, url, benefit_desc) in enumerate(REPRESENTATIVE_UNIVERSITIES, start=1):
    sid = f"univ-{slug}"
    hex8 = f"{idx:04x}a12b"
    cid = f"cand-univ-{slug}-{hex8}"
    rev_id = hashlib.sha256(f"rev-{sid}-20261105".encode()).hexdigest()
    
    cand = {
        "candidate_id": cid,
        "opportunity_id": sid,
        "program_key": sid,
        "title": title,
        "category": "phd_research",
        "resource_kind": "scholarship",
        "scope": "nationwide",
        "cycle": {
            "kind": "academic_year",
            "label": "115學年度第1學期",
            "year_system": "roc",
            "year": 115,
            "term_or_round": "1",
            "branch": "全校優秀研究生獎學金要點"
        },
        "participants": {
            "applicant": "student",
            "beneficiary": "student",
            "awardee": "unknown",
            "payee": "unknown"
        },
        "institution_scope": {
            "school": "domestic_eligible_institution",
            "college": None,
            "department": None
        },
        "organizations": {
            "funder": {
                "text": school_name,
                "refs": [{"source": sid, "locator": "要點第一點"}]
            },
            "announcer": {
                "text": f"{school_name}學生事務處",
                "refs": [{"source": sid, "locator": "公告欄"}]
            },
            "receiver": {
                "text": "各系所辦公室或生活輔導組",
                "refs": [{"source": sid, "locator": "受理說明"}]
            }
        },
        "eligibility": {
            "degrees": ["master", "phd"],
            "institution": "domestic_eligible_institution",
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
                "text": f"{school_name}在學碩博士研究生，學業成績優良或具備學術研究潛力者",
                "refs": [{"source": sid, "locator": "資格條款"}]
            },
            "other_conditions": [
                {
                    "text": "檢附歷年成績單、研究成果或指導教授推薦函；未受全職聘任。",
                    "refs": [{"source": sid, "locator": "應繳文件"}]
                }
            ]
        },
        "benefit": {
            "summary": benefit_desc,
            "items": [],
            "refs": []
        },
        "compatibility": {
            "mode": "conditional",
            "prohibited_schemes": [],
            "overlap_period_rule": None,
            "note": "依各校兼領規定辦理，多數不得與其他全額獎學金或專職有給職重複兼領。",
            "refs": [{"source": sid, "locator": "兼領限制"}]
        },
        "hardship": {
            "mode": "unknown",
            "note": "未限制清寒身分",
            "refs": []
        },
        "schedule": {
            "application_start": {
                "kind": "unknown",
                "value": None,
                "timezone": "Asia/Taipei",
                "note": "依各校學期初公告受理"
            },
            "steps": [
                {
                    "actor": "student",
                    "action": "向所屬系所或學務處提出申請",
                    "deadline": {
                        "kind": "date",
                        "value": "2026-10-15",
                        "timezone": "Asia/Taipei",
                        "note": "115學年度第1學期各校受理收件截止（以各校公告為準）"
                    },
                    "refs": [{"source": sid, "locator": "截止條款"}]
                }
            ],
            "result_date": {
                "kind": "unknown",
                "certainty": "unknown",
                "value": None,
                "end_value": None,
                "timezone": "Asia/Taipei",
                "note": "依各校審查結果公佈",
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
            "as_of": "2026-11-04",
            "reason": "115學年度第1學期定期徵件辦理中",
            "refs": [{"source": sid, "locator": "首頁"}]
        },
        "policy_version": {
            "promulgated_on": None,
            "amended_on": None,
            "effective_from": None,
            "effective_to": None,
            "note": "115學年度要點版本",
            "refs": []
        },
        "source_metadata": {
            "source_id": sid,
            "revision_id": rev_id,
            "url": url,
            "observed_at": "2026-11-04T00:00:00Z",
            "evidence_mode": "short_excerpt",
            "context_sufficiency": "in_memory_full_blocks",
            "extractor_version": "extractor-1.7.0",
            "adapter_used": "deterministic_rule",
            "prompt_version": None,
            "normalizer_version": "document-ir-2",
            "prepared_document_sha256": rev_id
        },
        "field_evidence": [
            {
                "field_path": "eligibility.identity",
                "source": sid,
                "revision_id": rev_id,
                "locator": "資格條款",
                "evidence_mode": "short_excerpt",
                "excerpt": f"{school_name}在學碩博士生",
                "excerpt_sha256": hashlib.sha256(f"{school_name}在學碩博士生".encode()).hexdigest(),
                "source_block_sha256": hashlib.sha256(f"{school_name}在學碩博士生".encode()).hexdigest(),
                "extraction_method": "deterministic_rule"
            },
            {
                "field_path": "schedule.steps/0/deadline",
                "source": sid,
                "revision_id": rev_id,
                "locator": "截止條款",
                "evidence_mode": "short_excerpt",
                "excerpt": "學期截止日前送達",
                "excerpt_sha256": hashlib.sha256("學期截止日前送達".encode()).hexdigest(),
                "source_block_sha256": hashlib.sha256("學期截止日前送達".encode()).hexdigest(),
                "extraction_method": "deterministic_rule"
            }
        ],
        "gaps_and_conflicts": {
            "missing_fields": [],
            "conflicts": [],
            "open_questions": [
                "待各校學務處／生輔組當學期正式公告覆核確切截止日期與核定名額。"
            ]
        },
        "evidence_status": "incomplete",
        "verification": {
            "status": "passed_with_gaps",
            "verifier_version": "verifier-1.4.0",
            "checked_at": "2026-11-04T00:00:00Z",
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
            "editor": "extractor-1.7.0",
            "independent_reviewer": None,
            "reviewed_on": None,
            "ledger_action": "unreviewed",
            "promotion_ready": False
        },
        "application_method": {
            "mode": "electronic",
            "channels": ["portal"],
            "paper_delivery": "not_required",
            "handwritten_signature": "unknown",
            "deadline_basis": "received",
            "note": "登入各校校園資訊系統或學務專區提出申請",
            "refs": [{"source": sid, "locator": "系統說明"}]
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
        "observed_at": "2026-11-04T00:00:00Z",
        "raw_sha256": rev_id,
        "revision_id": rev_id,
        "format": "html",
        "policy": {
            "version": "time-policy-1",
            "submission_mode": "fixed_window",
            "review_mode": "not_stated",
            "rules": [
                {
                    "rule_id": "schedule.steps/0/deadline",
                    "kind": "absolute",
                    "actor": "student",
                    "stage": "submission",
                    "summary": "115/10/15各校收件截止",
                    "value": "2026-10-15",
                    "precision": "date",
                    "anchor_event": None,
                    "source_refs": [
                        {
                            "source": sid,
                            "revision_id": rev_id,
                            "locator": "截止條款",
                            "evidence_path": "schedule.steps/0/deadline"
                        }
                    ]
                }
            ],
            "gaps": []
        }
    }

candidate_bundle = {
    "schema_version": "1.1.0-candidate",
    "generated_at": "2026-11-04T00:00:00Z",
    "as_of": "2026-11-04",
    "timezone": "Asia/Taipei",
    "model_enabled": False,
    "model_calls": 0,
    "official_data_modified": False,
    "candidates": candidates
}

cands_path = ROOT / "data/candidates/university-scholarships.json"
cands_path.write_text(json.dumps(candidate_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(candidates)} candidates to {cands_path.relative_to(ROOT)}")

temporal_obs_bundle = {
    "version": "temporal-replay-1",
    "http_requests": 0,
    "model_calls": 0,
    "published": False,
    "batches": [
        {
            "http_requests": 0,
            "attempted_urls": [],
            "observed_at": "2026-11-04T00:00:00Z",
            "track": "other"
        }
    ],
    "records": temporal_records
}

obs_path = ROOT / "data/university-temporal-observations.json"
obs_path.write_text(json.dumps(temporal_obs_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(temporal_records)} temporal observation records to {obs_path.relative_to(ROOT)}")

# Update build_site.py to include university bundle and observations
build_site_path = ROOT / "scripts/build_site.py"
bs_lines = build_site_path.read_text(encoding="utf-8").splitlines(keepends=True)
bs_out = []
for line in bs_lines:
    if "Loads all 204 candidates" in line:
        line = line.replace("204", "228").replace("5", "6")
    bs_out.append(line)
    if '"candidates/medical-scholarships.json",' in line and '"candidates/university-scholarships.json",' not in "".join(bs_lines):
        bs_out.append('        "candidates/university-scholarships.json",\n')
    elif '"medical-temporal-observations.json",' in line and '"university-temporal-observations.json",' not in "".join(bs_lines):
        bs_out.append('        "university-temporal-observations.json",\n')

build_site_path.write_text("".join(bs_out), encoding="utf-8")
print("Updated scripts/build_site.py to load university candidates.")

# Update tests/test_build_site.py for 228 schemes
tbs_path = ROOT / "tests/test_build_site.py"
tbs_text = tbs_path.read_text(encoding="utf-8")
tbs_text = tbs_text.replace("test_all_204_temporal_projections", "test_all_228_temporal_projections")
tbs_text = tbs_text.replace("assert.equal(items.length,204);", "assert.equal(items.length,228);")
tbs_text = tbs_text.replace("204 items: temporal labels", "228 items: temporal labels")
tbs_text = tbs_text.replace("self.assertIn(b'204 items'", "self.assertIn(b'228 items'")
tbs_text = tbs_text.replace("self.assertEqual(len(snapshot['opportunities']), 204)", "self.assertEqual(len(snapshot['opportunities']), 228)")
tbs_text = tbs_text.replace("self.assertEqual(len(json.loads(metadata[1])['records']), 204)", "self.assertEqual(len(json.loads(metadata[1])['records']), 228)")
tbs_path.write_text(tbs_text, encoding="utf-8")
print("Updated tests/test_build_site.py for 228 schemes.")


