import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "About Green Lake, Wisconsin — Yoocal",
  description:
    "Everything you need to know about Green Lake, Wisconsin — the deepest natural inland lake in the state and the Midwest's original summer resort town. Golf, boating, concerts, local events, best times to visit, and insider tips from Yoocal.",
  alternates: { canonical: "https://www.yoocal.com/about/green-lake" },
  openGraph: {
    title: "About Green Lake, Wisconsin — Yoocal",
    description:
      "Wisconsin's deepest lake, championship golf, summer concerts, and small-town charm — what to know before you visit.",
    url: "https://www.yoocal.com/about/green-lake",
    type: "website",
  },
};

const SUMMER_HIGHLIGHTS = [
  { dates: "Year-round", title: "Championship Golf", desc: "Four acclaimed courses — Lawsonia (with its famous links course), Mascoutin, Tuscumbia (Wisconsin's oldest course, 1896), and White Lake", major: true },
  { dates: "Summer", title: "Boating & Sailing", desc: "Seven miles of open, spring-fed water — ideal for sailing, fishing, paddleboarding, and even scuba diving on the state's deepest lake", major: true },
  { dates: "Summer", title: "Concerts in the Park", desc: "Free outdoor music all season long, plus shows at the restored 1910 Thrasher Opera House downtown", major: true },
  { dates: "Saturdays", title: "Princeton Flea Market", desc: "Wisconsin's largest outdoor weekly flea market — 12 acres, hundreds of vendors, late April through mid-October, just 10 miles west", major: false },
  { dates: "Late May", title: "Rubber Chicken Fling", desc: "Princeton's beloved quirky festival — rubber-chicken tossing, live music, food, and a big craft fair", major: false },
  { dates: "Summer", title: "Festivals & Outdoor Events", desc: "Art fairs, farmers markets, lakeside celebrations, and community events fill the calendar from June through September", major: false },
];

const AREA_CARDS = [
  { title: "Lawsonia", body: "One of the Midwest's most celebrated golf destinations. The Links Course is a Golden Age classic with dramatic elevated greens and deep bunkers; the Woodlands Course winds through forest and wetland. A bucket-list stop for serious golfers." },
  { title: "Green Lake itself", body: "The deepest natural inland lake in Wisconsin at 237 feet, stretching 7 miles with 27+ miles of shoreline. Spring-fed, jade-colored, and glacier-carved 12,000 years ago. Boating, sailing, fishing, swimming, and scuba diving." },
  { title: "Thrasher Opera House", body: "A lovingly restored 1910 theater in the heart of downtown Green Lake. Live music, comedy, and community performances year-round — a cultural anchor for the whole area." },
  { title: "Town Square Community Center", body: "The historic red-brick heartbeat of Green Lake. Home to community events, classes, and gatherings — the civic center of a town that prides itself on its sense of community." },
  { title: "Princeton, WI", body: "Ten miles west on the Fox River: Wisconsin's largest outdoor flea market, two antique malls, Amish shops, eclectic boutiques, and Fox River dining at spots like Horseradish Kitchen and Molly's Buckhorn Bar & Grill." },
  { title: "Parks & Trails", body: "Nine public parks, 221 miles of biking trails, and 7+ miles of hiking trails surround the lake — including Hattie Sherwood Park and the wooded campground on a glacial esker once held sacred by Native tribes." },
];

const TIPS = [
  { title: "Summer is the season", body: "Green Lake comes alive June through September — concerts in the park, boating, golf, and special events nearly every weekend. The town has welcomed summer visitors since the 1860s, and the rhythm hasn't changed much." },
  { title: "Book tee times early", body: "The area's four courses — especially Lawsonia — draw golfers from across the Midwest. Summer weekend tee times and golf-package stays fill up fast. Reserve well ahead." },
  { title: "You'll want a car", body: "Green Lake is about a 90-minute drive from Milwaukee and roughly 3.5 hours from Chicago. There's no public transit, and the best of the area — Princeton, the golf courses, the parks — is spread around the lake." },
  { title: "Get on the water", body: "Rent a boat, kayak, or paddleboard at the Green Lake Marina, or book a sailing charter. At 237 feet deep with exceptional clarity, the lake even draws scuba divers — a rarity for an inland Wisconsin lake." },
  { title: "Saturday is for Princeton", body: "Time a Saturday-morning trip to Princeton's flea market (6am–1pm, City Park, late April–mid-October), then explore the antique malls and Amish shops downtown. It's the area's best vintage-shopping day." },
  { title: "Stay near the lake", body: "Lakefront lodging and historic resorts put you steps from the water and downtown. Green Lake has hosted vacationers since it became the first summer resort town west of Niagara Falls — the hospitality runs deep." },
];

export default function AboutGreenLakePage() {
  return (
    <>
      <SiteNav activeKey="about" cityKey="greenlake" />

      <div className="hero">
        <div className="hero-inner-gl">
          <div className="hero-content-gl">
            <div className="hero-place-title-gl">Green Lake, Wisconsin</div>
            <h1>
              The Midwest&apos;s <em>original</em> lake escape.
            </h1>
            <p>
              On the shores of Wisconsin&apos;s deepest natural lake — the
              first resort community west of Niagara Falls. Championship golf,
              jade-colored water, and concerts in the park, all at a gentler
              pace.
            </p>
          </div>
          <div className="hero-image-gl"><img src="/green-lake-hero.webp" alt="Aerial view of Green Lake, Wisconsin" /></div></div></div>

      <div className="content">
        <div className="intro">
          <div className="intro-text">
            <h2>Deep water, deep roots.</h2>
            <p>
              Green Lake anchors the small city of the same name in
              south-central Wisconsin, about 90 minutes from Milwaukee. The
              lake itself is the star: 237 feet deep — the deepest natural
              inland lake in the state — stretching seven miles with more
              than 27 miles of shoreline that ranges from sandstone bluffs to
              quiet marsh.
            </p>
            <p>
              Formed by glaciers some 12,000 years ago and long held sacred
              by the Ho-Chunk, Menominee, and Potawatomi peoples, the lake
              became a resort destination in the 1860s, when railroads
              carried Chicago and Milwaukee vacationers north to its cool,
              clear waters. The grand hotels have changed, but the draw — the
              lake, the golf, the small-town warmth — hasn&apos;t.
            </p>
          </div>
          <div className="intro-stats">
            <div className="stat-card">
              <span className="num">237</span>
              <div className="label">Feet deep — WI&apos;s deepest natural lake</div>
            </div>
            <div className="stat-card">
              <span className="num">4</span>
              <div className="label">Area golf courses</div>
            </div>
            <div className="stat-card">
              <span className="num">221</span>
              <div className="label">Miles of biking trails</div>
            </div>
            <div className="stat-card">
              <span className="num">9</span>
              <div className="label">Public parks</div>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Summer in Green Lake</div>
          <h2>
            The season the <em>whole town</em> waits for
          </h2>
          <p>
            Green Lake is a summer destination at heart. From June through
            September the calendar fills with golf, boating, free concerts,
            farmers markets, and festivals — both in town and across the
            surrounding Green Lake County countryside.
          </p>

          <div className="race-schedule">
            <h3>What summer looks like here</h3>
            <div className="sub">
              Golf · boating · concerts · markets · festivals — in town and around the lake
            </div>
            {SUMMER_HIGHLIGHTS.map((r) => (
              <div key={r.title} className="race-item">
                <div className="race-dates">{r.dates}</div>
                <div className="race-info">
                  <h4>{r.title}</h4>
                  <p>{r.desc}</p>
                </div>
                {r.major && <div className="race-badge major">Top pick</div>}
              </div>
            ))}
          </div>
        </div>

        <div className="section">
          <div className="section-label">Around the lake</div>
          <h2>
            Where to <em>spend your time</em>
          </h2>
          <p>
            The lake is the centerpiece, but the area rewards exploring —
            from Golden Age golf to a 1910 opera house to the largest flea
            market in Wisconsin just down the road in Princeton.
          </p>

          <div className="cards-grid">
            {AREA_CARDS.map((c) => (
              <div key={c.title} className="card">
                <div className="card-accent" aria-hidden="true"></div>
                <h3>{c.title}</h3>
                <p>{c.body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="section">
          <div className="section-label">Plan your visit</div>
          <h2>
            When to go & <em>what to know</em>
          </h2>
          <p>
            Green Lake is at its best from late spring through early fall,
            when the water warms, the courses open up, and the events
            calendar runs full.
          </p>

          <div className="tips-grid">
            {TIPS.map((t) => (
              <div key={t.title} className="tip">
                <h4>{t.title}</h4>
                <p>{t.body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="cta-banner">
          <h2>
            See what&apos;s happening <em>this weekend.</em>
          </h2>
          <p>Concerts, golf, markets, festivals, and more — all in one place.</p>
          <a href="/green-lake" className="cta-btn">
            Browse Green Lake events →
          </a>
        </div>
      </div>

      <SiteFooter cityLabel="Green Lake, Wisconsin" />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }

        .hero {
          background: var(--dark);
          padding: 120px 80px 80px;
          position: relative; overflow: hidden;
        }
        .hero::before {
          content: ''; position: absolute; inset: 0;
          background: linear-gradient(135deg, #0a1628 0%, #1a2840 50%, #0d1f35 100%);
        }
        .hero::after {
          content: ''; position: absolute; inset: 0;
          background: radial-gradient(ellipse 80% 60% at 20% 80%, rgba(83,74,183,0.25) 0%, transparent 70%);
        }
        .hero-inner-gl { position: relative; z-index: 2; max-width: 1200px; margin: 0 auto; display: flex; align-items: flex-start; gap: 60px; }
        .hero-content-gl { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 440px; }
        .hero-image-gl { flex: 1; min-width: 0; border-radius: 16px; overflow: hidden; box-shadow: 0 24px 64px rgba(0,0,0,0.5); }
        .hero-image-gl img { width: 100%; height: 440px; object-fit: cover; display: block; }
        .hero-place-title-gl {
          font-family: 'DM Serif Display', serif;
          color: var(--purple-light);
          font-size: clamp(52px, 7vw, 84px);
          font-weight: 400; line-height: 1.04;
          margin-bottom: 44px; display: block;
        }
        .hero-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9);
          font-size: 12px; font-weight: 600;
          padding: 5px 14px; border-radius: 100px;
          margin-bottom: 24px; letter-spacing: 0.5px;
          border: 1px solid rgba(255,255,255,0.15);
        }
        .hero h1 {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(26px, 3.2vw, 40px);
          color: white; line-height: 1.12; margin-bottom: 28px;
        }
        .hero h1 em { font-style: italic; color: var(--purple-light); }
        .hero p {
          font-size: 18px; color: rgba(255,255,255,0.6);
          line-height: 1.7; font-weight: 300; max-width: 560px;
          margin-top: auto;
        }

        .content { max-width: 1100px; margin: 0 auto; padding: 80px 40px; }

        .intro {
          display: grid; grid-template-columns: 1fr 1fr;
          gap: 80px; align-items: start; margin-bottom: 80px;
        }
        .intro-text h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 36px; margin-bottom: 20px;
        }
        .intro-text p { font-size: 16px; color: var(--muted); line-height: 1.8; margin-bottom: 16px; }
        .intro-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .stat-card {
          background: var(--purple-pale); border-radius: 16px;
          padding: 24px; text-align: center;
        }
        .stat-card .num {
          font-family: 'DM Serif Display', serif;
          font-size: 32px; color: var(--purple); display: block;
        }
        .stat-card .label { font-size: 12px; color: var(--muted); margin-top: 4px; }

        .section { margin-bottom: 72px; }
        .section-label {
          font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 1px; color: var(--amber);
          margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
        }
        .section-label::before {
          content: ''; width: 24px; height: 2px;
          background: var(--purple-light); display: inline-block;
        }
        .section h2 {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(28px, 4vw, 40px);
          margin-bottom: 16px; line-height: 1.2;
        }
        .section h2 em { font-style: italic; color: var(--purple); }
        .section p { font-size: 16px; color: var(--muted); line-height: 1.8; margin-bottom: 16px; max-width: 700px; }

        .cards-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 20px; margin-top: 28px;
        }
        .card {
          background: white; border: 1px solid var(--border);
          border-radius: 20px; padding: 28px; transition: all 0.2s;
        }
        .card:hover {
          border-color: var(--purple); transform: translateY(-3px);
          box-shadow: 0 12px 32px rgba(83,74,183,0.08);
        }
        .card-accent { width: 40px; height: 3px; background: var(--purple); border-radius: 0; margin-bottom: 16px; }
        .card h3 { font-size: 17px; font-weight: 600; margin-bottom: 8px; }
        .card p { font-size: 14px; color: var(--muted); line-height: 1.7; }

        .race-schedule {
          background: var(--dark); border-radius: 24px;
          padding: 48px; margin-top: 28px;
        }
        .race-schedule h3 {
          font-family: 'DM Serif Display', serif;
          font-size: 28px; color: white; margin-bottom: 8px;
        }
        .race-schedule .sub {
          font-size: 14px; color: rgba(255,255,255,0.4);
          margin-bottom: 32px;
        }
        .race-item {
          display: flex; align-items: flex-start; gap: 20px;
          padding: 16px 0;
          border-bottom: 1px solid rgba(255,255,255,0.07);
        }
        .race-item:last-child { border-bottom: none; }
        .race-dates {
          font-size: 12px; font-weight: 700; color: var(--amber);
          min-width: 90px; padding-top: 2px;
          text-transform: uppercase; letter-spacing: 0.5px;
        }
        .race-info { flex: 1; min-width: 0; }
        .race-info h4 { font-size: 15px; font-weight: 600; color: white; margin-bottom: 3px; }
        .race-info p { font-size: 13px; color: rgba(255,255,255,0.4); }
        .race-badge {
          margin-left: auto; font-size: 10px; font-weight: 700;
          padding: 3px 10px; border-radius: 100px;
          background: rgba(83,74,183,0.3); color: var(--purple-light);
          white-space: nowrap; flex-shrink: 0;
        }
        .race-badge.major {
          background: rgba(239,159,39,0.2); color: var(--amber);
        }

        .tips-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 28px; }
        .tip {
          background: white; border: 1px solid var(--border);
          border-radius: 16px; padding: 24px;
        }
        .tip h4 { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
        .tip p { font-size: 14px; color: var(--muted); line-height: 1.7; }

        .cta-banner {
          background: var(--dark); border-radius: 24px;
          padding: 64px; text-align: center; margin-top: 80px;
        }
        .cta-banner h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 40px; color: white; margin-bottom: 16px;
          line-height: 1.2;
        }
        .cta-banner h2 em { font-style: italic; color: var(--purple-light); }
        .cta-banner p { color: rgba(255,255,255,0.5); font-size: 17px; margin-bottom: 32px; }
        .cta-btn {
          display: inline-block; background: var(--purple);
          color: white; padding: 14px 32px;
          border-radius: 100px; font-size: 15px; font-weight: 600;
          text-decoration: none; transition: background 0.2s;
        }
        .cta-btn:hover { background: var(--purple-light); }

        @media (max-width: 1100px) {
          .hero-inner-gl { flex-direction: column; gap: 24px; align-items: stretch; }
          .hero-content-gl { min-height: 0; }
          .hero p { margin-top: 16px; }
          .hero-image-gl img { height: 320px; }
        }
        @media (max-width: 768px) {
          .hero { padding: 100px 24px 60px; }
          .hero-image-gl img { height: 240px; }
          .content { padding: 48px 24px; }
          .intro { grid-template-columns: 1fr; gap: 40px; }
          .tips-grid { grid-template-columns: 1fr; }
          .race-schedule { padding: 32px 24px; }
          .cta-banner { padding: 48px 28px; }
        }
      `}</style>
    </>
  );
}
