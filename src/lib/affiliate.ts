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

const toLinear = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = ([r, g, b]: number[]) => 0.2126 * toLinear(r / 255) + 0.7152 * toLinear(g / 255) + 0.0722 * toLinear(b / 255);
const contrast = (a: number[], b: number[]) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const parse = (hex: string): number[] => {
  const m = /^#?([0-9a-f]{6})/i.exec(hex);
  return m ? [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)) : [51, 115, 220];
};
const toHex = (rgb: number[]) => '#' + rgb.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');

/**
 * Button colours from the original brand colour: picks white or black text and, if the pair is
 * below WCAG AA (4.5:1), nudges the background lighter/darker until it passes.
 */
export function buttonColors(bg: string): { bg: string; fg: string } {
  let rgb = parse(bg);
  const white = [255, 255, 255];
  const black = [0, 0, 0];
  const useWhite = contrast(rgb, white) >= contrast(rgb, black);
  const fg = useWhite ? white : black;
  for (let i = 0; i < 40 && contrast(rgb, fg) < 4.5; i++) {
    rgb = useWhite ? rgb.map((v) => v * 0.95) : rgb.map((v) => v + (255 - v) * 0.05);
  }
  return { bg: toHex(rgb), fg: toHex(fg) };
}

/**
 * Posts whose facts go stale fastest: affiliate boxes/links, tables with rates/fees/prices,
 * or "just nu"-style claims. These get the more prominent "not updated" note.
 */
export function goesStaleFast(source: string | undefined): boolean {
  if (!source) return false;
  if (hasAffiliate(source)) return true;
  if (/\b(just nu|i nuläget|för närvarande|för tillfället|i skrivande stund|skrivande stund)\b/i.test(source)) return true;
  const tables = source.match(/<HtmlTable html=\{"[^\n]*\} \/>/g) ?? [];
  return tables.some((t) => /(ränta|räntor|avgift|avkastning|courtage|pris|kurs)/i.test(t));
}
