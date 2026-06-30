// ── Setup ────────────────────────────────────────────────────────────────
const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) { tg.ready(); tg.expand(); }

const params = new URLSearchParams(location.search);
const GAME_ID = params.get("game");
const MY_UID = parseInt(params.get("uid"), 10);
const MY_NAME = params.get("name") || "You";

const PIECE_GLYPH = {
  P: "♙", N: "♘", B: "♗", R: "♖", Q: "♕", K: "♔",
  p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚",
};

let state = null;          // last known server state
let selected = null;       // currently selected square (e.g. "e2")
let legalTargets = [];     // squares the selected piece can move to
let myColor = null;        // "white" | "black" | null (spectator)
let lastMove = null;       // [from, to]
let ws = null;
let clockTimer = null;

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status-line");

// ── FEN parsing ─────────────────────────────────────────────────────────
function fenToBoard(fen) {
  const rows = fen.split(" ")[0].split("/");
  const grid = {}; // "e4" -> piece char
  for (let r = 0; r < 8; r++) {
    let file = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) { file += parseInt(ch, 10); continue; }
      const square = "abcdefgh"[file] + (8 - r);
      grid[square] = ch;
      file++;
    }
  }
  return grid;
}

function squareColor(file, rank) { return (file + rank) % 2 === 0 ? "dark" : "light"; }

// ── Rendering ───────────────────────────────────────────────────────────
function render() {
  if (!state) return;
  boardEl.innerHTML = "";
  const grid = fenToBoard(state.fen);
  const flip = myColor === "black";
  const files = "abcdefgh".split("");
  const ranks = [8, 7, 6, 5, 4, 3, 2, 1];
  const orderedRanks = flip ? [...ranks].reverse() : ranks;
  const orderedFiles = flip ? [...files].reverse() : files;

  for (const rank of orderedRanks) {
    for (const file of orderedFiles) {
      const sq = file + rank;
      const fIdx = files.indexOf(file), rIdx = ranks.indexOf(rank);
      const div = document.createElement("div");
      div.className = "sq " + squareColor(fIdx, rIdx);
      div.dataset.square = sq;
      if (selected === sq) div.classList.add("selected");
      if (legalTargets.includes(sq)) {
        div.classList.add("target");
        if (grid[sq]) div.classList.add("has-piece");
      }
      if (lastMove && lastMove.includes(sq)) div.classList.add("last-move");
      const piece = grid[sq];
      if (piece) {
        const span = document.createElement("span");
        span.className = "piece";
        span.textContent = PIECE_GLYPH[piece];
        div.appendChild(span);
      }
      div.addEventListener("click", () => onSquareClick(sq));
      boardEl.appendChild(div);
    }
  }
  updateSideLabels();
  updateStatusLine();
}

function updateSideLabels() {
  const topIsWhite = myColor === "black"; // if I'm black, white sits on top
  const topName = topIsWhite ? state.white_name : state.black_name;
  const bottomName = topIsWhite ? state.black_name : state.white_name;
  document.getElementById("top-name").textContent = topName || "Waiting…";
  document.getElementById("bottom-name").textContent = bottomName || "Waiting…";
  document.getElementById("mode-label").textContent =
    state.mode === "bot" ? `♟️ vs Aira Bot (Lvl ${state.bot_level})` : "♟️ Aira Chess";
}

function fmtClock(sec) {
  if (sec === null || sec === undefined) return "∞";
  sec = Math.max(0, sec);
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function updateClocksDisplay() {
  if (!state) return;
  const topIsWhite = myColor === "black";
  const topClock = topIsWhite ? state.white_clock : state.black_clock;
  const bottomClock = topIsWhite ? state.black_clock : state.white_clock;
  const topEl = document.getElementById("top-clock");
  const bottomEl = document.getElementById("bottom-clock");
  topEl.textContent = fmtClock(topClock);
  bottomEl.textContent = fmtClock(bottomClock);
  const whiteToMove = state.turn === "white";
  topEl.classList.toggle("active", state.status === "active" && (topIsWhite ? whiteToMove : !whiteToMove));
  bottomEl.classList.toggle("active", state.status === "active" && (topIsWhite ? !whiteToMove : whiteToMove));
  topEl.classList.toggle("low", topClock !== null && topClock !== undefined && topClock < 20);
  bottomEl.classList.toggle("low", bottomClock !== null && bottomClock !== undefined && bottomClock < 20);
}

function updateStatusLine() {
  if (state.status === "waiting") {
    statusEl.textContent = "Waiting for opponent to join…";
    return;
  }
  if (state.status === "finished") {
    let text;
    if (state.result === "draw") text = `Draw — ${state.result_reason}`;
    else {
      const winnerName = state.result === "white" ? state.white_name : state.black_name;
      text = `${winnerName} wins — ${state.result_reason}`;
    }
    statusEl.textContent = text;
    showGameOverModal(text);
    return;
  }
  if (state.draw_offered_by && state.draw_offered_by !== MY_UID) {
    showDrawOfferModal();
  }
  statusEl.textContent = state.in_check ? "Check!" : (state.turn === myColor ? "Your move" : "Opponent's move");
}

// ── Interaction ─────────────────────────────────────────────────────────
function pieceOwner(ch) {
  if (!ch) return null;
  return ch === ch.toUpperCase() ? "white" : "black";
}

async function onSquareClick(sq) {
  if (!state || state.status !== "active") return;
  if (myColor !== state.turn) return; // not your turn / spectating

  const grid = fenToBoard(state.fen);
  if (selected && legalTargets.includes(sq)) {
    const fromPiece = grid[selected];
    const isPromotion = fromPiece && fromPiece.toUpperCase() === "P" &&
      ((fromPiece === "P" && sq[1] === "8") || (fromPiece === "p" && sq[1] === "1"));
    if (isPromotion) {
      askPromotion((promo) => makeMove(selected, sq, promo));
    } else {
      makeMove(selected, sq, null);
    }
    selected = null; legalTargets = [];
    render();
    return;
  }

  const owner = pieceOwner(grid[sq]);
  if (owner === myColor) {
    selected = sq;
    legalTargets = await fetchLegalTargets(sq);
  } else {
    selected = null; legalTargets = [];
  }
  render();
}

// Lightweight client-side legal-destination lookup: ask the server's move
// endpoint is the source of truth, but we don't want a round trip per
// highlight, so we recompute legality locally using the same square-by-
// square scan the server would reject anyway -- simplest robust approach
// here is just to try every target square 'a1'..'h8' against /api can be
// slow, so instead we derive pseudo-legal targets from the FEN client-side
// is non-trivial without a JS chess lib. Easiest reliable option: fetch the
// authoritative legal-move list once per state from a tiny server helper.
async function fetchLegalTargets(fromSquare) {
  if (!state.legal_moves) return [];
  return state.legal_moves
    .filter(uci => uci.startsWith(fromSquare))
    .map(uci => uci.substring(2, 4));
}

function askPromotion(callback) {
  const modal = document.getElementById("promo-modal");
  const opts = document.getElementById("promo-options");
  opts.innerHTML = "";
  const pieces = myColor === "white" ? ["Q", "R", "B", "N"] : ["q", "r", "b", "n"];
  const labels = { Q: "♕", R: "♖", B: "♗", N: "♘", q: "♛", r: "♜", b: "♝", n: "♞" };
  pieces.forEach(p => {
    const span = document.createElement("span");
    span.className = "piece";
    span.textContent = labels[p];
    span.onclick = () => { modal.classList.add("hidden"); callback(p.toLowerCase()); };
    opts.appendChild(span);
  });
  modal.classList.remove("hidden");
}

async function makeMove(from, to, promotion) {
  try {
    const res = await fetch(`/api/game/${GAME_ID}/move`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: MY_UID, uci: from + to, promotion }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      statusEl.textContent = err.detail || "Move rejected";
      return;
    }
    state = await res.json();
    if (tg) tg.HapticFeedback?.impactOccurred("light");
    lastMove = [from, to];
    render();
  } catch (e) {
    statusEl.textContent = "Connection error — retrying via refresh";
    refreshState();
  }
}

// ── Draw / resign ───────────────────────────────────────────────────────
document.getElementById("btn-resign").onclick = async () => {
  if (!confirm("Resign this game?")) return;
  const res = await fetch(`/api/game/${GAME_ID}/resign`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid: MY_UID }),
  });
  state = await res.json();
  render();
};

document.getElementById("btn-draw").onclick = async () => {
  await fetch(`/api/game/${GAME_ID}/draw/offer`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid: MY_UID }),
  });
  statusEl.textContent = "Draw offer sent";
};

function showDrawOfferModal() {
  const modal = document.getElementById("info-modal");
  document.getElementById("info-title").textContent = "Draw offered";
  document.getElementById("info-body").textContent = "Your opponent is offering a draw.";
  const actions = document.getElementById("info-actions");
  actions.innerHTML = "";
  const accept = document.createElement("button");
  accept.className = "action accent"; accept.textContent = "Accept";
  accept.onclick = () => respondDraw(true);
  const decline = document.createElement("button");
  decline.className = "action"; decline.textContent = "Decline";
  decline.onclick = () => respondDraw(false);
  actions.append(accept, decline);
  modal.classList.remove("hidden");
}

async function respondDraw(accept) {
  document.getElementById("info-modal").classList.add("hidden");
  const res = await fetch(`/api/game/${GAME_ID}/draw/respond?accept=${accept}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid: MY_UID }),
  });
  state = await res.json();
  render();
}

function showGameOverModal(text) {
  const modal = document.getElementById("info-modal");
  document.getElementById("info-title").textContent = "Game over";
  document.getElementById("info-body").textContent = text;
  document.getElementById("info-actions").innerHTML = "";
  modal.classList.remove("hidden");
}

// ── Networking: WS push + polling fallback + local clock tick ────────────
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/${GAME_ID}`);
  ws.onopen = () => document.getElementById("conn-dot").style.color = "#4caf6d";
  ws.onclose = () => { document.getElementById("conn-dot").style.color = "#888"; setTimeout(connectWS, 2000); };
  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "state") { state = msg.state; lastMove = state.moves.length
        ? [state.moves[state.moves.length - 1].slice(0, 2), state.moves[state.moves.length - 1].slice(2, 4)]
        : null; render(); }
    if (msg.type === "draw_offered" && msg.uid !== MY_UID) { state.draw_offered_by = msg.uid; render(); }
  };
}

async function refreshState() {
  const res = await fetch(`/api/game/${GAME_ID}/state`);
  if (!res.ok) return;
  state = await res.json();
  render();
}

async function init() {
  const res = await fetch(`/api/game/${GAME_ID}/state`);
  if (!res.ok) { statusEl.textContent = "Game not found"; return; }
  state = await res.json();
  myColor = state.white_uid === MY_UID ? "white" : (state.black_uid === MY_UID ? "black" : null);
  render();
  connectWS();
  setInterval(refreshState, 5000);          // safety-net poll in case WS drops silently
  clockTimer = setInterval(updateClocksDisplay, 250);
}

init();
