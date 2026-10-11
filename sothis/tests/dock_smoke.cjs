const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {openSearch}=require('./navigation_helpers.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,args:['--no-sandbox','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1']});
 const context=await browser.newContext({viewport:{width:360,height:800}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.SOTHIS_TEST_URL||'http://127.0.0.1:8765');
 await page.waitForFunction(()=>state.connected&&provinceState.data&&partyState.data&&state.tab==='home');
 await page.evaluate(()=>document.fonts.ready);
 assert.equal(await page.evaluate(()=>document.fonts.check('400 10px "Roboto Mono"')),true);
 for(const width of [320,360,390,412,720,1280]){
  await page.setViewportSize({width,height:844});
  for(const tab of ['home','regions','opportunities','profile','settings','search','sources','tenders','party','cases']){
   await page.evaluate(name=>tab(name),tab);
   const expected=['search','sources','tenders','opportunities','party'].includes(tab);
   assert.equal(await page.locator('.search-orb').isVisible(),!expected,tab+' search visibility');
   const state=await page.evaluate(()=>{
    const dock=document.querySelector('.nav'),b=dock.getBoundingClientRect();
    return {x:b.x,right:b.right,height:b.height,labels:[...dock.querySelectorAll('.dock-label')].filter(n=>getComputedStyle(n).display!=='none').map(n=>n.textContent),icons:[...dock.querySelectorAll('.dock-icon')].filter(n=>n.offsetWidth).map(n=>[n.offsetWidth,n.offsetHeight]),buttons:[...dock.querySelectorAll('.navinner button')].map(n=>({w:n.offsetWidth,h:n.offsetHeight,current:n.getAttribute('aria-current'),label:n.getAttribute('aria-label')}))};
   });
   assert.ok(state.x>=0&&state.right<=width);assert.equal(state.height,64);
   for(const icon of state.icons)assert.deepEqual(icon,[20,20]);
   for(const b of state.buttons){assert.ok(b.w>=44&&b.h===52);assert.ok(b.label);}
   const label={home:'HOME',regions:'REGIONS',opportunities:'JOBS',profile:'PROFILE',settings:'PROFILE'}[tab];
   assert.deepEqual(state.labels,label?[label]:[]);
   assert.equal(state.buttons.filter(b=>b.current==='page').length,label?1:0);
   assert.equal(await page.locator('.route-back,.province-back,#member-back,#party-directory-back').count(),0);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  }
 }
 // Native Back traverses a province detail and a representative without visible controls.
 await page.evaluate(()=>{provinceDirectory();tab('regions')});
 await page.locator('#region-map [data-region="Northern Cape"]').click();
 await page.locator('#province-dashboard h1').filter({hasText:'Northern Cape'}).waitFor();
 const employment=page.locator('.province-overview .analytics-card').filter({has:page.getByRole('heading',{name:'Employment',exact:true})});
 const item=await employment.evaluate(n=>shareCards.item(n));
 assert.match(item.lines.join(' '),/36\.3%/);assert.match(item.lines.join(' '),/28\.7%/);
 assert.match(item.date,/published/);assert.doesNotMatch(item.date,/^EMPLOYMENT ABSORPTION$/);
 await page.evaluate(()=>window.sothisBack());await page.locator('#region-directory').waitFor({state:'visible'});
 await page.evaluate(()=>{partyState.current=null;partyState.member=null;tab('party')});
 await page.getByRole('button',{name:'View ANC',exact:true}).click();
 await page.locator('#party-title').filter({hasText:'African National Congress'}).waitFor();
 await page.locator('#member-filter').fill('Mantashe');await page.locator('[data-member="5975"]').click();
 await page.locator('#member-body').waitFor({state:'visible'});assert.equal(await page.locator('.search-orb').isVisible(),true);
 await page.evaluate(()=>window.sothisBack());await page.locator('#party-body').waitFor({state:'visible'});
 assert.equal(await page.locator('.search-orb').isVisible(),false);
 await page.evaluate(()=>window.sothisBack());await page.locator('#party-directory').waitFor({state:'visible'});
 await openSearch(page);await page.setViewportSize({width:360,height:844});
 await page.locator('#query').focus();await page.setViewportSize({width:360,height:500});
 await page.locator('.nav').waitFor({state:'hidden'});
 await page.setViewportSize({width:360,height:844});await page.locator('.nav').waitFor({state:'visible'});
 await page.evaluate(()=>sothisKeyboard(true));assert.equal(await page.locator('.nav').isVisible(),false);
 await page.evaluate(()=>sothisKeyboard(false));await page.locator('.nav').waitFor({state:'visible'});
 await page.locator('#query').blur();await page.locator('#search-form button[type=submit]').focus();
 assert.equal(await page.locator('.nav button[aria-label=Home]').getAttribute('aria-label'),'Home');
 fs.mkdirSync('/tmp/sothis-dock',{recursive:true});
 for(const screen of ['home','regions','search']){await page.evaluate(name=>{tab(name);document.getElementById('toast').hidden=true},screen);await page.screenshot({path:'/tmp/sothis-dock/'+screen+'.png'});}
 assert.deepEqual(errors,[]);await browser.close();
 console.log('Dock passed: six widths, fixed icons, single active label, one search entry, no Back controls, native history, IME hiding, local font, and preserved employment share metrics.');
})().catch(e=>{console.error(e);process.exit(1)});
