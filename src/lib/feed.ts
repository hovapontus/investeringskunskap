import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { loadRenderers } from 'astro:container';
import { getContainerRenderer as mdxRenderer } from '@astrojs/mdx';
import { render } from 'astro:content';
import { getImage } from 'astro:assets';
import { allPosts, categoryName } from './content';
import { feedComponents } from './feed-components';
import { SITE, abs } from './site';
import { getUpload } from './images';

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const cdata = (s: string) => `<![CDATA[${s.replace(/]]>/g, ']]]]><![CDATA[>')}]]>`;

/** Make site-relative URLs absolute and drop script/style blocks (feed readers ignore them anyway). */
function absolutize(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/\s(?:data-astro-cid-[\w-]+|loading|decoding|fetchpriority|sizes)="[^"]*"/g, '')
    .replace(/\s(href|src)="\/(?!\/)/g, (_m, a) => ` ${a}="${SITE.url}/`)
    .replace(/\ssrcset="([^"]*)"/g, (_m, v: string) =>
      ` srcset="${v.replace(/(^|,\s*)\/(?!\/)/g, (_x, p) => `${p}${SITE.url}/`)}"`,
    );
}

/** RSS 2.0 feed with the 10 newest posts, full content, same shape as the old WordPress feed. */
export async function buildFeed(): Promise<string> {
  const posts = (await allPosts()).slice(0, 10);
  const container = await AstroContainer.create({ renderers: await loadRenderers([mdxRenderer()]) });

  const items: string[] = [];
  for (const post of posts) {
    const { Content } = await render(post);
    let html = absolutize(await container.renderToString(Content, { props: { components: feedComponents } }));
    if (post.data.image) {
      const img = await getImage({ src: await getUpload(post.data.image), width: 1200, format: 'jpg' });
      html = `<p><img src="${abs(img.src)}" alt="${esc(post.data.imageAlt ?? '')}" /></p>\n` + html;
    }
    html += `\n<p>Inlägget <a href="${abs(`/${post.id}/`)}">${esc(post.data.title)}</a> dök först upp på <a href="${SITE.url}/">${SITE.name}</a>.</p>`;
    const wpGuid = post.data.wpId ? `${SITE.url}/?p=${post.data.wpId}` : abs(`/${post.id}/`);
    items.push(`    <item>
      <title>${esc(post.data.title)}</title>
      <link>${abs(`/${post.id}/`)}</link>
      <dc:creator>${cdata(post.data.author)}</dc:creator>
      <pubDate>${post.data.pubDate.toUTCString()}</pubDate>
${post.data.categories.map((c) => `      <category>${cdata(categoryName(c))}</category>`).join('\n')}
      <guid isPermaLink="false">${wpGuid}</guid>
      <description>${cdata(post.data.description)}</description>
      <content:encoded>${cdata(html)}</content:encoded>
    </item>`);
  }

  const built = (posts[0]?.data.updatedDate ?? posts[0]?.data.pubDate ?? new Date()).toUTCString();
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${SITE.name}</title>
    <atom:link href="${SITE.url}/feed/" rel="self" type="application/rss+xml" />
    <link>${SITE.url}/</link>
    <description>Allt om aktier, fonder och krypto</description>
    <lastBuildDate>${built}</lastBuildDate>
    <language>sv-SE</language>
${items.join('\n')}
  </channel>
</rss>
`;
}
