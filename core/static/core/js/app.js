(function () {
  const page = document.querySelector(".page");
  if (!page) return;

  const urls = JSON.parse(page.dataset.urls);
  const staticCitizen = JSON.parse(page.dataset.static || "{}");
  const staticFamily = JSON.parse(page.dataset.familyStatic || "{}");
  const selectedInit = JSON.parse(page.dataset.selected || "[]");
  const csrf = document.querySelector('meta[name="csrf"]').content;

  const $ = (s, r = document) => r.querySelector(s);
  const streetsBox = $("#streets");

  const labels = {
    mobile_phone: "Telefon", survey_date: "So'rov sanasi (bo'sh=bugun)",
    property_type: "property_type", home_type: "home_type", ownership: "ownership",
    home_registered: "home_registered", study_level_id: "study_level_id (bo'sh=null)",
    home_num: "home_num", document_type: "document_type", phone: "phone (bo'sh=null)",
  };

  // ko'cha tanlovi — ikkala bo'lim uchun UMUMIY
  let selectedStreets = Array.isArray(selectedInit) ? selectedInit.slice() : [];
  const isSelected = (id) => selectedStreets.some((x) => String(x.id) === String(id));

  function renderStreets(list) {
    streetsBox.innerHTML = "";
    if (!list.length) { streetsBox.innerHTML = '<p class="muted">Ko\'cha yo\'q.</p>'; return; }
    list.forEach((s) => {
      const chip = document.createElement("div");
      chip.className = "chip" + (isSelected(s.id) ? " on" : "");
      const meta = s.homes != null ? ` <small>${s.surveyed ?? 0}/${s.homes}</small>` : "";
      chip.innerHTML = `${s.name}${meta}`;
      chip.addEventListener("click", () => {
        chip.classList.toggle("on");
        if (chip.classList.contains("on")) selectedStreets.push({ id: s.id, name: s.name });
        else selectedStreets = selectedStreets.filter((x) => String(x.id) !== String(s.id));
      });
      streetsBox.appendChild(chip);
    });
  }

  async function loadStreets() {
    streetsBox.innerHTML = '<p class="muted">Yuklanmoqda...</p>';
    try {
      const r = await fetch(urls.streets);
      const d = await r.json();
      if (!d.ok) throw new Error(d.error || "xato");
      renderStreets(d.streets);
    } catch (e) {
      if (selectedStreets.length) renderStreets(selectedStreets);
      else streetsBox.innerHTML = `<p class="muted">Xatolik: ${e.message}</p>`;
    }
  }
  $("#btn-streets").addEventListener("click", loadStreets);
  if (selectedStreets.length) loadStreets();

  // --- segmented (A/B) ---
  document.querySelectorAll(".seg").forEach((seg) => {
    seg.addEventListener("click", () => {
      if (seg.disabled) return;
      document.querySelectorAll(".seg").forEach((s) => s.classList.remove("active"));
      seg.classList.add("active");
      document.querySelectorAll(".section[data-sec]").forEach((el) => {
        el.hidden = el.dataset.sec !== seg.dataset.sec;
      });
    });
  });

  // --- har bir bo'lim boshqaruvi ---
  function setupSection(secEl, sectionName, staticDefaults) {
    const sf = secEl.querySelector(".sf");
    const startBtn = secEl.querySelector(".bt-start");
    const stopBtn = secEl.querySelector(".bt-stop");
    const pill = secEl.querySelector(".st-pill");
    const logsEl = secEl.querySelector(".lg");

    Object.keys(staticDefaults).forEach((k) => {
      const w = document.createElement("label");
      w.style.fontSize = "12px"; w.style.color = "var(--muted)";
      w.innerHTML = `${labels[k] || k}<input data-sf="${k}" value="${staticDefaults[k] ?? ""}">`;
      sf.appendChild(w);
    });
    const readStatic = () => {
      const o = {};
      sf.querySelectorAll("input[data-sf]").forEach((i) => (o[i.dataset.sf] = i.value));
      return o;
    };

    startBtn.addEventListener("click", async () => {
      if (!selectedStreets.length) { alert("Kamida bitta ko'cha tanlang."); return; }
      startBtn.disabled = true;
      try {
        const r = await fetch(urls.start, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify({ section: sectionName, streets: selectedStreets, static: readStatic() }),
        });
        const d = await r.json();
        if (!d.ok) throw new Error(d.error || "xato");
      } catch (e) {
        alert("Boshlashda xatolik: " + e.message);
        startBtn.disabled = false;
      }
    });

    stopBtn.addEventListener("click", async () => {
      stopBtn.disabled = true;
      await fetch(urls.stop + "?section=" + sectionName, {
        method: "POST", headers: { "X-CSRFToken": csrf },
      });
    });

    function apply(d) {
      const running = d.status === "running" || d.status === "stopping" || d.running;
      pill.textContent = d.status;
      pill.className = "status-pill " + d.status;
      startBtn.disabled = running;
      stopBtn.disabled = !running;
      Object.entries(d.stats || {}).forEach(([k, v]) => {
        const el = secEl.querySelector(`.stat .n[data-k="${k}"]`);
        if (el) el.textContent = v;
      });
      logsEl.textContent = (d.logs || []).join("\n");
      logsEl.scrollTop = logsEl.scrollHeight;
    }

    async function poll() {
      try {
        const r = await fetch(urls.status + "?section=" + sectionName);
        const d = await r.json();
        if (d.ok) apply(d);
      } catch (e) { /* jim */ }
    }
    poll();
    setInterval(poll, 2000);
  }

  setupSection(document.querySelector('.section[data-sec="citizen"]'), "citizen", staticCitizen);
  setupSection(document.querySelector('.section[data-sec="family"]'), "family", staticFamily);
})();
