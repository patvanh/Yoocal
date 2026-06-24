import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy | Yoocal',
  description: 'How Yoocal collects, uses, and protects information — including event submissions and newsletter signups.',
  alternates: { canonical: 'https://www.yoocal.com/privacy' },
}

export default function PrivacyPage() {
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
        <h1 className="legal-title">Privacy <em>Policy</em></h1>
        <p className="legal-meta">Last updated: June 24, 2026</p>
        <div className="legal-body">
          <p>Yoocal (“we,” “us”) operates yoocal.com, a free local-events calendar for resort and mountain towns. This policy explains what information we collect and how we use it.</p>
          <h3>Information we collect</h3>
          <p><strong>Event submissions.</strong> When you submit an event through our submission form, we collect the information you provide — which may include your name, email address, phone number, and details about your event. We use this to review, publish, and attribute the event, and to contact you about it if needed.</p>
          <p><strong>Newsletter signups.</strong> If you subscribe to our newsletter, we collect your email address to send you event updates. You can unsubscribe at any time using the link in any email.</p>
          <p><strong>Publicly available event data.</strong> Yoocal aggregates event listings from public sources (venue websites, chambers of commerce, public calendars). This information is already public; we attribute events to their original source.</p>
          <p><strong>Usage data.</strong> Like most websites, we collect basic analytics (pages viewed, general location, device type) to understand how the site is used and improve it. We use privacy-respecting analytics and do not sell this data.</p>
          <h3>How we use information</h3>
          <p>We use the information we collect to operate and improve Yoocal: to publish and attribute submitted events, send newsletters you’ve requested, respond to your messages, and understand site usage. We do not sell your personal information.</p>
          <h3>Sharing</h3>
          <p>We don’t sell or rent your personal information. We use a small number of third-party services to run the site (for example, hosting, email delivery, and analytics providers), which process data on our behalf. Event details you submit for publication are, by nature, shown publicly on the site.</p>
          <h3>Your choices</h3>
          <p>You can unsubscribe from emails at any time. To request access to, correction of, or deletion of personal information you’ve provided, email us at <a href="mailto:hello@yoocal.com">hello@yoocal.com</a> and we’ll respond promptly.</p>
          <h3>Children</h3>
          <p>Yoocal is not directed to children under 13, and we do not knowingly collect personal information from them.</p>
          <h3>Changes</h3>
          <p>We may update this policy from time to time; we’ll revise the “last updated” date above when we do.</p>
          <h3>Contact</h3>
          <p>Questions about this policy? Email <a href="mailto:hello@yoocal.com">hello@yoocal.com</a> or see our <a href="/contact">contact page</a>.</p>
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
