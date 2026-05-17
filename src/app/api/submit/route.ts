import { NextRequest, NextResponse } from 'next/server';
import { Resend } from 'resend';

const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      title, date, startTime, endTime, location, description, link, city,
      category, priceType, price,
      submitterName, submitterEmail, submitterPhone, interestedInFeatured,
    } = body;

    // Required fields
    if (!title || !date || !location || !category || !city ||
        !submitterName || !submitterEmail || !submitterPhone) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(submitterEmail)) {
      return NextResponse.json({ error: 'Invalid email address' }, { status: 400 });
    }

    const featuredFlag = interestedInFeatured
      ? '⭐ INTERESTED IN FEATURED EVENT — follow up!\n\n'
      : '';

    const priceDisplay = priceType === 'paid'
      ? (price ? `Paid (${price})` : 'Paid (price not specified)')
      : 'Free';

    const emailBody = `${featuredFlag}New event submission for yoocal.com

EVENT DETAILS
City:        ${city}
Title:       ${title}
Category:    ${category}
Date:        ${date}
Time:        ${startTime || 'not specified'}${endTime ? ` - ${endTime}` : ''}
Location:    ${location}
Pricing:     ${priceDisplay}
Link:        ${link || 'none'}

Description:
${description || '(none)'}

SUBMITTED BY
Name:        ${submitterName}
Email:       ${submitterEmail}
Phone:       ${submitterPhone}
Featured interest: ${interestedInFeatured ? 'YES — wants to learn about featured events' : 'no'}

Submitted at: ${new Date().toISOString()}
    `.trim();

    const subjectPrefix = interestedInFeatured ? '[yoocal ⭐ FEATURED]' : '[yoocal submission]';
    const { error } = await resend.emails.send({
      from: 'yoocal submissions <submit@yoocal.com>',
      to: ['hello@yoocal.com'],
      replyTo: submitterEmail,
      subject: `${subjectPrefix} ${title} - ${date}`,
      text: emailBody,
    });

    if (error) {
      console.error('Resend error:', error);
      return NextResponse.json({ error: 'Failed to send email' }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error('Submit error:', err);
    return NextResponse.json({ error: 'Server error' }, { status: 500 });
  }
}
