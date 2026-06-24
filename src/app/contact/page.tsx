import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Contact | Yoocal',
  description: 'Get in touch with Yoocal — report an event error, ask about featured placements, or request a new city.',
  alternates: { canonical: 'https://www.yoocal.com/contact' },
}

export default function ContactPage() {
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
        <div className="legal-kicker">Contact</div>
        <h1 className="legal-title">Get in <em>touch</em></h1>
        <p className="legal-lede">Yoocal is an independent local-events calendar for resort and mountain towns. The fastest way to reach us is email.</p>
        <div className="legal-body">
          <div className="legal-row">
            <h3>General &amp; support</h3>
            <p><a href="mailto:hello@yoocal.com">hello@yoocal.com</a> — we read everything.</p>
          </div>
          <div className="legal-row">
            <h3>Report an event error</h3>
            <p>Found a wrong date, time, or price? Email us the event name and city and we’ll fix it.</p>
          </div>
          <div className="legal-row">
            <h3>List or promote an event</h3>
            <p>Submit a free listing on our <a href="/submit">submit page</a>, or see <a href="/for-businesses">for businesses</a> for featured placement.</p>
          </div>
          <div className="legal-row">
            <h3>Request a new city</h3>
            <p>Want Yoocal in your town? <a href="/request-town">Request a city</a> and tell us where.</p>
          </div>
        </div>
      </div>

      <style>{`
        .legal-wrap { max-width: 720px; margin: 0 auto; padding: 120px 24px 80px; }
        .legal-kicker { font-size: 12px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #b9aef5; }
        .legal-title { font-family: 'DM Serif Display', serif; font-size: 40px; line-height: 1.1; color: #fff; margin: 14px 0 6px; }
        .legal-title em { color: #b9aef5; font-style: italic; }
        .legal-lede { font-size: 17px; line-height: 1.7; color: rgba(255,255,255,0.6); margin: 8px 0 40px; max-width: 560px; }
        .legal-body { font-size: 16px; line-height: 1.7; color: rgba(255,255,255,0.78); }
        .legal-body h3 { font-family: 'DM Serif Display', serif; font-size: 19px; font-weight: 600; color: #fff; margin: 0 0 6px; }
        .legal-row { padding: 0 0 24px; margin: 0 0 24px; border-bottom: 1px solid rgba(255,255,255,0.08); }
        .legal-row:last-child { border-bottom: none; }
        .legal-body a { color: #b9aef5; text-decoration: none; border-bottom: 1px solid rgba(185,174,245,0.35); transition: border-color 0.15s; }
        .legal-body a:hover { border-bottom-color: #b9aef5; }
      `}</style>
    </>
  )
}
