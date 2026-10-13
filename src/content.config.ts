import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const id = ({ entry }: { entry: string }) => entry.replace(/\.mdx$/, '');

const posts = defineCollection({
  loader: glob({ pattern: '*.mdx', base: './src/content/posts', generateId: id }),
  schema: z.object({
    title: z.string(),
    description: z.string().default(''),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    author: z.string(),
    categories: z.array(z.string()).default([]),
    primaryCategory: z.string().optional(),
    tags: z.array(z.string()).default([]),
    image: z.string().optional(), // upload path, e.g. "2022/09/x.jpg" (resolved in src/lib/images.ts)
    imageAlt: z.string().optional(),
    seoTitle: z.string().optional(), // full <title> when it differs from "<title> | Investeringskunskap"
    noindex: z.boolean().default(false),
    focusKeyword: z.string().optional(),
    wpId: z.number().optional(),
  }),
});

const pages = defineCollection({
  loader: glob({ pattern: '*.mdx', base: './src/content/pages', generateId: id }),
  schema: z.object({
    title: z.string(),
    description: z.string().default(''),
    template: z.enum(['default', 'landing', 'home', 'latest', 'calculator']).default('default'),
    category: z.string().optional(), // landing pages list this category
    tag: z.string().optional(), // ...or this tag
    heroImage: z.string().optional(),
    heading: z.string().optional(),
    seoTitle: z.string().optional(),
    updatedDate: z.coerce.date().optional(),
    noindex: z.boolean().default(false),
    handwritten: z.boolean().optional(),
    wpId: z.number().optional(),
  }),
});

export const collections = { posts, pages };
