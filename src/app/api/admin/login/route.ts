import { NextResponse } from 'next/server'

// Admin login: compares submitted password to ADMIN_PASSWORD (server-only env),
// sets an httpOnly cookie on success. The cookie value is a shared secret token
// (ADMIN_SESSION_SECRET) so middleware can validate without re-checking the
// password. Both env vars are set in Vercel, never shipped to the client.
export async function POST(req: Request) {
  const { password } = await req.json().catch(() => ({ password: '' }))
  const expected = process.env.ADMIN_PASSWORD
  if (!expected) {
    return NextResponse.json({ error: 'Admin not configured' }, { status: 500 })
  }
  if (!password || password !== expected) {
    return NextResponse.json({ error: 'Incorrect password' }, { status: 401 })
  }
  const token = process.env.ADMIN_SESSION_SECRET || expected
  const res = NextResponse.json({ ok: true })
  res.cookies.set('yoocal_admin', token, {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * 7, // 7 days
  })
  return res
}
