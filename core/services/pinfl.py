"""PINFL yordamchi funksiyalari."""

CENTURY = {"1": 1800, "2": 1800, "3": 1900, "4": 1900, "5": 2000, "6": 2000}


def _parts(pinfl):
    s = str(pinfl or "").strip()
    if len(s) != 14 or not s.isdigit():
        return None
    century = CENTURY.get(s[0])
    if century is None:
        return None
    day, month, yy = s[1:3], s[3:5], s[5:7]
    try:
        d, m = int(day), int(month)
    except ValueError:
        return None
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return None
    return day, month, century + int(yy)


def birth_date_ddmmyyyy(pinfl):
    """PINFL -> 'DD.MM.YYYY' yoki None."""
    p = _parts(pinfl)
    if not p:
        return None
    day, month, year = p
    return f"{day}.{month}.{year}"


def birth_date_iso(pinfl):
    """PINFL -> 'YYYY-MM-DD' yoki None."""
    p = _parts(pinfl)
    if not p:
        return None
    day, month, year = p
    return f"{year:04d}-{month}-{day}"


def ddmmyyyy_to_iso(s):
    """'07.02.1979' -> '1979-02-07'."""
    try:
        d, m, y = str(s).strip().split(".")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, AttributeError):
        return None
