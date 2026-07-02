import { getAllEventsWithCity } from '@/lib/events';
import AdminTable from './AdminTable';

export const dynamic = 'force-dynamic';

export default function AdminPage() {
  const events = getAllEventsWithCity();
  // Strip heavy fields we don't need in the table to keep the payload sane.
  const rows = events.map((e) => ({
    id: e.id || '',
    title: e.title || '',
    date: (e.date || '').slice(0, 10),
    start_time: e.start_time || '',
    city: e.citySlug || '',
    venue_name: e.venue_name || '',
    location: e.location || '',
    source: e.source || '',
    image_url: e.image_url || '',
    link: e.link || '',
    categories: (e.filter_categories && e.filter_categories.length ? e.filter_categories : e.categories) || [],
    is_free: e.is_free ?? null,
    drift: !!e._drift,
    overridden: !!e._overridden,
    manual: !!e._manual_added,
  }));
  return <AdminTable rows={rows} />;
}
