'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import SiteNav from '@/components/SiteNav';
import SiteFooter from '@/components/SiteFooter';

function RequestTownInner() {
  const params = useSearchParams();
  const [town, setTown] = useState('');
  const [email, setEmail] = useState('');
  const [note, setNote] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  // Prefill town from search query when arriving via /request-town?city=Provo
  useEffect(() => {
    const fromQuery = params.get('city');
    if (fromQuery) setTown(fromQuery);
  }, [params]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus('submitting');
    setErrorMsg('');

    try {
      const r = await fetch('/api/request-town', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ town, email, note }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        setErrorMsg(j.error || 'Something went wrong');
        setStatus('error');
        return;
      }
      setStatus('success');
    } catch (err) {
      setErrorMsg('Network error. Try again?');
      setStatus('error');
    }
  }

  return (
    <>
      <SiteNav />
      <div className="rt-page">
        <div className="rt-card">
          {/* Chooser: event vs town request — matches /submit */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
            marginBottom: 32, padding: 6,
            background: 'rgba(83,74,183,0.06)',
            borderRadius: 16,
          }}>
            <a href="/submit" style={{
              padding: '14px 18px',
              borderRadius: 12,
              textAlign: 'center',
              fontWeight: 600,
              fontSize: 14,
              color: '#6B7280',
              textDecoration: 'none',
              transition: 'background 0.15s',
            }}
            onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.6)'; }}
            onMouseOut={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              📅 Submit an event
            </a>
            <div style={{
              padding: '14px 18px',
              background: 'white',
              borderRadius: 12,
              textAlign: 'center',
              fontWeight: 600,
              fontSize: 14,
              color: '#1e1b3a',
              boxShadow: '0 2px 6px rgba(83,74,183,0.08)',
            }}>
              📍 Request a new town
            </div>
          </div>

          <div className="rt-eyebrow">Request a town</div>
          <h1>Tell us where you live.</h1>
          <p className="rt-sub">
            We&apos;ll start pulling local events for your community and let
            you know when it&apos;s live. Free, always.
          </p>

          {status === 'success' ? (
            <div className="rt-success">
              <div className="rt-success-icon">✓</div>
              <h2>Got it.</h2>
              <p>
                We&apos;ll reach out at <strong>{email}</strong> when{' '}
                <strong>{town}</strong> is ready. Thanks for the nudge.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="rt-form">
              <label>
                <span>Your town</span>
                <input
                  type="text"
                  value={town}
                  onChange={(e) => setTown(e.target.value)}
                  placeholder="e.g. Telluride, CO"
                  required
                  autoFocus={!town}
                />
              </label>
              <label>
                <span>Your email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </label>
              <label>
                <span>Anything we should know? (optional)</span>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Local sources we should check, what kinds of events matter to you, etc."
                  rows={4}
                />
              </label>
              {errorMsg && <div className="rt-error">{errorMsg}</div>}
              <button type="submit" disabled={status === 'submitting'}>
                {status === 'submitting' ? 'Sending…' : 'Request this town'}
              </button>
            </form>
          )}
        </div>
      </div>
      <SiteFooter />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); }
        .rt-page { min-height: 70vh; padding: 100px 24px 80px; display: flex; justify-content: center; }
        .rt-card {
          width: 100%; max-width: 560px;
          background: white; border: 1px solid var(--border);
          border-radius: 24px; padding: 48px;
        }
        .rt-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(83,74,183,0.08); color: var(--purple);
          font-size: 12px; font-weight: 700; padding: 6px 14px;
          border-radius: 100px; margin-bottom: 20px;
          letter-spacing: 0.5px;
        }
        .rt-card h1 {
          font-family: 'DM Serif Display', serif;
          font-size: 36px; line-height: 1.15;
          margin-bottom: 12px;
        }
        .rt-sub { color: var(--muted); font-size: 15px; margin-bottom: 32px; line-height: 1.6; }
        .rt-form { display: flex; flex-direction: column; gap: 18px; }
        .rt-form label { display: flex; flex-direction: column; gap: 6px; }
        .rt-form label span {
          font-size: 12px; font-weight: 600; color: var(--muted);
          text-transform: uppercase; letter-spacing: 0.5px;
        }
        .rt-form input, .rt-form textarea {
          font-family: inherit; font-size: 15px;
          padding: 12px 14px;
          border: 1px solid var(--border);
          border-radius: 10px;
          background: white;
          color: var(--text);
        }
        .rt-form input:focus, .rt-form textarea:focus {
          outline: none; border-color: var(--purple);
        }
        .rt-form button {
          margin-top: 8px;
          background: var(--purple); color: white;
          padding: 14px 24px;
          border: none; border-radius: 100px;
          font-size: 15px; font-weight: 600;
          cursor: pointer; transition: background 0.2s;
        }
        .rt-form button:hover { background: var(--purple-light); }
        .rt-form button:disabled { opacity: 0.6; cursor: wait; }
        .rt-error {
          color: #c0392b; font-size: 14px;
          background: rgba(192,57,43,0.08);
          padding: 10px 14px; border-radius: 8px;
        }
        .rt-success { text-align: center; padding: 16px 0 8px; }
        .rt-success-icon {
          width: 56px; height: 56px; border-radius: 50%;
          background: rgba(46,160,67,0.12); color: #2ea043;
          font-size: 28px; line-height: 56px;
          margin: 0 auto 16px;
        }
        .rt-success h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 28px; margin-bottom: 10px;
        }
        .rt-success p { color: var(--muted); font-size: 15px; line-height: 1.6; }
      `}</style>
    </>
  );
}


export default function RequestTownPage() {
  return (
    <Suspense fallback={<div style={{minHeight:'70vh'}} />}>
      <RequestTownInner />
    </Suspense>
  );
}
