const {openSearch}=require('./navigation_helpers.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.join(__dirname,'../android/app/src/main/assets');
const data=JSON.parse(fs.readFileSync(path.join(root,'party-data.json'),'utf8'));
const snapshot=JSON.parse(fs.readFileSync(path.join(root,'snapshot.json'),'utf8'));
const anc=data.parties.find(p=>p.code==='ANC'),seed=anc.members.find(m=>m.id==='5975');
const member={...seed,...data.profiles['5975'],party_name:anc.name,roster_url:anc.source_url,captured_at:anc.captured_at,
 interests_register:data.interests_register,remuneration:data.remuneration_schedules.find(r=>r.role==='Minister'),status:'refreshed'};
const hits=[
 {id:'official-biography',url:'https://www.gov.za/gwede-mantashe',title:'Gwede Mantashe public biography',description:'Gwede Mantashe holds degrees from Wits and UNISA.',category:'government',platform:null},
 {id:'public-news',url:'https://example.org/public-news',title:'Gwede Mantashe public statement',description:'Gwede Mantashe statement reported in this public article.',category:'web',platform:null},
 {id:'social-profile',url:'https://instagram.com/example',title:'Gwede Mantashe profile candidate',description:'Gwede Mantashe name match. Ownership unreviewed.',category:'social',platform:'Instagram'}
].map(h=>({...h,match_label:'Name terms match',match_reason:'Text relevance, not identity.',retrieved_at:data.captured_at,content_hash:'fixture-hash'}));
function discovery(body){const results=body.scope==='social'?hits.filter(h=>h.platform):body.scope==='government'?hits.filter(h=>h.category==='government'):hits;return {query:body.query,results,hit_count:results.length,account_count:results.filter(h=>h.platform).length,statuses:[{service:'Recorded fixture provider',status:'completed'}],retrieved_at:data.captured_at,coverage:'Retrieved public candidates only.',companies:[],cipc:{url:'https://www.bizportal.gov.za/',detail:'Authorised CIPC disclosure required.'}}}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,args:['--no-sandbox','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1']});
 for(const standalone of [false,true]){
  const context=await browser.newContext({viewport:{width:390,height:844}}),errors=[],requests=[];
  if(standalone)await context.addInitScript(({snapshot,data,member})=>{
   window.savedReports=[];window.bridgeCalls=[];let rules=[];
   window.Native={snapshot:()=>JSON.stringify(snapshot),partySnapshot:()=>JSON.stringify(data),config:()=>JSON.stringify({url:'',configured:false}),open:()=>{},save:(name,text,mime)=>savedReports.push({name,text,mime}),share:()=>{},bundle:(name,text)=>savedReports.push({name,text}),
    request:(id,route,method,body)=>{const d=JSON.parse(body);bridgeCalls.push({route,method,d});route=route.replace('/api/device/','/api/');let r;
     if(route==='/api/party')r={...data.parties.find(p=>p.code===d.code),status:d.refresh?'refresh_unavailable':'saved_roster',detail:'Recorded provider failure',coverage:data.coverage};
     else if(route==='/api/member')r=member;
     else if(route==='/api/discover'){const h={id:'fixture',url:'https://instagram.com/example',title:'Gwede Mantashe',description:'Public name match',platform:'Instagram',category:'social',match_label:'Name terms match',retrieved_at:data.captured_at,content_hash:'fixture-hash'};r={query:d.query,results:[h],hit_count:1,account_count:1,statuses:[],retrieved_at:data.captured_at,coverage:'Candidate only.'};}
     else if(route==='/api/monitors'){if(method==='POST'){rules.push({...d,id:'rule-party'});r=rules.at(-1)}else r=rules}
     else if(route==='/api/alerts')r=[];
     else if(route==='/api/evidence')r={url:d.url,sha256:'b'.repeat(64),bytes:123,mime:'application/pdf',retrieved_at:data.captured_at,location:'device_archive'};
     else throw Error('Unexpected party route '+route);
     setTimeout(()=>nativeReply(id,JSON.stringify(r),''),5);
    }};
  },{snapshot,data,member});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  if(!standalone){
   await page.route('**/api/member',route=>route.fulfill({json:member}));
   await page.route('**/api/discover',route=>{const d=route.request().postDataJSON();requests.push(d);return route.fulfill({json:discovery(d)})});
  }
  await page.goto(process.env.SOTHIS_TEST_URL||'http://127.0.0.1:8765');await openSearch(page);await page.evaluate(()=>document.getElementById('search-scope').open=true);await page.waitForFunction(()=>state.docs.size>0);
  if(!standalone)await page.waitForFunction(()=>state.connected);
  await page.locator('#query').fill('ANC');await page.locator('#search-form button[type=submit]').click();await page.locator('#party-title').filter({hasText:anc.name}).waitFor();
  await page.locator('#member-filter').fill('Gwede Mantashe');assert.equal(await page.locator('#party-members [data-member]').count(),1);
  await page.locator('[data-member="5975"]').click();await page.locator('#member-results .record').first().waitFor();
  assert.match(await page.locator('#member-summary').innerText(),/Minister of Mineral and Petroleum Resources/);
  const facts=await page.locator('#member-facts').innerText();assert.match(facts,/2025-04-01/);assert.match(facts,/not verified personal pay/);assert.match(facts,/Witwatersrand/);assert.match(facts,/Nothing to disclose/);assert.match(facts,/historical|past appointment/i);
  await page.locator('[data-member-section=education]').click();await page.locator('#member-results .record').first().waitFor();
  if(!standalone){assert.equal(requests.at(-1).query,'Gwede Mantashe');assert.equal(requests.at(-1).topic,'education')}
  await page.locator('[data-member-section=social]').click();await page.locator('#member-results').filter({hasText:/account candidates/}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(standalone){await page.locator('#member-facts .record').first().getByRole('button',{name:'Save original locally',exact:true}).click();await page.locator('#member-facts .record').first().filter({hasText:'Saved 123 bytes'}).waitFor();}
  await page.locator('#member-export').click();
  if(standalone){const report=await page.evaluate(()=>savedReports.at(-1));assert.equal(report.name,'sothis-member-5975.md');assert.match(report.text,/Annual ZAR: 2792155/);assert.match(report.text,/PDF pages/);assert.match(report.text,/not verified personal pay/)}
  await page.screenshot({path:'/tmp/sothis-party-member-'+(standalone?'native':'engine')+'.png',fullPage:false});
  await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=cases]').click();await page.locator('#new-case').click();await page.getByLabel('Investigation title',{exact:true}).fill('Party research dossier');await page.getByRole('button',{name:'Save investigation',exact:true}).click();
  await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=party]').click();await page.locator('#member-pin').click();await page.locator('#toast').filter({hasText:/Pinned to/}).waitFor();
  await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=cases]').click();await page.locator('#case-list').filter({hasText:/1 evidence records|1 pinned record|1 evidence|1 pinned/}).waitFor();assert.match(await page.locator('#case-list').innerText(),/1 evidence records|1 pinned record|1 evidence|1 pinned/);
  if(standalone){await page.locator('#case-list .case').filter({hasText:'Party research dossier'}).getByRole('button',{name:'Export brief',exact:true}).click();await page.getByRole('button',{name:'Download evidence bundle',exact:true}).click();const exported=await page.evaluate(()=>JSON.parse(savedReports.find(r=>r.name==='sothis-evidence.zip').text));assert.equal(exported.evidence.length,1);assert.match(exported.evidence[0].url,/53965gon7004/);await page.getByRole('button',{name:'Close',exact:true}).click();}
  await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=party]').click();await page.locator('#member-alert').click();assert.equal(await page.getByLabel('Person, business number or keyword').inputValue(),'Gwede Mantashe');await page.getByRole('button',{name:'Save alert',exact:true}).click();await page.locator('#monitor-list').filter({hasText:'Gwede Mantashe'}).waitFor();
  await page.evaluate(()=>document.querySelector('.header-explore').open=true);await page.locator('[data-tab=party]').click();await page.evaluate(()=>parentRoute('party'));await page.locator('#party-title').filter({hasText:anc.name}).waitFor();await page.evaluate(()=>parentRoute('directory'));
  await page.locator('#party-query').fill('DA');await page.locator('#party-search-form button').click();await page.locator('#party-title').filter({hasText:'Democratic Alliance'}).waitFor();
  if(standalone){await page.locator('#party-refresh').click();await page.locator('#party-note').filter({hasText:'Refresh unavailable'}).waitFor();assert.match(await page.locator('#party-member-count').innerText(),/99 captured/);assert.ok(await page.evaluate(()=>bridgeCalls.some(c=>c.route==='/api/device/member'&&c.d.refresh)));}
  assert.deepEqual(errors,[]);await context.close();
 }
 await browser.close();console.log('Party UI passed: ANC routing, official roster, member dossier, salary provenance, education, disclosures, category searches, export, pinning, alerts, provider failure and mobile width (engine + native bridge).');
})().catch(e=>{console.error(e);process.exit(1)});
