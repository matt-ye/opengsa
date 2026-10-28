const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../docs/design/prototype.js");
const today = "2026-10-28";
const demo = core.makeDemo(today);
const pilot = JSON.parse(fs.readFileSync(path.join(__dirname,"../data/pilot.json"),"utf8"));

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
