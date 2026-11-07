# SEO Implementation Notes — www.chautaramavi.edu.np

This document records the on-page SEO work applied to the official website of
**Shree Chautara Secondary School (Chautara Mavi)**, Dandakharka, Sunkoshi
Rural Municipality-5, Okhaldhunga, Nepal.

## What was added

- Unique, keyword-focused `<title>` and `<meta name="description">` on every page.
- Target keyword variants, including common spellings and misspellings
  (`Chautara Mavi`, `Chautara Mavi School`, `Chautara School`,
  `Chautara Secondary School`, `Chautara Ma Vi`, `Chautaramavi`,
  `Chautara Mabi`, `Danda Kharka`, `Dandakharka Okhaldhunga`,
  `Sunkoshi Rural Municipality`).
- Canonical URLs on every page, using the `https://www.chautaramavi.edu.np`
  host (the apex domain already redirects to `www`).
- Open Graph and Twitter Card metadata for better sharing previews.
- Local SEO metadata: `geo.region`, `geo.placename`, `geo.position`, `ICBM`,
  plus the school's exact map coordinates (`27.29159754, 86.36485448`).
- Schema.org JSON-LD:
  - `School` / `EducationalOrganization` with name, alternate names, address,
    phone, email, logo, map, service area, social profiles and academic programs.
  - `WebSite`, `WebPage`, `AboutPage`, `ContactPage`, `CollectionPage`,
    `BreadcrumbList`, `Course`, `ItemList`, `Person` and `ImageGallery`
    where relevant.
- `sitemap.xml` with all main pages and all published notice pages.
- `robots.txt` with the sitemap reference and private/development paths blocked.
- Internal links added to the existing footer "Quick Links" column.
- A visible "View on Google Maps" link on the contact page.
- Descriptive `alt` text for campus, course, teacher and student images.
- Mobile/performance improvements: `preconnect`/`dns-prefetch` hints,
  `decoding="async"`, safe `loading="lazy"` for below-the-fold images,
  a poster image and `preload="metadata"` for the hero video, and `theme-color`.
- Dynamic canonical/Open Graph updates on `notice_detail.html` so each notice
  can be shared and indexed with its own title and URL.

No existing page structure, navigation, forms, scripts or visible content was
removed. The additions are metadata, structured data, accessibility attributes,
footer links and a map link.

## Deploy

The site is a static GitHub Pages site in this repository. After reviewing the
changes:

```powershell
git add -A
git commit -m "SEO: titles, structured data, sitemap, robots, local SEO, performance"
git push origin main
```

GitHub Pages will publish the changes. Cloudflare may cache HTML for up to
about 10 minutes; the `sitemap.xml` and `robots.txt` files should then be
available at:

- https://www.chautaramavi.edu.np/sitemap.xml
- https://www.chautaramavi.edu.np/robots.txt

## Google indexing checklist

1. Open [Google Search Console](https://search.google.com/search-console/).
2. Add a **Domain** property for `chautaramavi.edu.np` (DNS verification is
   preferred) or a **URL-prefix** property for
   `https://www.chautaramavi.edu.np/`.
3. If you use HTML-tag verification, add the verification meta tag to the
   `<head>` of `index.html` and redeploy.
4. In **Sitemaps**, submit `sitemap.xml`.
5. Use **URL Inspection** for the home page, About, Courses, Contact, Notice
   and the three course detail pages, then click **Request indexing**.
6. Check **Pages** and **Core Web Vitals** reports after a few days.

## Google Business Profile (important for local searches)

Schema markup helps search engines understand the school, but local map
rankings depend mainly on a Google Business Profile:

1. Create or claim the profile for **Shree Chautara Secondary School**.
2. Use the exact name, address, phone and website used on the site:
   - Dandakharka, Sunkoshi Rural Municipality-5, Okhaldhunga, Nepal
   - +977-9862606960
   - https://www.chautaramavi.edu.np/
3. Select the category **School** (and relevant secondary categories).
4. Add the location pin `27.29159754, 86.36485448`.
5. Upload campus, classroom, laboratory and event photos regularly.
6. Post notices, admissions updates and results announcements.

Keep the name, address and phone number (NAP) identical on Facebook,
Edusanjal, local directories and the Google Business Profile.

## Bing and other search engines

1. Add the site to [Bing Webmaster Tools](https://www.bing.com/webmasters/).
2. Submit `https://www.chautaramavi.edu.np/sitemap.xml`.
3. Optionally use IndexNow for faster notice indexing.

## Ongoing SEO tasks

- Publish notices and admission updates regularly; fresh content is a ranking
  signal for notice-related searches.
- Compress very large images when convenient (`img/about.png` is about 939 KB
  and some staff photos are over 1 MB). WebP versions would improve mobile
  performance without changing the design.
- Ask Sunkoshi Rural Municipality, the Okhaldhunga EDCU, CTEVT and local news
  sites to link to the official website.
- Keep the Facebook page link and contact details current.
- Re-submit the sitemap after adding new top-level pages.

## Notes

SEO work improves technical discoverability, relevance and local signals. No
one can guarantee a specific Google position, because rankings also depend on
competition, links, user behaviour and Google's own systems. The changes above
address the on-site factors that are under the school's control.
