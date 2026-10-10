'use strict';
// Browser presentation over the shared Android UI; Android assets stay untouched.
const webStatus = setStatus;
setStatus = function() { webStatus(); $('status').lastChild.textContent = state.connected ? 'SERVER CONNECTED' : 'SERVER UNAVAILABLE'; };
const webTag = el('span', 'web-tag', 'WEB');
document.querySelector('.header-actions').prepend(webTag);
const settings = $('settings-panel');
settings.querySelector('h1').textContent = 'Your workspace.';
settings.querySelector('h1').nextElementSibling.textContent = 'Your server collects government sources, stores investigations and checks alerts while you are away.';
for (const id of ['engine-url','engine-token','search-key']) $(id).closest('.field').hidden = true;
$('connect').parentElement.hidden = true;
$('save-search-key').hidden = true;
settings.querySelector('h3').nextElementSibling.textContent = 'An optional Brave Search API key can be configured on the server. Live search otherwise uses the public provider and reports its availability.';
const account = el('div', 'web-account'), copy = el('p','muted','Private workspace · loading account…');
account.append(copy, button('Sign out', async () => {
  try {
    const session = await workspaceSession;
    const response = await fetch('/auth/logout', {method:'POST', credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-Sothis-CSRF':session.csrf}, body:'{}'});
    if (!response.ok) throw new Error('Sign-out failed. Try again.');
    daily.reader.stop();
    await daily.vault.clear().catch(()=>{});
    for (const key of Object.keys(localStorage)) if (key.startsWith('za-') || key.startsWith('sothis-')) localStorage.removeItem(key);
    location.replace('/login');
  } catch (error) { toast(error.message); }
}));
settings.querySelector('h1').nextElementSibling.after(account);
workspaceSession.then(session => { copy.textContent = 'Signed in as '+session.username+' · one private research workspace'; }).catch(() => {});
const sharedTools = toolsHome;
toolsHome = function() {
  sharedTools();
  const grid = $('tools-home').querySelector('.toolsgrid');
  const description = grid.nextElementSibling.nextElementSibling;
  description.textContent = 'Your server checks enabled rules while it runs. Changes appear in this inbox, including checks made while this website is closed.';
  const actions = description.nextElementSibling;
  // The alert inbox works without browser permission or an open tab.
  actions.lastElementChild.replaceWith(button('Alert delivery', () => {
    const box = modal('Your alert inbox');
    box.append(el('p','muted','Rules run on the server. Open Tools to review new or changed results. Closing the website does not pause your rules. This version does not send push notifications when the browser is closed.'));
  }));
};
archiveEvidence = async function(url, box) {
  const progress = el('div','note','Archiving original source…');
  box.append(progress);
  try {
    const file = await api('/api/evidence','POST',{url});
    const list = evidenceFiles().filter(item => item.sha256 !== file.sha256);
    list.push(file); saveLocal('sothis-evidence-files',list);
    progress.textContent = 'Archived '+file.bytes+' bytes · SHA-256 '+file.sha256;
    progress.className = 'note archivebadge';
    const link = el('a','small','Download original to this device');
    link.href = '/api/evidence/'+file.sha256+'/download'; link.download = '';
    progress.append(el('br'),link);
    link.click();
  } catch (error) { progress.className='note error'; progress.textContent=error.message; }
};
const webExport = exportCase;
exportCase = async function(caseRecord) {
  await webExport(caseRecord);
  const oldBundleButton = [...$('dialog').querySelectorAll('button')].find(item => item.textContent === 'Download evidence bundle');
  if (!oldBundleButton) return;
  oldBundleButton.onclick = async () => {
    oldBundleButton.disabled = true;
    try {
      const session = await workspaceSession;
      const report = (await api('/api/cases/'+caseRecord.id+'/export')).content;
      const documents = (caseRecord.pins || []).map(id => state.docs.get(id)).filter(Boolean);
      const response = await fetch('/api/bundle', {method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-Sothis-CSRF':session.csrf},
        body:JSON.stringify({title:caseRecord.title,report,documents,account_reviews:reviewed(),
          verification_notes:readLocal('sothis-review-notes',{}),evidence:evidenceForPins(documents)})});
      if (!response.ok) throw new Error((await response.json()).error || 'Bundle export failed.');
      const url = URL.createObjectURL(await response.blob()), link = el('a');
      link.href=url;link.download='sothis-evidence.zip';document.body.append(link);link.click();link.remove();
      setTimeout(() => URL.revokeObjectURL(url),1000);
    } catch(error) { noticeDialog(error.message); }
    finally { oldBundleButton.disabled=false; }
  };
};
