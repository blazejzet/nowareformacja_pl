#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prosta symulacja gry: wczytanie kart, plansza, gracze i rozgrywka dla N graczy.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque

# --- Prosty logger / helper do czytelnych komunikatów gry (polski) ---
def log_round_start(rnd: int, level: int):
    print("\n" + "=" * 60)
    print(f"Runda {rnd} — Era {level}")
    print("-" * 60)


def log_player_exchange(p: 'Player', cost: int):
    print(f"{p.id}: wymienia rękę (koszt: {cost} monet) — Stan: Monety={p.money}, Support={p.support}, _1={p._1}, _2={p._2}, _3={p._3}")


def log_player_pass(p: 'Player'):
    print(f"{p.id}: PAS (nie stać na wymianę lub pula za mała) — Stan: Monety={p.money}, Support={p.support}, _1={p._1}, _2={p._2}, _3={p._3}")


def log_player_play(p: 'Player', filename: str):
    print(f"{p.id} zagrał: {filename}")


def log_effects_available(typ: str, ids: List[int]):
    print(f"    -> Dostępne pola [{typ}]: {ids}")


def log_effect_result(p: 'Player', typ: str, success: bool, msg: str):
    prefix = "      *" if success else "      !"
    print(f"{prefix} {p.id} — {typ}: {msg}")


def log_payment_start():
    print("Wypłata: poparcie + zarobek z pól investment")


def log_game_end(reached: List[str], max_indicator: int):
    print(f"Koniec gry: {len(reached)} wskaźniki osiągnęły poziom {max_indicator}: {reached}")


class CardLoader:
    def __init__(self, base_path: str = "cards"):
        self.base_path = Path(base_path)
        self.cards: Dict[int, List[Dict[str, Any]]] = {}

    def load_all_cards(self):
        for level in range(1, 7):
            level_path = self.base_path / str(level)
            if not level_path.exists():
                self.cards[level] = []
                continue
            items = []
            for jf in sorted(level_path.glob("*.json")):
                desc = level_path / (jf.stem + ".desc")
                try:
                    with open(jf, encoding='utf-8') as f:
                        jd = json.load(f)
                    with open(desc, encoding='utf-8') as f:
                        dd = json.load(f)
                    items.append({
                        "json_file": jf.name,
                        "desc_file": desc.name,
                        "json_data": jd,
                        "desc_data": dd,
                        "card_code": jd.get("cardcode"),
                        "card_name": dd.get("title"),
                    })
                except Exception:
                    continue
            self.cards[level] = items

    def get_level_cards(self, level: int) -> List[Dict[str, Any]]:
        return list(self.cards.get(level, []))


class Board:
    def __init__(self, buildings=16, investment=16, social=16, max_level=4):
        self.max_level = max_level
        self.fields = []
        idx = 0
        for _ in range(buildings):
            self.fields.append({"id": idx, "type": "buildings", "occupant": None, "occupation_level": 0}); idx += 1
        for _ in range(investment):
            self.fields.append({"id": idx, "type": "investment", "occupant": None, "occupation_level": 0}); idx += 1
        for _ in range(social):
            self.fields.append({"id": idx, "type": "social", "occupant": None, "occupation_level": 0}); idx += 1

    def find_empty_field(self, t: str) -> Optional[int]:
        for f in self.fields:
            if f["type"] == t and f["occupant"] is None:
                return f["id"]
        return None

    def find_player_fields(self, pid: str, t: str) -> List[Dict[str, Any]]:
        return [f for f in self.fields if f["type"] == t and f["occupant"] == pid]

    def occupy_field(self, fid: int, pid: str) -> bool:
        f = self.fields[fid]
        if f["occupant"] is None:
            f["occupant"] = pid; f["occupation_level"] = 1; return True
        if f["occupant"] != pid:
            raise ValueError("Pole zajęte przez innego gracza")
        if f["occupation_level"] < self.max_level:
            f["occupation_level"] += 1; return True
        return False

    def upgrade_field(self, fid: int, pid: str) -> bool:
        f = self.fields[fid]
        if f["occupant"] != pid: raise ValueError("Nie twoje pole")
        if f["occupation_level"] >= self.max_level: return False
        f["occupation_level"] += 1
        return True

    def place_with_card_effect(self, effect_type: str, player_id: str, prefer_upgrade: bool = False):
        if effect_type not in ("buildings", "investment", "social"):
            return False, f"Nieznany typ efektu: {effect_type}", None
        player_fields = self.find_player_fields(player_id, effect_type)
        if prefer_upgrade and player_fields:
            candidates = [f for f in player_fields if f["occupation_level"] < self.max_level]
            if candidates:
                field = sorted(candidates, key=lambda x: x["occupation_level"])[-1]
                self.upgrade_field(field["id"], player_id)
                return True, f"Ulepszono pole {field['id']}", field["id"]
        empty = self.find_empty_field(effect_type)
        if empty is not None and not prefer_upgrade:
            self.occupy_field(empty, player_id)
            return True, f"Zajęto puste pole {empty}", empty
        if not prefer_upgrade and player_fields:
            candidates = [f for f in player_fields if f["occupation_level"] < self.max_level]
            if candidates:
                field = sorted(candidates, key=lambda x: x["occupation_level"])[-1]
                self.upgrade_field(field["id"], player_id)
                return True, f"Ulepszono pole {field['id']}", field["id"]
        return False, "Brak dostępnych pól do użycia efektu", None

    def summary(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for f in self.fields:
            t = f["type"]
            out.setdefault(t, {"total": 0, "occupied": 0})
            out[t]["total"] += 1
            if f["occupant"]: out[t]["occupied"] += 1
        return out


class Player:
    def __init__(self, pid: str):
        self.id = pid
        self.money = 20
        self.support = 20
        self._1 = 0
        self._2 = 0
        self._3 = 0
        self.hand: List[Dict[str, Any]] = []

    def can_play_card(self, card: Dict[str, Any]) -> bool:
        req = card.get("json_data", {}).get("requirements", {})
        price = req.get("price", 0)
        if self.money < price: return False
        support_req = req.get("support", 0)
        if self.support < support_req: return False
        for k, v in req.items():
            if k == "_1" and self._1 < v: return False
            if k == "_2" and self._2 < v: return False
            if k == "_3" and self._3 < v: return False
        return True


class Game:
    def __init__(self, num_players: int = 4, seed: int = 1, verbose: bool = True):
        random.seed()
        self.loader = CardLoader()
        self.loader.load_all_cards()
        self.board = Board()
        self.verbose = verbose
        self.players: List[Player] = [Player(f"P{i+1}") for i in range(num_players)]
        self.decks: Dict[int, deque] = {}
        # All cards from all levels in one pool (level 1)
        all_cards = []
        for level in range(1, 7):
            all_cards.extend(self.loader.get_level_cards(level))
        random.shuffle(all_cards)
        self.decks = {1: deque(all_cards)}
        for level in range(2, 7):
            self.decks[level] = deque()
        # Ensure deck 1 is shuffled (we shuffled the list above, but normalize via helper)
        self.shuffle_deck(1)
        self.current_level = 1
        # Initialize indicators: only columns 1..3 exist (_1_1.._3_3)
        # (do not create _1_4/_2_4/_3_4 even if there are 4+ players)
        self.indicators = {}
        for base in [1, 2, 3]:
            for col in range(1, 4):
                self.indicators[f"_{base}_{col}"] = 0
        # Track who increased indicators: event counts and total increment amounts
        self.indicator_events: Dict[str, Dict[str, int]] = {}
        self.indicator_amounts: Dict[str, Dict[str, int]] = {}
        for ind_key in list(self.indicators.keys()):
            self.indicator_events[ind_key] = {p.id: 0 for p in self.players}
            self.indicator_amounts[ind_key] = {p.id: 0 for p in self.players}
        self.max_indicator = 6
        self.deal_initial()

    def deal_initial(self):
        for p in self.players:
            for _ in range(6):
                c = self.draw_card()
                if c: p.hand.append(c)

    def draw_card(self) -> Optional[Dict[str, Any]]:
        lvl = self.current_level
        while lvl <= 6:
            deck = self.decks.get(lvl)
            if deck and len(deck) > 0:
                return deck.popleft()
            lvl += 1
        return None

    def shuffle_deck(self, level: int):
        """Shuffle the deck at given level in-place.

        Decks are stored as deques; convert to list to shuffle and reassign.
        """
        deck = self.decks.get(level)
        if deck is None:
            return
        lst = list(deck)
        random.shuffle(lst)
        self.decks[level] = deque(lst)

    def advance_level(self) -> bool:
        if self.current_level < 6:
            self.current_level += 1
            print(f"--- Przechodzimy do ery {self.current_level} ---")
            return True
        return False

    def resolve_play(self, p: Player, card: Dict[str, Any]):
        try:
            p.hand.remove(card)
        except ValueError:
            pass
        jd = card.get("json_data", {})
        req = jd.get("requirements", {})
        price = req.get("price", 0)
        p.money -= price

        # Capture old parameter values to compute deltas for indicators
        old_1, old_2, old_3 = p._1, p._2, p._3

        # Apply simple results (support and local _1/_2/_3 increments)
        # Note: do NOT increment global indicators here; indicator changes
        # are handled only via effects['incr'] (one increment per play).
        results = jd.get("results", {})
        for k, v in results.items():
            if k == "support":
                p.support += v
            elif k == "_1":
                p._1 += v
            elif k == "_2":
                p._2 += v
            elif k == "_3":
                p._3 += v

        # Zwiększ _1/_2/_3 jeśli karta ma jawny typ 1/2/3
        card_type = jd.get("type")
        if card_type == 1:
            p._1 += 1
        elif card_type == 2:
            p._2 += 1
        elif card_type == 3:
            p._3 += 1

        # Obsługa efektów: tylko dla kluczy obecnych w effects
        effects = jd.get("effects", {})
        for typ, val in effects.items():
            if typ not in ("buildings", "investment", "social"):
                continue
            if val == 1 or val == "1":
                available = [f for f in self.board.fields if f["type"] == typ and f["occupant"] is None]
                if self.verbose:
                    log_effects_available(typ, [f["id"] for f in available])
                success, msg, fid = self.board.place_with_card_effect(typ, p.id)
                if self.verbose:
                    log_effect_result(p, typ, success, msg)

        # Some cards specify effects['incr'] = "_1_3" (string) meaning increment that indicator
        # Rule: one card play => at most one indicator increment, and only if effects['incr'] is present.
        incr = effects.get("incr")
        if incr:
            # normalize to list, but only take the first entry (one increment per play)
            if isinstance(incr, str):
                key = incr
            elif isinstance(incr, list) and len(incr) > 0:
                key = incr[0]
            else:
                key = None
            if isinstance(key, str) and key in self.indicators:
                try:
                    # Default increment is 1 (one raise per play)
                    amount = 1
                    current = self.indicators.get(key, 0)
                    allowed = min(amount, max(0, self.max_indicator - current))
                    if allowed <= 0:
                        if self.verbose:
                            print(f"    -> Wskaźnik {key} już osiągnął maksymalny poziom ({self.max_indicator}); efekt pominięty dla {p.id}")
                    else:
                        self.indicators[key] += allowed
                        # record who contributed (single event)
                        self.indicator_events[key][p.id] += 1
                        self.indicator_amounts[key][p.id] += allowed
                        if self.verbose:
                            print(f"    -> Wskaźnik {key} zwiększony o {allowed} przez {p.id} (suma: {self.indicators[key]})")
                except Exception:
                    pass

        # Do NOT update global indicators based on local _1/_2/_3 deltas anymore.
        # Player local params (_1/_2/_3) are updated above but global indicators
        # are modified only via effects['incr'] (one increment per play).

        # Show player state after action
        print(f"    Stan {p.id}: monety={p.money}, support={p.support}, _1={p._1}, _2={p._2}, _3={p._3}")

        # Draw replacement card
        new = self.draw_card()
        if new:
            p.hand.append(new)

    def pay_investments(self):
        # Najpierw wypłata za support
        for p in self.players:
            p.money += p.support
            print(f"{p.id} otrzymuje {p.support} monet za poziom Supportu")
        # Następnie wypłata za inwestycje
        for f in self.board.fields:
            if f["type"] == "investment" and f["occupant"]:
                pid = f["occupant"]
                pl = next((x for x in self.players if x.id == pid), None)
                if pl:
                    pl.money += f["occupation_level"]
                    print(f"{pl.id} otrzymuje {f['occupation_level']} monet z pola {f['id']}")

    def print_contributions(self):
        """Wypisz tabelarycznie, kto ile razy i o ile zwiększył każdy wskaźnik."""
        players = [p.id for p in self.players]
        for ind in sorted(self.indicators.keys()):
            print('\nWskaźnik:', ind, f"(wartość końcowa: {self.indicators[ind]})")
            print('-' * 60)
            hdr = f"{'Player':8} | {'Events':6} | {'TotalInc':8}"
            print(hdr)
            print('-' * len(hdr))
            for pid in players:
                ev = self.indicator_events.get(ind, {}).get(pid, 0)
                amt = self.indicator_amounts.get(ind, {}).get(pid, 0)
                print(f"{pid:8} | {ev:6} | {amt:8}")

    def compute_scores(self) -> Dict[str, Dict[str, int]]:
        """Compute per-player scoring:
        - 1 point per level of owned building on the board (occupation_level)
        - 1 point per unit of indicator increment the player caused (sum of indicator_amounts)

        Returns mapping player_id -> {building_points, indicator_points, total}
        """
        scores: Dict[str, Dict[str, int]] = {}
        for p in self.players:
            building_points = sum(
                f["occupation_level"]
                for f in self.board.fields
                if f["occupant"] == p.id
            )
            # sum of all increments this player caused across all indicators
            indicator_points = sum(
                self.indicator_amounts.get(ind, {}).get(p.id, 0)
                for ind in self.indicator_amounts
            )
            total = building_points + indicator_points
            scores[p.id] = {
                "building_points": building_points,
                "indicator_points": indicator_points,
                "total": total,
            }
        return scores

    def play(self, max_rounds: int = 200):
        for rnd in range(1, max_rounds + 1):
            if self.verbose:
                log_round_start(rnd, self.current_level)
            any_played = False
            passes = 0
            cannot_exchange = 0
            for p in self.players:
                playable = [c for c in p.hand if p.can_play_card(c)]
                if not playable:
                    deck = self.decks.get(self.current_level)
                    needed = len(p.hand)
                    lvl = self.current_level + 1
                    while deck and len(deck) < needed and lvl <= 6:
                        next_deck = self.decks.get(lvl)
                        # move all cards from the next level into current deck, then shuffle
                        if next_deck and len(next_deck) > 0:
                            items = list(next_deck)
                            deck.extend(items)
                            next_deck.clear()
                            self.shuffle_deck(self.current_level)
                        lvl += 1
                    cost = needed
                    if deck and len(deck) >= needed and p.money >= cost:
                        p.money -= cost
                        for c in p.hand:
                            deck.append(c)
                        p.hand.clear()
                        # shuffle deck after returning cards to it
                        self.shuffle_deck(self.current_level)
                        for _ in range(6):
                            if deck:
                                p.hand.append(deck.popleft())
                        if self.verbose:
                            log_player_exchange(p, cost)
                    else:
                        if self.verbose:
                            log_player_pass(p)
                        passes += 1
                        cannot_exchange += 1
                    continue
                card = random.choice(playable)
                if self.verbose:
                    log_player_play(p, card['json_file'])
                self.resolve_play(p, card)
                any_played = True
            # Wypłata tylko jeśli wszyscy gracze nie mogą zagrać i nie mogą wymienić kart
            if passes == len(self.players) and cannot_exchange == len(self.players):
                if self.verbose:
                    log_payment_start()
                self.pay_investments()
                for p in self.players:
                    print(f"{p.id}: money={p.money} (po wypłacie)")
            # End condition: game ends when at least 3 indicators reached the max_indicator
            reached = [k for k, v in self.indicators.items() if v >= self.max_indicator]
            if len(reached) >= 3:
                if self.verbose:
                    log_game_end(reached, self.max_indicator)
                return
            deck = self.decks.get(self.current_level)
            if deck is not None and len(deck) == 0:
                if not self.advance_level():
                    print("Koniec gry: brak zagrań i brak dalszych leveli")
                    return


def run_simulation():
    game = Game(num_players=4, seed=123, verbose=True)
    game.play()
    print('\n--- Wyniki końcowe ---')
    for p in game.players:
        print(f"{p.id}: money={p.money} support={p.support} _1={p._1} _2={p._2} _3={p._3} hand={len(p.hand)}")
    print('Indicators:', game.indicators)
    # Print contributions report (who increased which indicators)
    # print('\n--- Contributions report ---')
    # game.print_contributions()
    # Compute and print scoring
    print('\n--- Scoring ---')
    scores = game.compute_scores()
    # print a compact table
    hdr = f"{'Player':6} | {'BuildPts':8} | {'IndPts':6} | {'Total':5}"
    print(hdr)
    print('-' * len(hdr))
    for p in game.players:
        s = scores.get(p.id, {})
        print(f"{p.id:6} | {s.get('building_points',0):8} | {s.get('indicator_points',0):6} | {s.get('total',0):5}")


if __name__ == "__main__":
    loader = CardLoader()
    loader.load_all_cards()
    print(f"Level 1 cards: {len(loader.get_level_cards(1))}")
    board = Board()
    print('Początkowe podsumowanie planszy:', board.summary())
    success, msg, fid = board.place_with_card_effect('social', 'Alice')
    print('Demo placement:', msg)
    run_simulation()

