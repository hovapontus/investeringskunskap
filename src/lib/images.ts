import type { ImageMetadata } from 'astro';

// All images migrated from WordPress live in src/assets/uploads/<yyyy>/<mm>/<file>.
const files = import.meta.glob<{ default: ImageMetadata }>(
  '/src/assets/uploads/**/*.{jpg,jpeg,png,webp,gif,svg,avif}',
);

export async function getUpload(key: string): Promise<ImageMetadata> {
  const load = files[`/src/assets/uploads/${key}`];
  if (!load) throw new Error(`Image not found in src/assets/uploads: ${key}`);
  return (await load()).default;
}

export const isSvg = (key: string) => key.toLowerCase().endsWith('.svg');
