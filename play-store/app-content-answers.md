# Play Console ▸ Policy ▸ App content — what to answer

These answers describe the **Google Play build** of SubPlayer as it is coded (no ads, no analytics, no account, no
server of yours). Read each one before you submit it: you are the one declaring it to Google, and Google rejects or
removes apps whose declarations don't match what the app does.

## Privacy policy
`https://github.com/aftabigbehrouz-hub/SubPlayer/blob/main/PRIVACY.md`
**Before you submit, fill in your name, address and contact e-mail** in PRIVACY.md and TERMS.md on GitHub. Open the file
on github.com, click the pencil icon, edit, then "Commit changes". The app links to both files from its paywall.

## Ads
**No, my app does not contain ads.**

## App access
**All or some functionality is restricted.** Add one instruction:
- Name: `Subscription / free trial`
- Instructions: `SubPlayer opens with a Google Play subscription screen. New users get a 10-day free trial: tap "Start
  10-day free trial" and confirm in Google Play. There is no login. To try the features, open any video file (MP4) with
  speech, tap Subtitles ▸ Deutsch or English ▸ Accurate ▸ Start, then pause and tap a word.`

## Content rating (IARC questionnaire)
- Category: **Reference, News, or Educational**
- Violence, fear, sexuality, gambling, drugs, crude humour, bad language: **No** to all.
- Does the app allow users to interact or exchange content with other users? **No**
- Does the app share the user's current physical location with other users? **No**
- Does the app allow users to purchase digital goods? **Yes** (the subscription)
- Unrestricted internet or web browser inside the app? **No.** The app only opens fixed dictionary pages in your
  browser, or in the ChatGPT/Grok apps.
- Expected result: **Everyone / PEGI 3 / USK 0**, with a "Digital purchases" notice. Users open their own videos; Google
  rates the app, not those videos.

## Target audience and content
- Target age groups: **13–15, 16–17, 18 and over.** Leave out the under‑13 groups so that the Families policy does not
  apply.
- Could the app unintentionally appeal to children? **No**

## News app: **No** · Government app: **No** · Financial features: **None** · Health: **No**

## Advertising ID
**No.** SubPlayer and its libraries (Media3, Play Billing, WorkManager) do not use the advertising ID.

## Data safety

**Does your app collect or share any of the required user data types?** → **Yes.** The app sends some data off the phone,
but only for optional features the user turns on.

**Is all of the user data collected by your app encrypted in transit?** → **Yes** (HTTPS only).

**Do you provide a way for users to request that their data is deleted?** → **Yes.** Users delete words, sentences and
subtitles in the app, stop syncing in Settings ▸ Sync, and delete the "SubPlayer sync (private)" gist on GitHub. The
developer stores no user data.

**Account creation:** none. You don't need a data deletion URL, because the app has no accounts.

Data types to tick:

| Data type | Collected | Shared | Optional? | Ephemeral? | Purpose | Why |
|---|---|---|---|---|---|---|
| **Audio ▸ Voice or sound recordings** | Yes | No ¹ | Optional | No ² | App functionality | Online subtitles send the video's audio to Groq or OpenAI, with the user's own key |
| **App activity ▸ Other user-generated content** | Yes | No ¹ | Optional | No | App functionality | Translation sends the sentence to Google Translate/MyMemory; Sync sends saved words and sentences to the user's own GitHub gist |

Leave everything else unticked: location, personal info, financial info, contacts, photos/videos (videos never leave
the phone), files, calendar, health, messages, web history, app info/performance, device IDs.

¹ *Not "shared": Google exempts transfers that the user starts and expects ("user-initiated action"). The user picks the
provider, enters their own key or token, and taps the button.*
² *You can't promise that Groq, OpenAI or Google delete it straight away, so answer "No".*

Purchases go through Google Play Billing. The app only reads on the phone whether a subscription is active and sends no
purchase data anywhere, so you don't declare purchase history.

## Store settings
- App category: **Education**
- Tags: Language learning, Education, Video players
- Contact e-mail: required and **shown publicly**. Use a separate address (for example a new Gmail) rather than your
  private one.
- Website (optional): `https://github.com/aftabigbehrouz-hub/SubPlayer`

## Trader status (EU Digital Services Act)
If you sell to users in the EU or UK as a business, choose **Trader**. On a personal account Google then shows your
**address and phone number publicly** on the listing. Because SubPlayer is a paid subscription, you are most likely a
trader. If you don't want your home address shown, a business address service or a company (organisation account) are
the usual routes. Ask a German tax adviser (Steuerberater) or a lawyer what fits your case.
