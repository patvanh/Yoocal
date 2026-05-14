export default function handler(req, res) {
  const { url } = req.query;

  if (!url) return res.redirect(302, 'https://yoocal.com');

  try {
    const dest = new URL(decodeURIComponent(url));
    return res.redirect(302, dest.href);
  } catch {
    return res.redirect(302, 'https://yoocal.com');
  }
}
