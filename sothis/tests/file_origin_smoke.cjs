// Exercise the packaged file-origin security model, without granting file CORS access.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assets=path.join(__dirname,'../android/app/src/main/assets');
const captures=process.env.SOTHIS_SCREENSHOTS||'/tmp/sothis-file-origin';
const snapshots=Object.fromEntries([
 ['snapshot','snapshot.json'],['party','party-data.json'],['province','province-data.json'],
 ['analytics','analytics-data.json'],['credits','photo-credits.json'],['registers','education-registers.json'],
].map(([name,file])=>[name,fs.readFileSync(path.join(assets,file),'utf8')]));

async function assertVectorPaints(page,icon,label){
 const geometry=await icon.evaluate(node=>{
  const svg=node.querySelector('svg'),shape=svg?.querySelector('path'),r=node.getBoundingClientRect(),box=shape?.getBBox();
  return {width:r.width,height:r.height,svgWidth:svg?.getBoundingClientRect().width,
   fill:shape&&getComputedStyle(shape).fill,color:getComputedStyle(node).color,
   mask:getComputedStyle(node).maskImage,pathWidth:box?.width,pathHeight:box?.height};
 });
 assert.ok(geometry.width>=16&&geometry.width<=28&&geometry.height>=16&&geometry.height<=28,label+' icon bounds');
 assert.ok(geometry.svgWidth>=16&&geometry.pathWidth>0&&geometry.pathHeight>0,label+' vector geometry');
 assert.equal(geometry.fill,geometry.color,label+' inherits currentColor');
 assert.equal(geometry.mask,'none',label+' does not depend on a file-origin CSS mask');
 // A nonempty SVG element alone missed the old bug. Compare actual painted pixels.
 await icon.evaluate(node=>node.scrollIntoView({block:'center',inline:'nearest'}));
 const clip=await icon.boundingBox();
 const visible=await page.screenshot({clip,animations:'disabled'});
 await icon.evaluate(node=>node.style.opacity='0');
 const hidden=await page.screenshot({clip,animations:'disabled'});
 await icon.evaluate(node=>node.style.removeProperty('opacity'));
 assert.equal(visible.equals(hidden),false,label+' paints visible glyph pixels');
}

(async()=>{
 fs.mkdirSync(captures,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,
  args:['--no-sandbox','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1']});
 try{
  for(const width of [320,390]){
   const context=await browser.newContext({viewport:{width,height:844},reducedMotion:'reduce'}),page=await context.newPage();
   const errors=[],iconFailures=[];
   page.on('pageerror',error=>errors.push(error.message));
   page.on('console',message=>{if(message.type()==='error'&&/CORS|ERR_FAILED/.test(message.text())&&/icons\/|\.svg/.test(message.text()))iconFailures.push(message.text());});
   page.on('requestfailed',request=>{if(request.url().startsWith('file:')&&/\/icons\/|\.svg(?:$|\?)/.test(request.url()))iconFailures.push(request.url());});
   // Native provides bundled JSON. Services intentionally fail: this checks UI delivery,
   // not live providers. A clearly marked cached article exercises the action glyphs.
   await page.addInitScript(data=>{
    window.Native={snapshot:()=>data.snapshot,partySnapshot:()=>data.party,provinceSnapshot:()=>data.province,
     analyticsSnapshot:()=>data.analytics,photoCredits:()=>data.credits,educationRegisters:()=>data.registers,
     config:()=>JSON.stringify({url:'',configured:false}),dailyCapabilities:()=>'',backgroundStatus:()=>'',
     request:id=>setTimeout(()=>window.nativeReply(id,'','Services offline for file-origin rendering test'),0)};
    localStorage.setItem('sothis-news-cache',JSON.stringify([{id:'file-origin-fixture',publisher:'RECORDED UI FIXTURE',
     title:'A public source card with a deliberately long headline that wraps inside its container',
     description:'Recorded content exercises the same saved, liked and shared action controls at narrow screen widths.',
     url:'https://www.gov.za/',published_at:'2026-10-11T08:00:00Z',reader_allowed:false}]));
   },snapshots);
   await page.goto(pathToFileURL(path.join(assets,'index.html')).href);
   await page.waitForFunction(()=>state.tab==='home'&&partyState.data&&provinceState.data&&document.querySelectorAll('.nav .dock-icon svg').length===5);
   await page.evaluate(()=>document.fonts.ready);
   assert.equal(await page.locator('.nav .dock-icon').count(),5);
   assert.equal(await page.locator('.nav .dock-icon:visible').count(),4,'Home owns inline search');
   for(const icon of await page.locator('.nav .dock-icon:visible').all())await assertVectorPaints(page,icon,'dock');
   await assertVectorPaints(page,page.locator('.header-settings .ui-icon'),'header settings');
   for(const action of await page.locator('#home-news .action-icon').all()){
    assert.ok(await action.getAttribute('aria-label'),'action has accessible name');
    const bounds=await action.boundingBox();assert.ok(bounds.width>=44&&bounds.height>=44,'action touch bounds');
    await assertVectorPaints(page,action.locator('.ui-icon'),'article action');
   }
   const clipped=await page.locator('.daily-hero .daily-tabs button').evaluateAll(buttons=>buttons.filter(button=>{
    const r=button.getBoundingClientRect(),p=button.closest('.daily-hero').getBoundingClientRect();
    return r.left<p.left||r.right>p.right||r.bottom>p.bottom;
   }).map(button=>button.textContent));
   assert.deepEqual(clipped,[],'hero actions stay inside their container at '+width);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'page width at '+width);
   await page.evaluate(()=>scrollTo(0,0));
   await page.screenshot({path:path.join(captures,'file-current-home-'+width+'.png'),animations:'disabled'});
   // This detail crop omits the fixed dock so the whole card's action row is inspectable.
   await page.locator('.nav,.dock-shade').evaluateAll(nodes=>nodes.forEach(node=>node.style.visibility='hidden'));
   await page.locator('#home-news').screenshot({path:path.join(captures,'file-current-actions-'+width+'.png'),animations:'disabled'});
   await page.locator('.nav,.dock-shade').evaluateAll(nodes=>nodes.forEach(node=>node.style.removeProperty('visibility')));

   await page.locator('.nav [data-tab=regions]').click();
   await page.waitForFunction(()=>state.tab==='regions');
   assert.equal(await page.locator('.nav [data-tab=regions]').getAttribute('aria-current'),'page');
   assert.equal(await page.evaluate(()=>window.sothisBack()),true);
   await page.waitForFunction(()=>state.tab==='home');
   await page.locator('#home-search-form button[type=submit]').click();await page.waitForFunction(()=>state.tab==='search');
   await assertVectorPaints(page,page.locator('#search-form button[type=submit] .ui-icon'),'global search');
   assert.equal(await page.locator('.search-orb').isVisible(),false,'inline search replaces dock search');
   assert.equal(await page.evaluate(()=>window.sothisBack()),true);await page.waitForFunction(()=>state.tab==='home');
   await page.locator('.nav [data-tab=profile]').click();await assertVectorPaints(page,page.locator('.search-orb .dock-icon'),'contextual dock search');await page.evaluate(()=>window.sothisBack());await page.waitForFunction(()=>state.tab==='home');
   await page.evaluate(()=>window.sothisKeyboard(true));assert.equal(await page.locator('.nav').isVisible(),false);
   await page.evaluate(()=>window.sothisKeyboard(false));assert.equal(await page.locator('.nav').isVisible(),true);
   assert.deepEqual(iconFailures,[],'no local vector CORS failures');assert.deepEqual(errors,[],'no UI errors');
   await context.close();
  }
 }finally{await browser.close();}
 console.log('File origin passed: painted dock/header/search/action vectors, currentColor, container bounds, navigation/Back and keyboard behavior at 320 and 390 px. Captures: '+captures);
})().catch(error=>{console.error(error);process.exit(1)});
