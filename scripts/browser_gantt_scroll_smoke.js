// Manual Chrome check: default view, native two-axis scrolling and sticky headings.
async (page) => {
 await page.setViewportSize({width:1280,height:900});
 await page.goto('http://127.0.0.1:8783/?smoke=sticky-gantt-'+Date.now()+'#search');
 const chart=page.locator('#gantt-view'), scroll=chart.locator('.gantt-scroll');
 if(!await chart.isVisible()||await page.locator('#view-switch [data-view="gantt"]').getAttribute('aria-pressed')!=='true')throw new Error('Gantt is not the default');
 await page.locator('#timeline-focus').click();
 await scroll.evaluate(node=>window.scrollTo(0,node.getBoundingClientRect().top+window.scrollY-200));
 const read=()=>scroll.evaluate(node=>{
  const box=node.getBoundingClientRect(),head=node.querySelector('.gantt-top').getBoundingClientRect(),corner=node.querySelector('.gantt-heading').getBoundingClientRect();
  return {top:box.top,height:box.height,headerTop:head.top,cornerLeft:corner.left,left:box.left,scrollTop:node.scrollTop,scrollLeft:node.scrollLeft,
   scrollHeight:node.scrollHeight,clientHeight:node.clientHeight,windowY:window.scrollY,navBottom:document.querySelector('.nav-wrap').getBoundingClientRect().bottom};
 });
 const before=await read();
 if(before.scrollHeight<=before.clientHeight)throw new Error('Chart has no independent vertical scroll');
 await scroll.evaluate(node=>{node.scrollTop=600;node.scrollLeft=300;});
 const after=await read();
 if(after.scrollTop<500||after.scrollLeft<200||Math.abs(after.headerTop-after.top)>2||Math.abs(after.cornerLeft-after.left)>2||after.windowY!==before.windowY)throw new Error('Sticky header/corner failed '+JSON.stringify(after));
 await page.evaluate(()=>window.scrollBy(0,80));
 const outer=await read();
 if(outer.headerTop<outer.navBottom-1)throw new Error('Page scroll hides chart heading '+JSON.stringify(outer));
 await scroll.focus();
 await scroll.press('Control+End');
 await page.waitForFunction(()=>{const node=document.querySelector('#gantt-view .gantt-scroll');return node.scrollTop>600;});
 const keyboard=await read();
 if(Math.abs(keyboard.headerTop-keyboard.top)>2)throw new Error('Keyboard scroll lost header');
 await scroll.evaluate(node=>{node.scrollTop=0;node.scrollLeft=0;});
 await page.screenshot({path:'output/playwright/gantt-sticky-desktop.png'});
 await page.locator('#view-switch [data-view="list"]').click();
 if(!await page.locator('#list-view').isVisible()||await chart.isVisible())throw new Error('List switch broken');
 await page.locator('#view-switch [data-view="gantt"]').click();
 await page.setViewportSize({width:320,height:844});
 await scroll.evaluate(node=>{node.scrollTop=500;node.scrollLeft=250;});
 const mobile=await read();
 const width=await page.evaluate(()=>({viewport:innerWidth,page:document.documentElement.scrollWidth}));
 if(Math.abs(mobile.headerTop-mobile.top)>2||Math.abs(mobile.cornerLeft-mobile.left)>2||width.page>width.viewport+1)throw new Error('Mobile scrolling failed '+JSON.stringify({mobile,width}));
 await scroll.scrollIntoViewIfNeeded();
 await page.screenshot({path:'output/playwright/gantt-sticky-mobile.png'});
 await page.setViewportSize({width:1280,height:900});
 await scroll.evaluate(node=>{node.scrollTop=0;node.scrollLeft=0;});
 await scroll.scrollIntoViewIfNeeded();
 return {default_gantt:true,vertical_scroll:true,sticky_header:true,sticky_corner:true,outer_scroll:outer,keyboard_scroll:true,list_toggle:true,mobile:width,rows:await page.locator('#gantt-grid > .gantt-row:not(.gantt-top)').count()};
}
