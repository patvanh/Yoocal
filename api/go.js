export default function handler(req, res) {
  const { url } = req.query;

  if (!url) return res.redirect(302, 'https://yoocal.com');

  try {
    const parsed = new URL(url);
    res.setHeader('X-Redirect-Source', 'calendar');
    return res.redirect(302, parsed.href);
  } catch {
    return res.redirect(302, 'https://yoocal.com');
  }
}
