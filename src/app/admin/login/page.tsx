'use client';

import { useState } from 'react';

export default function AdminLogin() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError('');
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        const params = new URLSearchParams(window.location.search);
        window.location.href = params.get('next') || '/admin';
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.error || 'Login failed');
      }
    } catch {
      setError('Network error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#1a1830', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ width: 320, padding: 32, background: '#26224a', borderRadius: 12, boxShadow: '0 8px 40px rgba(0,0,0,0.3)' }}>
        <div style={{ color: '#b9aef5', fontWeight: 700, fontSize: 22, marginBottom: 4 }}>yoocal admin</div>
        <div style={{ color: '#8f8ab0', fontSize: 14, marginBottom: 24 }}>Enter the admin password to continue.</div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
          placeholder="Password"
          autoFocus
          style={{ width: '100%', boxSizing: 'border-box', padding: '10px 12px', borderRadius: 8, border: '1px solid #3a3470', background: '#1a1830', color: '#fff', fontSize: 15, marginBottom: 12 }}
        />
        {error ? <div style={{ color: '#ff8080', fontSize: 13, marginBottom: 12 }}>{error}</div> : null}
        <button
          onClick={submit}
          disabled={busy}
          style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: 'none', background: '#7f77dd', color: '#fff', fontSize: 15, fontWeight: 600, cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1 }}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </div>
    </div>
  );
}
