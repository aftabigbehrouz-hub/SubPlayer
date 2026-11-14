# Publishing SubPlayer on Google Play — step by step

Everything in this folder:

| File | What it is |
|---|---|
| `PLAY-STORE-GUIDE.md` | this guide |
| `listing-en.md`, `listing-de.md` | app name, short and full description, English and German (checked against Google's limits) |
| `app-content-answers.md` | what to answer in every "App content" form (Data safety, content rating, ads, app access …) |
| `graphics/icon-512.png` | store icon, 512 × 512, 32-bit PNG |
| `graphics/feature-graphic-1024x500.png` | feature graphic, 1024 × 500, 24-bit PNG |
| `SubPlayer-GooglePlay.aab` (next to this folder) | the app bundle you upload: version 2.6 (code 9), package `com.behrouz.subplayer.play`, signed with your key |

Revenue model with price scenarios: https://claude.ai/artifact/R2zCWnee2yD928JZNGjijb

---

## 0. Before you start (one-off)

1. **A Google account** in your own name.
2. **Play Console developer account:** https://play.google.com/console/signup. Choose **Personal**, pay the one-time
   **US $25**, and verify your identity with your German ID or passport plus proof of address. Use your legal name and
   your German address; the registration fee is not refunded if the details don't match.
3. **Payments profile** (Play Console ▸ Setup ▸ Payments profile): your German bank account (IBAN) and tax details.
   Without it you cannot sell subscriptions.
4. **A public contact e-mail** for the listing. A separate Gmail is fine.
5. **Fill in PRIVACY.md and TERMS.md** on GitHub with your name, address and contact e-mail. Open the file on
   github.com, click the pencil icon, edit, then commit.
6. **German business side.** I'm not a tax adviser; please check this with a Steuerberater:
   - Selling subscriptions regularly is usually a trade: register it at your local **Gewerbeamt** (often online, around €20–60).
   - The Finanzamt then asks for a short tax questionnaire (Fragebogen zur steuerlichen Erfassung, via ELSTER).
   - For sales to consumers, **Google collects and pays VAT** in the EU and most other countries, so your Google payouts
     are already net of VAT. Your profit counts as income for income tax. The small-business rule (§ 19 UStG,
     "Kleinunternehmer") is a question for the adviser.
   - **Trader status:** because you sell, you are a "trader" under the EU Digital Services Act. Google then shows your
     address and phone number on the listing (see `app-content-answers.md`).

## 1. Create the app (Play Console ▸ Create app)

- App name: `SubPlayer: Learn with Videos` · Default language: English (United States)
- App or game: **App** · Free or paid: **Free**. Subscriptions are sold inside a free app; don't choose "Paid".
- Accept the declarations.
- App signing: keep **"Use Google-generated key"** (Play App Signing). The key that signed `SubPlayer-GooglePlay.aab`
  becomes your **upload key**: SHA-256 `7f8c8b676b35aa71b705f5b072c521bedd00ffb20f68ce4a95983882b4c9cc88`. Keep the
  keystore safe, because all future versions must be uploaded with it.

## 2. Upload the bundle to Internal testing (needed before you can create the subscription)

Testing ▸ Internal testing ▸ Create new release ▸ upload `SubPlayer-GooglePlay.aab`. Release name: `2.6`.
Release notes:
```
First release: subtitles for your own videos, tap-a-word dictionary (German and English), A-B repeat, review and practice.
```
Add yourself as an internal tester (an e-mail list with your Gmail), save, and roll out. Google only lets you create a
subscription after a bundle that contains the billing library has been uploaded.

## 3. Create the subscription (Monetize ▸ Products ▸ Subscriptions)

The app looks for these **exact IDs**. Type them exactly as shown, because IDs can't be changed later:

| Field | Value |
|---|---|
| Product ID | `subplayer_pro` |
| Name | SubPlayer Pro |
| Benefits (up to 4) | Subtitles for your own videos · Tap-a-word dictionary, German & English · A-B repeat, review & practice · Sync with Windows |
| **Base plan ID** | `yearly` |
| Type | Auto-renewing · Billing period **1 year** · keep Google's default grace and account-hold settings |
| Price | Set **Germany €29.99** and **United States US$29.99**, then "Update other prices" to let Google convert the rest. Google adjusts prices to local norms. |
| Activate | Activate the base plan |
| **Offer ID** | `free-trial-10d` |
| Offer eligibility | **New customer acquisition ▸ Never had this subscription** |
| Phases | **Free trial, 10 days** (no other phase) |
| Activate | Activate the offer |

Google Play then handles everything: the user sees "10 days free, then €29.99/year" and can cancel
in Google Play.

## 4. Test the purchase yourself (free)

1. Play Console ▸ Setup ▸ **License testing**: add your Gmail (and testers' Gmails). License testers are never charged.
2. On your phone, install from the internal-testing link (Testing ▸ Internal testing ▸ Testers ▸ copy link). Open
   SubPlayer: you should see the subscription screen with "Start 10-day free trial" and the price.
3. Subscribe with a test card. In Google's test mode, a free trial lasts a few minutes and a yearly plan renews every
   ~30 minutes, so you can watch a whole cycle in one evening.
4. Check: the app opens; Settings ▸ Subscription says "Active"; "Manage / cancel" opens Google Play; after cancelling
   and the test period ending, the subscription screen comes back.

## 5. Store listing (Grow users ▸ Store presence ▸ Main store listing)

- Paste the texts from `listing-en.md`. Then Translations ▸ add **German (de-DE)** and paste `listing-de.md`.
- App icon: `graphics/icon-512.png` · Feature graphic: `graphics/feature-graphic-1024x500.png`
- **Phone screenshots** (minimum 2; use 6–8), taken on your phone (power + volume-down). Google requires real
  screenshots of the app:
  1. A German video playing with a subtitle line (portrait)
  2. A tapped word: the word card with IPA, meanings, English/Persian
  3. The A-B loop / control panel
  4. "Make subtitles" with Accurate selected
  5. My Words with review counts
  6. Review card with the video moment
  7. Practice: gap-fill
  8. An English video with the English word card
  Use videos you are allowed to show: your own recordings, or Creative Commons videos with attribution. Avoid TV
  shows or films in the screenshots.
- Optional: a 7-inch tablet screenshot or two, and a YouTube promo video.

## 6. App content forms

Work through every item under **Policy and programs ▸ App content** using `app-content-answers.md`.

## 7. Closed test: 12 testers for 14 days (required for new personal accounts)

1. Testing ▸ **Closed testing** ▸ create a track ▸ upload the same AAB (or promote it from internal testing).
2. Testers: an e-mail list of **at least 15 Gmail addresses** (a few extra, in case someone drops out). Friends, family,
   your Telegram/Bale channel, language-exchange partners. Each tester must open the opt-in link, tap **"Become a
   tester"**, install from Google Play, and **stay opted in for 14 days in a row**.
3. Add them as **license testers** too (step 4), so they can use the free trial without being charged.
4. Ask them to really use it (open a video, make subtitles, tap words, save a few) and send feedback. Google asks about
   this when you apply.
5. After 14 days: Dashboard ▸ **Apply for production**. Answer honestly: who tested, how you recruited them, what you
   changed after feedback, why it's ready.

## 8. Production

Production ▸ Countries/regions: start with **Germany, Austria, Switzerland**, then add all countries where the
subscription is available. Create a release with the same AAB and send it for review. Reviews usually take a few days.

## 9. Updates later

Every new version must have a higher `versionCode` and target the then-required Android version. The GitHub build does
both and refuses to publish a build with a wrong certificate or native code that isn't 16 KB-aligned. Upload the new
`SubPlayer-GooglePlay.aab` from the "latest" release.

---

## What is different in the Google Play version

| | Google Play version | Your own APK (direct) |
|---|---|---|
| Package name | `com.behrouz.subplayer.play` | `com.behrouz.subplayer` (unchanged, keeps your data) |
| Payment | Google Play subscription, 10-day free trial | 10-day trial + activation code from you (Telegram @Bgilone) |
| "Fast" engine (Vosk) | Not included. Its library isn't aligned for 16 KB memory pages, which Play refuses. Accurate, Best and Online remain. | Included |
| Paste a video link (Tagesschau …) | Not included, to stay clear of Play's rules on downloading other people's content | Included |
| Everything else | Same | Same |

The two can be installed side by side. Play policy: the Play version must not point users to buying outside Google Play,
so it never mentions Telegram or activation codes. The Windows app is still sold with activation codes; that is allowed,
because Google Play doesn't sell PC software.

## Price and target

**€29.99 / US$29.99 a year** with a 10-day free trial. That's below LingQ ($119.99/yr) and Lingopie ($83.88/yr), which
include their own video libraries, and fair for a tool that works with your own videos.

To net **US$10,000 in 12 months** at that price you need about **460 paying subscribers**. If about 3 in 100 installs
end up paying, that's roughly **15,300 installs, ~1,300 a month**. Google's store alone won't bring that many; plan for:
- your Bale/Telegram channel and German-learning groups: post short clips "watch → tap → understand" made with the app
- YouTube Shorts / Instagram Reels / TikTok showing one tap-a-word moment per video
- German teachers and Volkshochschule (VHS) course groups; Reddit r/German and r/languagelearning (follow their rules
  on self-promotion)
- a German-language listing (included) and good ratings: ask happy users for a review after their 10th saved word
  (Google's in-app review API can be added later)

The spreadsheet lets you change the price, conversion rate, VAT and refunds and see the effect.
