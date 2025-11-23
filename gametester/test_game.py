#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skrypt testujący grę - wczytanie informacji o kartach
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any

class CardLoader:
    """Klasa odpowiadająca za wczytywanie i przetwarzanie kart gry"""
    
    def __init__(self, base_path: str = "cards"):
        self.base_path = Path(base_path)
        self.cards: Dict[int, List[Dict[str, Any]]] = {}  # {level: [cards]}
        self.stats = {
            "total_cards": 0,
            "cards_by_level": {},
            "cards_by_type": {},
            "errors": []
        }
    
    def load_all_cards(self):
        """Wczytaj wszystkie karty ze wszystkich levelów (1-6)"""
        print("🎮 Wczytywanie kart gry...")
        print("-" * 60)
        
        for level in range(1, 7):
            level_path = self.base_path / str(level)
            
            if not level_path.exists():
                print(f"⚠️  Folder levelu {level} nie istnieje: {level_path}")
                #!/usr/bin/env python3
                # -*- coding: utf-8 -*-
                """
                Uproszczona wersja skryptu: wczytuje karty, tworzy planszę, graczy i przeprowadza szybką symulację.

                Zaimplementowane:
                - CardLoader (wczytywanie kart .json + .desc)
                - Board (pola buildings/investment/social, zajmowanie i ulepszanie)
                - Player i Game: prosty loop rozgrywki dla N graczy
                """

                import json
                import random
                from pathlib import Path
                from typing import Dict, List, Any, Optional
                from collections import deque


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
                                    # skip malformed or missing desc
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
                        # occupy empty if available
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
                        # other _ requirements
                        for k, v in req.items():
                            if k == "_1" and self._1 < v: return False
                            if k == "_2" and self._2 < v: return False
                            if k == "_3" and self._3 < v: return False
                        return True


                class Game:
                    def __init__(self, num_players: int = 4, seed: int = 1):
                        random.seed(seed)
                        self.loader = CardLoader()
                        self.loader.load_all_cards()
                        self.board = Board()
                        self.players: List[Player] = [Player(f"P{i+1}") for i in range(num_players)]
                        self.decks: Dict[int, deque] = {}
                        for level in range(1, 7):
                            cards = list(self.loader.get_level_cards(level))
                            random.shuffle(cards)
                            self.decks[level] = deque(cards)
                        self.current_level = 1
                        self.indicators = {k: 0 for k in [
                            "_1_1","_1_2","_1_3",
                            "_2_1","_2_2","_2_3",
                            "_3_1","_3_2","_3_3"]}
                        self.max_indicator = 8
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

                    def advance_level(self) -> bool:
                        if self.current_level < 6:
                            self.current_level += 1
                            print(f"--- Przechodzimy do ery {self.current_level} ---")
                            return True
                        return False

                    def resolve_play(self, p: Player, card: Dict[str, Any]):
                        # remove from hand
                        try: p.hand.remove(card)
                        except ValueError: pass
                        jd = card.get("json_data", {})
                        req = jd.get("requirements", {})
                        price = req.get("price", 0)
                        p.money -= price
                        # apply results
                        results = jd.get("results", {})
                        for k, v in results.items():
                            if k == "support": p.support += v
                            elif k == "_1": p._1 += v
                            elif k == "_2": p._2 += v
                            elif k == "_3": p._3 += v
                            elif k in self.indicators: self.indicators[k] += v
                        # effects -> board
                        effects = jd.get("effects", {})
                        for t in ("buildings", "investment", "social"):
                            if effects.get(t):
                                success, msg, fid = self.board.place_with_card_effect(t, p.id, prefer_upgrade=True)
                                print(f"  {p.id} effect {t}: {msg} (success={success})")
                        # draw
                        new = self.draw_card()
                        if new: p.hand.append(new)

                    def pay_investments(self):
                        for f in self.board.fields:
                            if f["type"] == "investment" and f["occupant"]:
                                pid = f["occupant"]
                                pl = next((x for x in self.players if x.id == pid), None)
                                if pl:
                                    pl.money += f["occupation_level"]
                                    print(f"{pl.id} otrzymuje {f['occupation_level']} monet z pola {f['id']}")

                    def play(self, max_rounds: int = 200):
                        for rnd in range(1, max_rounds + 1):
                            print(f"\n--- Runda {rnd} (level {self.current_level}) ---")
                            any_played = False
                            for p in self.players:
                                playable = [c for c in p.hand if p.can_play_card(c)]
                                if not playable:
                                    print(f"{p.id} passes")
                                    continue
                                card = random.choice(playable)
                                print(f"{p.id} zagrywa {card['json_file']}")
                                self.resolve_play(p, card)
                                any_played = True
                            self.pay_investments()
                            # check indicators
                            for k, v in self.indicators.items():
                                if v >= self.max_indicator:
                                    print(f"Koniec gry: {k} osiągnął {v}")
                                    return
                            if not any_played:
                                if not self.advance_level():
                                    print("Koniec gry: brak zagrań i brak dalszych leveli")
                                    return


                def run_simulation():
                    game = Game(num_players=4, seed=123)
                    game.play(max_rounds=200)
                    print('\n--- Wyniki końcowe ---')
                    for p in game.players:
                        print(f"{p.id}: money={p.money} support={p.support} _1={p._1} _2={p._2} _3={p._3} hand={len(p.hand)}")
                    print('Indicators:', game.indicators)


                if __name__ == "__main__":
                    loader = CardLoader()
                    loader.load_all_cards()
                    loader_cards = loader.get_level_cards(1)
                    print(f"Przykłowo: level 1 ma {len(loader_cards)} kart")
                    # pokaz demo planszy
                    board = Board()
                    print('Początkowe podsumowanie planszy:', board.summary())
                    success, msg, fid = board.place_with_card_effect('social', 'Alice')
                    print('Demo placement:', msg)
                    # uruchom symulację 4 graczy
                    run_simulation()
            for card_type, count in sorted(self.stats["cards_by_type"].items()):
                print(f"    {card_type}: {count} kart")
        
        if self.stats["errors"]:
            print(f"\n  ⚠️  Błędy ({len(self.stats['errors'])}):")
            for error in self.stats["errors"][:5]:  # Pokaż pierwsze 5 błędów
                print(f"    - {error}")
            if len(self.stats["errors"]) > 5:
                print(f"    ... i {len(self.stats['errors']) - 5} więcej błędów")
    
    def get_card_by_code(self, card_code: str) -> Dict[str, Any]:
        """Wyszukaj kartę po kodzie"""
        for level_cards in self.cards.values():
            for card in level_cards:
                if card["card_code"] == card_code:
                    return card
        return None
    
    def get_level_cards(self, level: int) -> List[Dict[str, Any]]:
        """Zwróć wszystkie karty z danego levelu"""
        return self.cards.get(level, [])
    
    def print_level_summary(self, level: int):
        """Wydrukuj podsumowanie kart z danego levelu"""
        cards = self.get_level_cards(level)
        
        if not cards:
            print(f"Brak kart dla levelu {level}")
            return
        
        print(f"\n📋 LEVEL {level} ({len(cards)} kart):")
        print("-" * 60)
        
        for i, card in enumerate(cards, 1):
            print(f"{i}. {card['card_name']}")
            print(f"   Kod: {card['card_code']}")
            print(f"   Plik JSON: {card['json_file']}")
            print(f"   Plik DESC: {card['desc_file']}")
            print()


class Board:
    """Plansza gry z polami typu 'buildings', 'investment', 'social'.

    Każde pole ma:
      - id: int (0..47)
      - type: 'buildings'|'funds'|'social'
      - occupant: player id (str) lub None
      - occupation_level: 0..4 (0 = puste)

    Zasady:
      - Zagrywając kartę z efektem odpowiadającym typowi pola, gracz może zająć puste pole (ustaw level=1)
        albo zwiększyć swój level na polu (do max 4).
      - Efekt karty można zastosować tylko na pasującym typie pola.
    """

    def __init__(self, buildings=16, investment=16, social=16, max_level=4):
        self.max_level = max_level
        self.fields = []  # list of dicts
        # create fields: first buildings, then funds, then social
        idx = 0
        for _ in range(buildings):
            self.fields.append({"id": idx, "type": "buildings", "occupant": None, "occupation_level": 0})
            idx += 1
        for _ in range(investment):
            self.fields.append({"id": idx, "type": "investment", "occupant": None, "occupation_level": 0})
            idx += 1
        for _ in range(social):
            self.fields.append({"id": idx, "type": "social", "occupant": None, "occupation_level": 0})
            idx += 1

    def find_empty_field(self, field_type: str):
        """Zwróć indeks pierwszego pustego pola danego typu lub None"""
        for f in self.fields:
            if f["type"] == field_type and f["occupant"] is None:
                return f["id"]
        return None

    def find_player_fields(self, player_id: str, field_type: str):
        """Zwróć listę pól danego typu zajętych przez gracza"""
        return [f for f in self.fields if f["type"] == field_type and f["occupant"] == player_id]

    def occupy_field(self, field_id: int, player_id: str):
        f = self.fields[field_id]
        if f["occupant"] is None:
            f["occupant"] = player_id
            f["occupation_level"] = 1
            return True
        if f["occupant"] != player_id:
            raise ValueError(f"Pole {field_id} zajęte przez innego gracza: {f['occupant']}")
        # if same player, increase level
        if f["occupation_level"] < self.max_level:
            f["occupation_level"] += 1
            return True
        return False

    def upgrade_field(self, field_id: int, player_id: str):
        """Zwiększ poziom zajęcia pola, jeśli należy do gracza"""
        f = self.fields[field_id]
        if f["occupant"] != player_id:
            raise ValueError("Nie możesz ulepszyć pola, które nie należy do Ciebie")
        if f["occupation_level"] >= self.max_level:
            return False
        f["occupation_level"] += 1
        return True

    def place_with_card_effect(self, effect_type: str, player_id: str, prefer_upgrade: bool = False):
        """Zagraj kartę z efektem effect_type na planszy.

        Jeśli prefer_upgrade=True: spróbuj najpierw ulepszyć istniejące pole gracza (do max),
        w przeciwnym wypadku spróbuj zająć puste pole pierwsze.

        Zwraca (success: bool, message: str, field_id: int|None)
        """
        if effect_type not in ("buildings", "investment", "social"):
            return False, f"Nieznany typ efektu: {effect_type}", None

        # find player's fields of that type
        player_fields = self.find_player_fields(player_id, effect_type)

        # Option A: upgrade existing field
        if prefer_upgrade and player_fields:
            # choose the field with lowest level < max to upgrade
            candidates = [f for f in player_fields if f["occupation_level"] < self.max_level]
            if candidates:
                # pick one with highest level (or any policy)
                field = sorted(candidates, key=lambda x: x["occupation_level"])[-1]
                self.upgrade_field(field["id"], player_id)
                return True, f"Ulepszono pole {field['id']}", field["id"]

        # Option B: occupy empty field of that type
        empty_id = self.find_empty_field(effect_type)
        if empty_id is not None and not prefer_upgrade:
            self.occupy_field(empty_id, player_id)
            return True, f"Zajęto puste pole {empty_id}", empty_id

        # If prefer_upgrade=False, try to upgrade player's existing field
        if not prefer_upgrade and player_fields:
            candidates = [f for f in player_fields if f["occupation_level"] < self.max_level]
            if candidates:
                field = sorted(candidates, key=lambda x: x["occupation_level"])[-1]
                self.upgrade_field(field["id"], player_id)
                return True, f"Ulepszono pole {field['id']}", field["id"]

        return False, "Brak dostępnych pól do użycia efektu", None

    def summary(self):
        out = {}
        for f in self.fields:
            t = f["type"]
            out.setdefault(t, {"total": 0, "occupied": 0})
            out[t]["total"] += 1
            if f["occupant"] is not None:
                out[t]["occupied"] += 1
        return out



def main():
    """Główna funkcja"""
    # Zaladuj karty
    loader = CardLoader()
    loader.load_all_cards()
    
    # Przykład: wydrukuj podsumowanie levelu 1
    loader.print_level_summary(1)
    
    # Przykład: wyszukaj kartę po kodzie
    print("\n🔍 Przykład wyszukiwania:")
    card = loader.get_card_by_code("1-1-E[1]")
    if card:
        print(f"Znaleziona karta: {card['card_name']}")
        print(f"Opis: {card['desc_data'].get('description', 'Brak')[:100]}...")
    else:
        print("Karta nie znaleziona")

    # ---- Demonstracja planszy i zasad zajmowania pól ----
    board = Board()
    print('\n🎲 Demonstracja planszy:')
    print('Początkowe podsumowanie:', board.summary())

    # Gracz Alice zagra kartę typu 'social' i chce zająć puste pole
    success, msg, field_id = board.place_with_card_effect('social', 'Alice', prefer_upgrade=False)
    print(f"Alice gra 'social' -> {msg} (success={success})")

    # Alice zagrywa kolejną kartę 'social' i woli ulepszyć swoje pole
    success, msg, field_id = board.place_with_card_effect('social', 'Alice', prefer_upgrade=True)
    print(f"Alice gra drugi raz 'social' (prefer_upgrade) -> {msg} (success={success})")

    # Gracz Bob zajmuje pole typu 'investment'
    success, msg, field_id = board.place_with_card_effect('investment', 'Bob')
    print(f"Bob gra 'funds' -> {msg} (success={success})")

    # Kolejne zagranie Alice na social (ulepszamy dalej)
    for _ in range(3):
        success, msg, field_id = board.place_with_card_effect('social', 'Alice', prefer_upgrade=True)
        print(f"Alice dalsze granie 'social' -> {msg} (success={success})")

    # Pokaż status kilku pól social
    social_fields = [f for f in board.fields if f['type'] == 'social'][:5]
    print('\nStatus pierwszych 5 pól social:')
    for f in social_fields:
        print(f"  id={f['id']} occupant={f['occupant']} level={f['occupation_level']}")

    print('\nPodsumowanie planszy po zagraniach:', board.summary())


if __name__ == "__main__":
    main()
