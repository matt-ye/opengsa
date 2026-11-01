const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../docs/design/prototype.js");
const today = "2026-10-28";
const demo = core.makeDemo(today);
const pilot = JSON.parse(fs.readFileSync(path.join(__dirname,"../data/pilot.json"),"utf8"));
const conferenceData=JSON.parse(fs.readFileSync(path.join(__dirname,"../data/conference-programs.json"),"utf8"));

test("雷達將已知符合與未知條件分區，未知不冒充不限年級或可兼領",()=>{
 const entries=[{id:"SYNTH-known",title:"SYNTH",cycle:"2026",year:"unlimited",compatibility:"allowed",degrees:["phd"],rawState:"open"},
 {id:"SYNTH-unknown",title:"SYNTH",cycle:"2026",year:"unknown",compatibility:"unknown",degrees:[],rawState:"unknown"},
 {id:"SYNTH-no",title:"SYNTH",cycle:"2026",year:"range",compatibility:"prohibited",degrees:["master"],rawState:"closed"}];
 const result=core.partitionItems(entries,{year:"unlimited",compatibility:"allowed",includeUnknown:true});
 assert.deepEqual(result.matched.map(i=>i.id),["SYNTH-known"]);
 assert.deepEqual(result.possible.map(i=>i.id),["SYNTH-unknown"]);
 assert.equal(core.partitionItems(entries,{degree:"phd",includeUnknown:false}).all.length,1);
 assert.equal(core.partitionItems(entries,{application:"open",includeUnknown:true}).matched.length,1);
 assert.equal(core.partitionItems(entries,{application:"open",includeUnknown:true}).possible.length,1);
});

test("回報連結保留公開識別與原文URL，不帶個人規劃或篩選條件",()=>{
 const publicItem={id:"SYNTH-id",title:"合成獎助 & ? # 測試",url:"https://example.test/"+"%E7%94%B3".repeat(40)+".pdf",sourceVersion:"a".repeat(64),privateAge:29,filter:{school:"PRIVATE"}};
 const url=new URL(core.issueUrl(publicItem));
 assert.equal(url.pathname,"/matt-ye/opengsa/issues/new");
 assert.equal(url.searchParams.get("resource_id"),publicItem.id);
 assert.equal(url.searchParams.get("resource_name"),publicItem.title);
 assert.equal(url.searchParams.get("source_url"),publicItem.url);
 assert.equal(url.searchParams.get("source_version"),publicItem.sourceVersion);
 assert.doesNotMatch(url.href,/PRIVATE|privateAge|filter/);
 const personal=core.issueUrl({...publicItem,personal:true,title:"PRIVATE-CONFERENCE"});
 assert.doesNotMatch(personal,/SYNTH-id|PRIVATE-CONFERENCE|source_url/);
 assert.equal(core.officialUrl("javascript:alert(1)"),null);
 assert.equal(core.officialUrl("https://user:password@example.test"),null);
});

test("清晰度評估核心欄位，日期矛盾不能被完整度抵銷",()=>{
 const item={title:"SYNTH",url:"https://example.test",cycle:"115年度",audience:"博士生",sourceChecked:"2026-10-31",
  start:{value:"2026-11-01",certainty:"confirmed"},end:{value:"2026-12-01",certainty:"confirmed"}};
 assert.equal(core.clarity(item,"2026-11-01").level,"green");
 assert.equal(core.clarity({...item,audience:null},"2026-11-01").level,"amber");
 assert.equal(core.clarity({...item,audienceKind:"program_descriptor"},"2026-11-01").level,"amber");
 const descriptor={...item,id:'SYNTH-descriptor',degrees:[],candidateMode:'unknown'};
 assert.equal(core.partitionItems([descriptor],{degree:'phd',includeUnknown:false}).all.length,0);
 assert.equal(core.partitionItems([descriptor],{degree:'phd',includeUnknown:true}).possible.length,1);
 assert.equal(core.clarity({...item,sourceChecked:"2020-01-01"},"2026-11-01").level,"amber");
 assert.equal(core.clarity({...item,end:{value:"2026-10-01"}},"2026-11-01").level,"red");
 assert.equal(core.clarity({...item,resourceKind:"tool_subscription"},"2026-11-01").level,"amber");
});

test("方案彙整不把辦法與當期公告的欄位拼接，所有其他文件仍可連回來源",()=>{
 const docs=[{id:"SYNTH-policy",programKey:"SYNTH",cycle:"辦法",cycleKind:"policy_snapshot",url:"https://example.test/rule",benefit:"policy amount"},
 {id:"SYNTH-call",programKey:"SYNTH",cycle:"115年度",cycleKind:"academic_year",url:"https://example.test/call",benefit:null}];
 const grouped=core.groupDocuments(docs);
 assert.equal(grouped.length,1);assert.equal(grouped[0].id,"SYNTH-call");assert.equal(grouped[0].benefit,null);
 assert.equal(grouped[0].relatedDocuments[0].url,docs[0].url);
 assert.equal(docs[0].relatedDocuments,undefined);
});

test("雷達不顯示缺證據的預設資格與日期，來源版次仍可回報",()=>{
 const data=JSON.parse(JSON.stringify(pilot));const raw=data.opportunities[0];
 const metadata={records:{[raw.id]:{url:"https://example.test/original.pdf",revision:"a".repeat(64),observed_at:"2026-10-31T12:00:00+08:00",unsafe:false,
  known:Object.fromEntries(["audience","year","candidate","compatibility","hardship","start","deadline","result","benefit","method"].map(k=>[k,false]))}}};
 const item=core.makeDrafts(data,"2026-11-01",metadata)[0];
 assert.equal(item.audience,null);assert.deepEqual(item.degrees,[]);assert.equal(item.year,"unknown");
 assert.equal(item.start.value,null);assert.equal(item.end.value,null);assert.equal(item.benefit,null);
 assert.equal(item.url,metadata.records[raw.id].url);
 assert.equal(new URL(core.issueUrl(item)).searchParams.get("source_version"),"a".repeat(64));
});

test("局部未知不抹掉整段說明，推估日期與正式受理分開",()=>{
 assert.equal(core.unknownValue('待確認'),true);
 assert.equal(core.unknownValue('身分條件請至來源定位核對'),true);
 assert.equal(core.unknownValue('會議舉行前一個月首日；例假日校正尚待確認'),false);
 assert.equal(core.unknownValue('地方青年訂閱費補助；個別資格須依各條件核對'),false);
 const data=JSON.parse(JSON.stringify(pilot)),raw=data.opportunities.find(x=>x.id==='ntu-president-114');
 raw.eligibility.identity.text='部分身分已明確；其他條件尚未確認';
 const metadata={records:{[raw.id]:{url:'https://example.test',revision:'SYNTH',observed_at:'2026-11-01T00:00:00+08:00',unsafe:false,
 known:{audience:true,start:true,deadline:false},organizations:{receiver:'先送系所，再送學院'},
 time_steps:[{actor:'university',action:'校級收件',deadline:{kind:'date',value:'2026-08-25',note:'系所可能更早'}}]}}};
 const item=core.makeDrafts(data,'2026-11-01',metadata).find(x=>x.id===raw.id);
 assert.equal(item.start.value,null);assert.equal(item.end.value,null);assert.notEqual(item.rawState,'open');
 assert.equal(item.estimatedStart.value,'2026-07-08');assert.equal(item.organizations.receiver,'先送系所，再送學院');
 assert.equal(item.timeSteps[0].actor,'university');assert.equal(item.audience,raw.eligibility.identity.text);
});

test("審查篩選保留處置且不解除來源缺漏的核准限制（合成DOM）",async()=>{
 class Element{
  constructor(tag){this.tag=tag;this.children=[];this.handlers={};this.value="";this.textContent="";}
  append(...nodes){this.children.push(...nodes);}
  setAttribute(key,value){this[key]=value;}
  addEventListener(key,handler){this.handlers[key]=handler;}
  click(){this.handlers.click?.();}
 }
 const ids=Object.fromEntries(["review-data","review-date","run-info","review-counts","document-groups","candidates","reviewer","download-decisions","export-status","review-filter","review-filter-count"].map(id=>[id,new Element("div")]));
 ids["review-filter"].value="all";
 const row=id=>({candidate_id:id,title:"SYNTH "+id,source:{url:"https://example.test",source_id:"SYNTH",revision_id:"SYNTH"},
  fingerprint:"SYNTH-fingerprint",editor:"SYNTH-editor",last_verification:"passed_automated_checks",context_status:"fresh_semantic_revision_matched",
  verification:{status:"passed_automated_checks",errors:[]},gaps:{source:[],personal:[],operational:[]},before:null,after:{},evidence:[],questions:[]});
 const ready=row("SYNTH-ready"),blocked=row("SYNTH-blocked"),stale=row("SYNTH-stale");blocked.gaps.source=["ai_tools:age_reference_date"];
 stale.context_status="source_revision_changed_requires_rescan";
 ids["review-data"].textContent=JSON.stringify({as_of:"2026-11-01",manifest:{http_requests:0},document_groups:{SYNTH:[ready.candidate_id,blocked.candidate_id,stale.candidate_id]},rows:[ready,blocked,stale]});
 let downloaded;
 require("node:vm").runInNewContext(fs.readFileSync(path.join(__dirname,"../docs/design/review-workspace.js"),"utf8"),{
  document:{getElementById:id=>ids[id],createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text})},
  Intl,Date,Blob,URL:{createObjectURL:blob=>{downloaded=blob;return "blob:SYNTH";},revokeObjectURL(){}},setTimeout:fn=>fn()
 });
 const find=(parent,tag)=>parent.children.flatMap(n=>[n,...(n.children?find(n,tag):[])]).filter(n=>n.tag===tag);
 const [a,b,c]=ids.candidates.children;
 assert.equal(find(a,"select")[0].children.find(n=>n.value==="applied").disabled,undefined);
 assert.equal(find(b,"select")[0].children.find(n=>n.value==="applied").disabled,true);
 assert.equal(find(c,"select")[0].children.find(n=>n.value==="applied").disabled,true);
 find(a,"select")[0].value="applied";find(b,"select")[0].value="noted";
 find(a,"textarea")[0].value="SYNTH 核對原文";find(b,"textarea")[0].value="SYNTH 等待官方依據";
 ids["reviewer"].value="SYNTH-independent";
 ids["review-filter"].value="ready";ids["review-filter"].handlers.change();
 assert.equal(a.hidden,false);assert.equal(b.hidden,true);
 assert.equal(c.hidden,true);
 assert.match(ids["review-filter-count"].textContent,/1／3/);
 ids["download-decisions"].click();
 const reviews=JSON.parse(await downloaded.text()).reviews;
 assert.deepEqual(reviews.map(r=>[r.candidate_id,r.action]),[["SYNTH-ready","applied"],["SYNTH-blocked","noted"]]);
 assert.match(ids["export-status"].textContent,/尚未核准發布/);
 ids["review-filter"].value="exceptions";ids["review-filter"].handlers.change();
 assert.equal(a.hidden,true);assert.equal(c.hidden,false);
 find(ids["document-groups"],"a")[0].click();
 assert.equal(ids["review-filter"].value,"all");assert.equal(a.hidden,false);assert.equal(b.hidden,false);
});
test("具名地方政府補助跨年度仍可由政府來源篩選，不靠單位名稱含政府二字",()=>{
 const candidates=JSON.parse(fs.readFileSync(path.join(__dirname,"../data/candidates/ai-tools-115.json"),"utf8")).candidates;
 const items=candidates.map(c=>({...pilot.opportunities[0],id:c.program_key+"-synthetic-year",program_key:c.program_key,title:c.title,organizations:c.organizations}));
 const drafts=core.makeDrafts({...pilot,opportunities:items},today);
 assert.equal(core.filterItems(drafts,{source:"government"}).length,2);
});
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
test("真實草稿的學院送件不回填為學生期限，缺起日不補猜測，載明起日者精確結構化",()=>{
 const drafts=core.makeDrafts(pilot);
 const moe=drafts.find(x=>x.id==="ntu-moe-phd-115-round2");
 assert.equal(moe.end.value,null);
 assert.equal(moe.milestones[0].value,"2026-11-09");
 // 缺起日者嚴禁從學院送件日或非學生日期胡亂回填
 assert.equal(moe.start.value,null);
 assert.equal(moe.result.value,null);

 // 官方文本載明起訖日者，精確結構化為甘特圖起日，不捏造也不遺失
 const tuition=drafts.find(x=>x.id==="ntu-tuition-115-1");
 assert.equal(tuition.start.value,"2026-08-05");
 assert.equal(tuition.end.value,"2026-08-13");

 const president=drafts.find(x=>x.id==="ntu-president-114");
 assert.equal(president.start.value,"2026-07-08");

 const abroad=drafts.find(x=>x.id==="nstc-abroad-116-ntu");
 assert.equal(abroad.start.value,"2026-06-01");
 assert.equal(abroad.end.value,"2026-07-29T08:00:00+08:00");
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
 assert.equal(new Set(conferenceData.programs.map(p=>p.id)).size,5);
 assert.ok(conferenceData.reference_sources.some(x=>x.url.includes("rd.mc.ntu.edu.tw")));
 for(const p of conferenceData.programs) for(const ref of p.refs) assert.equal(new URL(ref.url).protocol,"https:");
});

test("醫學院、FAOS與千里馬可從來源清單檢索，缺日期的制度入口不製造時間或受理狀態",()=>{
 const entries=core.conferenceEntries(conferenceData.programs);
 assert.equal(entries.length,3);
 const faos=core.filterItems(entries,{source:"foundation",query:"傑出人才",includeUnknown:false});
 assert.equal(faos.length,1);assert.equal(faos[0].id,"PROGRAM-faos-student");
 const dragon=entries.find(x=>x.id==="PROGRAM-nstc-abroad-dragon");
 assert.ok(dragon);
 assert.equal(dragon.category,"overseas_research");
 assert.deepEqual(dragon.degrees,["phd"]);
 assert.ok(entries.every(x=>!x.synthetic && !x.personal && x.start.value===null && x.end.value===null && x.result.value===null));
});

test("國科會千里馬赴國外研究依預計出國年份推算前一年申請窗與校內收件基準",()=>{
 const dragonProg=conferenceData.programs.find(x=>x.id==="nstc-abroad-dragon");
 assert.ok(dragonProg);
 const item=core.makeConferenceItem({name:"德國馬克斯普朗克訪問",start:"2027-03-01",buffer:14},dragonProg);
 assert.ok(item);
 assert.equal(item.category,"overseas_research");
 assert.deepEqual(item.degrees,["phd"]);
 assert.equal(item.end.value,"2026-07-28"); // 國科會 7/31 提前 3 天校內基準
 assert.equal(item.result.value,"2026-10-31"); // 預計核定結果
 assert.ok(item.milestones.some(m=>m.label==="國科會受理截止（試算）" && m.value==="2026-07-31"));
 assert.ok(item.milestones.some(m=>m.label==="國科會申請起日（試算）" && m.value==="2026-06-01"));
 assert.ok(item.milestones.some(m=>m.label==="赴外首日（自填）" && m.value==="2027-03-01"));
 assert.equal(item.preparation.start,"2026-07-14"); // 2026-07-28 前 14 天
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


test("擴充篩選器支援博士候選人資格、受理狀態與多來源維度",()=>{
 const sampleItems = [
  {id:"P-1",title:"博士候選人培育",degrees:["phd"],candidateMode:"required",source:"research_institute",category:"phd_research",cycle:"2026",rawState:"open",application:"受理中",compatibility:"allowed",hardship:"not_exclusive",year:"unlimited"},
  {id:"P-2",title:"碩士兼任助理",degrees:["master"],candidateMode:"not_required",source:"enterprise",category:"indirect_support",cycle:"2026",rawState:"not_yet_open",application:"尚未開放",compatibility:"conditional",hardship:"unknown",year:"range"},
  {id:"P-3",title:"一般清寒獎助",degrees:["master","phd"],candidateMode:"unknown",source:"foundation",category:"living_tuition",cycle:"2026",rawState:"closed",application:"已截止",compatibility:"prohibited",hardship:"required",year:"freshman"}
 ];

 const candOnly = core.filterItems(sampleItems,{degree:"candidate"});
 assert.deepEqual(candOnly.map(x=>x.id),["P-1"]);

 const openOnly = core.filterItems(sampleItems,{application:"open"});
 assert.deepEqual(openOnly.map(x=>x.id),["P-1"]);

 const closedOnly = core.filterItems(sampleItems,{application:"closed"});
 assert.deepEqual(closedOnly.map(x=>x.id),["P-3"]);

 const enterpriseOnly = core.filterItems(sampleItems,{source:"enterprise",includeUnknown:false});
 assert.deepEqual(enterpriseOnly.map(x=>x.id),["P-2"]);

 const researchInstOnly = core.filterItems(sampleItems,{source:"research_institute",includeUnknown:false});
 assert.deepEqual(researchInstOnly.map(x=>x.id),["P-1"]);
});

test("makeDrafts保留候選人屬性、受理狀態並支援結構化起訖甘特圖色帶",()=>{
 const drafts = core.makeDrafts(pilot);
 assert.ok(drafts.length >= 10);
 for(const d of drafts) {
  assert.ok("candidateMode" in d);
  assert.ok("rawState" in d);
  assert.ok("source" in d);
  assert.ok(["government","university","foundation","enterprise","research_institute","unknown"].includes(d.source));
 }

 // 模擬帶有結構化起訖日之草稿，驗證甘特圖色帶能正常生成
 const mockWithStart = {
  ...drafts[0],
  start: {value:"2026-08-01",certainty:"confirmed",note:"官方起日"},
  end: {value:"2026-08-15",certainty:"confirmed",note:"官方截止"},
  result: {value:"2026-09-01",certainty:"confirmed",note:"官方結果"}
 };
 const range = {start: core.dayNumber("2026-07-20"), end: core.dayNumber("2026-09-20")};
 const geom = core.geometry(mockWithStart, range);
 assert.ok(geom.bar !== null);
 assert.ok(geom.bar.width > 0);
 assert.ok(geom.wait !== null);
 assert.ok(geom.wait.width > 0);
 assert.ok(geom.result !== null);
});

test("方向C：官方未載起日但有截止日之方案，保留start為null且繪製截止前30天準備提醒帶",()=>{
 const drafts = core.makeDrafts(pilot);
 const medPub = drafts.find(x=>x.id==="ntu-med-publication-115");
 assert.ok(medPub);
 // 原始資料嚴禁捏造官方起日
 assert.strictEqual(medPub.start.value, null);
 assert.strictEqual(medPub.start.certainty, "unknown");
 assert.ok(medPub.end.value);

 // 截止前 30 天準備提醒期幾何推算
 const endDay = medPub.end.value.slice(0, 10);
 const prepStart = core.addDays(endDay, -30);
 assert.strictEqual(prepStart, "2026-10-27");
 const range = {start: core.dayNumber("2026-10-01"), end: core.dayNumber("2026-12-31")};
 const noticeGeom = core.geometry({start: {value: prepStart}, end: {value: endDay}, result: {value: null}, milestones: []}, range).bar;
 assert.ok(noticeGeom !== null);
 assert.ok(noticeGeom.width > 0);

 // 驗證 wireframes.html 樣式與圖例完整支援 notice-window
 const html = fs.readFileSync(path.join(__dirname,"../docs/design/wireframes.html"),"utf8");
 assert.ok(html.includes(".gantt-bar.notice-window"));
 assert.ok(html.includes(".legend-prep-window"));
 assert.ok(html.includes("準備提醒期（截止前30天）"));

 // 驗證 prototype.js 包含 notice-window 繪製邏輯
 const js = fs.readFileSync(path.join(__dirname,"../docs/design/prototype.js"),"utf8");
 assert.ok(js.includes('gantt-bar notice-window'));
 assert.ok(core.noticeWindow(medPub));
});

test("方向B：依官方公告發布日推定起日之方案，標註certainty為inferred且具備專屬甘特圖樣式",()=>{
 const drafts = core.makeDrafts(pilot);
 const pres = drafts.find(x=>x.id==="ntu-president-114");
 assert.ok(pres);
 // 校長獎由公文公告發布日推定即日起受理
 assert.strictEqual(pres.start.certainty, "inferred");
 assert.strictEqual(pres.start.value, "2026-07-08");
 assert.ok(pres.start.note.includes("推定"));

 // 起點節點正常生成（校長獎只有校級程序截止，學生截止維持未知，嚴守不猜測原則）
 const range = {start: core.dayNumber("2026-06-01"), end: core.dayNumber("2026-09-30")};
 const geom = core.geometry(pres, range);
 assert.ok(geom.start !== null);

 // 模擬帶有學生截止之推定起訖草稿，驗證甘特長條正常生成
 const mockInferred = {
  ...pres,
  end: {value: "2026-08-25", certainty: "confirmed", note: "學生截止"}
 };
 const mockGeom = core.geometry(mockInferred, range);
 assert.ok(mockGeom.bar !== null);
 assert.ok(mockGeom.bar.width > 0);

 // 驗證 wireframes.html 樣式與圖例支援 inferred
 const html = fs.readFileSync(path.join(__dirname,"../docs/design/wireframes.html"),"utf8");
 assert.ok(html.includes(".gantt-bar.inferred"));
 assert.ok(html.includes(".legend-inferred"));
 assert.ok(html.includes("推定受理起日"));

 // 驗證 prototype.js 包含 inferred 樣式賦予與標記邏輯
 const js = fs.readFileSync(path.join(__dirname,"../docs/design/prototype.js"),"utf8");
 assert.ok(js.includes('isInferred?"推定受理期（依官方公告日推定）："'));
 assert.ok(js.includes('start"+(isStartInferred?" inferred":"")'));
 assert.ok(js.includes('起日依官方公告推定'));
});


test("受理狀態只比對狀態碼，待確認不得混入受理中",()=>{
 const items=[{id:"unknown",rawState:"unknown",application:"受理待確認"},{id:"open",rawState:"open",application:"受理中"}];
 assert.deepEqual(core.filterItems(items,{application:"open"}).map(x=>x.id),["open"]);
});
test("涵蓋所有日期包含準備建議，未知起日仍未寫入資料",()=>{
 const item={start:{value:null},end:{value:"2026-12-01"},result:{value:null},milestones:[]};
 const range=core.domain([item],"2026-12-01","fit");
 assert.ok(range.start<=core.dayNumber("2026-11-01"));
 assert.strictEqual(item.start.value,null);
});
test("公告快照過期或推定起日不宣稱今天已開放",()=>{
 const item={application:{state:"open",as_of:"2026-10-01"},start:{kind:"date",value:"2026-10-01",certainty:"inferred"},steps:[{actor:"student",deadline:{kind:"date",value:"2026-12-01"}}]};
 assert.strictEqual(core.windowState(item,"2026-10-30"),"unknown");
 item.start.certainty="confirmed";
 assert.strictEqual(core.windowState(item,"2026-10-30"),"open");
 assert.strictEqual(core.windowState(item,"2026-12-02"),"closed");
});


test("申請方式與給付由同一資料列更新，N/A不冒充待確認或受理中",()=>{
 const data=structuredClone(pilot),raw=data.opportunities[0];
 raw.application_method={mode:"electronic",paper_delivery:"not_required",handwritten_signature:"required",deadline_basis:"online_submission"};
 raw.benefit.text="SYNTH 更新後給付";
 raw.start={kind:"unknown",value:null,note:"SYNTH免申請"};
 raw.steps=[];raw.result={kind:"unknown",value:null,note:"SYNTH無審查"};
 raw.field_applicability=Object.fromEntries(["application_start","student_deadline","result_date"].map(k=>[k,{status:"not_applicable",reason:"合成案例：來源明示免申請／無審查",refs:[]} ]));
 const item=core.makeDrafts(data,"2026-10-30")[0];
 assert.equal(item.benefit,"SYNTH 更新後給付");
 assert.match(core.methodText(item.method),/免遞交紙本/);
 assert.match(core.methodText(item.method),/親筆簽名/);
 assert.match(core.startLabel(item),/N\/A 不適用/);
 assert.match(core.deadlineText(item),/N\/A 不適用/);
 assert.match(core.resultText(item),/N\/A 不適用/);
 assert.equal(core.noticeWindow(item),null);
 assert.equal(core.filterItems([item],{application:"unknown"}).length,0);
 assert.equal(core.filterItems([item],{application:"not_applicable"}).length,1);
 const unknown=core.makeDrafts(pilot,"2026-10-30").find(x=>!x.end.value);
 assert.equal(core.deadlineText(unknown),core.UNKNOWN_LABEL);
 assert.doesNotMatch(core.deadlineText(unknown),/N\/A/);
});


test("地方工具補助須檢查個人相對期限，不以年度上限宣稱開放",()=>{
 const candidates=JSON.parse(fs.readFileSync(path.join(__dirname,"../data/candidates/ai-tools-115.json"),"utf8"));
 for(const c of candidates.candidates) {
  const row={...c,steps:c.schedule.steps,start:c.schedule.application_start};
  assert.equal(core.windowState(row,"2026-10-30"),"unknown");
  assert.equal(core.windowState(row,"2026-12-01"),"closed");
  assert.equal(c.category,"research_tools");
 }
});
