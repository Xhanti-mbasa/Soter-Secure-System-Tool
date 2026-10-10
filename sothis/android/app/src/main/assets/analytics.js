'use strict';
// All chart numbers come from dated evidence. Decorative Figma geometry is
// adapted to real data; no mock performance curve is used as an election result.
const analyticsState={data:null,lastRefresh:0};
const analyticsReady=(async()=>{
 try{analyticsState.data=native()&&typeof Native.analyticsSnapshot==='function'?JSON.parse(Native.analyticsSnapshot()):await(await fetch('analytics-data.json')).json();}
 catch(e){console.warn('Election evidence unavailable',e.message)}
})();
function latestElection(data=analyticsState.data){return data?.national_elections?.slice().sort((a,b)=>b.date.localeCompare(a.date))[0]}
function activeNationalPoll(data=analyticsState.data,today=new Date().toISOString().slice(0,10)){
 const election=latestElection(data);if(!election)return null;
 return (data.polls||[]).filter(p=>p.election_type==='national'&&p.measure==='voting_intention'&&p.target_after===election.date&&p.published_at<=today&&p.expires_at>today).sort((a,b)=>b.published_at.localeCompare(a.published_at))[0]||null;
}
async function refreshAnalytics(){
 await analyticsReady;
 if(!state.connected||Date.now()-analyticsState.lastRefresh<300000)return;
 analyticsState.lastRefresh=Date.now();
 try{const data=await api('/api/analytics');analyticsState.data=data;if(state.tab==='party'&&!partyState.member){if(partyState.current)renderPartyAnalytics(partyState.current);else renderPartyOverview()}}
 catch(e){/* The dated bundled capture remains visible when an engine is offline. */}
}
function evidenceDate(value){
 if(!value)return 'Unavailable';const d=new Date(/^\d{4}-\d\d-\d\d$/.test(value)?value+'T00:00:00Z':value);
 return Number.isNaN(d.valueOf())?'Unavailable':d.toLocaleDateString('en-ZA',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});
}
function chartCard(title,kicker){const card=el('article','analytics-card');if(kicker)card.append(el('div','eyebrow',kicker));card.append(el('h3','chart-heading',title));return card}
function evidenceLink(card,label,url){const a=el('a','chart-source',label+' ↗');a.href=url;a.onclick=e=>{e.preventDefault();openExternal(url)};card.append(a);return a}
function svgNode(tag,attrs){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs||{}))n.setAttribute(k,String(v));return n}
function ringChart(value,total,color,caption){
 const wrap=el('div','chart-ring'),svg=svgNode('svg',{viewBox:'0 0 160 160',role:'img','aria-label':caption+': '+value+' of '+total});
 const length=2*Math.PI*75;svg.append(svgNode('circle',{cx:80,cy:80,r:75,class:'ring-track'}),svgNode('circle',{cx:80,cy:80,r:75,fill:'none',stroke:color,'stroke-width':10,'stroke-linecap':'butt','stroke-dasharray':length,'stroke-dashoffset':length*(1-value/total),transform:'rotate(-90 80 80)'}));
 const label=el('div','ring-label');label.append(el('strong','',((value/total)*100).toLocaleString('en-ZA',{maximumFractionDigits:2})+'%'),el('span','',caption));wrap.append(svg,label);return wrap;
}
function metric(label,value,detail){const item=el('div','chart-metric');item.append(el('span','mono muted',label),el('strong','',value));if(detail)item.append(el('span','muted',detail));return item}
function chartBar(label,value,max,color,display,action){
 const row=el(action?'button':'div','chart-bar');if(action){row.type='button';row.onclick=action}
 row.append(el('span','bar-label',label));const track=el('span','bar-track'),fill=el('span','bar-fill');fill.style.width=Math.max(0,Math.min(100,value/max*100))+'%';fill.style.background=color;track.append(fill);row.append(track,el('strong','bar-value',display));return row;
}
function sortedSeats(election){return Object.entries(election.seats).filter(([,n])=>n>0).sort((a,b)=>b[1]-a[1])}
function seatTiles(election,selected){
 const tiles=el('div','seat-tiles');tiles.setAttribute('role','img');tiles.setAttribute('aria-label','400 seat tiles. '+(selected?selected+' holds '+(election.seats[selected]||0)+' seats.':sortedSeats(election).map(([c,n])=>c+' '+n).join(', ')));
 for(const [code,count] of sortedSeats(election))for(let i=0;i<count;i++){const t=el('span','seat-tile');t.style.background=selected&&code!==selected?'#515151':analyticsState.data.colors[code]||'#aaa';t.title=code;t.setAttribute('aria-hidden','true');tiles.append(t)}return tiles;
}
function renderPartyOverview(){
 const box=$('party-overview');if(!box)return;box.replaceChildren();box.hidden=!!partyState.current||!!partyState.member||!!$('party-query').value.trim();
 if(box.hidden)return;
 const data=analyticsState.data,e=latestElection();
 if(!data||!e){box.append(el('div','note','Election analytics are unavailable. The representative directory remains available.'));return}
 const head=el('div','sectionhead');head.append(el('h2','','The Assembly.'),el('span','mono muted','ELECTION · '+evidenceDate(e.date)));box.append(head);
 const grid=el('div','analytics-grid overview-grid'),card=chartCard('Seats in Parliament','NATIONAL ASSEMBLY'),map=chartCard('South Africa, by province','PROVINCIAL VOTE');
 card.append(metric('TOTAL SEATS','400',sortedSeats(e).length+' represented parties'),seatTiles(e));
 const bars=el('div','seat-bars');for(const [code,count] of sortedSeats(e))bars.append(chartBar(code,count,400,data.colors[code]||'#bbb',String(count),()=>openParty(code)));card.append(bars,el('p','coverage','Each tile is one National Assembly seat. Roster counts also include NCOP members and are shown separately.'));
 evidenceLink(card,'Parliament · allocation captured '+evidenceDate(data.captured_at),e.source_url);
 renderProvinceMap(map);grid.append(card,map);box.append(grid);box.append(el('h2','directory-heading','Explore a party.'));
}
function renderProvinceMap(card){
 const data=analyticsState.data,svg=svgNode('svg',{viewBox:'0 0 460 425',class:'province-map',role:'group','aria-label':'South Africa: highest provincial-ballot vote share by province'}),info=el('div','province-detail');
 function select(province){
  svg.querySelectorAll('path').forEach(p=>p.classList.toggle('selected',p.dataset.province===province.name));info.replaceChildren(el('h3','',province.name));
  const leader=province.results[0];info.append(el('p','muted',leader.code+' · '+leader.share.toFixed(2)+'% · highest vote share'));
  for(const r of province.results.slice(0,4))info.append(chartBar(r.code,r.share,100,data.colors[r.code]||'#aaa',r.share.toFixed(2)+'%',()=>openParty(r.code)));
 }
 for(const province of data.provinces){const path=svgNode('path',{d:province.path,fill:data.colors[province.leader],stroke:'#242424','stroke-width':1.2,'fill-rule':'evenodd',tabindex:0,role:'button','aria-label':province.name+' · '+province.leader+' · '+province.results[0].share.toFixed(2)+'%'});path.dataset.province=province.name;const title=svgNode('title');title.textContent=path.getAttribute('aria-label');path.append(title);path.onclick=()=>select(province);path.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(province)}};svg.append(path)}
 card.append(svg);const choices=el('div','province-choices');for(const p of data.provinces){const b=button(p.name,()=>select(p),'small');b.setAttribute('aria-label','Show '+p.name+' results');choices.append(b)}card.append(choices,info);select(data.provinces.find(p=>p.name==='Western Cape'));
 card.append(el('p','coverage','Largest share of the '+evidenceDate(data.provincial_election.date)+' provincial ballot. A plurality does not establish coalition control.'));
 evidenceLink(card,'IEC · provincial results',data.provincial_election.source_url);
 evidenceLink(card,'Map · '+data.map_credit.source+' · '+data.map_credit.license,data.map_credit.url);
}
function renderPartyAnalytics(p){
 const box=$('party-analytics');box.replaceChildren();const data=analyticsState.data,e=latestElection();if(!data||!e)return;
 const count=e.seats[p.code]||0,color=data.colors[p.code]||'#aaa';
 const grid=el('div','analytics-grid party-chart-grid'),share=chartCard('Assembly share','PARLIAMENT'),trend=chartCard('Seats over time','ELECTION RESULTS'),outlook=chartCard('Next national election','OUTLOOK');
 share.append(ringChart(count,400,color,'of Assembly seats'),metric('SEAT ALLOCATION',count+' / 400','Election · '+evidenceDate(e.date)));
 const majority=201;share.append(chartBar('Seats',count,400,color,String(count)),el('p','coverage',count>=majority?'At least 201 allocated seats.':(majority-count)+' seats short of a 201-seat majority in a full Assembly. This is seat share, not ownership or a voting forecast.'));
 evidenceLink(share,'Parliament · seat allocation',e.source_url);
 const history=data.national_elections.slice().sort((a,b)=>a.date.localeCompare(b.date));
 const graph=svgNode('svg',{viewBox:'0 0 280 180',class:'election-trend',role:'img','aria-label':history.map(h=>h.date.slice(0,4)+': '+(h.seats[p.code]||0)+' seats').join('; ')}),points=history.map((h,i)=>({x:25+(history.length>1?i/(history.length-1)*230:115),y:145-(h.seats[p.code]||0)/400*125,seats:h.seats[p.code]||0}));
 for(const n of [0,200,400]){const y=145-n/400*125;graph.append(svgNode('line',{x1:20,x2:265,y1:y,y2:y,stroke:'#555','stroke-dasharray':'2 5'}))}
 graph.append(svgNode('polyline',{points:points.map(p=>p.x+','+p.y).join(' '),fill:'none',stroke:color,'stroke-width':3}));
 points.forEach(point=>{graph.append(svgNode('circle',{cx:point.x,cy:point.y,r:5,fill:color}));const text=svgNode('text',{x:point.x,y:point.y-12,fill:'#ddd','text-anchor':'middle','font-size':12});text.textContent=point.seats;graph.append(text)});trend.append(graph);
 for(const h of history){const seats=h.seats[p.code]||0;trend.append(chartBar(h.date.slice(0,4),seats,400,color,seats+' seats'));evidenceLink(trend,'Allocation · '+h.date.slice(0,4),h.source_url)}
 const delta=count-(history.length>1?history.at(-2).seats[p.code]||0:count);trend.append(metric('CHANGE',delta>0?'+'+delta:String(delta),'Seats since the previous captured election'));
 trend.append(el('p','coverage','Comparable National Assembly allocations. A zero means no allocated Assembly seats in that election.'));
 const poll=activeNationalPoll();
 if(poll){const share=poll.shares[p.code];outlook.append(el('p','mono muted',poll.publisher+' · published '+evidenceDate(poll.published_at)));
  if(share===undefined)outlook.append(el('p','muted','This party was not reported separately in the poll.'));
  else outlook.append(chartBar('Voting intention',share,100,color,share.toFixed(1)+'%'));
  outlook.append(el('p','coverage',poll.population+' · sample '+poll.sample_size+' · fieldwork '+evidenceDate(poll.fieldwork_from)+'–'+evidenceDate(poll.fieldwork_to)),el('p','coverage',poll.methodology),el('p','coverage','Voting intention is not the probability of winning. Polls for an earlier election cycle are retired when newer results are installed.'));
  evidenceLink(outlook,'Read poll and methodology',poll.source_url);
 }else{outlook.append(el('div','outlook-unavailable','NO REVIEWED FORECAST'),el('p','muted','A credible national-election forecast has not been added to this capture.'),el('div','unavailable-track'),el('p','coverage','No percentage is assigned. The '+e.date.slice(0,4)+' results and local-election polls cannot establish a national win probability. New national polls must include dates, sample and methodology.'))}
 outlook.append(el('p','mono muted','Current cycle · after '+evidenceDate(e.date)));
 grid.append(share,trend,outlook);box.append(grid);
 const provinces=chartCard('Provincial footprint',data.provincial_election.date.slice(0,4)+' PROVINCIAL BALLOT');for(const province of data.provinces){const r=province.results.find(r=>r.code===p.code);if(r)provinces.append(chartBar(province.name,r.share,100,color,r.share.toFixed(2)+'%'))}
 provinces.append(el('p','coverage','Share of valid provincial-ballot votes, not national-ballot share or governing control. Captured '+evidenceDate(data.captured_at)+'.'));evidenceLink(provinces,'IEC · detailed provincial results',data.provincial_election.source_url);box.append(provinces);
}
function disclosureSections(text){
 const headings=[...text.matchAll(/(?:^|\n)\s*([1-4])\.\s*([^\n]+)/g)],columns=[/Name of Company[^\n]*/i,/Name of Employer[^\n]*/i,/Name of the Company[^\n]*/i,/Name of Org(?:an|na)ization[^\n]*/i];
 const labels=['Shares & financial interests','Outside employment','Directorships & partnerships','Consultancies & retainers'];
 return labels.map((label,i)=>{const at=headings.findIndex(m=>Number(m[1])===i+1);if(at<0)return {label,status:'unavailable',body:''};const start=headings[at].index+headings[at][0].length,end=headings[at+1]?.index||text.length,body=text.slice(start,end).replace(columns[i],'').trim();
  const empty=/^(?:nothing to disclose|none|nil|n\/a|not applicable|no(?:ne)?[.\s]*)(?:[.\s]*)$/i.test(body);return {label,status:!body?'unavailable':empty?'none_declared':'entry_text',body};});
}
function declaredAmounts(text){
 const section=disclosureSections(text)[0].body;return [...section.matchAll(/\bR[ \u00a0]*([\d][\d \u00a0.,]*)/g)].map(m=>{const s=m[1].trim().replace(/[ \u00a0]/g,'');if(!/^\d+(?:[.,]\d{3})*(?:[.,]\d{2})?$/.test(s))return NaN;const decimal=/[.,]\d{2}$/.test(s);return decimal?Number(s.slice(0,-3).replace(/[.,]/g,'')+'.'+s.slice(-2)):Number(s.replace(/[.,]/g,''))}).filter(n=>Number.isFinite(n)&&n>=0).slice(0,12);
}
function businessCharts(b){
 const wrap=el('div','disclosure-charts'),sections=disclosureSections(b.text),count=sections.filter(s=>s.status==='entry_text').length;
 const summary=el('div','disclosure-summary');summary.append(ringChart(count,4,'#4388ff','sections with entry text'),metric('PUBLIC DISCLOSURE',count+' / 4','Business sections with entry text'));wrap.append(summary);
 const rows=el('div','disclosure-sections');for(const s of sections){const row=el('div','disclosure-section '+s.status);row.append(el('span','',s.label),el('span','disclosure-marker'),el('strong','',s.status==='none_declared'?'Nothing declared':s.status==='entry_text'?'Entry text present':'Not extracted'));rows.append(row)}wrap.append(rows);
 const amounts=declaredAmounts(b.text);if(amounts.length){wrap.append(el('h3','','Nominal amounts in shares section'));const max=Math.max(1,...amounts);amounts.forEach((n,i)=>wrap.append(chartBar('Amount '+(i+1),n,max,'#4388ff','R '+n.toLocaleString('en-ZA',{maximumFractionDigits:2}))));wrap.append(el('p','coverage','ZAR amounts extracted from the nominal-value section, in source order. These are declared figures, not market values or confirmed company ownership. Check the original table for the associated entity.'))}
 wrap.append(el('p','coverage','Section status summarises the dated declaration text; it does not count companies or verify holdings. Source: '+b.period+' · PDF p. '+b.page+'–'+b.page_end+'.'));return wrap;
}
const platformIcons={'Instagram':'instagram','Facebook':'facebook','LinkedIn':'linkedin','X / Twitter':'x','TikTok':'tiktok','YouTube':'youtube'};
function sourceBadge(hit){
 const badge=el('div','source-badge'),name=hit.platform||(()=>{try{return new URL(hit.url).hostname.replace(/^www\./,'')}catch(e){return 'Public source'}})();
 const img=el('img','source-icon');img.src='icons/'+(platformIcons[hit.platform]|| (hit.category==='government'?'buildings':'newspaper'))+'.svg';img.alt='';badge.append(img,el('span','',name));return badge;
}
function publicationDates(hit){
 const box=el('div','publication-dates');const publication=el('p','published-date',hit.published_at?'Published · '+evidenceDate(hit.published_at):'Publication date unavailable');box.append(publication);
 if(hit.published_at&&hit.publication_date_source)box.append(el('p','mono muted',hit.publication_date_source));
 if(hit.index_date&&!hit.published_at)box.append(el('p','mono muted','Search page date · '+evidenceDate(hit.index_date)+' · may be modified date'));
 box.append(el('p','mono muted','Retrieved · '+evidenceDate(hit.retrieved_at)));
 if(!hit.published_at&&!hit.platform){const b=button('Check article date',async()=>{b.disabled=true;b.textContent='Checking date…';try{const r=await api(native()&&!state.connected?'/api/device/publication':'/api/publication','POST',{url:hit.url});if(!box.isConnected)return;Object.assign(hit,r);box.replaceChildren(...publicationDates(hit).childNodes);if(!r.published_at)box.append(el('p','coverage',r.date_status==='conflicting_metadata'?'Source metadata gives conflicting dates. Review the original article.':'No explicit publication date found in this source’s metadata.'));}catch(e){b.textContent='Date unavailable';box.append(el('p','coverage',e.message))}},'small');box.append(b)}return box;
}
analyticsReady.then(()=>{if(typeof partyState!=='undefined'&&partyState.data){renderPartyOverview();if(partyState.current&&!partyState.member)renderPartyAnalytics(partyState.current)}});
