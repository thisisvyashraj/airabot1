(() => {
  "use strict";

  const CSRF = document.body.dataset.csrf;

  // ─── fetch helper ────────────────────────────────────────────────────

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (opts.method && opts.method !== "GET") headers["X-CSRF-Token"] = CSRF;
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    let body = null;
    try { body = await res.json(); } catch (_) { /* no body */ }
    if (!res.ok) {
      const msg = (body && (body.detail || body.error)) || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return body;
  }

  function toast(message, kind = "ok") {
    const stack = document.getElementById("toast-stack");
    const el = document.createElement("div");
    el.className = `toast glass ${kind}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  function fmtTime(ts) {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleString();
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ─── nav / view switching ────────────────────────────────────────────

  const navItems = document.querySelectorAll(".nav-item");
  const views = document.querySelectorAll(".view");

  function showView(name) {
    views.forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
    navItems.forEach((n) => n.classList.toggle("active", n.dataset.view === name));
    loaders[name] && loaders[name]();
  }

  navItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      showView(item.dataset.view);
      history.replaceState(null, "", `#${item.dataset.view}`);
    });
  });

  // ─── logout ──────────────────────────────────────────────────────────

  document.getElementById("logoutBtn").addEventListener("click", async () => {
    try { await api("/logout", { method: "POST" }); } catch (_) {}
    window.location.href = "/login";
  });

  // ─── schema banner ───────────────────────────────────────────────────

  async function loadSchemaBanner() {
    try {
      const data = await api("/api/schema-check");
      const banner = document.getElementById("schemaBanner");
      const list = document.getElementById("schemaProblems");
      if (data.problems && data.problems.length) {
        list.innerHTML = data.problems.map((p) => `<li>${escapeHtml(p)}</li>`).join("");
        banner.classList.add("show");
      } else {
        banner.classList.remove("show");
      }
    } catch (_) { /* non-fatal */ }
  }

  // ─── status chip (polled everywhere) ────────────────────────────────

  async function refreshStatus() {
    try {
      const s = await api("/api/status");
      const dot = document.getElementById("statusDot");
      const text = document.getElementById("statusText");
      const active = (s.active || "").toLowerCase() === "active";
      dot.className = `status-dot ${active ? "on" : "off"}`;
      text.textContent = active ? "Bot running" : `Bot ${s.active || "unknown"}`;
    } catch (_) { /* keep last state */ }
  }

  // ─── OVERVIEW ────────────────────────────────────────────────────────

  async function loadOverview() {
    const tiles = document.getElementById("overviewTiles");
    tiles.innerHTML = `<div class="tile glass"><span class="num">…</span><span class="label">Loading</span></div>`;
    try {
      const [status, analytics] = await Promise.all([api("/api/status"), api("/api/analytics")]);
      tiles.innerHTML = `
        <div class="tile glass"><span class="num">${escapeHtml(status.active || "?")}</span><span class="label">Process state</span></div>
        <div class="tile glass"><span class="num">${analytics.total_users}</span><span class="label">Total users</span></div>
        <div class="tile glass"><span class="num">${analytics.total_groups}</span><span class="label">Groups</span></div>
        <div class="tile glass"><span class="num">${analytics.total_hunts}</span><span class="label">Total hunts</span></div>
      `;
    } catch (e) { toast(e.message, "err"); }
    refreshStatus();
  }

  document.querySelectorAll("[data-bot-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.botAction;
      btn.disabled = true;
      try {
        const res = await api(`/api/bot/${action}`, { method: "POST" });
        if (res.ok) {
          toast(`Bot ${action} succeeded.`);
          btn.classList.add("pulse-ok");
          setTimeout(() => btn.classList.remove("pulse-ok"), 700);
        } else {
          toast(res.stderr || `Bot ${action} failed.`, "err");
        }
      } catch (e) { toast(e.message, "err"); }
      finally { btn.disabled = false; refreshStatus(); loadOverview(); }
    });
  });

  // ─── USERS ───────────────────────────────────────────────────────────

  let usersPage = 1;
  let usersSearch = "";

  async function loadUsers() {
    const body = document.getElementById("usersBody");
    body.innerHTML = `<tr><td colspan="7">Loading…</td></tr>`;
    try {
      const data = await api(`/api/users?search=${encodeURIComponent(usersSearch)}&page=${usersPage}`);
      usersPage = data.page;
      document.getElementById("usersPageInfo").textContent = `Page ${data.page} of ${data.pages} · ${data.total} users`;
      if (!data.users.length) {
        body.innerHTML = `<tr><td colspan="7">No users found.</td></tr>`;
        return;
      }
      body.innerHTML = data.users.map((u) => `
        <tr data-uid="${escapeHtml(u._id)}">
          <td class="uid mono">${escapeHtml(u._id)}</td>
          <td>${escapeHtml(u.username || "—")}</td>
          <td>${escapeHtml(u.name || "—")}</td>
          <td>
            <span class="mono">${u.coins ?? 0}</span>
            <button class="btn btn-sm" data-adj="coins" data-delta="10">+10</button>
            <button class="btn btn-sm" data-adj="coins" data-delta="-10">-10</button>
          </td>
          <td>
            <span class="mono">${u.gems ?? 0}</span>
            <button class="btn btn-sm" data-adj="gems" data-delta="10">+10</button>
            <button class="btn btn-sm" data-adj="gems" data-delta="-10">-10</button>
          </td>
          <td class="mono" style="font-size:12px;">${u.hunts ?? 0} hunts · streak ${u.best_streak ?? 0}</td>
          <td class="row-actions">
            <button class="btn btn-sm" data-reset-cd title="Clear hunt/daily/boost cooldowns">Reset cooldowns</button>
            <button class="btn btn-sm" data-grant-badge title="Add a badge to this user">+ Badge</button>
            <button class="btn btn-sm" data-edit-raw>Edit</button>
          </td>
        </tr>
      `).join("");
    } catch (e) {
      body.innerHTML = `<tr><td colspan="7">Failed to load users.</td></tr>`;
      toast(e.message, "err");
    }
  }

  document.getElementById("usersBody").addEventListener("click", async (e) => {
    const row = e.target.closest("tr");
    if (!row) return;
    const uid = row.dataset.uid;

    if (e.target.matches("[data-adj]")) {
      const field = e.target.dataset.adj;
      const delta = parseInt(e.target.dataset.delta, 10);
      try {
        await api(`/api/users/${encodeURIComponent(uid)}/currency`, {
          method: "POST", body: JSON.stringify({ field, delta }),
        });
        toast(`${field} ${delta > 0 ? "+" : ""}${delta} for ${uid}`);
        loadUsers();
      } catch (err) { toast(err.message, "err"); }
    }

    if (e.target.matches("[data-edit-raw]")) {
      openRawModal(uid);
    }

    if (e.target.matches("[data-reset-cd]")) {
      try {
        await api(`/api/users/${encodeURIComponent(uid)}/reset-cooldowns`, { method: "POST" });
        toast(`Cooldowns cleared for ${uid}`);
      } catch (err) { toast(err.message, "err"); }
    }

    if (e.target.matches("[data-grant-badge]")) {
      const badge = prompt("Badge to grant (e.g. VIP, Beta Tester):");
      if (!badge) return;
      try {
        await api(`/api/users/${encodeURIComponent(uid)}/badge`, {
          method: "POST", body: JSON.stringify({ badge }),
        });
        toast(`"${badge}" granted to ${uid}`);
      } catch (err) { toast(err.message, "err"); }
    }
  });

  document.getElementById("userSearchBtn").addEventListener("click", () => {
    usersSearch = document.getElementById("userSearch").value;
    usersPage = 1;
    loadUsers();
  });
  document.getElementById("userSearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("userSearchBtn").click();
  });
  document.getElementById("usersPrev").addEventListener("click", () => { if (usersPage > 1) { usersPage--; loadUsers(); } });
  document.getElementById("usersNext").addEventListener("click", () => { usersPage++; loadUsers(); });

  // raw edit modal

  const rawBackdrop = document.getElementById("rawModalBackdrop");
  const rawTextarea = document.getElementById("rawModalTextarea");
  let rawModalUid = null;

  async function openRawModal(uid) {
    try {
      const user = await api(`/api/users/${encodeURIComponent(uid)}`);
      rawModalUid = uid;
      rawTextarea.value = JSON.stringify(user, null, 2);
      rawBackdrop.classList.add("active");
    } catch (e) { toast(e.message, "err"); }
  }

  document.getElementById("rawModalCancel").addEventListener("click", () => rawBackdrop.classList.remove("active"));

  document.getElementById("rawModalSave").addEventListener("click", async () => {
    try {
      const doc = JSON.parse(rawTextarea.value);
      await api(`/api/users/${encodeURIComponent(rawModalUid)}/raw`, {
        method: "POST", body: JSON.stringify({ doc }),
      });
      toast("User document saved.");
      rawBackdrop.classList.remove("active");
      loadUsers();
    } catch (e) { toast(e.message, "err"); }
  });

  document.getElementById("rawModalDelete").addEventListener("click", async () => {
    if (!confirm(`Delete user ${rawModalUid}? This can't be undone from here.`)) return;
    try {
      await api(`/api/users/${encodeURIComponent(rawModalUid)}`, { method: "DELETE" });
      toast("User deleted.");
      rawBackdrop.classList.remove("active");
      loadUsers();
    } catch (e) { toast(e.message, "err"); }
  });

  // ─── ANALYTICS ───────────────────────────────────────────────────────

  async function loadAnalytics() {
    const tiles = document.getElementById("analyticsTiles");
    tiles.innerHTML = `<div class="tile glass"><span class="num">…</span><span class="label">Loading</span></div>`;
    try {
      const a = await api("/api/analytics");
      tiles.innerHTML = `
        <div class="tile glass"><span class="num">${a.total_users}</span><span class="label">Total users</span></div>
        <div class="tile glass"><span class="num">${a.total_groups}</span><span class="label">Groups</span></div>
        <div class="tile glass"><span class="num">${a.total_coins}</span><span class="label">Coins in economy</span></div>
        <div class="tile glass"><span class="num">${a.total_gems}</span><span class="label">Gems in economy</span></div>
        <div class="tile glass"><span class="num">${a.total_hunts}</span><span class="label">Total hunts</span></div>
        <div class="tile glass"><span class="num">${a.total_coins_ever}</span><span class="label">Lifetime coins earned</span></div>
        <div class="tile glass"><span class="num">${a.users_with_pet}</span><span class="label">Users with a pet</span></div>
        <div class="tile glass"><span class="num">${a.top_streak}</span><span class="label">Top streak</span></div>
      `;
      document.getElementById("analyticsNote").textContent = a.note || "";
    } catch (e) { toast(e.message, "err"); }
  }
  document.getElementById("refreshAnalytics").addEventListener("click", loadAnalytics);

  // ─── ANNOUNCE ────────────────────────────────────────────────────────

  async function loadAnnounce() {
    try {
      const t = await api("/api/announce/targets");
      document.getElementById("announceTargets").textContent = t.count;
    } catch (e) { toast(e.message, "err"); }
  }

  document.getElementById("announceSend").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const text = document.getElementById("announceText").value;
    if (!text.trim()) { toast("Write something first.", "err"); return; }
    if (!confirm("Send this to every known chat right now?")) return;
    btn.disabled = true;
    try {
      const res = await api("/api/announce", { method: "POST", body: JSON.stringify({ text }) });
      toast(`Sent to ${res.sent}, failed for ${res.failed}.`);
      document.getElementById("announceText").value = "";
    } catch (e) { toast(e.message, "err"); }
    finally { btn.disabled = false; }
  });

  // ─── REDEEM ──────────────────────────────────────────────────────────

  async function loadRedeem() {
    const list = document.getElementById("redeemList");
    list.innerHTML = "Loading…";
    try {
      const data = await api("/api/redeem/list");
      if (!data.codes.length) { list.innerHTML = `<p>No active codes yet.</p>`; return; }
      list.innerHTML = data.codes.map((c) => `
        <span class="code-pill">
          ${escapeHtml(c.code)} · ${c.amount} ${escapeHtml(c.currency)}
          ${c.redeemed_by ? " · redeemed" : ""}
          <button class="btn btn-sm btn-ghost" data-revoke="${escapeHtml(c.code)}" title="Revoke">✕</button>
        </span>
      `).join("");
    } catch (e) { toast(e.message, "err"); }
  }

  document.getElementById("redeemList").addEventListener("click", async (e) => {
    if (!e.target.matches("[data-revoke]")) return;
    const code = e.target.dataset.revoke;
    try {
      await api(`/api/redeem/${encodeURIComponent(code)}`, { method: "DELETE" });
      toast(`${code} revoked.`);
      loadRedeem();
    } catch (err) { toast(err.message, "err"); }
  });

  document.getElementById("redeemCreate").addEventListener("click", async () => {
    const count = parseInt(document.getElementById("redeemCount").value, 10) || 1;
    const amount = parseInt(document.getElementById("redeemAmount").value, 10) || 1;
    const currency = document.getElementById("redeemCurrency").value;
    try {
      const res = await api("/api/redeem/create", { method: "POST", body: JSON.stringify({ count, amount, currency }) });
      toast(`Generated ${res.codes.length} code(s).`);
      loadRedeem();
    } catch (e) { toast(e.message, "err"); }
  });

  // ─── FILES ───────────────────────────────────────────────────────────

  let currentFilePath = null;

  function fileIcon(entry) {
    return entry.is_dir
      ? `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>`
      : `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3h9l3 3v15H6z"/></svg>`;
  }

  async function loadFileTree(path = "") {
    const tree = document.getElementById("fileTree");
    tree.innerHTML = "Loading…";
    try {
      const data = await api(`/api/files?path=${encodeURIComponent(path)}`);
      let rows = "";
      if (path) {
        const parent = path.split("/").slice(0, -1).join("/");
        rows += `<div class="file-row" data-nav="${escapeHtml(parent)}"><span class="fname">.. (up)</span></div>`;
      }
      rows += data.entries.map((e) => `
        <div class="file-row ${e.path === currentFilePath ? "selected" : ""}" data-${e.is_dir ? "nav" : "open"}="${escapeHtml(e.path)}" data-editable="${e.editable}">
          ${fileIcon(e)}<span class="fname">${escapeHtml(e.name)}</span>
        </div>
      `).join("");
      tree.innerHTML = rows || "<p>Empty directory.</p>";
    } catch (e) { tree.innerHTML = "Failed to load."; toast(e.message, "err"); }
  }

  document.getElementById("fileTree").addEventListener("click", async (e) => {
    const navRow = e.target.closest("[data-nav]");
    const openRow = e.target.closest("[data-open]");
    if (navRow) { loadFileTree(navRow.dataset.nav); return; }
    if (openRow) {
      const path = openRow.dataset.open;
      const editable = openRow.dataset.editable === "true";
      currentFilePath = path;
      document.getElementById("editorPath").textContent = path;
      document.getElementById("fileDownloadBtn").disabled = false;
      document.getElementById("fileDownloadBtn").onclick = () => window.open(`/api/files/download?path=${encodeURIComponent(path)}`, "_blank");
      const ta = document.getElementById("editorContent");
      if (!editable) {
        ta.value = "This file type isn't opened in the editor - use Download instead.";
        ta.disabled = true;
        document.getElementById("fileSaveBtn").disabled = true;
        return;
      }
      try {
        const data = await api(`/api/files/content?path=${encodeURIComponent(path)}`);
        ta.value = data.content;
        ta.disabled = false;
        document.getElementById("fileSaveBtn").disabled = false;
      } catch (err) { toast(err.message, "err"); }
    }
  });

  document.getElementById("fileSaveBtn").addEventListener("click", async () => {
    if (!currentFilePath) return;
    try {
      const res = await api("/api/files/save", {
        method: "POST", body: JSON.stringify({ path: currentFilePath, content: document.getElementById("editorContent").value }),
      });
      toast(res.backup ? "Saved (backup made)." : "Saved.");
    } catch (e) { toast(e.message, "err"); }
  });

  // ─── LOGS ────────────────────────────────────────────────────────────

  async function loadLogs() {
    const view = document.getElementById("logView");
    try {
      const data = await api("/api/logs");
      view.textContent = data.logs || "(no logs)";
      view.scrollTop = view.scrollHeight;
    } catch (e) { toast(e.message, "err"); }
  }
  document.getElementById("refreshLogs").addEventListener("click", loadLogs);

  // ─── OWNER COMMANDS ──────────────────────────────────────────────────

  async function loadOwner() {
    const list = document.getElementById("ownerList");
    list.innerHTML = "Loading…";
    try {
      const data = await api("/api/owner-commands");
      if (data.error) {
        list.innerHTML = `<div class="owner-cmd"><div class="meta" style="color:var(--chili);">${escapeHtml(data.error)}</div></div>`;
        return;
      }
      list.innerHTML = data.commands.map((c) => `
        <div class="owner-cmd">
          <div class="head">
            <span class="mono">${escapeHtml(c.snippet || c.name || "—")}</span>
            <span class="mono" style="color:var(--dust);">${c.file ? `${escapeHtml(c.file)}:${c.line}` : ""}</span>
          </div>
          <div class="meta">${escapeHtml(c.note || c.description || "")}</div>
        </div>
      `).join("");
    } catch (e) { list.innerHTML = "Failed to load."; toast(e.message, "err"); }
  }

  // ─── TERMINAL ────────────────────────────────────────────────────────

  let termInstance = null, termFit = null, termSocket = null, termConnecting = false;

  function connectTerminal() {
    if (termConnecting || (termSocket && termSocket.readyState === WebSocket.OPEN)) return;
    termConnecting = true;
    const statusEl = document.getElementById("terminalStatus");

    if (!termInstance) {
      termInstance = new Terminal({
        theme: {
          background: "#00000000",
          foreground: "#f2ecdf",
          cursor: "#e8b34c",
          selectionBackground: "rgba(232,179,76,0.35)",
        },
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 13,
        cursorBlink: true,
      });
      termFit = new FitAddon.FitAddon();
      termInstance.loadAddon(termFit);
      termInstance.open(document.getElementById("terminalContainer"));
      termFit.fit();
      termInstance.onData((data) => {
        if (termSocket && termSocket.readyState === WebSocket.OPEN) {
          termSocket.send(JSON.stringify({ type: "input", data }));
        }
      });
      window.addEventListener("resize", () => {
        if (document.getElementById("view-terminal").classList.contains("active")) termFit.fit();
      });
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    termSocket = new WebSocket(`${proto}//${window.location.host}/ws/terminal`);
    termSocket.binaryType = "arraybuffer";

    termSocket.onopen = () => {
      termConnecting = false;
      statusEl.textContent = "Connected";
      statusEl.classList.add("connected");
      const { cols, rows } = termInstance;
      termSocket.send(JSON.stringify({ type: "resize", cols, rows }));
      termFit.fit();
    };
    termSocket.onmessage = (ev) => {
      const bytes = ev.data instanceof ArrayBuffer ? new Uint8Array(ev.data) : null;
      if (bytes) termInstance.write(bytes);
    };
    termSocket.onclose = () => {
      termConnecting = false;
      statusEl.textContent = "Disconnected";
      statusEl.classList.remove("connected");
      termInstance.writeln("\r\n\x1b[33m[session ended]\x1b[0m");
    };
    termSocket.onerror = () => { termConnecting = false; };
  }

  // ─── SETTINGS ────────────────────────────────────────────────────────

  document.getElementById("changePassBtn").addEventListener("click", async () => {
    const current_password = document.getElementById("curPass").value;
    const new_password = document.getElementById("newPass").value;
    try {
      await api("/api/settings/password", { method: "POST", body: JSON.stringify({ current_password, new_password }) });
      toast("Password updated.");
      document.getElementById("curPass").value = "";
      document.getElementById("newPass").value = "";
    } catch (e) { toast(e.message, "err"); }
  });

  // ─── boot ────────────────────────────────────────────────────────────

  const loaders = {
    overview: loadOverview,
    users: loadUsers,
    analytics: loadAnalytics,
    announce: loadAnnounce,
    redeem: loadRedeem,
    files: () => loadFileTree(""),
    terminal: connectTerminal,
    logs: loadLogs,
    owner: loadOwner,
    settings: () => {},
  };

  loadSchemaBanner();
  const initial = (window.location.hash || "#overview").slice(1);
  showView(loaders[initial] ? initial : "overview");
  setInterval(refreshStatus, 15000);
})();
