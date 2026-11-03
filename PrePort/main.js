(() => {
  const p = window.PROFILE;
  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Hero
  $("hero-name").textContent = p.name;
  $("hero-title").textContent = p.title;
  $("hero-tagline").textContent = p.tagline;
  const mailto = `mailto:${p.email}`;
  $("hero-mail").href = mailto;
  if (p.resumeUrl) {
    $("hero-resume").href = p.resumeUrl;
    $("hero-resume").hidden = false;
  }

  // About
  $("about-text").innerHTML = p.about.paragraphs.map((t) => `<p>${esc(t)}</p>`).join("");
  $("about-stats").innerHTML = p.about.highlights
    .map((h) => `<li><strong class="mono">${esc(h.value)}</strong><span>${esc(h.label)}</span></li>`)
    .join("");

  // Skills
  const levelText = { 3: "실무 주도", 2: "실무 사용", 1: "기초" };
  $("skills-grid").innerHTML = p.skills
    .map(
      (g) => `
      <article class="card">
        <h3>${esc(g.category)}</h3>
        <ul class="skill-list">
          ${g.items
            .map(
              (s) => `<li><span>${esc(s.name)}</span>
                <i class="dots" data-level="${s.level}" title="${levelText[s.level]}" aria-label="${levelText[s.level]}"></i></li>`
            )
            .join("")}
        </ul>
      </article>`
    )
    .join("");

  // Experience
  $("timeline").innerHTML = p.experience
    .map(
      (e) => `
      <li>
        <div class="tl-head">
          <h3>${esc(e.company)}</h3>
          <span class="mono period">${esc(e.period)}</span>
        </div>
        <p class="role">${esc(e.role)}</p>
        <ul>${e.achievements.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
      </li>`
    )
    .join("");

  // Projects
  $("projects-grid").innerHTML = p.projects
    .map(
      (pr) => `
      <article class="card project">
        <p class="mono period">${esc(pr.period)}</p>
        <h3>${esc(pr.name)}</h3>
        <dl>
          <dt>대상 시스템</dt><dd>${esc(pr.system)}</dd>
          <dt>역할</dt><dd>${esc(pr.role)}</dd>
        </dl>
        <ul class="results">${pr.results.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        <ul class="tags">${pr.tools.map((t) => `<li class="mono">${esc(t)}</li>`).join("")}</ul>
      </article>`
    )
    .join("");

  // Certifications
  $("certs").innerHTML = p.certifications
    .map(
      (c) => `<li><span class="cert-name">${esc(c.name)}</span>
        <span class="cert-meta">${esc(c.issuer)} · <span class="mono">${esc(c.year)}</span></span></li>`
    )
    .join("");

  // Contact
  $("contact-mail").href = mailto;
  $("contact-mail").textContent = p.email;
  $("contact-links").innerHTML = p.links
    .map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ↗</a></li>`)
    .join("");
  $("footer-name").textContent = p.name;
  $("year").textContent = new Date().getFullYear();

  // 이메일 복사
  const toast = $("toast");
  let toastTimer;
  const showToast = (msg) => {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 1800);
  };
  $("copy-btn").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(p.email);
      showToast("이메일 주소를 복사했어요");
    } catch {
      showToast(p.email);
    }
  });

  // 테마 전환 (시스템 설정 기본, 선택 시 저장)
  const root = document.documentElement;
  try {
    const saved = localStorage.getItem("theme");
    if (saved) root.dataset.theme = saved;
  } catch {}
  document.querySelector(".theme-toggle").addEventListener("click", () => {
    const current =
      root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {}
  });
})();
