export default function Loading() {
  return (
    <div className="load-wrap">
      <div className="load-spinner" />
      <div className="load-text">Loading your local…</div>
      <style>{`
        .load-wrap {
          min-height: 70vh; display: flex; flex-direction: column;
          align-items: center; justify-content: center; gap: 18px;
          font-family: 'DM Sans', sans-serif; background: var(--bg, #faf9fc);
        }
        .load-spinner {
          width: 40px; height: 40px; border-radius: 50%;
          border: 3px solid var(--border, #e5e3ef);
          border-top-color: var(--purple, #534ab7);
          animation: load-spin 0.8s linear infinite;
        }
        .load-text {
          font-size: 14px; color: var(--muted, #6b7280); font-weight: 500;
        }
        @keyframes load-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
