const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../docs/design/prototype.js");
const today = "2026-10-28";
const demo = core.makeDemo(today);
const pilot = JSON.parse(fs.readFileSync(path.join(__dirname,"../data/pilot.json"),"utf8"));
const conferenceData=JSON.parse(fs.readFileSync(path.join(__dirname,"../data/conference-programs.json"),"utf8"));

test("機構時間規則不依賴學生截止閘門，缺日期仍保留角色與來源",()=>{
 const id=pilot.opportunities[0].id;
 const policy={version:"time-policy-1",submission_mode:"event_relative",review_mode:"not_stated",gaps:["needs_event_date","student_window_not_recorded"],rules:[
  {kind:"event_relative",actor:"institution",stage:"submission",summary:"SYNTH 會前兩個曆月",value:null,anchor_event:"conference_start",source_refs:[{locator:"SYNTH"}]}]};
 const meta={url:"https://example.test/synth",revision:"SYNTH",observed_at:"2026-11-03T00:00:00+08:00",unsafe:false,known:{},organizations:{},time_steps:[],time_policy:policy};
 const item=core.makeDrafts(pilot,"2026-11-03",{records:{[id]:meta}})[0];
 assert.equal(item.end.value,null);assert.equal(item.timeRule,null);
 assert.equal(item.rawState,core.makeDrafts(pilot,"2026-11-03")[0].rawState);
 assert.equal(core.timePresentation(item).mode,"event_relative");
 assert.equal(core.timePresentation(item).rules[0].actor,"institution");
 assert.equal(core.timePresentation(item).rules[0].value,null);
 assert.ok(core.timePresentation(item).gaps.some(s=>s.includes("所屬單位")));
});

test("條件上限保持條件標記，常態規則不補日期，來源衝突不顯示規則",()=>{
 const base={start:{value:null},end:{value:null},result:{value:null},milestones:[],timePolicy:{submission_mode:"recurring",rules:[{kind:"recurring",actor:"unit",stage:"submission",value:null}],gaps:[]}};
 assert.equal(core.timePresentation(base).mode,"recurring");
 const conditional={...base,start:{value:"2026-01-01"},end:{value:"2026-11-10"},timePolicy:{...base.timePolicy,submission_mode:"conditional_deadline"}};
 assert.equal(core.timePresentation(conditional).mode,"conditional_deadline");
 const unsafe=core.timePresentation({...base,conflict:true});
 assert.equal(unsafe.mode,"undetermined");assert.deepEqual(unsafe.rules,[]);
 const example={...base,start:{value:"2026-06-01"},end:{value:"2026-06-30"},timeline:{isExample:true}};
 assert.equal(core.timePresentation(example).mode,"fixed_window");
 assert.equal(core.timePresentation(example).rules[0].actor,"unit");
});

test("地方時程全局綜覽依單位／梯次分列，範例與歷史不改全局受理",()=>{
 const item={id:"SYNTH",title:"SYNTH",start:{value:null},end:{value:null},result:{value:null},milestones:[],rawState:"unknown",application:"待確認",note:"SYNTH",degrees:[]};
 const data={documents:[{id:"d",url:"https://example.test/call",checked_on:"2026-07-01"}],records:{SYNTH:{contexts:[
  {scope:"unit",scope_label:"合成單位",year:2026,phase:"annual",conflict:false,events:[
   {id:"a",kind:"announcement",value:"2026-06-01",document_id:"d"},
   {id:"s",kind:"application_start",value:"2026-07-08",document_id:"d"},
   {id:"e",kind:"student_deadline",value:"2026-07-27T17:00:00+08:00",document_id:"d"},
   {id:"f",kind:"college_forward",value:"2026-08-01",document_id:"d"}],baselines:[]},
  {scope:"unit",scope_label:"合成單位",year:2027,phase:"annual",conflict:false,events:[],baselines:[
   {start:"2027-07-07",end:"2027-07-27",sample_years:[2025,2026],kind:"historical_estimate"}]}]}}};
 assert.equal(core.applyTimeline(item,data,"general",2026),item);
 assert.equal(core.applyTimeline(item,data,"other",2026),item);
 item.timeSteps=[{actor:"university",action:"合成原公告程序",deadline:{value:"2026-08-01"}}];
 const actual=core.applyTimeline(item,data,"unit",2026,true,"2026-07-10");
 assert.equal(actual.start.value,"2026-07-08");assert.equal(actual.end.value,"2026-07-27T17:00:00+08:00");
 assert.equal(actual.rawState,"open");assert.deepEqual(actual.degrees,[]);assert.equal(item.start.value,null);
 const overview=core.applyTimeline(item,data,"examples",2026,true,"2026-07-10");
 assert.equal(overview.start.value,"2026-07-08");assert.equal(overview.rawState,"unknown");
 assert.equal(overview.application,item.application);assert.equal(overview.timeline.examples[0].timeline.scopeLabel,"合成單位");
 assert.deepEqual(overview.timeSteps,item.timeSteps);
 assert.equal(actual.milestones.find(x=>x.note==="college_forward").value,"2026-08-01");
 const forecast=core.applyTimeline(item,data,"unit",2027,true,"2027-07-10");
 assert.equal(forecast.rawState,"unknown");assert.equal(forecast.start.value,null);
 assert.equal(forecast.timeline.baselines.length,1);
 assert.equal(core.applyTimeline(item,data,"unit",2027,false).timeline.baselines.length,0);
 const range=core.domain([forecast],"2026-11-01","fit");
 assert.ok(range.end>=core.dayNumber("2027-07-27"));
 data.records.SYNTH.contexts[0].conflict=true;
 const conflict=core.applyTimeline(item,data,"unit",2026,true,"2026-07-10");
 assert.equal(conflict.start.value,null);assert.equal(conflict.rawState,"unknown");
 data.records.SYNTH.contexts[0].conflict=false;
 data.documents[0].checked_on="2020-01-01";
 assert.equal(core.applyTimeline(item,data,"unit",2026,true,"2026-07-10").rawState,"unknown");
 data.documents[0].checked_on="2026-07-01";
 for(const e of data.records.SYNTH.contexts[0].events)e.certainty="expected";
 const expected=core.applyTimeline(item,data,"unit",2026,true,"2026-07-10");
 assert.equal(expected.rawState,"unknown");assert.equal(expected.start.value,null);
 assert.ok(expected.milestones.some(e=>e.label==="預定 申請開始"));
 for(const e of data.records.SYNTH.contexts[0].events)e.certainty="announced";
 data.records.SYNTH.contexts.push({...data.records.SYNTH.contexts[0],phase:"round2"});
 const multiple=core.applyTimeline(item,data,"unit",2026,true,"2026-07-10");
 assert.equal(multiple.start.value,null);assert.equal(multiple.timeline.multiPhase,true);
 // Global overview retains separate unit/round tracks, never a fabricated combined interval.
 data.records.SYNTH.contexts.push({...data.records.SYNTH.contexts[0],scope:"other",scope_label:"其他合成系所",
  events:data.records.SYNTH.contexts[0].events.map(e=>({...e,id:"other-"+e.id,value:e.kind==="student_deadline"?"2026-08-15":e.value}))});
 const all=core.applyTimeline(item,data,"examples",2026,true,"2026-07-10");
 assert.equal(all.timeline.examples.length,3);assert.equal(all.start.value,null);assert.equal(all.end.value,null);
 assert.equal(all.rawState,item.rawState);assert.equal(all.timeline.conflict,false);
 assert.deepEqual(all.timeline.examples.map(e=>e.timeline.scopeLabel),["合成單位","合成單位","其他合成系所"]);
 assert.equal(all.timeline.examples[0].end.value,"2026-07-27T17:00:00+08:00");
 assert.equal(all.timeline.examples[2].end.value,"2026-08-15");
 assert.ok(core.timelineDates(all).includes("2026-08-15"));
});

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

test("方案代表文件優先較新年度，工具快捷不清除搜尋或受理條件",()=>{
 const old={id:"SYNTH-old",programKey:"SYNTH",cycleKind:"academic_year",cycleYear:114,cycle:"114學年度"};
 const newer={...old,id:"SYNTH-new",cycleYear:115,cycle:"115學年度"};
 assert.equal(core.groupDocuments([old,newer])[0].id,"SYNTH-new");
 assert.equal(core.groupDocuments([newer,old])[0].id,"SYNTH-new");
 assert.equal(core.groupDocuments([{...old,cycleYear:2025},newer])[0].id,"SYNTH-new");
 const filters=core.applyPersona({query:"GitHub",application:"open",includeUnknown:false},"research_tools");
 assert.equal(filters.category,"research_tools");assert.equal(filters.query,"GitHub");
 assert.equal(filters.application,"open");assert.equal(filters.includeUnknown,false);
});

test("公告年份推估只顯示參考帶，不升格為官方起訖或受理中",()=>{
 const events=[{kind:"application_start",value:"2026-11-01",certainty:"expected",basis:"publication_year_context",document_id:"SYNTH-doc"},
  {kind:"student_deadline",value:"2026-11-30",certainty:"expected",basis:"publication_year_context",document_id:"SYNTH-doc"}];
 const baseline={start:"2026-11-01",end:"2026-11-30",kind:"publication_year_reference",sample_years:[2026]};
 const item={id:"SYNTH-reference",cycleKind:"academic_year",rawState:"unknown",application:"待確認",start:{value:null},end:{value:null},result:{value:null}};
 const data={documents:[{id:"SYNTH-doc",checked_on:"2026-11-02"}],records:{[item.id]:{contexts:[{scope:"SYNTH",scope_label:"合成",year:2026,phase:"annual",events,baselines:[baseline],document_ids:["SYNTH-doc"]}]}}};
 const output=core.applyTimeline(item,data,"SYNTH",2026,true,"2026-11-02");
 assert.equal(output.rawState,"unknown");assert.equal(output.start.value,null);assert.equal(output.end.value,null);
 assert.equal(output.timeline.baselines.length,1);assert.match(output.milestones[0].label,/公告年份推估/);
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

test("權益跨主題連結揭露目標、展開規劃並維持焦點，未知目標不跳錯頁",()=>{
 const vm=require("node:vm");
 const js=fs.readFileSync(path.join(__dirname,"../docs/design/prototype.js"),"utf8");
 const groups=["overview","pay","standards","grievance"].map(view=>({dataset:{rightsSection:view},hidden:view!=="overview"}));
 let panel=null,selected=null,focused=false,scrolled=false;
 const details={open:false,parentElement:null};
 const target={tabIndex:-1,closest:selector=>selector==="main > .screen"?{id:"rights"}:selector==="[data-rights-section]"?groups[1]:details,
  scrollIntoView:options=>{assert.equal(groups[1].hidden,false);assert.equal(details.open,true);assert.equal(options.behavior,"instant");scrolled=true;},
  focus:()=>{focused=true;}};
 const scope={byId:id=>id==="salary-target"?target:null,activatePanel:id=>{panel=id;},
  selectedButtons:(_selector,_key,value)=>{selected=value;},document:{querySelectorAll:()=>groups},
  location:{hash:"#rights"},history:{replaceState:(_state,_title,hash)=>{scope.location.hash=hash;}}};
 vm.createContext(scope);
 for(const [begin,end] of [["function setRightsView(",'\nif(byId("rights-view-switch"))'],["function scrollToInternalTarget(",'\ndocument.addEventListener("click"']]){
  const start=js.indexOf(begin);vm.runInContext(js.slice(start,js.indexOf(end,start)),scope);
 }
 assert.equal(scope.scrollToInternalTarget("salary-target"),true);
 assert.equal(panel,"rights");assert.equal(selected,"pay");assert.equal(focused,true);assert.equal(scrolled,true);
 assert.equal(scope.location.hash,"#salary-target");
 assert.deepEqual(groups.map(g=>g.hidden),[true,false,true,true]);
 panel=null;assert.equal(scope.scrollToInternalTarget("missing"),false);assert.equal(panel,null);
 scope.setRightsView("invalid");assert.deepEqual(groups.map(g=>g.hidden),[false,true,true,true]);
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

test("跨Chunk與多文件Map-Reduce合成之fixed_window與學院里程碑可投影至甘特圖",()=>{
 const id=pilot.opportunities[0].id;
 const policy={
  version:"time-policy-1",
  submission_mode:"fixed_window",
  review_mode:"batch",
  gaps:[],
  rules:[
   {rule_id:"model_verified/0",kind:"absolute",actor:"student",stage:"application_start",summary:"來源明示受理起日",value:"2026-06-01",precision:"date",anchor_event:null,source_refs:[{source:"s1",revision_id:"r1",locator:"HTML/p1",evidence_path:"temporal_model_verified/application_start"}]},
   {rule_id:"model_verified/1",kind:"absolute",actor:"student",stage:"submission",summary:"來源明示收件截止",value:"2026-07-29T08:00:00+08:00",precision:"datetime",anchor_event:null,source_refs:[{source:"s1",revision_id:"r2",locator:"PDF/p2",evidence_path:"temporal_model_verified/submission",url:"https://example.test/call.pdf"}]},
   {rule_id:"model_verified/2",kind:"absolute",actor:"college",stage:"submission",summary:"來源明示學院彙送截止",value:"2026-08-05",precision:"date",anchor_event:null,source_refs:[{source:"s1",revision_id:"r1",locator:"HTML/p2",evidence_path:"temporal_model_verified/submission"}]},
   {rule_id:"model_verified/3",kind:"absolute",actor:"other",stage:"result",summary:"來源明示結果公布日",value:"2026-10-15",precision:"date",anchor_event:null,source_refs:[{source:"s1",revision_id:"r2",locator:"PDF/p3",evidence_path:"temporal_model_verified/result",url:"https://example.test/call.pdf"}]}
  ]
 };
 const meta={
  url:"https://example.test/synth",
  revision:"r1",
  observed_at:"2026-11-03T00:00:00+08:00",
  unsafe:false,
  known:{},
  organizations:{},
  time_steps:[],
  time_policy:policy,
  time_observed_at:"2026-11-03T00:00:00+08:00",
  time_revision:"r1",
  time_dates:{
   start:{value:"2026-06-01",certainty:"confirmed"},
   end:{value:"2026-07-29T08:00:00+08:00",certainty:"confirmed"},
   result:{value:"2026-10-15",certainty:"confirmed"}
  }
 };
 const item=core.makeDrafts(pilot,"2026-06-15",{records:{[id]:meta}})[0];
 assert.equal(item.start.value,"2026-06-01");
 assert.equal(item.end.value,"2026-07-29T08:00:00+08:00");
 assert.equal(item.result.value,"2026-10-15");
 assert.equal(item.milestones.length,1);
 assert.equal(item.milestones[0].label,"學院截止");
 assert.equal(item.milestones[0].value,"2026-08-05");
 assert.equal(core.timePresentation(item).mode,"fixed_window");
 const range=core.domain([item],"2026-06-15","fit");
 const geom=core.geometry(item,range);
 assert.ok(geom.bar && geom.bar.width>0);
 assert.ok(geom.wait && geom.wait.width>0);
});

test("URL 狀態序列化與反序列化支援深層連結與稀疏編碼",()=>{
 const parsed = core.parseUrlParams("?tab=detail&id=ntu-med-publication-115&q=%E8%AB%96%E6%96%87&cat=outcome_award&deg=phd&picks=a,b&compare=ntu-president-114", "");
 assert.equal(parsed.tab, "detail");
 assert.equal(parsed.id, "ntu-med-publication-115");
 assert.equal(parsed.query, "論文");
 assert.equal(parsed.category, "outcome_award");
 assert.equal(parsed.degree, "phd");
 assert.equal(parsed.compare, "ntu-president-114");
 assert.deepEqual(parsed.picks, ["a", "b"]);

 const serialized = core.serializeStateToParams({
  tab: "detail",
  mode: "draft",
  view: "list",
  query: "論文",
  category: "outcome_award",
  degree: "phd",
  id: "ntu-med-publication-115",
  compare: "ntu-president-114",
  picks: ["a", "b"]
 }, "demo");
 assert.ok(serialized.includes("tab=detail"));
 assert.ok(serialized.includes("mode=draft"));
 assert.ok(serialized.includes("cat=outcome_award"));
 assert.ok(serialized.includes("id=ntu-med-publication-115"));
 assert.ok(serialized.includes("compare=ntu-president-114"));
 assert.ok(serialized.includes("picks=a%2Cb"));
});

test("搜尋擴充同義詞比對：搜尋論文／著作／醫學院均能精確命中臺大醫學院研究生優秀著作獎",()=>{
 const drafts = core.makeDrafts(pilot, "2026-11-04");
 const medPub = drafts.find(x => x.id === "ntu-med-publication-115");
 assert.ok(medPub, "臺大醫學院優秀著作獎應存在於 drafts 中");
 assert.ok(core.itemMatchesQuery(medPub, "論文"), "搜尋「論文」應命中著作獎");
 assert.ok(core.itemMatchesQuery(medPub, "著作"), "搜尋「著作」應命中著作獎");
 assert.ok(core.itemMatchesQuery(medPub, "醫學院"), "搜尋「醫學院」應命中著作獎");
 assert.ok(core.itemMatchesQuery(medPub, "成果獎"), "搜尋「成果獎」應命中著作獎");

 const filteredByPaper = core.filterItems(drafts, {query: "論文"});
 assert.ok(filteredByPaper.some(x => x.id === "ntu-med-publication-115"), "filterItems 應包含醫學院著作獎");

 const filteredByMed = core.filterItems(drafts, {query: "醫學院"});
 assert.ok(filteredByMed.some(x => x.id === "ntu-med-publication-115"), "filterItems 應包含醫學院著作獎");
});

test("搜尋擴充同義詞比對：搜尋頂會／頂級會議／Travel Grant／差旅補助精確命中研討會與出國方案",()=>{
 const drafts = core.makeDrafts(pilot, "2026-11-04");
 const nstcConf = drafts.find(x => x.id === "nstc-grad-conference-policy");
 assert.ok(nstcConf, "國科會研討會補助應存在於 drafts 中");
 assert.ok(core.itemMatchesQuery(nstcConf, "頂會"), "搜尋「頂會」應命中研討會補助");
 assert.ok(core.itemMatchesQuery(nstcConf, "頂級會議"), "搜尋「頂級會議」應命中研討會補助");
 assert.ok(core.itemMatchesQuery(nstcConf, "travel grant"), "搜尋「travel grant」應命中研討會補助");
 assert.ok(core.itemMatchesQuery(nstcConf, "差旅補助"), "搜尋「差旅補助」應命中研討會補助");
 assert.ok(core.itemMatchesQuery(nstcConf, "出國開會"), "搜尋「出國開會」應命中研討會補助");
 assert.ok(core.itemMatchesQuery(nstcConf, "neurips"), "搜尋「neurips」應命中研討會補助");
 assert.ok(core.itemMatchesQuery(nstcConf, "cvpr"), "搜尋「cvpr」應命中研討會補助");

 const filteredByTopConf = core.filterItems(drafts, {query: "頂會"});
 assert.ok(filteredByTopConf.some(x => x.id === "nstc-grad-conference-policy"), "filterItems 搜尋「頂會」應列出研討會補助");

 const samplePerk = {id: "cand-perk-copilot", programKey: "perk-copilot", title: "GitHub Copilot Student", category: "research_tools"};
 assert.ok(core.itemMatchesQuery(samplePerk, "perk"), "搜尋「perk」應命中福利方案");
 assert.ok(core.itemMatchesQuery(samplePerk, "學生福利"), "搜尋「學生福利」應命中福利方案");
 assert.ok(core.itemMatchesQuery(samplePerk, "教育版"), "搜尋「教育版」應命中福利方案");
});

test("全教育階段學歷與身分篩選：支援大學部、高中職與國中小幼兒，杜絕K-12方案被排擠", ()=>{
 const sample = [
  {id:"k12-high", title:"高中職免學費補助", audience:"適用教育階段: senior_high,vocational_high", degrees:[], rawState:"open", category:"living_tuition"},
  {id:"k12-elem", title:"原住民小學清寒助學金", audience:"適用教育階段: elementary,junior_high", degrees:[], rawState:"open", category:"living_tuition"},
  {id:"univ-ug", title:"大專校院優秀學士獎學金", audience:"大專大學部在學學生", degrees:[], rawState:"open", category:"living_tuition"},
  {id:"grad-phd", title:"國科會博士生研究獎學金", audience:"博士班學生", degrees:["phd"], rawState:"open", category:"phd_research"},
  {id:"grad-master", title:"碩士研究生獎助金", audience:"碩士班學生", degrees:["master"], rawState:"open", category:"living_tuition"}
 ];

 const seniorHighOnly = core.filterItems(sample, {degree:"senior_high"});
 assert.deepEqual(seniorHighOnly.map(x=>x.id), ["k12-high"]);

 const basicK12Only = core.filterItems(sample, {degree:"basic_k12"});
 assert.deepEqual(basicK12Only.map(x=>x.id), ["k12-elem"]);

 const ugOnly = core.filterItems(sample, {degree:"undergraduate"});
 assert.deepEqual(ugOnly.map(x=>x.id), ["univ-ug"]);

 const gradOnly = core.filterItems(sample, {degree:"master_phd"});
 assert.deepEqual(gradOnly.map(x=>x.id), ["grad-phd", "grad-master"]);

 const allItems = core.filterItems(sample, {degree:"all"});
 assert.equal(allItems.length, 5);
});

test("出國出訪與國際交流總覽篩選：綜合國際會議與境外研究，一鍵綜覽全庫出國方案", ()=>{
 const travelItems = [
  {id:"conf-1", title:"國際會議出差發表補助", category:"international_conference", resourceKind:"travel_grant", rawState:"open"},
  {id:"study-1", title:"千里馬赴國外研究補助", category:"overseas_research", resourceKind:"travel_grant", rawState:"open"},
  {id:"award-1", title:"國內校長獎學金", category:"outcome_award", resourceKind:"award", rawState:"open"}
 ];

 const allAbroad = core.filterItems(travelItems, {category:"all_abroad"});
 assert.deepEqual(allAbroad.map(x=>x.id), ["conf-1", "study-1"]);

 const confOnly = core.filterItems(travelItems, {category:"international_conference"});
 assert.deepEqual(confOnly.map(x=>x.id), ["conf-1"]);
});

test("情境按鈕擴充：k12_aid與abroad_all快速套用並正確還原", ()=>{
 const base = {query:"", category:"all", source:"all", degree:"all", year:"all", compatibility:"all", hardship:"all", includeUnknown:false};
 
 const k12Persona = core.applyPersona(base, "k12_aid");
 assert.equal(k12Persona.category, "all_k12");
 assert.equal(core.activePersona(k12Persona), "k12_aid");

 const resetK12 = core.applyPersona(k12Persona, "k12_aid");
 assert.equal(resetK12.category, "all");
 assert.equal(core.activePersona(resetK12), null);

 const abroadPersona = core.applyPersona(base, "abroad_all");
 assert.equal(abroadPersona.category, "all_abroad");
 assert.equal(core.activePersona(abroadPersona), "abroad_all");
});

test("新手上手指南規格：4 步驟嚴格受控（<= 4 步）、標題與導覽索引健全", ()=>{
 assert.ok(Array.isArray(core.guideStepTitles));
 assert.equal(core.guideStepTitles.length, 4, "導覽步驟嚴格遵循 Toutour 規範限制在 4 步以內");
 assert.ok(core.guideStepTitles[0].includes("探索與快篩"));
 assert.ok(core.guideStepTitles[1].includes("時程甘特圖"));
 assert.ok(core.guideStepTitles[2].includes("收藏與跨頁行事曆"));
 assert.ok(core.guideStepTitles[3].includes("推播與權益保障"));
});

test("HTML 語意結構防線：頁首快速指南按鈕、4 步驟導覽 Dialog、甘特圖滾動提示與全域 Toast 齊備", ()=>{
 const fs = require("node:fs");
 const html = fs.readFileSync("docs/design/wireframes.html", "utf-8");
 
 // Header button
 assert.ok(html.includes('id="guide-open-btn"'), "頁首必須包含快速上手指南按鈕");
 assert.ok(html.includes("❓ 快速指南"));
 
 // Guide Dialog & 4 steps
 assert.ok(html.includes('id="guide-dialog"'), "必須包含指南 Dialog 容器");
 assert.ok(html.includes('data-step="1"'));
 assert.ok(html.includes('data-step="2"'));
 assert.ok(html.includes('data-step="3"'));
 assert.ok(html.includes('data-step="4"'));
 
 // Stepper Buttons & Dots
 assert.ok(html.includes('id="guide-prev-btn"'));
 assert.ok(html.includes('id="guide-next-btn"'));
 assert.ok(html.includes('id="guide-finish-btn"'));
 assert.ok(html.includes('class="guide-dots"'));
 
 // Gantt Scroll Hint for Mobile
 assert.ok(html.includes('id="gantt-scroll-hint"'), "甘特圖必須掛載行動端橫向捲動提示");
 assert.ok(html.includes('id="scroll-hint-dismiss"'));
 
 // Global Toast
 assert.ok(html.includes('id="global-toast"'), "必須包含全域微回饋 Toast 容器");
});

test("全域快捷鍵與無障礙宣告防線：支援 Escape / ? / 1~4 鍵盤行為定義", ()=>{
 const fs = require("node:fs");
 const js = fs.readFileSync("docs/design/prototype.js", "utf-8");
 
 assert.ok(js.includes('event.key === "Escape"'), "必須監聽 Esc 關閉彈窗");
 assert.ok(js.includes('event.key === "?"'), "必須支援按鍵 ? 喚起指南");
 assert.ok(js.includes('event.key === "/"'), "必須支援按鍵 / 聚焦搜尋框");
 assert.ok(js.includes('event.key === "1"'), "必須支援按鍵 1~4 切換分頁");
 assert.ok(js.includes("showGlobalToast"), "必須包含全域微提示函式");
});

test("Toutour 情境感知專屬子導覽規格：5大導覽體系步數嚴格受控（<= 4 步）、資訊完整", ()=>{
 assert.ok(core.subTours, "必須匯出 subTours 導覽體系");
 const expectedTours = ["global", "search", "detail", "timeline", "rights"];
 for (const key of expectedTours) {
  const tour = core.subTours[key];
  assert.ok(tour, "必須包含子導覽：" + key);
  assert.ok(Array.isArray(tour.steps));
  assert.ok(tour.steps.length <= 4, key + " 導覽步數必須嚴格受控在 4 步以內");
  assert.ok(tour.steps.length >= 3, key + " 導覽步數至少 3 步");
  tour.steps.forEach((step, idx) => {
   assert.ok(step.title, key + " 步驟 " + (idx+1) + " 必須有標題");
   assert.ok(step.desc, key + " 步驟 " + (idx+1) + " 必須有說明");
   assert.ok(step.icon, key + " 步驟 " + (idx+1) + " 必須有圖標");
   assert.ok(Array.isArray(step.features) && step.features.length >= 2, key + " 步驟 " + (idx+1) + " 必須包含特色清單");
  });
 }
});

test("RWD 響應式優化與甘特圖 64px 緊湊防線：消除底部死空白與手機端欄寬優化", ()=>{
 const fs = require("node:fs");
 const html = fs.readFileSync("docs/design/wireframes.html", "utf-8");
 
 // 甘特圖緊湊列高 64px
 assert.ok(html.includes("min-height:64px"), "甘特圖列高必須緊湊化為 64px 以提高單屏可視方案數");
 
 // 消除底部空白
 assert.ok(html.includes(".screen{border-bottom:0;padding:24px 0 20px}"), "首頁 screen 底部 padding 必須收斂為 20px");
 assert.ok(html.includes("footer{max-width:1280px;margin:0 auto;padding:20px 32px 28px"), "footer padding 必須緊湊化消滅懸空");
 
 // 手機端左欄收窄至 108px/112px
 assert.ok(html.includes("--label-width:112px") || html.includes("--label-width:108px"), "手機端甘特圖標籤欄必須收窄以釋出日期軸空間");
 
 // 導覽切換器
 assert.ok(html.includes('id="guide-tour-select"'), "必須包含子導覽切換選單");
 assert.ok(html.includes('value="global"'));
 assert.ok(html.includes('value="search"'));
 assert.ok(html.includes('value="detail"'));
 assert.ok(html.includes('value="timeline"'));
 assert.ok(html.includes('value="rights"'));
});

test("甘特圖資訊卡浮動彈窗與關閉機制：在甘特圖上跳出、點按遮罩/按鈕/Esc可關閉，不遮擋排版", () => {
 const html = fs.readFileSync("docs/design/wireframes.html", "utf-8");
 const js = fs.readFileSync("docs/design/prototype.js", "utf-8");

 // 1. wireframes.html 語意與樣式
 assert.ok(html.includes('id="inspect-backdrop"'), "必須包含浮動資訊卡之遮罩層 #inspect-backdrop");
 assert.ok(html.includes('id="schedule-inspect" role="dialog" aria-modal="true"'), "時程預覽卡必須具備 dialog 語意與 aria-modal");
 assert.ok(html.includes(".inspect-close-btn"), "必須包含關閉按鈕樣式");
 assert.ok(html.includes(".inspect-backdrop"), "必須包含遮罩層樣式");
 assert.ok(html.includes("position:fixed;top:50%;left:50%;transform:translate(-50%,-50%)"), "資訊卡必須居中浮動於甘特圖上方，不擠壓版面");

 // 2. prototype.js 互動行為
 assert.ok(typeof core.closeInspect === "function", "必須匯出 closeInspect 關閉函式");
 assert.ok(js.includes('btn-inspect-detail'), "浮動卡必須包含前往詳情按鈕");
 assert.ok(js.includes('btn-inspect-dismiss'), "浮動卡必須包含關閉預覽按鈕");
 assert.ok(js.includes('inspectCloseBtn'), "關閉按鈕必須綁定關閉事件");
 assert.ok(js.includes('inspectBackdrop.addEventListener("click", closeInspect)'), "點擊遮罩必須關閉浮動卡片");
 assert.ok(!js.includes('box.scrollIntoView({behavior:"instant",block:"start"})'), "開啟預覽卡片時絕對不得觸發 scrollIntoView 造成頁面跳動");
});

test("甘特圖名稱導向與申請區無效勾選框清理：提供查看詳情超連結、移除Tab 3無作用checkbox", () => {
 const html = fs.readFileSync("docs/design/wireframes.html", "utf-8");
 const js = fs.readFileSync("docs/design/prototype.js", "utf-8");

 // 1. 甘特圖名稱導向
 assert.ok(html.includes(".gantt-detail-link"), "甘特圖標籤欄必須包含直達詳情連結樣式");
 assert.ok(js.includes('el("a","gantt-detail-link","查看詳情 →")'), "甘特圖項目旁必須提供查看詳情直達連結");
 assert.ok(js.includes('titleLink.href="#detail"'), "預覽卡標題必須連結至 #detail");

 // 2. 申請區無效 checkbox 清理
 assert.ok(!html.includes('id="plan-progress"'), "必須移除無效待辦進度條 id=plan-progress");
 assert.ok(html.includes('id="plan-count"'), "申請區標題應改為已收錄方案計數器 id=plan-count");
 assert.ok(!js.includes('["核對申請資格","確認學生收件時間","整理申請文件"]'), "必須徹底移除無作用之三項核對勾選清單");
 assert.ok(!js.includes('["核對使用條件","確認開通／領取程序"]'), "必須徹底移除無作用之 N/A 勾選清單");
 assert.ok(!js.includes('el("div","plan-tasks")'), "必須移除無用之 plan-tasks 容器");
 assert.ok(js.includes('✕ 從時間軸移除'), "申請清單卡片必須提供一鍵從時間軸移除按鈕");
});


test("搜尋擴充同義詞比對：搜尋急難救助／學產基金／緊急紓困精確命中生活與急難方案", () => {
 const item = {
  id: "cand-moe-student-aid-emergency",
  title: "教育部學產基金設置急難慰問金",
  category: "living_emergency",
  programKey: "moe-student-aid-emergency"
 };
 assert.ok(core.itemMatchesQuery(item, "急難"), "搜尋急難應命中");
 assert.ok(core.itemMatchesQuery(item, "急難救助"), "搜尋急難救助應命中");
 assert.ok(core.itemMatchesQuery(item, "學產基金"), "搜尋學產基金應命中");
 assert.ok(core.itemMatchesQuery(item, "緊急紓困"), "搜尋緊急紓困應命中");
 assert.ok(core.itemMatchesQuery(item, "emergency relief"), "搜尋英文 emergency relief 應命中");
 assert.ok(core.itemMatchesQuery(item, "救助金"), "搜尋救助金應命中");
 assert.ok(core.itemMatchesQuery(item, "變故"), "搜尋變故應命中");
});

test("急難救助情境按鈕與按鈕島規格：支援「急」急難救助卡一鍵快篩與點擊還原", () => {
 const html = fs.readFileSync(path.join(__dirname, "../docs/design/wireframes.html"), "utf8");
 assert.ok(html.includes('data-persona="emergency_relief"'), "persona-bar 必須包含 emergency_relief 按鈕");
 assert.ok(html.includes('<span aria-hidden="true" class="hex-badge">急</span>'), "必須包含「急」字情境徽章");
 assert.ok(core.personaPresets.emergency_relief, "personaPresets 必須註冊 emergency_relief");
 assert.equal(core.personaPresets.emergency_relief.category, "living_emergency");
 
 const base = {category: "all", source: "all", degree: "all", year: "all", compatibility: "all", hardship: "all"};
 const applied = core.applyPersona(base, "emergency_relief");
 assert.equal(applied.category, "living_emergency", "套用後 category 應為 living_emergency");
 
 const toggled = core.applyPersona(applied, "emergency_relief");
 assert.equal(toggled.category, "all", "再次點擊應還原為 all");
});

test("單親、特境、國際生與縣市急難擴充同義詞精確命中急難救助資源", () => {
 const singleItem = {
  id: "cand-sfaa-special-family",
  title: "衛生福利部特殊境遇家庭扶助－緊急生活扶助與子女生活津貼",
  category: "living_emergency",
  programKey: "sfaa-special-family"
 };
 assert.ok(core.itemMatchesQuery(singleItem, "單親"), "搜尋單親應命中");
 assert.ok(core.itemMatchesQuery(singleItem, "擔心"), "搜尋同音詞擔心應容錯命中");
 assert.ok(core.itemMatchesQuery(singleItem, "特境"), "搜尋特境應命中");
 assert.ok(core.itemMatchesQuery(singleItem, "特殊境遇"), "搜尋特殊境遇應命中");

 const intlItem = {
  id: "cand-ntu-oia-international-emergency",
  title: "國立臺灣大學國際事務處國際學生急難救助金",
  category: "living_emergency",
  programKey: "ntu-oia-emergency"
 };
 assert.ok(core.itemMatchesQuery(intlItem, "國際生"), "搜尋國際生應命中");
 assert.ok(core.itemMatchesQuery(intlItem, "外籍生"), "搜尋外籍生應命中");

 const cityItem = {
  id: "cand-ntpc-emergency-relief",
  title: "新北市好日子愛心大平台急難救助與弱勢學生專案",
  category: "living_emergency",
  programKey: "ntpc-sw-emergency"
 };
 assert.ok(core.itemMatchesQuery(cityItem, "縣市急難"), "搜尋縣市急難應命中");
 assert.ok(core.itemMatchesQuery(cityItem, "好日子"), "搜尋好日子應命中");
});

test("首頁標頭操作列 GitHub Star 按鈕規格：支援一鍵開新分頁直達專案庫按星", () => {
 const html = fs.readFileSync(path.join(__dirname, "../docs/design/wireframes.html"), "utf8");
 assert.ok(html.includes('id="github-star-btn"'), "標頭操作列必須包含 github-star-btn ID");
 assert.ok(html.includes('href="https://github.com/matt-ye/opengsa"'), "必須導向專案開源 repo 網址");
 assert.ok(html.includes('target="_blank"'), "必須於新分頁開啟");
 assert.ok(html.includes('rel="noopener noreferrer"'), "必須具備安全連結屬性");
 assert.ok(html.includes("⭐ GitHub Star ↗"), "按鈕標籤必須顯示 ⭐ GitHub Star ↗");
 assert.ok(html.includes(".header-action.star-btn"), "必須具備專屬金色高亮樣式");
});
