# Mahalla tizimi (Django)

Fuqaro ma'lumotlari va oila tarkibini boshqarish uchun lokal web-tizim.
Barcha API'lar `../DOCUMENTATION-API.md` da hujjatlashtirilgan.

## Ishga tushirish

```bash
cd NEW-PROJECT
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

So'ng brauzerda: http://127.0.0.1:8000

## Oqim (1-bo'lim: Fuqaro ma'lumotlari)

1. **Mahalla qo'shish** (nom, obl_id, area_id, district_id).
2. Mahalla ichida **Bearer token** kiritib saqlash (istalgan vaqt yangilash mumkin).
3. **Baza**: Excel (`royxat.xlsx`) yuklash → kadastr, pinfl olinadi, pinfl'dan tug'ilgan sana
   hisoblanadi va bazaga saqlanadi. (Bazasi bo'lsa qayta yuklash shart emas.)
4. **Ko'chalarni olish** (street API) va kerakli ko'chalarni tanlash.
5. **Static maydonlar**ni ko'rib chiqib (kerak bo'lsa o'zgartirib) **Boshlash**.
6. Ish fonda ketadi — sahifa refresh bo'lsa ham davom etadi; statistika va loglar
   jonli ko'rinib turadi. **To'xtatish** mumkin; keyin yana boshlansa, allaqachon
   to'ldirilganlar qayta yuborilmaydi.

Turli mahallalarni turli tablarda bir vaqtda ishlatish mumkin (bloklash yo'q).

## Muhim eslatma

- Kod **tasodifiy/uydirma qiymat yozmaydi**. Identity maydonlar gcp'dan (haqiqiy) olinadi,
  static maydonlar esa foydalanuvchi tomonidan kiritiladi.
- `gcp/pinfl` rate-limit qo'yadi — so'rovlar orasida 15s kutiladi + 429 da backoff.
