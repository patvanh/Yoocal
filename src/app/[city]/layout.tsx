// Scoped layout for city pages (/park-city, /heber, etc.). Sets a dark
// background at the route level so the page paints dark on first frame
// (no white FOUC on refresh). Does NOT affect light pages (About, etc.)
// which keep the white body background from globals.css.
export default function CityLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#1a1830', minHeight: '100vh', width: '100%', overflowX: 'clip' }}>
      {children}
    </div>
  )
}
