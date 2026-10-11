const {openSearch}=require('./navigation_helpers.cjs');
// Visual asset delivery and compact dock regressions, against an isolated engine.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assets=path.join(__dirname,'../android/app/src/main/assets');
const data=JSON.parse(fs.readFileSync(path.join(assets,'party-data.json'))),anc=data.parties.find(p=>p.code==='ANC'),seed=anc.members.find(m=>m.id==='5975');
const member={...seed,...data.profiles['5975'],party_name:anc.name,roster_url:anc.source_url,captured_at:anc.captured_at,interests_register:data.interests_register,remuneration:data.remuneration_schedules.find(r=>r.role==='Minister'),status:'saved_capture'};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,args:['--no-sandbox','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1']});
 const out=process.env.SOTHIS_SCREENSHOTS||'/tmp/sothis-visual';fs.mkdirSync(out,{recursive:true});
 const ctx=await browser.newContext({viewport:{width:390,height:844}}),page=await ctx.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 // Published representative photos are optional network assets; exercise fallback deterministically.
 await page.route('https://www.parliament.gov.za/storage/app/media/MemberImages/*',route=>{
  const id=path.basename(new URL(route.request().url()).pathname,'.jpg'),photo='/tmp/sothis-portrait-'+id+'.jpg';
  return fs.existsSync(photo)?route.fulfill({body:fs.readFileSync(photo),contentType:'image/jpeg'}):route.abort();
 });
 await page.route('**/api/member',route=>route.fulfill({json:member}));
 await page.route('**/api/party',route=>route.fulfill({json:{...anc,status:'saved_roster'}}));
 await page.route('**/api/discover',route=>route.fulfill({json:{query:member.name,results:[],hit_count:0,account_count:0,statuses:[],retrieved_at:data.captured_at,coverage:'No live provider invoked in this recorded UI check.'}}));
 const base=process.env.SOTHIS_TEST_URL||'http://127.0.0.1:8765';
 await page.goto(base);await openSearch(page);await page.evaluate(()=>document.getElementById('search-scope').open=true);await page.waitForFunction(()=>state.connected);await page.evaluate(()=>document.fonts.ready);
 for(const [url,mime] of [['/nothing.css','text/css'],['/visuals.js','application/javascript'],['/images/cape-town.webp','image/webp'],['/fonts/doto.ttf','font/ttf'],['/icons/flag.svg','image/svg+xml']]){
  const r=await ctx.request.get(base+url);assert.equal(r.status(),200);assert.equal(r.headers()['content-type'].split(';')[0],mime);
 }
 for(const url of ['/images/../../engine/core.py','/images/missing.webp','/images/..%2F..%2Fengine%2Fcore.py','/fonts/OFL.txt'])assert.equal((await ctx.request.get(base+url)).status(),404);
 await page.waitForFunction(()=>[...document.querySelectorAll('#start-cards>button>img')].every(i=>i.complete&&i.naturalWidth));
 assert.equal(await page.evaluate(()=>document.fonts.check('800 30px Doto')),true);
 await page.screenshot({path:path.join(out,'home.png')});
 await page.locator('#explore-country').click();await page.waitForFunction(()=>document.querySelectorAll('#regions .region-photo').length===10);
 await page.waitForFunction(()=>[...document.querySelectorAll('#regions .region-photo')].slice(0,4).every(i=>i.complete&&i.naturalWidth));
 await page.screenshot({path:path.join(out,'regions.png')});
 await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=party]').click();await page.getByRole('button',{name:'View ANC',exact:true}).click();
 await page.locator('#member-filter').fill('Mantashe');await page.locator('[data-member="5975"]').click();
 await page.locator('#member-name').filter({hasText:member.name}).waitFor();await page.waitForFunction(()=>!document.querySelector('#member-status').textContent);
 await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,'profile.png')});
 await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=sources]').click();await page.screenshot({path:path.join(out,'tools.png')});
 for(const width of [320,360,390,412,720,1200]){
  await page.setViewportSize({width,height:844});
  for(const tab of ['home','opportunities','profile','search','party','regions','sources','cases','settings']){
   if(['party','sources','cases'].includes(tab))await page.evaluate(()=>document.querySelector('.header-explore').open=true);
   if(tab==='search')await openSearch(page);else await page.locator('[data-tab='+tab+']').click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Overflow: '+tab+' at '+width);
   const dock=await page.locator('.nav').boundingBox();assert.ok(dock.x>=0&&dock.x+dock.width<=width+1);
   for(const button of await page.locator('.nav button:visible').all()){const b=await button.boundingBox();assert.ok(b.width>=44&&b.height>=44,'Dock touch target at '+width)}
  }
 }
 const offline=await browser.newContext({viewport:{width:390,height:844}});
 await offline.addInitScript(({snapshot,data,credits})=>{window.Native={snapshot:()=>JSON.stringify(snapshot),partySnapshot:()=>JSON.stringify(data),photoCredits:()=>JSON.stringify(credits),config:()=>JSON.stringify({url:'',configured:false}),request:()=>{throw Error('Offline photo navigation should not need an engine')}}},{snapshot:JSON.parse(fs.readFileSync(path.join(assets,'snapshot.json'))),data,credits:JSON.parse(fs.readFileSync(path.join(assets,'photo-credits.json')))});
 const filePage=await offline.newPage();filePage.on('pageerror',e=>errors.push(e.message));
 await filePage.goto('file://'+path.join(assets,'index.html'));await filePage.locator('.nav [data-tab=search]').click();await filePage.evaluate(()=>document.getElementById('search-scope').open=true);await filePage.locator('#result-count').filter({hasText:/passages/}).waitFor();
 await filePage.evaluate(()=>document.fonts.ready);assert.equal(await filePage.evaluate(()=>document.fonts.check('800 30px Doto')),true,'Bundled font at file origin');
 await filePage.locator('[data-tab=regions]').click();await filePage.waitForFunction(()=>document.querySelectorAll('#regions .region-photo').length===10);
 await filePage.waitForFunction(()=>[...document.querySelectorAll('#regions .region-photo')].slice(0,4).every(i=>i.complete&&i.naturalWidth));
 await offline.close();
 assert.deepEqual(errors,[]);await browser.close();console.log('Visual UI passed: local photos/fonts/icons, static asset boundaries, photo fallbacks, all navigation screens at six widths, 44px dock targets and no JavaScript errors. Screenshots: '+out);
})().catch(e=>{console.error(e);process.exit(1)});
