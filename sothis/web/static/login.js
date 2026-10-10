'use strict';
document.getElementById('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('sign-in'), error = document.getElementById('login-error');
  button.disabled = true;
  error.textContent = '';
  try {
    const response = await fetch('/auth/login', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: document.getElementById('username').value.trim(), password: document.getElementById('password').value})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Sign-in failed.');
    document.getElementById('password').value = '';
    location.replace('/');
  } catch (exception) {
    error.textContent = exception.message;
    button.disabled = false;
  }
});
