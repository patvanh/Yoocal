import { NextRequest, NextResponse } from 'next/server';

// Protects /admin/* — redirects to /admin/login when the yoocal_admin cookie
// is missing or doesn't match the expected token. Login page + login API are
// exempt so the user can authenticate.
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isLogin = pathname === '/admin/login' || pathname === '/api/admin/login';
  if (isLogin) return NextResponse.next();

  const cookie = req.cookies.get('yoocal_admin')?.value;
  const expected = process.env.ADMIN_SESSION_SECRET || process.env.ADMIN_PASSWORD;
  if (!cookie || !expected || cookie !== expected) {
    const url = req.nextUrl.clone();
    url.pathname = '/admin/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/admin/:path*', '/api/admin/:path*'],
};
