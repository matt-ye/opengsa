const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../docs/design/prototype.js");
const today = "2026-10-28";
const demo = core.makeDemo(today);
const pilot = JSON.parse(fs.readFileSync(path.join(__dirname,"../data/pilot.json"),"utf8"));
const conferenceData=JSON.parse(fs.readFileSync(path.join(__dirname,"../data/conference-programs.json"),"utf8"));
const conference=(id,changes={})=>core.makeConferenceItem({name:"合成測試會議",start:"2027-07-20",buffer:14,...changes},conferenceData.programs.find(p=>p.id===id));

test("今天以臺北時區跨日，不取執行電腦的日期",()=>{
 assert.equal(core.taipeiToday(new Date("2026-10-28T16:05:00Z")),"2026-10-29");
 assert.equal(core.addDays("2028-02-28",1),"2028-02-29");
 assert.equal(core.dayNumber("2026-02-30"),null);
});
test("來源、身分與清寒標籤交集會同步縮減結果",()=>{
 assert.deepEqual(core.filterItems(demo,{source:"government",degree:"phd"}).map(x=>x.id),["SYNTH-A","SYNTH-E"]);
 assert.deepEqual(core.filterItems(demo,{hardship:"required",includeUnknown:false}).map(x=>x.id),["SYNTH-C"]);
 assert.equal(core.filterItems(demo,{source:"government",degree:"master"}).length,0);
});
test("未知值預設保留，但不冒充已確認兼領",()=>{
 const broad=core.filterItems(demo,{compatibility:"allowed",includeUnknown:true});
 assert.deepEqual(broad.map(x=>x.id),["SYNTH-B","SYNTH-D","SYNTH-F"]);
 assert.deepEqual(core.filterItems(demo,{compatibility:"allowed",includeUnknown:false}).map(x=>x.id),["SYNTH-B"]);
 assert.equal(broad.find(x=>x.id==="SYNTH-D").compatibility,"unknown");
});
test("尚未勾選時，第二三頁共用第一頁的篩選結果",()=>{
 const filtered=core.filterItems(demo,{source:"government"});
 assert.deepEqual(core.workspaceItems(demo,filtered,new Set()).map(x=>x.id),["SYNTH-A","SYNTH-E"]);
 assert.deepEqual(core.workspaceItems(demo,[],new Set()),[]);
});
test("勾選後改篩選不刪選項；清除勾選才回到目前結果",()=>{
 const selected=new Set(["SYNTH-B","SYNTH-F"]),filtered=core.filterItems(demo,{source:"government"});
 assert.deepEqual(core.workspaceItems(demo,filtered,selected).map(x=>x.id),["SYNTH-B","SYNTH-F"]);
 assert.deepEqual(core.workspaceItems(demo,[],selected).map(x=>x.id),["SYNTH-B","SYNTH-F"]);
 selected.clear();
 assert.deepEqual(core.workspaceItems(demo,filtered,selected).map(x=>x.id),["SYNTH-A","SYNTH-E"]);
});
test("選項在資料集中消失時，不默默以其他方案替代",()=>{
 assert.deepEqual(core.workspaceItems(demo,demo,new Set(["removed-program"])),[]);
});
test("篩選改變時近90天的尺度與今天位置保持穩定",()=>{
 const before=core.domain(demo,today), after=core.domain(demo.slice(0,1),today);
 assert.deepEqual(before,after);
 assert.equal(before.end-before.start+1,91);
 assert.equal(core.position(today,before),core.position(today,after));
 const moved=core.domain(demo,today,"recent",90);
 assert.ok(core.position(today,moved)<0);
});
test("缺日期不畫期間、不製造結果；起訖衝突不畫反向色帶",()=>{
 const range=core.domain(demo,today);
 const missing=core.geometry(demo.find(x=>x.id==="SYNTH-F"),range);
 assert.equal(missing.bar,null);assert.equal(missing.result,null);
 const invalid={...demo[0],start:{value:"2026-11-20"},end:{value:"2026-11-01"}};
 assert.equal(core.geometry(invalid,range).invalid,true);
 assert.equal(core.geometry(invalid,range).bar,null);
});
test("手機自動捲動到今天，固定名稱欄不蓋住進行線",()=>{
 const p=core.position(today,core.domain(demo,today));
 const scroll=core.centerScroll(p,805,267,165);
 const todayX=165+p/100*640-scroll;
 assert.ok(scroll>0);assert.ok(todayX>165 && todayX<267);
 assert.equal(core.centerScroll(p,965,965,220),0);
});
test("結果在截止之後以獨立節點與等待線呈現，保留預定狀態",()=>{
 const range=core.domain(demo,today), shape=core.geometry(demo[0],range);
 assert.ok(shape.bar.width>0);assert.ok(shape.result>shape.end);assert.ok(shape.wait.width>0);
 assert.equal(demo[0].result.certainty,"expected");
 const abroad=demo.find(x=>x.id==="SYNTH-E");
 assert.ok(core.dayNumber(abroad.milestones[0].value)>core.dayNumber(abroad.end.value));
 const fit=core.domain(demo,today,"fit");
 assert.ok(core.position(today,fit)>0 && core.position(today,fit)<100);
});
test("真實草稿的學院送件不回填為學生期限，結果日不補猜測",()=>{
 const drafts=core.makeDrafts(pilot);
 const moe=drafts.find(x=>x.id==="ntu-moe-phd-115-round2");
 assert.equal(moe.end.value,null);
 assert.equal(moe.milestones[0].value,"2026-11-09");
 assert.ok(drafts.every(x=>x.result.value===null && x.start.value===null));
 assert.equal(drafts.find(x=>x.id==="nstc-abroad-116-ntu").end.value,"2026-07-29T08:00:00+08:00");
});
test("線框嵌入快照與正式草稿同源，避免維護兩份不同資料",()=>{
 const html=fs.readFileSync(path.join(__dirname,"../docs/design/wireframes.html"),"utf8");
 const embedded=html.match(/<script id="pilot-data" type="application\/json">([\s\S]*?)<\/script>/);
 assert.ok(embedded);assert.deepEqual(JSON.parse(embedded[1]),pilot);
 assert.equal((html.match(/role="tabpanel"/g)||[]).length,4);
 assert.equal((html.match(/role="tab"/g)||[]).length,4);
});

test("研討會以月份首日倒推，跨年不誤當會前30天",()=>{
 const plan=core.conferencePlan("2027-01-15");
 assert.equal(plan.agencyBase,"2026-12-01");
 assert.equal(plan.studentBase,"2026-11-30");
 assert.equal(plan.studentTime,"17:00");
 assert.equal(plan.supplement,"2026-12-18");
 assert.equal(plan.prepare,"2026-11-16");
 assert.equal(core.conferencePlan("2027-01-31").agencyBase,plan.agencyBase);
});

test("接受函四週補送跨閏月；例假日未核不升級正式期限",()=>{
 const plan=core.conferencePlan("2028-03-01");
 assert.equal(plan.supplement,"2028-02-02");
 assert.equal(plan.calendarStatus,"unverified");
 assert.equal(plan.deadlineStatus,"estimate_pending_calendar");
 assert.equal(plan.noticeRisk,"unknown");
});

test("接受通知晚於送件與晚於補送分別提醒，補送當日不誤當已逾期",()=>{
 assert.equal(core.conferencePlan("2026-07-20","2026-05-30").noticeRisk,"before_submission");
 assert.equal(core.conferencePlan("2026-07-20","2026-06-10").noticeRisk,"after_submission");
 assert.equal(core.conferencePlan("2026-07-20","2026-06-22").noticeRisk,"after_submission");
 assert.equal(core.conferencePlan("2026-07-20","2026-06-23").noticeRisk,"after_supplement");
});

test("無效會議日期及緩衝不產生試算，0天緩衝仍有效",()=>{
 assert.equal(core.conferencePlan("2026-02-30"),null);
 assert.equal(core.conferencePlan(null),null);
 assert.equal(core.conferencePlan("2026-07-20T08:00:00+08:00"),null);
 assert.equal(core.conferencePlan("2026-07-20","2026-05-30T18:00"),null);
 assert.equal(core.conferencePlan("2026-07-20","bad"),null);
 for(const buffer of [-1,91,1.5,NaN]) assert.equal(core.conferencePlan("2026-07-20",null,buffer),null);
 const plan=core.conferencePlan("2026-07-20",null,0);
 assert.equal(plan.prepare,plan.studentBase);
});

test("個人會議轉為可篩選、可選取的時程，但不捏造官方起日或補助結果",()=>{
 const item=conference("nstc-ntu");
 assert.equal(item.personal,true);assert.equal(item.synthetic,false);
 assert.equal(item.end.value,"2027-05-31");assert.equal(item.end.certainty,"estimated");
 assert.equal(item.start.value,null);assert.equal(item.result.value,null);
 assert.equal(item.preparation.start,"2027-05-17");
 assert.equal(core.geometry(item,core.domain([item],today,"fit")).bar,null);
 assert.deepEqual(core.workspaceItems([item],[],new Set([item.id])),[item]);
 assert.equal(core.filterItems([item],{source:"government",includeUnknown:false}).length,1);
 assert.ok(item.milestones.some(x=>x.label.includes("接受函補送")));
});

test("同場同方案更新同ID，不同方案及院系分列；個人資料不混入正式快照",()=>{
 const a=conference("nstc-ntu"),b=conference("nstc-ntu",{buffer:7,notice:"2027-06-10"}),c=conference("faos-student");
 assert.equal(a.id,b.id);assert.notEqual(a.preparation.start,b.preparation.start);assert.notEqual(a.id,c.id);
 assert.notEqual(conference("custom-unit",{unit:"A系"}).id,conference("custom-unit",{unit:"B系"}).id);
 assert.ok(!pilot.opportunities.some(x=>x.id===a.id));
});

test("醫學院四週前送件與國科會四週補送不混為同一程序",()=>{
 const item=conference("ntu-med-oia",{notice:"2027-06-25"});
 assert.equal(item.end.value,"2027-06-22");assert.equal(item.noticeRisk,"after_deadline");
 assert.ok(!item.milestones.some(x=>x.label.includes("補送")));
 assert.equal(item.source,"university");assert.equal(item.compatibility,"conditional");
});

test("FAOS以兩個曆月計機構基準，校內學生截止留未知，不套用國科會補送",()=>{
 const item=conference("faos-student",{notice:"2027-05-25"});
 assert.equal(item.end.value,null);assert.equal(item.end.certainty,"unknown");
 assert.equal(item.preparation.end,"2027-05-20");assert.equal(item.noticeRisk,"after_deadline");
 assert.ok(!item.milestones.some(x=>x.label.includes("補送")));
 assert.equal(core.monthsBefore("2028-04-30",2),"2028-02-29");
 assert.equal(core.monthsBefore("2027-08-31",2),"2027-06-30");
 assert.equal(core.monthsBefore("2027-01-15",2),"2026-11-15");
});

test("未知院系期限不畫補助期間，自填日期只作待核節點",()=>{
 const unknown=conference("custom-unit"),manual=conference("custom-unit",{manualDeadline:"2027-06-15"});
 assert.equal(unknown.end.value,null);assert.equal(unknown.preparation,null);
 assert.equal(unknown.milestones.length,1);assert.equal(manual.end.value,"2027-06-15");
 assert.equal(manual.end.certainty,"estimated");
 assert.equal(conference("custom-unit",{manualDeadline:"2027-02-30"}),null);
 assert.equal(core.makeConferenceItem({start:"2027-07-20",buffer:14},{}),null);
});

test("來源登錄與離線嵌入同源；醫學院研發處維持角色待核的參考入口",()=>{
 const html=fs.readFileSync(path.join(__dirname,"../docs/design/wireframes.html"),"utf8");
 assert.deepEqual(JSON.parse(html.match(/<script id="conference-data" type="application\/json">([\s\S]*?)<\/script>/)[1]),conferenceData);
 assert.equal(new Set(conferenceData.programs.map(p=>p.id)).size,4);
 assert.ok(conferenceData.reference_sources.some(x=>x.url.includes("rd.mc.ntu.edu.tw")));
 for(const p of conferenceData.programs) for(const ref of p.refs) assert.equal(new URL(ref.url).protocol,"https:");
});

test("醫學院與FAOS可從來源清單檢索，缺日期的制度入口不製造時間或受理狀態",()=>{
 const entries=core.conferenceEntries(conferenceData.programs);
 assert.equal(entries.length,2);
 const faos=core.filterItems(entries,{source:"foundation",query:"傑出人才",includeUnknown:false});
 assert.equal(faos.length,1);assert.equal(faos[0].id,"PROGRAM-faos-student");
 assert.ok(entries.every(x=>!x.synthetic && !x.personal && x.start.value===null && x.end.value===null && x.result.value===null));
 assert.ok(!entries.some(x=>x.id.includes("nstc")));
});

test("探索島情境快速篩選可一鍵套用並再次點擊還原，保留搜尋字詞與待確認設定",()=>{
 const base={query:"臺大",category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all",includeUnknown:false};
 const phd=core.applyPersona(base,"phd_research");
 assert.equal(phd.category,"phd_research");
 assert.equal(phd.degree,"phd");
 assert.equal(phd.query,"臺大");
 assert.equal(phd.includeUnknown,false);
 assert.equal(core.activePersona(phd),"phd_research");
 const reset=core.applyPersona(phd,"phd_research");
 assert.equal(reset.category,"all");
 assert.equal(reset.degree,"all");
 assert.equal(core.activePersona(reset),null);
});

test("權益島從屬性自測依勾選指標整理爭點與對應救濟層級，不冒充正式法律裁決",()=>{
 const none=core.evaluateSubordination({});
 assert.equal(none.score,0);assert.equal(none.level,"none");
 const single=core.evaluateSubordination({schedule:true});
 assert.equal(single.score,1);assert.equal(single.level,"review_needed");
 assert.deepEqual(single.recommendedTiers,["TIER 01","TIER 02"]);
 const high=core.evaluateSubordination({schedule:true,consideration:true,supervision:true});
 assert.equal(high.score,3);assert.equal(high.level,"high_subordination");
 assert.deepEqual(high.recommendedTiers,["TIER 02","TIER 04","TIER 05"]);
 assert.ok(high.summary.includes("不構成正式法律裁決"));
});

test("權益島雙軌視角、五級救濟地圖與RWD觸控優化已嵌入線框且維持四頁籤結構",()=>{
 const html=fs.readFileSync(path.join(__dirname,"../docs/design/wireframes.html"),"utf8");
 assert.equal((html.match(/role="tabpanel"/g)||[]).length,4);
 assert.equal((html.match(/role="tab"/g)||[]).length,4);
 assert.ok(html.includes('id="persona-bar"'));
 assert.ok(html.includes('id="rights-view-switch"'));
 assert.ok(html.includes('id="rights-standards-group"'));
 assert.ok(html.includes('id="rights-grievance-group"'));
 assert.ok(html.includes('id="subordination-wizard"'));
 assert.ok(html.includes('id="grievance-map"'));
 assert.ok(html.includes("font-size:16px"));
 assert.ok(html.includes(".gantt-marker::after"));
});

test("法源位階地圖按鈕導向正確表格ID，不觸發未定義hash跳轉回甘特圖",()=>{
 const html=fs.readFileSync(path.join(__dirname,"../docs/design/wireframes.html"),"utf8");
 const js=fs.readFileSync(path.join(__dirname,"../docs/design/prototype.js"),"utf8");
 assert.ok(html.includes('href="#work-matrix-title"'));
 assert.ok(html.includes('href="#nstc-rights-title"'));
 assert.ok(html.includes('href="#ta-salary-title"'));
 assert.ok(html.includes('id="work-matrix-title"'));
 assert.ok(html.includes('id="nstc-rights-title"'));
 assert.ok(html.includes('id="ta-salary-title"'));
 assert.ok(js.includes("scrollToInternalTarget"));
 assert.ok(js.includes('["search","detail","timeline","rights"].includes(targetId)'));
});
