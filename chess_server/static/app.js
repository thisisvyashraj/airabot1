// ── Setup ────────────────────────────────────────────────────────────────
const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) { tg.ready(); tg.expand(); }

const params = new URLSearchParams(location.search);
const GAME_ID = params.get("game");

// ── Identity ────────────────────────────────────────────────────────────
// IMPORTANT: in a private chat the bot can bake the correct uid into the
// button URL because it knows who it's messaging. In a GROUP or CHANNEL the
// same button/URL is shown to every member, so a URL-only uid would be
// identical for everyone who taps it (usually the game creator's id) —
// that's what made multiplayer break outside DMs. Telegram signs the real
// tapping user into initDataUnsafe.user regardless of chat type, so that
// must take priority whenever it's present.
function resolveIdentity() {
  const tgUser = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
  const uid = tgUser && tgUser.id != null ? tgUser.id : parseInt(params.get("uid"), 10);
  const name = (tgUser && (tgUser.first_name || tgUser.username)) || params.get("name") || "You";
  return { uid, name };
}
const { uid: MY_UID, name: MY_NAME } = resolveIdentity();

let state = null;          
let selected = null;       
let legalTargets = [];     
let myColor = null;        
let lastMove = null;       
let ws = null;
let clockTimer = null;
let moveInFlight = false; // guards against the 1s poll clobbering an optimistic move

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status-line");

// ── FEN parsing ─────────────────────────────────────────────────────────
function fenToBoard(fen) {
  const rows = fen.split(" ")[0].split("/");
  const grid = {}; 
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

// Recompute which color WE are from the latest state. This must be re-run
// every time fresh state arrives (poll, WS push, initial load) — not just
// once at startup — because a game can start "waiting" with only white_uid
// set and pick up black_uid later once someone else joins. Computing this
// only in init() left the first player stuck as a permanent spectator.
function deriveMyColor() {
  if (!state) return null;
  if (state.white_uid === MY_UID) return "white";
  if (state.black_uid === MY_UID) return "black";
  return null;
}

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

      // Highlights
      if (selected === sq) div.classList.add("selected");
      if (legalTargets.includes(sq)) {
        div.classList.add("target");
        if (grid[sq]) div.classList.add("has-piece");
      }
      if (lastMove && lastMove.includes(sq)) div.classList.add("last-move");
      
      const piece = grid[sq];
      const kingInCheck = state.in_check && piece &&
        piece === (state.turn === "white" ? "K" : "k");
      if (kingInCheck) div.classList.add("in-check");
      if (piece) {
        const pieceDiv = document.createElement("div");
        const color = piece === piece.toUpperCase() ? "w" : "b";
        const type = piece.toLowerCase();
        pieceDiv.className = `piece ${color}-${type}`;
        
        // DRAG AND DROP LOGIC
        if (color === myColor && state.turn === myColor) {
            pieceDiv.draggable = true;
            pieceDiv.ondragstart = async (e) => {
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("from", sq);
                // Compute legal targets directly instead of routing through
                // onSquareClick — that function is written for taps and, if
                // called here, can act on whatever selected/legalTargets was
                // left over from a previous interaction and fire a move by
                // accident.
                selected = sq;
                legalTargets = await fetchLegalTargets(sq);
                render();
            };
        }
        div.appendChild(pieceDiv);
      }

      // DROP LOGIC
      div.ondragover = (e) => e.preventDefault();
      div.ondrop = (e) => {
          e.preventDefault();
          const from = e.dataTransfer.getData("from");
          if (!from || !legalTargets.includes(sq)) return;
          const fromPiece = grid[from];
          const isPromotion = fromPiece && fromPiece.toUpperCase() === "P" &&
            ((fromPiece === "P" && sq[1] === "8") || (fromPiece === "p" && sq[1] === "1"));
          selected = null; legalTargets = [];
          if (isPromotion) {
              askPromotion((promo) => makeMove(from, sq, promo));
          } else {
              makeMove(from, sq, null);
          }
      };

      // Keep click logic for mobile users
      div.addEventListener("click", () => onSquareClick(sq));
      boardEl.appendChild(div);
    }
  }
  updateSideLabels();
  updateStatusLine();
}

function updateSideLabels() {
  const topIsWhite = myColor === "black"; 
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
  if (myColor !== state.turn) return; 

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
  const pieces = ["Q", "R", "B", "N"];
  pieces.forEach(p => {
    const pieceDiv = document.createElement("div");
    const color = myColor === "white" ? "w" : "b";
    pieceDiv.className = `piece ${color}-${p.toLowerCase()}`;
    pieceDiv.onclick = () => { modal.classList.add("hidden"); callback(p.toLowerCase()); };
    opts.appendChild(pieceDiv);
  });
  modal.classList.remove("hidden");
}

async function makeMove(from, to, promotion) {
  // 1. Save the previous state in case the server rejects the move
  const previousFen = state.fen;
  const previousMoves = [...state.moves];
  moveInFlight = true;

  // 2. OPTIMISTIC UPDATE: Update UI immediately
  // This makes the board feel instant
  const grid = fenToBoard(state.fen);
  grid[to] = grid[from];
  delete grid[from];
  
  // Update state locally so render() draws the new position immediately
  // We need to manually sync the FEN briefly to show the move happened
  state.fen = toFen(grid, state.turn === "white" ? "b" : "w"); 
  lastMove = [from, to];
  render();

  // 3. Send to Server
  try {
    const res = await fetch(`/api/game/${GAME_ID}/move`, {
      method: "POST", 
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: MY_UID, uci: from + to, promotion }),
    });

    if (!res.ok) {
      // If server rejects (e.g. illegal move), revert the board
      state.fen = previousFen;
      state.moves = previousMoves;
      const err = await res.json().catch(() => ({}));
      statusEl.textContent = err.detail || "Move rejected";
      render();
      return;
    }

    // Server confirmed: Update with the *official* state from server
    state = await res.json();
    myColor = deriveMyColor();
    if (tg) tg.HapticFeedback?.impactOccurred("light");
    render();
    
  } catch (e) {
    // Connection failed: Revert and show error
    state.fen = previousFen;
    statusEl.textContent = "Connection error — retrying...";
    render();
    refreshState();
  } finally {
    moveInFlight = false;
  }
}

// Add this helper to turn the grid back into a FEN string for the optimistic update
function toFen(grid, nextTurn) {
    let fen = "";
    for (let r = 8; r >= 1; r--) {
        let empty = 0;
        for (let f = 0; f < 8; f++) {
            let p = grid["abcdefgh"[f] + r];
            if (p) {
                if (empty > 0) { fen += empty; empty = 0; }
                fen += p;
            } else { empty++; }
        }
        if (empty > 0) fen += empty;
        if (r > 1) fen += "/";
    }
    return `${fen} ${nextTurn} - - 0 1`;
}
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

// ── Draw offer / Resign ────────────────────────────────────────────────
// NOTE: the buttons in the HTML (#btn-draw / #btn-resign) had no listeners
// at all before this fix, so they were completely inert. Wiring assumes
// REST endpoints mirroring the existing draw/respond one; adjust the paths
// below if your backend uses different routes.
async function offerDraw() {
  if (!state || state.status !== "active") return;
  try {
    const res = await fetch(`/api/game/${GAME_ID}/draw/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: MY_UID }),
    });
    if (res.ok) {
      state = await res.json();
      myColor = deriveMyColor();
      render();
    } else {
      const err = await res.json().catch(() => ({}));
      statusEl.textContent = err.detail || "Couldn't offer draw";
    }
  } catch (e) {
    statusEl.textContent = "Connection error — try again";
  }
}

function confirmResign() {
  if (!state || state.status !== "active") return;
  const modal = document.getElementById("info-modal");
  document.getElementById("info-title").textContent = "Resign?";
  document.getElementById("info-body").textContent = "Are you sure you want to resign this game?";
  const actions = document.getElementById("info-actions");
  actions.innerHTML = "";
  const cancel = document.createElement("button");
  cancel.className = "action"; cancel.textContent = "Cancel";
  cancel.onclick = () => modal.classList.add("hidden");
  const confirmBtn = document.createElement("button");
  confirmBtn.className = "action danger"; confirmBtn.textContent = "Resign";
  confirmBtn.onclick = () => { modal.classList.add("hidden"); resignGame(); };
  actions.append(cancel, confirmBtn);
  modal.classList.remove("hidden");
}

async function resignGame() {
  try {
    const res = await fetch(`/api/game/${GAME_ID}/resign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: MY_UID }),
    });
    if (res.ok) {
      state = await res.json();
      myColor = deriveMyColor();
      render();
    } else {
      const err = await res.json().catch(() => ({}));
      statusEl.textContent = err.detail || "Couldn't resign";
    }
  } catch (e) {
    statusEl.textContent = "Connection error — try again";
  }
}

document.getElementById("btn-draw").addEventListener("click", offerDraw);
document.getElementById("btn-resign").addEventListener("click", confirmResign);

// ── Networking: WS push + polling fallback + local clock tick ────────────
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/${GAME_ID}`);
  ws.onopen = () => document.getElementById("conn-dot").style.color = "#4caf6d";
  ws.onclose = () => { document.getElementById("conn-dot").style.color = "#888"; setTimeout(connectWS, 2000); };
  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "state") { 
      state = msg.state; 
      myColor = deriveMyColor();
      lastMove = state.moves.length
        ? [state.moves[state.moves.length - 1].slice(0, 2), state.moves[state.moves.length - 1].slice(2, 4)]
        : null; 
      render(); 
    }
    if (msg.type === "draw_offered" && msg.uid !== MY_UID) { state.draw_offered_by = msg.uid; render(); }
  };
}

async function refreshState() {
  const res = await fetch(`/api/game/${GAME_ID}/state`);
  if (!res.ok) return;
  state = await res.json();
  myColor = deriveMyColor();
  render();
}

async function init() {
  const res = await fetch(`/api/game/${GAME_ID}/state`);
  if (!res.ok) { statusEl.textContent = "Game not found"; return; }
  state = await res.json();
  myColor = deriveMyColor();
  render();
  connectWS();
 // Sync clock with server every 1 second
setInterval(async () => {
    if (state && state.status === "active" && !moveInFlight) {
        const res = await fetch(`/api/game/${GAME_ID}/state`);
        if (res.ok) {
            state = await res.json();
            myColor = deriveMyColor();
            updateClocksDisplay();
        }
    }
}, 1000);
}

init();
