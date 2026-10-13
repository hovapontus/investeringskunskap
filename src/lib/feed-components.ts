// Components used when MDX is rendered for the RSS feed: static HTML only, no scripts or iframes.
import { mdxComponents } from './mdx-components';
import FeedLink from '../components/feed/FeedLink.astro';
import FeedAffiliate from '../components/feed/FeedAffiliate.astro';

export const feedComponents = {
  ...mdxComponents,
  YouTube: FeedLink,
  Embed: FeedLink,
  AffiliateBox: FeedAffiliate,
  CompoundCalculator: FeedLink,
  ContactEmail: FeedLink,
};
