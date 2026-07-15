const els = {
  lobby: document.getElementById("lobby"),
  privacy: document.getElementById("privacy"),
  table: document.getElementById("table"),
  meta: document.getElementById("meta"),
  banner: document.getElementById("banner"),
  market: document.getElementById("market"),
  hand: document.getElementById("hand"),
  handTitle: document.getElementById("hand-title"),
  offerZone: document.getElementById("offer-zone"),
  offer: document.getElementById("offer"),
  players: document.getElementById("players"),
  scoreboard: document.getElementById("scoreboard"),
  privacyTitle: document.getElementById("privacy-title"),
  privacyBody: document.getElementById("privacy-body"),
  privacyBtn: document.getElementById("privacy-btn"),
  startForm: document.getElementById("start-form"),
  newGameBtn: document.getElementById("new-game-btn"),
  lobbyNote: document.getElementById("lobby-note"),
  zoom: document.getElementById("zoom"),
  zoomImg: document.getElementById("zoom-img"),
  zoomCaption: document.getElementById("zoom-caption"),
};

let state = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

function show(el) {
  el.classList.remove("hidden");
}
function hide(el) {
  el.classList.add("hidden");
}

function cardButton(card, { selectable = false, sanctuary = false, onChoose = null } = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `card${sanctuary ? " sanctuary" : ""}${selectable ? " selectable" : ""}`;

  const art = document.createElement("span");
  art.className = "card-art";
  const img = document.createElement("img");
  img.src = card.image;
  img.alt = card.summary || card.id;
  img.loading = "lazy";
  art.appendChild(img);
  btn.appendChild(art);

  if (selectable) {
    const choose = document.createElement("span");
    choose.className = "card-choose";
    choose.textContent = "Choose";
    btn.appendChild(choose);
  }

  const cap = document.createElement("p");
  cap.className = "card-caption";
  cap.textContent = card.summary || card.id;
  btn.appendChild(cap);

  btn.addEventListener("click", async (ev) => {
    if (selectable && onChoose) {
      ev.stopPropagation();
      await onChoose(card);
      return;
    }
    openZoom(card);
  });
  return btn;
}

function miniCard(card, sanctuary = false) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `mini${sanctuary ? " sanctuary" : ""}`;
  const img = document.createElement("img");
  img.src = card.image;
  img.alt = card.summary || card.id;
  btn.appendChild(img);
  btn.addEventListener("click", () => openZoom(card));
  return btn;
}

function openZoom(card) {
  els.zoomImg.src = card.image;
  els.zoomCaption.textContent = card.summary || "";
  els.zoom.showModal();
}

function render(data) {
  state = data;
  // Only /api/state returns active:false when idle; action endpoints now set active:true.
  if (data.active === false) {
    show(els.lobby);
    hide(els.privacy);
    hide(els.table);
    els.meta.textContent = "";
    els.lobbyNote.textContent = "No game in progress.";
    return;
  }
  if (!data.phase) {
    show(els.lobby);
    hide(els.privacy);
    hide(els.table);
    return;
  }

  els.meta.textContent = `Round ${data.round}/8 · Seed ${data.seed}`;

  if (data.phase === "privacy") {
    hide(els.lobby);
    hide(els.table);
    show(els.privacy);
    const active = data.players.find((p) => p.id === data.active_player_id);
    els.privacyTitle.textContent = `For ${active?.name || "next player"}`;
    els.privacyBody.textContent = data.message;
    return;
  }

  hide(els.lobby);
  hide(els.privacy);
  show(els.table);
  els.banner.textContent = data.message;

  // Market
  els.market.replaceChildren();
  const canPick = data.phase === "pick_region";
  for (const card of data.market) {
    els.market.appendChild(
      cardButton(card, {
        selectable: canPick,
        onChoose: async (c) => {
          await api("/api/pick-market", {
            method: "POST",
            body: JSON.stringify({ region: c.number }),
          }).then(render);
        },
      })
    );
  }

  // Active player hand / offers
  const active = data.players.find((p) => p.id === data.active_player_id);
  els.hand.replaceChildren();
  els.offer.replaceChildren();
  hide(els.offerZone);

  if (data.phase === "choose_region" && active) {
    els.handTitle.textContent = `${active.name}'s hand`;
    for (const card of active.hand) {
      els.hand.appendChild(
        cardButton(card, {
          selectable: true,
          onChoose: async (c) => {
            await api("/api/choose-region", {
              method: "POST",
              body: JSON.stringify({ region: c.number }),
            }).then(render);
          },
        })
      );
    }
  } else if (data.phase === "choose_sanctuary" && active) {
    els.handTitle.textContent = `${active.name}'s hand`;
    for (const card of active.hand) {
      els.hand.appendChild(cardButton(card));
    }
    show(els.offerZone);
    for (const card of active.pending_sanctuaries) {
      els.offer.appendChild(
        cardButton(card, {
          selectable: true,
          sanctuary: true,
          onChoose: async (c) => {
            await api("/api/choose-sanctuary", {
              method: "POST",
              body: JSON.stringify({ tile: c.tile }),
            }).then(render);
          },
        })
      );
    }
  } else if (data.phase === "pick_region" && active) {
    els.handTitle.textContent = `${active.name}'s hand (${active.hand.length || active.hand_count} cards)`;
    for (const card of active.hand) {
      els.hand.appendChild(cardButton(card));
    }
    if (active.pending_sanctuaries?.length) {
      show(els.offerZone);
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent = "After picking, you'll keep one of these Sanctuaries:";
      els.offer.appendChild(note);
      for (const card of active.pending_sanctuaries) {
        els.offer.appendChild(cardButton(card, { sanctuary: true }));
      }
    }
  } else {
    els.handTitle.textContent = "Hand hidden";
  }

  // Players tableaux
  els.players.replaceChildren();
  for (const player of data.players) {
    const card = document.createElement("article");
    card.className = `player-card${player.id === data.active_player_id ? " active" : ""}`;
    const title = document.createElement("h3");
    title.innerHTML = `<span>${player.name}</span><span class="muted">${player.tableau.length}/8 · ${player.sanctuaries.length} sanct.</span>`;
    card.appendChild(title);

    const pathLabel = document.createElement("p");
    pathLabel.className = "muted";
    pathLabel.textContent = "Path (left → right)";
    card.appendChild(pathLabel);
    const tableau = document.createElement("div");
    tableau.className = "tableau";
    for (const region of player.tableau) {
      tableau.appendChild(miniCard(region));
    }
    card.appendChild(tableau);

    const sanctLabel = document.createElement("p");
    sanctLabel.className = "muted";
    sanctLabel.textContent = "Sanctuaries";
    card.appendChild(sanctLabel);
    const sancts = document.createElement("div");
    sancts.className = "sancts";
    for (const s of player.sanctuaries) {
      sancts.appendChild(miniCard(s, true));
    }
    if (!player.sanctuaries.length) {
      sancts.textContent = "—";
    }
    card.appendChild(sancts);
    els.players.appendChild(card);
  }

  // Scores
  if (data.phase === "game_over" && data.scores) {
    show(els.scoreboard);
    const rows = data.players
      .map((p) => {
        const s = data.scores[p.id];
        const win = data.winner_id === p.id ? " ★" : "";
        return `<tr>
          <td><strong>${p.name}${win}</strong></td>
          <td>${s.region_scores.join(" + ")}</td>
          <td>${s.sanctuary_score}</td>
          <td><strong>${s.total}</strong></td>
          <td>${s.duration_sum}</td>
        </tr>`;
      })
      .join("");
    els.scoreboard.innerHTML = `
      <h3>Final fame</h3>
      <table>
        <thead><tr><th>Player</th><th>Regions (L→R)</th><th>Sanctuaries</th><th>Total</th><th>Duration Σ</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } else {
    hide(els.scoreboard);
  }
}

els.startForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const submitBtn = els.startForm.querySelector('button[type="submit"]');
  if (submitBtn) submitBtn.disabled = true;
  try {
    const fd = new FormData(els.startForm);
    const seedRaw = fd.get("seed");
    const body = {
      player1: fd.get("player1"),
      player2: fd.get("player2"),
      seed: seedRaw === "" || seedRaw == null ? null : Number(seedRaw),
    };
    const data = await api("/api/new", { method: "POST", body: JSON.stringify(body) });
    render(data);
  } catch (err) {
    els.lobbyNote.textContent = String(err.message || err);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
});

els.privacyBtn.addEventListener("click", async () => {
  const data = await api("/api/privacy", { method: "POST", body: "{}" });
  render(data);
});

els.newGameBtn.addEventListener("click", () => {
  show(els.lobby);
  hide(els.privacy);
  hide(els.table);
});

api("/api/state").then(render).catch((err) => {
  els.lobbyNote.textContent = String(err.message || err);
});
