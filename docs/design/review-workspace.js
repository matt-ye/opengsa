/* Local review intent only. All publication checks run again in the CLI. */
(function(){
"use strict";
const data=JSON.parse(document.getElementById("review-data").textContent);
const byId=id=>document.getElementById(id);
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const fields={title:"名稱",cycle:"年度／梯次",category:"分類",resource_kind:"資源類型",scope:"適用範圍",institution_scope:"學校／學院／系所限制",participants:"申請／受益角色",organizations:"相關單位",benefit:"給付",eligibility:"資格",compatibility:"兼領",hardship:"清寒限制",application_method:"申請途徑",expense_period:"可認列支出期間",start:"申請起日",steps:"分層程序",result:"結果日期",field_applicability:"不適用依據",policy_version:"法規版本",evidence_status:"證據狀態"};
const UNKNOWN_LABEL="不明，請見來源";
const readable={mode:"類型",min:"最低",max:"最高",assessed_at:"採認基準日",degrees:"學位",institution:"機構",identity:"對象",year_limit:"年級",candidate:"候選人資格",text:"說明",nationality:"國籍",employment_status:"在職限制",other_conditions:"其他條件",negated_conditions:"排除條件",mode_note:"說明",kind:"類型",value:"日期／值",items:"給付項目",amount_min:"金額下限",amount_max:"金額上限",currency:"幣別",unit:"給付週期",branch_or_tier:"適用身分／級距",duration_months_min:"最短月數",duration_months_max:"最長月數",basis:"給付基準",school:"學校",college:"學院",department:"系所",label:"說明",note:"補充",status:"狀態",reason:"原因",deadline:"期限",actor:"角色",action:"程序",funder:"資助",announcer:"公告",receiver:"收件",applicant:"申請人",beneficiary:"受益者",awardee:"受獎者",payee:"受款者",paper_delivery:"紙本遞交",handwritten_signature:"親簽",deadline_basis:"收件判準",electronic_channels:"電子管道",paper_channels:"紙本管道",summary:"摘要",required:"必要／限定",not_required:"非必要",not_applicable:"不適用（需核對依據）",conditional:"有條件",allowed:"允許（已查範圍）",prohibited:"禁止",range:"範圍",unlimited:"來源明示不限",phd:"博士",master:"碩士",student:"學生",per_month:"每月",per_year:"每年",lump_sum:"一次給付",TWD:"新臺幣",paper:"紙本",electronic:"電子",hybrid:"紙本與電子",automatic:"免另行申請",received:"送達",postmark:"郵戳",online_submission:"線上送出"};
Object.assign(readable,{claim_kind:"資訊類型",eligibility_clause:"資格段落摘要",program_descriptor:"制度對象線索"});
function valueCell(value,row){
 const td=el("td");
 function render(value,parent){
  if(value===undefined||value===null||value==="unknown"||(Array.isArray(value)&&!value.length)){
   const link=el("a");const icon=el("span","⚠ ");icon.setAttribute("style","color:#966300");icon.setAttribute("aria-hidden","true");link.append(icon,el("span",UNKNOWN_LABEL+" ↗"));if(row.source.url.startsWith("https://")){link.href=row.source.url;link.target="_blank";link.rel="noopener noreferrer";}parent.append(link);return;
  }
  if(typeof value!=="object"){parent.append(el("span",readable[value]||String(value)));return;}
  const list=el("ul");
  for(const [key,child] of Object.entries(value)){
   if(["refs","source_block_sha256","excerpt_sha256","timezone"].includes(key))continue;
   const line=el("li");if(!Array.isArray(value))line.append(el("strong",(readable[key]||key)+"："));render(child,line);list.append(line);
  }
  if(list.children.length)parent.append(list);else render(null,parent);
 }
 render(value,td);return td;
}
const gapNames={"ai_tools:personal_purchase_or_completion_date":"學生的購買日／條件完成日尚未提供","ai_tools:budget_exhaustion_status":"目前是否額滿或經費用罄尚未確認","ai_tools:age_reference_date":"年齡採認基準與出生日期區間須核對",
 "schedule.application_start":"申請起日未確認","schedule.steps/0/deadline":"學生／院系收件截止日未確認","schedule.result_date":"結果公告日期未確認","hardship":"是否清寒限定待核","compatibility":"兼領條件待核","benefit.unit_and_payee":"金額的給付單位／對象未辨明","cycle_year_unknown":"文件適用年度未辨明","missing_structured_benefit_items":"給付尚未完整萃取，需要修正解析","eligibility.identity_not_extracted":"申請／受益身分未完整萃取，需要修正解析","policy_version.full_attachment_robots_restricted":"完整辦法附件受robots限制，須人工核對","official_holiday_calendar":"例假日順延仍需官方行事曆","department_internal_lead_time":"院系是否提前收件待核","conference_start_event_date":"需提供個人會議日期才能試算（不是官方固定截止日）","cross_agency_compatibility":"跨補助方案兼領條件待核"};
const statusNames={passed_automated_checks:"自動檢核通過（仍待人工覆核）",passed_with_gaps:"檢核通過但有缺漏",needs_context:"本次未取得完整來源脈絡",failed_automated_checks:"檢核失敗",conflict_detected:"有待解衝突",fresh_semantic_revision_matched:"已重新核對，來源與準備版本相符",offline_context_not_refreshed:"離線檢視，尚未重新核對來源版本",source_revision_changed_requires_rescan:"來源內容已變更，須重掃重審",source_preparation_changed_requires_rescan:"來源準備版本已變更，須重掃重審"};
const displayStatus=value=>statusNames[value]||value;
const canPropose=row=>!row.gaps.source.length&&!(row.verification.errors||[]).length&&!["failed_automated_checks","conflict_detected"].includes(row.verification.status)&&["fresh_semantic_revision_matched","offline_context_not_refreshed"].includes(row.context_status);
const controls=[];
const date=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
byId("review-date").value=date;
byId("run-info").textContent="快照 "+data.as_of+" · "+data.rows.length+"筆文件候選／"+Object.keys(data.document_groups||{}).length+"組方案 · 本次工作台來源GET "+data.manifest.http_requests+"次 · 模型呼叫0次 · 未發布";
byId("review-counts").textContent="本批 "+data.rows.length+" 份文件可查看雷達摘要；有未明欄位 "+data.rows.filter(r=>r.gaps.source.length).length+" 筆；可提出完整資料核准意向 "+data.rows.filter(canPropose).length+" 筆。完整意向數不限制雷達摘要顯示。";
const articles=[];
for(const [program,ids] of Object.entries(data.document_groups||{})){
 const li=el("li",program+"：");
 for(const id of ids){const row=data.rows.find(r=>r.candidate_id===id);if(!row)continue;const a=el("a",row.title);a.href="#"+id;a.addEventListener("click",()=>{byId("review-filter").value="all";filterReview();});li.append(a,document.createTextNode("； "));}
 byId("document-groups").append(li);
}
for(const row of data.rows){
 const article=el("article");article.className="card";article.id=row.candidate_id;
 article.append(el("h2",row.title));
 const link=el("a","核對官方來源 ↗");
 if(row.source.url.startsWith("https://")){link.href=row.source.url;link.target="_blank";link.rel="noopener noreferrer";}
 article.append(link,el("p","本次來源狀態："+displayStatus(row.context_status)),el("p","上次檢核："+displayStatus(row.last_verification)+"；本次檢核："+displayStatus(row.verification.status)));
 const groups=el("div");groups.className="columns";
 for(const [key,title] of [["source","來源缺漏（影響核准）"],["personal","個人資料未填（影響個人判斷）"],["operational","受理／經費狀態未知"]]){
  const section=el("section");section.append(el("h3",title));const list=el("ul");
  for(const item of row.gaps[key])list.append(el("li",gapNames[item]||item));
  if(!row.gaps[key].length)list.append(el("li","未記錄此類缺漏；仍須核對原文"));
  section.append(list);groups.append(section);
 }
 article.append(groups);
 const errors=row.verification.errors||[];
 if(errors.length)article.append(el("p","檢核錯誤："+errors.join("；")));
 const table=el("table"),head=el("thead"),hr=el("tr");table.append(el("caption","逐欄比較；淡黃色表示內容不同，完整結構可展開核對"));
 for(const label of ["欄位","既有資料","本次候選"])hr.append(el("th",label));head.append(hr);table.append(head);
 const body=el("tbody");
 for(const [key,title] of Object.entries(fields)){
  const tr=el("tr"),th=el("th",title);th.scope="row";tr.append(th);
  const old=row.before?.[key],value=row.after[key];
  for(const v of [old,value])tr.append(valueCell(v,row));
  if(JSON.stringify(old)!==JSON.stringify(value))tr.className="changed";body.append(tr);
 }
 table.append(body);article.append(table);
 const details=el("details");details.append(el("summary","短證據、來源定位與內容版本"));
 details.append(el("p","候選內容 SHA-256："),el("code",row.fingerprint),el("p","來源 revision："),el("code",row.source.revision_id));
 for(const evidence of row.evidence){const block=el("div");block.className="evidence";block.append(el("strong",evidence.field_path),el("p",evidence.excerpt||"僅保留雜湊／定位，請回正式來源核對"),el("code",evidence.locator+" · "+evidence.source_block_sha256));details.append(block);}
 article.append(details);
 if(row.questions.length){const q=el("ul");for(const item of row.questions)q.append(el("li",item));article.append(el("h3","待查事項"),q);}
 const label=el("label","本筆處置"),select=el("select");select.setAttribute("aria-label",row.title+"處置");
 const canProposeApproval=canPropose(row);
 for(const [value,text] of [["","尚未處置"],["noted","待補資料"],["dismissed","退回／不採用"],["applied","核准意向（仍須重新核驗來源）"]]){
  const option=el("option",text);option.value=value;if(value==="applied"&&!canProposeApproval)option.disabled=true;select.append(option);
 }
 label.append(select);article.append(label);
 if(!canProposeApproval)article.append(el("p","本筆來源缺漏、版本異動／受阻或檢核問題尚未解除，目前不能提出核准意向。"));
 const reasonLabel=el("label","處置理由（必填）"),reason=el("textarea");reason.setAttribute("aria-label",row.title+"處置理由");reasonLabel.append(reason);article.append(reasonLabel);
 controls.push({row,select,reason});articles.push({row,article});byId("candidates").append(article);
}
function filterReview(){
 const mode=byId("review-filter").value;let count=0;
 for(const {row,article} of articles){
  const exception=(row.verification.errors||[]).length>0||row.verification.status==="conflict_detected"||!["fresh_semantic_revision_matched","offline_context_not_refreshed"].includes(row.context_status);
  const show=mode==="all"||(mode==="exceptions"&&exception)||(mode==="ready"&&canPropose(row))||(mode==="gaps"&&row.gaps.source.length>0)||(mode==="stale"&&row.context_status!=="fresh_semantic_revision_matched");
  article.hidden=!show;if(show)count++;
 }
 byId("review-filter-count").textContent="顯示 "+count+"／"+articles.length+" 筆；切換篩選保留已填處置，下載包含所有已處置項目。";
}
byId("review-filter").addEventListener("change",filterReview);filterReview();
byId("download-decisions").addEventListener("click",()=>{
 const reviewer=byId("reviewer").value.trim(),reviewed_on=byId("review-date").value;
 const selected=controls.filter(c=>c.select.value);
 if(!selected.length){byId("export-status").textContent="請先選擇至少一筆處置。";return;}
 if(!reviewer||!reviewed_on||reviewed_on>date){byId("export-status").textContent="請填實際覆核者及有效、非未來日期。";return;}
 if(selected.some(c=>!c.reason.value.trim()||c.row.editor.trim().toLowerCase()===reviewer.toLowerCase())){byId("export-status").textContent="每筆須有理由，覆核者須不同於原編輯者。";return;}
 const reviews=selected.map(({row,select,reason})=>({revision_id:row.source.revision_id,source_id:row.source.source_id,
  candidate_id:row.candidate_id,candidate_sha256:row.fingerprint,action:select.value,reviewer,reviewed_on,reason:reason.value.trim()}));
 const blob=new Blob([JSON.stringify({schema_version:"1.1.0",reviews},null,2)+"\n"],{type:"application/json"});
 const url=URL.createObjectURL(blob),anchor=el("a");anchor.href=url;anchor.download="review-decisions.json";anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 byId("export-status").textContent="已下載 "+reviews.length+" 筆人工處置意向。尚未核准發布；請用 CLI --refresh --decisions 檔案路徑重新核驗並產生資料 PR 草稿。";
});
}());
