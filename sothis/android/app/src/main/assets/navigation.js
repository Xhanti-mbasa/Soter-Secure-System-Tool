'use strict';
// One screen history for browser Back and Android's native back gesture.
const navigationState={restoring:false,sequence:0,routes:[]};
function currentRoute(){return {tab:state.tab,party:state.tab==='party'?partyState.current?.code||partyState.member?.party_code||null:null,member:state.tab==='party'?partyState.member?.id||null:null,province:state.tab==='regions'?provinceState.current?.name||null:null}}
function sameRoute(a,b){return a&&b&&a.tab===b.tab&&a.party===b.party&&a.member===b.member&&(a.province||null)===(b.province||null)}
function recordRoute(){
 updateDock();if(navigationState.restoring)return;
 const route=currentRoute(),previous=navigationState.routes[navigationState.sequence];if(sameRoute(route,previous))return;
 navigationState.routes.splice(navigationState.sequence+1);navigationState.routes.push(route);navigationState.sequence++;
 const hash='#'+[route.tab,route.party,route.member,route.province].filter(Boolean).map(encodeURIComponent).join('/');
 history.pushState({sothis:route,sequence:navigationState.sequence},'',hash);
}
const navigationTab=tab,navigationPartyRender=renderParty,navigationMemberRender=renderPartyMember,navigationDirectory=renderPartyDirectory;
tab=function(name){navigationTab(name);recordRoute()};
renderParty=function(p){navigationPartyRender(p);recordRoute()};
renderPartyMember=function(m){navigationMemberRender(m);recordRoute()};
renderPartyDirectory=function(q){navigationDirectory(q);recordRoute()};
async function restoreRoute(route){
 navigationState.restoring=true;
 try{
  await partyReady;partyState.serial++;partyState.memberSerial++;notice('party-note','');
  if(route.tab==='party'){
   const p=partyState.data.parties.find(p=>p.code===route.party);
   const m=[...partyState.data.leaders||[],...partyState.data.parties.flatMap(p=>p.members)].find(m=>m.id===route.member);
   partyState.current=p||null;partyState.member=m?localMember(m):null;
   navigationTab('party');
   if(m){partyState.discoveries={};partyState.section='all';navigationMemberRender(partyState.member);loadMemberMentions('all')}
   else if(p)navigationPartyRender(p);
   else{$('party-query').value='';navigationDirectory('')}
  }else if(route.tab==='regions'){
   await provinceReady;provinceState.serial++;provinceState.current=provinceState.data?.provinces.find(p=>p.name===route.province)||null;
   navigationTab('regions');if(provinceState.current){provinceState.section='overview';renderProvince();loadProvinceNews()}
  }else tab(route.tab||'home');
  updateDock();
 }finally{navigationState.restoring=false}
}
function parentRoute(level){
 const party=partyState.member?.party_code||partyState.current?.code;
 const target=level==='party'?{tab:'party',party,member:null}:{tab:'party',party:null,member:null};
 if(sameRoute(navigationState.routes[navigationState.sequence-1],target)){history.back();return}
 restoreRoute(target).then(recordRoute);
}
function provinceParent(){
 const target={tab:'regions',party:null,member:null,province:null};
 if(sameRoute(navigationState.routes[navigationState.sequence-1],target)){history.back();return}
 restoreRoute(target).then(recordRoute);
}
window.sothisBack=function(){
 if(!$('overlay').hidden){closeDetail();return true}
 if(navigationState.sequence>0){history.back();return true}
 if(partyState.member&&state.tab==='party'){parentRoute('party');return true}
 if(partyState.current&&state.tab==='party'){parentRoute('directory');return true}
 if(provinceState.current&&state.tab==='regions'){provinceParent();return true}
 if(state.tab!=='home'){tab('home');return true}
 return false;
};
navigationState.routes=[currentRoute()];history.replaceState({sothis:currentRoute(),sequence:0},'','#'+state.tab);updateDock();
window.addEventListener('popstate',e=>{if(!e.state?.sothis)return;navigationState.sequence=e.state.sequence;restoreRoute(e.state.sothis)});
