export const SITE = {
  name: 'Investeringskunskap',
  url: 'https://investeringskunskap.se',
  tagline: 'Allt du vill veta om aktier, fonder & krypto',
  description:
    'Vill du lära dig om investeringar och sparande? Läs inlägg om aktier, omdömen av banker och mäklare, fonder, krypto och privatekonomi.',
  locale: 'sv_SE',
  pageSize: 10, // same as the old WordPress archives, so /page/N/ URLs stay identical
  categoryFirstPageSize: 12, // 2 hero cards + 10 posts
};

// Single place for the contact address (rendered obfuscated by ContactEmail.astro)
export const CONTACT_EMAIL = 'info@investeringskunskap.se';

export const abs = (path: string) => new URL(path, SITE.url).toString();

// Hard-coded main menu, same dropdowns as the live site.
export type MenuItem = {
  label: string;
  href?: string;
  children?: { label: string; href: string }[];
  icon: 'money' | 'person' | 'news';
};

export const MENU: MenuItem[] = [
  {
    label: 'Investera pengar',
    icon: 'money',
    children: [
      { label: 'Aktier', href: '/aktier/' },
      { label: 'Fonder', href: '/fonder/' },
      { label: 'Kryptovaluta', href: '/kryptovaluta/' },
      { label: 'Nybörjarguider', href: '/nyborjarguider/' },
    ],
  },
  {
    label: 'Privatekonomi',
    href: '/privatekonomi/',
    icon: 'person',
    children: [
      { label: 'Tips', href: '/tips/' },
      { label: 'Räntekalkylator', href: '/ranta-pa-ranta-kalkylator/' },
      { label: 'Spara pengar', href: '/category/spara-pengar/' },
    ],
  },
  { label: 'Alla inlägg', href: '/senaste-inlaggen/', icon: 'news' },
];
