# SnapGrab — All-in-One Social Media Downloader

Free, mobile-first web tool to download videos, reels, photos and IGTV from
Instagram, TikTok, Facebook and YouTube. Clean UI, SEO/GEO optimized, ad-ready,
deployable on Vercel for $0.

## 🚀 Deploy to Vercel (free, 2 minutes)

1. Push this folder to a GitHub repo (or run `npx vercel` inside the folder).
2. Go to [vercel.com](https://vercel.com) → **Add New → Project** → import the repo.
3. Framework: **Other** · Build command: *(leave empty)* · Output dir: `/` (root).
4. Deploy. Done — you get a free `yourapp.vercel.app` URL + free HTTPS.

Free tier includes: 100 GB bandwidth/month, serverless functions, automatic SSL,
global CDN. Plenty to start earning.

## ⚙️ Make real downloads work

The site ships in **demo mode** (full UI/UX, link detection, quality picker).
Browsers can't fetch video files directly from Instagram/TikTok/etc. due to CORS —
you need a small API. In `index.html`, set:

```js
const DOWNLOADER_API = "https://your-api.com/fetch?url=";
```

Your API should return JSON like:
```json
{ "title": "...", "duration": "0:34", "thumbnail": "https://...",
  "formats": [ {"label":"1080p HD","url":"https://cdn.../v.mp4","audio":false} ] }
```

**Free backend options (fits Vercel free tier):**
- A Vercel serverless function wrapping **yt-dlp** (Python) — most common approach.
- A free-tier RapidAPI downloader endpoint as the upstream (mind their rate limits).
- Cloudflare Workers free tier as a proxy layer.

## 💰 Ads (monetization without hurting UX)

Three ad slots are pre-built and labeled — replace the placeholder `<div class="ad-box">`
content with your ad network's embed code:
- `#ad1` — banner below the downloader
- `#ad2` — in-feed unit before the FAQ
- `#stickyAd` — mobile anchor (320×50) that sits **below** the download button, dismissible

Recommended networks: Google AdSense, Adsterra, Monetag, PopAds.
**Honest heads-up:** AdSense often rejects downloader sites, so most people in this
niche start with Adsterra/Monetag. You also can't run ads until you have some traffic
(typically 30–60 days of SEO work).

## 🔍 SEO/GEO checklist (already built in)

- ✅ Meta title/description/keywords, canonical, Open Graph, Twitter cards
- ✅ JSON-LD structured data (`WebApplication` + `FAQPage` — helps Google & AI overviews)
- ✅ Semantic HTML, fast single-file load, mobile-first responsive
- ✅ FAQ section targeting "how to download X" queries
- ⬜ After deploy: submit to Google Search Console + Bing Webmaster Tools
- ⬜ Write 4–8 short blog posts (e.g., "How to download Instagram reels on iPhone")
  targeting long-tail keywords — this is what actually ranks

**Honest note:** no one can guarantee "#1 in SEO" — it takes 3–6 months of content +
backlinks. The technical foundation here is solid; the content work is on you.

## ⚖️ Important legal reality

- Downloading YouTube/Instagram/TikTok content violates their Terms of Service
  in most cases. Sites in this niche frequently get DMCA'd or domain-blocked.
- Only download your own content or content you have permission to save.
- Consider adding a DMCA contact page once you're live.

## 📁 Files

```
snapgrab/
├── index.html   ← the entire app (UI, logic, SEO, ads, JSON-LD)
└── README.md    ← this file
```
