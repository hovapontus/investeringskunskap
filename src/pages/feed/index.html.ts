import type { APIRoute } from 'astro';
import { buildFeed } from '../../lib/feed';

// Emits dist/feed/index.html containing the RSS XML so that the old WordPress feed URL
// https://investeringskunskap.se/feed/ keeps working. public/_headers sets its Content-Type.
export const GET: APIRoute = async () =>
  new Response(await buildFeed(), { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
