// Browser test for the dashboard card (jsdom). Run: node tests/card.test.mjs
// Needs jsdom: NODE_PATH=<node_modules with jsdom> node tests/card.test.mjs
import { createRequire } from "module";
const { JSDOM } = createRequire(import.meta.url)(process.env.NODE_PATH ? `${process.env.NODE_PATH}/jsdom` : "jsdom");
import fs from "fs";
const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { runScripts: "outside-only", pretendToBeVisual: true });
const w = dom.window;
const cardPath = process.argv[2] || new URL("../custom_components/seerr_requests/frontend/seerr-requests-card.js", import.meta.url);
w.eval(fs.readFileSync(cardPath, "utf8"));
const calls = [];
const now = Date.now();
const reqs = [
  { id: 11, type: "movie", title: "Dune <b>x</b>", year: "2024", overview: "A".repeat(200), poster: "https://image.tmdb.org/t/p/w342/p.jpg",
    backdrop: "https://image.tmdb.org/t/p/w1280/b.jpg", requested_by: "Bob Smith", requested_by_avatar: "https://seerr.example.com/avatarproxy/abc",
    requested_at: new Date(now - 2*3600e3).toISOString(), is4k: false, seasons: [], tmdb_url: "https://www.themoviedb.org/movie/1", imdb_url: "https://www.imdb.com/title/tt1/", tvdb_url: null, seerr_url: "https://seerr.example.com/movie/1" },
  { id: 12, type: "tv", title: "Severance", year: "2022", overview: "Short", poster: null, backdrop: "javascript:alert(1)", requested_by: "Sue",
    requested_by_avatar: null, requested_at: new Date(now - 30e3).toISOString(), is4k: true, seasons: [1,2,3], tmdb_url: "https://www.themoviedb.org/tv/2", imdb_url: null, tvdb_url: "https://thetvdb.com/dereferrer/series/3", seerr_url: "https://seerr.example.com/tv/2" },
];
const approvedReqs = [
  { ...reqs[0], id: 20, status: "approved", approved_by: "A.J." },
  { ...reqs[1], id: 21, status: "downloading", approved_by: "A.J." },
  { ...reqs[1], id: 22, status: "partially_available" },
];
const mkHass = (r, ap = null) => ({ locale: { language: "en-AU" }, states: {
    "sensor.seerr_pending_requests": { state: String(r.length), attributes: { requests: r } },
    ...(ap ? { "sensor.seerr_approved_requests": { state: String(ap.length), attributes: { requests: ap } } } : {}) },
  callService: async (d, s, data) => { calls.push([d, s, data]); } });
const card = w.document.createElement("seerr-requests-card");
card.setConfig({ entity: "sensor.seerr_pending_requests" });
w.document.body.appendChild(card);
card.hass = mkHass(reqs);
const sr = card.shadowRoot;
const ok = (c, m) => { if (!c) { console.log("FAIL:", m); process.exitCode = 1; } else console.log("ok:", m); };
ok(sr.querySelectorAll(".req").length === 2, "two requests rendered");
ok(!sr.querySelector(".title b"), "title HTML escaped");
ok(sr.querySelector(".req .bg").style.backgroundImage.includes("w1280"), "fanart on first");
ok(sr.querySelectorAll(".bg").length === 1, "unsafe backdrop dropped");
ok(sr.textContent.includes("2 hours ago") && sr.textContent.includes("just now"), "relative times");
ok(sr.textContent.includes("Seasons 1–3") && sr.querySelector(".k4"), "season + 4K badges");
ok([...sr.querySelectorAll(".req")[1].querySelectorAll(".links a")].map(a=>a.textContent).join() === "TMDB,TVDB,Open in Seerr", "tv links");
ok(sr.querySelector(".count").textContent === "2", "count badge");
sr.querySelector('[data-act="more"]').click();
ok(!sr.querySelector(".summary").classList.contains("clamp"), "more expands");
sr.querySelector('[data-act="time"]').click();
ok(/2026|\d{4}/.test(sr.querySelector(".time").textContent), "tap time shows exact: " + sr.querySelector(".time").textContent);
sr.querySelector('.approve[data-id="11"]').click();
await new Promise(r => setTimeout(r, 10));
ok(calls.length === 1 && calls[0][1] === "approve" && calls[0][2].request_id === 11, "approve calls service");
sr.querySelector('.decline[data-id="12"]').click();
ok(calls.length === 1 && sr.textContent.includes("Tap again"), "reject needs confirm");
sr.querySelector('.decline[data-id="12"]').click();
await new Promise(r => setTimeout(r, 10));
ok(calls.length === 2 && calls[1][1] === "decline", "second tap declines");
card.hass = mkHass([]);
ok(sr.textContent.includes("All caught up"), "empty state");
card.setConfig({ entity: "sensor.seerr_pending_requests", show_fanart: false, show_summary: false, show_links: false });
card.hass = mkHass(reqs);
ok(sr.querySelectorAll(".compact").length === 2 && !sr.querySelector(".bg") && !sr.querySelector(".summary") && !sr.querySelector(".links"), "options off");
card.setConfig({ entity: "sensor.seerr_pending_requests" });
card.hass = mkHass(reqs, approvedReqs);
ok(sr.querySelectorAll(".req").length === 5, "pending + approved rendered");
ok(sr.textContent.includes("Waiting for approval") && sr.textContent.includes("Approved · on its way"), "section headings");
ok(sr.querySelectorAll(".actions").length === 2, "only pending have buttons");
ok(sr.textContent.includes("Approved by A.J.") && sr.textContent.includes("Downloading") && sr.textContent.includes("Partially available"), "status badges");
ok(sr.querySelector(".count").textContent === "2", "count is pending only");
card.hass = mkHass([], approvedReqs);
ok(sr.textContent.includes("Nothing waiting for approval") && sr.querySelectorAll(".req").length === 3, "no pending, approved shown");
card.setConfig({ entity: "sensor.seerr_pending_requests", show_pending: false });
card.hass = mkHass(reqs, approvedReqs);
ok(sr.querySelectorAll(".req").length === 3 && !sr.querySelector(".section") && !sr.querySelector(".actions"), "approved-only card");
card.setConfig({ entity: "sensor.seerr_pending_requests", show_approved: false });
card.hass = mkHass(reqs, approvedReqs);
ok(sr.querySelectorAll(".req").length === 2 && !sr.querySelector(".section"), "pending-only card");
// Card mistakenly pointed at the APPROVED sensor: requests still land in the right sections,
// and approved ones never get Approve / Reject.
card.setConfig({ entity: "sensor.seerr_approved_requests" });
card.hass = mkHass(reqs.map((r) => ({ ...r, status: "pending" })), approvedReqs);
ok(sr.querySelectorAll(".req").length === 5, "approved-sensor card shows both lists");
ok(sr.querySelectorAll(".actions").length === 2 && sr.querySelector(".count").textContent === "2", "buttons only on pending (approved-sensor card)");
// A request that is in both sensors (stale overlap) appears once, in its real section.
const dup = { ...approvedReqs[0], id: 11, status: "approved" };
card.setConfig({ entity: "sensor.seerr_pending_requests" });
card.hass = mkHass([{ ...reqs[0], status: "approved" }, { ...reqs[1], status: "pending" }], [dup]);
ok(sr.querySelectorAll(".req").length === 2 && sr.querySelectorAll(".actions").length === 1, "approved request never offered Approve");
card.setConfig({ entity: "sensor.seerr_pending_requests" });
card.hass = mkHass([], []);
ok(sr.textContent.includes("All caught up"), "both empty");
const stub = w.customElements.get("seerr-requests-card").getStubConfig({ states: {
  "sensor.seerr_approved_requests": { attributes: { kind: "approved", requests: [] } },
  "sensor.seerr_pending_requests": { attributes: { kind: "pending", requests: [] } } } });
ok(stub.entity === "sensor.seerr_pending_requests", "new card picks the pending sensor");
const ed = w.document.createElement("seerr-requests-card-editor");
ed.setConfig({ entity: "x" }); ed.hass = mkHass([]);
ok(ed.querySelector("ha-form") && ed.querySelector("ha-form").data.show_fanart === true, "editor defaults");
ok(w.customCards.some(c => c.type === "seerr-requests-card"), "registered in card picker");
card.remove();
process.exit(process.exitCode || 0);
