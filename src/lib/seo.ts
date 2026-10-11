import { SITE, abs } from './site';

export const ORGANIZATION = {
  '@type': 'Organization',
  '@id': `${SITE.url}/#organization`,
  name: SITE.name,
  url: SITE.url,
  logo: { '@type': 'ImageObject', url: abs('/logo.png'), width: 512, height: 512 },
};

export const websiteJsonLd = () => ({
  '@context': 'https://schema.org',
  '@graph': [
    ORGANIZATION,
    {
      '@type': 'WebSite',
      '@id': `${SITE.url}/#website`,
      url: SITE.url,
      name: SITE.name,
      inLanguage: 'sv-SE',
      publisher: { '@id': ORGANIZATION['@id'] },
      potentialAction: {
        '@type': 'SearchAction',
        target: { '@type': 'EntryPoint', urlTemplate: `${SITE.url}/sok/?q={search_term_string}` },
        'query-input': 'required name=search_term_string',
      },
    },
  ],
});

export const breadcrumbJsonLd = (items: { name: string; path: string }[]) => ({
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: items.map((it, i) => ({
    '@type': 'ListItem',
    position: i + 1,
    name: it.name,
    item: abs(it.path),
  })),
});

export const blogPostingJsonLd = (p: {
  path: string;
  title: string;
  description: string;
  image?: string;
  published: Date;
  modified?: Date;
  author: string;
}) => ({
  '@context': 'https://schema.org',
  '@type': 'BlogPosting',
  '@id': `${abs(p.path)}#article`,
  mainEntityOfPage: { '@type': 'WebPage', '@id': abs(p.path) },
  headline: p.title.slice(0, 110),
  description: p.description || undefined,
  image: p.image ? [p.image] : undefined,
  datePublished: p.published.toISOString(),
  dateModified: (p.modified ?? p.published).toISOString(),
  inLanguage: 'sv-SE',
  author: { '@type': 'Person', name: p.author },
  publisher: { '@id': ORGANIZATION['@id'] },
});
