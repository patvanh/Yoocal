import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service | Yoocal',
  description: 'The terms that govern use of Yoocal — our local-events calendar, event submissions, and featured placements.',
  alternates: { canonical: 'https://www.yoocal.com/terms' },
}

export default function TermsPage() {
  return (
    <>
      <nav>
        <a href="/" className="nav-logo"><div className="nav-dot" /> yoocal</a>
        <div className="nav-links">
          <a href="/about">About</a>
          <a href="/for-businesses">For businesses</a>
          <a href="https://forms.groupmail.info/subscribe/yoocal" target="_blank" rel="noopener noreferrer" className="nav-cta">Get notified</a>
        </div>
      </nav>
      <div className="legal-wrap">
        <div className="legal-kicker">Legal</div>
        <h1 className="legal-title">Terms of <em>Service</em></h1>
        <p className="legal-meta">Last updated: June 24, 2026</p>
        <div className="legal-body">
          <p>These terms govern your use of yoocal.com. By using the site, you agree to them.</p>
          <h3>What Yoocal is</h3>
          <p>Yoocal is a free local-events calendar that aggregates listings from public sources and from events submitted directly to us, provided for general convenience.</p>
          <h3>Accuracy of event information</h3>
          <p>Event details come from third-party sources and submitters and can change or contain errors. We don’t guarantee any listing is accurate, complete, or current. <strong>Always confirm details with the official organizer or venue before making plans or purchases.</strong> Yoocal is not responsible for events that are changed, canceled, sold out, or misrepresented.</p>
          <h3>Submitting events</h3>
          <p>If you submit an event, you confirm you have the right to share the information and that it’s accurate. We may edit, decline, or remove any submission at our discretion. Submitted events may be published, attributed, and displayed publicly.</p>
          <h3>Featured and partner placements</h3>
          <p>We offer paid promotional placements at the rates shown on our <a href="/for-businesses">for-businesses</a> page. Paid placement affects where and how an event appears, not the accuracy of its information. Fees, availability, and terms may change; specific arrangements are confirmed directly with us.</p>
          <h3>Acceptable use</h3>
          <p>Don’t use Yoocal to break the law, scrape or copy the site at scale without permission, submit false or misleading listings, or interfere with the site’s operation.</p>
          <h3>Third-party links</h3>
          <p>Listings link to external sites we don’t control and aren’t responsible for. Your use of those sites is governed by their own terms.</p>
          <h3>Disclaimer &amp; liability</h3>
          <p>Yoocal is provided “as is,” without warranties of any kind. To the fullest extent permitted by law, we’re not liable for any loss arising from your use of the site or reliance on any listing.</p>
          <h3>Changes</h3>
          <p>We may update these terms; continued use after changes means you accept them.</p>
          <h3>Contact</h3>
          <p>Questions? Email <a href="mailto:hello@yoocal.com">hello@yoocal.com</a> or see our <a href="/contact">contact page</a>.</p>
        </div>
      </div>

      <style>{`
        .legal-wrap { max-width: 720px; margin: 0 auto; padding: 120px 24px 80px; }
        .legal-kicker { font-size: 12px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #b9aef5; }
        .legal-title { font-family: 'DM Serif Display', serif; font-size: 40px; line-height: 1.1; color: #fff; margin: 14px 0 6px; }
        .legal-title em { color: #b9aef5; font-style: italic; }
        .legal-meta { font-size: 13px; color: rgba(255,255,255,0.4); margin: 0 0 40px; }
        .legal-body { font-size: 16px; line-height: 1.75; color: rgba(255,255,255,0.78); }
        .legal-body h3 { font-family: 'DM Serif Display', serif; font-size: 21px; font-weight: 600; color: #fff; margin: 38px 0 10px; }
        .legal-body p { margin: 0 0 16px; }
        .legal-body strong { color: rgba(255,255,255,0.95); font-weight: 600; }
        .legal-body a { color: #b9aef5; text-decoration: none; border-bottom: 1px solid rgba(185,174,245,0.35); transition: border-color 0.15s; }
        .legal-body a:hover { border-bottom-color: #b9aef5; }
      `}</style>
    </>
  )
}
