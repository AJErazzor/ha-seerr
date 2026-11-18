/*
 * Seerr Requests Card
 * Shows pending Seerr requests with fanart, who/when, summary, links and
 * Approve / Reject buttons. Served automatically by the seerr_requests integration.
 */
const CARD_VERSION = "0.2.0";
const DOMAIN = "seerr_requests";

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : "");
const cssUrl = (u) => {
  const s = safeUrl(u);
  return s && !/["'()\\\s]/.test(s) ? s : "";
};

function relTime(iso) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d} day${d === 1 ? "" : "s"} ago`;
  return new Date(t).toLocaleDateString();
}

function exactTime(iso, lang) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  return new Date(t).toLocaleString(lang || undefined, {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function seasonText(seasons) {
  if (!Array.isArray(seasons) || !seasons.length) return "";
  const s = [...new Set(seasons)].sort((a, b) => a - b);
  if (s.length === 1) return `Season ${s[0]}`;
  const run = s.every((v, i) => i === 0 || v === s[i - 1] + 1);
  return run ? `Seasons ${s[0]}–${s[s.length - 1]}` : `Seasons ${s.join(", ")}`;
}

const initials = (name) =>
  String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";

const DEFAULTS = {
  title: "Seerr requests",
  show_pending: true,
  show_approved: true,
  show_fanart: true,
  show_summary: true,
  show_links: true,
  max_items: 0,
};

const STATUS = {
  approved: { label: "Approved", icon: "mdi:check-circle-outline" },
  downloading: { label: "Downloading", icon: "mdi:download" },
  partially_available: { label: "Partially available", icon: "mdi:progress-check" },
};

// The approved sensor lives next to the pending one unless the card says otherwise.
const approvedEntityFor = (config) =>
  config.approved_entity || String(config.entity || "").replace(/pending_requests$/, "approved_requests");

const STYLE = `
  :host { display:block; }
  ha-card { overflow:hidden; }
  .header { display:flex; align-items:center; justify-content:space-between; padding:16px 16px 8px; }
  .header .name { font-size:1.2em; font-weight:500; color:var(--primary-text-color); }
  .count { background:var(--primary-color); color:var(--text-primary-color,#fff); border-radius:12px; padding:2px 10px; font-size:.85em; font-weight:600; }
  .list { display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr)); padding:4px 16px 16px; }
  .section { padding:8px 16px 0; font-size:.8em; font-weight:600; letter-spacing:.04em; text-transform:uppercase;
             color:var(--secondary-text-color); }
  .none { padding:0 16px 12px; font-size:.85em; color:var(--secondary-text-color); }
  .status { display:flex; align-items:center; gap:4px; font-size:.85em; font-weight:600; margin-top:auto; padding-top:4px; }
  .status ha-icon { --mdc-icon-size:18px; }
  .status.downloading { color:var(--info-color,#039be5); }
  .req.fanart.has-bg .status.downloading { color:#7fd3ff; }
  .status.partially_available { color:var(--warning-color,#ffa600); }
  .empty { padding:8px 16px 24px; text-align:center; color:var(--secondary-text-color); }
  .empty ha-icon { --mdc-icon-size:40px; color:var(--success-color,#4caf50); display:block; margin:0 auto 6px; }
  .warn { padding:16px; color:var(--error-color,#db4437); }

  .req { position:relative; border-radius:12px; overflow:hidden; background:var(--secondary-background-color);
         transition:opacity .35s ease, transform .35s ease; }
  .req.done { opacity:0; transform:scale(.97); pointer-events:none; }
  .req .bg { position:absolute; inset:0; background-size:cover; background-position:center top; }
  .req.fanart.has-bg .bg::after { content:""; position:absolute; inset:0;
     background:linear-gradient(90deg,rgba(0,0,0,.88) 0%,rgba(0,0,0,.68) 55%,rgba(0,0,0,.45) 100%); }
  .req.fanart.has-bg { color:#fff; --sec:rgba(255,255,255,.75); --chip:rgba(255,255,255,.16); }
  .req:not(.has-bg), .req.compact { color:var(--primary-text-color); --sec:var(--secondary-text-color); --chip:var(--divider-color,rgba(127,127,127,.2)); }
  .inner { position:relative; display:flex; gap:12px; padding:12px; }
  .poster { flex:0 0 auto; width:92px; aspect-ratio:2/3; border-radius:8px; object-fit:cover; background:var(--chip);
            box-shadow:0 2px 8px rgba(0,0,0,.35); }
  .compact .poster { width:56px; }
  .body { flex:1 1 auto; min-width:0; display:flex; flex-direction:column; gap:6px; }
  .title { font-weight:600; font-size:1.05em; line-height:1.25; }
  .title .year { font-weight:400; color:var(--sec); }
  .badges { display:flex; flex-wrap:wrap; gap:4px; }
  .badge { background:var(--chip); border-radius:6px; padding:1px 7px; font-size:.75em; font-weight:500; }
  .badge.k4 { background:#f5c518; color:#000; }
  .who { display:flex; align-items:center; gap:6px; font-size:.85em; color:var(--sec); flex-wrap:wrap; }
  .avatar-wrap { position:relative; width:22px; height:22px; flex:0 0 auto; }
  .avatar-wrap .ini { position:absolute; inset:0; border-radius:50%; background:var(--primary-color); color:#fff;
                      font-size:10px; font-weight:700; display:flex; align-items:center; justify-content:center; }
  .avatar-wrap img { position:absolute; inset:0; width:100%; height:100%; border-radius:50%; object-fit:cover; }
  .who .name { color:inherit; font-weight:600; }
  .time { background:none; border:0; padding:0; color:inherit; font:inherit; cursor:pointer; text-decoration:underline dotted; }
  .summary { font-size:.85em; line-height:1.4; color:var(--sec); }
  .summary.clamp { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
  .more { background:none; border:0; padding:0; color:inherit; font:inherit; font-size:.8em; font-weight:600; cursor:pointer; align-self:flex-start; opacity:.85; }
  .links { display:flex; flex-wrap:wrap; gap:6px; }
  .links a { font-size:.75em; font-weight:600; text-decoration:none; color:inherit; background:var(--chip);
             border-radius:6px; padding:3px 8px; }
  .actions { display:flex; gap:8px; margin-top:auto; padding-top:4px; }
  .actions button { flex:1; border:0; border-radius:8px; padding:8px 10px; font:inherit; font-weight:600; font-size:.9em;
                    cursor:pointer; color:#fff; display:flex; align-items:center; justify-content:center; gap:4px; }
  .actions button[disabled] { opacity:.6; cursor:default; }
  .approve { background:var(--success-color,#43a047); }
  .decline { background:var(--error-color,#e53935); }
  .decline.confirm { background:#b71c1c; }
  .actions ha-icon { --mdc-icon-size:18px; }
`;

class SeerrRequestsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._expanded = new Set();
    this._exact = new Set();
    this._busy = new Set();
    this._done = new Set();
    this._confirm = new Map();
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
    // Broken avatar → fall back to initials underneath.
    this.shadowRoot.addEventListener("error", (e) => {
      if (e.target?.classList?.contains("avatar")) e.target.remove();
    }, true);
  }

  static getConfigElement() {
    return document.createElement("seerr-requests-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {}).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes?.requests)
    );
    return { entity: entity || "sensor.seerr_pending_requests" };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("Choose the Seerr pending requests sensor");
    this._config = { ...DEFAULTS, ...config };
    this._lastState = undefined;
    this._lastApproved = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const st = hass.states[this._config?.entity];
    const ap = hass.states[approvedEntityFor(this._config || {})];
    if (st !== this._lastState || ap !== this._lastApproved) {
      this._lastState = st;
      this._lastApproved = ap;
      // Forget per-request UI state for requests that are gone.
      const ids = new Set(
        [...(st?.attributes?.requests || []), ...(ap?.attributes?.requests || [])].map((r) => r.id)
      );
      for (const set of [this._expanded, this._exact, this._busy, this._done]) {
        for (const id of [...set]) if (!ids.has(id)) set.delete(id);
      }
      this._render();
    }
  }

  connectedCallback() {
    this._tick = setInterval(() => this._render(), 60000); // keep "x min ago" fresh
  }

  disconnectedCallback() {
    clearInterval(this._tick);
    for (const t of this._confirm.values()) clearTimeout(t);
    this._confirm.clear();
  }

  getCardSize() {
    const n =
      (this._lastState?.attributes?.requests?.length || 0) +
      (this._lastApproved?.attributes?.requests?.length || 0);
    return 1 + Math.max(1, n) * (this._config?.show_fanart ? 3 : 2);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el) return;
    const id = Number(el.dataset.id);
    const act = el.dataset.act;
    if (act === "more") {
      this._expanded.has(id) ? this._expanded.delete(id) : this._expanded.add(id);
      this._render();
    } else if (act === "time") {
      this._exact.has(id) ? this._exact.delete(id) : this._exact.add(id);
      this._render();
    } else if (act === "approve" || act === "decline") {
      this._act(id, act);
    }
  }

  async _act(id, action) {
    if (this._busy.has(id) || this._done.has(id)) return;
    if (action === "decline" && !this._confirm.has(id)) {
      // Two taps to reject, so a stray tap doesn't throw a request away.
      this._confirm.set(id, setTimeout(() => { this._confirm.delete(id); this._render(); }, 4000));
      this._render();
      return;
    }
    clearTimeout(this._confirm.get(id));
    this._confirm.delete(id);
    this._busy.add(id);
    this._render();
    try {
      await this._hass.callService(DOMAIN, action, { request_id: id });
      this._done.add(id);
    } catch (err) {
      this._toast(err?.message || `Couldn't ${action} the request`);
    } finally {
      this._busy.delete(id);
      this._render();
    }
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
  }

  _renderRequest(r, approved = false) {
    const c = this._config;
    const id = Number(r.id);
    const bg = c.show_fanart ? cssUrl(r.backdrop) : "";
    const poster = safeUrl(r.poster);
    const avatar = safeUrl(r.requested_by_avatar);
    const busy = this._busy.has(id);
    const confirming = this._confirm.has(id);
    const lang = this._hass?.locale?.language;
    const overview = String(r.overview || "");
    const expanded = this._expanded.has(id);

    const badges = [`<span class="badge">${r.type === "tv" ? "TV" : "Movie"}</span>`];
    if (r.type === "tv" && r.seasons?.length) badges.push(`<span class="badge">${esc(seasonText(r.seasons))}</span>`);
    if (r.is4k) badges.push(`<span class="badge k4">4K</span>`);

    const link = (href, label) => (safeUrl(href) ? `<a href="${esc(safeUrl(href))}" target="_blank" rel="noopener noreferrer">${label}</a>` : "");
    const links = c.show_links
      ? [link(r.tmdb_url, "TMDB"), link(r.imdb_url, "IMDb"), link(r.tvdb_url, "TVDB"), link(r.seerr_url, "Open in Seerr")].filter(Boolean).join("")
      : "";

    const timeLabel = this._exact.has(id) ? exactTime(r.requested_at, lang) : relTime(r.requested_at);

    return `
      <div class="req ${c.show_fanart ? "fanart" : "compact"} ${bg ? "has-bg" : ""} ${this._done.has(id) ? "done" : ""}">
        ${bg ? `<div class="bg" style="background-image:url('${bg}')"></div>` : ""}
        <div class="inner">
          ${poster ? `<img class="poster" src="${esc(poster)}" alt="" loading="lazy">` : `<div class="poster"></div>`}
          <div class="body">
            <div class="title">${esc(r.title)}${r.year ? ` <span class="year">(${esc(r.year)})</span>` : ""}</div>
            <div class="badges">${badges.join("")}</div>
            <div class="who">
              <span class="avatar-wrap"><span class="ini">${esc(initials(r.requested_by))}</span>${avatar ? `<img class="avatar" src="${esc(avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}</span>
              <span class="name">${esc(r.requested_by)}</span>
              ${timeLabel ? `<span>·</span><button class="time" data-act="time" data-id="${id}" title="${esc(exactTime(r.requested_at, lang))}">${esc(timeLabel)}</button>` : ""}
            </div>
            ${c.show_summary && overview ? `
              <div class="summary ${expanded ? "" : "clamp"}">${esc(overview)}</div>
              ${overview.length > 160 ? `<button class="more" data-act="more" data-id="${id}">${expanded ? "less" : "more"}</button>` : ""}` : ""}
            ${links ? `<div class="links">${links}</div>` : ""}
            ${approved ? this._renderStatus(r) : `<div class="actions">
              <button class="approve" data-act="approve" data-id="${id}" ${busy ? "disabled" : ""}>
                <ha-icon icon="mdi:check"></ha-icon>${busy ? "Working…" : "Approve"}
              </button>
              <button class="decline ${confirming ? "confirm" : ""}" data-act="decline" data-id="${id}" ${busy ? "disabled" : ""}>
                <ha-icon icon="mdi:close"></ha-icon>${confirming ? "Tap again to reject" : "Reject"}
              </button>
            </div>`}
          </div>
        </div>
      </div>`;
  }

  _renderStatus(r) {
    const st = STATUS[r.status] || STATUS.approved;
    const by = r.approved_by ? ` by ${esc(r.approved_by)}` : "";
    return `<div class="status ${esc(r.status || "approved")}"><ha-icon icon="${st.icon}"></ha-icon>${st.label}${r.status === "approved" ? by : ""}</div>`;
  }

  _list(reqs, approved) {
    const max = this._config.max_items;
    const shown = max > 0 ? reqs.slice(0, max) : reqs;
    return `<div class="list">${shown.map((r) => this._renderRequest(r, approved)).join("")}</div>`;
  }

  _render() {
    if (!this._config) return;
    const c = this._config;
    const st = this._lastState;
    let body;
    if (!this._hass) {
      body = "";
    } else if (!st) {
      body = `<div class="warn">Entity not found: ${esc(c.entity)}</div>`;
    } else {
      const pending = Array.isArray(st.attributes?.requests) ? st.attributes.requests : [];
      const apState = this._lastApproved;
      const approved = Array.isArray(apState?.attributes?.requests) ? apState.attributes.requests : [];
      const showPending = c.show_pending !== false;
      const showApproved = c.show_approved !== false && !!apState;
      const both = showPending && showApproved;
      const parts = [];
      if (showPending) {
        if (both) parts.push(`<div class="section">Waiting for approval</div>`);
        if (pending.length) parts.push(this._list(pending, false));
        else if (both && approved.length) parts.push(`<div class="none">Nothing waiting for approval</div>`);
      }
      if (showApproved && approved.length) {
        if (both) parts.push(`<div class="section">Approved · on its way</div>`);
        parts.push(this._list(approved, true));
      }
      const nothing = (!showPending || !pending.length) && (!showApproved || !approved.length);
      body = nothing
        ? `<div class="empty"><ha-icon icon="mdi:check-circle-outline"></ha-icon>All caught up — nothing waiting</div>`
        : parts.join("");
    }
    const count =
      c.show_pending !== false && Array.isArray(st?.attributes?.requests) ? st.attributes.requests.length : 0;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        ${c.title ? `<div class="header"><span class="name">${esc(c.title)}</span>${count ? `<span class="count">${count}</span>` : ""}</div>` : ""}
        ${body}
      </ha-card>`;
  }
}

const EDITOR_SCHEMA = [
  { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: DOMAIN } } },
  {
    name: "approved_entity",
    selector: { entity: { domain: "sensor", integration: DOMAIN } },
  },
  { name: "title", selector: { text: {} } },
  {
    type: "grid",
    name: "",
    schema: [
      { name: "show_pending", selector: { boolean: {} } },
      { name: "show_approved", selector: { boolean: {} } },
    ],
  },
  {
    type: "grid",
    name: "",
    schema: [
      { name: "show_fanart", selector: { boolean: {} } },
      { name: "show_summary", selector: { boolean: {} } },
      { name: "show_links", selector: { boolean: {} } },
    ],
  },
  { name: "max_items", selector: { number: { min: 0, max: 50, mode: "box" } } },
];

const EDITOR_LABELS = {
  entity: "Pending requests sensor",
  approved_entity: "Approved requests sensor (optional, found automatically)",
  show_pending: "Show waiting for approval",
  show_approved: "Show approved · on its way",
  title: "Title",
  show_fanart: "Show fanart",
  show_summary: "Show summary",
  show_links: "Show TMDB / IMDb / TVDB links",
  max_items: "Maximum requests to show (0 = all)",
};

class SeerrRequestsCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => EDITOR_LABELS[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = EDITOR_SCHEMA;
    this._form.data = { ...DEFAULTS, ...this._config };
  }
}

if (!customElements.get("seerr-requests-card")) {
  customElements.define("seerr-requests-card", SeerrRequestsCard);
  customElements.define("seerr-requests-card-editor", SeerrRequestsCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "seerr-requests-card",
    name: "Seerr Requests",
    description: "Pending Seerr requests with fanart and Approve / Reject buttons",
    preview: true,
    documentationURL: "https://github.com/AJErazzor/ha-seerr",
  });
  console.info(`%c SEERR-REQUESTS-CARD %c v${CARD_VERSION} `, "background:#6366f1;color:#fff;font-weight:700", "");
}
