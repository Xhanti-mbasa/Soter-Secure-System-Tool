const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage();
 const errors=[],securityErrors=[];
 page.on('pageerror',error=>errors.push(error.message));
 page.on('console',message=>{if(message.type()==='error'&&/Content Security Policy|Refused to/.test(message.text()))securityErrors.push(message.text());});
 const base=process.env.SOTHIS_TEST_URL,shots=process.env.SOTHIS_SCREENSHOTS;
 if(shots)fs.mkdirSync(shots,{recursive:true});
 await page.goto(base);assert.match(page.url(),/\/login$/);
 assert.equal((await context.request.get(base+'/api/cases')).status(),401);
 await page.locator('#username').fill('qa');await page.locator('#password').fill('incorrect-password');
 await page.locator('#sign-in').click();await page.locator('#login-error').filter({hasText:'incorrect'}).waitFor();
 if(shots){await page.locator('#login-error').evaluate(n=>n.textContent='');await page.locator('#username').fill('');await page.locator('#password').fill('');await page.screenshot({path:path.join(shots,'web-login.png')});await page.locator('#username').fill('qa');}
 await page.locator('#password').fill(process.env.SOTHIS_TEST_PASSWORD);await page.locator('#sign-in').click();
 await page.waitForFunction(()=>typeof state!=='undefined'&&state.connected);
 assert.match(await page.locator('#status').innerText(),/SERVER CONNECTED/);
 assert.equal(await page.evaluate(()=>document.fonts.ready.then(()=>document.fonts.check('800 30px Doto'))),true);
 await page.waitForFunction(()=>[...document.querySelectorAll('#start-cards>button>img')].every(image=>image.complete&&image.naturalWidth));
 if(shots)await page.screenshot({path:path.join(shots,'web-home.png')});
 await page.locator('#search-mode').selectOption('index');await page.locator('#query').fill('Ramaphosa');
 await page.locator('#search-form button').click();await page.waitForFunction(()=>state.total>0&&state.results.some(result=>/Ramaphosa/i.test(result.text||result.excerpt||result.title)));
 await page.locator('#results button').filter({hasText:'View evidence'}).first().click();
 await page.locator('#dialog').filter({hasText:'SHA-256'}).waitFor();await page.getByRole('button',{name:'Close',exact:true}).click();
 await page.locator('[data-tab=cases]').click();await page.locator('#new-case').click();
 await page.getByLabel('Investigation title',{exact:true}).fill('Website QA investigation');
 await page.getByLabel('Research question',{exact:true}).fill('Public source verification');
 await page.getByLabel('Research notes',{exact:true}).fill('Check publication date and source context.');
 await page.getByRole('button',{name:'Save investigation',exact:true}).click();
 await page.locator('[data-tab=search]').click();await page.locator('#results button').filter({hasText:'+ Pin'}).first().click();
 await page.locator('#toast').filter({hasText:'Pinned to'}).waitFor();
 await page.locator('[data-tab=cases]').click();let card=page.locator('.case').filter({hasText:'Website QA investigation'});
 await card.getByRole('button',{name:'Export brief',exact:true}).click();
 let downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Save Markdown',exact:true}).click();
 let download=await downloadPromise;assert.match(fs.readFileSync(await download.path(),'utf8'),/Evidence register/);
 downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download evidence bundle',exact:true}).click();
 download=await downloadPromise;assert.equal(download.suggestedFilename(),'sothis-evidence.zip');
 assert.equal(fs.readFileSync(await download.path()).subarray(0,2).toString(),'PK');
 await page.getByRole('button',{name:'Close',exact:true}).click();
 // The HTTP endpoint delivers real archived bytes under the authenticated cookie.
 const archive=await context.request.get(base+'/api/evidence/'+process.env.SOTHIS_TEST_ARCHIVE_HASH+'/download');
 assert.equal(archive.status(),200);assert.match((await archive.body()).toString(),/Public source fixture/);
 assert.match(archive.headers()['content-disposition'],/attachment/);
 await page.locator('[data-tab=sources]').click();await page.getByRole('button',{name:'New alert',exact:true}).click();
 await page.getByLabel('Person, business number or keyword',{exact:true}).fill('Ramaphosa');
 await page.getByRole('button',{name:'Save alert',exact:true}).click();
 await page.locator('#monitor-list').filter({hasText:'Ramaphosa'}).waitFor();
 await page.locator('#monitor-list').getByRole('button',{name:'Pause',exact:true}).click();
 await page.locator('#monitor-list').getByRole('button',{name:'Resume',exact:true}).waitFor();
 await page.locator('[data-tab=party]').click();await page.getByRole('button',{name:'View ANC',exact:true}).waitFor();
 await page.locator('[data-tab=regions]').click();assert.equal(await page.locator('#regions button').count(),10);
 await page.locator('[data-tab=settings]').click();assert.equal(await page.locator('#engine-url').isVisible(),false);
 assert.equal(await page.locator('#search-key').isVisible(),false);
 assert.match(await page.locator('.web-account').innerText(),/Signed in as qa/);
 for(const width of [320,390,720,1280]){
  await page.setViewportSize({width,height:900});
  for(const tab of ['search','party','regions','sources','cases','settings']){
   await page.locator('[data-tab='+tab+']').click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Overflow '+tab+' at '+width);
  }
 }
 await page.setViewportSize({width:390,height:844});await page.locator('[data-tab=search]').click();
 await page.locator('#query').fill('');await page.locator('#search-form button').click();
 if(shots)await page.screenshot({path:path.join(shots,'web-mobile.png')});
 await page.reload();await page.waitForFunction(()=>state.connected);await page.locator('[data-tab=cases]').click();
 await page.locator('.case').filter({hasText:'Website QA investigation'}).waitFor();
 await page.locator('[data-tab=settings]').click();await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await page.waitForURL('**/login');assert.equal((await context.request.get(base+'/api/cases')).status(),401);
 assert.equal(await page.evaluate(()=>Object.keys(localStorage).some(key=>key.startsWith('za-')||key.startsWith('sothis-'))),false);
 await page.goto(base);assert.match(page.url(),/\/login$/);
 assert.deepEqual(errors,[]);assert.deepEqual(securityErrors,[]);
 await browser.close();console.log('Web UI passed: real login/CSRF, seeded search, saved cases/pins, Markdown/ZIP export, original download, alert creation/pause, Party/regions, reload/logout and all six screens at four widths.');
})().catch(error=>{console.error(error);process.exit(1)});
