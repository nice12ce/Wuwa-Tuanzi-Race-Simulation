import random
from collections import defaultdict

# ====================== 地图常量 ======================
MAP_SIZE = 32
START_TILE = 1
FINISH_TILE = 32
GREEN_TILES = {3, 11, 16, 23}   # 推进装置
RED_TILES = {10, 28}            # 阻遏装置
RIFT_TILES = {6, 20}            # 裂隙

# ====================== 实体基类 ======================
class Entity:
    def __init__(self, name):
        self.name = name
        self.finished = False
        self.total_progress = 0   # 下半模式累计里程
    def is_tuanzi(self):
        return isinstance(self, Tuanzi)

# ====================== 团子技能基类 ======================
class Tuanzi(Entity):
    def __init__(self, name):
        super().__init__(name)
        self.met_bu = False
        self.activated = False
        self.last_base_roll = None

    def get_base_roll(self, round_num):
        return random.randint(1, 3)

    def get_actual_steps(self, base_roll, global_info=None):
        return base_roll

    def on_move_end(self, race):
        pass

# -------------------- 原有6名选手 --------------------
class QianZhi(Tuanzi):
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
        if r < 0.6:
            return base_roll * 2
        if r < 0.8:
            return 0
        return base_roll

class AiMiSi(Tuanzi):
    def __init__(self, name):
        super().__init__(name)
        self.teleport_used = False
        self.reached_mid = False

    def check_teleport(self, race):
        if self.teleport_used or self.finished:
            return
        tile = race.locate_entity(self)
        if tile is None or tile < 17:
            return
        if not self.reached_mid:
            self.reached_mid = True

        candidates = []
        for t in race.tuanzis:
            if t.finished or t == self:
                continue
            pos = race.locate_entity(t)
            if pos is not None and pos > tile:
                candidates.append((pos, t))
        if not candidates:
            return
        target_tile, target = min(candidates, key=lambda x: x[0])
        race.cell[tile].remove(self)
        race.cell[target_tile].append(self)
        self.teleport_used = True
        if race.verbose:
            print(f"  ⚡ 爱弥斯触发被动！传送至格子{target_tile}，骑在{target.name}头上！")

class ShouAnRen(Tuanzi):
    def get_base_roll(self, round_num):
        return random.choice([2, 3])

class KeLaiTa(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        if random.random() < 0.28:
            return base_roll * 2
        return base_roll

# -------------------- 新增6名选手 --------------------
class Daniya(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        steps = base_roll
        if self.last_base_roll is not None and base_roll == self.last_base_roll:
            steps += 2
        self.last_base_roll = base_roll
        return steps

class Feibi(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        if random.random() < 0.5:
            return base_roll + 1
        return base_roll

class Xigelika(Tuanzi):
    def mark_nearby(self, race):
        if self.finished:
            return
        ranking = race.get_ranking()
        if self not in ranking:
            return
        idx = ranking.index(self)
        targets = []
        for i in range(idx - 1, -1, -1):
            targets.append(ranking[i])
            if len(targets) >= 2:
                break
        race.marked_entities.update(targets)
        if race.verbose and targets:
            print(f"  🎯 西格莉卡标记了: {[t.name for t in targets]}（少前进1格）")

class Feixue(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        steps = base_roll
        if self.met_bu:
            steps += 1
        return steps

class LuHesi(Tuanzi):
    pass

class Katixiya(Tuanzi):
    def get_actual_steps(self, base_roll, global_info=None):
        steps = base_roll
        if self.activated and random.random() < 0.6:
            steps += 2
        return steps

    def on_move_end(self, race):
        if not self.activated and not self.finished:
            if race.is_last_place(self):
                self.activated = True
                if race.verbose:
                    print(f"  🔥 卡提希娅激活翻盘桥段！后续60%概率额外+2")

# ====================== 选手注册表（可扩充至18+） ======================
TUANZI_REGISTRY = {
    "千咲": QianZhi,
    "莫宁": MoNing,
    "琳奈": LinNai,
    "爱弥斯": AiMiSi,
    "守岸人": ShouAnRen,
    "珂莱塔": KeLaiTa,
    "达妮娅": Daniya,
    "菲比": Feibi,
    "西格莉卡": Xigelika,
    "绯雪": Feixue,
    "陆・赫斯": LuHesi,
    "卡提希娅": Katixiya,
}

def create_tuanzi(name):
    if name not in TUANZI_REGISTRY:
        raise ValueError(f"未知团子: {name}，可选: {list(TUANZI_REGISTRY.keys())}")
    return TUANZI_REGISTRY[name](name)

# ====================== 布大王 ======================
class BaDawang(Entity):
    def __init__(self):
        super().__init__("布大王")
        self.pos = FINISH_TILE
        self.active = False

    def get_base_roll(self, round_num):
        return random.randint(1, 6)

    def get_actual_steps(self, base_roll, global_info=None):
        return base_roll

# ====================== 比赛引擎 ======================
class Race:
    def __init__(self, mode='first', tuanzi_names=None, start_cell=None, verbose=False):
        self.mode = mode
        self.verbose = verbose
        self.round = 0
        self.champion = None
        self.marked_entities = set()

        # ----- 参赛名单 -----
        if tuanzi_names is None:
            tuanzi_names = ["千咲", "莫宁", "琳奈", "爱弥斯", "守岸人", "珂莱塔"]
        if len(tuanzi_names) != 6:
            raise ValueError(f"必须恰好6名团子参赛，提供了{len(tuanzi_names)}人")

        self.tuanzis = [create_tuanzi(name) for name in tuanzi_names]
        self.name_to_tuanzi = {t.name: t for t in self.tuanzis}

        self.bu = BaDawang()

        self.cell = {i: [] for i in range(1, MAP_SIZE + 1)}
        if mode == 'first':
            for t in self.tuanzis:
                self.cell[START_TILE].append(t)
            self.bu.active = False
            self.bu.pos = FINISH_TILE
        else:   # mode == 'second'
            if start_cell is None:
                raise ValueError("下半场模式下必须提供 start_cell 参数来指定各格子的起始堆叠")
            self._apply_start_cell(start_cell)

    def _apply_start_cell(self, cell_dict):
        self.cell = {i: [] for i in range(1, MAP_SIZE + 1)}
        for tile, entity_list in cell_dict.items():
            for e_desc in entity_list:
                if isinstance(e_desc, str):
                    if e_desc == "布大王":
                        obj = self.bu
                    else:
                        obj = self.name_to_tuanzi.get(e_desc)
                        if obj is None:
                            raise ValueError(f"start_cell 中的团子 '{e_desc}' 不在参赛名单中")
                else:
                    obj = e_desc
                self.cell[tile].append(obj)
        bu_tile = self.locate_entity(self.bu)
        self.bu.pos = bu_tile if bu_tile is not None else FINISH_TILE
        self.bu.active = False

    def log(self, msg):
        if self.verbose:
            print(msg)

    def locate_entity(self, entity):
        for tile in range(1, MAP_SIZE + 1):
            if entity in self.cell[tile]:
                return tile
        return None

    # -------------------- 移动整格实体的新方法 --------------------
    def _move_all_entities(self, tile, delta):
        """移动该格内所有实体（含布大王），返回是否冲线"""
        entities = self.cell[tile][:]
        self.cell[tile] = []
        tuanzis_in_group = [e for e in entities if e.is_tuanzi()]
        bu_in_group = [e for e in entities if isinstance(e, BaDawang)]

        if self.mode == 'first':
            new_tile = tile + delta
            if new_tile >= FINISH_TILE:
                if self.champion is None and tuanzis_in_group:
                    self.champion = tuanzis_in_group[-1].name
                for t in tuanzis_in_group:
                    t.finished = True
                # 布大王留在终点附近，放回32底部
                for bu in bu_in_group:
                    self.cell[FINISH_TILE].insert(0, bu)
                    bu.pos = FINISH_TILE
                return True
            new_tile = max(1, new_tile)
        else:  # second
            for t in tuanzis_in_group:
                if delta > 0:
                    t.total_progress += delta

            win_flag = False
            for t in tuanzis_in_group:
                if not t.finished:
                    old_progress = t.total_progress - delta
                    if old_progress < 32 and t.total_progress >= 32:
                        win_flag = True
                        break

            raw_new = tile + delta
            if raw_new >= FINISH_TILE + 1:
                new_tile = (raw_new - 1) % MAP_SIZE + 1
            else:
                new_tile = raw_new

            if win_flag:
                if self.champion is None and tuanzis_in_group:
                    self.champion = tuanzis_in_group[-1].name
                for t in tuanzis_in_group:
                    t.finished = True
                for bu in bu_in_group:
                    self.cell[new_tile].insert(0, bu)
                    bu.pos = new_tile
                return True

        # 未冲线：所有实体放入新格
        self.cell[new_tile].extend(entities)
        for bu in bu_in_group:
            bu.pos = new_tile
        return False

    # -------------------- 移动核心（原团子组） --------------------
    def move_group(self, group, from_tile, delta):
        for e in group:
            self.cell[from_tile].remove(e)

        if self.mode == 'first':
            new = from_tile + delta
            if new >= FINISH_TILE:
                if self.champion is None:
                    top_tuanzi = [e for e in group if e.is_tuanzi()]
                    if top_tuanzi:
                        self.champion = top_tuanzi[-1].name
                for e in group:
                    if e.is_tuanzi():
                        e.finished = True
                return True
            new = max(1, new)
            self.cell[new].extend(group)
            return False
        else:
            if delta > 0:
                for e in group:
                    if e.is_tuanzi():
                        e.total_progress += delta

            win_flag = False
            for e in group:
                if e.is_tuanzi() and not e.finished:
                    old_progress = e.total_progress - delta
                    if old_progress < 32 and e.total_progress >= 32:
                        win_flag = True
                        break

            raw_new = from_tile + delta
            if raw_new >= FINISH_TILE + 1:
                new_tile = (raw_new - 1) % MAP_SIZE + 1
            else:
                new_tile = raw_new

            if win_flag:
                if self.champion is None:
                    top_tuanzi = [e for e in group if e.is_tuanzi()]
                    if top_tuanzi:
                        self.champion = top_tuanzi[-1].name
                for e in group:
                    if e.is_tuanzi():
                        e.finished = True
                return True

            self.cell[new_tile].extend(group)
            return False

    def move_single_entity(self, entity, delta, trigger_effects=False):
        tile = self.locate_entity(entity)
        if tile is None or entity.finished:
            return
        self.cell[tile].remove(entity)

        if self.mode == 'first':
            new_tile = tile + delta
            if new_tile >= FINISH_TILE:
                if self.champion is None and entity.is_tuanzi():
                    self.champion = entity.name
                entity.finished = True
                return
            new_tile = max(1, new_tile)
            self.cell[new_tile].append(entity)
        else:
            if delta > 0:
                entity.total_progress += delta
            old_progress = entity.total_progress - delta
            if old_progress < 32 and entity.total_progress >= 32 and delta > 0:
                if self.champion is None and entity.is_tuanzi():
                    self.champion = entity.name
                entity.finished = True
                return
            raw_new = tile + delta
            if raw_new >= FINISH_TILE + 1:
                new_tile = (raw_new - 1) % MAP_SIZE + 1
            else:
                new_tile = raw_new
            self.cell[new_tile].append(entity)

        if entity.is_tuanzi() and not entity.finished:
            entity.on_move_end(self)
            if isinstance(entity, Feixue) and not entity.met_bu:
                if self.locate_entity(entity) == self.locate_entity(self.bu):
                    entity.met_bu = True
                    if self.verbose:
                        print(f"  ✨ 绯雪与布大王相遇！buff激活")

    # -------------------- 格子效果（已修改红绿部分） --------------------
    def apply_tile_effect(self, tile):
        if tile in RIFT_TILES:
            normal = [e for e in self.cell[tile] if e.is_tuanzi()]
            if normal:
                random.shuffle(normal)
                others = [e for e in self.cell[tile] if not e.is_tuanzi()]
                self.cell[tile] = others + normal
                self.log(f"  🌀 裂隙打乱了格子{tile}的堆叠！")
            return

        if tile in GREEN_TILES or tile in RED_TILES:
            delta = 1 if tile in GREEN_TILES else -1
            occupants = self.cell[tile][:]
            has_bu = self.bu in occupants

            if has_bu:
                self.log(f"  {'🟢' if delta == 1 else '🔴'} 格子{tile}效果！全组（含布大王）{'前进' if delta == 1 else '后退'}1格。")
                finished = self._move_all_entities(tile, delta)
                if finished:
                    return
                # 陆・赫斯额外移动（仅对团子）
                for e in occupants:
                    if isinstance(e, LuHesi) and not e.finished:
                        extra = 3 if tile in GREEN_TILES else -1
                        if self.verbose:
                            print(f"    🍬 陆・赫斯额外{'前进' if extra > 0 else '后退'}{abs(extra)}格！")
                        self.move_single_entity(e, extra, trigger_effects=False)
            else:
                normal = [e for e in occupants if e.is_tuanzi()]
                if not normal:
                    return
                self.log(f"  {'🟢' if delta == 1 else '🔴'} 格子{tile}效果！全组{'前进' if delta == 1 else '后退'}1格。")
                self.move_group(normal, tile, delta)
                for e in normal:
                    if isinstance(e, LuHesi) and not e.finished:
                        extra = 3 if tile in GREEN_TILES else -1
                        if self.verbose:
                            print(f"    🍬 陆・赫斯额外{'前进' if extra > 0 else '后退'}{abs(extra)}格！")
                        self.move_single_entity(e, extra, trigger_effects=False)

    # -------------------- 排名与最后一名 --------------------
    def get_ranking(self):
        entities = [t for t in self.tuanzis if not t.finished]
        if self.mode == 'first':
            def key(e):
                tile = self.locate_entity(e)
                if tile is None: return (0, 0)
                idx = self.cell[tile].index(e) if e in self.cell[tile] else 0
                return (tile, idx)
            entities.sort(key=key, reverse=True)
        else:
            def key(e):
                tile = self.locate_entity(e) or 0
                return (e.total_progress, tile)
            entities.sort(key=key, reverse=True)
        return entities

    def is_last_place(self, entity):
        ranking = self.get_ranking()
        if not ranking or entity not in ranking:
            return False
        if self.mode == 'first':
            last_key = (self.locate_entity(ranking[-1]), self.cell[self.locate_entity(ranking[-1])].index(ranking[-1]))
            entity_key = (self.locate_entity(entity), self.cell[self.locate_entity(entity)].index(entity))
        else:
            last_key = (ranking[-1].total_progress, self.locate_entity(ranking[-1]))
            entity_key = (entity.total_progress, self.locate_entity(entity))
        return entity_key == last_key

    # -------------------- 布大王传送 --------------------
    def ba_teleport(self):
        if not self.bu.active or self.champion:
            return
        unfinished_tiles = []
        for t in self.tuanzis:
            if not t.finished:
                tile = self.locate_entity(t)
                if tile is not None:
                    unfinished_tiles.append(tile)
        if not unfinished_tiles:
            return
        bu_tile = self.locate_entity(self.bu) if self.mode == 'second' else self.bu.pos
        if bu_tile < min(unfinished_tiles):
            if self.mode == 'second':
                self.cell[bu_tile].remove(self.bu)
                self.cell[FINISH_TILE].insert(0, self.bu)
            self.bu.pos = FINISH_TILE
            self.log(f"  ⚡ 布大王跑到了所有人后面，传送回32！")

    # -------------------- 步数计算 --------------------
    def step_order(self, participants):
        base_rolls = {}
        for p in participants:
            if p.is_tuanzi():
                base_rolls[p] = p.get_base_roll(self.round)
            else:
                base_rolls[p] = p.get_base_roll(self.round)

        self.marked_entities.clear()
        for p in participants:
            if isinstance(p, Xigelika) and not p.finished:
                p.mark_nearby(self)

        all_base = list(base_rolls.values())
        global_info = {"all_base_rolls": all_base, "marked": self.marked_entities}

        actual_steps = {}
        for p in participants:
            steps = p.get_actual_steps(base_rolls[p], global_info)
            if p in self.marked_entities and steps > 1:
                steps -= 1
                if self.verbose:
                    print(f"  ↓ {p.name}被标记，步数减至{steps}")
            actual_steps[p] = steps
        return actual_steps

    # -------------------- 回合流程 --------------------
    def process_turn(self, participants, actual_steps):
        for entity in participants:
            if self.champion:
                break

            if entity.is_tuanzi():
                if entity.finished:
                    continue
                tile = self.locate_entity(entity)
                if tile is None:
                    self.log(f"  ⚠️ {entity.name} 已失踪，跳过")
                    continue

                stack = self.cell[tile]
                try:
                    idx = stack.index(entity)
                except ValueError:
                    continue
                group = [e for e in stack[idx:] if e.is_tuanzi()]
                steps = actual_steps[entity]
                self.log(f"  {entity.name} 从格子{tile}，步数={steps}，带着{[p.name for p in group]}前进。")

                from_tile = tile
                finished_now = self.move_group(group, from_tile, steps)
                if finished_now:
                    self.log(f"    🏁 该组冲线！")
                    continue

                new_tile = self.locate_entity(entity)
                if new_tile is not None:
                    self.apply_tile_effect(new_tile)

                for ent in group:
                    if not ent.finished:
                        ent.on_move_end(self)
                        if isinstance(ent, Feixue) and not ent.met_bu:
                            if self.locate_entity(ent) == self.locate_entity(self.bu):
                                ent.met_bu = True
                                if self.verbose:
                                    print(f"  ✨ 绯雪与布大王相遇！buff激活")

            else:  # 布大王行动
                if not self.bu.active:
                    continue
                if self.mode == 'first':
                    tile = self.bu.pos
                    taken = self.cell[tile][:]
                    self.cell[tile] = []
                else:
                    tile = self.locate_entity(self.bu)
                    if tile is None:
                        continue
                    taken = self.cell[tile][:]
                    self.cell[tile] = []

                steps = actual_steps[entity]
                new_pos = tile - steps
                if new_pos < 1:
                    new_pos = 1

                self.bu.pos = new_pos
                if self.mode == 'first':
                    self.cell[new_pos] = self.cell[new_pos] + taken
                else:
                    self.cell[new_pos].extend(taken)

                self.log(f"  布大王 从格子{tile}，逆行步数={steps}，停在格子{new_pos}，带走{[p.name for p in taken]}")
                self.apply_tile_effect(new_pos)

                for ent in taken:
                    if ent.is_tuanzi() and not ent.finished:
                        ent.on_move_end(self)
                        if isinstance(ent, Feixue) and not ent.met_bu:
                            if self.locate_entity(ent) == self.locate_entity(self.bu):
                                ent.met_bu = True
                                if self.verbose:
                                    print(f"  ✨ 绯雪与布大王相遇！buff激活")

        for t in self.tuanzis:
            if isinstance(t, AiMiSi):
                t.check_teleport(self)

    # -------------------- 比赛主循环 --------------------
    def run(self):
        if self.mode == 'first':
            return self._run_first()
        else:
            return self._run_second()

    def _run_first(self):
        first_order = self.tuanzis[:]
        random.shuffle(first_order)
        self.cell[START_TILE] = list(reversed(first_order))
        self.round = 1
        self.log(f"第1回合行动顺序：{' → '.join(t.name for t in first_order)}")
        self.log(f"起点堆叠（底→顶）：{' → '.join(t.name for t in self.cell[START_TILE])}")
        actual_steps = self.step_order(first_order)
        self.process_turn(first_order, actual_steps)
        if self.champion:
            return self.champion

        self.round = 2
        while self.champion is None:
            if all(t.finished for t in self.tuanzis):
                if self.champion is None:
                    self.champion = self.tuanzis[0].name
                break

            participants = [t for t in self.tuanzis if not t.finished]
            if self.round >= 3 and not self.bu.active:
                self.bu.active = True
                self.log(f"第{self.round}回合 布大王加入！")
            if self.bu.active:
                participants.append(self.bu)

            random.shuffle(participants)
            actual_steps = self.step_order(participants)
            self.log(f"\n=== 第{self.round}回合 行动顺序：{' → '.join(p.name for p in participants)} ===")
            self.process_turn(participants, actual_steps)
            self.ba_teleport()
            self.round += 1

        return self.champion

    def _run_second(self):
        self.round = 1
        participants = self.tuanzis[:]
        random.shuffle(participants)
        self.log(f"第1回合行动顺序：{' → '.join(t.name for t in participants)}")
        self.log("初始堆叠：")
        for tile in range(1, MAP_SIZE+1):
            if self.cell[tile]:
                names = [e.name for e in self.cell[tile]]
                self.log(f"  格子{tile}: {' → '.join(names)}")
        actual_steps = self.step_order(participants)
        self.process_turn(participants, actual_steps)
        if self.champion:
            return self.champion

        self.round = 2
        while self.champion is None:
            if all(t.finished for t in self.tuanzis):
                if self.champion is None:
                    self.champion = self.tuanzis[0].name
                break

            participants = [t for t in self.tuanzis if not t.finished]
            if self.round >= 3 and not self.bu.active:
                self.bu.active = True
                self.log(f"第{self.round}回合 布大王加入！")
            if self.bu.active:
                participants.append(self.bu)

            random.shuffle(participants)
            actual_steps = self.step_order(participants)
            self.log(f"\n=== 第{self.round}回合 行动顺序：{' → '.join(p.name for p in participants)} ===")
            self.process_turn(participants, actual_steps)
            self.ba_teleport()
            self.round += 1

        return self.champion

# ====================== 便捷模拟控制 ======================
def run_simulation(mode, num_simulations=1000, tuanzi_names=None, start_cell=None):
    wins = defaultdict(int)
    for _ in range(num_simulations):
        r = Race(mode=mode, tuanzi_names=tuanzi_names, start_cell=start_cell, verbose=False)
        champion = r.run()
        wins[champion] += 1
    total = sum(wins.values())
    print(f"\n===== {mode}半场 {num_simulations}次模拟结果 =====")
    for name, w in sorted(wins.items(), key=lambda x: x[1], reverse=True):
        print(f"{name}: {w}胜, 胜率 {w/total*100:.1f}%")

# ====================== 测试入口 ======================
if __name__ == "__main__":
    MODE = 'second'          # 选择 'first' 或 'second'
    SIM_COUNT = 100000
    VERBOSE_SINGLE = True

    my_tuanzi_names = ["千咲", "莫宁", "琳奈", "爱弥斯", "守岸人", "珂莱塔"]

    custom_start = {
         32: ["布大王", "珂莱塔"],
         30: ["琳奈","千咲"],
         29: ["爱弥斯","莫宁"],
         28: ["守岸人"],
    }

    print(f"开始模拟：{MODE}半场，次数 {SIM_COUNT}，参赛选手 {my_tuanzi_names}")
    run_simulation(MODE, SIM_COUNT, my_tuanzi_names, custom_start)

    if VERBOSE_SINGLE:
        print("\n===== 单局详细演示 =====")
        r = Race(mode=MODE, tuanzi_names=my_tuanzi_names, start_cell=custom_start, verbose=True)
        champ = r.run()
        print(f"冠军：{champ}")