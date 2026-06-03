'use client';

import { useState } from 'react';

export default function ShareButtons({
  url,
  title,
}: {
  url: string;
  title: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard blocked — fall back to a prompt so the user can copy manually.
      window.prompt('Copy this link:', url);
    }
  };

  const enc = encodeURIComponent;
  const xUrl = `https://twitter.com/intent/tweet?text=${enc(title)}&url=${enc(url)}`;
  const fbUrl = `https://www.facebook.com/sharer/sharer.php?u=${enc(url)}`;
  const mailUrl = `mailto:?subject=${enc(title)}&body=${enc(title + '\n\n' + url)}`;

  return (
    <div className="share-row">
      <span className="share-label">Share</span>
      <button onClick={copy} className="share-btn" type="button">
        {copied ? '✓ Copied' : '🔗 Copy link'}
      </button>
      <a className="share-btn" href={xUrl} target="_blank" rel="noopener noreferrer">
        𝕏
      </a>
      <a className="share-btn" href={fbUrl} target="_blank" rel="noopener noreferrer">
        f
      </a>
      <a className="share-btn" href={mailUrl}>
        ✉
      </a>
      <style>{`
        .share-row {
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
          margin-bottom: 40px;
        }
        .share-label {
          font-size: 13px; font-weight: 600; color: var(--muted, #6b7280);
          margin-right: 2px;
        }
        .share-btn {
          display: inline-flex; align-items: center; justify-content: center;
          min-width: 40px; height: 40px; padding: 0 14px;
          border: 1px solid var(--border, #e5e3ef); border-radius: 100px;
          background: white; color: var(--text, #1f2937);
          font-size: 14px; font-weight: 600; cursor: pointer;
          text-decoration: none; font-family: inherit; transition: all 0.15s;
        }
        .share-btn:hover {
          border-color: var(--purple, #534ab7); color: var(--purple, #534ab7);
        }
      `}</style>
    </div>
  );
}
