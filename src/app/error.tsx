'use client';

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error to the console / monitoring.
    console.error(error);
  }, [error]);

  return (
    <div className="err-wrap">
      <div className="err-card">
        <div className="err-eyebrow">Something went wrong</div>
        <h1>This page hit a snag.</h1>
        <p>
          We couldn&apos;t load this just now. It&apos;s usually temporary —
          try again, or head back to a city calendar.
        </p>
        <div className="err-actions">
          <button onClick={() => reset()} className="err-btn">
            Try again
          </button>
          <a href="/" className="err-link">
            Go home →
          </a>
        </div>
      </div>
      <style>{`
        .err-wrap {
          min-height: 70vh; display: flex; align-items: center;
          justify-content: center; padding: 40px 24px;
          font-family: 'DM Sans', sans-serif; background: var(--bg, #faf9fc);
        }
        .err-card {
          max-width: 460px; text-align: center;
          background: white; border: 1px solid var(--border, #eee);
          border-radius: 24px; padding: 48px 40px;
        }
        .err-eyebrow {
          display: inline-block; font-size: 12px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 1px;
          color: var(--amber, #b45309); margin-bottom: 16px;
        }
        .err-card h1 {
          font-family: 'DM Serif Display', serif;
          font-size: 32px; margin-bottom: 12px; color: var(--text, #1f2937);
        }
        .err-card p {
          font-size: 16px; color: var(--muted, #6b7280);
          line-height: 1.7; margin-bottom: 28px;
        }
        .err-actions {
          display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;
        }
        .err-btn {
          background: var(--purple, #534ab7); color: white; border: none;
          padding: 13px 28px; border-radius: 100px; font-size: 15px;
          font-weight: 600; cursor: pointer; font-family: inherit;
        }
        .err-btn:hover { background: var(--purple-light, #6b61d6); }
        .err-link {
          display: inline-flex; align-items: center;
          padding: 13px 28px; border-radius: 100px; font-size: 15px;
          font-weight: 600; text-decoration: none;
          color: var(--purple, #534ab7); border: 1px solid var(--border, #eee);
        }
        .err-link:hover { border-color: var(--purple, #534ab7); }
      `}</style>
    </div>
  );
}
