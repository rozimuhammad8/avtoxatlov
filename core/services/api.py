"""online-mahalla.uz API klienti.

Endpointlar DOCUMENTATION-API.md da hujjatlashtirilgan:
  - ko'chalar: survey_homes/cache/street
  - uylar:     survey_homes_street/cache/data (sahifalangan)
  - shaxs:     gcp/pinfl (rate-limit -> 15s throttle + 429 backoff)
  - forma:     web/v1/{next_link} (GET/PUT)
"""

import json
import time

import requests

API_BASE = "https://api.online-mahalla.uz"
STREET_URL = f"{API_BASE}/api/v1/survey_homes/cache/street"
HOMES_URL = f"{API_BASE}/api/v1/survey_homes_street/cache/data"
GCP_URL = f"{API_BASE}/api/v1/gcp/pinfl"
WEB_BASE = f"{API_BASE}/web/v1/"
CHECK_URL = f"{API_BASE}/api/v1/survey_homes/family/check"
FAMILY_DATA_URL = f"{API_BASE}/web/v1/tables/survey_homes_family/data"
IHMA_URL = "https://sr.ihma.uz/api/ProposedFamilyMember/FamilyFromIntegration"

MAX_RETRIES = 6
RETRY_BASE = 10
GCP_MIN_INTERVAL = 15  # gcp so'rovlari orasidagi minimal vaqt (soniya)


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, token, ihma_token=None, gcp_min_interval=GCP_MIN_INTERVAL):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        self.ihma = requests.Session()
        if ihma_token:
            self.ihma.headers.update({
                "Authorization": f"Bearer {ihma_token}",
                "Accept": "application/json",
            })
        self.gcp_min_interval = gcp_min_interval
        self._last_gcp = 0.0

    # --- past darajali so'rov (429 da kutib qayta urinadi) ---
    def _request(self, method, url, stop_event=None, session=None, **kwargs):
        sess = session or self.session
        resp = None
        for attempt in range(1, MAX_RETRIES + 1):
            if stop_event is not None and stop_event.is_set():
                raise ApiError("to'xtatildi")
            resp = sess.request(method, url, timeout=30, **kwargs)
            if resp.status_code != 429:
                return resp
            ra = resp.headers.get("Retry-After")
            wait = float(ra) if (ra and ra.replace(".", "", 1).isdigit()) else RETRY_BASE * attempt
            if stop_event is not None:
                # kutishni bo'laklarga bo'lib, to'xtatishga tez javob beramiz
                slept = 0.0
                while slept < wait:
                    if stop_event.is_set():
                        raise ApiError("to'xtatildi")
                    time.sleep(min(1.0, wait - slept))
                    slept += 1.0
            else:
                time.sleep(wait)
        return resp

    # --- ko'chalar ---
    def streets(self, mahalla):
        r = self._request("GET", STREET_URL, params={
            "obl_id": mahalla.obl_id, "area_id": mahalla.area_id,
            "district_id": mahalla.district_id,
        })
        r.raise_for_status()
        data = r.json().get("data") or {}
        return data.get("results") or []

    # --- uylar (sahifalab qaytaradi) ---
    def iter_homes(self, mahalla, street_id, surveyed=0, size=100, stop_event=None):
        page = 1
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            r = self._request("GET", HOMES_URL, stop_event=stop_event, params={
                "obl_id": mahalla.obl_id, "area_id": mahalla.area_id,
                "district_id": mahalla.district_id, "street_id": street_id,
                "surveyed": surveyed, "page": page, "size": size,
            })
            r.raise_for_status()
            data = r.json().get("data") or {}
            results = data.get("results") or []
            if not results:
                return
            for home in results:
                yield home
            if len(results) < size:
                return
            page += 1

    # --- gcp/pinfl (15s throttle) ---
    def gcp(self, pinfl, birth_date_iso, form_name, stop_event=None):
        # throttle: oxirgi gcp so'rovidan kamida gcp_min_interval o'tsin
        wait = self.gcp_min_interval - (time.monotonic() - self._last_gcp)
        while wait > 0:
            if stop_event is not None and stop_event.is_set():
                raise ApiError("to'xtatildi")
            time.sleep(min(1.0, wait))
            wait = self.gcp_min_interval - (time.monotonic() - self._last_gcp)
        r = self._request("GET", GCP_URL, stop_event=stop_event, params={
            "pinfl": pinfl, "birth_date": birth_date_iso, "form_name": form_name,
        })
        self._last_gcp = time.monotonic()
        r.raise_for_status()
        return (r.json().get("data") or {}).get("data") or {}

    # --- forma GET/PUT ---
    def get_form(self, next_link, stop_event=None):
        r = self._request("GET", WEB_BASE + next_link, stop_event=stop_event)
        r.raise_for_status()
        return r.json()

    def put_form(self, next_link, payload, stop_event=None):
        r = self._request("PUT", WEB_BASE + next_link, stop_event=stop_event, json=payload)
        r.raise_for_status()
        return r

    # --- OILA (family) ---
    def ihma_family(self, pinfl, stop_event=None):
        """sr.ihma.uz dan oila tarkibini qaytaradi (dict'lar ro'yxati)."""
        r = self._request("POST", IHMA_URL, stop_event=stop_event,
                          session=self.ihma, json={"pinFL": str(pinfl)})
        r.raise_for_status()
        j = r.json()
        data = j.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        ras = j.get("responseAsString")
        if isinstance(ras, str) and ras.strip():
            try:
                return [x for x in json.loads(ras) if isinstance(x, dict)]
            except json.JSONDecodeError:
                return []
        return []

    def family_existing_count(self, params, survey_uuid, stop_event=None):
        """Uy (survey_uuid) bo'yicha allaqachon kiritilgan a'zolar soni (egasi ham kiradi)."""
        p = {**params, "survey_uuid": survey_uuid}
        r = self._request("GET", FAMILY_DATA_URL, stop_event=stop_event, params=p)
        r.raise_for_status()
        data = r.json().get("data") or {}
        total = data.get("total")
        if isinstance(total, int):
            return total
        return len(data.get("results") or [])

    def family_check(self, owner_pinfl, member_pinfl, stop_event=None):
        r = self._request("GET", CHECK_URL, stop_event=stop_event,
                          params={"owner_pinfl": owner_pinfl, "pinfl": member_pinfl})
        r.raise_for_status()
        return r.json()

    def form_get(self, url, stop_event=None):
        """To'liq forma URL bo'yicha GET (formani ochish)."""
        r = self._request("GET", url, stop_event=stop_event)
        r.raise_for_status()
        return r

    def form_post(self, url, payload, stop_event=None):
        r = self._request("POST", url, stop_event=stop_event, json=payload)
        r.raise_for_status()
        return r
