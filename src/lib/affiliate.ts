// Affiliate / sponsored link detection. One place, used by the link renderer,
// the AffiliateBox component and the per-post disclosure.
const AFFILIATE_HOSTS = [
  /(^|\.)click\.adrecord\.com$/i,
  /(^|\.)track\.adtraction\.com$/i,
  /(^|\.)refunder\.se$/i, // referral links (…/b/<code>)
];

export function isAffiliateHref(href: string | undefined | null): boolean {
  if (!href) return false;
  let url: URL;
  try {
    url = new URL(href, 'https://investeringskunskap.se');
  } catch {
    return false;
  }
  if (AFFILIATE_HOSTS.some((re) => re.test(url.hostname))) return true;
  return url.searchParams.has('aff_id'); // TradingView
}

export const SPONSORED_REL = 'sponsored nofollow noopener';

export function isExternal(href: string | undefined | null): boolean {
  return !!href && /^https?:\/\//i.test(href) && !/^https?:\/\/(www\.)?investeringskunskap\.se(\/|$)/i.test(href);
}

export function relFor(href: string | undefined | null): string | undefined {
  if (isAffiliateHref(href)) return SPONSORED_REL;
  return isExternal(href) ? 'noopener' : undefined;
}

/** Does this MDX source contain affiliate boxes/buttons or affiliate links? */
export function hasAffiliate(source: string | undefined): boolean {
  if (!source) return false;
  if (/<AffiliateBox|<CtaButton/.test(source)) return true;
  const urls = source.match(/https?:\/\/[^\s)>"]+/g) ?? [];
  return urls.some(isAffiliateHref);
}

/** Readable text colour (black/white) for a button background. */
export function textOn(bg: string): string {
  const m = /^#?([0-9a-f]{6})/i.exec(bg);
  if (!m) return '#fff';
  const [r, g, b] = [0, 2, 4]
    .map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return 1.05 / (L + 0.05) >= (L + 0.05) / 0.05 ? '#fff' : '#111';
}
