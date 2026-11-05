/* OpenGSA 互動線框：只處理檢視，不進行個人資格核定。 */
(function () {
"use strict";
const DAY = 86400000;
const labels = {
 category: {all_abroad:"出國與境外總覽",all_k12:"各級教育弱勢扶助",living_tuition:"生活／學費",living_emergency:"急難支持",phd_research:"博士研究",outcome_award:"成果獎",international_conference:"國際會議",overseas_research:"境外研究",indirect_support:"聘任入口",research_tools:"研究工具／算力"},
 source: {government:"政府",university:"學校",foundation:"基金會／學會",enterprise:"企業／產學",research_institute:"研究法人／中研院",unknown:"來源待查"},
 degree: {all:"全部學歷與身分",master_phd:"碩士與博士",master:"碩士",phd:"博士",candidate:"博士候選人",undergraduate:"大學部／大專",senior_high:"高中職／五專",basic_k12:"國中小／幼兒"},
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
 if(item.resource_kind==="tool_subscription") {const cap=item.steps?.filter(s=>s.actor==="student").map(s=>s.deadline?.value).filter(Boolean).sort()[0];return cap&&cap.slice(0,10)<today?"closed":"unknown";}
 if(["application_start","student_deadline"].every(k=>item.field_applicability?.[k]?.status==="not_applicable")) return "not_applicable";
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
const UNKNOWN_LABEL="不明，請見來源";
const timingLabels={fixed_window:"固定申請期",deadline_only:"截止已公告",start_only:"起日已公告",event_relative:"依活動日期計算",recurring:"常態月日規則",rule_text:"時間規則已載（計算方式待整理）",mixed:"多階段時間規則",procedure_only:"僅有行政程序",conditional_deadline:"年度上限＋個人條件",automatic:"免另行申請",reference:"制度參考",undetermined:"時間資訊待補",historical:"往年／月份參考"};
Object.assign(timingLabels,{continuous:"常態受理（資格與額度另核）",unit_announced:"依所屬單位公告",review_only:"已載審查方式；受理期間另查"});
timingLabels.procedure_only="已知單位／行政時點";
const timingActors={student:"學生",department:"系所",unit:"單位",college:"學院",university:"校級",institution:"機構",supplement:"補件",other:"其他程序"};
const timingGaps={source_checks_failed:"來源檢核未通過，需重新核對",time_not_projected:"目前快照未有可投影的申請時程",student_window_not_recorded:"學生／所屬單位收件時間另查",needs_event_date:"有規則，需活動日期才能換算",calendar_unverified:"假日順延與所屬單位期限仍需確認",personal_conditions_required:"年度最晚日仍受個人條件期限限制"};
Object.assign(timingGaps,{multiple_cycles_need_split:"來源含不同年度時點，先分年核對；不合成申請區間",needs_linked_document:"申請時程需續查附件／配合單位公告",unparsed_timing_clause:"來源有時間文字，日期或申請角色仍需核對",time_rule_not_verified:"尚未取得可確認的受理時間規則"});
Object.assign(timingGaps,{replay_deferred:"本次重查未完成，保留先前快照供查找",source_access_restricted:"本次自動讀取受限，需人工確認來源"});
function timePresentation(item){
 const policy=item.timePolicy, rules=item.conflict?[]:policy?.rules||[];
 let mode=item.conflict?"undetermined":policy?.submission_mode||"undetermined";
 if(!item.conflict&&mode!=="conditional_deadline"){
  if(item.start.value&&item.end.value)mode="fixed_window";
  else if(item.timeline?.baselines?.length&&!item.start.value&&!item.end.value)mode="historical";
  else if(mode==="undetermined"&&item.end.value)mode="deadline_only";
  else if(mode==="undetermined"&&item.start.value)mode="start_only";
  else if(mode==="undetermined"&&item.milestones?.length)mode="procedure_only";
 }
 const known=mode!=="undetermined"||rules.length>0;
 return {mode,label:timingLabels[mode]||timingLabels.undetermined,known,rules,
  icon:({event_relative:"⚓",recurring:"↻",procedure_only:"◇",historical:"◌",automatic:"✓",reference:"▤",conditional_deadline:"◷",continuous:"↺",unit_announced:"⌂",review_only:"≋"})[mode]||(known?"▣":"⚠"),
  gaps:item.conflict?[timingGaps.source_checks_failed]:(policy?.gaps||[]).map(g=>timingGaps[g])};
}
function unknownValue(value){
 return !value||value===UNKNOWN_LABEL||/^(?:待確認|待核|待查|未載明|未確認|尚無|尚未辨識|unknown|身分條件請至來源定位核對)$/.test(value.trim());
}
function officialUrl(value){
 try{const url=new URL(value);return url.protocol==="https:"&&!url.username&&!url.password?url.href:null;}catch{return null;}
}
function issueUrl(item){
 const url=new URL("https://github.com/matt-ye/opengsa/issues/new");
 if(item.personal||item.synthetic){url.searchParams.set("template","preview-feedback.yml");return url.href;}
 url.searchParams.set("template","data-problem.yml");
 const fields={title:"[資料問題] "+item.title,resource_name:item.title,resource_id:item.id,
  source_url:officialUrl(item.url)||"",source_version:item.sourceVersion||item.sourceChecked||item.cycle||""};
 const limits={title:120,resource_name:120,resource_id:200,source_version:160};
 for(const [key,value] of Object.entries(fields)){
  if(key==="source_url"){if(value.length<=2000)url.searchParams.set(key,value);}
  else url.searchParams.set(key,String(value||"").slice(0,limits[key]));
 }
 if(url.href.length>7500)url.searchParams.delete("source_url");
 return url.href;
}
function itemMatchesQuery(item, query) {
 if(!query) return true;
 const q = query.trim().toLocaleLowerCase();
 if(!q) return true;
 const isMed = item.id === "ntu-med-publication-115" || item.programKey === "ntu-med-publication";
 const aliases = isMed ? " 優秀著作 優秀論文 論文 著作 醫學院 研究生 出版 publication paper 成果獎" : "";
 const catLabel = (typeof labels !== "undefined" && labels.category && labels.category[item.category]) || "";
 const srcLabel = (typeof labels !== "undefined" && labels.source && labels.source[item.source]) || "";
 const haystack = (item.title + " " + item.id + " " + (item.cycle||"") + " " + (item.scope||"") + " " + catLabel + " " + srcLabel + aliases).toLocaleLowerCase();
 return haystack.includes(q);
}
function parseUrlParams(searchStr, hashStr) {
 const search = (searchStr || "").replace(/^\?/, "");
 const params = new URLSearchParams(search);
 const hash = (hashStr || "").replace(/^#/, "");
 const res = {};
 if (params.get("tab")) res.tab = params.get("tab");
 else if (["search", "detail", "timeline", "rights"].includes(hash)) res.tab = hash;
 if (params.get("q")) res.query = params.get("q");
 if (params.get("cat")) res.category = params.get("cat");
 if (params.get("deg")) res.degree = params.get("deg");
 if (params.get("mode") && ["demo", "draft"].includes(params.get("mode"))) res.mode = params.get("mode");
 if (params.get("view") && ["list", "gantt"].includes(params.get("view"))) res.view = params.get("view");
 if (params.get("id")) res.id = params.get("id");
 if (params.get("compare")) res.compare = params.get("compare");
 if (params.get("picks")) res.picks = params.get("picks").split(",").filter(Boolean);
 return res;
}
function serializeStateToParams(current, defaultMode="demo") {
 const params = new URLSearchParams();
 if (current.tab && current.tab !== "search") params.set("tab", current.tab);
 if (current.mode && current.mode !== defaultMode) params.set("mode", current.mode);
 if (current.view && current.view !== "gantt") params.set("view", current.view);
 if (current.query) params.set("q", current.query);
 if (current.category && current.category !== "all") params.set("cat", current.category);
 if (current.degree && current.degree !== "all") params.set("deg", current.degree);
 if (current.id) params.set("id", current.id);
 if (current.compare) params.set("compare", current.compare);
 if (current.picks && current.picks.length > 0) params.set("picks", current.picks.join(","));
 return params.toString();
}
function partitionItems(items,filters){
 const matched=[],possible=[],unknownFields={};
 const query=(filters.query||"").trim().toLocaleLowerCase();
 for(const item of items){
  if(query && !itemMatchesQuery(item, query)) continue;
  const missing=[];let excluded=false;
  for(const key of ["category","source","degree","year","compatibility","hardship","application"]){
   const wanted=filters[key];if(!wanted||wanted==="all")continue;
   if(filterItems([item],{[key]:wanted,includeUnknown:false}).length)continue;
   const unknown=key==="degree"?(wanted==="candidate"?item.candidateMode==="unknown":!item.degrees?.length):
    key==="application"?item.rawState==="unknown":item[key]===undefined||item[key]===null||item[key]==="unknown";
   if(unknown&&wanted!=="unknown")missing.push(key);else{excluded=true;break;}
  }
  if(excluded)continue;
  if(missing.length){if(filters.includeUnknown){possible.push(item);unknownFields[item.id]=missing;}}
  else matched.push(item);
 }
 return {matched,possible,unknownFields,all:[...matched,...possible]};
}
function clarity(item,asOf=taipeiToday()){
 if(item.synthetic||item.personal)return {level:"example",text:item.personal?"個人規劃／未核實":"合成示範",known:0,total:0};
 const parts=[Boolean(officialUrl(item.url)&&item.title),Boolean(item.cycle&&!/待|不明|unknown/.test(item.cycle)),
  Boolean(item.timeRule||item.timePolicy?.rules?.length||(item.end.value&&item.end.certainty==="confirmed"&&item.resourceKind!=="tool_subscription")),Boolean(item.audience&&item.audienceKind!=="program_descriptor")];
 const known=parts.filter(Boolean).length;
 const invalidDate=[item.start,item.end].some(e=>e.value&&dayNumber(e.value)===null);
 const conflict=Boolean(item.conflict)||!parts[0]||invalidDate||(item.start.value&&item.end.value&&dayNumber(item.end.value)<dayNumber(item.start.value));
 const checked=dayNumber(item.sourceChecked),fresh=checked!==null&&dayNumber(asOf)-checked>=0&&dayNumber(asOf)-checked<=180;
 return {level:conflict?"red":known===4&&fresh?"green":"amber",text:conflict?"待重新核對":known===4&&fresh?"核心資訊明確":"部分資訊待確認",known,total:4};
}
function groupDocuments(items){
 const groups=new Map();
 for(const item of items){const key=item.personal||item.synthetic?item.id:item.programKey||item.id;
  if(!groups.has(key))groups.set(key,[]);groups.get(key).push(item);}
 return [...groups.values()].map(docs=>{
  const rank=item=>(["academic_year","calendar_year"].includes(item.cycleKind)&&!/待|unknown/.test(item.cycle)?2:0)+(item.cycleKind==="event_relative"?1:0);
  const year=item=>{const n=Number(item.cycleYear)||Number((item.cycle||'').match(/(?:20\d{2}|1\d{2})/)?.[0])||0;return n>=100&&n<1000?n+1911:n;};
  const primary=[...docs].sort((a,b)=>rank(b)-rank(a)||year(b)-year(a)||a.id.localeCompare(b.id))[0];
  return {...primary,relatedDocuments:docs.filter(d=>d.id!==primary.id).map(d=>({id:d.id,title:d.title,url:d.url,cycle:d.cycle}))};
 });
}
function makeDrafts(pilot,asOf=taipeiToday(),radarData=null) {
 const funding = {
  "ntu-tuition-115-1":"government","ntu-emergency-policy":"university",
  "ntu-nstc-phd-115":"government","ntu-moe-phd-115-round2":"government",
  "ntu-med-publication-115":"university","ntu-president-114":"university",
  "nstc-grad-conference-policy":"government","nstc-abroad-116-ntu":"government",
  "ntu-yuanxue-115-ordinary":"university","ntu-ta-policy":"university",
  "taipei-ai-tools":"government","hsinchu-ai-tools":"government"
 };
 const sourceMap = new Map(pilot.sources.map(s=>[s.id,s]));
 return pilot.opportunities.map(item => {
  const student = item.steps.find(s=>s.actor==="student" && ["date","datetime"].includes(s.deadline?.kind));
  const milestones = item.steps.filter(s=>s.actor!=="student" && ["date","datetime"].includes(s.deadline?.kind)).map(s=>({
   label:{college:"學院送件",institution:"機關送件",university:"校級程序",unit:"單位程序"}[s.actor] || "其他程序",
   ...event(s.deadline.value,"confirmed",s.action+"；"+s.deadline.note)
  }));

  let resolvedSource = funding[item.id] || funding[item.program_key];
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
  const structuredStart = (item.start && item.start.value) ? event(item.start.value, startCertainty, item.start.note || (startCertainty==="inferred"?"依官方公告發布日推定即日起受理":"官方受理申請起始日")) : event(null, "unknown", item.field_applicability?.application_start?.reason||"目前無結構化申請起日；依內文敘述");
  const structuredResult = (item.result && item.result.value && ["date","datetime"].includes(item.result.kind)) ? event(item.result.value, item.result.certainty || "unknown", item.result.note || "結果公告日") : event(null, "unknown", item.field_applicability?.result_date?.reason||"結果尚無結構證據");

  const sources = [...item.application.refs,...item.steps.flatMap(s=>s.refs)];
  const source = sources.map(r=>sourceMap.get(r.source)).find(Boolean);
   const state=windowState(item,asOf);
   const draft={
   id:item.id,title:item.title,category:item.category,source:resolvedSource,programKey:item.program_key,cycleKind:item.cycle.kind,cycleYear:item.cycle.year,resourceKind:item.resource_kind,
   audience:unknownValue(item.eligibility.identity.text)?null:item.eligibility.identity.text,
   audienceKind:item.eligibility.identity.claim_kind||"source_specific_summary",
   degrees:/身分條件請至來源/.test(item.eligibility.identity.text)?[]:item.eligibility.degrees,year:item.field_applicability?.year_limit?.status==="not_applicable"?"not_applicable":item.eligibility.year_limit.mode,
   candidateMode:item.eligibility?.candidate?.mode || "unknown",
   compatibility:item.compatibility.mode,hardship:item.hardship.mode,
   cycle:item.cycle.label,synthetic:false,
   method:item.application_method,applicability:item.field_applicability||{},benefit:item.benefit.text,
   start:structuredStart,
   end:event(student?.deadline?.value||null,student?"confirmed":"unknown",student?.deadline?.note||"學生截止尚未確認"),
   result:structuredResult,
   milestones,
    application:({open:"受理中（依已記錄條件）",closed:"本期已截止",unknown:UNKNOWN_LABEL,not_yet_open:"尚未開放",not_applicable:item.application_method?.mode==="automatic"?"來源明示免另行申請":"制度參考；當期申請請查個別公告"})[state],
    rawState:state,
   evidence:item.evidence_status==="incomplete"?"資料不完整／草稿":"草稿待獨立覆核",
   url:source?.url||null,officeUrl:officialUrl(item.organizations?.receiver?.url),sourceChecked:source?.checked_on,
   organizations:Object.fromEntries(Object.entries(item.organizations||{}).filter(([,fact])=>fact.refs?.length&&!unknownValue(fact.text)).map(([role,fact])=>[role,fact.text])),
   timeSteps:[],estimatedStart:null,
   sourceVersion:source?.locator?.startsWith("來源revision ")?source.locator:pilot.as_of,conflict:item.evidence_status==="conflicting_sources",
   timeRule:item.steps.find(s=>s.actor==="student"&&s.deadline?.kind==="relative")?.deadline?.note||null,
   note:item.application.reason+"；所有資料皆待獨立覆核。"
  };
  const meta=radarData?.records?.[item.id];
  if(meta){
   draft.url=officialUrl(meta.url);draft.sourceVersion=meta.revision;draft.sourceChecked=taipeiToday(new Date(meta.observed_at));
   draft.conflict=meta.unsafe;
   draft.organizations=meta.organizations||{};
   if(meta.programme_source){draft.source=meta.programme_source.type;draft.sourceBasis=meta.programme_source.label;}
   draft.timeSteps=meta.time_steps||[];
   draft.timePolicy=meta.time_policy;
   if(meta.known.start&&["inferred","tentative"].includes(draft.start.certainty))draft.estimatedStart={...draft.start};
   if(!meta.known.audience){draft.audience=null;draft.degrees=[];}
   for(const key of ["year","compatibility","hardship"])if(!meta.known[key])draft[key]="unknown";
   if(!meta.known.candidate)draft.candidateMode="unknown";
   if(!meta.known.start||["inferred","tentative","unknown"].includes(draft.start.certainty))draft.start=event();
   if(!meta.known.deadline){draft.end=event();draft.timeRule=null;}
   if(!meta.known.result)draft.result=event();
   if(meta.time_dates&&!meta.unsafe){
    for(const key of ["start","end","result"])draft[key]=meta.time_dates[key]?{...meta.time_dates[key]}:event();
    draft.timeObservedAt=meta.time_observed_at;draft.timeRevision=meta.time_revision;
    draft.estimatedStart=null;
    draft.note="時程由本輪來源重萃；資格與其他欄位各自查核。所有資料皆待獨立覆核。";
    if(!["automatic","reference"].includes(meta.time_policy?.submission_mode)){
     draft.rawState="unknown";draft.application="時程已更新；目前受理狀態請查來源";
     if(dayNumber(draft.end.value)!==null&&dayNumber(draft.end.value)<dayNumber(asOf)){draft.rawState="closed";draft.application="已記錄的學生截止已過（資格另核）";}
     else if(dayNumber(draft.start.value)!==null&&dayNumber(draft.start.value)>dayNumber(asOf)){draft.rawState="not_yet_open";draft.application="尚未開放（已記錄起日）";}
    }
    draft.milestones=(meta.time_policy?.gaps?.includes("multiple_cycles_need_split")?[]:meta.time_policy?.rules||[]).filter(r=>r.kind==="absolute"&&r.actor!=="student"&&r.stage!=="result").map(r=>({
     ...event(r.value,"confirmed",r.summary),label:(timingActors[r.actor]||"其他程序")+(r.stage==="application_start"?"起日":"截止")
    }));
   }
   if(!meta.known.benefit)draft.benefit=null;
   if(!meta.known.method)draft.method=null;
   if(meta.unsafe){draft.rawState="unknown";draft.application=UNKNOWN_LABEL;draft.applicability={};}
  }
  return draft;
 });
}
const timelineLabels={announcement:"公布",application_start:"申請開始",student_deadline:"學生截止",supplement_deadline:"補件截止",college_forward:"學院送件",university_forward:"校級彙送",decision:"核定（排程）",result_publication:"結果公布",payment:"報支／撥款"};
function timelinePhase(phase){return phase.split("／").map(p=>/^round\d+$/.test(p)?"第"+p.slice(5)+"梯次":p==="annual"?"年度收件":p).join("／");}
function applyTimeline(item,data,scope,year,showBaselines=true,asOf=taipeiToday()){
 if(item.personal||item.synthetic)return item;
 const contexts=data?.records?.[item.id]?.contexts.filter(c=>(scope==="examples"||c.scope===scope)&&c.year===Number(year))||[];
 if(!contexts.length)return item;
 if(scope==="examples"){
  // Each unit/round keeps its own interval; examples never change the global intake status.
  const examples=contexts.map(c=>{
   const localData={...data,records:{[item.id]:{contexts:[c]}}};
   const local=applyTimeline(item,localData,c.scope,year,showBaselines,asOf);
   return {...local,rawState:item.rawState,application:item.application,timeline:{...local.timeline,isExample:true}};
  });
  const first=examples[0];
  return {...(examples.length===1?first:item),timeSteps:item.timeSteps,timeline:{...first.timeline,examples,
   events:[...new Map(examples.flatMap(e=>e.timeline.events).map(e=>[e.id,e])).values()],
   baselines:examples.flatMap(e=>e.timeline.baselines),conflict:examples.some(e=>e.timeline.conflict)}};
 }
 const documents=new Map(data.documents.map(d=>[d.id,d]));
 const events=[...new Map(contexts.flatMap(c=>c.events).map(e=>[e.id,e])).values()];
 const multiPhase=new Set(contexts.map(c=>c.phase)).size>1;
 const conflict=contexts.some(c=>c.conflict)||multiPhase;
 const pick=kind=>events.filter(e=>e.kind===kind&&e.certainty!=="expected").sort((a,b)=>b.value.length-a.value.length)[0];
 const start=conflict?null:pick("application_start"), end=conflict?null:pick("student_deadline");
 const fresh=e=>{const checked=dayNumber(documents.get(e?.document_id)?.checked_on),now=dayNumber(asOf);return checked!==null&&now-checked>=0&&now-checked<=180;};
 const baseline=showBaselines?contexts.flatMap(c=>c.baselines):[];
 const marks=events.filter(e=>!["application_start","student_deadline"].includes(e.kind)||e.certainty==="expected").map(e=>({
  label:(e.basis==="publication_year_context"?"公告年份推估 ":e.certainty==="expected"?"預定 ":"")+timelineLabels[e.kind],...event(e.value,e.certainty,e.kind),
  sourceUrl:documents.get(e.document_id)?.url,eventId:e.id}));
 let rawState=item.rawState;
 if(conflict||item.conflict)rawState="unknown";
 else if(item.cycleKind==="policy_snapshot")rawState=item.rawState;
 else if(!conflict&&end&&end.value.slice(0,10)<asOf)rawState="closed";
 else if(!conflict&&start&&fresh(start)&&start.value.slice(0,10)>asOf)rawState="not_yet_open";
 // A historical estimate, publication date or administrative milestone never opens a call.
 else if(!conflict&&start&&end&&fresh(start)&&fresh(end)&&start.value.slice(0,10)<=asOf&&end.value.slice(0,10)>asOf)rawState="open";
 else if(start||end)rawState="unknown";
 const actual=events.length>0;
 return {...item,start:start?event(start.value,"confirmed",start.basis==="since_publication"?"同公告即日起＋發布日":"地方公告明載"):event(),
  end:end?event(end.value,"confirmed","地方收件期限"):event(),result:event(),milestones:marks,
  rawState,application:actual?({closed:"本期已截止（地方公告）",open:"受理中（地方公告，資格另核）",not_yet_open:"尚未開放（地方公告）"}[rawState]||item.application):item.application,
  timeSteps:[],estimatedStart:null,
  timeline:{scope,scopeLabel:contexts[0].scope_label,year:Number(year),events,baselines:baseline,conflict,
   multiPhase,
   phase:contexts.map(c=>c.phase).join("／"),documents:documents,
   documentIds:[...new Set(contexts.flatMap(c=>c.document_ids||[]))]},
  note:item.note+"；地方補充時程僅適用"+contexts[0].scope_label+"，不代表其他單位期限。"};
}
function timelineDates(item){return [...(item.timeline?.baselines||[]).flatMap(b=>[b.start,b.end]),...(item.timeline?.events||[]).map(e=>e.value)];}
function filterItems(items, filters) {
 const query = (filters.query||"").trim().toLocaleLowerCase();
 return items.filter(item=>{
  if(query && !itemMatchesQuery(item, query)) return false;
  return ["category","source","degree","year","compatibility","hardship","application"].every(key=>{
   const wanted=filters[key];
   if(!wanted || wanted==="all") return true;
   if(key==="category") {
    if(wanted==="all_abroad" || wanted==="abroad_all") {
     return item.category==="international_conference" ||
            item.category==="overseas_research" ||
            item.resourceKind==="travel_grant" ||
            (item.title && /出國|境外|海外|國際會議/.test(item.title));
    }
    if(wanted==="all_k12" || wanted==="k12_all") {
     return (item.id && item.id.includes("k12")) ||
            (item.audience && /elementary|junior_high|senior_high|vocational|preschool/i.test(item.audience)) ||
            (item.title && /小學|國中|高中|高職|幼兒|兒少|弱勢助學|就學助學金/.test(item.title));
    }
    const value=item[key];
    if(Array.isArray(value)) return value.includes(wanted);
    return value===wanted || (filters.includeUnknown && value==="unknown");
   }
   if(key==="degree") {
    if(wanted==="candidate") return item.candidateMode==="required" || item.degrees?.includes("candidate");
    if(wanted==="master_phd") return Array.isArray(item.degrees) && (item.degrees.includes("master") || item.degrees.includes("phd"));
    if(wanted==="undergraduate") {
     return (Array.isArray(item.degrees) && item.degrees.includes("undergraduate")) ||
            (item.audience && /大學|學士|大專|undergraduate/i.test(item.audience)) ||
            (item.title && /大學|學士|大專/i.test(item.title));
    }
    if(wanted==="senior_high") {
     return (Array.isArray(item.degrees) && item.degrees.includes("senior_high")) ||
            (item.audience && /senior_high|vocational|高中|高職|五專/i.test(item.audience)) ||
            (item.title && /高中|高職|五專/i.test(item.title));
    }
    if(wanted==="basic_k12") {
     return (Array.isArray(item.degrees) && (item.degrees.includes("elementary") || item.degrees.includes("junior_high") || item.degrees.includes("preschool"))) ||
            (item.audience && /elementary|junior_high|preschool|國中|國小|幼兒|小學|幼兒園/i.test(item.audience)) ||
            (item.title && /國中|國小|幼兒/i.test(item.title));
    }
    return Array.isArray(item.degrees) && item.degrees.includes(wanted);
   }
   if(key==="application") {
    if(wanted==="open") return item.rawState==="open";
    if(wanted==="upcoming") return item.rawState==="not_yet_open";
    if(wanted==="closed") return item.rawState==="closed";
    if(wanted==="unknown") return item.rawState==="unknown";
    if(wanted==="not_applicable") return item.rawState==="not_applicable";
    return true;
   }
   const value=item[key];
   if(Array.isArray(value)) return value.includes(wanted);
   return value===wanted || (filters.includeUnknown && value==="unknown");
  });
 });
}
function noticeWindow(item) {
 if(item.personal || item.resourceKind==="tool_subscription" || isNA(item,"application_start") || isNA(item,"student_deadline") || item.start.value || dayNumber(item.end.value)===null) return null;
 return {start:addDays(item.end.value.slice(0,10),-30),end:item.end.value};
}
function isNA(item,key) {
 const kind={application_start:"application_start",student_deadline:"student_deadline",result_date:"result_publication"}[key];
 if(!item.timeline?.conflict&&item.timeline?.events.some(e=>e.kind===kind))return false;
 return item.applicability?.[key]?.status==="not_applicable";
}
function fieldText(item,key,value) {
 return isNA(item,key) ? "N/A 不適用（"+item.applicability[key].reason+"）" : dateText(value);
}
function resultText(item) {return fieldText(item,"result_date",item.result.value);}
function methodText(method) {
 if(!method) return "申請方式待確認";
 const mode={paper:"紙本申請",electronic:"電子申請",hybrid:"紙本＋電子（須核對各階段／是否擇一）",automatic:"免另行申請",unknown:"申請方式待確認",not_applicable:"申請方式 N/A 不適用"}[method.mode];
 const paper={required:"須遞交紙本",not_required:"免遞交紙本",unknown:"紙本遞交待確認",not_applicable:"紙本遞交 N/A 不適用"}[method.paper_delivery];
 const basis={received:"以送達為準",postmark:"以郵戳為準",online_submission:"以線上送出為準"}[method.deadline_basis];
 return [mode,paper,method.handwritten_signature==="required"?"需親筆簽名（另核對是否上傳）":null,basis].filter(Boolean).join("；");
}
function startLabel(item) {
 if(isNA(item,"application_start")) return fieldText(item,"application_start",null);
 const suffix={inferred:"（推定）",tentative:"（暫定）",unknown:"（待確認）"}[item.start.certainty] || "";
 return item.start.value ? dateText(item.start.value)+suffix : UNKNOWN_LABEL;
}
function domain(items,today,mode="recent",offset=0) {
 const current=dayNumber(today);
 if(mode==="fit") {
  const values=items.flatMap(x=>[x.start.value,x.end.value,x.result.value,...x.milestones.map(m=>m.value),x.preparation?.start,noticeWindow(x)?.start,...timelineDates(x)]).map(dayNumber).filter(x=>x!==null);
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
function dateText(value) { return value ? value.slice(0,10).replaceAll("-","/")+(value.length>10?" "+value.slice(11,16):"") : UNKNOWN_LABEL; }
function deadlineText(item){return (item.personal&&item.end.value?"試算／自填 ":item.resourceKind==="tool_subscription"&&item.end.value?"年度最晚上限（個人期限另核） ":"")+fieldText(item,"student_deadline",item.end.value);}
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
 abroad_all:{category:"all_abroad",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 abroad_conf:{category:"international_conference",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 overseas_study:{category:"overseas_research",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 k12_aid:{category:"all_k12",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 outcome_award:{category:"outcome_award",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 ta_assistant:{category:"indirect_support",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"},
 research_tools:{category:"research_tools",source:"all",degree:"all",year:"all",compatibility:"all",hardship:"all"}
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
const api={dayNumber,iso,taipeiToday,addDays,makeDemo,makeDrafts,timePresentation,windowState,filterItems,partitionItems,clarity,groupDocuments,issueUrl,officialUrl,UNKNOWN_LABEL,unknownValue,workspaceItems,domain,position,centerScroll,geometry,noticeWindow,conferencePlan,monthsBefore,makeConferenceItem,conferenceEntries,personaPresets,activePersona,applyPersona,evaluateSubordination,isNA,fieldText,resultText,methodText,startLabel,deadlineText,applyTimeline,timelineDates,itemMatchesQuery,parseUrlParams,serializeStateToParams};
if(typeof module!=="undefined" && module.exports) module.exports=api;
if(typeof document==="undefined") return;

const byId=id=>document.getElementById(id);
const pilot=JSON.parse(byId("pilot-data").textContent);
const conferenceData=JSON.parse(byId("conference-data").textContent);
const reviewPreview=document.body.dataset.reviewPreview==="true";
const radarView=document.body.dataset.radarView==="true";
const radarData=byId("radar-data")?JSON.parse(byId("radar-data").textContent):null;
const chainData=byId("source-chain-data")?JSON.parse(byId("source-chain-data").textContent):null;
let timelineYear=chainData?.years[0]||Number(taipeiToday().slice(0,4)),showBaselines=true;
if(reviewPreview){byId("mode-switch").hidden=true;byId("conference-program")?.closest("details")?.setAttribute("hidden","");}
const personalConferences=new Map();
function scoped(items){return items.map(item=>applyTimeline(item,chainData,"examples",timelineYear,showBaselines,today));}
function currentItems(){return [...scoped(mode==="demo"?makeDemo(today):documentMode==="documents"?documentDrafts:drafts),...personalConferences.values()];}
function allItems(){return [...scoped(mode==="demo"?makeDemo(today):documentDrafts),...personalConferences.values()];}
const documentDrafts=[...makeDrafts(pilot,taipeiToday(),radarData),...(reviewPreview||radarView?[]:conferenceEntries(conferenceData.programs))];
const drafts=groupDocuments(documentDrafts);
let documentMode="documents";
const rawById=new Map(pilot.opportunities.map(item=>[item.id,item]));
const sourceById=new Map(pilot.sources.map(source=>[source.id,source]));
const picked={demo:new Set(),draft:new Set()}, completed={demo:new Set(),draft:new Set()}, activeDetail={demo:null,draft:null};
let sharedItems=[], personalRangeMode="recent", lastPersonalRange=null;
let today=taipeiToday(), mode=reviewPreview||radarView?"draft":"demo", view="gantt", rangeMode="recent", offset=0, inspectedId=null, lastRange=null, centerPending=true, rightsView="overview", activePanelId="search", detailScope="shared", detailSearchQuery="", activeCompareId=null;
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
if(window.matchMedia("(max-width:800px)").matches)document.querySelector("#search .filter>details").open=false;
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
function activatePanel(id, focus=false, updateUrl=true) {
 if(!["search","detail","timeline","rights"].includes(id)) id="search";
 if(activePanelId && byId(activePanelId) && !byId(activePanelId).hidden) scrollPositions[activePanelId]=window.scrollY;
 document.querySelectorAll('[role="tab"]').forEach(tab=>{
  const active=tab.dataset.panel===id;
  tab.setAttribute("aria-selected",String(active));
  tab.tabIndex=active?0:-1;
  if(active && focus) tab.focus();
 });
 document.querySelectorAll("main > .screen").forEach(panel=>{panel.hidden=panel.id!==id;});
 activePanelId=id;
 if(updateUrl) updateUrlState(true);
 window.scrollTo({top:scrollPositions[id]||0,behavior:"instant"});
 if(id==="search" && lastRange) requestAnimationFrame(()=>centerToday(lastRange));
 if(id==="timeline" && lastPersonalRange) requestAnimationFrame(()=>centerToday(lastPersonalRange,"personal-gantt-grid"));
}

function updateUrlState(push=false) {
 if (typeof window === "undefined" || !window.history) return;
 const stateObj = {
  tab: activePanelId,
  mode,
  view,
  query: state.query,
  category: state.category,
  degree: state.degree,
  id: activeDetail[mode],
  compare: activeCompareId,
  picks: Array.from(picked[mode])
 };
 const queryString = serializeStateToParams(stateObj, reviewPreview||radarView ? "draft" : "demo");
 const newUrl = window.location.pathname + (queryString ? "?" + queryString : "") + (location.hash ? location.hash : "");
 if (window.location.search !== (queryString ? "?" + queryString : "")) {
  if (push) history.pushState(null, "", newUrl);
  else history.replaceState(null, "", newUrl);
 }
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
 const rightsSection=target.closest("[data-rights-section]");
 if(rightsSection) setRightsView(rightsSection.dataset.rightsSection);
 for(let details=target.closest("details");details;details=details.parentElement?.closest("details")) details.open=true;
 if(location.hash!=="#"+targetId) history.replaceState(null,"","#"+targetId);
 target.scrollIntoView({behavior:"instant",block:"start"});
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
 const tags = [item.source!=="unknown"?(labels.source[item.source]||item.source):null, (item.degrees||[]).map(x=>labels.degree[x]||x).join("／"), item.year!=="unknown"?(labels.year[item.year]||item.year):null, item.compatibility!=="unknown"?(labels.compatibility[item.compatibility]||item.compatibility):null, item.hardship!=="unknown"?(labels.hardship[item.hardship]||item.hardship):null];
 if(item.candidateMode==="required") tags.push("須博士候選人");
 if(isNA(item,"year_limit")) tags[2]="年級 N/A 不適用";
 return tags.filter(Boolean);
}
function sourceLink(text,item,url=item.url){
 const safe=officialUrl(url);if(!safe)return el("span","quiet",item.synthetic?"合成示範，無官方來源":text+"（目前無有效來源連結）");
 const a=el("a",text.includes(UNKNOWN_LABEL)?"unknown-link":"",text+" ↗");
 if(text.includes(UNKNOWN_LABEL)){const icon=el("span","unknown-icon","⚠");icon.setAttribute("aria-hidden","true");a.prepend(icon);a.title="來源可能未載明或尚未完整辨識，請核對官方原文";}
 a.href=safe;a.target="_blank";a.rel="noopener noreferrer";return a;
}
function radarFact(container,label,value,item){
 const p=el("p","small");p.append(el("strong","",label+"："));
 const unknown=unknownValue(value);
 p.append(unknown?sourceLink(UNKNOWN_LABEL,item):document.createTextNode(value));container.append(p);
}
function radarLinks(item){
 const links=el("div","card-actions");
 if(!item.synthetic&&!item.personal){
  links.append(sourceLink("官方公告",item));
  links.append(item.organizations?.receiver?sourceLink("收件／轉送："+item.organizations.receiver,item,item.officeUrl||item.url):sourceLink("收件單位："+UNKNOWN_LABEL,item));
 }
 const report=el("a","","回報問題 ↗");report.href=issueUrl(item);report.target="_blank";report.rel="noopener noreferrer";links.append(report);
 return links;
}
function timelineSummary(container,item){
 if(!item.timeline)return;
 if(item.timeline.examples){for(const example of item.timeline.examples)timelineSummary(container,example);return;}
 const t=item.timeline, box=el("div","timeline-summary");
 box.append(el("p","small",(t.isExample?"以"+t.scopeLabel+"為例；實際請以所屬系所為準":"地方補充時程："+t.scopeLabel+"（僅此單位適用）")+" · "+t.year+"年 · "+timelinePhase(t.phase)));
 if(t.conflict)box.append(el("p","callout",t.multiPhase?"有多個梯次，暫不合成單一申請條；請分別核對公告。":"時程有衝突，暫不畫正式申請條；請核對補充公告。"));
 for(const e of t.events){
  const doc=t.documents.get(e.document_id),line=el("p","small",(e.basis==="publication_year_context"?"公告年份推估 ":e.certainty==="expected"?"預定 ":"")+timelineLabels[e.kind]+"："+dateText(e.value)+(e.basis==="since_publication"?"（公告明載即日起）":""));
  line.append(el("span","","　"),sourceLink("時程來源",item,doc?.url));box.append(line);
 }
 for(const b of t.baselines){
  const label=b.kind==="publication_year_reference"?"公告年份推估（原文僅載月日）":b.kind==="historical_estimate"?"歷史估計（低信心）":"單年度參考（非正式起訖）";
  box.append(el("p","small",label+"："+b.start+"–"+b.end+"；參考"+b.sample_years.join("、")+"年，實際以當期公告為準。"));
 }
 if(!t.events.length)box.append(el("p","small","此參考年度尚無已讀取的當期地方公告；歷史底帶不代表已開放申請。"));
 const details=el("details");details.append(el("summary","來源資訊鏈（公告／辦法與格式）"));
 const ids=new Set(t.documentIds);
 for(const r of chainData?.relations||[])if(ids.has(r.from))ids.add(r.to);
 for(const id of ids){
  const d=t.documents.get(id);if(!d)continue;
  const line=el("p","small");
  const status=["changed","unchanged","unchanged_304"].includes(d.status)?"已讀取":d.status==="candidate_snapshot"?"既有快照":"待讀取／需核對";
  const role=d.role==="policy"?"制度辦法":d.role==="local_intake"?"收件公告":"相關來源";
  line.append(sourceLink(role+"（"+(d.format==="unknown"?"格式待核":d.format.toUpperCase())+"；"+status+"）",item,d.url));details.append(line);
 }
 box.append(details);container.append(box);
}
function radarSummary(container,item){
 const quality=clarity(item),badge=el("p","clarity "+quality.level);
 badge.textContent=({green:"🟢 ",amber:"🟡 ",red:"🔴 ",example:"○ "})[quality.level]+quality.text+(quality.total?" · 核心資訊 "+quality.known+"／"+quality.total+" 項":"");
 container.append(badge);
 timelineSummary(container,item);
 renderTimePolicy(container,item);
 if(item.rawState==="closed")container.append(el("p","small","歷史公告：本期已截止"));
 radarFact(container,item.audienceKind==="program_descriptor"?"對象線索（非完整資格）":"大致對象",item.audience||(item.synthetic?"合成示範":null),item);
 if(item.estimatedStart)radarFact(container,"推估開始（非官方起日）",dateText(item.estimatedStart.value)+"；"+item.estimatedStart.note,item);
 if(!item.timePolicy?.rules?.length){
 if(item.rawState==="not_applicable")radarFact(container,"申請時間",item.method?.mode==="automatic"?"來源明示免另行申請":"制度參考；當期申請請查個別公告",item);
 else if(item.timeSteps?.length){
  if(item.start.value)radarFact(container,"申請開始",startLabel(item),item);
  for(const step of item.timeSteps){
   const actor={student:"學生",department:"系所",unit:"單位",college:"學院",university:"校級",institution:"機構",supplement:"補件"}[step.actor]||"其他程序";
   radarFact(container,actor+(step.deadline.kind==="relative"?"時間規則":"期限"),[step.action,step.deadline.value?dateText(step.deadline.value):null,step.deadline.note].filter(Boolean).join("；"),item);
  }
  if(!item.timeSteps.some(s=>s.actor==="student"))radarFact(container,"學生截止",null,item);
 }
 else if(item.timeRule)radarFact(container,"申請時間規則",item.timeRule,item);
 else if(item.start.value||item.end.value){radarFact(container,"申請開始",item.start.value?startLabel(item):null,item);radarFact(container,"學生截止",item.end.value?deadlineText(item):null,item);}
 else radarFact(container,"申請時間",null,item);
 }
 const missing=[item.year==="unknown"?"年級":null,item.compatibility==="unknown"?"兼領":null,item.hardship==="unknown"?"清寒限定":null].filter(Boolean);
 if(missing.length)radarFact(container,missing.join("／"),null,item);
 container.append(radarLinks(item));
 if(item.relatedDocuments?.length){
  const details=el("details");details.append(el("summary","相關公告／辦法（"+item.relatedDocuments.length+"份）"));
  for(const doc of item.relatedDocuments){const p=el("p","small");p.append(sourceLink(doc.title,item,doc.url));details.append(p);}container.append(details);
 }
}
function renderTimePolicy(container,item,expanded=false){
 const timing=timePresentation(item),box=el("div","time-policy"),label=el("p","time-label "+(timing.known?"known":"pending"));
 const icon=el("span","",timing.icon);icon.setAttribute("aria-hidden","true");label.append(icon,el("strong","",timing.label));box.append(label);
 if(item.timeObservedAt){const checked=el("p","tiny quiet","時程檢核："+taipeiToday(new Date(item.timeObservedAt)));checked.title="時程來源revision "+item.timeRevision;box.append(checked);}
 if(timing.rules.length){
  const list=el("ul","time-rule-list");
  for(const rule of timing.rules){
   const stageSuffix=rule.stage==="application_start"?"起日":rule.stage==="result"?"結果公布":"";
   const actorTitle=rule.stage==="result"&&rule.actor==="other"?"結果公布":(timingActors[rule.actor]||"其他程序")+stageSuffix;
   const row=el("li");row.append(el("strong","",actorTitle+"："));
   if(rule.value){const date=el("time","",dateText(rule.value));date.dateTime=rule.value;row.append(date,"；");}
   row.append(document.createTextNode(rule.summary+" "));
   for(const evidence of rule.source_refs){
    const isModelVerified=String(evidence.evidence_path||"").startsWith("temporal_model_verified/");
    const ref=sourceLink(evidence.url?"來源附件":"來源",{...item,url:evidence.url||item.url});
    ref.title=(isModelVerified?"雙軌引文核驗 · ":"")+evidence.locator;
    if(isModelVerified)ref.dataset.evidenceOrigin="model_verified";
    row.append(ref," ");
   }
   list.append(row);
  }
  if(expanded)box.append(list);
  else {const details=el("details"),summary=el("summary","",timing.rules.length+" 條時間規則（依角色分列）");details.append(summary,list);box.append(details);}
 }
 if(timing.gaps.length)box.append(el("p","tiny quiet",timing.gaps.join("；")));
 if(!timing.known)box.append(sourceLink("確認當期／所屬單位公告",item));
 else if(timing.rules.some(r=>r.anchor_event==="conference_start")){
  const link=el("a","time-planner-link","選擇方案並填入活動日期 →");link.href="#conference-planner";box.append(link);
 }
 container.append(box);
}
function inspect(item) {
 inspectedId=item.id;
 const box=byId("schedule-inspect");box.replaceChildren();
 box.append(el("strong","",item.title));
 timelineSummary(box,item);
 renderTimePolicy(box,item,true);
 if(!item.timePolicy?.rules?.length){
  radarFact(box,"申請開始",item.start.value?startLabel(item):null,item);
  radarFact(box,"學生截止",item.end.value?deadlineText(item):null,item);
  radarFact(box,"結果公告",resultText(item),item);
 }
 item.milestones.forEach(m=>box.append(el("p","small",m.label+"："+dateText(m.value))));
 box.append(el("p","tiny quiet",item.synthetic?"合成排程，全部為虛構日期。":item.note));
 box.append(radarLinks(item));
 const more=el("button","secondary",picked[mode].has(item.id)?"查看詳情":"勾選並看詳情");more.type="button";more.dataset.openDetail=item.id;
 more.addEventListener("click",()=>chooseAndOpen(item));box.append(more);
 const wasHidden=box.hidden;
 box.hidden=false;
 if(wasHidden && typeof box.getBoundingClientRect==="function"){
  const rect=box.getBoundingClientRect();
  if(rect.top<180 || rect.bottom>window.innerHeight) box.scrollIntoView({behavior:"instant",block:"start"});
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
function drawCards(items,partition) {
 const list=byId("result-cards");list.replaceChildren();
 items.forEach(item=>{
  if(partition&&item.id===partition.matched[0]?.id)list.append(el("h3","result-group",partition.active?"符合已知篩選條件（非資格核定）":"來源摘要（非資格核定）"));
  if(partition&&item.id===partition.possible[0]?.id)list.append(el("h3","result-group","可能相關：部分篩選條件未確認"));
  const card=el("article","card");
  card.append(el("div","category",labels.category[item.category]+" · "+item.cycle));
  card.append(el("h3","",item.title));
  radarSummary(card,item);
  const tags=el("div","pills");itemTags(item).forEach(tag=>tags.append(el("span","pill",tag)));card.append(tags);
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
 if(item.timeline?.isExample)label="以"+item.timeline.scopeLabel+"為例；實際請以所屬系所為準；"+label;
 const node=el("button","gantt-marker "+kind);
 node.type="button";node.style.left=percent+"%";
 node.title=label;node.setAttribute("aria-label",item.title+"："+label);
 node.addEventListener("click",()=>onInspect(item));plot.append(node);
}
function drawGantt(items,range,gridId="gantt-grid",onInspect=inspect) {
 const grid=byId(gridId);grid.replaceChildren();
 grid.style.minWidth=Math.max(960,280+(range.end-range.start+1)*4)+"px";
 grid.style.setProperty("--week-step",7/(range.end-range.start+1)*100+"%");
 const top=el("div","gantt-row gantt-top");
 top.append(el("div","gantt-label gantt-heading","獎助項目／申請時程"));
 const head=el("div","gantt-plot axis-plot");
 const tickStep=range.end-range.start>180?28:range.end-range.start>100?14:7;
 for(let day=range.start;day<=range.end;day+=tickStep) head.append(tickNode(iso(day).slice(5).replace("-","/"),position(iso(day),range)));
 const monthMarks=new Set();
 for(let day=range.start;day<=range.end;day++) {
  const month=iso(day).slice(0,7);
  if(!monthMarks.has(month)){
   monthMarks.add(month);
   if(day!==range.start||Number(iso(day).slice(8))<=15)head.append(tickNode(month.replace("-"," 年 ")+" 月",position(iso(day),range),"month-tick"));
  }
 }
 todayLine(head,range,true);top.append(head);grid.append(top);
 items.flatMap(item=>item.timeline?.examples||[item]).forEach(item=>{
  const g=geometry(item,range), row=el("div","gantt-row");
  const timing=timePresentation(item),hasCoordinates=[item.start.value,item.end.value,item.result.value,...item.milestones.map(m=>m.value),...timelineDates(item)].some(Boolean);
  const exampleNote=item.timeline?.isExample?"以"+item.timeline.scopeLabel+"為例；實際請以所屬系所為準":"";
  if(exampleNote)row.title=exampleNote+" · "+timelinePhase(item.timeline.phase);
  const label=el("div","gantt-label");
  if(gridId==="gantt-grid") label.append(pickControl(item,"gantt"));
  const button=el("button","row-title",item.title);button.type="button";button.addEventListener("click",()=>onInspect(item));
  label.append(button,el("div","tiny quiet",labels.category[item.category]+" · "+labels.source[item.source]));
  if(exampleNote)label.append(el("div","tiny quiet timeline-example",exampleNote+" · "+timelinePhase(item.timeline.phase)));
  const labelDateDesc = item.personal ? "學生期限："+deadlineText(item) : (item.start.certainty==="inferred"||item.end.certainty==="inferred"?"推定起訖：":"")+startLabel(item)+" → "+deadlineText(item);
  if(item.start.value||item.end.value)label.append(el("div","tiny quiet",labelDateDesc));
  else label.append(sourceLink(timing.label,item));
  if(item.start.value||item.end.value)label.append(el("div","tiny quiet",timing.label));
  if(partitionItems([item],state).possible.length)label.append(el("div","tiny quiet","部分篩選條件未確認"));
  row.append(label);
  const plot=el("div","gantt-plot"+(hasCoordinates?"":" rule-plot"));
  if(hasCoordinates||item.synthetic||item.personal)todayLine(plot,range);
  if(!hasCoordinates)renderTimePolicy(plot,item,true);
  for(const b of item.timeline?.baselines||[]){
   const area=geometry({start:event(b.start),end:event(b.end),result:event(),milestones:[]},range).bar;
   if(area){const bar=el("button","gantt-bar baseline");bar.type="button";bar.style.left=area.left+"%";bar.style.width=area.width+"%";
    bar.title=(exampleNote?exampleNote+"；":"")+(b.kind==="publication_year_reference"?"公告年份推估（原文僅載月日）":b.kind==="historical_estimate"?"歷史估計（低信心）":"單年度參考")+"："+b.start+" 至 "+b.end+"，參考"+b.sample_years.join("、")+"年；非官方申請期";
    bar.setAttribute("aria-label",item.title+"："+bar.title);bar.addEventListener("click",()=>onInspect(item));plot.append(bar);}
  }
  const announce=item.timeline?.events.find(e=>e.kind==="announcement");
  if(announce&&item.end.value){const area=geometry({start:event(announce.value),end:item.end,result:event(),milestones:[]},range).bar;
   if(area){const line=el("span","process-line");line.style.left=area.left+"%";line.style.width=area.width+"%";line.setAttribute("aria-hidden","true");plot.append(line);}}
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
   const isInferred=item.start.certainty==="inferred"||item.end.certainty==="inferred";
   const bar=el("button","gantt-bar"+(isInferred?" inferred":""));
   bar.type="button";bar.style.left=g.bar.left+"%";bar.style.width=g.bar.width+"%";
   bar.title=(exampleNote?exampleNote+"；":"")+(timing.mode==="conditional_deadline"?"外層受理區間（個人條件另核）：":isInferred?"推定受理期（依官方公告日推定）：":"申請期間：")+dateText(item.start.value)+" 至 "+dateText(item.end.value)+(isInferred?"（"+(item.start.note||item.end.note||"依官方公告發布日推定即日起受理")+"）":"");
   bar.setAttribute("aria-label",item.title+"，"+bar.title);bar.addEventListener("click",()=>onInspect(item));plot.append(bar);
  }
  const isStartInferred=item.start.certainty==="inferred";
  marker(plot,g.start,"start"+(isStartInferred?" inferred":""),(isStartInferred?"推定申請開始（依官方公告日）：":"申請開始：")+dateText(item.start.value)+(isStartInferred?"（"+(item.start.note||"")+"）":""),item,onInspect);
  marker(plot,g.end,"end"+(item.personal?" estimated":item.end.certainty==="inferred"?" inferred":""),(item.end.certainty==="inferred"?"推定學生截止（待核座標）：":"學生截止：")+deadlineText(item),item,onInspect);
  marker(plot,g.result,"result "+(item.result.certainty==="expected"?"expected":""),(item.result.certainty==="expected"?"預定":"")+"結果公布："+resultText(item),item,onInspect);
  item.milestones.forEach(m=>{const p=position(m.value,range);if(p!==null&&p>=0&&p<100) marker(plot,p,"milestone"+(item.personal?" estimated":""),m.label+"："+dateText(m.value),item,onInspect);});
  const notes=[];
  if(item.personal) notes.push("個人規劃：虛線為準備建議，空心節點待核");
  if(item.timeline)notes.push(item.timeline.year+"年 · "+timelinePhase(item.timeline.phase)+(item.timeline.conflict?" · 時程衝突":""));
  if(item.timeline?.baselines.length)notes.push("淺色底帶為歷史參考／估計，非官方受理");
  if(noticeWindow(item)) notes.push(prepNoticeGeom?"官方起日待確認（已標示截止前30天準備建議）":"準備建議在視窗外；官方起日待確認");
  else if(hasCoordinates&&!item.start.value && !item.personal) notes.push(isNA(item,"application_start")?"申請起日 N/A 不適用":"起日待確認");
  if(item.start.certainty === "inferred") notes.push("起日依官方公告推定");
  if(hasCoordinates&&!item.end.value) notes.push(isNA(item,"student_deadline")?"學生截止 N/A 不適用":"學生截止待確認");
  if(timing.mode==="conditional_deadline")notes.push(timing.gaps.join("；"));
  if(g.invalid) notes.push("起訖衝突，暫不畫期間");
  const hasKnown=[item.start.value,item.end.value,item.result.value,...item.milestones.map(m=>m.value),...timelineDates(item)].some(Boolean);
  if(hasKnown && !g.bar && !prepNoticeGeom && g.start===null && g.end===null && g.result===null && !item.milestones.some(m=>{const p=position(m.value,range);return p!==null&&p>=0&&p<100;})) notes.push("已知日期在視窗外");
  plot.append(el("div","gantt-notes",notes.join(" · ")));
  row.append(plot);grid.append(row);
 });
}
function drawTable(items) {
 const body=byId("date-rows");body.replaceChildren();
 items.forEach(item=>{
  const startDisplay=startLabel(item)+(item.start.certainty==="inferred"?" (推定)":"")+(!item.start.value&&item.end.value&&!item.personal&&!isNA(item,"application_start")?" (標示截止前30天準備帶)":"");
  const hasRules=item.timePolicy?.rules?.length;
  const startCell=!item.start.value&&hasRules?"未有固定起日，請見規則":startDisplay;
  const endCell=!item.end.value&&hasRules?(item.timePolicy.rules.some(r=>r.actor==="student"&&r.stage==="submission")?"依規則；尚未換算日期":"學生／所屬單位收件時間另查"):deadlineText(item);
  const row=el("tr");[item.title,startCell,endCell,(item.result.certainty==="expected"?"預定 ":"")+resultText(item),item.milestones.map(m=>m.label+" "+dateText(m.value)).join("；")||"—"].forEach(text=>row.append(el("td","",text)));
  const rules=el("td");renderTimePolicy(rules,item);row.append(rules);body.append(row);
  if(item.timeline){const detailRow=el("tr"),cell=el("td");cell.colSpan=6;timelineSummary(cell,item);detailRow.append(cell);body.append(detailRow);}
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
function renderCompareCard(col, item) {
 const raw = rawById.get(item.id);
 col.append(el("div", "category", (labels.category[item.category] || item.category) + " · " + item.cycle));
 col.append(el("h3", "", item.title));
 radarSummary(col, item);
 const pills = el("div", "pills");
 itemTags(item).forEach(tag => pills.append(el("span", "pill", tag)));
 col.append(pills);

 const secEligibility = el("div", "compare-section");
 secEligibility.append(el("h4", "", "📌 申請資格與對象"));
 const degText = (item.degrees || []).map(x => labels.degree[x] || x).join("／") || "依主辦公告";
 secEligibility.append(el("p", "small", "學位身分：" + degText));
 if (raw?.eligibility?.year_limit) {
  const y = raw.eligibility.year_limit;
  secEligibility.append(el("p", "small", "年級限制：" + (item.year === "range" ? y.min + "–" + y.max + "年級" : item.year === "unlimited" ? "不限年級" : "依辦法核對")));
 }
 col.append(secEligibility);

 const secBenefit = el("div", "compare-section");
 secBenefit.append(el("h4", "", "💰 獎助給付與金額"));
 secBenefit.append(el("p", "small", item.benefit || "依官方公告核定"));
 col.append(secBenefit);

 const secCompat = el("div", "compare-section");
 secCompat.append(el("h4", "", "⚖️ 兼領與相容性限制"));
 const compatText = raw?.compatibility?.note || (item.program?.compatibility) || (item.compatibility === "allowed" ? "原則可兼領（仍須核對他方規定）" : item.compatibility === "prohibited" ? "明示不得兼領" : "兼領規定待核對");
 secCompat.append(el("p", "small", compatText));
 col.append(secCompat);

 const secTiming = el("div", "compare-section");
 secTiming.append(el("h4", "", "📅 申請時程與期限"));
 secTiming.append(el("p", "small", "學生截止：" + deadlineText(item)));
 secTiming.append(el("p", "small", "申請開始：" + startLabel(item)));
 secTiming.append(el("p", "small", "結果公告：" + resultText(item)));
 col.append(secTiming);

 const secRef = el("div", "compare-section");
 secRef.append(el("h4", "", "🔗 官方來源與依據"));
 if (item.url) {
  const link = el("a", "source-link", "查看主辦官方網頁 ↗");
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  secRef.append(link);
 } else {
  secRef.append(el("span", "quiet tiny", "官方連結載於條文備查台帳"));
 }
 col.append(secRef);
}

function renderComparisonView(content, itemA, itemB) {
 const wrap = el("div", "compare-wrap");
 const notice = el("div", "compare-notice", "💡 雙方案並排比對：兼領條款需雙方機關同時核准，請分別確認彼此之限制條款與年級限制。");
 wrap.append(notice);
 const grid = el("div", "compare-grid");
 const colA = el("div", "compare-col");
 colA.append(el("span", "compare-badge primary", "主檢視方案 A"));
 renderCompareCard(colA, itemA);
 const colB = el("div", "compare-col");
 colB.append(el("span", "compare-badge target", "比對方案 B"));
 renderCompareCard(colB, itemB);
 grid.append(colA, colB);
 wrap.append(grid);
 content.append(wrap);
}

function drawDetail() {
 const select=byId("detail-option");
 if(!select) return;
 select.replaceChildren();

 const currentAll = currentItems();
 let candidates = detailScope === "all" ? currentAll : sharedItems;
 if (detailSearchQuery) {
  candidates = candidates.filter(item => itemMatchesQuery(item, detailSearchQuery));
 }
 if (activeDetail[mode] && !candidates.some(item => item.id === activeDetail[mode])) {
  const currentTarget = currentAll.find(item => item.id === activeDetail[mode]);
  if (currentTarget) candidates = [currentTarget, ...candidates];
 }

 candidates.forEach(item => {
  const option = el("option", "", item.title);
  option.value = item.id;
  select.append(option);
 });

 if (!candidates.some(item => item.id === activeDetail[mode])) {
  activeDetail[mode] = candidates[0]?.id || null;
 }
 select.value = activeDetail[mode] || "";
 const index = candidates.findIndex(item => item.id === activeDetail[mode]);
 if (byId("detail-previous")) byId("detail-previous").disabled = index <= 0;
 if (byId("detail-next")) byId("detail-next").disabled = index < 0 || index >= candidates.length - 1;

 if (byId("detail-shared-count")) byId("detail-shared-count").textContent = sharedItems.length;
 if (byId("detail-all-count")) byId("detail-all-count").textContent = currentAll.length;

 const compareSelect = byId("detail-compare-select");
 if (compareSelect) {
  compareSelect.replaceChildren();
  const defaultOpt = el("option", "", "➕ 選擇第二個方案進行並排比對...");
  defaultOpt.value = "";
  compareSelect.append(defaultOpt);
  currentAll.filter(x => x.id !== activeDetail[mode]).forEach(other => {
   const opt = el("option", "", other.title);
   opt.value = other.id;
   compareSelect.append(opt);
  });
  compareSelect.value = activeCompareId || "";
 }
 if (byId("clear-compare-btn")) {
  byId("clear-compare-btn").hidden = !activeCompareId;
 }

 const content = byId("detail-content");
 if (!content) return;
 content.replaceChildren();

 const item = candidates[index] || currentAll.find(x => x.id === activeDetail[mode]);
 if (!item) return;

 const compareItem = activeCompareId ? currentAll.find(x => x.id === activeCompareId) : null;
 if (compareItem) {
  renderComparisonView(content, item, compareItem);
  return;
 }
 const raw=rawById.get(item.id), top=el("div","panel");
 top.append(el("div","category",labels.category[item.category]+" · "+item.cycle),el("h3","detail-title",item.title));
 if(raw)radarSummary(top,item);
 else {const axes=el("div","axes");axes.append(axis("資格："+(item.synthetic?"合成示範／未比對":"待補資料／人工核對"),"warn"),axis("受理："+item.application));top.append(axes,radarLinks(item));}
 const tags=el("div","pills");itemTags(item).forEach(tag=>tags.append(el("span","pill",tag)));top.append(tags);
 top.append(el("p","small",raw?"資訊雷達摘要；請依來源當期公告確認。來源觀察："+(item.sourceChecked||"未記錄"):item.note));content.append(top);
 if(raw){
  const details=el("section","panel detail-section");details.append(el("h3","","申請重點"));
  const year=raw.eligibility.year_limit;
  radarFact(details,"年級",item.year==="range"?year.min+"–"+year.max+"年級；基準日 "+dateText(year.assessed_at):item.year==="unlimited"?"來源明示不限年級":null,item);
  radarFact(details,"學校／學院",[raw.institution_scope?.school==="NTU"?"國立臺灣大學":null,raw.institution_scope?.college,raw.institution_scope?.department].filter(Boolean).join("／")||null,item);
  for(const [role,label] of Object.entries({funder:"資助單位",announcer:"公告單位",receiver:"收件／轉送"}))if(item.organizations?.[role])radarFact(details,label,item.organizations[role],item);
  if(item.sourceBasis)radarFact(details,"方案來源分類依據",item.sourceBasis,item);
  radarFact(details,"給付",item.benefit,item);
  radarFact(details,"兼領",item.compatibility==="unknown"?null:raw.compatibility.note,item);
  radarFact(details,"申請方式",{paper:"紙本申請",electronic:"電子申請",hybrid:"紙本與電子程序，請核對各階段",automatic:"來源明示免另行申請"}[item.method?.mode],item);
  radarFact(details,"紙本遞交",{required:"須遞交紙本",not_required:"免遞交紙本"}[item.method?.paper_delivery],item);
  radarFact(details,"結果公告",resultText(item),item);
  content.append(details);return;
 }
 const columns=el("div","two-col"), left=el("div"), right=el("aside");
  const startDetailText="申請開始："+startLabel(item)+(item.start.certainty==="inferred"?"（依官方公告日推定）":"")+(!item.start.value&&item.end.value&&!item.personal&&!isNA(item,"application_start")?"（官方起日待確認，甘特圖提供截止前 30 天準備提醒帶）":"")+"；"+item.start.note;
  const timing=factSection("申請與結果時程",[
   startDetailText,
   "學生截止："+deadlineText(item)+"；"+item.end.note,
   (item.result.certainty==="expected"?"預定":"")+"結果："+resultText(item)+"；"+item.result.note
  ]);left.append(timing);
 if(item.program) {
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

 const pickSummary = byId("timeline-pick-summary");
 if (pickSummary) {
  pickSummary.textContent = "已收藏 " + picked[mode].size + " 項專屬方案" + (personalConferences.size ? " ＋ " + personalConferences.size + " 場研討會" : "");
 }

 const cards=byId("plan-options");cards.replaceChildren();
 let totalTasks = 0, completedTasks = 0;
 sharedItems.forEach(item=>{
  const card=el("article","card"), button=el("button","plan-title",item.title);button.type="button";button.addEventListener("click",()=>openSharedDetail(item));card.append(button);
  radarSummary(card,item);
  radarFact(card,"結果公告",resultText(item),item);
  card.append(el("p","tiny quiet",item.synthetic?"合成資料，僅供規劃示範。":"來源摘要；未明欄位請直接核對原文。"));
  const tasks=el("div","plan-tasks");
  const taskList = isNA(item,"student_deadline")?["核對使用條件","確認開通／領取程序"]:["核對申請資格","確認學生收件時間","整理申請文件"];
  taskList.forEach((text,index)=>{
   totalTasks++;
   const key=item.id+":"+index,label=el("label","task-item"),input=el("input");input.type="checkbox";input.checked=completed[mode].has(key);input.setAttribute("aria-label",item.title+"："+text);
   if (input.checked) completedTasks++;
   input.addEventListener("change",()=>{
    if(input.checked) completed[mode].add(key);else completed[mode].delete(key);
    updatePlanProgress();
   });
   label.append(input,el("span","",text));tasks.append(label);
  });card.append(tasks);cards.append(card);
 });

 function updatePlanProgress() {
  const done = Array.from(completed[mode]).length;
  const prog = byId("plan-progress");
  if (prog) prog.textContent = "已準備 " + done + " / " + totalTasks + " 項待辦";
 }
 updatePlanProgress();

 if(!byId("timeline").hidden && sharedItems.length) requestAnimationFrame(()=>centerToday(range,"personal-gantt-grid"));
}
function renderWorkspace() {
 const items=allItems(),filtered=partitionItems(currentItems(),state).all,selected=picked[mode];
 sharedItems=workspaceItems(items,filtered,selected);
 const hiddenCount=sharedItems.filter(item=>!filtered.some(found=>found.id===item.id)).length;
 const basis=selected.size?"第一頁已勾選的 "+sharedItems.length+" 項":"第一頁目前篩選的 "+sharedItems.length+" 項（尚未勾選）";
 const text=(mode==="demo"?"合成資料":"來源草稿")+(personalConferences.size?"＋本次個人規劃":"")+" · "+basis+(hiddenCount?"；其中 "+hiddenCount+" 項不在目前篩選結果":"");
 for(const id of ["detail-context","timeline-context"]){byId(id).textContent=text;byId(id).classList.toggle("synthetic-note",mode==="demo");}
 byId("selection-count").textContent="已勾選 "+selected.size+" 項；第二、三頁使用 "+sharedItems.length+" 項"+(selected.size?"已選內容":"篩選結果");
 byId("picked-count").textContent=selected.size+" 項";
 byId("select-filtered").disabled=!filtered.length;byId("clear-selection").disabled=!selected.size;
 document.querySelectorAll("[data-pick-id]").forEach(input=>{input.checked=selected.has(input.dataset.pickId);});
 document.querySelectorAll("[data-open-detail]").forEach(button=>{button.textContent=selected.has(button.dataset.openDetail)?"查看詳情":"勾選並看詳情";});
 for(const name of ["detail","timeline"]){byId(name+"-empty").hidden=!!sharedItems.length;byId(name+"-workspace").hidden=!sharedItems.length;}
 drawDetail();drawPlan();
updateUrlState(false);
}
function render() {
 const items=currentItems();
 const partition=partitionItems(items,state),found=partition.all, range=domain(found,today,rangeMode,offset);
 partition.active=Object.entries(state).some(([key,value])=>key!=="includeUnknown"&&value!=="all"&&Boolean(value));
 if(lastRange && rangeMode==="fit" && (lastRange.start!==range.start || lastRange.end!==range.end)) centerPending=true;
 lastRange=range;
 byId("result-count").textContent=partition.active?"符合已知篩選 "+partition.matched.length+" 項；可能相關／待確認 "+partition.possible.length+" 項（共 "+items.length+" 項）":items.length+" 項來源摘要（"+new Set(items.map(x=>x.programKey||x.id)).size+" 組方案）";
 byId("mode-note").textContent=mode==="demo"
  ? "合成示範模式：日期與標籤僅供介面體驗，非正式公告。"
  : "獎助雷達來源摘要；未明資訊請至來源確認。文件檢視保留各年度，方案彙整不混合不同文件的欄位。";
 byId("mode-note").classList.toggle("synthetic-note",mode==="demo");
 if(personalConferences.size) byId("mode-note").textContent+=" 另含本次研討會規劃"+personalConferences.size+"項，為自填／試算待核，非合成方案。";
 byId("chart-range").textContent=iso(range.start).replaceAll("-","/")+" — "+iso(range.end).replaceAll("-","/")+" · 臺北時間";
 byId("return-today").title="今天 "+today.replaceAll("-","/");
 byId("return-today").setAttribute("aria-label","回到今天，"+today.replaceAll("-","/"));
 byId("outside-today").hidden=!(dayNumber(today)<range.start || dayNumber(today)>range.end);
 byId("empty-results").hidden=found.length>0;
 byId("gantt-view").hidden=view!=="gantt" || !found.length;
 byId("results-panel").classList.toggle("has-gantt",view==="gantt"&&found.length>0);
 byId("list-view").hidden=view!=="list" || !found.length;
 byId("dates-table").hidden=!found.length;
 selectedButtons("#mode-switch","mode",mode);selectedButtons("#view-switch","view",view);
 selectedButtons("#persona-bar","persona",activePersona(state));
 drawCards(found,partition);drawGantt(found,range);drawTable(found);
 renderWorkspace();
 if(centerPending && view==="gantt" && found.length && !byId("search").hidden){const value=rangeMode==="fit"?timelineFocusValue(found):today;requestAnimationFrame(()=>centerToday(range,"gantt-grid",value));centerPending=false;}
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
byId("select-filtered").addEventListener("click",()=>{partitionItems(currentItems(),state).all.forEach(item=>picked[mode].add(item.id));renderWorkspace();});
byId("document-mode").addEventListener("change",()=>{documentMode=byId("document-mode").value;render();});
function timelineFocusValue(items){
 const item=items.find(i=>i.timeline&&timelineDates(i).length)||items.find(i=>i.start.value||i.end.value||i.milestones.some(m=>m.value));
 return item?.start.value||item?.timeline?.baselines[0]?.start||item?.timeline?.events[0]?.value||item?.end.value||item?.milestones.find(m=>m.value)?.value||today;
}
function focusTimeline(){
 rangeMode="fit";offset=0;byId("range-mode").value="fit";view="gantt";centerPending=true;render();
}
if(byId("timeline-controls")){
 byId("timeline-year-control").hidden=!chainData;
 byId("timeline-baselines-control").hidden=!chainData;
 if(chainData){
  for(const year of chainData.years){const option=el("option","",year+"年");option.value=year;byId("timeline-year").append(option);}
  byId("timeline-year").addEventListener("change",()=>{timelineYear=Number(byId("timeline-year").value);focusTimeline();});
  byId("timeline-baselines").addEventListener("change",()=>{showBaselines=byId("timeline-baselines").checked;render();});
 }
}
byId("clear-selection").addEventListener("click",()=>{picked[mode].clear();renderWorkspace();});
byId("detail-option").addEventListener("change",event=>{activeDetail[mode]=event.target.value;drawDetail();});
function moveDetail(amount){const index=sharedItems.findIndex(item=>item.id===activeDetail[mode]);const next=sharedItems[index+amount];if(next){activeDetail[mode]=next.id;drawDetail();}}
byId("detail-previous").addEventListener("click",()=>moveDetail(-1));
byId("detail-next").addEventListener("click",()=>moveDetail(1));
byId("personal-range-mode").addEventListener("change",event=>{personalRangeMode=event.target.value;drawPlan();});
byId("personal-return-today").addEventListener("click",()=>{personalRangeMode="recent";byId("personal-range-mode").value="recent";drawPlan();});
byId("mode-switch").addEventListener("click",event=>{const button=event.target.closest("[data-mode]");if(button){mode=button.dataset.mode;inspectedId=null;centerPending=true;byId("schedule-inspect").hidden=true;render();}});
byId("view-switch").addEventListener("click",event=>{const button=event.target.closest("[data-view]");if(button){view=button.dataset.view;centerPending=true;render();}});
byId("range-mode").addEventListener("change",event=>{if(event.target.value==="fit"){focusTimeline();return;}rangeMode=event.target.value;offset=0;centerPending=true;render();});
byId("previous-range").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset-=30;render();});
byId("next-range").addEventListener("click",()=>{rangeMode="recent";byId("range-mode").value="recent";offset+=30;render();});
byId("return-today").addEventListener("click",()=>{const year=Number(today.slice(0,4));if(chainData?.years.includes(year)){timelineYear=year;byId("timeline-year").value=year;}rangeMode="recent";byId("range-mode").value="recent";offset=0;centerPending=true;render();});
function refreshToday(){const value=taipeiToday();if(value!==today){today=value;render();renderConferencePlan();}}
document.addEventListener("visibilitychange",()=>{if(!document.hidden) refreshToday();});
window.addEventListener("focus",refreshToday);
window.addEventListener("resize",()=>{updateNavHeight();if(lastRange && view==="gantt" && !byId("search").hidden){const value=rangeMode==="fit"?timelineFocusValue(partitionItems(currentItems(),state).all):today;requestAnimationFrame(()=>centerToday(lastRange,"gantt-grid",value));}if(lastPersonalRange && !byId("timeline").hidden) requestAnimationFrame(()=>centerToday(lastPersonalRange,"personal-gantt-grid"));});
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
 if(!["overview","pay","standards","grievance"].includes(nextView)) nextView="overview";
 rightsView=nextView;
 selectedButtons("#rights-view-switch","rightsView",rightsView);
 document.querySelectorAll("[data-rights-section]").forEach(section=>{section.hidden=section.dataset.rightsSection!==rightsView;});
}
if(byId("rights-view-switch")){
 byId("rights-view-switch").addEventListener("click",event=>{
  const button=event.target.closest("[data-rights-view]");
  if(button) setRightsView(button.dataset.rightsView);
 });
}
if(byId("jump-to-grievance")){
 byId("jump-to-grievance").addEventListener("click",()=>{
  scrollToInternalTarget("subordination-wizard");
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
// Bind new Toolbar & Timeline Events
if(byId("copy-share-link")){
 byId("copy-share-link").addEventListener("click",()=>{
  updateUrlState(false);
  const url=window.location.href;
  const showToast=()=>{
   const toast=byId("share-toast");
   if(toast){toast.hidden=false;setTimeout(()=>{toast.hidden=true;},2500);}
  };
  if(navigator.clipboard&&navigator.clipboard.writeText){
   navigator.clipboard.writeText(url).then(showToast).catch(showToast);
  }else{showToast();}
 });
}
if(byId("detail-scope-switch")){
 byId("detail-scope-switch").addEventListener("click",event=>{
  const btn=event.target.closest("[data-scope]");
  if(!btn) return;
  detailScope=btn.dataset.scope;
  selectedButtons("#detail-scope-switch","scope",detailScope);
  drawDetail();
 });
}
if(byId("detail-search-input")){
 byId("detail-search-input").addEventListener("input",event=>{
  detailSearchQuery=event.target.value.trim();
  drawDetail();
 });
}
if(byId("detail-compare-select")){
 byId("detail-compare-select").addEventListener("change",event=>{
  activeCompareId=event.target.value||null;
  updateUrlState(false);
  drawDetail();
 });
}
if(byId("clear-compare-btn")){
 byId("clear-compare-btn").addEventListener("click",()=>{
  activeCompareId=null;
  updateUrlState(false);
  drawDetail();
 });
}
const pickAllFiltered=()=>{
 const filtered=partitionItems(currentItems(),state).all;
 filtered.forEach(item=>picked[mode].add(item.id));
 renderWorkspace();
 updateUrlState(false);
};
if(byId("timeline-pick-all-filtered")) byId("timeline-pick-all-filtered").addEventListener("click",pickAllFiltered);
if(byId("timeline-empty-pick-all")) byId("timeline-empty-pick-all").addEventListener("click",pickAllFiltered);

window.addEventListener("popstate",()=>{
 const p=parseUrlParams(window.location.search,window.location.hash);
 if(p.tab&&p.tab!==activePanelId) activatePanel(p.tab,false,false);
 if(p.id) activeDetail[mode]=p.id;
 if(p.compare!==undefined) activeCompareId=p.compare;
 if(p.query!==undefined){
  state.query=p.query;
  const sq=byId("search-query");if(sq)sq.value=state.query;
 }
 if(p.category) state.category=p.category;
 if(p.degree) state.degree=p.degree;
 render();
});

// Read and apply URL parameters on initial startup
const urlParams=parseUrlParams(window.location.search,window.location.hash);
if(urlParams.mode) mode=urlParams.mode;
if(urlParams.view) view=urlParams.view;
if(urlParams.query!==undefined){
 state.query=urlParams.query;
 const sq=byId("search-query");if(sq)sq.value=state.query;
}
if(urlParams.category) state.category=urlParams.category;
if(urlParams.degree) state.degree=urlParams.degree;
if(urlParams.id){
 activeDetail[mode]=urlParams.id;
 if(rawById.has(urlParams.id)||urlParams.id.startsWith("ntu-")||urlParams.id.startsWith("nstc-")){
  mode="draft";
 }
}
if(urlParams.compare) activeCompareId=urlParams.compare;
if(urlParams.picks&&urlParams.picks.length){
 urlParams.picks.forEach(id=>picked[mode].add(id));
}

setRightsView(rightsView);
const initialTarget=urlParams.tab||location.hash.slice(1);
if(["search","detail","timeline","rights"].includes(initialTarget)) activatePanel(initialTarget,false,false);
else if(!scrollToInternalTarget(initialTarget)) activatePanel("search",false,false);
render();
}());
