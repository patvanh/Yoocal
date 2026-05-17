'use client';

import { useState } from 'react';

export default function SubmitEventPage() {
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [priceType, setPriceType] = useState<'free' | 'paid'>('free');

  // Time state — separate so AM/PM dropdowns work
  const [startHour, setStartHour] = useState('');
  const [startMinute, setStartMinute] = useState('00');
  const [startAmPm, setStartAmPm] = useState('PM');
  const [endHour, setEndHour] = useState('');
  const [endMinute, setEndMinute] = useState('00');
  const [endAmPm, setEndAmPm] = useState('PM');

  function buildTimeString(hour: string, minute: string, ampm: string): string {
    if (!hour) return '';
    return `${hour}:${minute} ${ampm}`;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus('submitting');
    setErrorMsg('');

    const form = e.currentTarget;
    const fd = new FormData(form);
    const payload = {
      city: fd.get('city'),
      title: fd.get('title'),
      category: fd.get('category'),
      date: fd.get('date'),
      startTime: buildTimeString(startHour, startMinute, startAmPm),
      endTime: buildTimeString(endHour, endMinute, endAmPm),
      location: fd.get('location'),
      description: fd.get('description'),
      link: fd.get('link'),
      priceType: fd.get('priceType'),
      price: fd.get('price'),
      submitterName: fd.get('submitterName'),
      submitterEmail: fd.get('submitterEmail'),
      submitterPhone: fd.get('submitterPhone'),
      interestedInFeatured: fd.get('interestedInFeatured') === 'on',
    };

    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus('error');
        setErrorMsg(data.error || 'Submission failed');
        return;
      }
      setStatus('success');
      form.reset();
      setPriceType('free');
      setStartHour(''); setStartMinute('00'); setStartAmPm('PM');
      setEndHour(''); setEndMinute('00'); setEndAmPm('PM');
    } catch {
      setStatus('error');
      setErrorMsg('Network error — please try again');
    }
  }

  return (
    <main style={{ paddingTop: 64, minHeight: '100vh', background: 'var(--bg, #faf9ff)' }}>
      <div style={{ maxWidth: 640, margin: '40px auto', padding: '0 24px 80px' }}>
        <h1 style={{ fontSize: 36, marginBottom: 8, color: '#1e1b3a', fontFamily: "'DM Serif Display', serif" }}>
          Submit an event
        </h1>
        <p style={{ color: '#6B7280', marginBottom: 32, fontSize: 16, lineHeight: 1.5 }}>
          Know about a Park City, Heber Valley, or Elkhart Lake event we&apos;re missing?
          Tell us about it. We&apos;ll review and add it within 24 hours.
        </p>

        {status === 'success' ? (
          <div style={{
            padding: 24, borderRadius: 12,
            background: 'rgba(34, 197, 94, 0.1)',
            border: '1px solid rgba(34, 197, 94, 0.3)',
            color: '#15803d',
          }}>
            <strong style={{ fontSize: 18 }}>Thanks!</strong>
            <p style={{ marginTop: 8 }}>We received your submission and will review it shortly.</p>
            <button
              onClick={() => setStatus('idle')}
              style={{
                marginTop: 12,
                background: 'transparent', border: '1px solid #15803d',
                color: '#15803d', padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
                fontSize: 14, fontWeight: 500,
              }}
            >
              Submit another
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <Section title="Event details">
              <Field label="City *">
                <select name="city" required style={inputStyle}>
                  <option value="">Select a city</option>
                  <option value="parkcity">Park City</option>
                  <option value="heber">Heber Valley</option>
                  <option value="elkhartlake">Elkhart Lake</option>
                  <option value="jackson">Jackson Hole</option>
                </select>
              </Field>

              <Field label="Event title *">
                <input type="text" name="title" required maxLength={200} style={inputStyle}
                  placeholder="e.g. Friday Night Jazz at the Egyptian" />
              </Field>

              <Field label="Category *">
                <select name="category" required style={inputStyle}>
                  <option value="">Select a category</option>
                  <option value="music">Music / Concert</option>
                  <option value="arts">Arts / Theatre / Film</option>
                  <option value="food">Food &amp; Drink</option>
                  <option value="sports">Sports / Race / Outdoor</option>
                  <option value="family">Family / Kids</option>
                  <option value="festival">Festival / Fair</option>
                  <option value="community">Community / Volunteer</option>
                  <option value="education">Class / Workshop / Education</option>
                  <option value="nightlife">Nightlife</option>
                  <option value="other">Other</option>
                </select>
              </Field>

              <Field label="Date *">
                <input type="date" name="date" required style={inputStyle} />
              </Field>

              <Field label="Start time">
                <div style={timeRowStyle}>
                  <select value={startHour} onChange={e => setStartHour(e.target.value)} style={timeSelectStyle}>
                    <option value="">--</option>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map(h => (
                      <option key={h} value={String(h)}>{h}</option>
                    ))}
                  </select>
                  <span style={timeColonStyle}>:</span>
                  <select value={startMinute} onChange={e => setStartMinute(e.target.value)} style={timeSelectStyle}>
                    <option value="00">00</option>
                    <option value="15">15</option>
                    <option value="30">30</option>
                    <option value="45">45</option>
                  </select>
                  <select value={startAmPm} onChange={e => setStartAmPm(e.target.value)} style={timeSelectStyle}>
                    <option value="AM">AM</option>
                    <option value="PM">PM</option>
                  </select>
                </div>
              </Field>

              <Field label="End time">
                <div style={timeRowStyle}>
                  <select value={endHour} onChange={e => setEndHour(e.target.value)} style={timeSelectStyle}>
                    <option value="">--</option>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map(h => (
                      <option key={h} value={String(h)}>{h}</option>
                    ))}
                  </select>
                  <span style={timeColonStyle}>:</span>
                  <select value={endMinute} onChange={e => setEndMinute(e.target.value)} style={timeSelectStyle}>
                    <option value="00">00</option>
                    <option value="15">15</option>
                    <option value="30">30</option>
                    <option value="45">45</option>
                  </select>
                  <select value={endAmPm} onChange={e => setEndAmPm(e.target.value)} style={timeSelectStyle}>
                    <option value="AM">AM</option>
                    <option value="PM">PM</option>
                  </select>
                </div>
              </Field>

              <Field label="Location / venue *">
                <input type="text" name="location" required maxLength={200} style={inputStyle}
                  placeholder="e.g. Egyptian Theatre, 328 Main St, Park City" />
              </Field>

              <Field label="Event link / website">
                <input type="url" name="link" style={inputStyle} placeholder="https://..." />
              </Field>

              <Field label="Description">
                <textarea name="description" rows={4} maxLength={1000}
                  style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
                  placeholder="What's the event about?" />
              </Field>

              <Field label="Pricing *">
                <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
                  <label style={radioLabel}>
                    <input type="radio" name="priceType" value="free" checked={priceType === 'free'}
                      onChange={() => setPriceType('free')} />
                    <span>Free</span>
                  </label>
                  <label style={radioLabel}>
                    <input type="radio" name="priceType" value="paid" checked={priceType === 'paid'}
                      onChange={() => setPriceType('paid')} />
                    <span>Paid</span>
                  </label>
                </div>
              </Field>

              {priceType === 'paid' && (
                <Field label="Price">
                  <input type="text" name="price" maxLength={50} style={inputStyle}
                    placeholder="e.g. $25, or $25-$50" />
                </Field>
              )}
            </Section>

            <Section title="Your contact info">
              <Field label="Your name *">
                <input type="text" name="submitterName" required maxLength={100}
                  style={inputStyle} placeholder="Full name" />
              </Field>

              <Field label="Email *">
                <input type="email" name="submitterEmail" required style={inputStyle}
                  placeholder="you@example.com" />
              </Field>

              <Field label="Phone *">
                <input type="tel" name="submitterPhone" required style={inputStyle}
                  placeholder="(555) 555-5555" />
              </Field>

              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginTop: 8, cursor: 'pointer' }}>
                <input type="checkbox" name="interestedInFeatured" style={{ marginTop: 4 }} />
                <span style={{ fontSize: 14, color: '#374151', lineHeight: 1.5 }}>
                  I&apos;d like to learn more about getting this event <strong>featured</strong> on yoocal
                </span>
              </label>
            </Section>

            {status === 'error' && (
              <div style={{ color: '#dc2626', fontSize: 14, padding: 12, background: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
                {errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={status === 'submitting'}
              style={{
                padding: '14px 24px', borderRadius: 12, border: 'none',
                background: status === 'submitting' ? '#9CA3AF' : '#534AB7',
                color: 'white', fontSize: 16, fontWeight: 600,
                cursor: status === 'submitting' ? 'wait' : 'pointer',
                marginTop: 8,
                transition: 'background 0.15s',
              }}
            >
              {status === 'submitting' ? 'Submitting…' : 'Submit event'}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: '#1e1b3a', marginTop: 8, marginBottom: 0 }}>{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>{label}</span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '10px 14px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  background: '#ffffff',
  color: '#111827',
  fontSize: 15,
  fontFamily: 'inherit',
  outline: 'none',
};

const timeRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

const timeSelectStyle: React.CSSProperties = {
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  background: '#ffffff',
  color: '#111827',
  fontSize: 15,
  fontFamily: 'inherit',
  outline: 'none',
  minWidth: 64,
};

const timeColonStyle: React.CSSProperties = {
  fontSize: 18,
  fontWeight: 600,
  color: '#6B7280',
};

const radioLabel: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  fontSize: 15,
  color: '#374151',
  cursor: 'pointer',
};
