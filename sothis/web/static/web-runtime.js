'use strict';
// Installed before the shared features capture their transport and call boot().
// Server cookies are the only credentials. Never read a phone/legacy API token.
localStorage.removeItem('za-engine');
const workspaceSession = fetch('/api/session', {credentials: 'same-origin', cache: 'no-store'})
  .then(async response => {
    if (!response.ok) throw new Error('The workspace server is unavailable.');
    const session = await response.json();
    if (!session.authenticated) { location.replace('/login'); throw new Error('Sign in again.'); }
    return session;
  });
api = async function(path, method='GET', data) {
  if (!path.startsWith('/api/') || path.includes('://')) throw new Error('Use the workspace server.');
  const session = await workspaceSession;
  const response = await fetch(path, {method, credentials: 'same-origin', cache: 'no-store',
    headers: {'Content-Type': 'application/json', ...(method === 'POST' ? {'X-Sothis-CSRF': session.csrf} : {})},
    ...(method === 'POST' ? {body: JSON.stringify(data || {})} : {})});
  if (response.status === 401) { location.replace('/login'); throw new Error('Your session expired. Sign in again.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The server could not complete this request.');
  return result;
};
const sharedBoot = boot;
boot = async function() {
  try {
    await workspaceSession;
    await sharedBoot();
    if (!state.connected) throw new Error('The engine is unavailable. Refresh the page after checking server health.');
    state.config = {configured: true};
  } catch (exception) {
    notice('search-note', exception.message, true);
    $('status').lastChild.textContent = 'SERVER UNAVAILABLE';
  }
};
