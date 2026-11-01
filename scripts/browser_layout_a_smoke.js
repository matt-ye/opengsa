// Manual Chrome check: approved layout A with the real 19-record radar snapshot.
async page => {
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewportSize({width:1280,height:900});
 await page.goto('http://127.0.0.1:8783/?smoke=layout-a-'+Date.now());
 if(!await page.locator('#gantt-view').isVisible()||await page.locator('#gantt-grid > .gantt-row:not(.gantt-top)').count()!==19)throw new Error('Default radar changed');
 if(await page.locator('aside.filter #selection-management').count()!==1||await page.locator('#timeline-focus').count())throw new Error('Controls not consolidated');
 for(const id of ['range-mode','timeline-year','timeline-baselines','view-switch','selection-count'])if(await page.locator('#'+id).count()!==1)throw new Error('Duplicate control '+id);
 if(await page.locator('#chart-legend').getAttribute('open')!==null)throw new Error('Legend should start collapsed');
 await page.locator('#chart-legend summary').click();
 const legend=await page.locator('#chart-legend .gantt-legend').evaluate(node=>({background:getComputedStyle(node).backgroundColor,columns:getComputedStyle(node).gridTemplateColumns,items:node.children.length}));
 if(legend.items!==11||legend.background!=='rgb(255, 255, 255)')throw new Error('Legend grid incorrect');
 await page.screenshot({path:'output/playwright/layout-a-legend.png'});
 await page.locator('#chart-legend summary').click();
 await page.locator('#selection-management summary').click();
 await page.locator('#select-filtered').click();
 if(await page.locator('#picked-count').textContent()!=='19 項')throw new Error('Batch selection broken');
 await page.locator('#search-query').fill('校長獎');
 if(await page.locator('#picked-count').textContent()!=='19 項')throw new Error('Filtering lost selection');
 await page.locator('#clear-selection').click();
 if(!(await page.locator('#selection-count').textContent()).includes('2 項篩選結果'))throw new Error('Fallback selection changed');
 await page.locator('#range-mode').selectOption('fit');
 const original=await page.locator('#chart-range').textContent();
 await page.locator('#next-range').click();
 if(await page.locator('#range-mode').inputValue()!=='recent')throw new Error('Pan mode not synced');
 await page.locator('#range-mode').selectOption('fit');
 if(await page.locator('#chart-range').textContent()!==original)throw new Error('Fit failed to reset pan');
 await page.locator('#timeline-year').selectOption('2027');
 if(await page.locator('#range-mode').inputValue()!=='fit')throw new Error('Year failed to focus reference dates');
 await page.locator('#return-today').click();
 if(await page.locator('#timeline-year').inputValue()!=='2026'||await page.locator('#range-mode').inputValue()!=='recent')throw new Error('Today failed to reset year and range');
 await page.locator('#timeline-baselines').uncheck();
 if(await page.locator('#gantt-grid .baseline').count())throw new Error('Baseline toggle broken');
 await page.locator('#timeline-baselines').check();
 await page.locator('#search-query').fill('');
 await page.locator('#selection-management summary').click();
 await page.locator('#range-mode').selectOption('fit');
 await page.locator('#results-panel').scrollIntoViewIfNeeded();
 await page.screenshot({path:'output/playwright/layout-a-desktop.png'});
 const widths=[];
 for(const width of [1059,768,320]){
  await page.setViewportSize({width,height:844});
  const item=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
  if(item.scroll>item.width+1)throw new Error('Page overflow '+JSON.stringify(item));widths.push(item);
 }
 await page.locator('#chart-legend summary').click();
 await page.locator('#chart-legend').scrollIntoViewIfNeeded();
 await page.screenshot({path:'output/playwright/layout-a-mobile.png'});
 await page.locator('#chart-legend summary').click();
 // A fresh phone visit starts with qualification filters collapsed, without hiding selection management.
 await page.reload();
 if(await page.locator('#search .filter>details').getAttribute('open')!==null||!await page.locator('#selection-management summary').isVisible())throw new Error('Mobile sidebar disclosure incorrect');
 await page.setViewportSize({width:1280,height:900});
 if(errors.length)throw new Error(errors.join(';'));
 return {records:19,layout:'A',legend,sidebar_selection:true,selection_preserved:true,range_year_and_pan_synced:true,widths,mobile_filter_collapsed:true,script_errors:0};
}
