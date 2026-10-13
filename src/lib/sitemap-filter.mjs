// Pages that must stay out of sitemap.xml (kept in plain JS: also imported by astro.config.mjs).
import { readdirSync, readFileSync } from 'node:fs';

const draftPages = new Set();
for (const f of readdirSync('src/content/pages')) {
  const fm = readFileSync(`src/content/pages/${f}`, 'utf8').split('\n---')[0];
  if (/^noindex:\s*true/m.test(fm)) draftPages.add(f.replace(/\.mdx$/, ''));
}

// Tags with a single post are noindexed (see src/pages/tag/[slug]/[...page].astro)
const thinTags = new Set();
try {
  const tax = JSON.parse(readFileSync('src/data/taxonomy.json', 'utf8'));
  for (const [slug, t] of Object.entries(tax.tags)) if (t.count <= 1) thinTags.add(slug);
} catch {}

export function sitemapFilter(url) {
  const path = new URL(url).pathname;
  const first = path.split('/').filter(Boolean);
  if (path === '/sok/' || path === '/404/' || path === '/hem/') return false;
  if (first.length === 1 && draftPages.has(first[0])) return false;
  if (first[0] === 'tag' && thinTags.has(first[1])) return false;
  return true;
}
