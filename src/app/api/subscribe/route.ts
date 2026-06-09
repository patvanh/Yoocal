import { NextRequest, NextResponse } from 'next/server';
import { Resend } from 'resend';

const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const email = typeof body?.email === 'string' ? body.email.trim() : '';

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json({ error: 'Invalid email address' }, { status: 400 });
    }

    const { error } = await resend.emails.send({
      from: 'yoocal signups <submit@yoocal.com>',
      to: ['hello@yoocal.com'],
      replyTo: email,
      subject: `[yoocal newsletter] New signup: ${email}`,
      text: `New newsletter signup from the homepage.\n\nEmail: ${email}\nSubmitted at: ${new Date().toISOString()}`,
    });

    if (error) {
      console.error('Resend error:', error);
      return NextResponse.json({ error: 'Failed to send' }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error('Subscribe error:', err);
    return NextResponse.json({ error: 'Server error' }, { status: 500 });
  }
}
