import random
from core import Tuanzi, GREEN_TILES

class QianXiao(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        if global_info and "all_base_rolls" in global_info:
            if base_roll == min(global_info["all_base_rolls"]):
                return base_roll + 2
        return base_roll

class MoNing(Tuanzi):
    def get_base_roll(self, round_num):
        return 3 - (round_num - 1) % 3

class LinNai(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        r = random.random()
        if r < 0.6: return base_roll * 2
        if r < 0.8: return 0
        return base_roll

class AiMiSi(Tuanzi):
    def __init__(self, name):
        super().__init__(name)
        self.teleport_used = False
        self.reached_mid = False

    def on_move_end(self, race):
        if self.teleport_used or self.finished: return
        tile = race.locate_entity(self)
        if tile is None or tile < 17: return
        if not self.reached_mid: self.reached_mid = True
        candidates = []
        for t in race.tuanzis:
            if t.finished or t == self: continue
            pos = race.locate_entity(t)
            if pos is not None and pos > tile: candidates.append((pos, t))
        if not candidates: return
        target_tile, target = min(candidates, key=lambda x: x[0])
        race.cell[tile].remove(self)
        race.cell[target_tile].append(self)
        self.teleport_used = True
        if race.verbose: print(f"  ⚡ 爱弥斯传送至{target_tile}，骑在{target.name}头上！")

class ShouAnRen(Tuanzi):
    def get_base_roll(self, round_num): return random.choice([2, 3])

class KeLaiTa(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        if random.random() < 0.28: return base_roll * 2
        return base_roll

class Daniya(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        steps = base_roll
        if self.last_base_roll is not None and base_roll == self.last_base_roll: steps += 2
        self.last_base_roll = base_roll
        return steps

class Feibi(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        return base_roll + 1 if random.random() < 0.5 else base_roll

class Xigelika(Tuanzi):
    def mark_nearby(self, race):
        if self.finished: return
        ranking = race.get_ranking()
        if self not in ranking: return
        idx = ranking.index(self)
        targets = []
        for i in range(idx-1, -1, -1):
            targets.append(ranking[i])
            if len(targets) >= 2: break
        race.marked_entities.update(targets)
        if race.verbose and targets: print(f"  🎯 西格莉卡标记了: {[t.name for t in targets]}")

class Feixue(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        return base_roll + 1 if self.met_bu else base_roll

    def on_move_end(self, race):
        if not self.met_bu and not self.finished:
            if race.locate_entity(self) == race.locate_entity(race.bu):
                self.met_bu = True
                if race.verbose: print("  ✨ 绯雪与布大王相遇！buff激活")

class LuHesi(Tuanzi):
    def on_tile_effect(self, race, tile, delta, has_bu):
        if self.finished: return
        extra = 3 if tile in GREEN_TILES else -1
        if race.verbose: print(f"    🍬 陆·赫斯额外{'前进' if extra>0 else '后退'}{abs(extra)}格！")
        race.move_single_entity(self, extra)

class Katixiya(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        steps = base_roll
        if self.activated and random.random() < 0.6: steps += 2
        return steps
    def on_move_end(self, race):
        if not self.activated and not self.finished and race.is_last_place(self):
            self.activated = True
            if race.verbose: print("  🔥 卡提希娅激活翻盘桥段！")

class Aogusita(Tuanzi):
    """奥古斯塔：总督权柄"""
    FORCE_PRIORITY = 1          # 下回合强制最后的优先级（越大越晚）→可自行调整

    def __init__(self, name):
        super().__init__(name)
        self.skip_next = False

    def pre_turn_effect(self, race):
        if self.skip_next:
            self.skip_next = False
            return
        tile = race.locate_entity(self)
        if tile is None or self.finished: return
        if race.cell[tile] and race.cell[tile][-1] == self:
            race.skip_entities.append(self)
            race.force_last_next.append((self, self.FORCE_PRIORITY))
            self.skip_next = True
            if race.verbose: print("  👑 奥古斯塔发动总督权柄：本回合不行动，下回合最后")

class Younuo(Tuanzi):
    """尤诺：锚定命途"""
    def __init__(self, name):
        super().__init__(name)
        self.used = False

    def on_move_end(self, race):
        if self.used or self.finished: return
        passed = (race.locate_entity(self) and race.locate_entity(self) >= 17) if race.mode == 'first' else self.total_progress >= 17
        if not passed: return
        ranking = race.get_ranking()
        if self not in ranking: return
        idx = ranking.index(self)
        targets = [ranking[i] for i in (idx-1, idx+1) if 0 <= i < len(ranking)]
        if not targets: return
        my_tile = race.locate_entity(self)
        if my_tile is None: return
        targets_sorted = sorted(targets, key=lambda t: race._entity_sort_key(t), reverse=True)
        for t in targets_sorted:
            tile = race.locate_entity(t)
            if tile is not None and t in race.cell[tile]:
                race.cell[tile].remove(t)
                race.cell[my_tile].append(t)
        self.used = True
        if race.verbose: print(f"  🔗 尤诺锚定命途！将 {[t.name for t in targets_sorted]} 拉至身边")

class Fuluoluo(Tuanzi):
    """弗洛洛：优雅阴谋"""
    def pre_turn_effect(self, race):
        if self.finished: return
        tile = race.locate_entity(self)
        if tile is not None and race.cell[tile] and race.cell[tile][0] == self:
            race.extra_steps[self] = race.extra_steps.get(self, 0) + 3
            if race.verbose: print("  🌹 弗洛洛处于最底层，+3步")

class Changli(Tuanzi):
    """长离：谋而后定"""
    FORCE_PRIORITY = 2          # 优先级高于奥古斯塔，更晚行动

    def end_turn_effect(self, race):
        if self.finished: return
        tile = race.locate_entity(self)
        if tile is None: return
        if race.cell[tile] and race.cell[tile][0] != self:     # 不是最底层
            if random.random() < 0.65:
                race.force_last_next.append((self, self.FORCE_PRIORITY))
                if race.verbose: print("  🌿 长离谋而后定：下回合最后行动")

class Jinxi(Tuanzi):
    """今汐：令尹之名"""
    def before_move_effect(self, race):
        if self.finished: return
        tile = race.locate_entity(self)
        if tile is None: return
        stack = race.cell[tile]
        if len(stack) <= 1 or stack[-1] == self: return
        if random.random() < 0.4:
            stack.remove(self)
            stack.append(self)
            if race.verbose: print(f"  🦅 今汐跃至格子{tile}顶部！")

class Kakaluo(Tuanzi):
    """卡卡罗：如影随形"""
    def before_move_effect(self, race):
        if self.finished: return
        if race.is_last_place(self):
            race.extra_steps[self] = race.extra_steps.get(self, 0) + 3
            if race.verbose: print("  🏃 卡卡罗最后一名，+3步")

TUANZI_REGISTRY = {
    "千咲": QianXiao, "莫宁": MoNing, "琳奈": LinNai, "爱弥斯": AiMiSi,
    "守岸人": ShouAnRen, "珂莱塔": KeLaiTa, "达妮娅": Daniya, "菲比": Feibi,
    "西格莉卡": Xigelika, "绯雪": Feixue, "陆·赫斯": LuHesi, "卡提希娅": Katixiya,
    "奥古斯塔": Aogusita, "尤诺": Younuo, "弗洛洛": Fuluoluo,
    "长离": Changli, "今汐": Jinxi, "卡卡罗": Kakaluo,
}

def create_tuanzi(name):
    if name not in TUANZI_REGISTRY:
        raise ValueError(f"未知团子: {name}")
    return TUANZI_REGISTRY[name](name)