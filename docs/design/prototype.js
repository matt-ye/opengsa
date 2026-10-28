/* OpenGSA 互動線框：只處理檢視，不進行個人資格核定。 */
(function () {
"use strict";
const DAY = 86400000;
const labels = {
 category: {living_tuition:"生活／學費",living_emergency:"急難支持",phd_research:"博士研究",outcome_award:"成果獎",international_conference:"國際會議",overseas_research:"境外研究",indirect_support:"聘任入口"},
 source: {government:"政府",university:"學校",foundation:"基金會",unknown:"來源待查"},
 degree: {master:"碩士",phd:"博士"},
 year: {unlimited:"明示不限年級",range:"限定年級",unknown:"年級待確認"},
 compatibility: {allowed:"可兼領（限已查範圍）",conditional:"兼領有條件",prohibited:"不可兼領",unknown:"兼領待確認"},
 hardship: {required:"清寒限定",not_exclusive:"非僅清寒",unknown:"清寒限定待確認"}
};
function dayNumber(value) {
 if (!value) return null;
 const text = value.slice(0,10);
 if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return null;
 const number = Date.parse(text+"T00:00:00Z");
 return Number.isFinite(number) && new Date(number).toISOString().slice(0,10) === text ? number/DAY : null;
}
function iso(number) { return new Date(number*DAY).toISOString().slice(0,10); }
function taipeiToday(now = new Date()) {
 const parts = new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(now);
 const part = name => parts.find(x=>x.type===name).value;
 return part("year")+"-"+part("month")+"-"+part("day");
}
function addDays(value, amount) { return iso(dayNumber(value)+amount); }
function event(value=null, certainty="unknown", note="尚無日期") { return {value,certainty,note}; }
function makeDemo(today) {
 const at = offset => addDays(today, offset);
 const seeds = [
  ["SYNTH-A","示範 A｜博士研究支持","phd_research","government",["phd"],"unlimited","conditional","not_exclusive",-18,12,35,"expected"],
  ["SYNTH-B","示範 B｜國際會議補助","international_conference","university",["master","phd"],"unknown","allowed","unknown",-5,24,43,"expected"],
  ["SYNTH-C","示範 C｜清寒生活獎學金","living_tuition","foundation",["master","phd"],"range","prohibited","required",9,35,57,"expected"],
  ["SYNTH-D","示範 D｜研究成果獎","outcome_award","university",["master","phd"],"unknown","unknown","unknown",-32,-7,-2,"confirmed"],
  ["SYNTH-E","示範 E｜境外移地研究","overseas_research","government",["phd"],"unlimited","conditional","not_exclusive",-10,27,null,"unknown"],
  ["SYNTH-F","示範 F｜急難支持","living_emergency","university",["master","phd"],"unknown","unknown","unknown",null,null,null,"unknown"]
 ];
 return seeds.map(([id,title,category,source,degrees,year,compatibility,hardship,start,end,result,certainty]) => ({
  id,title,category,source,degrees,year,compatibility,hardship,
  cycle:"合成排程 · 僅供互動設計",synthetic:true,
  start:event(start===null?null:at(start),start===null?"unknown":"confirmed","合成申請起日"),
  end:event(end===null?null:at(end),end===null?"unknown":"confirmed","合成學生截止"),
  result:event(result===null?null:at(result),certainty,"合成結果日，非官方日期"),
  milestones:id==="SYNTH-E"?[{label:"校內推薦",...event(at(34),"confirmed","合成校內節點")}]:[],
  application:start===null||end===null?"合成：待確認":start>0?"合成：尚未開放":end<0?"合成：已截止":"合成：受理中",evidence:"合成資料",url:null,
  note:"所有名稱、標籤與日期均為虛構；不代表任何實際方案。"
 }));
}
function makeDrafts(pilot) {
 const funding = {
  "ntu-tuition-115-1":"government","ntu-emergency-policy":"university",
  "ntu-nstc-phd-115":"government","ntu-moe-phd-115-round2":"government",
  "ntu-med-publication-115":"university","ntu-president-114":"university",
  "nstc-grad-conference-policy":"government","nstc-abroad-116-ntu":"government",
  "ntu-yuanxue-115-ordinary":"university","ntu-ta-policy":"university"
 };
 const sourceMap = new Map(pilot.sources.map(s=>[s.id,s]));
 return pilot.opportunities.map(item => {
  const student = item.steps.find(s=>s.actor==="student" && ["date","datetime"].includes(s.deadline.kind));
  const milestones = item.steps.filter(s=>s.actor!=="student" && ["date","datetime"].includes(s.deadline.kind)).map(s=>({
   label:{college:"學院送件",institution:"機關送件",university:"校級程序",unit:"單位程序"}[s.actor] || "其他程序",
   ...event(s.deadline.value,"confirmed",s.action+"；"+s.deadline.note)
  }));
  const sources = [...item.application.refs,...item.steps.flatMap(s=>s.refs)];
  const source = sources.map(r=>sourceMap.get(r.source)).find(Boolean);
  return {
   id:item.id,title:item.title,category:item.category,source:funding[item.id]||"unknown",
   degrees:item.eligibility.degrees,year:item.eligibility.year_limit.mode,
   compatibility:item.compatibility.mode,hardship:item.hardship.mode,
   cycle:item.cycle.label,synthetic:false,
   start:event(null,"unknown","現有契約尚無結構化申請起日；不從敘述推算"),
   end:event(student?.deadline.value||null,student?"confirmed":"unknown",student?.deadline.note||"學生截止尚未確認"),
   result:event(null,"unknown","結果公布日尚無結構化證據"),
   milestones,
   application:({open:"摘要顯示受理中",closed:"本期已截止",unknown:"受理待確認",not_yet_open:"尚未開放"})[item.application.state],
   evidence:item.evidence_status==="incomplete"?"資料不完整／草稿":"草稿待獨立覆核",
   url:source?.url||null,note:item.application.reason+"；所有資料皆待獨立覆核。"
  };
 });
}
function filterItems(items, filters) {
 const query = (filters.query||"").trim().toLocaleLowerCase();
 return items.filter(item=>{
  if(query && !(item.title+" "+item.id+" "+item.cycle).toLocaleLowerCase().includes(query)) return false;
  return ["category","source","degree","year","compatibility","hardship"].every(key=>{
   const wanted=filters[key];
   if(!wanted || wanted==="all") return true;
   const value=key==="degree"?item.degrees:item[key];
   if(Array.isArray(value)) return value.includes(wanted);
   return value===wanted || (filters.includeUnknown && value==="unknown");
  });
 });
}
function domain(items,today,mode="recent",offset=0) {
 const current=dayNumber(today);
 if(mode==="fit") {
  const values=items.flatMap(x=>[x.start.value,x.end.value,x.result.value,...x.milestones.map(m=>m.value)]).map(dayNumber).filter(x=>x!==null);
  const low=Math.min(current,...values), high=Math.max(current,...values);
  return {start:low-7,end:Math.max(high+7,low+42)};
 }
 return {start:current-21+offset,end:current+69+offset};
}
function position(value, range) {
 const day=dayNumber(value);
 return day===null ? null : (day-range.start)/(range.end-range.start+1)*100;
}
function centerScroll(percent,totalWidth,viewportWidth,labelWidth) {
 const maximum=Math.max(0,totalWidth-viewportWidth);
 return Math.min(maximum,Math.max(0,percent/100*(totalWidth-labelWidth)-(viewportWidth-labelWidth)/2));
}
function geometry(item, range) {
 const s=dayNumber(item.start.value), e=dayNumber(item.end.value), r=dayNumber(item.result.value);
 const visible=value=>value!==null && value>=range.start && value<=range.end;
 const invalid=s!==null && e!==null && e<s;
 const bar=s!==null && e!==null && !invalid && e>=range.start && s<=range.end
  ? {left:position(iso(Math.max(s,range.start)),range),width:(Math.min(e,range.end)-Math.max(s,range.start)+1)/(range.end-range.start+1)*100} : null;
 return {bar,invalid,
  start:visible(s)?position(item.start.value,range):null,
  end:visible(e)?position(item.end.value,range):null,
  result:visible(r)?position(item.result.value,range):null,
  wait:e!==null && r!==null && r>=e && r>=range.start && e<=range.end
   ? {left:position(iso(Math.max(e,range.start)),range),width:(Math.min(r,range.end)-Math.max(e,range.start))/(range.end-range.start+1)*100} : null
 };
}
function dateText(value) { return value ? value.slice(0,10).replaceAll("-","/")+(value.length>10?" "+value.slice(11,16):"") : "待確認"; }
const api={dayNumber,iso,taipeiToday,addDays,makeDemo,makeDrafts,filterItems,domain,position,centerScroll,geometry};
if(typeof module!=="undefined" && module.exports) module.exports=api;
if(typeof document==="undefined") return;

const byId=id=>document.getElementById(id);
const pilot=JSON.parse(byId("pilot-data").textContent);
const drafts=makeDrafts(pilot);
let today=taipeiToday(), mode="demo", view="gantt", rangeMode="recent", offset=0, selectedId=null, lastRange=null, centerPending=true;
const state={query:"",category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all",includeUnknown:true};
function el(tag, cls, text) {
 const node=document.createElement(tag);
 if(cls) node.className=cls;
 if(text!==undefined) node.textContent=text;
 return node;
}
function axis(text,kind="") { return el("span","axis "+kind,text); }
function selectedButtons(container,attribute,value) {
 document.querySelectorAll(container+" button").forEach(button=>{
  const active=button.dataset[attribute]===value;
  button.setAttribute("aria-pressed",String(active));
 });
}
function activatePanel(id, focus=false) {
 if(!["search","detail","timeline","rights"].includes(id)) id="search";
 document.querySelectorAll('[role="tab"]').forEach(tab=>{
  const active=tab.dataset.panel===id;
  tab.setAttribute("aria-selected",String(active));
  tab.tabIndex=active?0:-1;
  if(active && focus) tab.focus();
 });
 document.querySelectorAll("main > .screen").forEach(panel=>{panel.hidden=panel.id!==id;});
 if(location.hash!=="#"+id) history.replaceState(null,"","#"+id);
 window.scrollTo(0,0);
 if(id==="search" && lastRange) requestAnimationFrame(()=>centerToday(lastRange));
}
document.querySelector('[role="tablist"]').addEventListener("click",event=>{
 const tab=event.target.closest('[role="tab"]');
 if(tab) activatePanel(tab.dataset.panel);
});
document.querySelector('[role="tablist"]').addEventListener("keydown",event=>{
 const tabs=[...document.querySelectorAll('[role="tab"]')];
 const index=tabs.indexOf(event.target);
 if(index<0 || !["ArrowLeft","ArrowRight","Home","End"].includes(event.key)) return;
 event.preventDefault();
 const next=event.key==="Home"?0:event.key==="End"?tabs.length-1:(index+(event.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;
 activatePanel(tabs[next].dataset.panel,true);
});
document.addEventListener("click",event=>{
 const link=event.target.closest('a[href^="#"]');
 if(link && ["#search","#detail","#timeline","#rights"].includes(link.getAttribute("href"))) {
  event.preventDefault();activatePanel(link.getAttribute("href").slice(1));
 }
});
window.addEventListener("hashchange",()=>activatePanel(location.hash.slice(1)));
function itemTags(item) {
 return [labels.source[item.source],item.degrees.map(x=>labels.degree[x]).join("／"),labels.year[item.year],labels.compatibility[item.compatibility],labels.hardship[item.hardship]];
}
function inspect(item) {
 selectedId=item.id;
 const box=byId("schedule-inspect");box.replaceChildren();
 box.append(el("strong","",item.title));
 box.append(el("p","small","申請開始："+dateText(item.start.value)+"　→　學生截止："+dateText(item.end.value)+"　→　"+(item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value)));
 item.milestones.forEach(m=>box.append(el("p","small",m.label+"："+dateText(m.value))));
 box.append(el("p","tiny quiet",item.synthetic?"合成排程，全部為虛構日期。":item.note));
 if(item.url) {const link=el("a","small","核對官方來源 ↗");link.href=item.url;box.append(link);}
 box.hidden=false;
}
function drawCards(items) {
 const list=byId("result-cards");list.replaceChildren();
 items.forEach(item=>{
  const card=el("article","card");
  card.append(el("div","category",labels.category[item.category]+" · "+item.cycle));
  card.append(el("h3","",item.title));
  const axes=el("div","axes");
  axes.append(axis("資格："+(item.synthetic?"未進行比對":"待補資料／人工核對"),"warn"),axis("受理："+item.application),axis("證據："+item.evidence,"info"));card.append(axes);
  const tags=el("div","pills");itemTags(item).forEach(tag=>tags.append(el("span","pill",tag)));card.append(tags);
  card.append(el("p","small","申請開始 "+dateText(item.start.value)+" → 學生截止 "+dateText(item.end.value)+" → "+(item.result.certainty==="expected"?"預定":"")+"結果 "+dateText(item.result.value)));
  const button=el("button","secondary","檢視時程摘要");button.type="button";button.addEventListener("click",()=>inspect(item));card.append(button);
  list.append(card);
 });
}
function tickNode(text,percent,cls="tick") {
 const node=el("span",cls,text);node.style.left=percent+"%";return node;
}
function todayLine(plot, range, header=false) {
 const p=position(today,range);
 if(p===null||p<0||p>=100) return;
 const line=el("span","today-line"+(header?" header-today":""));
 line.style.left=p+"%";
 line.setAttribute("aria-hidden","true");
 if(header) line.append(el("span","today-badge","今天"));
 plot.append(line);
}
function marker(plot,percent,kind,label,item) {
 if(percent===null) return;
 const node=el("button","gantt-marker "+kind);
 node.type="button";node.style.left=percent+"%";
 node.title=label;node.setAttribute("aria-label",item.title+"："+label);
 node.addEventListener("click",()=>inspect(item));plot.append(node);
}
function drawGantt(items,range) {
 const grid=byId("gantt-grid");grid.replaceChildren();
 grid.style.setProperty("--week-step",7/(range.end-range.start+1)*100+"%");
 const top=el("div","gantt-row gantt-top");
 top.append(el("div","gantt-label gantt-heading","獎助項目／申請時程"));
 const head=el("div","gantt-plot axis-plot");
 for(let day=range.start;day<=range.end;day+=7) head.append(tickNode(iso(day).slice(5).replace("-","/"),position(iso(day),range)));
 const monthMarks=new Set();
 for(let day=range.start;day<=range.end;day++) {
  const month=iso(day).slice(0,7);
  if(!monthMarks.has(month)){monthMarks.add(month);head.append(tickNode(month.replace("-"," 年 ")+" 月",position(iso(day),range),"month-tick"));}
 }
 todayLine(head,range,true);top.append(head);grid.append(top);
 items.forEach(item=>{
  const g=geometry(item,range), row=el("div","gantt-row");
  const label=el("div","gantt-label");
  const button=el("button","row-title",item.title);button.type="button";button.addEventListener("click",()=>inspect(item));
  label.append(button,el("div","tiny quiet",labels.category[item.category]+" · "+labels.source[item.source]));
  label.append(el("div","tiny quiet",dateText(item.start.value)+" → "+dateText(item.end.value)));
  row.append(label);
  const plot=el("div","gantt-plot");todayLine(plot,range);
  if(g.wait) {const wait=el("span","gantt-wait");wait.style.left=g.wait.left+"%";wait.style.width=g.wait.width+"%";wait.setAttribute("aria-hidden","true");plot.append(wait);}
  if(g.bar) {
   const bar=el("button","gantt-bar");
   bar.type="button";bar.style.left=g.bar.left+"%";bar.style.width=g.bar.width+"%";
   bar.title="申請期間："+dateText(item.start.value)+" 至 "+dateText(item.end.value);
   bar.setAttribute("aria-label",item.title+"，"+bar.title);bar.addEventListener("click",()=>inspect(item));plot.append(bar);
  }
  marker(plot,g.start,"start","申請開始："+dateText(item.start.value),item);
  marker(plot,g.end,"end","學生截止："+dateText(item.end.value),item);
  marker(plot,g.result,"result "+(item.result.certainty==="expected"?"expected":""),(item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value),item);
  item.milestones.forEach(m=>{const p=position(m.value,range);if(p!==null&&p>=0&&p<100) marker(plot,p,"milestone",m.label+"："+dateText(m.value),item);});
  const notes=[];
  if(!item.start.value) notes.push("起日待確認");
  if(!item.end.value) notes.push("學生截止待確認");
  if(!item.result.value) notes.push("結果日未確認");
  if(g.invalid) notes.push("起訖衝突，暫不畫期間");
  const hasKnown=[item.start.value,item.end.value,item.result.value,...item.milestones.map(m=>m.value)].some(Boolean);
  if(hasKnown && !g.bar && g.start===null && g.end===null && g.result===null && !item.milestones.some(m=>{const p=position(m.value,range);return p!==null&&p>=0&&p<100;})) notes.push("已知日期在視窗外");
  plot.append(el("div","gantt-notes",notes.join(" · ")));
  row.append(plot);grid.append(row);
 });
}
function drawTable(items) {
 const body=byId("date-rows");body.replaceChildren();
 items.forEach(item=>{
  const row=el("tr");[item.title,dateText(item.start.value),dateText(item.end.value),(item.result.certainty==="expected"?"預定 ":"")+dateText(item.result.value),item.milestones.map(m=>m.label+" "+dateText(m.value)).join("；")||"—"].forEach(text=>row.append(el("td","",text)));body.append(row);
 });
}
function centerToday(range) {
 const scroll=document.querySelector(".gantt-scroll"), grid=byId("gantt-grid");
 const percent=position(today,range);
 if(!grid.offsetWidth || percent===null || percent<0 || percent>=100) return;
 const label=grid.querySelector(".gantt-label").offsetWidth;
 scroll.scrollLeft=centerScroll(percent,grid.clientWidth,scroll.clientWidth,label);
}
function render() {
 const items=mode==="demo"?makeDemo(today):drafts;
 const found=filterItems(items,state), range=domain(found,today,rangeMode,offset);
 if(lastRange && rangeMode==="fit" && (lastRange.start!==range.start || lastRange.end!==range.end)) centerPending=true;
 lastRange=range;
 byId("result-count").textContent="顯示 "+found.length+" / "+items.length+" 項";
 byId("mode-note").textContent=mode==="demo"
  ? "合成排程示範：名稱、身分標籤、起訖與結果日全部虛構，只用於確認互動。"
  : "來源草稿：10筆既有候選資料，全部待獨立覆核；尚無結構化起日與結果日，僅標示已記錄期限。";
 byId("mode-note").classList.toggle("synthetic-note",mode==="demo");
 byId("chart-range").textContent=iso(range.start).replaceAll("-","/")+" — "+iso(range.end).replaceAll("-","/")+" · 臺北時間";
 byId("today-label").textContent="今天 "+today.replaceAll("-","/");
 byId("outside-today").hidden=!(dayNumber(today)<range.start || dayNumber(today)>range.end);
 byId("empty-results").hidden=found.length>0;
 byId("gantt-view").hidden=view!=="gantt" || !found.length;
 byId("list-view").hidden=view!=="list" || !found.length;
 byId("dates-table").hidden=!found.length;
 selectedButtons("#mode-switch","mode",mode);selectedButtons("#view-switch","view",view);
 drawCards(found);drawGantt(found,range);drawTable(found);
 if(centerPending && view==="gantt" && found.length && !byId("search").hidden){requestAnimationFrame(()=>centerToday(range));centerPending=false;}
 if(selectedId){const selected=found.find(x=>x.id===selectedId);if(selected) inspect(selected);else{selectedId=null;byId("schedule-inspect").hidden=true;}}
}
document.querySelectorAll("[data-filter]").forEach(input=>{
 const update=()=>{state[input.dataset.filter]=input.type==="checkbox"?input.checked:input.value;render();};
 input.addEventListener(input.type==="search"?"input":"change",update);
});
function resetFilters() {
 Object.assign(state,{query:"",category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all",includeUnknown:true});
 document.querySelectorAll("[data-filter]").forEach(input=>{if(input.type==="checkbox") input.checked=true;else input.value=state[input.dataset.filter];});
 render();
}
byId("reset-filters").addEventListener("click",resetFilters);
byId("empty-reset").addEventListener("click",resetFilters);
byId("mode-switch").addEventListener("click",event=>{const button=event.target.closest("[data-mode]");if(button){mode=button.dataset.mode;selectedId=null;centerPending=true;byId("schedule-inspect").hidden=true;render();}});
byId("view-switch").addEventListener("click",event=>{const button=event.target.closest("[data-view]");if(button){view=button.dataset.view;centerPending=true;render();}});
byId("range-mode").addEventListener("change",event=>{rangeMode=event.target.value;offset=0;centerPending=true;render();});
byId("previous-range").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset-=30;render();});
byId("next-range").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset+=30;render();});
byId("return-today").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset=0;centerPending=true;render();});
function refreshToday(){const value=taipeiToday();if(value!==today){today=value;render();}}
document.addEventListener("visibilitychange",()=>{if(!document.hidden) refreshToday();});
window.addEventListener("focus",refreshToday);
window.addEventListener("resize",()=>{if(lastRange && view==="gantt" && !byId("search").hidden) requestAnimationFrame(()=>centerToday(lastRange));});
setInterval(refreshToday,60000);
activatePanel(location.hash.slice(1));render();
}());
