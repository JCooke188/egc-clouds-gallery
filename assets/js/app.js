/* EGC clouds site script.
   Content lives in content/site.json; figures and videos in media/manifest.json.
   Nothing here needs editing to add media: use tools/add_media.py. */
(function () {
  "use strict";

  const page = document.body.dataset.page;

  async function loadJSON(path) {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${path} returned ${res.status}`);
    return res.json();
  }

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children) if (c) node.append(c);
    return node;
  }

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso + "T12:00:00");
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
  }

  function formatDuration(s) {
    if (!s && s !== 0) return "";
    const m = Math.floor(s / 60), r = Math.round(s % 60);
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  function paragraphs(text) {
    const frag = document.createDocumentFragment();
    String(text || "").split(/\n\s*\n/).filter(Boolean)
      .forEach(p => frag.append(el("p", { text: p.trim() })));
    return frag;
  }

  function showLoadError(err) {
    const main = document.getElementById("main");
    const box = el("div", { class: "empty", role: "alert" });
    box.append(el("p", { text: `Could not load site content (${err.message}).` }));
    if (location.protocol === "file:") {
      box.append(el("p", {
        text: "Browsers block these requests for pages opened straight from disk. " +
              "From the repository folder run: python -m http.server 8000, then open http://localhost:8000"
      }));
    }
    main.prepend(box);
  }

  /* Shared site content */
  function fillSite(site, items) {
    document.querySelectorAll("[data-site]").forEach(n => {
      const v = site[n.dataset.site];
      if (v) n.textContent = v;
    });
    if (page === "home" && site.short_title) document.title = site.short_title;
    if (page === "gallery" && site.short_title) document.title = `Gallery | ${site.short_title}`;

    const summary = document.querySelector("[data-site-paragraphs]");
    if (summary) {
      summary.textContent = "";
      (site.summary || []).forEach(p => summary.append(el("p", { text: p })));
    }

    const links = document.querySelector("[data-site-links]");
    if (links) {
      (site.links || []).forEach(l => links.append(el("li", {}, el("a", { href: l.url, text: l.label }))));
    }

    const team = document.querySelector("[data-team]");
    if (team) {
      const groups = new Map();
      (site.team || []).forEach(m => {
        if (!groups.has(m.institution)) groups.set(m.institution, []);
        groups.get(m.institution).push(m);
      });
      const wrap = el("div", { class: "team-groups" });
      for (const [inst, members] of groups) {
        const ul = el("ul");
        members.forEach(m => {
          const name = m.url ? el("a", { href: m.url, text: m.name }) : document.createTextNode(m.name);
          ul.append(el("li", {}, name, m.role ? el("span", { class: "role", text: m.role }) : null));
        });
        wrap.append(el("section", {}, el("h3", { text: inst }), ul));
      }
      team.append(wrap);
    }

    const footer = document.querySelector("[data-footer]");
    if (footer) {
      const latest = items.map(i => i.date).filter(Boolean).sort().pop();
      const parts = [];
      if (latest) parts.push(`Last figure added ${formatDate(latest)}.`);
      if (site.contact && site.contact.name) {
        parts.push(site.contact.email
          ? `Questions: ${site.contact.name}, ${site.contact.email}.`
          : `Questions: ${site.contact.name}.`);
      }
      parts.push("Figures may show preliminary results; please ask before reusing them.");
      footer.textContent = parts.join(" ");
    }
  }

  /* Tiles */
  const PLAY = '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1l7 4-7 4z"/></svg>';

  function tile(item, href) {
    const plate = el("span", { class: "plate" },
      el("img", { src: item.thumb || item.poster || item.file, alt: "", loading: "lazy", decoding: "async" }));
    if (item.type === "video") {
      const badge = el("span", { class: "badge" });
      badge.innerHTML = PLAY;
      badge.append(document.createTextNode(item.duration_s ? `Video, ${formatDuration(item.duration_s)}` : "Video"));
      plate.append(badge);
    }
    const meta = [formatDate(item.date), (item.tags || []).slice(0, 3).join(", ")].filter(Boolean).join(". ");
    return el("li", {}, el("a", { class: "tile", href },
      plate,
      el("span", { class: "tile-title", text: item.title }),
      el("span", { class: "tile-meta", text: meta })));
  }

  function byDate(a, b) { return (b.date || "").localeCompare(a.date || ""); }

  /* Home */
  function renderHome(items) {
    const featured = items.filter(i => i.featured).sort(byDate).slice(0, 6);
    if (!featured.length) return;
    const list = document.querySelector("[data-featured]");
    featured.forEach(i => list.append(tile(i, `gallery.html#${encodeURIComponent(i.id)}`)));
    document.querySelector(".featured").hidden = false;
  }

  /* Gallery */
  function renderGallery(items) {
    const form = document.querySelector(".filters");
    const grid = document.querySelector("[data-grid]");
    const count = document.querySelector("[data-count]");
    const empty = document.querySelector("[data-empty]");
    const state = { q: "", kind: "all", sort: "new", tags: new Set() };
    let visible = [];

    const allTags = [...new Set(items.flatMap(i => i.tags || []))].sort((a, b) => a.localeCompare(b));
    if (allTags.length) {
      const holder = document.querySelector("[data-tag-list]");
      allTags.forEach(t => {
        const b = el("button", { type: "button", class: "tag", "aria-pressed": "false", text: t });
        b.addEventListener("click", () => {
          state.tags.has(t) ? state.tags.delete(t) : state.tags.add(t);
          b.setAttribute("aria-pressed", String(state.tags.has(t)));
          draw();
        });
        holder.append(b);
      });
      document.querySelector("[data-tags]").hidden = false;
    }

    function haystack(i) {
      return [i.title, i.caption, (i.tags || []).join(" "), (i.data_sources || []).join(" ")]
        .join(" ").toLowerCase();
    }

    function draw() {
      const q = state.q.trim().toLowerCase();
      visible = items.filter(i =>
        (state.kind === "all" || i.type === state.kind) &&
        (!q || haystack(i).includes(q)) &&
        [...state.tags].every(t => (i.tags || []).includes(t)));
      visible.sort(byDate);
      if (state.sort === "old") visible.reverse();

      grid.textContent = "";
      visible.forEach(i => grid.append(tile(i, `#${encodeURIComponent(i.id)}`)));

      const n = visible.length;
      count.textContent = items.length ? `${n} of ${items.length} ${items.length === 1 ? "item" : "items"}` : "";
      empty.textContent = "";
      empty.hidden = n > 0;
      if (!items.length) {
        empty.append(
          el("p", { text: "No figures or videos yet." }),
          el("p", { text: "Add one from the repository folder with:" }),
          el("p", {}, el("code", { text: 'python tools/add_media.py path/to/figure.png --title "..." --caption "..."' })));
      } else if (!n) {
        const clear = el("button", { type: "button", class: "tag", text: "Clear filters" });
        clear.addEventListener("click", () => {
          form.reset(); state.q = ""; state.kind = "all"; state.sort = "new"; state.tags.clear();
          form.querySelectorAll(".tag[aria-pressed]").forEach(b => b.setAttribute("aria-pressed", "false"));
          draw();
        });
        empty.append(el("p", { text: "Nothing matches these filters." }), clear);
      }
    }

    form.addEventListener("input", e => {
      if (e.target.name === "q") state.q = e.target.value;
      if (e.target.name === "kind") state.kind = e.target.value;
      if (e.target.name === "sort") state.sort = e.target.value;
      draw();
    });

    /* Viewer */
    const dlg = document.querySelector("[data-viewer]");
    const media = dlg.querySelector("[data-viewer-media]");
    const title = dlg.querySelector("[data-viewer-title]");
    const caption = dlg.querySelector("[data-viewer-caption]");
    const meta = dlg.querySelector("[data-viewer-meta]");
    const full = dlg.querySelector("[data-fullres]");
    const copyBtn = dlg.querySelector("[data-copy]");
    let current = null;

    function row(label, value) {
      if (!value) return;
      meta.append(el("dt", { text: label }), el("dd", {}, value));
    }

    function open(item) {
      current = item;
      media.textContent = "";
      media.classList.toggle("is-video", item.type === "video");
      if (item.type === "video") {
        media.append(el("video", {
          src: item.file, poster: item.poster, controls: true, preload: "metadata",
          playsinline: true, "aria-label": item.alt || item.title
        }));
      } else {
        media.append(el("img", { src: item.file, alt: item.alt || item.title }));
      }
      title.textContent = item.title;
      caption.textContent = "";
      caption.append(paragraphs(item.caption));
      meta.textContent = "";
      row("Date", item.date ? document.createTextNode(formatDate(item.date)) : null);
      row("Data", (item.data_sources || []).length ? document.createTextNode(item.data_sources.join("; ")) : null);
      if (item.code) {
        const label = [item.code.path, item.code.commit && `at ${item.code.commit}`].filter(Boolean).join(" ");
        row("Code", item.code.url ? el("a", { href: item.code.url, text: label || item.code.url }) :
          document.createTextNode(label));
      }
      if (item.full_res && item.full_res.doi) {
        row("DOI", el("a", { href: `https://doi.org/${item.full_res.doi}`, text: item.full_res.doi }));
      }
      row("Tags", (item.tags || []).length ? document.createTextNode(item.tags.join(", ")) : null);

      if (item.full_res && item.full_res.url) {
        full.href = item.full_res.url;
        full.textContent = item.full_res.label ? `Full resolution (${item.full_res.label})` : "Download full resolution";
        full.hidden = false;
      } else {
        full.hidden = true;
      }
      copyBtn.textContent = "Copy link";
      if (!dlg.open) dlg.showModal();
    }

    function step(delta) {
      if (!current || !visible.length) return;
      let idx = visible.findIndex(i => i.id === current.id);
      idx = (idx + delta + visible.length) % visible.length;
      location.hash = encodeURIComponent(visible[idx].id);
    }

    function fromHash() {
      const id = decodeURIComponent(location.hash.slice(1));
      if (!id) { if (dlg.open) dlg.close(); return; }
      const item = items.find(i => i.id === id);
      if (item) open(item);
    }

    dlg.addEventListener("close", () => {
      const v = media.querySelector("video");
      if (v) v.pause();
      media.textContent = "";
      current = null;
      if (location.hash) history.replaceState(null, "", location.pathname + location.search);
    });
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener("keydown", e => {
      if (e.target.tagName === "VIDEO" || e.target.tagName === "INPUT") return;
      if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    });
    dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
    dlg.querySelector("[data-next]").addEventListener("click", () => step(1));
    dlg.querySelector("[data-prev]").addEventListener("click", () => step(-1));
    copyBtn.addEventListener("click", async () => {
      const url = location.origin + location.pathname + "#" + encodeURIComponent(current.id);
      try {
        await navigator.clipboard.writeText(url);
        copyBtn.textContent = "Link copied";
      } catch (_) {
        window.prompt("Copy this link:", url);
      }
    });

    window.addEventListener("hashchange", fromHash);
    draw();
    fromHash();
  }

  Promise.all([loadJSON("content/site.json"), loadJSON("media/manifest.json")])
    .then(([site, manifest]) => {
      const items = (manifest.items || []).filter(i => i && i.id && i.file);
      fillSite(site, items);
      if (page === "home") renderHome(items);
      if (page === "gallery") renderGallery(items);
    })
    .catch(showLoadError);
})();
