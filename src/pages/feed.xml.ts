import type { APIRoute } from 'astro';
import { buildFeed } from '../lib/feed';

// /feed.xml (the old WordPress URL /feed/ is served by feed/index.html.ts with the same body).
export const GET: APIRoute = async () =>
  new Response(await buildFeed(), { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
