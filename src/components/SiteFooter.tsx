/**
 * SiteFooter — minimal designed footer matching the dark hero style.
 *
 * Props:
 *   cityLabel — optional city context to show in copyright line
 */
export default function SiteFooter({ cityLabel }: { cityLabel?: string }) {
  return (
    <>
      <footer className="yc-footer">
        <div className="yc-footer-bottom">
          <span>
            © 2026 Yoocal{cityLabel ? ` · ${cityLabel}` : ""}
          </span>
          <span>hello@yoocal.com</span>
        </div>
      </footer>

      <style>{`
        .yc-footer {
          background: var(--dark, #1a1830);
          color: white;
          padding: 40px 80px 28px;
        }
        .yc-footer-bottom {
          font-size: 13px;
          color: rgba(255,255,255,0.25);
          display: flex;
          justify-content: space-between;
          padding-top: 20px;
          border-top: 1px solid rgba(255,255,255,0.08);
        }
        @media (max-width: 768px) {
          .yc-footer { padding: 40px 24px 28px; }
          .yc-footer-bottom { flex-direction: column; gap: 8px; }
        }
      `}</style>
    </>
  );
}
