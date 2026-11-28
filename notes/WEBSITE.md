# KeyStow website

**Address: https://keystow.pages.dev** (Cloudflare Pages, project `keystow`,
owner's Cloudflare account, free plan). Moved from GitHub Pages
(`https://hullashoo6.github.io/keystow/`) on 28 Nov 2026, because GitHub's
rules do not allow GitHub Pages for a site that sells something.

## Editing the site

- The website is still the `docs/` folder on `main`. Edit it as before.
- Use **https://keystow.pages.dev/** in every address: canonical tags,
  `og:url`, `og:image`, the sitemap, structured data and the checkout's
  `redirect_url` (`https%3A%2F%2Fkeystow.pages.dev%2Fdownload%2F`). The
  publishing job also replaces any leftover old address automatically.
- Add new pages to `docs/sitemap.xml`.
- Installers stay on GitHub Releases
  (`releases/latest/download/KeyStowSetup.exe` and `KeyStowMac.dmg`);
  Cloudflare Pages takes files up to 25 MB only.

## Publishing

- `.github/workflows/site.yml` publishes `docs/` to Cloudflare on every push
  to `main` that changes `docs/`. It needs the secret `CLOUDFLARE_API_TOKEN`
  (see the comment at the top of the workflow); until that is added it
  publishes nothing and says so.
- By hand: `npx wrangler pages deploy docs --project-name keystow --branch main`.

## The old address

- GitHub Pages now serves the branch **`site-forwarding`**: one forwarding
  page for every old page (same path; query strings such as UTM tags and
  `#parts` are kept) and a catch-all 404 that forwards anything else. Old
  links in posts, videos and directories keep working.
- Do not edit or delete that branch, and do not switch GitHub Pages back to
  `docs/`: the old address would then compete with the new one in Google.
- Google Search Console: the old property keeps its verification file in the
  forwarding branch. The new address must be added as its own property and
  `https://keystow.pages.dev/sitemap.xml` submitted there.
