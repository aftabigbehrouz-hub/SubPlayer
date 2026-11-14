# Publishing SubPlayer on Cafe Bazaar and Myket — step by step

| File | What it is |
|---|---|
| `IRAN-STORES-GUIDE.md` | this guide |
| `listing-fa.md` | Persian app name, short and full description (half-spaces included) |
| `SubPlayer-CafeBazaar.apk` | upload to Cafe Bazaar: package `com.behrouz.subplayer.bazaar` |
| `SubPlayer-Myket.apk` | upload to Myket: package `com.behrouz.subplayer.myket` |
| Icon and feature graphic | the same as for Google Play (`SubPlayer-PlayStore-Kit/graphics/`) |

## How these versions work

- **First 10 days free**, counted by the app on the phone, like your own APK. No payment details needed to start.
- After that, the app asks for the **yearly subscription bought through that store** (Bazaar or Myket payment, in
  tomans). The store app must be installed on the phone.
- Same features as your own APK, including the Fast (Vosk) engine for older phones and Tagesschau links. Store rules
  require the store's own payment for digital features, so there are no activation codes or Telegram.
- Both versions use **Myket's official billing library (1.19)**, which also supports Cafe Bazaar. The billing
  settings for each store are set in the build.
- Different package names, so one person can't move a Bazaar purchase into the Myket version by mistake.
- **Online subtitles (Groq/OpenAI) and Google Translate are often blocked from Iran.** Offline subtitles, the
  dictionaries, review and practice work without them. The dictionaries and models download from GitHub, which is
  usually reachable.

## 1. Developer accounts

- **Cafe Bazaar:** https://pishkhan.cafebazaar.ir. **Myket:** https://developer.myket.ir
- Both ask for identity details and an **Iranian bank account (Shaba/IBAN)** for payouts, which are paid in tomans.
  Check each panel for the exact documents (usually national ID card and an Iranian mobile number).
- **You live in Germany.** Please check two things first, because I'm not a lawyer or tax adviser:
  1. How you will receive and use the toman income. Payouts go only to an Iranian account, and moving money between
     Iran and Germany is restricted by bank rules and sanctions.
  2. That selling a consumer app to Iranian users is allowed for you. EU sanctions are mostly targeted at listed people,
     companies and certain goods, but a German lawyer or tax adviser (Steuerberater) should confirm it, and also how to
     declare the income in Germany.

## 2. Create the app and the subscription in each panel

**Important (Bazaar ▸ اطلاعات پایه ▸ روش قیمت‌گذاری):** choose **رایگان** (free) and tick **«برنامه نیاز به پرداخت
درون‌برنامه‌ای دارد»**. Do **not** choose «پرداخت هزینه قبل از دانلود» (pay before download). The app charges through the
in-app subscription after the free trial; pay-before-download would make people pay twice. It also has a low price
cap: in your panel, 2,000,000 rials was accepted and 3,000,000 was refused.

Bazaar ▸ پرداخت درون‌برنامه‌ای ▸ محصول جدید:
- نوع محصول: **اشتراک مدت‌دار** · نوع اشتراک: **اشتراک | ۳۶۵ روزه**
- شناسهٔ کالا: **`subplayer_pro`** · عنوان: «اشتراک سالانهٔ ساب‌پلیر»
- قیمت شامل مالیات: **6,900,000 ریال** (= 690,000 تومان). Prices in the panel are in **rials** (10 rials = 1 toman).
- وضعیت: **فعال**
- The «اشتراک ۵ دقیقه‌ای (برای تست توسعه‌دهنده)» type is for test products. SubPlayer looks only for `subplayer_pro`.

Old general steps:

1. Create a new app and upload the APK: Bazaar `SubPlayer-CafeBazaar.apk`, Myket `SubPlayer-Myket.apk`. These first
   uploads are only there so you can create the product; they can't take payments yet.
2. **In-app payment** (پرداخت درون‌برنامه‌ای) ▸ add a **subscription** (اشتراک) product:
   - Product ID (SKU, شناسهٔ محصول): **`subplayer_pro`**, exactly like this
   - Period: **1 year** (یک‌ساله)
   - Price: see section 5
3. In the same section, copy the app's **public RSA key** (کلید عمومی RSA / کلید پرداخت).

## 3. Put the keys in the project and rebuild

1. On github.com open **`store-keys.properties`** (top folder of the repository), click the pencil icon, and paste each
   key after the `=` on one line:
   ```
   bazaar=MIHNMA0GCSqGSIb3DQEBAQUAA4G7ADC… (your Bazaar key)
   myket=MIGfMA0GCSqGSIb3DQEBAQUAA4GN…     (your Myket key)
   ```
   These are public keys, so it is safe to keep them in the repository. They let the app check that a purchase really
   came from the store.
2. Click "Commit changes". About 20 minutes later, the GitHub build publishes new `SubPlayer-CafeBazaar.apk` and
   `SubPlayer-Myket.apk` with the keys built in (https://github.com/aftabigbehrouz-hub/SubPlayer/releases/tag/latest).
3. Raise the version (versionCode) before each new upload if the store asks, or ask me to.

## 4. Test, then publish

1. Install the new APK from step 3 on a phone that has Bazaar (or Myket) installed and is signed in.
2. To test the trial ending without waiting 10 days, use a second phone, or clear the app's storage and set the date
   forward. The app checks that the clock hasn't been turned back, so put it back afterwards.
3. Buy the subscription once yourself. A real purchase is the safest test; refund yourself through the panel if it
   allows. The app should open, and Settings ▸ Subscription should say "Active".
4. Upload the tested APK to the panel and fill in the listing:
   - Name, short and full description: `listing-fa.md`
   - Category: **آموزش** (Education)
   - Icon 512 × 512 and screenshots: take them on your phone (Persian subtitles or the Persian word card make good
     screenshots)
   - Privacy policy link: `https://github.com/aftabigbehrouz-hub/SubPlayer/blob/main/PRIVACY.md`. It now covers Bazaar
     and Myket and has a Persian summary. Fill in your name and address first.
5. Submit for review (بررسی).

## 5. Price in tomans

Iranian learners compare prices with other language apps on Bazaar, which mostly sell monthly to yearly
subscriptions. Dollar prices don't translate: US$29.99 is about 8.1 million tomans. Suggested:
**۶۹۰٬۰۰۰ تومان a year** (about US$2.55), with an introductory or seasonal discount around Nowruz.

What US$10,000 a year would take from these two stores alone. Dollar = 271,060 tomans (free market, 8 Aban 1405).
Bazaar's share: 15% on a developer's first 1 billion tomans of sales per year (announced 1400; I assume 30% above it;
check the current terms in the panel). Myket's share isn't public; I assumed the same.

| Yearly price | ≈ US$ | Subscribers needed for US$10,000 net |
|---|---|---|
| 490,000 tomans | 1.81 | 7,466 |
| 690,000 tomans | 2.55 | 5,302 |
| 990,000 tomans | 3.65 | 3,695 |

Iran is a volume market. Bazaar has ~50 million monthly users, but each subscriber brings in about a tenth of a Google
Play subscriber. Use Iran for reach and reviews; most of the US$10,000 is more realistic from Google Play.

## 6. Updates

Each update: raise the version, push, and upload the new APKs from the "latest" release to both panels.
