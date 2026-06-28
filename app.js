(function () {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { try { tg.expand(); tg.ready(); } catch (e) {} }

  const params = new URLSearchParams(location.search);
  const uid = parseInt(params.get("uid") || "0", 10);
  const myName = params.get("name") || "You";
  let gameId = params.get("game") || null;
  const mode = params.get("mode"); // "queue" or null
  const queueColor = params.get("color") || "random";
  const queueTime = parseInt(params.get("time") || "0", 10);

  const PIECE_GLYPH = {
    p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚",
    P: "♙", N: "♘", B: "♗", R: "♖", Q: "♕", K: "♔",
  };
  const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];

  const boardEl       = document.getElementById("board");
  const topName        = document.getElementById("topName");
  const topRating       = document.getElementById("topRating");
  const topClock         = document.getElementById("topClock");
  const bottomName        = document.getElementById("bottomName");
  const bottomRating       = document.getElementById("bottomRating");
  const bottomClock         = document.getElementById("bottomClock");
  const checkBanner          = document.getElementById("checkBanner");
  const movesList              = document.getElementById("movesList");
  const roomInfo                = document.getElementById("roomInfo");
  const queueOverlay             = document.getElementById("queueOverlay");
  const promoOverlay               = document.getElementById("promoOverlay");
  const promoChoices                 = document.getElementById("promoChoices");
  const resultOverlay                  = document.getElementById("resultOverlay");
  const resultTitle                     = document.getElementById("resultTitle");
  const resultReason                     = document.getElementById("resultReason");
  const resultRating                      = document.getElementById("resultRating");
  const drawToast                          = document.getElementById("drawToast");
  const errorOverlay                        = document.getElementById("errorOverlay");
  const errorMsg                             = document.getElementById("errorMsg");

  let ws = null;
  let chessLocal = new Chess();
  let myColor = null;       // 'white' | 'black'
  let selectedSquare = null;
  let lastState = null;
  let resultShown = false;

  function buildBoardSquares() {
    boardEl.innerHTML = "";
    for (let rank = 8; rank >= 1; rank--) {
      for (let f = 0; f < 8; f++) {
        const square = `${FILES[f]}${rank}`;
        const div = document.createElement("div");
        div.className = "square " + (((f + rank) % 2 === 0) ? "dark" : "light");
        div.dataset.square = square;
        div.addEventListener("click", () => onSquareClick(square));
        boardEl.appendChild(div);
      }
    }
    boardEl.classList.toggle("flipped", myColor === "black");
  }

  function clearSelection() {
    selectedSquare = null;
    document.querySelectorAll(".square").forEach((el) =>
      el.classList.remove("selected", "legal-dot", "legal-capture")
    );
  }

  function renderPosition(fen) {
    chessLocal.load(fen);
    const board = chessLocal.board(); // row0 = rank8, each cell {type,color} or null
    document.querySelectorAll(".square").forEach((sqEl) => { sqEl.innerHTML = ""; });
    for (let r = 0; r < 8; r++) {
      for (let f = 0; f < 8; f++) {
        const cell = board[r][f];
        if (!cell) continue;
        const square = `${FILES[f]}${8 - r}`;
        const sqEl = boardEl.querySelector(`[data-square="${square}"]`);
        if (!sqEl) continue;
        const glyph = cell.color === "w" ? PIECE_GLYPH[cell.type.toUpperCase()] : PIECE_GLYPH[cell.type];
        const span = document.createElement("span");
        span.className = "piece " + (cell.color === "w" ? "white-piece" : "black-piece");
        span.textContent = glyph;
        sqEl.appendChild(span);
      }
    }
  }

  function squareIsMine(square) {
    const piece = chessLocal.get(square);
    if (!piece) return false;
    return (piece.color === "w" && myColor === "white") || (piece.color === "b" && myColor === "black");
  }

  function showLegalMoves(square) {
    const moves = chessLocal.moves({ square, verbose: true });
    moves.forEach((m) => {
      const el = boardEl.querySelector(`[data-square="${m.to}"]`);
      if (el) el.classList.add(m.captured ? "legal-capture" : "legal-dot");
    });
  }

  function myTurnAndMine() {
    if (!lastState || lastState.status !== "active") return false;
    if (myColor !== lastState.turn) return false;
    const mySide = lastState.turn === "white" ? lastState.white : lastState.black;
    return !!(mySide && mySide.type === "human" && mySide.uid === uid);
  }

  function onSquareClick(square) {
    if (!myTurnAndMine()) return;

    if (selectedSquare) {
      if (square === selectedSquare) { clearSelection(); return; }
      const moves = chessLocal.moves({ square: selectedSquare, verbose: true });
      const target = moves.find((m) => m.to === square);
      if (target) {
        const from = selectedSquare;
        clearSelection();
        attemptMove(from, square, target);
        return;
      }
      clearSelection();
      if (squareIsMine(square)) {
        selectedSquare = square;
        boardEl.querySelector(`[data-square="${square}"]`).classList.add("selected");
        showLegalMoves(square);
      }
    } else if (squareIsMine(square)) {
      selectedSquare = square;
      boardEl.querySelector(`[data-square="${square}"]`).classList.add("selected");
      showLegalMoves(square);
    }
  }

  function attemptMove(from, to, moveInfo) {
    if (moveInfo.flags && moveInfo.flags.indexOf("p") !== -1) {
      showPromotionPicker(from, to);
      return;
    }
    sendMove(from + to);
  }

  function showPromotionPicker(from, to) {
    promoChoices.innerHTML = "";
    ["q", "r", "b", "n"].forEach((p) => {
      const btn = document.createElement("button");
      btn.className = "promo-btn";
      btn.textContent = PIECE_GLYPH[myColor === "white" ? p.toUpperCase() : p];
      btn.onclick = () => {
        promoOverlay.classList.add("hidden");
        sendMove(from + to + p);
      };
      promoChoices.appendChild(btn);
    });
    promoOverlay.classList.remove("hidden");
  }

  function sendMove(uci) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "move", uci, uid }));
      if (tg && tg.HapticFeedback) { try { tg.HapticFeedback.impactOccurred("light"); } catch (e) {} }
    }
  }

  function fmtClock(seconds, timeControl) {
    if (timeControl === 0 || seconds == null) return "∞";
    seconds = Math.max(0, Math.floor(seconds));
    const m = Math.floor(seconds / 60), s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function applyState(state) {
    lastState = state;
    if (!myColor) {
      if (state.white && state.white.uid === uid) myColor = "white";
      else if (state.black && state.black.uid === uid) myColor = "black";
      else myColor = "white";
      buildBoardSquares();
    }
    renderPosition(state.fen);
    clearSelection();

    const top = myColor === "white" ? state.black : state.white;
    const bottom = myColor === "white" ? state.white : state.black;
    topName.textContent = top ? (top.name || "Opponent") : "Waiting for opponent…";
    bottomName.textContent = bottom ? (bottom.name || myName) : myName;
    topRating.textContent = top && top.type === "bot" ? `Bot · Lv${top.level}` : "";
    bottomRating.textContent = "";

    const topColor = myColor === "white" ? "black" : "white";
    const bottomColor = myColor;
    const clocks = state.clocks || {};
    topClock.textContent = fmtClock(clocks[topColor], state.time_control);
    bottomClock.textContent = fmtClock(clocks[bottomColor], state.time_control);
    topClock.classList.toggle("active-clock", state.turn === topColor && state.status === "active");
    bottomClock.classList.toggle("active-clock", state.turn === bottomColor && state.status === "active");

    checkBanner.classList.toggle("hidden", !(state.in_check && state.status === "active"));

    movesList.innerHTML = "";
    const moves = state.moves || [];
    for (let i = 0; i < moves.length; i += 2) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="mv-num">${i / 2 + 1}.</span><span>${moves[i] || ""}</span><span>${moves[i + 1] || ""}</span>`;
      movesList.appendChild(li);
    }
    movesList.scrollTop = movesList.scrollHeight;

    drawToast.classList.toggle("hidden", !(state.draw_offered_by && state.draw_offered_by !== uid));

    roomInfo.textContent = state.status === "waiting" ? "Waiting for opponent to join…" : "";

    if (state.status === "finished" && !resultShown) {
      resultShown = true;
      showResult(state);
    }
  }

  async function showResult(state) {
    const iAmWhite = myColor === "white";
    let title;
    if (state.result === "1/2-1/2") title = "It's a draw";
    else if ((state.result === "1-0" && iAmWhite) || (state.result === "0-1" && !iAmWhite)) title = "You won! 🎉";
    else title = "You lost";
    resultTitle.textContent = title;
    resultReason.textContent = state.reason ? `By ${state.reason}` : "";
    resultRating.classList.add("hidden");
    try {
      const res = await fetch(`/api/rating/${uid}`);
      if (res.ok) {
        const r = await res.json();
        resultRating.textContent = `New rating: ${r.rating}`;
        resultRating.classList.remove("hidden");
      }
    } catch (e) {}
    resultOverlay.classList.remove("hidden");
  }

  function connectWs(id) {
    gameId = id;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/${gameId}`);
    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.type === "state") applyState(msg);
      else if (msg.type === "error") console.warn("[chess]", msg.message);
    };
    ws.onerror = () => {
      errorMsg.textContent = "Lost connection to the chess server.";
      errorOverlay.classList.remove("hidden");
    };
    ws.onclose = () => {
      setTimeout(() => { if (gameId && document.visibilityState !== "hidden") connectWs(gameId); }, 2000);
    };
  }

  async function startQueueFlow() {
    queueOverlay.classList.remove("hidden");
    try {
      await fetch("/api/queue/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid, name: myName, color: queueColor, time_control: queueTime }),
      });
    } catch (e) {
      errorMsg.textContent = "Couldn't reach the chess service.";
      errorOverlay.classList.remove("hidden");
      return;
    }
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`/api/queue/status/${uid}`);
        const data = await res.json();
        if (data.matched) {
          clearInterval(poll);
          queueOverlay.classList.add("hidden");
          connectWs(data.game_id);
        }
      } catch (e) {}
    }, 1800);
    document.getElementById("cancelQueueBtn").onclick = async () => {
      clearInterval(poll);
      try { await fetch(`/api/queue/cancel?uid=${uid}`, { method: "POST" }); } catch (e) {}
      if (tg) tg.close(); else queueOverlay.classList.add("hidden");
    };
  }

  document.getElementById("movesBtn").onclick = () => document.getElementById("movesDrawer").classList.toggle("hidden");
  document.getElementById("closeMovesBtn").onclick = () => document.getElementById("movesDrawer").classList.add("hidden");
  document.getElementById("resignBtn").onclick = () => {
    if (confirm("Resign this game?") && ws) ws.send(JSON.stringify({ type: "resign", uid }));
  };
  document.getElementById("drawBtn").onclick = () => { if (ws) ws.send(JSON.stringify({ type: "draw_offer", uid })); };
  document.getElementById("acceptDrawBtn").onclick = () => { if (ws) ws.send(JSON.stringify({ type: "draw_accept", uid })); };
  document.getElementById("declineDrawBtn").onclick = () => { if (ws) ws.send(JSON.stringify({ type: "draw_decline", uid })); };
  document.getElementById("closeResultBtn").onclick = () => {
    resultOverlay.classList.add("hidden");
    if (tg) tg.close();
  };

  // Smooth per-second countdown between server state pushes (server is the
  // source of truth and corrects this on every move/poll).
  setInterval(() => {
    if (!lastState || lastState.status !== "active" || lastState.time_control === 0) return;
    const topColor = myColor === "white" ? "black" : "white";
    const bottomColor = myColor;
    if (!lastState.clocks) return;
    if (lastState.turn === topColor) {
      lastState.clocks[topColor] = Math.max(0, lastState.clocks[topColor] - 1);
      topClock.textContent = fmtClock(lastState.clocks[topColor], lastState.time_control);
    } else if (lastState.turn === bottomColor) {
      lastState.clocks[bottomColor] = Math.max(0, lastState.clocks[bottomColor] - 1);
      bottomClock.textContent = fmtClock(lastState.clocks[bottomColor], lastState.time_control);
    }
  }, 1000);

  // boot
  if (mode === "queue") {
    startQueueFlow();
  } else if (gameId) {
    connectWs(gameId);
  } else {
    errorMsg.textContent = "No game was specified in the link.";
    errorOverlay.classList.remove("hidden");
  }
})();
