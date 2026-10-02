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

⚖️ Final Integrated User Terms & Liability Waiver
The use of this platform and the decision to download any media is at the sole discretion, choice, and risk of the user.
• Independence & Non-Affiliation: SnapGrab is an independent tool and is not affiliated with Instagram, TikTok, Facebook, or YouTube.
• Tool-Only Service: This platform strictly provides a technical utility for content downloading. We do not host, store, or monitor any files, nor do we verify the ownership or intended use of the media.
• Zero Platform Liability: The user bears total responsibility for how they use this service and the content they retrieve. This platform has no affiliation with the owners of the content or the social networks listed, and accepts zero liability for any user actions.
• User Responsibility: SnapGrab operates strictly as an automated infrastructure capable of downloading any publicly available media from supported networks. The platform functions blindly without verifying user authorization, ownership, or licensing. The choice, purpose, and final usage of any downloaded media rest exclusively with you, and you assume all responsibility regarding the targeted platform's terms and copyright rights.


## 📁 Files

```
snapgrab/
├── index.html   ← the entire app (UI, logic, SEO, ads, JSON-LD)
└── README.md    ← this file
```
