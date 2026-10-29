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
function workspaceItems(items,filtered,selectedIds) {
 return selectedIds.size ? items.filter(item=>selectedIds.has(item.id)) : filtered;
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
function conferencePlan(start,notice=null,buffer=14) {
 const validDate=value=>typeof value==="string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && dayNumber(value)!==null;
 if(!validDate(start) || (notice && !validDate(notice)) || !Number.isInteger(buffer) || buffer<0 || buffer>90) return null;
 const agencyBase=addDays(start.slice(0,7)+"-01",-1).slice(0,7)+"-01";
 const studentBase=addDays(agencyBase,-1), supplement=addDays(start,-28);
 return {agencyBase,studentBase,studentTime:"17:00",supplement,prepare:addDays(studentBase,-buffer),buffer,
  noticeRisk:!notice?"unknown":notice>supplement?"after_supplement":notice>studentBase?"after_submission":"before_submission",
  calendarStatus:"unverified",deadlineStatus:"estimate_pending_calendar"};
}
const api={dayNumber,iso,taipeiToday,addDays,makeDemo,makeDrafts,filterItems,workspaceItems,domain,position,centerScroll,geometry,conferencePlan};
if(typeof module!=="undefined" && module.exports) module.exports=api;
if(typeof document==="undefined") return;

const byId=id=>document.getElementById(id);
const pilot=JSON.parse(byId("pilot-data").textContent);
const drafts=makeDrafts(pilot);
const rawById=new Map(pilot.opportunities.map(item=>[item.id,item]));
const sourceById=new Map(pilot.sources.map(source=>[source.id,source]));
const picked={demo:new Set(),draft:new Set()}, completed={demo:new Set(),draft:new Set()}, activeDetail={demo:null,draft:null};
let sharedItems=[], personalRangeMode="recent", lastPersonalRange=null;
let today=taipeiToday(), mode="demo", view="gantt", rangeMode="recent", offset=0, inspectedId=null, lastRange=null, centerPending=true;
const state={query:"",category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all",includeUnknown:true};
function el(tag, cls, text) {
 const node=document.createElement(tag);
 if(cls) node.className=cls;
 if(text!==undefined) node.textContent=text;
 return node;
}
function axis(text,kind="") { return el("span","axis "+kind,text); }
function updateNavHeight() {
 const height=Math.ceil(document.querySelector(".nav-wrap").getBoundingClientRect().height);
 document.documentElement.style.setProperty("--nav-height",height+"px");
}
updateNavHeight();
if(typeof ResizeObserver!=="undefined") new ResizeObserver(updateNavHeight).observe(document.querySelector(".nav-wrap"));
function renderConferencePlan() {
 const output=byId("conference-output"), start=byId("conference-start").value, notice=byId("conference-notice").value;
 output.replaceChildren();
 if(!start) {output.append(el("p","small","填入會議首日後，試算臺大／國科會這個申請路徑。"));return;}
 const buffer=byId("conference-buffer").value;
 const plan=conferencePlan(start,notice,buffer===""?NaN:Number(buffer));
 if(!plan) {output.append(el("p","small","請確認日期，準備緩衝需為0至90的整數天數。"));return;}
 output.append(el("h4","",byId("conference-name").value.trim()||"我的研討會"),el("p","tiny quiet","條文基準試算 · 未核例假日順延與院系所更早期限；以下不是已確認的正式截止。"));
 const facts=el("dl","facts");
 for(const [label,value] of [["會議首日",dateText(start)],["校方彙送基準",dateText(plan.agencyBase)+"（前一個月首日；待核例假日順延）"],["臺大送出基準",dateText(plan.studentBase)+" 17:00（按未順延基準倒推；正式日期待核）"],["接受函補送",dateText(plan.supplement)+"（會議首日前四週；須依程序註明補送）"],["建議開始準備",dateText(plan.prepare)+"（自訂提前"+plan.buffer+"天，非官方期限）"]]) facts.append(el("dt","",label),el("dd","",value));
 output.append(facts);
 const messages={unknown:"尚未填接受通知日。若接受函未取得，條文允許註明補送；先查申請程序，不必等接受函才開始準備。",after_supplement:"接受通知日可能晚於接受函補送規定。請提早洽承辦確認可行程序；平台不保證例外或核定。",after_submission:"接受通知日在未順延的申請基準後、補送日內。可先查註明補送程序，避免等接受函才開始申請。",before_submission:"接受通知日未晚於試算基準；仍須核例假日、文件及院系所期限，不能據此保證來得及申請。"};
 output.append(el("p","callout",messages[plan.noticeRisk]));
 if(start<=today) output.append(el("p","small","會議已開始或首日已過，以上僅作回顧試算。"));
 else if(plan.studentBase<today) output.append(el("p","small","未順延的學生送出基準已過；請先確認實際順延日期與校內公告，不把估算當成已確認逾期。"));
}
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
 if(id==="timeline" && lastPersonalRange) requestAnimationFrame(()=>centerToday(lastPersonalRange,"personal-gantt-grid"));
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
 inspectedId=item.id;
 const box=byId("schedule-inspect");box.replaceChildren();
 box.append(el("strong","",item.title));
 box.append(el("p","small","申請開始："+dateText(item.start.value)+"　→　學生截止："+dateText(item.end.value)+"　→　"+(item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value)));
 item.milestones.forEach(m=>box.append(el("p","small",m.label+"："+dateText(m.value))));
 box.append(el("p","tiny quiet",item.synthetic?"合成排程，全部為虛構日期。":item.note));
 if(item.url) {const link=el("a","small","核對官方來源 ↗");link.href=item.url;box.append(link);}
 const more=el("button","secondary",picked[mode].has(item.id)?"查看詳情":"勾選並看詳情");more.type="button";more.dataset.openDetail=item.id;
 more.addEventListener("click",()=>chooseAndOpen(item));box.append(more);
 box.hidden=false;
}
function pickControl(item,slot) {
 const label=el("label",slot==="gantt"?"row-pick":"item-pick");
 const input=el("input");input.type="checkbox";input.checked=picked[mode].has(item.id);input.dataset.pickId=item.id;
 input.setAttribute("aria-label","勾選 "+item.title);
 input.addEventListener("change",()=>{if(input.checked) picked[mode].add(item.id);else picked[mode].delete(item.id);renderWorkspace();});
 label.append(input,el("span","","列入我的選項"));return label;
}
function chooseAndOpen(item) {
 picked[mode].add(item.id);activeDetail[mode]=item.id;renderWorkspace();activatePanel("detail");
}
function openSharedDetail(item) {
 activeDetail[mode]=item.id;renderWorkspace();activatePanel("detail");
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
  const actions=el("div","card-actions");actions.append(pickControl(item,"list"));
  const button=el("button","secondary",picked[mode].has(item.id)?"查看詳情":"勾選並看詳情");button.type="button";button.dataset.openDetail=item.id;button.addEventListener("click",()=>chooseAndOpen(item));actions.append(button);card.append(actions);
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
function marker(plot,percent,kind,label,item,onInspect=inspect) {
 if(percent===null) return;
 const node=el("button","gantt-marker "+kind);
 node.type="button";node.style.left=percent+"%";
 node.title=label;node.setAttribute("aria-label",item.title+"："+label);
 node.addEventListener("click",()=>onInspect(item));plot.append(node);
}
function drawGantt(items,range,gridId="gantt-grid",onInspect=inspect) {
 const grid=byId(gridId);grid.replaceChildren();
 grid.style.setProperty("--week-step",7/(range.end-range.start+1)*100+"%");
 const top=el("div","gantt-row gantt-top");
 top.append(el("div","gantt-label gantt-heading","獎助項目／申請時程"));
 const head=el("div","gantt-plot axis-plot");
 const tickStep=range.end-range.start>180?28:range.end-range.start>100?14:7;
 for(let day=range.start;day<=range.end;day+=tickStep) head.append(tickNode(iso(day).slice(5).replace("-","/"),position(iso(day),range)));
 const monthMarks=new Set();
 for(let day=range.start;day<=range.end;day++) {
  const month=iso(day).slice(0,7);
  if(!monthMarks.has(month)){monthMarks.add(month);head.append(tickNode(month.replace("-"," 年 ")+" 月",position(iso(day),range),"month-tick"));}
 }
 todayLine(head,range,true);top.append(head);grid.append(top);
 items.forEach(item=>{
  const g=geometry(item,range), row=el("div","gantt-row");
  const label=el("div","gantt-label");
  if(gridId==="gantt-grid") label.append(pickControl(item,"gantt"));
  const button=el("button","row-title",item.title);button.type="button";button.addEventListener("click",()=>onInspect(item));
  label.append(button,el("div","tiny quiet",labels.category[item.category]+" · "+labels.source[item.source]));
  label.append(el("div","tiny quiet",dateText(item.start.value)+" → "+dateText(item.end.value)));
  row.append(label);
  const plot=el("div","gantt-plot");todayLine(plot,range);
  if(g.wait) {const wait=el("span","gantt-wait");wait.style.left=g.wait.left+"%";wait.style.width=g.wait.width+"%";wait.setAttribute("aria-hidden","true");plot.append(wait);}
  if(g.bar) {
   const bar=el("button","gantt-bar");
   bar.type="button";bar.style.left=g.bar.left+"%";bar.style.width=g.bar.width+"%";
   bar.title="申請期間："+dateText(item.start.value)+" 至 "+dateText(item.end.value);
   bar.setAttribute("aria-label",item.title+"，"+bar.title);bar.addEventListener("click",()=>onInspect(item));plot.append(bar);
  }
  marker(plot,g.start,"start","申請開始："+dateText(item.start.value),item,onInspect);
  marker(plot,g.end,"end","學生截止："+dateText(item.end.value),item,onInspect);
  marker(plot,g.result,"result "+(item.result.certainty==="expected"?"expected":""),(item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value),item,onInspect);
  item.milestones.forEach(m=>{const p=position(m.value,range);if(p!==null&&p>=0&&p<100) marker(plot,p,"milestone",m.label+"："+dateText(m.value),item,onInspect);});
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
function centerToday(range,gridId="gantt-grid") {
 const grid=byId(gridId), scroll=grid.closest(".gantt-scroll");
 const percent=position(today,range);
 if(!grid.offsetWidth || percent===null || percent<0 || percent>=100) return;
 const label=grid.querySelector(".gantt-label").offsetWidth;
 scroll.scrollLeft=centerScroll(percent,grid.clientWidth,scroll.clientWidth,label);
}
function factSection(title,paragraphs) {
 const section=el("section","panel detail-section");section.append(el("h3","",title));
 paragraphs.forEach(text=>section.append(el("p","",text)));return section;
}
function sourceReferences(value,found=new Map()) {
 if(Array.isArray(value)) value.forEach(child=>sourceReferences(child,found));
 else if(value && typeof value==="object") {
  if(typeof value.source==="string" && typeof value.locator==="string") {
   if(!found.has(value.source)) found.set(value.source,new Set());
   found.get(value.source).add(value.locator);
  }
  Object.values(value).forEach(child=>sourceReferences(child,found));
 }
 return found;
}
function drawDetail() {
 const select=byId("detail-option");select.replaceChildren();
 sharedItems.forEach(item=>{const option=el("option","",item.title);option.value=item.id;select.append(option);});
 if(!sharedItems.some(item=>item.id===activeDetail[mode])) activeDetail[mode]=sharedItems[0]?.id||null;
 select.value=activeDetail[mode]||"";
 const index=sharedItems.findIndex(item=>item.id===activeDetail[mode]);
 byId("detail-previous").disabled=index<=0;byId("detail-next").disabled=index<0||index>=sharedItems.length-1;
 const content=byId("detail-content");content.replaceChildren();
 const item=sharedItems[index];if(!item) return;
 const raw=rawById.get(item.id), top=el("div","panel");
 top.append(el("div","category",labels.category[item.category]+" · "+item.cycle),el("h3","detail-title",item.title));
 const axes=el("div","axes");axes.append(axis("資格："+(item.synthetic?"合成示範／未比對":"待補資料／人工核對"),"warn"),axis("受理："+item.application),axis("證據："+item.evidence,"info"));top.append(axes);
 const tags=el("div","pills");itemTags(item).forEach(tag=>tags.append(el("span","pill",tag)));top.append(tags);
 top.append(el("p","small",item.note));content.append(top);
 const columns=el("div","two-col"), left=el("div"), right=el("aside");
 const timing=factSection("申請與結果時程",[
  "申請開始："+dateText(item.start.value)+"；"+item.start.note,
  "學生截止："+dateText(item.end.value)+"；"+item.end.note,
  (item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value)+"；"+item.result.note
 ]);left.append(timing);
 if(raw) {
  const year=raw.eligibility.year_limit;
  const grade=year.mode==="range"?year.min+"–"+year.max+"年級，基準日"+dateText(year.assessed_at):labels.year[year.mode];
  const candidate={required:"須具博士候選人資格",not_required:"明示不要求候選人資格",unknown:"候選人限制待確認"}[raw.eligibility.candidate.mode];
  left.append(factSection("已記錄條件與待確認事項",[raw.eligibility.identity.text,grade,candidate,...raw.eligibility.other_conditions.map(x=>x.text)]));
  left.append(factSection("兼領與清寒條件",[raw.compatibility.note,raw.hardship.note]));
  const procedures=el("section","panel detail-section");procedures.append(el("h3","","各層程序"));
  const steps=el("ol","step-list");
  raw.steps.forEach(step=>{
   const row=el("li");
   const actor={student:"學生",student_or_representative:"學生／代申請人",institution:"申請機構",college:"學院",unit:"單位",university:"校級"}[step.actor]||step.actor;
   row.append(el("strong","",actor+"："+step.action),el("p","",dateText(step.deadline.value)),el("p","quiet",step.deadline.note));steps.append(row);
  });procedures.append(steps);left.append(procedures);
  const summary=factSection("給付與申請角色",[raw.benefit.text]);
  const roles={student:"學生",institution:"申請機構",unit:"單位",employed_student:"受聘學生",unknown:"待確認"};
  const facts=el("dl","facts");
  for(const [label,text] of [["申請者",roles[raw.participants.applicant]],["受益者",roles[raw.participants.beneficiary]],["受獎者",roles[raw.participants.awardee]],["受款者",roles[raw.participants.payee]],["資助",raw.organizations.funder.text],["公告",raw.organizations.announcer.text],["收件",raw.organizations.receiver.text]]) facts.append(el("dt","",label),el("dd","",text));
  summary.append(facts);right.append(summary);
  const evidence=factSection("正式來源與定位",["資料快照："+dateText(pilot.as_of)+"；全部待獨立覆核。"]);
  const links=el("ul","evidence-list");
  sourceReferences(raw).forEach((locators,id)=>{
   const source=sourceById.get(id);if(!source) return;
   const row=el("li"), link=el("a","",source.title+(source.authority==="official_search_excerpt"?"（僅搜尋摘要）":""));link.href=source.url;
   row.append(link,el("p","tiny quiet",[...locators].join("；")));links.append(row);
  });evidence.append(links);right.append(evidence);
  left.append(factSection("下一步待查",raw.open_questions));
 } else {
  left.append(factSection("合成資料的使用範圍",["這個方案與所有日期、標籤都是虛構，沒有正式資格辦法或金額。","切換第一頁的「10筆來源草稿」，可查看對應真實方案的條件、程序與公開依據。"]));
  if(item.milestones.length) left.append(factSection("其他程序節點",item.milestones.map(point=>point.label+"："+dateText(point.value))));
  right.append(factSection("與第一頁同步",["目前查看的是同一批選項中的一項。用上方選單或前後按鈕切換，第三頁也會保留這批選項。"]));
 }
 columns.append(left,right);content.append(columns);
}
function drawPlan() {
 const range=domain(sharedItems,today,personalRangeMode);
 lastPersonalRange=range;
 byId("personal-today").textContent="今天 "+today.replaceAll("-","/");
 byId("personal-chart-range").textContent=iso(range.start).replaceAll("-","/")+" — "+iso(range.end).replaceAll("-","/")+" · 臺北時間";
 drawGantt(sharedItems,range,"personal-gantt-grid",openSharedDetail);
 const cards=byId("plan-options");cards.replaceChildren();
 sharedItems.forEach(item=>{
  const card=el("article","card"), button=el("button","plan-title",item.title);button.type="button";button.addEventListener("click",()=>openSharedDetail(item));card.append(button);
  card.append(el("p","small","學生截止："+dateText(item.end.value)+"　／　"+(item.result.certainty==="expected"?"預定":"")+"結果："+dateText(item.result.value)));
  card.append(el("p","tiny quiet",item.synthetic?"合成資料，僅供規劃示範。":item.evidence+"；缺日期保留待確認。"));
  const tasks=el("div","plan-tasks");
  ["核對申請資格","確認學生收件時間","整理申請文件"].forEach((text,index)=>{
   const key=item.id+":"+index,label=el("label","task-item"),input=el("input");input.type="checkbox";input.checked=completed[mode].has(key);input.setAttribute("aria-label",item.title+"："+text);
   input.addEventListener("change",()=>{if(input.checked) completed[mode].add(key);else completed[mode].delete(key);});
   label.append(input,el("span","",text));tasks.append(label);
  });card.append(tasks);cards.append(card);
 });
 if(!byId("timeline").hidden && sharedItems.length) requestAnimationFrame(()=>centerToday(range,"personal-gantt-grid"));
}
function renderWorkspace() {
 const items=mode==="demo"?makeDemo(today):drafts,filtered=filterItems(items,state),selected=picked[mode];
 sharedItems=workspaceItems(items,filtered,selected);
 const hiddenCount=sharedItems.filter(item=>!filtered.some(found=>found.id===item.id)).length;
 const basis=selected.size?"第一頁已勾選的 "+sharedItems.length+" 項":"第一頁目前篩選的 "+sharedItems.length+" 項（尚未勾選）";
 const text=(mode==="demo"?"合成資料 · ":"來源草稿 · ")+basis+(hiddenCount?"；其中 "+hiddenCount+" 項不在目前篩選結果":"");
 for(const id of ["detail-context","timeline-context"]){byId(id).textContent=text;byId(id).classList.toggle("synthetic-note",mode==="demo");}
 byId("selection-count").textContent="已勾選 "+selected.size+" 項；第二、三頁使用 "+sharedItems.length+" 項"+(selected.size?"已選內容":"篩選結果");
 byId("select-filtered").disabled=!filtered.length;byId("clear-selection").disabled=!selected.size;
 document.querySelectorAll("[data-pick-id]").forEach(input=>{input.checked=selected.has(input.dataset.pickId);});
 document.querySelectorAll("[data-open-detail]").forEach(button=>{button.textContent=selected.has(button.dataset.openDetail)?"查看詳情":"勾選並看詳情";});
 for(const name of ["detail","timeline"]){byId(name+"-empty").hidden=!!sharedItems.length;byId(name+"-workspace").hidden=!sharedItems.length;}
 drawDetail();drawPlan();
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
 renderWorkspace();
 if(centerPending && view==="gantt" && found.length && !byId("search").hidden){requestAnimationFrame(()=>centerToday(range));centerPending=false;}
 if(inspectedId){const inspected=found.find(x=>x.id===inspectedId);if(inspected) inspect(inspected);else{inspectedId=null;byId("schedule-inspect").hidden=true;}}
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
byId("select-filtered").addEventListener("click",()=>{const items=mode==="demo"?makeDemo(today):drafts;filterItems(items,state).forEach(item=>picked[mode].add(item.id));renderWorkspace();});
byId("clear-selection").addEventListener("click",()=>{picked[mode].clear();renderWorkspace();});
byId("detail-option").addEventListener("change",event=>{activeDetail[mode]=event.target.value;drawDetail();});
function moveDetail(amount){const index=sharedItems.findIndex(item=>item.id===activeDetail[mode]);const next=sharedItems[index+amount];if(next){activeDetail[mode]=next.id;drawDetail();}}
byId("detail-previous").addEventListener("click",()=>moveDetail(-1));
byId("detail-next").addEventListener("click",()=>moveDetail(1));
byId("personal-range-mode").addEventListener("change",event=>{personalRangeMode=event.target.value;drawPlan();});
byId("personal-return-today").addEventListener("click",()=>{personalRangeMode="recent";byId("personal-range-mode").value="recent";drawPlan();});
byId("mode-switch").addEventListener("click",event=>{const button=event.target.closest("[data-mode]");if(button){mode=button.dataset.mode;inspectedId=null;centerPending=true;byId("schedule-inspect").hidden=true;render();}});
byId("view-switch").addEventListener("click",event=>{const button=event.target.closest("[data-view]");if(button){view=button.dataset.view;centerPending=true;render();}});
byId("range-mode").addEventListener("change",event=>{rangeMode=event.target.value;offset=0;centerPending=true;render();});
byId("previous-range").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset-=30;render();});
byId("next-range").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset+=30;render();});
byId("return-today").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset=0;centerPending=true;render();});
function refreshToday(){const value=taipeiToday();if(value!==today){today=value;render();renderConferencePlan();}}
document.addEventListener("visibilitychange",()=>{if(!document.hidden) refreshToday();});
window.addEventListener("focus",refreshToday);
window.addEventListener("resize",()=>{updateNavHeight();if(lastRange && view==="gantt" && !byId("search").hidden) requestAnimationFrame(()=>centerToday(lastRange));if(lastPersonalRange && !byId("timeline").hidden) requestAnimationFrame(()=>centerToday(lastPersonalRange,"personal-gantt-grid"));});
byId("conference-planner").addEventListener("input",renderConferencePlan);
byId("conference-clear").addEventListener("click",()=>{byId("conference-name").value="";byId("conference-start").value="";byId("conference-notice").value="";byId("conference-buffer").value="14";renderConferencePlan();});
renderConferencePlan();
setInterval(refreshToday,60000);
activatePanel(location.hash.slice(1));render();
}());
