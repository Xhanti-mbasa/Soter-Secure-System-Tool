'use strict';

// The same dock contract is used by the packaged app and self-hosted website.
function createNavigationDock() {
 const dock=document.querySelector('.navinner');
 dock.replaceChildren();
 for(const [name,label,asset] of [['home','HOME','newspaper'],['regions','REGIONS','map-trifold'],['opportunities','JOBS','briefcase'],['profile','PROFILE','users-three']]) {
  const b=button('',()=>tab(name));b.dataset.tab=name;
  b.setAttribute('aria-label',label==='JOBS'?'Jobs':label[0]+label.slice(1).toLowerCase());
  const glyph=icon(asset);glyph.classList.add('dock-icon');
  b.append(glyph,el('span','dock-label',label));dock.append(b);
 }
 const search=document.querySelector('.search-orb');
 search.replaceChildren();const glyph=icon('magnifying-glass');glyph.classList.add('dock-icon');search.append(glyph);
 updateDock();
}

function updateDock() {
 const dock=document.querySelector('.nav');if(!dock)return;
 const selected=state.tab==='settings'?'profile':state.tab;
 let active=false;
 for(const b of dock.querySelectorAll('.navinner [data-tab]')) {
  const current=b.dataset.tab===selected;active=active||current;
  b.classList.toggle('active',current);
  if(current)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');
 }
 dock.classList.toggle('unassigned',!active);
 // A dossier has no inline query; its directory and party roster do.
 const inlineSearch=['home','search','sources','tenders','opportunities'].includes(state.tab)||(state.tab==='party'&&!partyState.member);
 dock.querySelector('.search-orb').hidden=inlineSearch;
 dock.classList.toggle('search-hidden',inlineSearch);
}

// Browser visual viewport support complements Android's native IME signal.
const dockKeyboard={native:false,baseline:window.visualViewport?.height||innerHeight};
window.sothisKeyboard=function(visible){dockKeyboard.native=!!visible;updateDockKeyboard();};
function updateDockKeyboard() {
 const viewport=window.visualViewport,height=viewport?.height||innerHeight;
 const editable=document.activeElement?.matches('textarea,[contenteditable=true],input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=file]):not([type=button]):not([type=submit])');
 // Pinch zoom changes the viewport too, but is not an open keyboard.
 const resized=(viewport?.scale||1)===1&&dockKeyboard.baseline-height>120;
 const open=dockKeyboard.native||!!(editable&&resized);
 document.body.classList.toggle('keyboard-open',open);
 if(!open&&!editable)dockKeyboard.baseline=height;
}
window.visualViewport?.addEventListener('resize',updateDockKeyboard);
window.addEventListener('resize',updateDockKeyboard);
document.addEventListener('focusin',updateDockKeyboard);
document.addEventListener('focusout',()=>requestAnimationFrame(updateDockKeyboard));
window.addEventListener('orientationchange',()=>{dockKeyboard.baseline=window.visualViewport?.height||innerHeight;updateDockKeyboard();});
