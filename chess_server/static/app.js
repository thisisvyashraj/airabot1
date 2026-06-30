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
      
      const piece = grid[sq];
      if (piece) {
        // CORRECTED RENDER LOGIC
        const pieceDiv = document.createElement("div");
        const color = piece === piece.toUpperCase() ? "w" : "b";
        const type = piece.toLowerCase();
        // This class MUST match exactly what is in your style.css
        pieceDiv.className = `piece ${color}-${type}`;
        div.appendChild(pieceDiv);
      }
      
      div.addEventListener("click", () => onSquareClick(sq));
      boardEl.appendChild(div);
    }
  }
}
