"""Excel -> yozuvlar ro'yxati.

Ustunlar (0-indeks): A = kadastr (0), B = pinfl (1).
Birinchi qator — sarlavha (title), o'tkazib yuboriladi.
Bo'sh pinfl -> bo'sh qoldiriladi (tasodifiy qiymat QO'YILMAYDI).
"""

import openpyxl

from .pinfl import birth_date_ddmmyyyy

COL_KADASTR = 0
COL_PINFL = 1


def parse_excel(file_obj):
    """Fayl obyekti (yoki yo'l) -> [{'kadastr','pinfl','birth_date'}, ...]."""
    wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    next(rows, None)  # sarlavha

    records = []
    for row in rows:
        if row is None or all(v is None for v in row):
            continue
        kadastr = row[COL_KADASTR] if len(row) > COL_KADASTR else None
        pinfl = row[COL_PINFL] if len(row) > COL_PINFL else None
        pinfl = "" if pinfl is None else str(pinfl).strip()
        if pinfl in ("", "-"):
            pinfl = ""
        records.append({
            "kadastr": "" if kadastr is None else str(kadastr).strip(),
            "pinfl": pinfl,
            "birth_date": birth_date_ddmmyyyy(pinfl) or "",
        })
    return records
