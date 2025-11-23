const CARD_SOURCE = "./cards.json";

const state = {
  cards: [],
  game: null,
  waitingForHuman: false,
  log: [],
};

// --- Prosty RNG dla deterministycznych rozgrywek (opcjonalny seed) ---
function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function toNumber(val, fallback = 0) {
  const num = Number(val);
  return Number.isFinite(num) ? num : fallback;
}

function shuffleInPlace(arr, rng = Math.random) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function cardImagePath(card) {
  const level = toNumber(card.level, 1);
  const stem = (card.id || "").replace(/\.json$/i, "");
  return `../CARDS/${level}/${stem}.svg`;
}

const iconMap = {
  money: "FUNDS",
  support: "SUPPORT",
  _1: "_1",
  _2: "_2",
  _3: "_3",
  buildings: "INFRASTRUKTURA",
  investment: "INWESTYCJE",
  social: "SPOLECZNE",
};

function iconTag(name, alt) {
  if (!name) return "";
  return `<span class="icon-wrap"><img src="img/${name}.png" alt="${alt || name}" onerror="this.parentNode.style.display='none'"></span>`;
}

function indicatorIcon(key) {
  return iconTag(key, key);
}

function statIcon(key, alt) {
  return iconTag(iconMap[key] || key, alt || key);
}

// --- Dane kart ---
class CardLoader {
  constructor(url = CARD_SOURCE) {
    this.url = url;
    this.cards = [];
  }

  async load() {
    const res = await fetch(this.url);
    if (!res.ok) throw new Error("Nie udało się wczytać kart");
    const data = await res.json();
    this.cards = data.map((c, idx) => ({
      ...c,
      uid: `${c.id}-${idx}`,
    }));
    return this.cards;
  }
}

// --- Plansza ---
class Board {
  constructor(buildings = 16, investment = 16, social = 16, maxLevel = 4) {
    this.maxLevel = maxLevel;
    this.fields = [];
    let idx = 0;
    for (let i = 0; i < buildings; i++) {
      this.fields.push({ id: idx++, type: "buildings", occupant: null, occupationLevel: 0 });
    }
    for (let i = 0; i < investment; i++) {
      this.fields.push({ id: idx++, type: "investment", occupant: null, occupationLevel: 0 });
    }
    for (let i = 0; i < social; i++) {
      this.fields.push({ id: idx++, type: "social", occupant: null, occupationLevel: 0 });
    }
  }

  findEmptyField(type) {
    return this.fields.find((f) => f.type === type && !f.occupant);
  }

  findPlayerFields(playerId, type) {
    return this.fields.filter((f) => f.type === type && f.occupant === playerId);
  }

  occupyField(fieldId, playerId) {
    const f = this.fields.find((x) => x.id === fieldId);
    if (!f) return false;
    if (!f.occupant) {
      f.occupant = playerId;
      f.occupationLevel = 1;
      return true;
    }
    if (f.occupant !== playerId) return false;
    if (f.occupationLevel < this.maxLevel) {
      f.occupationLevel += 1;
      return true;
    }
    return false;
  }

  upgradeField(fieldId, playerId) {
    const f = this.fields.find((x) => x.id === fieldId);
    if (!f || f.occupant !== playerId) return false;
    if (f.occupationLevel >= this.maxLevel) return false;
    f.occupationLevel += 1;
    return true;
  }

  placeWithEffect(effectType, playerId, preferUpgrade = false) {
    if (!["buildings", "investment", "social"].includes(effectType)) {
      return { success: false, message: "Nieznany efekt karty" };
    }
    const playerFields = this.findPlayerFields(playerId, effectType);
    if (preferUpgrade && playerFields.length) {
      const target = playerFields.find((f) => f.occupationLevel < this.maxLevel);
      if (target) {
        this.upgradeField(target.id, playerId);
        return { success: true, message: `Ulepszono pole ${target.id}` };
      }
    }
    const empty = this.findEmptyField(effectType);
    if (empty && !preferUpgrade) {
      this.occupyField(empty.id, playerId);
      return { success: true, message: `Zajęto pole ${empty.id}` };
    }
    if (!preferUpgrade && playerFields.length) {
      const target = playerFields.find((f) => f.occupationLevel < this.maxLevel);
      if (target) {
        this.upgradeField(target.id, playerId);
        return { success: true, message: `Ulepszono pole ${target.id}` };
      }
    }
    return { success: false, message: "Brak dostępnych pól" };
  }

  summary() {
    return this.fields.reduce((acc, f) => {
      const ref = acc[f.type] || { total: 0, occupied: 0 };
      ref.total += 1;
      ref.occupied += f.occupant ? 1 : 0;
      acc[f.type] = ref;
      return acc;
    }, {});
  }
}

// --- Gracz ---
class Player {
  constructor(id, isHuman = false) {
    this.id = id;
    this.isHuman = isHuman;
    this.money = 20;
    this.support = 16;
    this._1 = 0;
    this._2 = 0;
    this._3 = 0;
    this.hand = [];
  }
}

// --- Silnik gry ---
class GameEngine {
  constructor(cards, rng = Math.random) {
    this.cards = cards;
    this.rng = rng;
    this.players = [];
    this.decks = {};
    this.board = new Board();
    this.indicators = {};
    this.indicatorEvents = {};
    this.indicatorAmounts = {};
    this.maxIndicator = 6;
    this.currentLevel = 1;
    this.currentPlayerIndex = 0;
    this.round = 1;
    this.roundPasses = 0;
    this.roundCannotExchange = 0;
    this.roundAnyPlayed = false;
    this.gameOver = false;
    this.onLog = () => {};
  }

  emit(msg) {
    this.onLog?.(msg);
  }

  start(numPlayers = 4) {
    this.players = [];
    for (let i = 0; i < numPlayers; i++) {
      this.players.push(new Player(`Gracz ${i + 1}`, i === 0));
    }
    this.board = new Board();
    this.indicators = {};
    for (let base = 1; base <= 3; base++) {
      for (let col = 1; col <= 3; col++) {
        this.indicators[`_${base}_${col}`] = 0;
      }
    }
    this.indicatorEvents = {};
    this.indicatorAmounts = {};
    Object.keys(this.indicators).forEach((key) => {
      this.indicatorEvents[key] = {};
      this.indicatorAmounts[key] = {};
      this.players.forEach((p) => {
        this.indicatorEvents[key][p.id] = 0;
        this.indicatorAmounts[key][p.id] = 0;
      });
    });

    // Osobne talie dla każdego poziomu, grane kolejno 1 -> 6.
    this.decks = {};
    for (let lvl = 1; lvl <= 6; lvl++) {
      const cardsForLevel = this.cards.filter((c) => toNumber(c.level, 1) === lvl);
      this.decks[lvl] = shuffleInPlace([...cardsForLevel], this.rng);
    }

    this.currentLevel = 1;
    while (this.currentLevel <= 6 && (!this.decks[this.currentLevel] || this.decks[this.currentLevel].length === 0)) {
      if (!this.advanceLevel()) break;
    }

    this.currentPlayerIndex = 0;
    this.round = 1;
    this.roundPasses = 0;
    this.roundCannotExchange = 0;
    this.roundAnyPlayed = false;
    this.gameOver = false;

    this.dealInitial();
    this.emit(`Nowa gra: ${numPlayers} graczy. Zaczynamy rundę 1.`);
  }

  dealInitial() {
    this.players.forEach((p) => {
      for (let i = 0; i < 6; i++) {
        const c = this.drawCard();
        if (c) p.hand.push(c);
      }
    });
  }

  drawCard() {
    while (this.currentLevel <= 6) {
      const deck = this.decks[this.currentLevel];
      if (deck && deck.length > 0) {
        return deck.shift();
      }
      if (!this.advanceLevel()) break;
    }
    return null;
  }

  shuffleDeck(level) {
    const deck = this.decks[level];
    if (!deck) return;
    shuffleInPlace(deck, this.rng);
  }

  advanceLevel() {
    for (let lvl = this.currentLevel + 1; lvl <= 6; lvl++) {
      const deck = this.decks[lvl];
      if (deck && deck.length > 0) {
        this.currentLevel = lvl;
        this.emit(`Przechodzimy do ery ${this.currentLevel}.`);
        return true;
      }
    }
    return false;
  }

  getPlayableCards(player) {
    return player.hand.filter((card) => this.canPlay(player, card, "normal"));
  }

  pickCardForAI(player) {
    const hand = player.hand;
    const normal = hand.filter((c) => this.canPlay(player, c, "normal"));
    if (normal.length) return { card: normal[Math.floor(this.rng() * normal.length)], mode: "normal" };
    const borrowable = hand.filter((c) => this.canPlay(player, c, "borrow"));
    if (borrowable.length) return { card: borrowable[Math.floor(this.rng() * borrowable.length)], mode: "borrow" };
    const undecided = hand.filter((c) => this.canPlay(player, c, "undecided"));
    if (undecided.length) return { card: undecided[Math.floor(this.rng() * undecided.length)], mode: "undecided" };
    return null;
  }

  canPlay(player, card, supportMode = "normal") {
    const req = card.requirements || {};
    const price = toNumber(req.price);
    if (player.money < price) return false;
    if (player._1 < toNumber(req._1)) return false;
    if (player._2 < toNumber(req._2)) return false;
    if (player._3 < toNumber(req._3)) return false;
    const supportReq = toNumber(req.support);
    const missing = Math.max(0, supportReq - player.support);
    if (supportMode === "normal") return missing <= 0;
    if (supportMode === "borrow") {
      const borrowable = this.players
        .filter((p) => p.id !== player.id)
        .reduce((sum, p) => sum + p.support, 0);
      return missing <= borrowable;
    }
    if (supportMode === "undecided") return true; // próba przekonania niezdecydowanych
    return false;
  }

  playCard(player, card, supportMode = "normal") {
    const req = card.requirements || {};
    const price = toNumber(req.price);
    if (player.money < price) {
      return { success: false, message: "Brakuje monet na zagranie karty." };
    }
    if (player._1 < toNumber(req._1) || player._2 < toNumber(req._2) || player._3 < toNumber(req._3)) {
      return { success: false, message: "Brak wymaganych parametrów (_1/_2/_3)." };
    }

    const supportReq = toNumber(req.support);
    const baseSupport = player.support;
    const missingSupport = Math.max(0, supportReq - baseSupport);
    let borrowed = 0;
    let undecidedGain = 0;

    if (missingSupport > 0) {
      if (supportMode === "borrow") {
        const borrowable = this.players
          .filter((p) => p.id !== player.id)
          .reduce((sum, p) => sum + p.support, 0);
        if (borrowable < missingSupport) {
          return { success: false, message: "Za mało poparcia do pożyczenia od innych graczy." };
        }
        borrowed = missingSupport;
      } else if (supportMode === "undecided") {
        undecidedGain = Math.max(1, Math.floor(this.rng() * (missingSupport + 2)));
        if (player.support + undecidedGain < supportReq) {
          return {
            success: false,
            message: `Nie udało się przekonać niezdecydowanych (+${undecidedGain}, nadal brakuje ${
              supportReq - (player.support + undecidedGain)
            })`,
          };
        }
        player.support += undecidedGain;
      } else {
        return { success: false, message: "Brakuje poparcia." };
      }
    }

    // Pożyczone poparcie jest jednorazowe do spełnienia warunku (nie zmienia stanu).

    player.hand = player.hand.filter((c) => c !== card);
    player.money -= price;

    const results = card.results || {};
    if (results.support) player.support += toNumber(results.support);
    if (results._1) player._1 += toNumber(results._1);
    if (results._2) player._2 += toNumber(results._2);
    if (results._3) player._3 += toNumber(results._3);

    if (card.type === 1) player._1 += 1;
    if (card.type === 2) player._2 += 1;
    if (card.type === 3) player._3 += 1;

    const effects = card.effects || {};
    ["buildings", "investment", "social"].forEach((typ) => {
      const val = effects[typ];
      if (val === 1 || val === "1") {
        this.board.placeWithEffect(typ, player.id);
      }
    });

    const incr = effects.incr;
    if (incr) {
      const key = Array.isArray(incr) ? incr[0] : incr;
      if (typeof key === "string" && this.indicators[key] !== undefined) {
        const amount = 1;
        const current = this.indicators[key];
        const allowed = Math.min(amount, Math.max(0, this.maxIndicator - current));
        if (allowed > 0) {
          this.indicators[key] += allowed;
          this.indicatorEvents[key][player.id] += 1;
          this.indicatorAmounts[key][player.id] += allowed;
        }
      }
    }

    const replacement = this.drawCard();
    if (replacement) player.hand.push(replacement);
    this.roundAnyPlayed = true;

    let modeNote = "";
    if (borrowed > 0) modeNote = ` (pożyczono poparcie ${borrowed})`;
    if (undecidedGain > 0) modeNote = ` (+${undecidedGain} niezdecydowanych)`;

    return { success: true, message: `${player.id} zagrywa ${card.title || card.id}${modeNote}` };
  }

  exchangeHand(player) {
    let deck = this.decks[this.currentLevel];
    const needed = player.hand.length;
    // Jeśli talia bieżącej ery jest pusta, spróbuj przejść do kolejnej ery.
    if (!deck || deck.length === 0) {
      const advanced = this.advanceLevel();
      if (advanced) {
        deck = this.decks[this.currentLevel];
      }
    }
    if (!deck) return { success: false, reason: "Brak dostępnych talii." };

    if (deck.length < needed) {
      return { success: false, reason: "Za mało kart w bieżącej erze (najpierw wyczerp talię)." };
    }

    const cost = needed;
    if (player.money < cost) {
      return { success: false, reason: "Za mało monet na wymianę." };
    }

    player.money -= cost;
    deck.push(...player.hand);
    player.hand = [];
    this.shuffleDeck(this.currentLevel);
    for (let i = 0; i < 6; i++) {
      if (deck.length === 0) break;
      player.hand.push(deck.shift());
    }
    return { success: true, cost };
  }

  pass(player, reason = "Pas") {
    this.roundPasses += 1;
    this.roundCannotExchange += 1;
    return { success: true, message: `${player.id}: pas (${reason})` };
  }

  payInvestments() {
    this.players.forEach((p) => {
      p.money += p.support;
      this.emit(`${p.id} otrzymuje ${p.support} monet za poziom wsparcia.`);
    });
    this.board.fields.forEach((f) => {
      if (f.type === "investment" && f.occupant) {
        const pl = this.players.find((x) => x.id === f.occupant);
        if (pl) {
          pl.money += f.occupationLevel;
          this.emit(`${pl.id} dostaje ${f.occupationLevel} monet z inwestycji ${f.id}.`);
        }
      }
    });
  }

  aiTurn(player) {
    if (this.gameOver) return;
    const pick = this.pickCardForAI(player);
    if (pick) {
      const res = this.playCard(player, pick.card, pick.mode);
      if (res.success) this.emit(`${player.id} zagrywa kartę ${pick.card.title || pick.card.id} [${pick.mode}].`);
      else this.emit(res.message);
    } else {
      const swap = this.exchangeHand(player);
      if (swap.success) {
        this.emit(`${player.id} wymienia rękę (koszt ${swap.cost} monet).`);
      } else {
        const passed = this.pass(player, swap.reason || "brak ruchów");
        this.emit(passed.message);
      }
    }
  }

  finishPlayerTurn() {
    if (this.gameOver) return;
    this.currentPlayerIndex += 1;
    if (this.currentPlayerIndex >= this.players.length) {
      if (this.roundPasses === this.players.length && this.roundCannotExchange === this.players.length) {
        this.emit("Nikt nie zagrał — wypłata inwestycji i wsparcia.");
        this.payInvestments();
      }
      this.checkEndCondition();
      if (!this.gameOver) {
        const deck = this.decks[this.currentLevel];
        if (!deck || deck.length === 0) {
          const advanced = this.advanceLevel();
          if (!advanced) {
            this.emit("Koniec gry: brak kart na kolejne ery.");
            this.gameOver = true;
          }
        }
      }
      this.round += 1;
      this.currentPlayerIndex = 0;
      this.roundPasses = 0;
      this.roundCannotExchange = 0;
      this.roundAnyPlayed = false;
    }
  }

  checkEndCondition() {
    const reached = Object.values(this.indicators).filter((v) => v >= this.maxIndicator).length;
    if (reached >= 3) {
      this.gameOver = true;
      this.emit("Koniec gry: co najmniej 3 wskaźniki osiągnęły maksimum.");
      const scores = this.computeScores();
      const summary = Object.entries(scores)
        .map(([pid, s]) => `${pid}: ${s.total} (pola ${s.buildingPoints} + wskaźniki ${s.indicatorPoints})`)
        .join(" | ");
      this.emit("Wynik: " + summary);
    }
  }

  computeScores() {
    const scores = {};
    this.players.forEach((p) => {
      const buildingPoints = this.board.fields
        .filter((f) => f.occupant === p.id)
        .reduce((sum, f) => sum + f.occupationLevel, 0);
      const indicatorPoints = Object.values(this.indicatorAmounts).reduce((acc, m) => acc + (m[p.id] || 0), 0);
      scores[p.id] = { buildingPoints, indicatorPoints, total: buildingPoints + indicatorPoints };
    });
    return scores;
  }
}

// --- UI / kontroler ---
const dom = {
  hand: document.getElementById("handContainer"),
  players: document.getElementById("playersContainer"),
  log: document.getElementById("logContainer"),
  indicatorList: document.getElementById("indicatorList"),
  boardSummary: document.getElementById("boardSummary"),
  scoreSummary: document.getElementById("scoreSummary"),
  roundInfo: document.getElementById("roundInfo"),
  deckInfo: document.getElementById("deckInfo"),
  indicatorInfo: document.getElementById("indicatorInfo"),
  resourceInfo: document.getElementById("resourceInfo"),
  stickyResources: document.getElementById("stickyResources"),
  stickyFields: document.getElementById("stickyFields"),
  stickyBoard: document.getElementById("stickyBoard"),
};

function addLog(message) {
  const time = new Date().toLocaleTimeString("pl-PL", { minute: "2-digit", second: "2-digit" });
  state.log.unshift(`[${time}] ${message}`);
  if (state.log.length > 120) state.log.pop();
  renderLog();
}

function render() {
  renderStatusStrip();
  renderHand();
  renderPlayers();
  renderIndicators();
  renderBoardSummary();
  renderScoreSummary();
  renderStickySummary();
  updateActionButtons();
  renderLog();
}

function renderStatusStrip() {
  if (!state.game) return;
  const g = state.game;
  dom.roundInfo.textContent = `Runda ${g.round} • Tura: ${g.players[g.currentPlayerIndex]?.id || "-"}`;
  dom.deckInfo.textContent = `Era ${g.currentLevel} • Karty w talii: ${(g.decks[g.currentLevel] || []).length}`;
  const reached = Object.values(g.indicators).filter((v) => v >= g.maxIndicator).length;
  dom.indicatorInfo.textContent = `Wskaźniki na maksa: ${reached}/3 (koniec przy 3)`;
  const me = g.players.find((p) => p.isHuman);
  if (me) {
    dom.resourceInfo.innerHTML = `
      Ty:
      ${statIcon("money", "Monety")}${me.money}
      ${statIcon("support", "Poparcie")}${me.support}
      ${statIcon("_1", "_1")}${me._1}
      ${statIcon("_2", "_2")}${me._2}
      ${statIcon("_3", "_3")}${me._3}
    `;
  } else {
    dom.resourceInfo.innerHTML = "";
  }
}

function renderHand() {
  const g = state.game;
  dom.hand.innerHTML = "";
  if (!g) return;
  const me = g.players.find((p) => p.isHuman);
  if (!me) return;
  me.hand.forEach((card, idx) => {
    const cardEl = document.createElement("article");
    cardEl.className = "card";
    const waiting = state.waitingForHuman && !g.gameOver;
    const playable = g.canPlay(me, card, "normal") && waiting;
    const canBorrow = waiting && g.canPlay(me, card, "borrow");
    const canUndecided = waiting && g.canPlay(me, card, "undecided");
    const missingSupport = Math.max(0, toNumber(card.requirements?.support) - me.support);
    const borrowable = g.players
      .filter((p) => p.id !== me.id)
      .reduce((sum, p) => sum + p.support, 0);
    if (playable) cardEl.classList.add("playable");
    cardEl.innerHTML = `
      <div>
        <div class="meta">${card.typename || "Karta"} • Era ${card.level}</div>
        <h4>${card.title || card.id}</h4>
        <div class="meta">${card.subtypename || ""}</div>
      </div>
      <div class="card-image">
        <img src="${cardImagePath(card)}" alt="Karta ${card.title || card.id}" onerror="this.style.display='none'">
      </div>
      <div class="description">${card.description || "Brak opisu."}</div>
      <div class="requirements">
        <span class="pill">${statIcon("money","Monety")}${toNumber(card.requirements?.price)}</span>
        <span class="pill">${statIcon("support","Poparcie")}${toNumber(card.requirements?.support)}</span>
        <span class="pill">${statIcon("_1","_1")}${toNumber(card.requirements?._1)}</span>
        <span class="pill">${statIcon("_2","_2")}${toNumber(card.requirements?._2)}</span>
        <span class="pill">${statIcon("_3","_3")}${toNumber(card.requirements?._3)}</span>
      </div>
      <div class="effects">
        ${toNumber(card.effects?.buildings) === 1 ? `<span class="pill strong">🏗 Budowa</span>` : ""}
        ${toNumber(card.effects?.investment) === 1 ? `<span class="pill strong">💹 Inwestycja</span>` : ""}
        ${toNumber(card.effects?.social) === 1 ? `<span class="pill strong">🤝 Społeczne</span>` : ""}
        ${card.effects?.incr ? `<span class="pill strong">⬆️ ${card.effects.incr}</span>` : ""}
      </div>
      <div class="play-buttons">
        <button ${!playable ? "disabled" : ""} data-card="${idx}" data-mode="normal">Zagraj</button>
        <button class="ghost" ${!canBorrow ? "disabled" : ""} data-card="${idx}" data-mode="borrow" title="Dostępne do pożyczenia: ${borrowable}">Zagraj (pożycz)</button>
        <button class="ghost" ${!canUndecided ? "disabled" : ""} data-card="${idx}" data-mode="undecided" title="Spróbuj pozyskać brakujące poparcie od niezdecydowanych">Zagraj (niezdecydowani)</button>
      </div>
      ${missingSupport > 0 ? `<div class="meta">Brakuje ${missingSupport} poparcia.</div>` : ""}
    `;
    cardEl.querySelectorAll("button[data-mode]").forEach((btn) => {
      const mode = btn.getAttribute("data-mode");
      btn.addEventListener("click", () => handlePlay(idx, mode));
    });
    dom.hand.appendChild(cardEl);
  });
}

function renderPlayers() {
  const g = state.game;
  dom.players.innerHTML = "";
  if (!g) return;
  g.players.forEach((p, idx) => {
    const el = document.createElement("div");
    el.className = "player";
    if (idx === g.currentPlayerIndex) el.classList.add("current");
    const fields = g.board.fields.filter((f) => f.occupant === p.id);
    const byType = fields.reduce(
      (acc, f) => {
        acc[f.type] = (acc[f.type] || 0) + 1;
        return acc;
      },
      { buildings: 0, investment: 0, social: 0 }
    );
    el.innerHTML = `
      <div class="header">
        <div>
          <strong>${p.id}</strong>
          <span class="tag">${p.isHuman ? "Ty" : "AI"}</span>
        </div>
        <div class="pill">Karty: ${p.hand.length}</div>
      </div>
      <div class="statline">
        <span>${statIcon("money","Monety")}${p.money}</span>
        <span>${statIcon("support","Poparcie")}${p.support}</span>
        <span>${statIcon("_1","_1")}${p._1}</span>
        <span>${statIcon("_2","_2")}${p._2}</span>
        <span>${statIcon("_3","_3")}${p._3}</span>
      </div>
      <div class="fields">
        ${statIcon("buildings","Budowy")} ${byType.buildings || 0}
        ${statIcon("investment","Inwestycje")} ${byType.investment || 0}
        ${statIcon("social","Społeczne")} ${byType.social || 0}
      </div>
    `;
    dom.players.appendChild(el);
  });
}

function renderIndicators() {
  const g = state.game;
  dom.indicatorList.innerHTML = "";
  if (!g) return;
  Object.entries(g.indicators).forEach(([key, val]) => {
    const wrap = document.createElement("div");
    wrap.className = "indicator";
    const pct = (val / g.maxIndicator) * 100;
    wrap.innerHTML = `
      <div class="label"><span>${indicatorIcon(key)}${key}</span><span>${val} / ${g.maxIndicator}</span></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
    `;
    dom.indicatorList.appendChild(wrap);
  });
}

function renderBoardSummary() {
  const g = state.game;
  dom.boardSummary.innerHTML = "";
  if (!g) return;
  const summary = g.board.summary();
  const items = Object.entries(summary)
    .map(([k, v]) => {
      const iconName =
        k === "buildings" ? "INFRASTRUKTURA" : k === "investment" ? "INWESTYCJE" : k === "social" ? "SPOLECZNE" : k;
      return `<div class="pill">${iconTag(iconName, k)}${v.occupied}/${v.total}</div>`;
    })
    .join(" ");
  dom.boardSummary.innerHTML = items || "<small>Brak pól</small>";
}

function renderScoreSummary() {
  const g = state.game;
  dom.scoreSummary.innerHTML = "";
  if (!g) return;
  const scores = g.computeScores();
  const rows = g.players
    .map((p) => {
      const s = scores[p.id];
      return `<div class="pill">${p.id}: ${s.buildingPoints} z pól, ${s.indicatorPoints} z wskaźników — razem ${s.total}</div>`;
    })
    .join("");
  dom.scoreSummary.innerHTML = rows || "<small>Brak danych</small>";
}

function renderStickySummary() {
  const g = state.game;
  if (!g) {
    dom.stickyResources.innerHTML = "";
    dom.stickyFields.innerHTML = "";
    dom.stickyBoard.innerHTML = "";
    return;
  }
  const me = g.players.find((p) => p.isHuman);
  if (me) {
    dom.stickyResources.innerHTML = `
      <div class="summary-line">${statIcon("money","Monety")} ${me.money}</div>
      <div class="summary-line">${statIcon("support","Poparcie")} ${me.support}</div>
      <div class="summary-line">${statIcon("_1","_1")} ${me._1}</div>
      <div class="summary-line">${statIcon("_2","_2")} ${me._2}</div>
      <div class="summary-line">${statIcon("_3","_3")} ${me._3}</div>
    `;
    const myFields = g.board.fields.filter((f) => f.occupant === me.id);
    const byType = myFields.reduce(
      (acc, f) => {
        acc[f.type] = (acc[f.type] || 0) + 1;
        return acc;
      },
      {}
    );
    dom.stickyFields.innerHTML = `
      <div class="summary-line">${statIcon("buildings","Budowy")} ${byType.buildings || 0}</div>
      <div class="summary-line">${statIcon("investment","Inwestycje")} ${byType.investment || 0}</div>
      <div class="summary-line">${statIcon("social","Społeczne")} ${byType.social || 0}</div>
    `;
  }
  const boardSummary = g.board.summary();
  dom.stickyBoard.innerHTML = Object.entries(boardSummary)
    .map(([k, v]) => {
      const iconName =
        k === "buildings" ? "INFRASTRUKTURA" : k === "investment" ? "INWESTYCJE" : k === "social" ? "SPOLECZNE" : k;
      return `<div class="summary-line">${iconTag(iconName, k)} ${v.occupied}/${v.total}</div>`;
    })
    .join("");
}

function renderLog() {
  dom.log.innerHTML = "";
  state.log.forEach((entry) => {
    const el = document.createElement("div");
    el.className = "log-entry";
    el.textContent = entry;
    dom.log.appendChild(el);
  });
}

function updateActionButtons() {
  const exchangeBtn = document.getElementById("exchangeBtn");
  const passBtn = document.getElementById("passBtn");
  const g = state.game;
  const canAct = Boolean(g && state.waitingForHuman && !g.gameOver);
  exchangeBtn.disabled = !canAct;
  passBtn.disabled = !canAct;
  if (canAct && g) {
    const me = g.players.find((p) => p.isHuman);
    const cost = me ? me.hand.length : 0;
    exchangeBtn.title = `Koszt: ${cost} monet`;
  } else {
    exchangeBtn.title = "";
  }
}

// --- Sterowanie ---
function handlePlay(handIndex, mode = "normal") {
  const g = state.game;
  if (!g || g.gameOver || !state.waitingForHuman) return;
  const me = g.players.find((p) => p.isHuman);
  const card = me?.hand?.[handIndex];
  if (!card) return;
  const res = g.playCard(me, card, mode);
  if (!res.success) {
    addLog(res.message);
    return;
  }
  addLog(res.message);
  g.checkEndCondition();
  state.waitingForHuman = false;
  g.finishPlayerTurn();
  render();
  if (!g.gameOver) scheduleAIMove();
}

function handleExchange() {
  const g = state.game;
  if (!g || g.gameOver || !state.waitingForHuman) return;
  const me = g.players.find((p) => p.isHuman);
  const res = g.exchangeHand(me);
  if (res.success) {
    addLog(`${me.id} wymienia rękę (koszt ${res.cost} monet).`);
    state.waitingForHuman = false;
    g.finishPlayerTurn();
    render();
    if (!g.gameOver) scheduleAIMove();
  } else {
    addLog(res.reason || "Nie można wymienić kart.");
  }
}

function handlePass() {
  const g = state.game;
  if (!g || g.gameOver || !state.waitingForHuman) return;
  const me = g.players.find((p) => p.isHuman);
  const res = g.pass(me, "gracz pasuje");
  addLog(res.message);
  state.waitingForHuman = false;
  g.finishPlayerTurn();
  render();
  if (!g.gameOver) scheduleAIMove();
}

function scheduleAIMove() {
  setTimeout(runUntilHumanTurn, 120);
}

function runUntilHumanTurn() {
  const g = state.game;
  if (!g || g.gameOver) {
    state.waitingForHuman = false;
    render();
    return;
  }
  const current = g.players[g.currentPlayerIndex];
  if (current.isHuman) {
    state.waitingForHuman = true;
    render();
    return;
  }
  state.waitingForHuman = false;
  g.aiTurn(current);
  g.checkEndCondition();
  g.finishPlayerTurn();
  render();
  if (g.gameOver) return;
  scheduleAIMove();
}

// --- Inicjalizacja ---
async function bootstrap() {
  const loader = new CardLoader();
  state.cards = await loader.load();
  attachUI();
  startNewGame();
}

function seedFromInput(raw) {
  if (!raw) return null;
  let hash = 0;
  for (let i = 0; i < raw.length; i++) {
    hash = (hash * 31 + raw.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function startNewGame() {
  const countInput = document.getElementById("playerCount");
  const seedInput = document.getElementById("seedInput");
  const players = Math.min(5, Math.max(2, Number(countInput.value) || 4));
  const seedValue = seedFromInput(seedInput.value.trim());
  const rng = seedValue !== null ? mulberry32(seedValue) : Math.random;
  state.log = [];
  const game = new GameEngine(state.cards, rng);
  game.onLog = addLog;
  game.start(players);
  state.game = game;
  state.waitingForHuman = false;
  render();
  scheduleAIMove();
}

function attachUI() {
  document.getElementById("newGameBtn").addEventListener("click", startNewGame);
  document.getElementById("exchangeBtn").addEventListener("click", handleExchange);
  document.getElementById("passBtn").addEventListener("click", handlePass);
  document.getElementById("clearLogBtn").addEventListener("click", () => {
    state.log = [];
    renderLog();
  });
}

bootstrap().catch((err) => {
  console.error(err);
  addLog("Błąd inicjalizacji: " + err.message);
});
