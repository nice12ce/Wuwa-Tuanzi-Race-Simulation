import random

# ====================== 地图常量 ======================
MAP_SIZE = 32
START_TILE = 1
FINISH_TILE = 32
GREEN_TILES = {3, 11, 16, 23}
RED_TILES = {10, 28}
RIFT_TILES = {6, 20}


# ====================== 实体基类 ======================
class Entity:
    def __init__(self, name):
        self.name = name
        self.finished = False
        self.total_progress = 0

    def is_tuanzi(self):
        return isinstance(self, Tuanzi)


# ====================== 团子技能基类（多态钩子） ======================
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

    # ---------- 可重写的钩子 ----------
    def on_move_end(self, race):
        """移动完全结束后调用（相遇、传送等）"""
        pass

    def pre_turn_effect(self, race):
        """回合开始前调用（奥古斯塔、弗洛洛等）"""
        pass

    def before_move_effect(self, race):
        """自身移动前调用（今汐、卡卡罗等）"""
        pass

    def end_turn_effect(self, race):
        """回合结束时调用（长离等）"""
        pass

    def mark_nearby(self, race):
        """标记周围团子（西格莉卡重写）"""
        pass

    def on_tile_effect(self, race, tile, delta, has_bu):
        """格子效果触发后的个人动作（陆·赫斯重写）"""
        pass


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
    def __init__(self, mode='first', tuanzis=None, start_cell=None, verbose=None):
        self.mode = mode
        self.verbose = verbose
        self.round = 0
        self.champion = None
        self.marked_entities = set()
        self.max_rounds = 200

        if tuanzis is None or len(tuanzis) != 6:
            raise ValueError("必须提供恰好6个团子对象")

        self.tuanzis = tuanzis
        self.name_to_tuanzi = {t.name: t for t in tuanzis}
        self.bu = BaDawang()
        self.cell = {i: [] for i in range(1, MAP_SIZE + 1)}

        if mode == 'first':
            for t in self.tuanzis:
                self.cell[START_TILE].append(t)
            self.bu.active = False
            self.bu.pos = FINISH_TILE
        else:  # second
            if start_cell is None:
                raise ValueError("下半场必须提供 start_cell")
            self._apply_start_cell(start_cell)

        # 回合级别状态
        self.skip_entities = []  # 本回合不行动的实体
        self.extra_steps = {}  # 临时额外步数 {entity: bonus}
        self.force_last_next = []  # 下回合强制最后的列表 [(entity, priority)]

    def _apply_start_cell(self, cell_dict):
        self.cell = {i: [] for i in range(1, MAP_SIZE + 1)}
        for tile, entity_list in cell_dict.items():
            for e_desc in entity_list:
                if isinstance(e_desc, str):
                    obj = self.bu if e_desc == "布大王" else self.name_to_tuanzi.get(e_desc)
                    if obj is None:
                        raise ValueError(f"未知实体: {e_desc}")
                else:
                    obj = e_desc
                self.cell[tile].append(obj)
        # 修复：优先从cell中获取布大王位置，确保pos与实际一致
        bu_tile = self.locate_entity(self.bu)
        self.bu.pos = bu_tile if bu_tile is not None else FINISH_TILE
        self.bu.active = False
        # 补充：如果布大王不在cell中，强制加入终点格
        if bu_tile is None:
            self.cell[FINISH_TILE].insert(0, self.bu)
            self.bu.pos = FINISH_TILE

    def log(self, msg):
        if self.verbose:
            print(msg)

    def locate_entity(self, entity):
        for tile in range(1, MAP_SIZE + 1):
            if entity in self.cell[tile]:
                return tile
        return None

    def _entity_sort_key(self, entity):
        """用于排名比较的键"""
        if self.mode == 'first':
            tile = self.locate_entity(entity)
            if tile is None: return (0, 0)
            idx = self.cell[tile].index(entity) if entity in self.cell[tile] else 0
            return (tile, idx)
        else:
            tile = self.locate_entity(entity) or 0
            return (entity.total_progress, tile)

    # ---------- 移动核心（初版逻辑，后退不减少里程） ----------
    def move_group(self, group, from_tile, delta):
        for e in group:
            self.cell[from_tile].remove(e)

        if self.mode == 'first':
            new = from_tile + delta
            if new >= FINISH_TILE:
                if self.champion is None:
                    top = [e for e in group if e.is_tuanzi()]
                    if top: self.champion = top[-1].name
                for e in group:
                    if e.is_tuanzi(): e.finished = True
                return True
            new = max(1, new)
            self.cell[new].extend(group)
            return False
        else:
            # 修复：处理后退时的进度下限，避免负进度
            if delta > 0:
                for e in group:
                    if e.is_tuanzi(): e.total_progress += delta
            elif delta < 0:
                for e in group:
                    if e.is_tuanzi():
                        e.total_progress = max(0, e.total_progress + delta)

            win_flag = False
            for e in group:
                if e.is_tuanzi() and not e.finished:
                    old_progress = e.total_progress - delta
                    if old_progress < 32 and e.total_progress >= 32:
                        win_flag = True
                        break

            raw_new = from_tile + delta
            new_tile = (raw_new - 1) % MAP_SIZE + 1 if raw_new >= FINISH_TILE + 1 else raw_new

            if win_flag:
                if self.champion is None:
                    top = [e for e in group if e.is_tuanzi()]
                    if top: self.champion = top[-1].name
                for e in group:
                    if e.is_tuanzi(): e.finished = True
                return True

            self.cell[new_tile].extend(group)
            return False

    def move_single_entity(self, entity, delta, trigger_effects=False):
        tile = self.locate_entity(entity)
        if tile is None or entity.finished: return
        self.cell[tile].remove(entity)

        if self.mode == 'first':
            new_tile = tile + delta
            if new_tile >= FINISH_TILE:
                if self.champion is None and entity.is_tuanzi(): self.champion = entity.name
                entity.finished = True
                return
            new_tile = max(1, new_tile)
            self.cell[new_tile].append(entity)
        else:
            # 修复：处理后退时的进度下限，避免负进度
            if delta > 0:
                entity.total_progress += delta
            elif delta < 0:
                entity.total_progress = max(0, entity.total_progress + delta)

            old_progress = entity.total_progress - delta
            if old_progress < 32 and entity.total_progress >= 32:
                if self.champion is None and entity.is_tuanzi(): self.champion = entity.name
                entity.finished = True
                return
            raw_new = tile + delta
            new_tile = (raw_new - 1) % MAP_SIZE + 1 if raw_new >= FINISH_TILE + 1 else raw_new
            self.cell[new_tile].append(entity)

        if entity.is_tuanzi() and not entity.finished:
            entity.on_move_end(self)

    # ---------- 格子效果 ----------
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
                self.log(
                    f"  {'🟢' if delta == 1 else '🔴'} 格子{tile}效果！全组（含布大王）{'前进' if delta == 1 else '后退'}1格。")
                self._move_all_entities(tile, delta)
                # 触发后续个人效果（陆·赫斯等）
                for e in occupants:
                    if e.is_tuanzi() and not e.finished:
                        e.on_tile_effect(self, tile, delta, True)
            else:
                normal = [e for e in occupants if e.is_tuanzi()]
                if not normal: return
                self.log(f"  {'🟢' if delta == 1 else '🔴'} 格子{tile}效果！全组{'前进' if delta == 1 else '后退'}1格。")
                self.move_group(normal, tile, delta)
                for e in normal:
                    if e.is_tuanzi() and not e.finished:
                        e.on_tile_effect(self, tile, delta, False)

    def _move_all_entities(self, tile, delta):
        """移动整格（含布大王）"""
        entities = self.cell[tile][:]
        self.cell[tile] = []
        tuanzis = [e for e in entities if e.is_tuanzi()]
        bus = [e for e in entities if isinstance(e, BaDawang)]

        if self.mode == 'first':
            new = tile + delta
            if new >= FINISH_TILE:
                if self.champion is None and tuanzis: self.champion = tuanzis[-1].name
                for t in tuanzis: t.finished = True
                for bu in bus:
                    self.cell[FINISH_TILE].insert(0, bu)
                    bu.pos = FINISH_TILE
                return
            new = max(1, new)
        else:
            # 修复：处理后退时的进度下限
            if delta > 0:
                for t in tuanzis:
                    t.total_progress += delta
            elif delta < 0:
                for t in tuanzis:
                    t.total_progress = max(0, t.total_progress + delta)

            win_flag = False
            for t in tuanzis:
                if not t.finished:
                    old_progress = t.total_progress - delta
                    if old_progress < 32 and t.total_progress >= 32: win_flag = True; break

            raw_new = tile + delta
            new_tile = (raw_new - 1) % MAP_SIZE + 1 if raw_new >= FINISH_TILE + 1 else raw_new

            if win_flag:
                if self.champion is None and tuanzis: self.champion = tuanzis[-1].name
                for t in tuanzis: t.finished = True
                for bu in bus:
                    self.cell[new_tile].insert(0, bu)
                    bu.pos = new_tile
                return
            new = new_tile

        self.cell[new].extend(entities)
        for bu in bus:
            bu.pos = new

    # ---------- 排名 ----------
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
            entities.sort(key=lambda e: (e.total_progress, self.locate_entity(e) or 0), reverse=True)
        return entities

    def is_last_place(self, entity):
        ranking = self.get_ranking()
        if not ranking or entity not in ranking: return False
        if self.mode == 'first':
            last = ranking[-1];
            last_tile = self.locate_entity(last)
            ent_tile = self.locate_entity(entity)
            if not last_tile or not ent_tile: return False
            return last_tile == ent_tile and self.cell[ent_tile].index(entity) == self.cell[last_tile].index(last)
        else:
            last = ranking[-1]
            return (entity.total_progress, self.locate_entity(entity)) == (
            last.total_progress, self.locate_entity(last))

    # ---------- 布大王传送 ----------
    def ba_teleport(self):
        if not self.bu.active or self.champion: return
        unfinished = [self.locate_entity(t) for t in self.tuanzis if
                      not t.finished and self.locate_entity(t) is not None]
        if not unfinished: return
        # 修复：优先获取实际位置，再用pos
        bu_tile = self.locate_entity(self.bu) or self.bu.pos
        if bu_tile and bu_tile < min(unfinished):
            if self.mode == 'second' and self.bu in self.cell.get(bu_tile, []):
                self.cell[bu_tile].remove(self.bu)
                self.cell[FINISH_TILE].insert(0, self.bu)
            self.bu.pos = FINISH_TILE
            self.log(f"  ⚡ 布大王传送回32！")

    # ---------- 步数计算 ----------
    def step_order(self, participants):
        base_rolls = {p: p.get_base_roll(self.round) for p in participants}
        self.marked_entities.clear()
        for p in participants:
            if p.is_tuanzi() and not p.finished:
                p.mark_nearby(self)  # 多态

        global_info = {"all_base_rolls": list(base_rolls.values()), "marked": self.marked_entities}
        actual_steps = {}
        for p, roll in base_rolls.items():
            steps = p.get_actual_steps(roll, global_info)
            if p in self.marked_entities and steps > 1:
                steps -= 1
                if self.verbose: print(f"  ↓ {p.name}被标记，步数减至{steps}")
            actual_steps[p] = steps
        return actual_steps

    # ---------- 布大王逐步后退（每格沉底，不触发格子效果） ----------
    # ---------- 布大王逐步后退（每格沉底+携带团子，不触发格子效果） ----------
    def _bu_step_move(self, steps):
        """
        严格遵循规则：
        1. 每移动1格 → 布大王沉底 + 携带当前格所有团子继续走
        2. 经过的所有格子 → 不触发任何地形效果
        3. 仅最终停留格 → 由外部触发效果
        返回最终格号
        """
        # 防卡死：布大王位置丢失，强制重置到终点
        start_tile = self.locate_entity(self.bu)
        if start_tile is None:
            self.log(f"  ⚠️ 布大王位置丢失，重置到32格")
            self.cell[FINISH_TILE].insert(0, self.bu)
            self.bu.pos = FINISH_TILE
            return FINISH_TILE

        # 第一步：初始格子处理 → 布大王沉底，携带当前格所有实体
        current_entities = self.cell[start_tile].copy()
        self.cell[start_tile] = []  # 清空原格子
        # 沉底规则：布大王在最下方，后面跟着所有携带的实体
        current_entities = [self.bu] + [e for e in current_entities if e != self.bu]
        current_tile = start_tile

        # 逐格后退移动（每一步都执行沉底+携带，不触发效果）
        for _ in range(steps):
            next_tile = max(1, current_tile - 1)
            # 边界保护：已到起点1格，无法继续后退，终止移动
            if next_tile == current_tile:
                break

            # 离开当前格，准备进入下一格
            self.cell[current_tile] = []

            # 进入新格子 → 合并新格子的实体 + 布大王再次沉底
            target_entities = self.cell[next_tile].copy()
            self.cell[next_tile] = []
            # 核心规则：布大王永远沉底，携带所有遇到的团子
            carried_entities = current_entities + target_entities
            # 去重+重新排序：布大王在最下方
            unique_carried = []
            for e in carried_entities:
                if e not in unique_carried:
                    unique_carried.append(e)
            current_entities = [self.bu] + [e for e in unique_carried if e != self.bu]

            # 放入新格子
            self.cell[next_tile] = current_entities
            current_tile = next_tile

            if self.verbose:
                names = [e.name for e in current_entities]
                self.log(f"    🐾 布大王经过格子{current_tile}，堆叠：{' → '.join(names)}")

        # 最终位置同步 + 日志输出
        self.bu.pos = current_tile
        if self.verbose:
            final_names = [e.name for e in self.cell[current_tile]]
            self.log(f"  布大王停留格子{current_tile}，最终堆叠：{' → '.join(final_names)}")

        return current_tile

    # ---------- 回合流程 ----------
    def process_turn(self, participants, actual_steps):
        for entity in participants:
            if self.champion: break
            if entity.is_tuanzi():
                if entity.finished: continue
                self._apply_before_move(entity)
                tile = self.locate_entity(entity)
                if tile is None: continue
                stack = self.cell[tile]
                idx = stack.index(entity)
                group = [e for e in stack[idx:] if e.is_tuanzi()]
                steps = actual_steps[entity]
                if entity in self.extra_steps: steps += self.extra_steps[entity]
                self.log(f"  {entity.name} 从格子{tile}，步数={steps}，带着{[p.name for p in group]}前进。")

                if self.move_group(group, tile, steps):
                    self.log("    🏁 该组冲线！")
                else:
                    new_tile = self.locate_entity(entity)
                    if new_tile is not None: self.apply_tile_effect(new_tile)

                for ent in group:
                    if not ent.finished: ent.on_move_end(self)

            else:  # 布大王行动
                if not self.bu.active: continue
                steps = actual_steps[entity]
                self.log(f"  布大王 开始逆行 {steps} 格...")
                final_tile = self._bu_step_move(steps)
                if final_tile is None: continue
                self.log(f"  布大王 最终停在格子{final_tile}，堆叠：{[e.name for e in self.cell[final_tile]]}")

                # 仅对最终停留格触发特殊效果
                self.apply_tile_effect(final_tile)

                # 移动结束钩子（绯雪、尤诺等）
                for ent in self.cell[final_tile][:]:
                    if ent.is_tuanzi() and not ent.finished:
                        ent.on_move_end(self)

    def _apply_before_move(self, entity):
        if entity.is_tuanzi() and not entity.finished:
            entity.before_move_effect(self)

    def _pre_turn_setup(self, participants):
        for t in self.tuanzis:
            if not t.finished: t.pre_turn_effect(self)
        for e in self.skip_entities:
            if e in participants: participants.remove(e)
        self.skip_entities.clear()
        self.extra_steps.clear()

    def _end_turn_effects(self):
        for t in self.tuanzis:
            if not t.finished: t.end_turn_effect(self)

    def _apply_force_last(self, participants):
        if not self.force_last_next: return
        self.force_last_next.sort(key=lambda x: x[1])
        for entity, pri in self.force_last_next:
            if entity in participants:
                participants.remove(entity)
                participants.append(entity)
        self.force_last_next.clear()

    # ---------- 主循环 ----------
    def run(self):
        return self._run_first() if self.mode == 'first' else self._run_second()

    def _run_first(self):
        first_order = self.tuanzis[:]
        random.shuffle(first_order)
        self.cell[START_TILE] = list(reversed(first_order))
        self.round = 1
        self.log(f"第1回合行动顺序：{' → '.join(t.name for t in first_order)}")
        self._pre_turn_setup(first_order)
        steps = self.step_order(first_order)
        self.process_turn(first_order, steps)
        self._end_turn_effects()
        if self.champion: return self.champion

        self.round = 2
        # 修复：重构循环终止条件，优先判断回合数超限
        while self.champion is None:
            # 超过最大回合数，强制结束
            if self.round > self.max_rounds:
                self.log(f"⚠️ 达到最大回合数{self.max_rounds}，强制结束比赛")
                unfinished = [t for t in self.tuanzis if not t.finished]
                self.champion = random.choice(unfinished).name if unfinished else self.tuanzis[0].name
                break
            # 所有团子完成，强制结束
            if all(t.finished for t in self.tuanzis):
                self.champion = self.champion or self.tuanzis[0].name
                break

            participants = [t for t in self.tuanzis if not t.finished]
            if self.round >= 3 and not self.bu.active:
                self.bu.active = True
                self.cell[FINISH_TILE].insert(0, self.bu)
                self.bu.pos = FINISH_TILE
                self.log(f"第{self.round}回合 布大王加入！")
            if self.bu.active: participants.append(self.bu)
            random.shuffle(participants)
            self._apply_force_last(participants)
            self._pre_turn_setup(participants)
            steps = self.step_order(participants)
            self.log(f"\n=== 第{self.round}回合 行动顺序：{' → '.join(p.name for p in participants)} ===")
            self.process_turn(participants, steps)
            self._end_turn_effects()
            self.ba_teleport()
            self.round += 1

        if self.champion is None:
            unfinished = [t for t in self.tuanzis if not t.finished]
            self.champion = random.choice(unfinished).name if unfinished else self.tuanzis[0].name
        return self.champion

    def _run_second(self):
        self.round = 1
        participants = self.tuanzis[:]
        random.shuffle(participants)
        self.log(f"第1回合行动顺序：{' → '.join(t.name for t in participants)}")
        self._pre_turn_setup(participants)
        steps = self.step_order(participants)
        self.process_turn(participants, steps)
        self._end_turn_effects()
        if self.champion:
            return self.champion

        self.round = 2
        # 修复：重构循环终止条件，优先判断回合数超限
        while self.champion is None:
            # 超过最大回合数，强制结束
            if self.round > self.max_rounds:
                self.log(f"⚠️ 达到最大回合数{self.max_rounds}，强制结束比赛")
                unfinished = [t for t in self.tuanzis if not t.finished]
                self.champion = random.choice(unfinished).name if unfinished else self.tuanzis[0].name
                break
            # 所有团子完成，强制结束
            if all(t.finished for t in self.tuanzis):
                self.champion = self.champion or self.tuanzis[0].name
                break

            participants = [t for t in self.tuanzis if not t.finished]
            if self.round >= 3 and not self.bu.active:
                self.bu.active = True
                self.cell[FINISH_TILE].insert(0, self.bu)
                self.bu.pos = FINISH_TILE
                self.log(f"第{self.round}回合 布大王加入！")
            if self.bu.active:
                participants.append(self.bu)
            random.shuffle(participants)
            self._apply_force_last(participants)
            self._pre_turn_setup(participants)
            steps = self.step_order(participants)
            self.log(f"\n=== 第{self.round}回合 行动顺序：{' → '.join(p.name for p in participants)} ===")
            self.process_turn(participants, steps)
            self._end_turn_effects()
            self.ba_teleport()
            self.round += 1

        if self.champion is None:
            unfinished = [t for t in self.tuanzis if not t.finished]
            self.champion = random.choice(unfinished).name if unfinished else self.tuanzis[0].name
        return self.champion