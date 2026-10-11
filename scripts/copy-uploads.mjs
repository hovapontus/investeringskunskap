// Keeps the old WordPress image URLs alive: /wp-content/uploads/<yyyy>/<mm>/<file> serves the original file.
// (Image search, hotlinks and old shares keep working; the site itself uses optimized copies from /_astro/.)
import { cpSync, existsSync } from 'node:fs';

if (!existsSync('dist')) throw new Error('Run "astro build" first');
cpSync('src/assets/uploads', 'dist/wp-content/uploads', { recursive: true });
console.log('Copied original uploads to dist/wp-content/uploads');
