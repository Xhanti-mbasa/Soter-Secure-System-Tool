'use strict';
// Photos enrich navigation and biographies; they do not verify a web candidate's identity.
let photoCredits=[];
const icon=(name)=>{const i=el('img','ui-icon');i.src='icons/'+name+'.svg';i.alt='';return i};
function portrait(member,large=false){
 const wrap=el('span','portrait'),initials=member.name.replace(/^(Mr|Ms|Mrs|Dr|Prof)\.?\s+/,'').split(/\s+/).filter(Boolean).map(n=>n[0]).slice(0,2).join('');
 const fallback=el('span','portrait-fallback',initials);fallback.setAttribute('aria-hidden','true');wrap.append(fallback);
 const bundled=typeof partyState!=='undefined'?partyState.data?.parties.flatMap(p=>p.members).find(m=>m.id===member.id):null;
 const candidate=member.image_url||bundled?.image_url||'';
 if(/^https:\/\/www\.parliament\.gov\.za\/storage\/app\/media\/MemberImages\/[\w.-]+\.(jpg|jpeg|png)$/i.test(candidate)){
  const image=el('img');image.alt=member.name+' · Parliament portrait';image.loading=large?'eager':'lazy';image.referrerPolicy='no-referrer';image.hidden=true;
  image.onload=()=>{fallback.hidden=true;image.hidden=false;wrap.classList.add('photo-loaded')};image.onerror=()=>{image.remove();fallback.hidden=false};image.src=candidate;wrap.append(image);
 }
 return wrap;
}
function decorateRegion(card,region,sources,passages){
 const photo=photoCredits.find(p=>p.region===region),copy=el('span','region-copy');
 if(photo){const i=el('img','region-photo');i.src=photo.file;i.alt=photo.place;i.loading='lazy';i.width=640;i.height=380;card.append(i)}
 else copy.append(el('span','region-number',String(['National',...provinces].indexOf(region)).padStart(2,'0')));
 copy.append(el('strong','',region),el('span','',sources+' sources · '+passages+' passages'));
 if(photo)copy.append(el('span','region-place',photo.place));card.append(copy);
}
function renderPhotoCredits(){
 const box=$('asset-credits');if(!box)return;box.replaceChildren();
 const unique=photoCredits.filter((p,i,a)=>a.findIndex(x=>x.file===p.file)===i);
 for(const p of unique){const row=el('p');const link=el('a','',p.title+' · '+p.author);link.href=p.source_url;link.onclick=e=>{e.preventDefault();openExternal(p.source_url)};row.append(link,document.createTextNode(' · '+p.license+'. '+p.changes));if(p.license_url){const license=el('a','',' License');license.href=p.license_url;license.onclick=e=>{e.preventDefault();openExternal(p.license_url)};row.append(license)}box.append(row)}
 box.append(el('p','','Representative portraits are loaded from Parliament’s published directory. When unavailable, initials are shown. Portraits are not evidence of account ownership. Doto: SIL Open Font License. Phosphor icons: MIT license. Simple Icons platform marks: CC0; trademarks belong to their owners.'));
 box.append(el('p','','Party charts adapt your Figma ring and rounded seat tiles from shatter prof. South Africa province boundaries: geoBoundaries / OCHA ROSEA / South African Municipal Demarcation Board, CC BY 3.0 IGO, 2020 boundaries. Election numbers: Parliament and IEC, with dates and original sources on each chart.'));
}
(async()=>{if(native()&&typeof Native.photoCredits==='function')return JSON.parse(Native.photoCredits());const r=await fetch('photo-credits.json');if(!r.ok)throw Error('Photo credits unavailable');return r.json()})().then(rows=>{photoCredits=rows;renderPhotoCredits();if(state.tab==='regions')renderRegions()}).catch(()=>{});
$('explore-country').onclick=()=>tab('regions');$('explore-party').onclick=()=>tab('party');
