import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'For Businesses — List & Promote Your Events | Yoocal',
  description: 'List your events free on Yoocal, or get featured placement in front of locals and visitors searching for things to do. Simple daily pricing, cancel any time.',
  alternates: { canonical: 'https://www.yoocal.com/for-businesses' },
}

export default function ForBusinessesPage() {
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

      <section className="biz-section" id="business" style={{ paddingTop: '120px' }}>
        <div className="section-label">For businesses</div>
        <h2>Get your events <em>found</em></h2>
        <p style={{ fontSize: '17px', color: 'var(--muted)', maxWidth: '480px', lineHeight: 1.7, fontWeight: 300, marginBottom: 0 }}>
          List your events free, or get featured placement in front of everyone looking for things to do.
        </p>
        <div className="biz-cards" style={{ marginTop: '48px' }}>
          <div className="biz-card">
            <div className="biz-price">Free</div>
            <div className="biz-name">Basic listing</div>
            <div className="biz-desc">Your events automatically pulled from public sources, or submit manually.</div>
            <ul className="biz-features"><li>Event listed in the calendar</li><li>Links to your registration page</li><li>Category &amp; date filtering</li><li>Sourced &amp; attributed to you</li></ul>
            <a href="/submit" className="biz-btn">Submit your event</a>
          </div>
          <div className="biz-card featured-card">
            <div className="biz-price">$0.99<span>/day</span></div>
            <div className="biz-name">Featured placement</div>
            <div className="biz-desc">Pin your events to the top of the calendar with a Featured badge on your event day.</div>
            <ul className="biz-features"><li>Top-of-calendar placement</li><li>⭐ Featured badge on your events</li><li>Priority in newsletter</li><li>Cancel any time</li></ul>
            <a href="mailto:hello@yoocal.com" className="biz-btn">Get featured →</a>
          </div>
          <div className="biz-card">
            <div className="biz-price">$9.99<span>/day</span></div>
            <div className="biz-name">Partner sponsor</div>
            <div className="biz-desc">Category sponsorship and newsletter placement for maximum visibility.</div>
            <ul className="biz-features"><li>Category sponsorship</li><li>Weekly newsletter slot</li><li>Featured badge on all events</li><li>Monthly performance report</li><li>Cancel any time</li></ul>
            <a href="mailto:hello@yoocal.com" className="biz-btn">Contact us →</a>
          </div>
        </div>
      </section>
    </>
  )
}
