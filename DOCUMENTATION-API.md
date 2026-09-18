# API Dokumentatsiyasi

Ushbu loyihada ishlatilgan API endpointlar. Barcha so'rovlar `Authorization: Bearer <token>`
sarlavhasini talab qiladi (aks holda `401 Unauthorized`). `online-mahalla.uz` va
`sr.ihma.uz` uchun **alohida** tokenlar kerak.

Umumiy javob konverti (online-mahalla.uz):
```json
{ "error": null, "message": null, "timestamp": "...", "status": 200, "path": null, "data": { ... }, "response": null }
```

---

## 1. Ko'chalar ro'yxati (streets)

Mahalladagi ko'chalar va ular bo'yicha statistika.

- **Metod:** `GET`
- **URL:** `https://api.online-mahalla.uz/api/v1/survey_homes/cache/street`
- **Query:** `obl_id`, `area_id`, `district_id`

**Namuna:**
```
GET https://api.online-mahalla.uz/api/v1/survey_homes/cache/street?obl_id=3&area_id=307&district_id=307032
```

**Javob (`data`):** `total` va `results[]`. Har bir element:

| Maydon | Izoh |
|---|---|
| `id` | Ko'cha id (street_id). `0` = "номаълум" |
| `name` | Ko'cha nomi |
| `homes_stat_count` | Jami uylar (statistik) |
| `homes_surveyed_count` | So'rov o'tkazilgan uylar |
| `population_surveyed_count` | So'rov o'tkazilgan aholi |
| `multistory_count`, `yard_count`, `dormitory_count` | Ko'p qavatli / hovli / yotoqxona soni |
| `youth_count`, `women_count`, `pensioner_count` | Yoshlar / ayollar / nafaqaxo'rlar |

---

## 2. Uylar ro'yxati (survey_homes_street)

Bitta ko'cha bo'yicha uylar ro'yxati (sahifalangan).

- **Metod:** `GET`
- **URL:** `https://api.online-mahalla.uz/api/v1/survey_homes_street/cache/data`
- **Query:** `obl_id`, `area_id`, `district_id`, `street_id`, `surveyed` (0/1), `page`, `size`

**Namuna:**
```
GET https://api.online-mahalla.uz/api/v1/survey_homes_street/cache/data?obl_id=3&area_id=307&district_id=307032&street_id=30700363&surveyed=0&page=1&size=100
```

**Javob (`data`):** `total` va `results[]`. Har bir element:

| Maydon | Izoh |
|---|---|
| `id` | Uy (forma) id |
| `cadaster_number` | Kadastr raqami |
| `full_name` | Uy egasi F.I.Sh (bo'sh bo'lsa `" - "`) |
| `mobile_phone` | Telefon (bo'sh bo'lsa `" - "`) |
| `pinfl` | Egasi PINFL (bo'sh bo'lsa `" - "`) |
| `ownership_type` | Egalik turi |
| `survey_date` | So'rov sanasi (DD.MM.YYYY) |
| `next_link` | Forma manzili: `forms/survey_homes/{id}?obl_id=...&street_id=...` |
| `_rownum` | Qator raqami |

**Eslatma:** Sahifalash — `results` uzunligi `size`dan kichik bo'lsa oxirgi sahifa.

---

## 3. Shaxs ma'lumoti (gcp/pinfl)

PINFL bo'yicha davlat registridan shaxs ma'lumotlari.

- **Metod:** `GET`
- **URL:** `https://api.online-mahalla.uz/api/v1/gcp/pinfl`
- **Query:** `pinfl`, `birth_date` (YYYY-MM-DD), `form_name` (`survey_homes` yoki `survey_homes_family`)
- **Diqqat:** Bu endpoint **rate-limit** qo'yadi — bir necha so'rovdan keyin `429 Too Many Requests`. Kutib qayta urinish (backoff) kerak.

**Namuna:**
```
GET https://api.online-mahalla.uz/api/v1/gcp/pinfl?pinfl=42510591220166&birth_date=1959-10-25&form_name=survey_homes
```

**Javob:** `data.data` ichida:

| Maydon | Izoh |
|---|---|
| `current_pinfl` | PINFL |
| `current_document` | Amaldagi hujjat, masalan `"AE3233009"` (seriya + raqam) |
| `full_name`, `sur_name`, `name`, `patronymic_name` | Ism ma'lumotlari |
| `birth_date` | Tug'ilgan sana (YYYY-MM-DD) |
| `birth_place`, `address` | Tug'ilgan joy / manzil |
| `gender` | Jins (1/2) |
| `tin` | STIR |
| `documents[]` | Hujjatlar ro'yxati (type_id, give_place, date_begin/end) |
| `pinfls[]` | Bog'liq PINFL'lar |

`data.code` va `data.message` ("OK"), `data.from_cache` ham bor.

---

## 4. survey_homes formasi

Bitta uy so'rovnomasini o'qish/yangilash.

- **O'qish (GET):** `https://api.online-mahalla.uz/web/v1/{next_link}`
  (masalan `.../web/v1/forms/survey_homes/4525480?obl_id=3&area_id=307&district_id=307032&street_id=30700363`)
- **Yozish (PUT):** xuddi shu URL, tanasida `formData` obyekti.

**GET javobi:** forma ta'rifi. Muhimi — `formData` obyekti (aynan PUT uchun kerak bo'lgan payload):
`survey_uuid`, `cadaster_number`, `street_id`, `pinfl`, `full_name`, `birth_date`, `passport`,
`mobile_phone`, `address`, `survey_date`, `photo[]`, `property_type`, `home_type`, `ownership`,
`home_registered`, `study_level_id`, `home_num`, `gas`, `electricity`, `drinking_water`,
`sewerage`, `income_id`, `has_debt`, `social_register`, `subsidy_applications` va h.k.

**Ish oqimi:** avval GET → `formData` olinadi → kerakli maydonlar to'ldiriladi (masalan pinfl,
full_name, birth_date, passport, address) → PUT bilan qaytariladi. `survey_uuid` va boshqa
mavjud maydonlar saqlanib qoladi.

---

## 5. Oila tarkibi (ihma FamilyFromIntegration)

PINFL bo'yicha oila a'zolarini (ota-ona, aka-uka, farzand) qaytaradi.

- **Metod:** `POST`
- **URL:** `https://sr.ihma.uz/api/ProposedFamilyMember/FamilyFromIntegration`
- **Auth:** `sr.ihma.uz` uchun **alohida** Bearer token
- **Tana (JSON):** `{ "pinFL": "50909085220116" }`

**Javob:** `data[]` (yoki `responseAsString` ichida JSON-string sifatida). Har bir a'zo:

| Maydon | Izoh |
|---|---|
| `traversal` | So'ralgan shaxsga nisbatan: `SELF`, `FATHER`, `MOTHER`, `BROTHER`, `SISTER`, `SON`, `DAUGHTER`, `SPOUSE`, ... |
| `certTraversal` | Guvohnoma bo'yicha munosabat |
| `pnfl` | A'zoning PINFL'i |
| `surname`, `name`, `patronym` | F.I.Sh |
| `birthDate` | Tug'ilgan sana (DD.MM.YYYY) |
| `gender` | `MALE` / `FEMALE` |
| `certSeries`, `certNumber`, `certDate` | Tug'ilganlik guvohnomasi |
| `relationShipID` | Munosabat kodi (R-03, R-04, ...) |
| `fFamily`/`f_family`, `fPnfl`/`f_pnfl`, `fBirthDay` ... | Ota ma'lumotlari |
| `mFamily`/`m_family`, `mPnfl`/`m_pnfl`, `mBirthDay` ... | Ona ma'lumotlari |
| `liveStatus` | Tiriklik holati ("1") |

> `data` — camelCase (`fFamily`), `responseAsString` — snake_case (`f_family`).

---

## 6. Oila a'zosini tekshirish (family/check)

A'zoni qo'shishdan oldin holatini tekshirish.

- **Metod:** `GET`
- **URL:** `https://api.online-mahalla.uz/api/v1/survey_homes/family/check`
- **Query:** `owner_pinfl` (uy egasi), `pinfl` (a'zo)

**Namuna:**
```
GET https://api.online-mahalla.uz/api/v1/survey_homes/family/check?owner_pinfl=42911690100027&pinfl=33006930260019
```

---

## 7. survey_homes_family formasi

Uy egasining oila a'zolarini qo'shish.

- **Formani ochish (GET):** modal URL (POST'dan oldin chaqiriladi)
- **A'zo qo'shish (POST):** xuddi shu URL, tanasida a'zo payloadi

**URL:**
```
https://api.online-mahalla.uz/web/v1/forms/survey_homes_family
  ?_target=modal
  &pinfl={owner_pinfl}
  &obl_id=3&area_id=307&district_id=307032&street_id=30700363
  &survey_uuid={survey_uuid}
  &owner_pinfl={owner_pinfl}
```
> URL'dagi `pinfl` = `owner_pinfl` (uy egasi). Payloaddagi `pinfl` = qo'shilayotgan a'zo.
> `survey_uuid` — uy egasining `survey_homes` formasidan (4-bo'lim) olinadi.

**POST payload:**
```json
{
  "address": "...",
  "birth_date": "1993-06-30",
  "doc_number": "2415717",
  "doc_serial": "AE",
  "document_type": "1",
  "full_name": "...",
  "phone": "...",
  "pinfl": 33006930260019,
  "relationship": "9",
  "study_level_id": "2"
}
```

**Majburiy maydonlar (server validatsiyasi):** `study_level_id`, `doc_serial`, `doc_number`
bo'sh bo'lmasligi kerak. Bo'sh yuborilsa `400 Bad Request`:
```json
{"status":400,"errors":{"study_level_id":"Bo'sh bo'lmasligi kerak"}}
```
> `doc_serial`/`doc_number` — gcp'da hujjat bo'lmagan a'zolarda (masalan voyaga yetmaganlar)
> bo'sh bo'lishi mumkin. `study_level_id` (ma'lumot darajasi) hech qaysi manbada yo'q —
> so'rovchi tomonidan qo'lda kiritilishi kutiladi.

### relationship (munosabat) qiymatlari

`traversal` (ihma) va tug'ilgan sanalarga qarab (aka/uka, opa/singil) hisoblanadi.
Formaga **string** sifatida yuboriladi ("9"):

| relationship | value |
|---|---|
| FATHER | 1 |
| MOTHER | 2 |
| OLDER_SISTER | 3 |
| OLDER_BROTHER | 4 |
| YOUNGER_SISTER | 5 |
| YOUNGER_BROTHER | 6 |
| SPOUSE | 7 |
| DAUGHTER | 8 |
| SON | 9 |
| FATHER_IN_LAW | 10 |
| MOTHER_IN_LAW | 11 |
| DAUGHTER_IN_LAW | 12 |
| OTHER | 13 |
| SON_IN_LAW | 14 |
| GRANDCHILD | 15 |

---

## 7a. Mavjud oila a'zolarini olish (survey_homes_family/data)

Bitta uy (survey_uuid) bo'yicha allaqachon kiritilgan oila a'zolari ro'yxati.
Oila tarkibini qo'shishdan oldin — takrorlamaslik uchun — tekshirish maqsadida ishlatiladi.

- **Metod:** `GET`
- **URL:** `https://api.online-mahalla.uz/web/v1/tables/survey_homes_family/data`
- **Query:** `obl_id`, `area_id`, `district_id`, `street_id`, `survey_uuid`

**Namuna:**
```
GET https://api.online-mahalla.uz/web/v1/tables/survey_homes_family/data?obl_id=3&area_id=307&district_id=307032&street_id=30700363&survey_uuid=5c2cd1d1-ea7f-4826-a3a1-4c9ddb8518c8
```

**Javob (`data`):** `total` va `results[]`. Har bir a'zo: `id`, `section`, `full_name`,
`relationship` (matnli: "хонадон эгаси", "Ўғли", "Турмуш ўртоғи", ...).

> `total` uy egasini ham hisoblaydi (section 0 = egasi). Shuning uchun `total > 1` bo'lsa —
> uyda allaqachon oila a'zolari kiritilgan, ya'ni yangi qo'shish **kerak emas** (skip).

---

## 8. Menyu (navigatsiya)

Foydalanuvchiga ko'rinadigan menyu daraxtini (sahifa havolalari bilan) qaytaradi.

- **Metod:** `GET`
- **URL:** `https://api.online-mahalla.uz/web/v1/menus`
- **Auth:** Bearer

**Javob:** menyu elementlari ro'yxati (ierarxik, `children[]` bilan). Har element:

| Maydon | Izoh |
|---|---|
| `id`, `projectId` | Menyu / loyiha id |
| `name` | Ko'rinadigan nom (masalan "Хонадонлар хатлови") |
| `link` | Sahifa yo'li (frontend route) yoki `null` (bo'lim sarlavhasi) |
| `cssClass`, `cssStyle`, `badge` | Ikonka / stil / belgi |
| `isHomepage`, `isTrackMenu`, `hasDividerBefore` | Bayroqlar |
| `children[]` | Ichki menyular |

> `link` ba'zan `fjs: (() => { ... })()` ko'rinishidagi **JS ifoda** (dinamik havola,
> `$user.oblId` kabi qiymatlarga qarab) yoki tashqi URL bo'lishi mumkin.

**Muhim havola — uylar xatlovi bo'limi:**

"Хонадонлар хатлови" menyu elementining `link`i:
```
tables/survey_homes?_level=4&obl_id=3&area_id=307&district_id=307032
```
Bu — frontend sahifa yo'li. Aynan shu bo'lim ichida ishlatiladigan `obl_id`, `area_id`,
`district_id` parametrlari 1-bo'limdagi **ko'chalar** (`survey_homes/cache/street`) va
2-bo'limdagi **uylar ro'yxati** (`survey_homes_street/cache/data`) API'lariga yuboriladi.
Ya'ni menyu havolasi — o'sha ko'chalar/uylar ma'lumotini oluvchi kirish nuqtasi.

Boshqa foydali havolalar: "Хонадонбай" → `pages/pa_survey`, "Чиқиш" → `system/logout`.

---

## Ilova: PINFL tuzilishi

PINFL (JSHSHIR) — 14 xonali. Undan tug'ilgan sana hisoblanadi:

- **1-raqam** → asr va jins: `1,2` → 18xx; `3,4` → 19xx; `5,6` → 20xx (toq = erkak, juft = ayol)
- **2–7 raqamlar** → tug'ilgan sana `DDMMYY`

Masalan `42510591220166` → `4` (19xx, ayol) + `251059` → **25.10.1959**.

---

## Ilova: Umumiy holatlar

- **401 Unauthorized** — token yo'q/eskirgan.
- **429 Too Many Requests** — rate-limit (ayniqsa `gcp/pinfl`). Kutib qayta urinish kerak.
- **400 Bad Request** — payload xato yoki majburiy maydon bo'sh (`errors` obyektida tafsilot).
