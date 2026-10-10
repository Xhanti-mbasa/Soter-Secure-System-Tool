'use strict';
// A separate public representative directory; web candidates remain reviewable.
const partySearchBase = search, partyTabBase = tab;
const partyState = {data:null, current:null, member:null, serial:0, memberSerial:0, limit:60, discoveries:{}, section:'all'};
const partySections = [['all','All mentions','all',''],['government','Government records','government',''],['news','News & statements','all','news'],['remuneration','Salary records','government','remuneration'],['education','Public education','all','education'],['business','Business interests','company',''],['social','Social profiles','social','']];
const partyKey = s => s.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu,'');
const partyReady = (async()=>{
 try {
  partyState.data=native()&&typeof Native.partySnapshot==='function'?JSON.parse(Native.partySnapshot()):await(await fetch('party-data.json')).json();
  const saved=readLocal('sothis-party-rosters',{});
  partyState.data.parties=partyState.data.parties.map(p=>saved[p.code]?.captured_at>p.captured_at?saved[p.code]:p);
  await analyticsReady;
  renderPartyDirectory();
 }catch(e){notice('party-note','The party directory could not be loaded. '+e.message,true)}
})();

function partyMatch(q) {
 return partyState.data?.parties.find(p=>[p.code,p.name,...p.aliases||[]].some(n=>partyKey(n)===partyKey(q)));
}
function memberMatches(q, members) {
 const tokens=q.toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu)||[];
 return (members||[...partyState.data?.leaders||[],...partyState.data?.parties.flatMap(p=>p.members)||[]]).filter(m=>tokens.every(t=>m.name.toLocaleLowerCase().includes(t)));
}
function captureLabel(date) {return date?date.replace(/\+00:00$/,'Z').replace('T',' · ').replace('Z',' UTC'):'No capture recorded'}
function memberLink(m) {
 const b=button('',()=>openPartyMember(m),'memberlink'),copy=el('span','member-copy');copy.append(el('strong','',m.name),el('span','mono muted',(m.party_code||'')+(m.entity_type==='party_leader'?' · Party leadership':'')));b.append(portrait(m),copy);b.dataset.member=m.id;return b;
}
function renderPartyDirectory(q=$('party-query').value) {
 if(!partyState.data)return;
 $('party-panel').classList.remove('member-view');
 const box=$('party-directory');box.replaceChildren();$('party-body').hidden=true;$('member-body').hidden=true;box.hidden=false;
 $('party-coverage').textContent=partyState.data.coverage;
 renderPartyOverview();
 const parties=partyState.data.parties.filter(p=>!q||partyKey(p.code+' '+p.name+' '+(p.aliases||[]).join(' ')).includes(partyKey(q)));
 const grid=el('div','toolsgrid');box.append(grid);
 for(const p of parties){const card=el('article','source party-card');card.append(el('div','party-code-display',p.code),el('h3','',p.name),el('p','muted',p.captured_at?p.member_count+' listed public representatives':'Roster unavailable from this party page'),el('p','mono muted',captureLabel(p.captured_at)),button('View '+p.code,()=>openParty(p.code)));const faces=el('div','portrait-row');for(const m of p.members.slice(0,4))faces.append(portrait(m));card.insertBefore(faces,card.lastElementChild);grid.append(card)}
 if(!parties.length){box.append(el('h2','','Public representative matches'));const members=memberMatches(q);for(const m of members.slice(0,80))box.append(memberLink(m));if(!members.length)box.append(el('div','empty','No directory match. Try a party abbreviation or representative’s name, or search the public web.'));if(members.length>80)box.append(el('p','coverage','Showing the first 80 matches. Add more of the name to narrow the list.'))}
}

async function openParty(code,refresh=false) {
 await partyReady;const serial=++partyState.serial;partyState.memberSerial++;partyState.member=null;
 const p=partyState.data.parties.find(p=>p.code===code);if(!p)return;
 partyState.current=p;partyState.limit=60;$('member-filter').value='';tab('party');renderParty(p);
 if(supported())try{
  $('party-refresh').disabled=true;notice('party-note',refresh?'Refreshing Parliament’s published composition…':'');
  const r=await api('/api/party','POST',{code,refresh});if(serial!==partyState.serial||partyState.member)return;
  partyState.current=r;
  if(r.status!=='refresh_unavailable'&&r.captured_at){const cached=readLocal('sothis-party-rosters',{});cached[code]=r;saveLocal('sothis-party-rosters',cached);const i=partyState.data.parties.findIndex(x=>x.code===code);partyState.data.parties[i]=r;}
  renderParty(r);if(r.status==='refresh_unavailable')notice('party-note','Refresh unavailable · '+r.detail+'. The last captured roster is shown.',true);
 }catch(e){if(serial===partyState.serial)notice('party-note','Saved roster shown. '+e.message,true)}
 finally{if(serial===partyState.serial)$('party-refresh').disabled=false}
}
function renderParty(p) {
 $('party-panel').classList.remove('member-view');
 $('party-directory').hidden=true;$('member-body').hidden=true;$('party-body').hidden=false;
 $('party-overview').hidden=true;renderPartyAnalytics(p);
 $('party-title').textContent=p.name;$('party-code').textContent=p.code;
 $('party-capture').textContent=captureLabel(p.captured_at);$('party-roster-source').onclick=()=>openExternal(p.source_url);
 $('party-refresh').onclick=()=>openParty(p.code,true);
 $('party-public-search').onclick=()=>partyWebSearch(p.code);
 $('party-alert').onclick=()=>editMonitor({query:p.code,services:['government'],condition:'new_hit',interval_minutes:1440,enabled:true});
 if(p.collection_error&&!p.members.length)notice('party-note','Parliament’s party page did not provide a validated roster. '+p.collection_error+'. Use public discovery or open the official directory.',true);
 renderPartyMembers();
}
function renderPartyMembers() {
 const p=partyState.current;if(!p)return;const matches=memberMatches($('member-filter').value,p.members),box=$('party-members');box.replaceChildren();
 const leaders=$('party-leadership');leaders.replaceChildren();
 const leadership=memberMatches($('member-filter').value,(partyState.data.leaders||[]).filter(m=>m.party_code===p.code));
 if(leadership.length){leaders.append(el('h2','','Party leadership'),el('p','coverage','Sourced leadership entries are separate from the Parliament roster and do not add seats.'));const list=el('div','memberlist');leadership.forEach(m=>list.append(memberLink(m)));leaders.append(list)}
 $('party-member-count').textContent=matches.length+' matching representatives · '+p.members.length+' captured';
 for(const m of matches.slice(0,partyState.limit))box.append(memberLink(m));
 if(!matches.length)box.append(el('div','empty',p.members.length?'No member matches this name.':'A validated roster has not been retrieved for this party.'));
 $('party-member-more').hidden=matches.length<=partyState.limit;
}
function localMember(m) {
 const p=partyState.data.parties.find(p=>p.members.some(x=>x.id===m.id)||m.entity_type==='party_leader'&&p.code===m.party_code);
 const profile={...m,party_name:p.name,roster_url:m.entity_type==='party_leader'?m.source_url:p.source_url,captured_at:m.entity_type==='party_leader'?m.captured_at:p.captured_at,...partyState.data.profiles[m.id],...readLocal('sothis-member-profiles',{})[m.id],interests_register:partyState.data.interests_register};
 const role=(profile.role||'').toLocaleLowerCase(),office=role.startsWith('deputy minister')?'Deputy Minister':role.startsWith('minister')?'Minister':role==='deputy president'?'Deputy President':'';
 profile.remuneration=partyState.data.remuneration_schedules.find(r=>r.role===office)||null;
 profile.search_name=profile.search_name||profile.name.replace(/^(Mr|Ms|Mrs|Dr|Prof|Rev|Hon)\.?\s+/,'');return profile;
}
async function openPartyMember(m) {
 await partyReady;const serial=++partyState.memberSerial;partyState.serial++;partyState.current=partyState.data.parties.find(p=>p.code===m.party_code)||partyState.current;partyState.member=localMember(m);partyState.discoveries={};partyState.section='all';tab('party');renderPartyMember(partyState.member);
 if(supported())try{
  notice('member-status','Refreshing the public member page…');
  const r=await api('/api/member','POST',{id:m.id,refresh:true});if(serial!==partyState.memberSerial)return;
  partyState.member=r;const cache=readLocal('sothis-member-profiles',{});cache[m.id]=r;saveLocal('sothis-member-profiles',cache);renderPartyMember(r);notice('member-status','');
  if(r.status==='refresh_unavailable')notice('member-status','Member page unavailable · '+r.detail+'. Saved evidence is shown.',true);
 }catch(e){if(serial===partyState.memberSerial)notice('member-status','Saved profile shown · '+e.message,true)}
 if(serial===partyState.memberSerial)loadMemberMentions('all');
}
function sourceRow(box,url,page) {
 const row=el('div','row');row.append(button('Open source'+(page?' · PDF p. '+page:''),()=>openExternal(url+(page?'#page='+page:''))),button('Save original locally',()=>archiveEvidence(url,box)));box.append(row);
}
function factGroup(title,rows,captured) {
 const c=el('article','record');c.append(el('h3','',title));
 if(!rows?.length)c.append(el('p','muted','No sourced biography entry in this saved profile. Use the live public education search below.'));
 for(const f of rows||[]){c.append(el('p','',f.text));sourceRow(c,f.source_url)}if(captured)c.append(el('p','mono muted','Biography captured '+captureLabel(captured)));return c;
}
function renderPartyMember(m) {
 $('party-panel').classList.add('member-view');
 $('party-directory').hidden=true;$('party-body').hidden=true;$('member-body').hidden=false;
 $('party-overview').hidden=true;
 $('member-name').textContent=m.name;const photo=portrait(m,true);$('member-portrait').replaceChildren(photo);$('member-photo-credit').textContent='Portrait · Parliament of South Africa';if(!photo.querySelector('img'))$('member-photo-credit').textContent='No portrait in this capture · initials shown';else photo.querySelector('img').addEventListener('error',()=>{if(partyState.member?.id!==m.id)return;$('member-photo-credit').textContent='Portrait unavailable · initials shown'});$('member-party').textContent=m.party_name||m.party_code;
 const info=$('member-summary');info.replaceChildren(el('p','member-role',m.role||'Role awaiting member-page retrieval'),el('p','muted',m.chamber||'Chamber awaiting member-page retrieval'),el('p','mono muted',(m.entity_type==='party_leader'?'Leadership captured ':'Roster captured ')+captureLabel(m.captured_at)),el('p','mono muted','Profile '+captureLabel(m.profile_captured_at)));
 sourceRow(info,m.source_url);if(m.membership_note)info.append(el('div','note',m.membership_note));
 if(m.role_source_url)sourceRow(info,m.role_source_url);
 $('member-back').onclick=()=>openParty(m.party_code||partyState.current?.code||'ANC');
 $('member-alert').onclick=()=>editMonitor({query:m.search_name,services:['government','web'],condition:'new_hit',interval_minutes:1440,enabled:true});
 $('member-export').onclick=()=>saveReport('sothis-member-'+m.id+'.md',memberReport(m),'text/markdown');
 $('member-pin').onclick=()=>pinMember(m);
 $('member-company').onclick=()=>{partyWebSearch(m.search_name,'company')};
 const facts=$('member-facts');facts.replaceChildren();
 const salary=el('article','record');salary.append(el('h3','','Salary & remuneration'));
 if(m.remuneration){const r=m.remuneration;salary.append(el('strong','salary-amount','R '+r.annual_zar.toLocaleString('en-ZA')+' / year'),el('p','',r.role+' · published annual office remuneration'),el('p','mono muted','Effective '+r.effective_from+' · Gazette '+r.published_at),el('p','coverage',r.label));sourceRow(salary,r.source_url,r.page)}
 else{salary.append(el('p','muted','An applicable pay level has not been verified for this office. An MP may hold an additional paid position.'),button('Official salary determinations',()=>openExternal('https://www.remcommission.gov.za/library/determinations')))}
 facts.append(salary,factGroup('Public education & qualifications',m.education,m.biography_captured_at));
 const business=el('article','record');business.append(el('h3','','Declared business interests'));
 if(m.business_interests){const b=m.business_interests;business.append(el('p','mono muted',b.period+' · PDF pages '+b.page+'–'+b.page_end),el('p','coverage',b.label),businessCharts(b));const original=el('details','business-original');original.append(el('summary','','Read the original declaration text'),el('div','business-excerpt',b.text));business.append(original);sourceRow(business,b.source_url,b.page)}
 else business.append(el('p','muted','No matched business-interest extract in the saved profile. Open the public register to check this member’s declaration.'));
 business.append(button('All public registers by year',()=>openExternal(m.interests_register.directory_url)),el('p','coverage','A declaration is dated and self-reported. “Nothing to disclose” is not a complete company-register search. CIPC lookup requires an authorised disclosure.'));
 if(m.historical_business?.length){business.append(el('h3','','Historical roles from biography'));for(const f of m.historical_business){business.append(el('p','',f.text));sourceRow(business,f.source_url)}}facts.append(business);
 $('member-category-tabs').replaceChildren();for(const [id,label] of partySections){const b=button(label,()=>loadMemberMentions(id));b.dataset.memberSection=id;b.classList.toggle('active',id===partyState.section);$('member-category-tabs').append(b)}
 $('member-results').replaceChildren(el('div','note','Live mentions load below. Select a category to look for additional evidence.'));
}
function hitSection(h) {
 if(h.platform)return 'social';const t=(h.title+' '+h.description).toLocaleLowerCase();
 if(/remuneration|salary|salaries|pay scale/.test(t))return 'remuneration';
 if(/university|qualification|bcom|degree|school|education/.test(t))return 'education';
 if(/directorship|shareholder|company|business interest|cipc/.test(t))return 'business';
 return h.category==='government'?'government':'news';
}
async function loadMemberMentions(section) {
 const m=partyState.member;if(!m)return;const serial=partyState.memberSerial;partyState.section=section;
 document.querySelectorAll('[data-member-section]').forEach(b=>b.classList.toggle('active',b.dataset.memberSection===section));
 const box=$('member-results');box.replaceChildren(el('div','loading','Looking for '+partySections.find(s=>s[0]===section)[1].toLocaleLowerCase()+'…'));
 if(partyState.discoveries[section]){renderMemberMentions(section,partyState.discoveries[section]);return}
 try{
  if(!supported())throw new Error('Open the Android app or connect your engine to retrieve live public mentions.');
  const [, ,scope,term]=partySections.find(s=>s[0]===section);
  const r=await api('/api/discover','POST',{query:m.search_name,scope,topic:term});
  if(serial!==partyState.memberSerial)return;partyState.discoveries[section]=r;if(partyState.section===section)renderMemberMentions(section,r);
 }catch(e){if(serial===partyState.memberSerial&&partyState.section===section){box.replaceChildren(el('div','note error',e.message));browserSearches(box,m.search_name)}}
}
function renderMemberMentions(section,r) {
 const box=$('member-results');box.replaceChildren();
 const results=section==='news'?r.results.filter(h=>hitSection(h)==='news'):r.results;
 box.append(el('p','coverage',r.hit_count+' retrieved unique hits · '+r.account_count+' account candidates · '+results.length+' shown in this view. '+r.coverage+' Retrieved '+r.retrieved_at));
 for(const s of r.statuses||[])box.append(el('div','note'+(s.status==='unavailable'?' error':''),s.service+' · '+s.status+(s.detail?' · '+s.detail:'')));
 if(!results.length)box.append(el('div','empty','No matching indexed mentions returned in this view. This does not establish that records are absent.'));
 const groups=section==='all'?partySections.filter(s=>s[0]!=='all').map(s=>[s[1],results.filter(h=>hitSection(h)===s[0])]):[[partySections.find(s=>s[0]===section)[1],results]];
 for(const [label,hits] of groups){if(!hits.length)continue;box.append(el('h3','member-group-title',label+' · '+hits.length));const grid=el('div','results');box.append(grid);
  for(const h of hits){docFromHit(h);const c=el('article','record');c.append(sourceBadge(h),el('h3','',h.title),el('p','',h.description||h.url),el('p','mono muted',h.url),publicationDates(h));const row=el('div','row');row.append(button('Open',()=>openExternal(h.url)),button('Review & save',()=>{$('query').value=partyState.member.search_name;state.discovery=r;reviewHit(h)}));c.append(row);grid.append(c)}
 }
 if(section==='news'){
  const checks=[...box.querySelectorAll('.publication-dates button')].slice(0,4),memberId=partyState.member.id;
  const worker=async()=>{while(checks.length&&partyState.member?.id===memberId&&partyState.section==='news'){const b=checks.shift();await b.onclick()}};
  worker();worker();
 }
}
function memberReport(m) {
 const lines=['# '+m.name,'','Public representative dossier · '+new Date().toISOString(),'','## Public role and party',m.role||'Role not yet retrieved',m.party_name+' · '+(m.chamber||'Chamber not yet retrieved'),'Source: '+m.source_url,'Roster source: '+m.roster_url,'Roster captured: '+m.captured_at,'Member page captured: '+(m.profile_captured_at||'Not retrieved')];
 if(m.membership_note)lines.push(m.membership_note);
 if(m.role_source_url)lines.push('Public role evidence: '+m.role_source_url);
 lines.push('','## Published remuneration');if(m.remuneration){const r=m.remuneration;lines.push('Office: '+r.role,'Annual ZAR: '+r.annual_zar,'Effective from: '+r.effective_from+' · Published: '+r.published_at,r.label,'Source: '+r.source_url+' · PDF page '+r.page)}else lines.push('Applicable pay level has not been verified.');
 lines.push('','## Public education');for(const f of m.education||[])lines.push(f.text,'Source: '+f.source_url);if(m.biography_captured_at)lines.push('Biography captured: '+m.biography_captured_at,'Biography source content SHA-256: '+m.biography_content_hash);
 lines.push('','## Declared business interests');if(m.business_interests){const b=m.business_interests;lines.push(b.period,b.label,b.text,'Source: '+b.source_url+' · PDF pages '+b.page+'–'+b.page_end,'Extract captured: '+b.captured_at,'Extract SHA-256: '+b.content_hash)}else lines.push('No matched extract in this profile.');
 for(const f of m.historical_business||[])lines.push(f.text,'Source: '+f.source_url);
 lines.push('','## Retrieved mentions');const unique=new Map();for(const r of Object.values(partyState.discoveries))for(const h of r.results)unique.set(h.url,h);
 for(const h of unique.values())lines.push('','### '+h.title,h.description,'Source: '+h.url,'Published: '+(h.published_at||'Unavailable'),...(h.publication_date_source?['Date evidence: '+h.publication_date_source]:[]),...(h.date_checked_at?['Date checked: '+h.date_checked_at,'Date metadata source: '+h.publication_source_url,'Date source SHA-256: '+h.publication_content_hash]:[]),...(h.index_date?['Search page date (published or modified): '+h.index_date]:[]),'Retrieved: '+h.retrieved_at,'Search-index candidate. Identity and relationships require review.');
 lines.push('','## Coverage and review','Parliament-listed representatives and separately sourced party leadership. Capture dates are shown; this is not every party member nationwide. Public biography statements and self-declarations do not replace verified qualifications or a current CIPC disclosure. Pay schedules do not establish personal pay. Web categories are text-based suggestions, not verified relationships. This dossier is not a complete search.');return lines.join('\n');
}
async function pinMember(m) {
 try {
  const text=memberReport(m),hash=await textHash(text),dossierUrl=m.entity_type==='party_leader'?m.role_source_url:m.source_url;let d={id:'party-member-'+m.id+'-'+hash.slice(0,12),url:dossierUrl,title:m.name+' · public representative dossier',text,category:'government',province:'National',source_id:'parliament-public-profile',retrieved_at:new Date().toISOString(),content_hash:hash,acquisition:'sourced_dossier',social_links:[]};
  if(state.connected){const source=state.sources.find(s=>new URL(s.url).hostname===new URL(dossierUrl).hostname);if(!source)throw new Error('Register this public source in the engine before pinning this dossier.');const r=await api('/api/import','POST',{source_id:source.id,url:dossierUrl,record_key:'member-'+m.id+'-'+hash.slice(0,12),title:d.title,text});d=await api('/api/documents/'+r.id)}
  state.docs.set(d.id,d);await pinDocument(d.id);
 }catch(e){toast(e.message)}
}
function partyWebSearch(query,mode='live') {tab('search');$('query').value=query;$('search-mode').value=mode;partySearchBase()}
search=async function(more=false) {
 const q=$('query').value.trim(),mode=$('search-mode').value;
 if(q||mode==='party')await partyReady;
 const exact=q&&partyMatch(q);
 if(mode==='party'||(exact&&mode==='live')){
  state.liveSerial++;state.searchSerial++;$('party-query').value=q;tab('party');notice('party-note','');
  if(exact)await openParty(exact.code);else renderPartyDirectory(q);return;
 }
 await partySearchBase(more);
 // Suggest verified public representative records alongside ordinary web searches.
 if(q&&mode==='live'&&state.tab==='search'&&$('query').value.trim()===q){const matches=memberMatches(q);if(matches.length&&matches.length<=8&&q.split(/\s+/).length>=2){const row=el('div','note');row.append(el('h3','','Public representative directory'));for(const m of matches)row.append(memberLink(m));$('live-discovery').prepend(row)}}
};
tab=function(name){partyTabBase(name);if(name==='party'){if(!partyState.member&&!partyState.current)partyReady.then(()=>renderPartyDirectory());refreshAnalytics()}};
$('party-query').oninput=()=>{partyState.serial++;partyState.memberSerial++;partyState.current=null;partyState.member=null;notice('party-note','');renderPartyDirectory()};
$('party-search-form').onsubmit=async e=>{e.preventDefault();await partyReady;const p=partyMatch($('party-query').value);if(p)openParty(p.code);else renderPartyDirectory()};
$('party-directory-back').onclick=()=>{partyState.serial++;partyState.memberSerial++;partyState.current=null;partyState.member=null;$('party-query').value='';notice('party-note','');renderPartyDirectory()};
$('member-filter').oninput=()=>{partyState.limit=60;renderPartyMembers()};
$('party-member-more').onclick=()=>{partyState.limit+=60;renderPartyMembers()};
