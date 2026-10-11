import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { sitemapFilter } from './src/lib/sitemap-filter.mjs';

export default defineConfig({
  site: 'https://investeringskunskap.se',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: [mdx(), sitemap({ filter: sitemapFilter })],
  image: { layout: 'constrained' },
});
