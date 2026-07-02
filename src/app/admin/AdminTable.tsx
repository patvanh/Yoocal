'use client';

import { useMemo, useState } from 'react';

type Row = {
  id: string; title: string; date: string; start_time: string; city: string;
  venue_name: string; location: string; source: string; image_url: string;
  link: string; categories: string[]; is_free: boolean | null;
  drift: boolean; overridden: boolean; manual: boolean;
};

const CITY_LABELS: Record<string, string> = {
  'park-city': 'Park City', 'heber': 'Heber', 'jackson-hole': 'Jackson',
  'elkhart-lake': 'Elkhart Lake', 'green-lake': 'Green Lake',
};

export default function AdminTable({ rows }: { rows: Row[] }) {
  const [q, setQ] = useState('');
  const [city, setCity] = useState('all');
  const [flag, setFlag] = useState('all');
  const [sort, setSort] = useState<'date' | 'title' | 'city' | 'source'>('date');

  const cities = useMemo(() => Array.from(new Set(rows.map((r) => r.city))).filter(Boolean).sort(), [rows]);

  const filtered = useMemo(() => {
    let out = rows;
    if (city !== 'all') out = out.filter((r) => r.city === city);
    if (flag === 'noimage') out = out.filter((r) => !r.image_url);
    else if (flag === 'novenue') out = out.filter((r) => !r.venue_name);
    else if (flag === 'drift') out = out.filter((r) => r.drift);
    else if (flag === 'overridden') out = out.filter((r) => r.overridden);
    else if (flag === 'manual') out = out.filter((r) => r.manual);
    const term = q.trim().toLowerCase();
    if (term) {
      out = out.filter((r) =>
        r.title.toLowerCase().includes(term) ||
        r.venue_name.toLowerCase().includes(term) ||
        r.location.toLowerCase().includes(term) ||
        r.source.toLowerCase().includes(term)
      );
    }
    out = [...out].sort((a, b) => {
      if (sort === 'date') return a.date.localeCompare(b.date);
      return (a[sort] || '').localeCompare(b[sort] || '');
    });
    return out;
  }, [rows, q, city, flag, sort]);

  const th: React.CSSProperties = { textAlign: 'left', padding: '8px 10px', fontSize: 12, color: '#8f8ab0', fontWeight: 600, borderBottom: '1px solid #2a2652', position: 'sticky', top: 0, background: '#1a1830' };
  const td: React.CSSProperties = { padding: '8px 10px', fontSize: 13, color: '#e6e3f5', borderBottom: '1px solid #221f42', verticalAlign: 'top' };
  const sel: React.CSSProperties = { padding: '8px 10px', borderRadius: 8, border: '1px solid #3a3470', background: '#26224a', color: '#fff', fontSize: 14 };

  return (
    <div style={{ minHeight: '100vh', background: '#141228', fontFamily: 'system-ui, sans-serif', padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 16 }}>
        <div style={{ color: '#b9aef5', fontWeight: 700, fontSize: 22 }}>yoocal admin</div>
        <div style={{ color: '#8f8ab0', fontSize: 14 }}>{filtered.length.toLocaleString()} of {rows.length.toLocaleString()} events</div>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, venue, source…" style={{ ...sel, flex: 1, minWidth: 220 }} />
        <select value={city} onChange={(e) => setCity(e.target.value)} style={sel}>
          <option value="all">All cities</option>
          {cities.map((c) => <option key={c} value={c}>{CITY_LABELS[c] || c}</option>)}
        </select>
        <select value={flag} onChange={(e) => setFlag(e.target.value)} style={sel}>
          <option value="all">All events</option>
          <option value="noimage">Missing image</option>
          <option value="novenue">Missing venue</option>
          <option value="drift">Drift flagged</option>
          <option value="overridden">Overridden</option>
          <option value="manual">Manually added</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} style={sel}>
          <option value="date">Sort: date</option>
          <option value="title">Sort: title</option>
          <option value="city">Sort: city</option>
          <option value="source">Sort: source</option>
        </select>
      </div>

      <div style={{ overflow: 'auto', border: '1px solid #2a2652', borderRadius: 10 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={th}>Date</th><th style={th}>Title</th><th style={th}>City</th>
              <th style={th}>Venue</th><th style={th}>Source</th><th style={th}>Flags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 500).map((r, i) => (
              <tr key={`${r.id}-${r.date}-${i}`}>
                <td style={{ ...td, whiteSpace: 'nowrap', color: '#b9aef5' }}>{r.date}{r.start_time ? <div style={{ color: '#6f6a95', fontSize: 11 }}>{r.start_time}</div> : null}</td>
                <td style={td}>{r.title}</td>
                <td style={{ ...td, whiteSpace: 'nowrap' }}>{CITY_LABELS[r.city] || r.city}</td>
                <td style={td}>{r.venue_name || <span style={{ color: '#6f6a95' }}>—</span>}</td>
                <td style={{ ...td, color: '#8f8ab0', fontSize: 12 }}>{r.source}</td>
                <td style={{ ...td, whiteSpace: 'nowrap' }}>
                  {!r.image_url ? <span title="no image" style={{ marginRight: 6 }}>NoImg</span> : null}
                  {r.drift ? <span title="drift" style={{ marginRight: 6 }}>Drift</span> : null}
                  {r.overridden ? <span title="overridden" style={{ marginRight: 6 }}>Edit</span> : null}
                  {r.manual ? <span title="manual" style={{ marginRight: 6 }}>Manual</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > 500 ? <div style={{ color: '#6f6a95', fontSize: 13, marginTop: 12 }}>Showing first 500. Narrow the filters to see more.</div> : null}
    </div>
  );
}
