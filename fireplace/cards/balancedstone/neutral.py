from ..utils import *


##
# Minions

class BS_001:
    """Flame Lance"""
    requirements = {PlayReq.REQ_MINION_TARGET: 0, PlayReq.REQ_TARGET_TO_PLAY: 0}
    play = Hit(TARGET, 8)

class BS_002:
    """Armor Vendor"""
    play = GainArmor(ALL_HEROES, 4)
