import { getCollection, type CollectionEntry } from 'astro:content';
import taxonomy from '../data/taxonomy.json';

export type Post = CollectionEntry<'posts'>;
export type Page = CollectionEntry<'pages'>;

let cache: Post[] | undefined;
export async function allPosts(): Promise<Post[]> {
  cache ??= (await getCollection('posts')).sort((a, b) => b.data.pubDate.getTime() - a.data.pubDate.getTime());
  return cache;
}

export const categories = taxonomy.categories as Record<string, { name: string; parent: string | null; count: number }>;
export const tags = taxonomy.tags as Record<string, { name: string; count: number }>;

export const categoryName = (slug: string) => categories[slug]?.name ?? slug;
export const tagName = (slug: string) => tags[slug]?.name ?? slug;
/** WordPress category URLs are hierarchical: /category/krypto/nfts/ */
export const categoryPath = (slug: string) => {
  const parent = categories[slug]?.parent;
  return parent ? `${parent}/${slug}` : slug;
};
export const categoryUrl = (slug: string) => `/category/${categoryPath(slug)}/`;
export const tagUrl = (slug: string) => `/tag/${slug}/`;
export const postUrl = (p: { id: string }) => `/${p.id}/`;

export const inCategory = (posts: Post[], slug: string) => posts.filter((p) => p.data.categories.includes(slug));
export const withTag = (posts: Post[], slug: string) => posts.filter((p) => p.data.tags.includes(slug));

/** Posts sharing the most categories/tags with `post` (newest first on ties). */
export function related(post: Post, posts: Post[], n = 6): Post[] {
  const score = (o: Post) =>
    post.data.categories.filter((c) => o.data.categories.includes(c)).length * 2 +
    post.data.tags.filter((t) => o.data.tags.includes(t)).length +
    (o.data.primaryCategory === post.data.primaryCategory ? 1 : 0);
  return posts
    .filter((o) => o.id !== post.id)
    .map((o) => ({ o, s: score(o) }))
    .sort((a, b) => b.s - a.s || b.o.data.pubDate.getTime() - a.o.data.pubDate.getTime())
    .slice(0, n)
    .map((x) => x.o);
}

/** Split into pages of `size`; the first page may be larger (category archives show 2 hero cards + 10 posts). */
export function paginate<T>(items: T[], size: number, firstSize = size) {
  if (items.length <= firstSize) return [{ page: 1, total: 1, items }];
  const rest = items.slice(firstSize);
  const total = 1 + Math.ceil(rest.length / size);
  return [
    { page: 1, total, items: items.slice(0, firstSize) },
    ...Array.from({ length: total - 1 }, (_, i) => ({ page: i + 2, total, items: rest.slice(i * size, (i + 1) * size) })),
  ];
}

/** WordPress-style pagination path segment: page 1 -> '', page 2 -> 'page/2/' */
export const pagePath = (page: number) => (page === 1 ? '' : `page/${page}/`);
