/* OpenGSA 互動線框：只處理檢視，不進行個人資格核定。 */
(function () {
"use strict";
const DAY = 86400000;
const labels = {
 category: {living_tuition:"生活／學費",living_emergency:"急難支持",phd_research:"博士研究",outcome_award:"成果獎",international_conference:"國際會議",overseas_research:"境外研究",indirect_support:"聘任入口"},
 source: {government:"政府",university:"學校",foundation:"基金會",enterprise:"企業／產學",research_institute:"研究法人／中研院",unknown:"來源待查"},
 degree: {master:"碩士",phd:"博士",candidate:"博士候選人"},
 year: {unlimited:"明示不限年級",range:"限定年級",freshman:"新生入學",graduating:"畢業／論文期",unknown:"年級待確認"},
 compatibility: {allowed:"可兼領（限已查範圍）",conditional:"兼領有條件",prohibited:"不可兼領",unknown:"兼領待確認"},
 hardship: {required:"清寒限定",not_exclusive:"非僅清寒",unknown:"清寒限定待確認"},
 application: {open:"受理中",upcoming:"尚未開放",closed:"本期已截止",unknown:"受理待確認"}
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
  rawState:start===null||end===null?"unknown":start>0?"not_yet_open":end<0?"closed":"open",
  application:start===null||end===null?"合成：待確認":start>0?"合成：尚未開放":end<0?"合成：已截止":"合成：受理中",evidence:"合成資料",url:null,
  note:"所有名稱、標籤與日期均為虛構；不代表任何實際方案。"
 }));
}
function windowState(item,today) {
 const steps=item.steps || [], end=steps.find(s=>s.actor==="student" && ["date","datetime"].includes(s.deadline?.kind))?.deadline;
 if(end?.value && end.value.slice(0,10)<today) return "closed";
 if(item.application?.as_of===today) return item.application.state;
 if(item.application?.state==="closed") return "closed";
 const start=item.start;
 if(start?.value && start.certainty!=="inferred" && start.certainty!=="tentative" && start.certainty!=="unknown") {
  if(start.value.slice(0,10)>today) return "not_yet_open";
  if(end?.value && end.kind==="date" && end.value>today) return "open";
 }
 return "unknown"; // An old open snapshot, inferred start or same-day time needs confirmation.
}
function makeDrafts(pilot,asOf=taipeiToday()) {
 const funding = {
  "ntu-tuition-115-1":"government","ntu-emergency-policy":"university",
  "ntu-nstc-phd-115":"government","ntu-moe-phd-115-round2":"government",
  "ntu-med-publication-115":"university","ntu-president-114":"university",
  "nstc-grad-conference-policy":"government","nstc-abroad-116-ntu":"government",
  "ntu-yuanxue-115-ordinary":"university","ntu-ta-policy":"university"
 };
 const sourceMap = new Map(pilot.sources.map(s=>[s.id,s]));
 return pilot.opportunities.map(item => {
  const student = item.steps.find(s=>s.actor==="student" && ["date","datetime"].includes(s.deadline?.kind));
  const milestones = item.steps.filter(s=>s.actor!=="student" && ["date","datetime"].includes(s.deadline?.kind)).map(s=>({
   label:{college:"學院送件",institution:"機關送件",university:"校級程序",unit:"單位程序"}[s.actor] || "其他程序",
   ...event(s.deadline.value,"confirmed",s.action+"；"+s.deadline.note)
  }));

  let resolvedSource = funding[item.id];
  if(!resolvedSource) {
   const funder = (item.organizations?.funder?.text || "").toLowerCase();
   const announcer = (item.organizations?.announcer?.text || "").toLowerCase();
   const title = (item.title || "").toLowerCase();
   const combined = funder; // Funding tags describe the funder, not the forwarding school.
   if (combined.includes("國科會") || combined.includes("教育部") || combined.includes("國家科學") || combined.includes("衛福部") || combined.includes("政府")) resolvedSource = "government";
   else if (combined.includes("大學") || combined.includes("臺大") || combined.includes("教務處") || combined.includes("研發處") || combined.includes("學院") || combined.includes("系所")) resolvedSource = "university";
   else if (combined.includes("基金會") || combined.includes("財團法人") || combined.includes("學會") || combined.includes("傑出人才")) resolvedSource = "foundation";
   else if (combined.includes("公司") || combined.includes("企業") || combined.includes("台積電") || combined.includes("聯發科")) resolvedSource = "enterprise";
   else if (combined.includes("研究院") || combined.includes("中研院") || combined.includes("國研院") || combined.includes("工研院")) resolvedSource = "research_institute";
   else resolvedSource = "unknown";
  }

  const startCertainty = item.start?.certainty || (["date","datetime"].includes(item.start?.kind) ? "confirmed" : "unknown");
  const structuredStart = (item.start && item.start.value) ? event(item.start.value, startCertainty, item.start.note || (startCertainty==="inferred"?"依官方公告發布日推定即日起受理":"官方受理申請起始日")) : event(null, "unknown", "目前無結構化申請起日；依內文敘述");
  const structuredResult = (item.result && item.result.value && ["date","datetime"].includes(item.result.kind)) ? event(item.result.value, item.result.certainty || "unknown", item.result.note || "結果公告日") : event(null, "unknown", "結果尚無結構證據");

  const sources = [...item.application.refs,...item.steps.flatMap(s=>s.refs)];
  const source = sources.map(r=>sourceMap.get(r.source)).find(Boolean);
   const state=windowState(item,asOf);
   return {
   id:item.id,title:item.title,category:item.category,source:resolvedSource,
   degrees:item.eligibility.degrees,year:item.eligibility.year_limit.mode,
   candidateMode:item.eligibility?.candidate?.mode || "unknown",
   compatibility:item.compatibility.mode,hardship:item.hardship.mode,
   cycle:item.cycle.label,synthetic:false,
   start:structuredStart,
   end:event(student?.deadline?.value||null,student?"confirmed":"unknown",student?.deadline?.note||"學生截止尚未確認"),
   result:structuredResult,
   milestones,
    application:({open:"受理中（依已記錄條件）",closed:"本期已截止",unknown:"受理待確認",not_yet_open:"尚未開放"})[state],
    rawState:state,
   evidence:item.evidence_status==="incomplete"?"資料不完整／草稿":"草稿待獨立覆核",
   url:source?.url||null,note:item.application.reason+"；所有資料皆待獨立覆核。"
  };
 });
}
function filterItems(items, filters) {
 const query = (filters.query||"").trim().toLocaleLowerCase();
 return items.filter(item=>{
  if(query && !(item.title+" "+item.id+" "+item.cycle).toLocaleLowerCase().includes(query)) return false;
  return ["category","source","degree","year","compatibility","hardship","application"].every(key=>{
   const wanted=filters[key];
   if(!wanted || wanted==="all") return true;
   if(key==="degree") {
    if(wanted==="candidate") return item.candidateMode==="required" || item.degrees?.includes("candidate");
    return Array.isArray(item.degrees) && item.degrees.includes(wanted);
   }
   if(key==="application") {
    if(wanted==="open") return item.rawState==="open";
    if(wanted==="upcoming") return item.rawState==="not_yet_open";
    if(wanted==="closed") return item.rawState==="closed";
    if(wanted==="unknown") return item.rawState==="unknown";
    return true;
   }
   const value=item[key];
   if(Array.isArray(value)) return value.includes(wanted);
   return value===wanted || (filters.includeUnknown && value==="unknown");
  });
 });
}
function noticeWindow(item) {
 if(item.personal || item.start.value || dayNumber(item.end.value)===null) return null;
 return {start:addDays(item.end.value.slice(0,10),-30),end:item.end.value};
}
function startLabel(item) {
 const suffix={inferred:"（推定）",tentative:"（暫定）",unknown:"（待確認）"}[item.start.certainty] || "";
 return item.start.value ? dateText(item.start.value)+suffix : "待確認"+(noticeWindow(item)?"（另有30天準備建議）":"");
}
function domain(items,today,mode="recent",offset=0) {
 const current=dayNumber(today);
 if(mode==="fit") {
  const values=items.flatMap(x=>[x.start.value,x.end.value,x.result.value,...x.milestones.map(m=>m.value),x.preparation?.start,noticeWindow(x)?.start]).map(dayNumber).filter(x=>x!==null);
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
function deadlineText(item){return (item.personal&&item.end.value?"試算／自填 ":"")+dateText(item.end.value);}
function conferencePlan(start,notice=null,buffer=14) {
 const validDate=value=>typeof value==="string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && dayNumber(value)!==null;
 if(!validDate(start) || (notice && !validDate(notice)) || !Number.isInteger(buffer) || buffer<0 || buffer>90) return null;
 const agencyBase=addDays(start.slice(0,7)+"-01",-1).slice(0,7)+"-01";
 const studentBase=addDays(agencyBase,-1), supplement=addDays(start,-28);
 return {agencyBase,studentBase,studentTime:"17:00",supplement,prepare:addDays(studentBase,-buffer),buffer,
  noticeRisk:!notice?"unknown":notice>supplement?"after_supplement":notice>studentBase?"after_submission":"before_submission",
  calendarStatus:"unverified",deadlineStatus:"estimate_pending_calendar"};
}
function monthsBefore(value,amount) {
 const date=new Date(value+"T00:00:00Z"), day=date.getUTCDate();
 date.setUTCDate(1);date.setUTCMonth(date.getUTCMonth()-amount);
 const last=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+1,0)).getUTCDate();
 date.setUTCDate(Math.min(day,last));return date.toISOString().slice(0,10);
}
function makeConferenceItem(input,program) {
 const base=conferencePlan(input.start,input.notice||null,input.buffer);
 const type=program?.rule?.type;
 if(!base || !["nstc_ntu","days_before","months_before","manual","fixed_window"].includes(type)) return null;
 if(type==="days_before" && (!Number.isInteger(program.rule.days)||program.rule.days<0)) return null;
 if(type==="months_before" && (!Number.isInteger(program.rule.months)||program.rule.months<1)) return null;
 if(input.manualDeadline && !/^\d{4}-\d{2}-\d{2}$/.test(input.manualDeadline)) return null;
 if(input.manualDeadline && dayNumber(input.manualDeadline)===null) return null;
 const name=(input.name||"").trim()||(type==="fixed_window"?"我的出國研究規劃":"我的研討會");
 const unit=(input.unit||"").trim(), title=type==="manual" && unit?unit:program.title;
 let student=null, agency=null;
 if(type==="nstc_ntu") { student=base.studentBase; agency=base.agencyBase; }
 else if(type==="days_before") { student=addDays(input.start,-program.rule.days); }
 else if(type==="months_before") { agency=monthsBefore(input.start,program.rule.months); }
 else if(type==="fixed_window") {
  const startYear=parseInt(input.start.slice(0,4),10);
  const appYear=startYear-1;
  const endMonth=String(program.rule.end_month||7).padStart(2,"0");
  const endDay=String(program.rule.end_day||31).padStart(2,"0");
  const schoolBuf=program.rule.school_buffer_days||3;
  agency=`${appYear}-${endMonth}-${endDay}`;
  student=addDays(agency,-schoolBuf);
 } else if(type==="manual") { student=input.manualDeadline||null; }
 const reference=student||agency, prepare=reference?addDays(reference,-input.buffer):null;
 const milestones=[{label:type==="fixed_window"?"赴外首日（自填）":"會議首日（自填）",...event(input.start,"estimated",type==="fixed_window"?"個人填寫預計赴外研究首日":"個人填寫會議日期")}];
 if(agency) milestones.push({label:type==="fixed_window"?"國科會受理截止（試算）":"機構彙送基準（試算）",...event(agency,"estimated",type==="fixed_window"?"每年 7/31 中午 12:00 國科會線上系統截止":"非已確認學生截止；例假日／校內日期待核")});
 if(type==="fixed_window") {
  const startMonth=String(program.rule.start_month||6).padStart(2,"0");
  const startDay=String(program.rule.start_day||1).padStart(2,"0");
  const appYear=parseInt(input.start.slice(0,4),10)-1;
  milestones.push({label:"國科會申請起日（試算）",...event(`${appYear}-${startMonth}-${startDay}`,"estimated","每年 6/1 開放線上申請")});
  milestones.push({label:"預計核定結果區間（試算）",...event(`${appYear}-10-31`,"estimated","預定 10 月底至 11 月初公告審查結果")});
 }
 if(type==="nstc_ntu") milestones.push({label:"接受函補送基準（試算）",...event(base.supplement,"estimated","四週前；不替代原申請")});
 if(input.notice) milestones.push({label:"預計接受通知（自填）",...event(input.notice,"estimated","個人預計，非官方公布結果")});
 if(prepare) milestones.push({label:type==="fixed_window"?"建議備件起日（試算）":"建議開始準備",...event(prepare,"estimated",type==="fixed_window"?"備妥指導教授推薦函、外語檢定與國外同意函":"個人緩衝，非官方申請起日")});
 const category=type==="fixed_window"?"overseas_research":"international_conference";
 return {id:"PERSONAL-"+encodeURIComponent(JSON.stringify([name,input.start,program.id,type==="manual"?unit:""])),
  title:name+"｜"+title+"（個人規劃）",conferenceName:name,program,category,source:program.source,
  degrees:type==="fixed_window"?["phd"]:["master","phd"],year:"unknown",compatibility:program.id==="faos-student"||type==="manual"?"unknown":"conditional",hardship:"unknown",
  cycle:"本次個人規劃 · 試算／自填待核",personal:true,synthetic:false,
  start:event(null,"unknown","未確認官方申請起日；準備建議不當作申請起日"),
  end:event(student,student?"estimated":"unknown",type==="nstc_ntu"?"未校正例假日的臺大17:00送出基準":type==="fixed_window"?"預估校內送件截止（國科會前 3 天）；當期各校公文待核":student?"試算／自填日期，尚待核對院系及當期公告":"機構期限不代替學生期限；校內收件待查"),
  result:event(type==="fixed_window"?`${parseInt(input.start.slice(0,4),10)-1}-10-31`:null,type==="fixed_window"?"expected":"unknown",type==="fixed_window"?"每年預計 10 月底公布審查結果":"沒有官方結果日；接受通知不是補助結果"),milestones,
  preparation:prepare?{start:prepare,end:reference}:null,
  application:"個人規劃／受理待確認",evidence:"來源初查，待獨立覆核；個人輸入未核",url:program.refs[0]?.url||null,
  note:"此列是個人試算，非已確認資格或正式截止。"+program.scope+" "+program.requirements+" "+program.compatibility,
  noticeRisk:type==="nstc_ntu"?base.noticeRisk:!input.notice||!reference?"unknown":input.notice>reference?"after_deadline":"before_submission"};
}
function conferenceEntries(programs){
 return programs.filter(p=>!["nstc-ntu","custom-unit"].includes(p.id)).map(program=>({
  id:"PROGRAM-"+program.id,title:program.title,program,
  category:program.rule.type==="fixed_window"?"overseas_research":"international_conference",
  source:program.source,
  degrees:program.rule.type==="fixed_window"?["phd"]:["master","phd"],
  year:"unknown",
  compatibility:program.id==="ntu-med-oia"||program.rule.type==="fixed_window"?"conditional":"unknown",
  hardship:"unknown",
  cycle:"制度入口 · 當期受理待查",synthetic:false,
  start:event(),end:event(),result:event(),milestones:[],application:"事件相對期限／受理待確認",evidence:"來源初查，待獨立覆核",
  url:program.refs[0]?.url||null,note:program.scope+" "+program.requirements+" "+program.compatibility
 }));
}
const personaPresets={
 phd_research:{category:"phd_research",source:"all",degree:"phd",year:"all",compatibility:"all",hardship:"all"},
 living_support:{category:"living_tuition",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 abroad_conf:{category:"international_conference",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 overseas_study:{category:"overseas_research",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 outcome_award:{category:"outcome_award",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 ta_assistant:{category:"indirect_support",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"}
};
function activePersona(currentState){
 if(!currentState) return null;
 for(const [id,preset] of Object.entries(personaPresets)){
  if(Object.entries(preset).every(([k,v])=>currentState[k]===v)) return id;
 }
 return null;
}
function applyPersona(currentState,personaId){
 const preset=personaPresets[personaId];
 if(!preset) return {...currentState};
 if(activePersona(currentState)===personaId){
  return {...currentState,category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"};
 }
 return {...currentState,...preset};
}
function evaluateSubordination(checks={}){
 const keys=["schedule","consideration","supervision","unrelated_admin"];
 const matched=keys.filter(k=>Boolean(checks[k]));
 const score=matched.length;
 const disclaimer="僅供依公開原則整理爭點，不構成正式法律裁決。";
 if(score===0) return {score:0,level:"none",recommendedTiers:[],disclaimer,summary:"尚未勾選項目。勾選上方任一實際情況後，將顯示對應的法規判準與救濟建議。"};
 if(score===1) return {score:1,level:"review_needed",recommendedTiers:["TIER 01","TIER 02"],disclaimer,summary:"已勾選 1 項指標：具部分從屬或學習分流爭點。建議核對勞動部指導原則第 2～4 點及書面協議，確認工時與給付是否相符（2026 最低時薪 196 元）；必要時洽 TIER 01 系院或 TIER 02 校級窗口釐清。"+disclaimer};
 return {score,level:"high_subordination",recommendedTiers:["TIER 02","TIER 04","TIER 05"],disclaimer,summary:"已勾選 "+score+" 項指標：高度呈現人格、經濟或組織從屬性（常見「假學習真勞動」爭點）。依勞動部指導原則實質認定原則，若受指揮監督並提供勞務獲取對價，不能只按給付名稱排除適用保障；勞基法、2026最低工資與退休金須分別依關係、身分及進用依據確認。建議參考下方 TIER 02 校內申訴、TIER 04（地方主管機關勞檢／勞工局調解）或 TIER 05 高教工會。"+disclaimer};
}
const api={dayNumber,iso,taipeiToday,addDays,makeDemo,makeDrafts,windowState,filterItems,workspaceItems,domain,position,centerScroll,geometry,noticeWindow,conferencePlan,monthsBefore,makeConferenceItem,conferenceEntries,personaPresets,activePersona,applyPersona,evaluateSubordination};
if(typeof module!=="undefined" && module.exports) module.exports=api;
if(typeof document==="undefined") return;

const byId=id=>document.getElementById(id);
const pilot=JSON.parse(byId("pilot-data").textContent);
const conferenceData=JSON.parse(byId("conference-data").textContent);
const personalConferences=new Map();
function currentItems(){return [...(mode==="demo"?makeDemo(today):drafts),...personalConferences.values()];}
const drafts=[...makeDrafts(pilot),...conferenceEntries(conferenceData.programs)];
const rawById=new Map(pilot.opportunities.map(item=>[item.id,item]));
const sourceById=new Map(pilot.sources.map(source=>[source.id,source]));
const picked={demo:new Set(),draft:new Set()}, completed={demo:new Set(),draft:new Set()}, activeDetail={demo:null,draft:null};
let sharedItems=[], personalRangeMode="recent", lastPersonalRange=null;
let today=taipeiToday(), mode="demo", view="gantt", rangeMode="recent", offset=0, inspectedId=null, lastRange=null, centerPending=true, rightsView="all", activePanelId="search";
const scrollPositions={search:0,detail:0,timeline:0,rights:0};
const state={query:"",category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all",application:"all",includeUnknown:true};
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
 const program=conferenceData.programs.find(x=>x.id===byId("conference-program").value);
 const manual=program?.rule.type==="manual";
 byId("conference-manual").hidden=!manual;
 byId("conference-program-info").replaceChildren();
 const info=byId("conference-program-info");
 if(program) {
  info.append(el("p","small",program.scope),el("p","small",program.requirements),el("p","small","兼領："+program.compatibility));
  for(const ref of program.refs){const link=el("a","small",ref.title+" ↗");link.href=ref.url;info.append(link,el("span","","　"));}
 }
 byId("conference-add").disabled=true;
 if(!start) {output.append(el("p","small","填入會議首日後試算，再按「加入／更新甘特圖」。"));return;}
 const buffer=byId("conference-buffer").value;
 const item=makeConferenceItem({name:byId("conference-name").value,start,notice,buffer:buffer===""?NaN:Number(buffer),unit:byId("conference-unit").value,manualDeadline:manual?byId("conference-deadline").value:null},program);
 if(!item) {output.append(el("p","small","請確認日期，準備緩衝需為0至90的整數天數。"));return;}
 byId("conference-add").disabled=false;
 output.append(el("h4","",item.title),el("p","tiny quiet","條文基準試算 · 例假日、月底換算與院系所更早期限待核，以下不是已確認的正式截止。"));
 const facts=el("dl","facts");
 facts.append(el("dt","","學生送件基準"),el("dd","",dateText(item.end.value)+(program.id==="nstc-ntu"?" 17:00（未校正例假日）":"（試算／自填待核）")));
 for(const point of item.milestones) facts.append(el("dt","",point.label),el("dd","",dateText(point.value)));
 output.append(facts);
 const messages={unknown:"接受通知或學生期限尚未確認，請先核對此方案的必要文件及收件程序。",after_supplement:"接受通知日可能晚於國科會接受函補送規定，請提早洽承辦確認。",after_submission:"接受通知日在申請基準後；國科會允許註明補送，仍須遵守補送程序與日期。",after_deadline:"接受通知日可能晚於本方案送件基準；此方案未查得接受函可補送條款，請洽承辦確認，勿套用國科會補送規則。",before_submission:"通知未晚於試算基準，仍須核對資格、文件、院系期限與當期公告，不能據此保證來得及申請。"};
 output.append(el("p","callout",messages[item.noticeRisk]));
 if(start<=today) output.append(el("p","small","會議已開始或首日已過，以上僅作回顧試算。"));
 else if(item.end.value && item.end.value<today) output.append(el("p","small","學生送件試算基準已過，請核對實際公告，不把估算當成已確認逾期。"));
 return item;
}
function renderConferenceList(){
 const list=byId("conference-saved");list.replaceChildren();
 for(const item of personalConferences.values()){
  const row=el("div","source-note"), remove=el("button","secondary","移除");remove.type="button";remove.setAttribute("aria-label","移除 "+item.title);
  remove.addEventListener("click",()=>{personalConferences.delete(item.id);for(const key of ["demo","draft"]){picked[key].delete(item.id);for(const task of completed[key]) if(task.startsWith(item.id+":")) completed[key].delete(task);}renderConferenceList();render();byId("conference-status").textContent="已移除這筆個人規劃。";});
  row.append(el("p","small",item.title),remove);list.append(row);
 }
}
function selectedButtons(container,attribute,value) {
 document.querySelectorAll(container+" button").forEach(button=>{
  const active=button.dataset[attribute]===value;
  button.setAttribute("aria-pressed",String(active));
 });
}
function activatePanel(id, focus=false) {
 if(!["search","detail","timeline","rights"].includes(id)) id="search";
 if(activePanelId && byId(activePanelId) && !byId(activePanelId).hidden) scrollPositions[activePanelId]=window.scrollY;
 document.querySelectorAll('[role="tab"]').forEach(tab=>{
  const active=tab.dataset.panel===id;
  tab.setAttribute("aria-selected",String(active));
  tab.tabIndex=active?0:-1;
  if(active && focus) tab.focus();
 });
 document.querySelectorAll("main > .screen").forEach(panel=>{panel.hidden=panel.id!==id;});
 if(location.hash!=="#"+id) history.replaceState(null,"","#"+id);
 activePanelId=id;
 window.scrollTo(0,scrollPositions[id]||0);
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
function scrollToInternalTarget(targetId) {
 const target=byId(targetId);
 if(!target) return false;
 const parentScreen=target.closest("main > .screen");
 if(parentScreen && parentScreen.id) {
  activatePanel(parentScreen.id);
 }
 if(parentScreen && parentScreen.id==="rights") {
  if(byId("rights-standards-group") && byId("rights-standards-group").contains(target)) {
   if(rightsView==="grievance") setRightsView("all");
  } else if(byId("rights-grievance-group") && byId("rights-grievance-group").contains(target)) {
   if(rightsView==="standards") setRightsView("all");
  }
 }
 target.scrollIntoView({behavior:"smooth",block:"start"});
 if(target.tabIndex<0) target.tabIndex=-1;
 target.focus({preventScroll:true});
 return true;
}
document.addEventListener("click",event=>{
 const link=event.target.closest('a[href^="#"]');
 if(link) {
  const href=link.getAttribute("href");
  if(href && href!=="#") {
   const targetId=href.slice(1);
   if(["search","detail","timeline","rights"].includes(targetId)) {
    event.preventDefault();activatePanel(targetId);
   } else if(byId(targetId)) {
    event.preventDefault();scrollToInternalTarget(targetId);
   }
  }
 }
});
window.addEventListener("hashchange",()=>{
 const id=location.hash.slice(1);
 if(["search","detail","timeline","rights"].includes(id)) {
  activatePanel(id);
 } else if(byId(id)) {
  scrollToInternalTarget(id);
 }
});
function itemTags(item) {
 const tags = [labels.source[item.source]||item.source, item.degrees.map(x=>labels.degree[x]||x).join("／"), labels.year[item.year]||item.year, labels.compatibility[item.compatibility]||item.compatibility, labels.hardship[item.hardship]||item.hardship];
 if(item.candidateMode==="required") tags.push("須博士候選人");
 return tags;
}
function inspect(item) {
 inspectedId=item.id;
 const box=byId("schedule-inspect");box.replaceChildren();
 box.append(el("strong","",item.title));
  const startDesc = item.start.certainty === "inferred"
   ? "推定開始：" + dateText(item.start.value) + "（" + (item.start.note || "依官方公告發布日推定") + "）"
   : (item.start.value ? "申請開始：" + dateText(item.start.value) : (item.end.value && !item.personal ? "申請開始：待確認（甘特圖已標示截止前 30 天準備提醒帶）" : "申請開始：待確認"));
  box.append(el("p","small",startDesc+"\u3000→\u3000學生截止："+deadlineText(item)+"\u3000→\u3000"+(item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value)));
 item.milestones.forEach(m=>box.append(el("p","small",m.label+"："+dateText(m.value))));
 box.append(el("p","tiny quiet",item.synthetic?"合成排程，全部為虛構日期。":item.note));
 if(item.url) {const link=el("a","small","核對官方來源 ↗");link.href=item.url;box.append(link);}
 const more=el("button","secondary",picked[mode].has(item.id)?"查看詳情":"勾選並看詳情");more.type="button";more.dataset.openDetail=item.id;
 more.addEventListener("click",()=>chooseAndOpen(item));box.append(more);
 const wasHidden=box.hidden;
 box.hidden=false;
 if(wasHidden && typeof box.getBoundingClientRect==="function"){
  const rect=box.getBoundingClientRect();
  if(rect.top>window.innerHeight || rect.bottom<0) box.scrollIntoView({behavior:"smooth",block:"nearest"});
 }
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
  card.append(el("p","small","申請開始 "+startLabel(item)+" → 學生截止 "+deadlineText(item)+" → "+(item.result.certainty==="expected"?"預定":"")+"結果 "+dateText(item.result.value)));
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
  const labelDateDesc = item.personal ? "學生期限："+deadlineText(item) : (item.start.certainty==="inferred"?"推定起訖：":"")+dateText(item.start.value)+" → "+dateText(item.end.value);
  label.append(el("div","tiny quiet",labelDateDesc));
  row.append(label);
  const plot=el("div","gantt-plot");todayLine(plot,range);
  if(item.preparation){
   const prep=geometry({start:event(item.preparation.start),end:event(item.preparation.end),result:event(),milestones:[]},range).bar;
   if(prep){const bar=el("button","gantt-bar preparation");bar.type="button";bar.style.left=prep.left+"%";bar.style.width=prep.width+"%";bar.title="個人準備建議（非官方申請期）："+dateText(item.preparation.start)+" 至 "+dateText(item.preparation.end);bar.setAttribute("aria-label",item.title+"："+bar.title);bar.addEventListener("click",()=>onInspect(item));plot.append(bar);}
  }
  let prepNoticeGeom=null;
  if(noticeWindow(item)){
   const prepNoticeStart=noticeWindow(item).start;
   prepNoticeGeom=geometry({start:event(prepNoticeStart),end:event(item.end.value.slice(0,10)),result:event(),milestones:[]},range).bar;
   if(prepNoticeGeom){
    const bar=el("button","gantt-bar notice-window");
    bar.type="button";bar.style.left=prepNoticeGeom.left+"%";bar.style.width=prepNoticeGeom.width+"%";
    bar.title="準備提醒期（官方起日尚未確認）："+dateText(prepNoticeStart)+" 至 "+dateText(item.end.value)+"（截止前 30 天準備提醒帶，非官方受理開放日）";
    bar.setAttribute("aria-label",item.title+"："+bar.title);bar.addEventListener("click",()=>onInspect(item));plot.append(bar);
   }
  }
  if(g.wait) {const wait=el("span","gantt-wait");wait.style.left=g.wait.left+"%";wait.style.width=g.wait.width+"%";wait.setAttribute("aria-hidden","true");plot.append(wait);}
  if(g.bar) {
   const isInferred=item.start.certainty==="inferred";
   const bar=el("button","gantt-bar"+(isInferred?" inferred":""));
   bar.type="button";bar.style.left=g.bar.left+"%";bar.style.width=g.bar.width+"%";
   bar.title=(isInferred?"推定受理期（依官方公告日推定）：":"申請期間：")+dateText(item.start.value)+" 至 "+dateText(item.end.value)+(isInferred?"（"+(item.start.note||"依官方公告發布日推定即日起受理")+"）":"");
   bar.setAttribute("aria-label",item.title+"，"+bar.title);bar.addEventListener("click",()=>onInspect(item));plot.append(bar);
  }
  const isStartInferred=item.start.certainty==="inferred";
  marker(plot,g.start,"start"+(isStartInferred?" inferred":""),(isStartInferred?"推定申請開始（依官方公告日）：":"申請開始：")+dateText(item.start.value)+(isStartInferred?"（"+(item.start.note||"")+"）":""),item,onInspect);
  marker(plot,g.end,"end"+(item.personal?" estimated":""),"學生截止："+deadlineText(item),item,onInspect);
  marker(plot,g.result,"result "+(item.result.certainty==="expected"?"expected":""),(item.result.certainty==="expected"?"預定":"")+"結果公布："+dateText(item.result.value),item,onInspect);
  item.milestones.forEach(m=>{const p=position(m.value,range);if(p!==null&&p>=0&&p<100) marker(plot,p,"milestone"+(item.personal?" estimated":""),m.label+"："+dateText(m.value),item,onInspect);});
  const notes=[];
  if(item.personal) notes.push("個人規劃：虛線為準備建議，空心節點待核");
  if(noticeWindow(item)) notes.push(prepNoticeGeom?"官方起日待確認（已標示截止前30天準備建議）":"準備建議在視窗外；官方起日待確認");
  else if(!item.start.value && !item.personal) notes.push("起日待確認");
  if(item.start.certainty === "inferred") notes.push("起日依官方公告推定");
  if(!item.end.value) notes.push("學生截止待確認");
  if(!item.result.value) notes.push("結果日未確認");
  if(g.invalid) notes.push("起訖衝突，暫不畫期間");
  const hasKnown=[item.start.value,item.end.value,item.result.value,...item.milestones.map(m=>m.value)].some(Boolean);
  if(hasKnown && !g.bar && !prepNoticeGeom && g.start===null && g.end===null && g.result===null && !item.milestones.some(m=>{const p=position(m.value,range);return p!==null&&p>=0&&p<100;})) notes.push("已知日期在視窗外");
  plot.append(el("div","gantt-notes",notes.join(" · ")));
  row.append(plot);grid.append(row);
 });
}
function drawTable(items) {
 const body=byId("date-rows");body.replaceChildren();
 items.forEach(item=>{
  const startLabel=dateText(item.start.value)+(item.start.certainty==="inferred"?" (推定)":"")+(!item.start.value&&item.end.value&&!item.personal?" (標示截止前30天準備帶)":"");
  const row=el("tr");[item.title,startLabel,deadlineText(item),(item.result.certainty==="expected"?"預定 ":"")+dateText(item.result.value),item.milestones.map(m=>m.label+" "+dateText(m.value)).join("；")||"—"].forEach(text=>row.append(el("td","",text)));body.append(row);
 });
}
function centerToday(range,gridId="gantt-grid",value=today) {
 const grid=byId(gridId), scroll=grid.closest(".gantt-scroll");
 const percent=position(value,range);
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
  const startDetailText="申請開始："+dateText(item.start.value)+(item.start.certainty==="inferred"?"（依官方公告日推定）":"")+(!item.start.value&&item.end.value&&!item.personal?"（官方起日待確認，甘特圖提供截止前 30 天準備提醒帶）":"")+"；"+item.start.note;
  const timing=factSection("申請與結果時程",[
   startDetailText,
   "學生截止："+deadlineText(item)+"；"+item.end.note,
   (item.result.certainty==="expected"?"預定":"")+"結果："+dateText(item.result.value)+"；"+item.result.note
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
  if(item.category==="indirect_support" || item.title.includes("助教") || item.title.includes("助理")) {
   const rightsCard=el("section","panel detail-section");
   rightsCard.append(el("h3","","⚖️ 法源位階與勞動權益參照"));
   rightsCard.append(el("p","small","本項兼任或助理職務受勞動基準法、教育部指導原則及校內兼任上限規範。具指揮監督與勞務對價者，學校不得僅以獎助生名義排除雇主責任。"));
   const linksDiv=el("div","range-buttons");
   const linkMap=el("a","pill","三層法源位階地圖 ↗");linkMap.href="#legal-hierarchy-map";
   const linkSal=el("a","pill","助教與兼任薪資總表 ↗");linkSal.href="#ta-salary-title";
   const linkGriev=el("a","pill","從屬性自測與救濟地圖 ↗");linkGriev.href="#grievance-title";
   linksDiv.append(linkMap,linkSal,linkGriev);rightsCard.append(linksDiv);left.append(rightsCard);
  } else if(item.source==="government" || item.title.includes("國科會") || item.title.includes("千里馬")) {
   const rightsCard=el("section","panel detail-section");
   rightsCard.append(el("h3","","📜 國科會作業要點上位法參照"));
   rightsCard.append(el("p","small","本項依國家科學及技術委員會相關作業要點規範。依上位法優於下位法原則，各校校內送件與給付基準不得牴觸中央主管機關辦法。"));
   const linksDiv=el("div","range-buttons");
   const linkNstc=el("a","pill","國科會要點與法源位階 ↗");linkNstc.href="#nstc-rights-title";
   const linkMap=el("a","pill","三層法源位階地圖 ↗");linkMap.href="#legal-hierarchy-map";
   linksDiv.append(linkNstc,linkMap);rightsCard.append(linksDiv);left.append(rightsCard);
  }
 } else if(item.program) {
  if(item.program.id==="nstc-abroad-dragon") {
   const rightsCard=el("section","panel detail-section");
   rightsCard.append(el("h3","","📜 國科會千里馬要點法源參照"));
   rightsCard.append(el("p","small","依國科會補助博士生赴國外研究作業要點（FL039188），每年 6/1 至 7/31 受理，各校校內申請基準得提前截止。"));
   const linksDiv=el("div","range-buttons");
   const linkNstc=el("a","pill","國科會要點與法源位階 ↗");linkNstc.href="#nstc-rights-title";
   linksDiv.append(linkNstc);rightsCard.append(linksDiv);left.append(rightsCard);
  }
  left.append(factSection(item.personal?"個人規劃與申請限制":"方案條件與待確認",[item.program.scope,item.program.requirements,"兼領："+item.program.compatibility]));
  if(item.milestones.length) left.append(factSection("會議、準備與程序節點",item.milestones.map(point=>point.label+"："+dateText(point.value))));
  const plan=el("button","secondary","用此方案規劃研討會");plan.type="button";
  plan.addEventListener("click",()=>{byId("conference-program").value=item.program.id;byId("conference-planner").open=true;renderConferencePlan();activatePanel("search");byId("conference-start").focus();});left.append(plan);
  const evidence=factSection("來源初查與版本",["查核日："+conferenceData.checked_on+"；待獨立覆核。",item.program.version]);
  for(const ref of item.program.refs){const link=el("a","",ref.title+" ↗");link.href=ref.url;evidence.append(link,el("p","small",ref.locator));}right.append(evidence);
 } else {
  left.append(factSection("合成資料的使用範圍",["這個方案與所有日期、標籤都是虛構，沒有正式資格辦法或金額。","切換第一頁的「來源草稿＋會議方案」，可查看對應真實方案的條件、程序與公開依據。"]));
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
  card.append(el("p","small","學生截止："+deadlineText(item)+"　／　"+(item.result.certainty==="expected"?"預定":"")+"結果："+dateText(item.result.value)));
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
 const items=currentItems(),filtered=filterItems(items,state),selected=picked[mode];
 sharedItems=workspaceItems(items,filtered,selected);
 const hiddenCount=sharedItems.filter(item=>!filtered.some(found=>found.id===item.id)).length;
 const basis=selected.size?"第一頁已勾選的 "+sharedItems.length+" 項":"第一頁目前篩選的 "+sharedItems.length+" 項（尚未勾選）";
 const text=(mode==="demo"?"合成資料":"來源草稿")+(personalConferences.size?"＋本次個人規劃":"")+" · "+basis+(hiddenCount?"；其中 "+hiddenCount+" 項不在目前篩選結果":"");
 for(const id of ["detail-context","timeline-context"]){byId(id).textContent=text;byId(id).classList.toggle("synthetic-note",mode==="demo");}
 byId("selection-count").textContent="已勾選 "+selected.size+" 項；第二、三頁使用 "+sharedItems.length+" 項"+(selected.size?"已選內容":"篩選結果");
 byId("select-filtered").disabled=!filtered.length;byId("clear-selection").disabled=!selected.size;
 document.querySelectorAll("[data-pick-id]").forEach(input=>{input.checked=selected.has(input.dataset.pickId);});
 document.querySelectorAll("[data-open-detail]").forEach(button=>{button.textContent=selected.has(button.dataset.openDetail)?"查看詳情":"勾選並看詳情";});
 for(const name of ["detail","timeline"]){byId(name+"-empty").hidden=!!sharedItems.length;byId(name+"-workspace").hidden=!sharedItems.length;}
 drawDetail();drawPlan();
}
function render() {
 const items=currentItems();
 const found=filterItems(items,state), range=domain(found,today,rangeMode,offset);
 if(lastRange && rangeMode==="fit" && (lastRange.start!==range.start || lastRange.end!==range.end)) centerPending=true;
 lastRange=range;
 byId("result-count").textContent="顯示 "+found.length+" / "+items.length+" 項";
 byId("mode-note").textContent=mode==="demo"
  ? "合成示範模式：日期與標籤僅供介面體驗，非正式公告。"
  : "收錄臺大與全國代表性獎助草稿及會議補助制度；申請前請以主辦單位當期公告為準。";
 byId("mode-note").classList.toggle("synthetic-note",mode==="demo");
 if(personalConferences.size) byId("mode-note").textContent+=" 另含本次研討會規劃"+personalConferences.size+"項，為自填／試算待核，非合成方案。";
 byId("chart-range").textContent=iso(range.start).replaceAll("-","/")+" — "+iso(range.end).replaceAll("-","/")+" · 臺北時間";
 byId("today-label").textContent="今天 "+today.replaceAll("-","/");
 byId("outside-today").hidden=!(dayNumber(today)<range.start || dayNumber(today)>range.end);
 byId("empty-results").hidden=found.length>0;
 byId("gantt-view").hidden=view!=="gantt" || !found.length;
 byId("list-view").hidden=view!=="list" || !found.length;
 byId("dates-table").hidden=!found.length;
 selectedButtons("#mode-switch","mode",mode);selectedButtons("#view-switch","view",view);
 selectedButtons("#persona-bar","persona",activePersona(state));
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
 Object.assign(state,{query:"",category:"all",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all",application:"all",includeUnknown:true});
 document.querySelectorAll("[data-filter]").forEach(input=>{if(input.type==="checkbox") input.checked=true;else input.value=state[input.dataset.filter];});
 render();
}
byId("reset-filters").addEventListener("click",resetFilters);
byId("empty-reset").addEventListener("click",resetFilters);
byId("select-filtered").addEventListener("click",()=>{filterItems(currentItems(),state).forEach(item=>picked[mode].add(item.id));renderWorkspace();});
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
for(const program of conferenceData.programs){const option=el("option","",program.title);option.value=program.id;byId("conference-program").append(option);}
for(const ref of conferenceData.reference_sources){const row=el("p","small"),link=el("a","",ref.title+" ↗");link.href=ref.url;row.append(link,el("span","","："+ref.note));byId("conference-references").append(row);}
byId("conference-planner").addEventListener("input",()=>{byId("conference-status").textContent="";renderConferencePlan();});
byId("conference-program").addEventListener("change",renderConferencePlan);
byId("conference-add").addEventListener("click",()=>{
 const item=renderConferencePlan();if(!item) return;
 const existed=personalConferences.has(item.id);personalConferences.set(item.id,item);
 for(const key of ["demo","draft"]) picked[key].add(item.id);
 rangeMode="fit";personalRangeMode="fit";offset=0;view="gantt";centerPending=true;
 byId("range-mode").value="fit";byId("personal-range-mode").value="fit";
 renderConferenceList();render();
 requestAnimationFrame(()=>centerToday(lastRange,"gantt-grid",item.end.value||item.milestones[0].value));
 byId("conference-status").textContent=(existed?"已更新":"已加入")+"甘特圖與我的時間軸。"+(!filterItems([item],state).length?"目前篩選隱藏此項，可按「清除篩選並查看甘特圖」。":"時間範圍已調整為涵蓋所有日期。")+" 本次瀏覽有效，重整即清除。";
});
byId("conference-show").addEventListener("click",()=>{view="gantt";resetFilters();byId("gantt-view").scrollIntoView({block:"start"});});
byId("conference-clear").addEventListener("click",()=>{for(const id of ["conference-name","conference-start","conference-notice","conference-unit","conference-deadline"]) byId(id).value="";byId("conference-buffer").value="14";byId("conference-status").textContent="已清空輸入，已加入的規劃保留，可逐筆移除。";renderConferencePlan();});
renderConferencePlan();
setInterval(refreshToday,60000);
if(byId("persona-bar")){
 byId("persona-bar").addEventListener("click",event=>{
  const button=event.target.closest("[data-persona]");
  if(!button) return;
  Object.assign(state,applyPersona(state,button.dataset.persona));
  document.querySelectorAll("[data-filter]").forEach(input=>{if(input.type==="checkbox") input.checked=state[input.dataset.filter];else input.value=state[input.dataset.filter];});
  centerPending=true;render();
 });
}
function setRightsView(nextView){
 if(!["all","standards","grievance"].includes(nextView)) nextView="all";
 rightsView=nextView;
 selectedButtons("#rights-view-switch","rightsView",rightsView);
 if(byId("rights-standards-group")) byId("rights-standards-group").hidden=(rightsView==="grievance");
 if(byId("rights-grievance-group")) byId("rights-grievance-group").hidden=(rightsView==="standards");
}
if(byId("rights-view-switch")){
 byId("rights-view-switch").addEventListener("click",event=>{
  const button=event.target.closest("[data-rights-view]");
  if(button) setRightsView(button.dataset.rightsView);
 });
}
if(byId("jump-to-grievance")){
 byId("jump-to-grievance").addEventListener("click",()=>{
  setRightsView("grievance");
  if(byId("subordination-wizard")) byId("subordination-wizard").scrollIntoView({behavior:"smooth",block:"start"});
 });
}
function updateSubordinationWizard(){
 const checks={};
 document.querySelectorAll("[data-subordination-check]").forEach(input=>{checks[input.dataset.subordinationCheck]=input.checked;});
 const res=evaluateSubordination(checks);
 if(byId("subordination-result")) byId("subordination-result").textContent=res.summary;
}
document.querySelectorAll("[data-subordination-check]").forEach(input=>input.addEventListener("change",updateSubordinationWizard));
if(byId("subordination-reset")){
 byId("subordination-reset").addEventListener("click",()=>{
  document.querySelectorAll("[data-subordination-check]").forEach(input=>{input.checked=false;});
  updateSubordinationWizard();
 });
}
activatePanel(location.hash.slice(1));render();
}());
