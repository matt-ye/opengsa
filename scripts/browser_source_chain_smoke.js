// Manual Chrome regression: global local examples, layered dates and historical references.
async (page) => {
 await page.setViewportSize({width:1280,height:900});
 await page.goto('http://127.0.0.1:8783/?smoke=source-chain-'+Date.now());
 await page.locator('#view-switch [data-view="gantt"]').click();
 if(await page.locator('#timeline-scope').count())throw new Error('scope dropdown still present');
 await page.locator('#range-mode').selectOption('fit');
 for(const unit of ['臺大電信所','臺大農化系','中研院政治所']){
  const rows=page.locator('#gantt-grid .gantt-row').filter({has:page.locator('.timeline-example',{hasText:unit})});
  if(!await rows.count())throw new Error('global example missing: '+unit);
  const bar=rows.locator('.gantt-bar:not(.baseline):not(.notice-window)').first();
  if(!(await bar.getAttribute('title')).includes('實際請以所屬系所為準'))throw new Error('example tooltip missing: '+unit);
 }
 const nstcId='cand-ntu-nstc-phd-115-49f19393';
 const gice=page.locator('#gantt-grid .gantt-row').filter({has:page.locator(`[data-pick-id="${nstcId}"]`)});
 if(await gice.locator('.gantt-bar:not(.baseline):not(.notice-window)').count()!==1)throw new Error('GICE actual interval missing');
 if(!(await gice.textContent()).includes('2026/07/10 17:00'))throw new Error('GICE precision missing');
 const search=page.locator('[data-filter="query"]');
 await search.fill('校長獎');
 const acId='cand-ntu-president-114-call-6d00251d';
 const ac=page.locator('#gantt-grid .gantt-row').filter({has:page.locator(`[data-pick-id="${acId}"]`)});
 if(await ac.locator('.gantt-bar:not(.baseline):not(.notice-window)').count()!==1)throw new Error('AC actual interval missing');
 if(await ac.locator('.baseline').count()!==1||await ac.locator('.process-line').count()!==1)throw new Error('AC layering missing');
 await page.locator('#range-mode').selectOption('fit');
 await ac.locator('.gantt-bar:not(.baseline)').click();
 if(!(await page.locator('#schedule-inspect').textContent()).includes('2026/07/27 17:00'))throw new Error('inspector missing exact local deadline');
 await page.locator('#schedule-inspect [data-open-detail]').click();
 if(!(await page.locator('#detail-content').textContent()).includes('臺大農化系'))throw new Error('detail scope lost');
 await page.getByRole('tab',{name:'我的時間軸',exact:true}).click();
 if(!(await page.locator('#plan-options').textContent()).includes('2026/07/27 17:00'))throw new Error('personal timeline scope lost');
 await page.getByRole('tab',{name:'找獎助',exact:true}).click();
 await page.locator('#timeline-year').selectOption('2027');
 if(await ac.locator('.gantt-bar:not(.baseline):not(.notice-window)').count()!==0)throw new Error('forecast painted as actual interval');
 const forecast=await ac.locator('.baseline').getAttribute('aria-label');
 if(!forecast.includes('低信心')||!forecast.includes('2025、2026'))throw new Error('forecast lacks sample years');
 await page.locator('#timeline-baselines').uncheck();
 if(await ac.locator('.baseline').count())throw new Error('baseline toggle ineffective');
 await page.locator('#timeline-baselines').check();
 await search.fill('人文社會科學博士候選人');
 await page.locator('#timeline-year').selectOption('2026');
 const ipsas=page.locator('#gantt-grid .gantt-row').filter({has:page.locator('[data-pick-id="cand-sinica-phd-fellowship-6165c00d"]')});
 if(!(await ipsas.textContent()).includes('2026/01/02'))throw new Error('since-publication start missing');
 await ipsas.locator('.gantt-bar:not(.baseline):not(.notice-window)').click();
 if(!(await page.locator('#schedule-inspect').textContent()).includes('公告明載即日起'))throw new Error('start basis lost');
 const sources=await page.locator('#schedule-inspect a').allTextContents();
 if(!sources.some(x=>x.includes('PDF')))throw new Error('source-chain formats missing');
 await page.setViewportSize({width:320,height:844});
 const mobile=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
 if(mobile.scroll>mobile.width+1)throw new Error('mobile overflow');
 await page.screenshot({path:'output/playwright/source-chain-mobile.png'});
 await page.setViewportSize({width:1280,height:900});
 await search.fill('校長獎');
 await page.locator('#range-mode').selectOption('fit');
 await search.fill('');
 await ac.locator('.row-title').scrollIntoViewIfNeeded();
 await page.screenshot({path:'output/playwright/source-chain-desktop.png'});
 const result={local_intervals:3,source_formats:true,global_examples:true,example_scope_shared_across_tabs:true,baseline_toggle:true,
  forecast_not_official:true,explicit_time_preserved:true,publication_basis:true,mobile,submitted_issues:0};
 await page.evaluate(value=>{document.body.dataset.chainSmokeResult=JSON.stringify(value)},result);
 return result;
}
