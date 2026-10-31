// Manual Chrome smoke test via playwright-cli run-code --filename. No issues submitted.
async (page) => {
 const summary=await page.evaluate(()=>{
  const metadata=JSON.parse(document.querySelector('#radar-data').textContent).records;
  const cards=[...document.querySelectorAll('#result-cards article.card')];
  const checks=cards.map(card=>{
   const id=card.querySelector('[data-pick-id]').dataset.pickId;
   const official=[...card.querySelectorAll('a')].find(a=>a.textContent==='官方公告 ↗');
   const report=[...card.querySelectorAll('a')].find(a=>a.textContent==='回報問題 ↗');
   const u=new URL(report.href);
   return {id,title:card.querySelector('h3').textContent,source:official.href===new URL(metadata[id].url).href,
    report:u.searchParams.get('resource_id')===id&&u.searchParams.get('source_version')===metadata[id].revision&&
     u.searchParams.get('source_url')===new URL(metadata[id].url).href&&u.searchParams.get('resource_name')===card.querySelector('h3').textContent.slice(0,120),
    unknown:[...card.querySelectorAll('a')].some(a=>a.textContent.includes('不明，請見來源')&&a.querySelector('.unknown-icon')),
    clean:!(/undefined|NaN|\[object Object\]|文件候選，待整併/.test(card.textContent)),clarity:!!card.querySelector('.clarity')};
  });
  const failed=checks.filter(c=>!c.source||!c.report||!c.unknown||!c.clean||!c.clarity);
  if(cards.length!==19||failed.length)throw new Error(JSON.stringify({count:cards.length,failed}));
  const receivers=cards.filter(c=>c.textContent.includes('收件／轉送：')).length;
  const timing=cards.filter(c=>[...c.querySelectorAll('strong')].some(s=>/^(學生|校級|學院|機構|補件)(時間規則|期限)：/.test(s.textContent))).length;
  if(receivers!==12||timing!==7)throw new Error('lost recorded facts '+JSON.stringify({receivers,timing}));
  // IDs reside in data attributes rather than visible card text.
  const ai=cards.filter(c=>c.querySelector('[data-pick-id]').dataset.pickId.includes('ai-tools'));
  if(ai.length!==2||ai.some(c=>!c.textContent.includes('地方青年訂閱費補助')))throw new Error('partial audience hidden');
  const national=cards.find(c=>c.querySelector('[data-pick-id]').dataset.pickId.includes('nstc-conference-rule'));
  if(!national.textContent.includes('機構時間規則')||!national.textContent.includes('學生截止：'))throw new Error('institution deadline confused with student');
  if(national.textContent.includes('學生先送臺大'))throw new Error('national policy inherited NTU-only receiver');
  return {count:cards.length,checks,receivers,timing};
 });
 for(const card of summary.checks){
  await page.locator(`[data-open-detail="${card.id}"]`).click();
  const heading=await page.locator('#detail-content .detail-title').textContent();
  if(heading!==card.title)throw new Error('detail mismatch '+card.id);
  const report=await page.locator('#detail-content a').filter({hasText:'回報問題 ↗'}).getAttribute('href');
  if(new URL(report).searchParams.get('resource_id')!==card.id)throw new Error('detail report mismatch '+card.id);
  await page.getByRole('tab',{name:'找獎助',exact:true}).click();
 }
 await page.getByRole('tab',{name:'我的時間軸',exact:true}).click();
 if(await page.locator('#plan-options article.card').count()!==19)throw new Error('timeline lost records');
 await page.getByRole('tab',{name:'找獎助',exact:true}).click();
 await page.locator('#document-mode').selectOption('programs');
 if(await page.locator('#result-cards article.card').count()!==13)throw new Error('grouping mismatch');
 await page.getByRole('tab',{name:'我的時間軸',exact:true}).click();
 if(await page.locator('#plan-options article.card').count()!==19)throw new Error('grouping lost selected documents');
 await page.getByRole('tab',{name:'找獎助',exact:true}).click();
 await page.locator('#document-mode').selectOption('documents');
 await page.locator('#filter-year').selectOption('unlimited');
 const yearText=await page.locator('#result-count').textContent();
 if(!yearText.includes('符合已知篩選 0 項；可能相關／待確認 17 項'))throw new Error('unknown year mixed '+yearText);
 await page.locator('#filter-unknown').uncheck();
 if(await page.locator('#result-cards article.card').count()!==0)throw new Error('strict filter includes unknown');
 await page.getByRole('button',{name:'清除條件',exact:true}).click();
 await page.locator('#filter-compatibility').selectOption('allowed');
 const compText=await page.locator('#result-count').textContent();
 if(!compText.includes('符合已知篩選 0 項；可能相關／待確認 7 項'))throw new Error('unknown compatibility mixed '+compText);
 await page.getByRole('button',{name:'清除條件',exact:true}).click();
 await page.setViewportSize({width:1280,height:900});
 await page.locator('#result-cards article.card').first().scrollIntoViewIfNeeded();
 await page.screenshot({path:'output/playwright/radar-desktop.png'});
 await page.setViewportSize({width:320,height:844});
 const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
 if(layout.scroll>layout.width+1)throw new Error('mobile overflow '+JSON.stringify(layout));
 await page.locator('#result-cards article.card').first().scrollIntoViewIfNeeded();
 await page.screenshot({path:'output/playwright/radar-mobile.png'});
 const report={records:summary.count,detail_views:19,timeline_cards:19,programs:13,receiver_summaries:summary.receivers,time_summaries:summary.timing,
  all_report_ids_and_source_versions_match:true,all_unknowns_link_to_source:true,
  year_filter:yearText,compatibility_filter:compText,mobile:layout,submitted_issues:0};
 await page.evaluate(value=>{document.body.dataset.radarSmokeResult=JSON.stringify(value)},report);
 return report;
}
