/* Local review intent only. All publication checks run again in the CLI. */
(function(){
"use strict";
const data=JSON.parse(document.getElementById("review-data").textContent);
const byId=id=>document.getElementById(id);
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const fields={title:"名稱",cycle:"年度／梯次",category:"分類",resource_kind:"資源類型",scope:"適用範圍",institution_scope:"學校／學院／系所限制",participants:"申請／受益角色",organizations:"相關單位",benefit:"給付",eligibility:"資格",compatibility:"兼領",hardship:"清寒限制",application_method:"申請途徑",expense_period:"可認列支出期間",start:"申請起日",steps:"分層程序",result:"結果日期",field_applicability:"不適用依據",policy_version:"法規版本",evidence_status:"證據狀態"};
function valueCell(value){
 const td=el("td");
 if(value===undefined||value===null){td.append(el("p","未記錄／尚未收錄"));return td;}
 if(typeof value==="string"){td.append(el("p",value));return td;}
 const summary=value.text||value.label||value.note||value.identity?.text||"結構化欄位，請展開逐項核對";
 td.append(el("p",summary));
 const details=el("details");details.append(el("summary","展開完整欄位"),el("pre",JSON.stringify(value,null,2)));td.append(details);return td;
}
const gapNames={"ai_tools:personal_purchase_or_completion_date":"學生的購買日／條件完成日尚未提供","ai_tools:budget_exhaustion_status":"目前是否額滿或經費用罄尚未確認","ai_tools:age_reference_date":"年齡採認基準與出生日期區間須核對"};
const controls=[];
const date=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
byId("review-date").value=date;
byId("run-info").textContent="快照 "+data.as_of+" · "+data.rows.length+"筆文件候選／"+Object.keys(data.document_groups||{}).length+"組方案 · 本次工作台來源GET "+data.manifest.http_requests+"次 · 模型呼叫0次 · 未發布";
for(const [program,ids] of Object.entries(data.document_groups||{})){
 const li=el("li",program+"：");
 for(const id of ids){const row=data.rows.find(r=>r.candidate_id===id);if(!row)continue;const a=el("a",row.title);a.href="#"+id;li.append(a,document.createTextNode("； "));}
 byId("document-groups").append(li);
}
for(const row of data.rows){
 const article=el("article");article.className="card";article.id=row.candidate_id;
 article.append(el("h2",row.title));
 const link=el("a","核對官方來源 ↗");
 if(row.source.url.startsWith("https://")){link.href=row.source.url;link.target="_blank";link.rel="noopener noreferrer";}
 article.append(link,el("p","本次來源狀態："+row.context_status),el("p","上次檢核："+row.last_verification+"；本次檢核："+row.verification.status));
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
  for(const v of [old,value])tr.append(valueCell(v));
  if(JSON.stringify(old)!==JSON.stringify(value))tr.className="changed";body.append(tr);
 }
 table.append(body);article.append(table);
 const details=el("details");details.append(el("summary","短證據、來源定位與內容版本"));
 details.append(el("p","候選內容 SHA-256："),el("code",row.fingerprint),el("p","來源 revision："),el("code",row.source.revision_id));
 for(const evidence of row.evidence){const block=el("div");block.className="evidence";block.append(el("strong",evidence.field_path),el("p",evidence.excerpt||"僅保留雜湊／定位，請回正式來源核對"),el("code",evidence.locator+" · "+evidence.source_block_sha256));details.append(block);}
 article.append(details);
 if(row.questions.length){const q=el("ul");for(const item of row.questions)q.append(el("li",item));article.append(el("h3","待查事項"),q);}
 const label=el("label","本筆處置"),select=el("select");select.setAttribute("aria-label",row.title+"處置");
 const canProposeApproval=!row.gaps.source.length&&!errors.length&&!["failed_automated_checks","conflict_detected"].includes(row.verification.status);
 for(const [value,text] of [["","尚未處置"],["noted","待補資料"],["dismissed","退回／不採用"],["applied","核准意向（仍須重新核驗來源）"]]){
  const option=el("option",text);option.value=value;if(value==="applied"&&!canProposeApproval)option.disabled=true;select.append(option);
 }
 label.append(select);article.append(label);
 if(!canProposeApproval)article.append(el("p","本筆來源缺漏或檢核錯誤尚未解除，目前不能提出核准意向。"));
 const reasonLabel=el("label","處置理由（必填）"),reason=el("textarea");reason.setAttribute("aria-label",row.title+"處置理由");reasonLabel.append(reason);article.append(reasonLabel);
 controls.push({row,select,reason});byId("candidates").append(article);
}
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
