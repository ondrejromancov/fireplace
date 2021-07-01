import os.path
import random
from bisect import bisect
from importlib import import_module
from pkgutil import iter_modules
from typing import List
from xml.etree import ElementTree
import csv

from hearthstone.enums import CardClass, CardType


# Autogenerate the list of cardset modules
_cards_module = os.path.join(os.path.dirname(__file__), "cards")
CARD_SETS = [cs for _, cs, ispkg in iter_modules([_cards_module]) if ispkg]


class CardList(list):
    def __contains__(self, x):
        for item in self:
            if x is item:
                return True
        return False

    def __getitem__(self, key):
        ret = super().__getitem__(key)
        if isinstance(key, slice):
            return self.__class__(ret)
        return ret

    def __int__(self):
        # Used in Kettle to easily serialize CardList to json
        return len(self)

    def contains(self, x):
        """
        True if list contains any instance of x
        """
        for item in self:
            if x == item:
                return True
        return False

    def index(self, x):
        for i, item in enumerate(self):
            if x is item:
                return i
        raise ValueError

    def remove(self, x):
        for i, item in enumerate(self):
            if x is item:
                del self[i]
                return
        raise ValueError

    def exclude(self, *args, **kwargs):
        if args:
            return self.__class__(e for e in self for arg in args if e is not arg)
        else:
            return self.__class__(e for k, v in kwargs.items() for e in self if getattr(e, k) != v)

    def filter(self, **kwargs):
        return self.__class__(e for k, v in kwargs.items() for e in self if getattr(e, k, 0) == v)


def random_draft(card_class: CardClass, exclude=[]):
    """
    Return a deck of 30 random cards for the \a card_class
    """
    from . import cards
    from .deck import Deck

    deck = []
    collection = []
    # hero = card_class.default_hero

    for card in cards.db.keys():
        if card in exclude:
            continue
        cls = cards.db[card]
        if not cls.collectible:
            continue
        if cls.type == CardType.HERO:
            # Heroes are collectible...
            continue
        if cls.card_class and cls.card_class not in [card_class, CardClass.NEUTRAL]:
            # Play with more possibilities
            continue
        collection.append(cls)

    while len(deck) < Deck.MAX_CARDS:
        card = random.choice(collection)
        if deck.count(card.id) < card.max_count_in_deck:
            deck.append(card.id)

    return deck


def random_class():
    return CardClass(random.randint(2, 10))


def get_script_definition(id):
    """
    Find and return the script definition for card \a id
    """
    for cardset in CARD_SETS:
        module = import_module("fireplace.cards.%s" % (cardset))
        if hasattr(module, id):
            return getattr(module, id)


def entity_to_xml(entity):
    e = ElementTree.Element("Entity")
    for tag, value in entity.tags.items():
        if value and not isinstance(value, str):
            te = ElementTree.Element("Tag")
            te.attrib["enumID"] = str(int(tag))
            te.attrib["value"] = str(int(value))
            e.append(te)
    return e


def game_state_to_xml(game):
    tree = ElementTree.Element("HSGameState")
    tree.append(entity_to_xml(game))
    for player in game.players:
        tree.append(entity_to_xml(player))
    for entity in game:
        if entity.type in (CardType.GAME, CardType.PLAYER):
            # Serialized those above
            continue
        e = entity_to_xml(entity)
        e.attrib["CardID"] = entity.id
        tree.append(e)

    return ElementTree.tostring(tree)


def capture_game_state(game):
    from .card import Minion

    state = {
        # Basic info
        'player1': game.players[0].hero.data.card_class,
        'player0': game.players[1].hero.data.card_class,
        'turn': game.turn,
        'current_player': game.current_player.hero.data.card_class,
        # Player 0
        'player1_health': game.players[0].hero.health,
        'player1_armor': game.players[0].hero.armor,
        'player1_fatique_counter': game.players[0].fatigue_counter,
        'player1_overloaded': game.players[0].overloaded,
        'player1_overload_locked': game.players[0].overload_locked,
        'player1_max_mana': game.players[0]._max_mana,
        'player1_temp_mana': game.players[0].temp_mana,
        'player1_used_mana': game.players[0].used_mana,
        'player1_weapon_atk': game.players[0].weapon.atk if game.players[0].weapon != None else 0,
        'player1_weapon_durability': game.players[0].weapon.durability if game.players[0].weapon != None else 0,
        'player1_weapon_immune_while_attacking': game.players[0].weapon.immune_while_attacking if game.players[0].weapon != None else False,
        'player1_weapon_incoming_damage_multiplier': game.players[0].weapon.incoming_damage_multiplier if game.players[0].weapon != None else False,
        'player1_deck_size': len(game.players[0].deck),
        'player1_hand_size': len(game.players[0].hand),
        'player1_secrets': len(game.players[0].secrets),
        # Player 1
        'player0_armor': game.players[1].hero.armor,
        'player0_health': game.players[1].hero.health,
        'player0_fatique_counter': game.players[1].fatigue_counter,
        'player0_overloaded': game.players[1].overloaded,
        'player0_overload_locked': game.players[1].overload_locked,
        'player0_max_mana': game.players[1]._max_mana,
        'player0_temp_mana': game.players[1].temp_mana,
        'player0_used_mana': game.players[1].used_mana,
        'player0_weapon_atk': game.players[1].weapon.atk if game.players[1].weapon != None else 0,
        'player0_weapon_durability': game.players[1].weapon.durability if game.players[1].weapon != None else 0,
        'player0_weapon_immune_while_attacking': game.players[1].weapon.immune_while_attacking if game.players[1].weapon != None else False,
        'player0_weapon_incoming_damage_multiplier': game.players[1].weapon.incoming_damage_multiplier if game.players[1].weapon != None else False,
        'player0_deck_size': len(game.players[1].deck),
        'player0_hand_size': len(game.players[1].hand),
        'player0_secrets': len(game.players[1].secrets),
    }

    for p_index, player in enumerate(game.players, start=1):
        for i in range(game.MAX_MINIONS_ON_FIELD):
            field = player.field
            if len(field) > i:
                minion = field.__getitem__(i)
            else:
                minion = None

            if isinstance(minion, Minion):
                # Integer values
                state[('player' + str(p_index) + '_minion' + str(i) + '_atk')] = minion.atk
                state[('player' + str(p_index) + '_minion' + str(i) + '_max_health')] = minion.max_health
                state[('player' + str(p_index) + '_minion' + str(i) + '_damage')] = minion.damage
                state[('player' + str(p_index) + '_minion' + str(i) + '_incoming_damage_multiplier')] = minion.incoming_damage_multiplier
                state[('player' + str(p_index) + '_minion' + str(i) + '_spellpower')] = minion.spellpower
                state[('player' + str(p_index) + '_minion' + str(i) + '_max_attacks')] = minion.max_attacks
                state[('player' + str(p_index) + '_minion' + str(i) + '_dormant')] = minion.dormant

                # Boolean values
                state[('player' + str(p_index) + '_minion' + str(i) + '_attackable')] = minion.attackable
                state[('player' + str(p_index) + '_minion' + str(i) + '_immune_while_attacking')] = minion.immune_while_attacking
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_attack')] = minion.cant_attack
                state[('player' + str(p_index) + '_minion' + str(i) + '_exhausted')] = minion.exhausted
                state[('player' + str(p_index) + '_minion' + str(i) + '_frozen')] = minion.frozen
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_be_targeted_by_opponents')] = minion.cant_be_targeted_by_opponents
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_be_targeted_by_abilities')] = minion.cant_be_targeted_by_abilities
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_be_targeted_by_hero_powers')] = minion.cant_be_targeted_by_hero_powers
                state[('player' + str(p_index) + '_minion' + str(i) + '_heavily_armored')] = minion.heavily_armored
                state[('player' + str(p_index) + '_minion' + str(i) + '_rush')] = minion.rush
                state[('player' + str(p_index) + '_minion' + str(i) + '_taunt')] = minion.taunt
                state[('player' + str(p_index) + '_minion' + str(i) + '_poisonous')] = minion.poisonous
                state[('player' + str(p_index) + '_minion' + str(i) + '_charge')] = minion.charge
                state[('player' + str(p_index) + '_minion' + str(i) + '_stealthed')] = minion.stealthed
                state[('player' + str(p_index) + '_minion' + str(i) + '_ignore_taunt')] = minion.ignore_taunt
            else:
                state[('player' + str(p_index) + '_minion' + str(i) + '_atk')] = 0
                state[('player' + str(p_index) + '_minion' + str(i) + '_max_health')] = 0
                state[('player' + str(p_index) + '_minion' + str(i) + '_damage')] = 0
                state[('player' + str(p_index) + '_minion' + str(i) + '_incoming_damage_multiplier')] = 0
                state[('player' + str(p_index) + '_minion' + str(i) + '_spellpower')] = 0
                state[('player' + str(p_index) + '_minion' + str(i) + '_max_attacks')] = 0
                state[('player' + str(p_index) + '_minion' + str(i) + '_dormant')] = 0

                # Boolean values
                state[('player' + str(p_index) + '_minion' + str(i) + '_attackable')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_immune_while_attacking')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_attack')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_exhausted')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_frozen')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_be_targeted_by_opponents')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_be_targeted_by_abilities')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_cant_be_targeted_by_hero_powers')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_heavily_armored')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_rush')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_taunt')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_poisonous')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_charge')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_stealthed')] = False
                state[('player' + str(p_index) + '_minion' + str(i) + '_ignore_taunt')] = False

    return state

def weighted_card_choice(source, weights: List[int], card_sets: List[str], count: int):
    """
    Take a list of weights and a list of card pools and produce
    a random weighted sample without replacement.
    len(weights) == len(card_sets) (one weight per card set)
    """

    chosen_cards = []

    # sum all the weights
    cum_weights = []
    totalweight = 0
    for i, w in enumerate(weights):
        totalweight += w * len(card_sets[i])
        cum_weights.append(totalweight)

    # for each card
    for i in range(count):
        # choose a set according to weighting
        chosen_set = bisect(cum_weights, random.random() * totalweight)

        # choose a random card from that set
        chosen_card_index = random.randint(0, len(card_sets[chosen_set]) - 1)

        chosen_cards.append(card_sets[chosen_set].pop(chosen_card_index))
        totalweight -= weights[chosen_set]
        cum_weights[chosen_set:] = [x - weights[chosen_set]
                                    for x in cum_weights[chosen_set:]]

    return [source.controller.card(card, source=source) for card in chosen_cards]


def setup_game():
    from .game import Game
    from .player import Player

    deck1 = random_draft(CardClass.MAGE)
    deck2 = random_draft(CardClass.WARRIOR)
    player1 = Player("Player1", deck1, CardClass.MAGE.default_hero)
    player2 = Player("Player2", deck2, CardClass.WARRIOR.default_hero)

    game = Game(players=(player1, player2))
    game.start()

    return game

def setup_random_game():
    from .game import Game
    from .player import Player

    class1 = random_class()
    class2 = random_class()

    deck1 = random_draft(class1)
    deck2 = random_draft(class2)
    player1 = Player("Player1", deck1, class1.default_hero)
    player2 = Player("Player2", deck2, class2.default_hero)

    game = Game(players=(player1, player2))
    game.start()

    return game


def play_turn(game):
    player = game.current_player

    while True:
        heropower = player.hero.power
        if heropower.is_usable() and random.random() < 0.1:
            if heropower.requires_target():
                heropower.use(target=random.choice(heropower.targets))
            else:
                heropower.use()
            continue

        # iterate over our hand and play whatever is playable
        for card in player.hand:
            if card.is_playable() and random.random() < 0.5:
                target = None
                if card.must_choose_one:
                    card = random.choice(card.choose_cards)
                if card.requires_target():
                    target = random.choice(card.targets)
                #print("Playing %r on %r" % (card, target))
                card.play(target=target)

                if player.choice:
                    choice = random.choice(player.choice.cards)
                    #print("Choosing card %r" % (choice))
                    player.choice.choose(choice)
                continue

        # Randomly attack with whatever can attack
        for character in player.characters:
            if character.can_attack():
                character.attack(random.choice(character.targets))
        break

    game.end_turn()
    return game


def play_full_game():
    game = setup_game()

    for player in game.players:
        #print("Can mulligan %r" % (player.choice.cards))
        mull_count = random.randint(0, len(player.choice.cards))
        cards_to_mulligan = random.sample(player.choice.cards, mull_count)
        player.choice.choose(*cards_to_mulligan)

    while True:
        play_turn(game)

    return game

def play_random_game():
    game = setup_random_game()

    for player in game.players:
        #print("Can mulligan %r" % (player.choice.cards))
        mull_count = random.randint(0, len(player.choice.cards))
        cards_to_mulligan = random.sample(player.choice.cards, mull_count)
        player.choice.choose(*cards_to_mulligan)

    while True:
        play_turn(game)

    return game

