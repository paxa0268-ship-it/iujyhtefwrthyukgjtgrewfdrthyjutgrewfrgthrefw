# 🤖 Men-Bot: sening raqamli ikkinchi "men"ing

Bu Telegram bot:

1. **Sen haqingda hamma narsani o'rganadi**: o'zing yozganlaring, intervyu savollari, eski chatlaring (eksport), Business chatlarda yozganlaring.
2. **Seni yozish uslubingda** boshqalarga javob beradi (til, yozuv, qisqalik, emoji, so'zlaring).
3. Har bir xabarda **vaziyatni tahlil qiladi** (kim yozdi, nima istaydi, shoshilinchmi, javob berish xavfsizmi) va faqat xavfsiz bo'lsa javob beradi. Pul, parol, va'da, janjal kabi masalalarda **jim turib senga xabar beradi**.
4. Sen undan o'zing haqingda so'rasang, **faqat saqlangan faktlar asosida aniq javob beradi** (bilmasa, "bilmayman" deydi, to'qimaydi).

## Qanday ishlaydi

```
Do'sting senga yozadi ─► (Telegram Business) ─► bot ─► tahlil + sening uslubingda javob
                                                         └─► senga: "kim yozdi, nima dedi, nima javob berdim"
Sen botga yozasan: "Men 12-martda tug'ilganman" ─► xotiraga saqlanadi
Sen so'raysan: "Tug'ilgan kunim qachon?"          ─► "12-mart" (saqlangan fakt bo'yicha)
```

Eslatma: Telegram **Business** rejimi uchun sizda **Telegram Premium** bo'lishi kerak. Premium bo'lmasa bot shunchaki o'zining chatida ishlaydi (kimdir botga to'g'ridan-to'g'ri yozsa, javob beradi).

---

## 1-QADAM. Kerakli narsalarni tayyorlash

### a) Bot yaratish
1. Telegramda **@BotFather** → `/newbot` → nom va username bering.
2. U bergan **TOKEN**ni saqlab qo'ying (`BOT_TOKEN`).
3. @BotFather → `/mybots` → botingiz → **Bot Settings → Business Mode → Turn on**. (Shu yoqilmasa, bot Business chatlarni ko'rmaydi.)

### b) Anthropic (Claude) API kaliti
1. https://console.anthropic.com saytida ro'yxatdan o'ting, hisobni to'ldiring (kam summa ham yetadi).
2. **API Keys → Create Key** → kalitni saqlang (`ANTHROPIC_API_KEY`).

### c) O'zingizning Telegram ID raqamingiz
1. Telegramda **@userinfobot** ga `/start` yozing → u sizning **Id** raqamingizni beradi (`OWNER_ID`).
2. Faqat shu ID egasi botni boshqara oladi.

### d) Bepul doimiy ma'lumotlar bazasi (juda muhim!)
Render'ning bepul serveri fayllarni saqlamaydi (qayta ishga tushsa hammasi o'chadi), shuning uchun xotira tashqi bazada turishi kerak:
1. https://neon.tech ga kiring (bepul) → **Create project**.
2. Dashboard'da **Connection string** (`postgresql://...`) ni nusxalang (`DATABASE_URL`).

> Render'ning o'z bepul Postgres'i 30 kundan keyin o'chadi, shuning uchun Neon tavsiya etiladi.

---

## 2-QADAM. Kodni GitHub'ga yuklash
1. https://github.com da **New repository** (xohlasangiz *Private*) yarating.
2. Shu papkadagi hamma fayllarni (`main.py`, `requirements.txt`, `render.yaml`, ...) reponing ildiziga yuklang (**Add file → Upload files**).
   Hech qanday `.env` fayl yuklamang. Kalitlar faqat Render'da turadi.

---

## 3-QADAM. Render'ga joylash
1. https://render.com ga GitHub orqali kiring.
2. **New + → Blueprint** → reponi tanlang. (`render.yaml` shuni avtomatik sozlaydi.)
   *Yoki qo'lda:* **New + → Web Service** → repo → Runtime: **Python 3** → Build: `pip install -r requirements.txt` → Start: `python main.py` → Plan: **Free**.
3. **Environment** bo'limiga quyidagilarni kiriting:

| Nomi | Qiymati | Majburiy? |
|---|---|---|
| `BOT_TOKEN` | BotFather bergan token | ✅ |
| `ANTHROPIC_API_KEY` | Anthropic kaliti | ✅ |
| `OWNER_ID` | Sizning Telegram ID'ingiz | ✅ |
| `DATABASE_URL` | Neon connection string | ✅ (tavsiya) |
| `TIMEZONE` | masalan `Asia/Tashkent` | ixtiyoriy |
| `MODEL` | standart `claude-sonnet-5-5` | ixtiyoriy |
| `FAST_MODEL` | standart `claude-haiku-5-5` | ixtiyoriy |
| `DEFAULT_MODE` | `auto` / `draft` / `off` (standart `auto`) | ixtiyoriy |
| `DEBOUNCE_SECONDS` | ketma-ket xabarlarni kutish (standart `6`) | ixtiyoriy |
| `PAUSE_MINUTES` | o'zingiz yozsangiz bot necha daqiqa jim turadi (standart `30`) | ixtiyoriy |
| `MAX_REPLIES_PER_HOUR` | bitta chatga soatiga maksimal javob (standart `40`) | ixtiyoriy |
| `AI_TAG` | avto-javob oxiriga qo'shiladigan belgi, masalan `🤖` (standart bo'sh) | ixtiyoriy |

   `RENDER_EXTERNAL_URL` ni Render o'zi beradi, webhook ham o'zi o'rnatiladi. Hech narsa qilish shart emas.
4. **Deploy** bosing. Loglarda `Webhook o'rnatildi` yozuvi chiqsa, tayyor.

### Bot "uxlab qolmasligi" uchun
Bot ishga tushgach, **o'zi avtomatik ravishda** o'z `/health` manzilini har 10 daqiqada so'rab turadi — shuning uchun Render'ning bepul serveri odatda uxlab qolmaydi va hech qanday tashqi xizmat (UptimeRobot va h.k.) sozlashingiz shart emas.

Agar baribir sekinlashishni sezsangiz (masalan, Render qayta deploy qilganda bir necha daqiqa o'chib turishi mumkin):
1. https://uptimerobot.com (bepul) → **Add monitor** → HTTP(s) → URL: `https://SIZNING-NOMINGIZ.onrender.com/health` → interval **5 daqiqa** — bu qo'shimcha kafolat sifatida.
2. Yoki Render'ning pullik (Starter) rejimiga o'ting: umuman uxlamaydi.

---

## 4-QADAM. Botni Telegram akkauntingizga ulash (Business)
1. Telegram → **Sozlamalar → Telegram Business → Chat-botlar**.
2. Bot username'ini kiriting → qaysi chatlarga ruxsat berishni tanlang (hammasi yoki tanlanganlar) → **"Xabarlarga javob berish"** huquqini yoqing.
3. Botga `/start` yozing. Ulangan bo'lsa "✅ Business akkaunting ulangan" deb ko'rsatadi.

---

## 5-QADAM. Botni o'rgatish (eng muhim qism)
Sifat shu yerga bog'liq: qancha ko'p o'rgatsangiz, shuncha aniq bo'ladi.

1. **`/intervyu`** — 24 ta savol: oila, ish, odat, do'stlar, qaysi mavzuda jim turish kerakligi va h.k. O'z so'zlaringiz bilan, erkin javob bering.
2. **Erkin yozing**: "Dugonam Malika, unga sen deb yozaman", "Ertalab 9 gacha band bo'laman" — bot saqlaydi.
3. **Eski chatlaringizni yuboring** (uslub uchun eng kuchli usul):
   Telegram Desktop → chatni oching → ⋮ → **Export chat history** → Format: **JSON**, media'siz → hosil bo'lgan `result.json` ni botga yuboring.
   Bot sizning xabarlaringizni topib uslubingizni o'rganadi va faktlarni ajratib oladi.
4. **Business chatlarda odatdagidek yozishda davom eting**: bot sizning xabarlaringizdan avtomatik o'rganib boradi.
5. **`/sinov salom, ertaga uchrashamizmi?`** — notanish odam shunday yozsa bot nima javob berishini sinab ko'ring. Yoqmasa, qo'shimcha o'rgating.
6. **`/uslub`** — bot sizning yozish uslubingiz haqida nima deb tushunganini ko'rsatadi.

### Birinchi kunlar uchun tavsiya
`/rejim draft` qo'ying: bot javobni avval **sizga** ko'rsatadi (✅ Yubor / 🔄 Boshqacha / ❌). Ishonch hosil qilgach `/rejim auto`.

---

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/intervyu`, `/keyingi`, `/tugat` | Savol-javob orqali o'rgatish |
| `/fakt [so'z]` | Saqlangan faktlar (id bilan) |
| `/ochir <id>` | Faktni o'chirish |
| `/ochiq <id>` / `/yopiq <id>` | Fakt boshqalarga javobda ishlatilsin / faqat sizga |
| `/sinov <matn>` | "Shu yozsa nima derdim?" sinovi |
| `/rejim auto\|draft\|off` | Avto-javob / avval ko'rsat / o'chiq (faqat o'rganadi) |
| `/xabar all\|important\|off` | Bildirishnomalar qancha tez-tez kelsin |
| `/kontaktlar`, `/kim <chat_id> <kim>` | Kim yozgan; kimligini belgilash |
| `/uslub [yangila]` | Uslub tahlili |
| `/holat` | Statistika va sozlamalar |
| `/eksport` | Xotiraning zaxira nusxasi (JSON) |
| `/yangi` | Suhbat tarixini tozalash (xotira o'chmaydi) |
| `/eslatma 45 <matn>` yoki `/eslatma 18:30 <matn>` | O'zingizga eslatma qo'yish (daqiqadan keyin yoki aniq vaqtda) |
| `/eslatmalar` | Faol eslatmalar ro'yxati |
| `/eslatma_ochir <id>` | Eslatmani bekor qilish |

Eslatmalar bazada saqlanadi, shuning uchun server qayta ishga tushsa ham (Render bepul tarifida bu tez-tez bo'lishi mumkin) yo'qolib ketmaydi — `DATABASE_URL` (Neon) ulangan bo'lsa.

**Bildirishnomaga reply:** botning "✉️ Ali yozdi..." xabariga reply qilib "ertaga bora olmayman de" deb yozsangiz, bot o'sha odamga sizning uslubingizda yuboradi. `!` bilan boshlasangiz (`!ertaga gaplashamiz`) so'zma-so'z yuboradi.

**Oddiy gapirib ham boshqarish mumkin:** "Faktlar ichidan telefon raqamimni o'chir", "Malika kimligini yozib qo'y: singlim", "Aliga ayt, soat 5 da kutaman".

---

## Xavfsizlik va maxfiylik

- **Maxfiy / ochiq faktlar.** Har bir fakt 🔒 *maxfiy* yoki 🔓 *ochiq*. Boshqalarga javob berayotganda bot **faqat ochiq** faktlarni ko'radi. Salomatlik, pul, hujjat, telefon, manzil kabilar avtomatik maxfiy bo'ladi. Nimaning ochiq bo'lishini `/fakt`, `/ochiq`, `/yopiq` bilan o'zingiz boshqarasiz.
- **Faqat siz boshqarasiz.** Buyruqlarni faqat `OWNER_ID` egasi bera oladi. Boshqa odam botni o'z Business akkauntiga ulasa ham, bot uni e'tiborsiz qoldiradi (API pulingiz xavfsiz).
- **Buyruqlar menyusi ham faqat sizga.** Boshqa odamlar botga `/start` bosganda faqat shuni ko'radi; `/fakt`, `/holat` kabi boshqaruv buyruqlari ularning Telegram menyusida umuman ko'rinmaydi.
- **Kalitlar** faqat Render Environment'da. Kodda yo'q.
- **Bot o'zini inson deb ko'rsatmaydi.** Agar kimdir jiddiy "bu botmi?" deb so'rasa, bot buni inkor qilmaydi: "bu yordamchi, egasi o'qiydi" deb aytadi. Xohlasangiz `AI_TAG=🤖` qo'yib har javobga belgi qo'shishingiz mumkin.
- **Bot nimaga javob bermaydi:** pul/qarz, parol va kodlar, shartnoma va va'dalar, hissiy inqirozlar, janjallar, o'zi bilmaydigan narsalar. Bunda senga "⏸ Javob bermadim: sabab" deb xabar yuboradi.
- **Sen o'zing chatga yozsang**, bot shu chatda `PAUSE_MINUTES` (30 daqiqa) jim turadi.
- Bitta chatga soatiga `MAX_REPLIES_PER_HOUR` dan ortiq javob bermaydi (aylanib ketishdan himoya).
- Boshqa odamlarning xabarlari ham bazada (suhbat tarixi sifatida) saqlanadi. Buni hisobga oling.

## Cheklovlar
- Ovozli xabar, video-xabar va rasmni bot tushunmaydi (faqat matn va sarlavha). Bunday xabarda "yozib yuboring" deb so'raydi yoki sizga xabar beradi.
- Business rejimi uchun Telegram Premium kerak.
- Guruhlarda ishlamaydi (faqat shaxsiy chatlar).
- Render bepul rejimida uxlab qolgan server birinchi xabarga sekinroq javob beradi (UptimeRobot buni hal qiladi).

## Xatolarni topish
| Muammo | Yechim |
|---|---|
| Deploy "XATO: muhit o'zgaruvchilari kiritilmagan" deydi | Render > Environment'da `BOT_TOKEN`, `ANTHROPIC_API_KEY`, `OWNER_ID` ni kiriting |
| Botga yozsam javob yo'q | Render Logs'ni oching; `Webhook o'rnatildi` bormi? Token to'g'rimi? |
| `/sinov` "Xato" deydi | API kalit yoki hisob puli; `MODEL` nomi to'g'rimi (masalan `claude-sonnet-4-5` sinab ko'ring) |
| Business chatda bot jim | BotFather'da *Business Mode* yoqilganmi? Telegram > Business > Chat-botlar'da "javob berish" huquqi bormi? |
| Server qayta ishga tushganda xotira yo'qoldi | `DATABASE_URL` kiritilmagan. Neon ulang |

## Fayllar
`main.py` (server), `handlers_owner.py` (siz bilan suhbat), `handlers_others.py` (boshqalarga javob), `brain.py` (xotira, uslub, tahlil), `llm.py` + `prompts.py` (Claude), `db.py` (baza), `importer.py` (chat eksporti), `sender.py` (yuborish), `config.py` (sozlamalar).
