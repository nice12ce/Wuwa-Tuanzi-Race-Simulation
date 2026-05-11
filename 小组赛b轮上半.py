import random
from collections import defaultdict

# ====================== 地图常量 ======================
MAP_SIZE = 32
START_TILE = 1
FINISH_TILE = 32
GREEN_TILES = {3, 11, 16, 23}
RED_TILES = {10, 28}
RIFT_TILES = {6, 20}


# ====================== 团子技能类 ======================
class Tuanzi:
    def __init__(self, name):
        self.name = name
        self.finished = False

    def get_base_roll(self, round_num):
        return random.randint(1, 3)

    def get_actual_steps(self, base_roll, global_info=None):
        return base_roll


class QianZhi(Tuanzi):
    """千咲 - 视阈解明"""

    def get_actual_steps(self, base_roll, global_info=None):
        if global_info and "all_base_rolls" in global_info:
            if base_roll == min(global_info["all_base_rolls"]):
                return base_roll + 2
        return base_roll


class MoNing(Tuanzi):
    """莫宁 - 精密演算"""

    def get_base_roll(self, round_num):
        return 3 - (round_num - 1) % 3


class LinNai(Tuanzi):
    """琳奈 - 炫彩时刻"""

    def get_actual_steps(self, base_roll, global_info=None):
        r = random.random()
        if r < 0.6:
            return base_roll * 2
        if r < 0.8:
            return 0
        return base_roll


class AiMiSi(Tuanzi):
    """爱弥斯 - 电子幽灵登场"""

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

        # 找前方最近的非布大王未完成团子
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

        # 执行传送
        race.cell[tile].remove(self)
        race.cell[target_tile].append(self)
        self.teleport_used = True
        if race.verbose:
            print(f"  ⚡ 爱弥斯触发被动！传送至格子{target_tile}，骑在{target.name}头上！")


class ShouAnRen(Tuanzi):
    """守岸人 - 收束的未来"""

    def get_base_roll(self, round_num):
        return random.choice([2, 3])


class KeLaiTa(Tuanzi):
    """珂莱塔 - 利润加倍"""

    def get_actual_steps(self, base_roll, global_info=None):
        if random.random() < 0.28:
            return base_roll * 2
        return base_roll


class BaDawang:
    def __init__(self):
        self.name = "布大王"
        self.pos = FINISH_TILE
        self.active = False

    def get_base_roll(self, round_num):
        return random.randint(1, 6)

    def get_actual_steps(self, base_roll, global_info=None):
        return base_roll


# ====================== 比赛引擎 ======================
class Race:
    def __init__(self, verbose=False):
        self.tuanzis = [
            QianZhi("千咲"), MoNing("莫宁"), LinNai("琳奈"),
            AiMiSi("爱弥斯"), ShouAnRen("守岸人"), KeLaiTa("珂莱塔")
        ]
        self.bu = BaDawang()
        self.cell = {i: [] for i in range(1, MAP_SIZE + 1)}
        for t in self.tuanzis:
            self.cell[START_TILE].append(t)
        self.round = 0
        self.champion = None
        self.verbose = verbose

    def log(self, msg):
        if self.verbose:
            print(msg)

    def locate_entity(self, entity):
        """返回普通团子所在格号，找不到返回None"""
        for tile in range(1, MAP_SIZE + 1):
            if entity in self.cell[tile]:
                return tile
        return None

    def build_initial_stack(self, order):
        self.cell[START_TILE] = list(reversed(order))

    def move_group(self, group, from_tile, delta):
        """
        移动一组团子。
        返回 True 表示该组已冲线（成员会被标记完成），False 表示正常移动。
        """
        # 从原格移除
        for t in group:
            self.cell[from_tile].remove(t)

        new = from_tile + delta
        if new >= FINISH_TILE:
            # 冲线：无论冠军是否已产生，所有组员都标记完成
            if self.champion is None:
                # 【修复1】：将 group[0] 改为 group[-1]，顶部团子成为冠军
                self.champion = group[-1].name
            for t in group:
                t.finished = True
            return True

        if new < 1:
            new = 1
        self.cell[new].extend(group)
        return False

    def apply_tile_effect(self, tile):
        if tile in RIFT_TILES:
            if self.cell[tile]:
                random.shuffle(self.cell[tile])
                self.log(f"  🌀 裂隙打乱了格子{tile}的堆叠！")
            return

        if tile in GREEN_TILES or tile in RED_TILES:
            delta = 1 if tile in GREEN_TILES else -1
            # 【修复2】：加上 [:] 创建切片副本，防止遍历时漏人
            all_normal = self.cell[tile][:]
            if not all_normal:
                return
            self.log(f"  {'🟢' if delta == 1 else '🔴'} 格子{tile}效果！全组{'前进' if delta == 1 else '后退'}1格。")
            self.move_group(all_normal, tile, delta)
            # 【修复5】：删除了布大王连带受红绿格影响的逻辑，只让普通团子移动

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
        if self.bu.pos < min(unfinished_tiles):
            self.bu.pos = FINISH_TILE
            self.log(f"  ⚡ 布大王跑到了所有人后面，传送回32！")

    def step_order(self, participants):
        base_rolls = {}
        for p in participants:
            if isinstance(p, Tuanzi):
                base_rolls[p] = p.get_base_roll(self.round)
            else:
                base_rolls[p] = p.get_base_roll(self.round)
        all_base = list(base_rolls.values())
        global_info = {"all_base_rolls": all_base}
        actual_steps = {}
        for p in participants:
            actual_steps[p] = p.get_actual_steps(base_rolls[p], global_info)
        return actual_steps

    def process_turn(self, participants, actual_steps):
        for entity in participants:
            if self.champion:
                break

            if isinstance(entity, Tuanzi):
                if entity.finished:
                    continue
                tile = self.locate_entity(entity)
                if tile is None:
                    self.log(f"  ⚠️ {entity.name} 已失踪，跳过")
                    continue
                stack = self.cell[tile]
                idx = stack.index(entity)
                group = stack[idx:]  # 自己及上方所有团子
                steps = actual_steps[entity]
                self.log(f"  {entity.name} 从格子{tile}，步数={steps}，带着{[p.name for p in group]}前进。")

                if self.move_group(group, tile, steps):
                    self.log(f"    🏁 该组冲线！")
                    continue  # 冲线后继续循环，让全局能检测到

                # 移动后位置
                new_tile = self.locate_entity(entity)
                if new_tile is not None:
                    self.apply_tile_effect(new_tile)

            else:  # 布大王行动
                if not self.bu.active:
                    continue
                tile = self.bu.pos
                taken = self.cell[tile][:]
                self.cell[tile] = []
                steps = actual_steps[entity]

                # 【修复3】：改为线性后退，限制最小值为 1，避免取模越界瞬移
                new_pos = tile - steps
                if new_pos < 1:
                    new_pos = 1

                self.bu.pos = new_pos
                self.cell[new_pos] = self.cell[new_pos] + taken
                self.log(f"  布大王 从格子{tile}，逆行步数={steps}，停在格子{new_pos}，带走{[p.name for p in taken]}")
                self.apply_tile_effect(new_pos)

            # 【修复4】：爱弥斯全局传送检查。无论谁行动、是否触发红绿格，结束后统一检查一次爱弥斯
            for t in self.tuanzis:
                if isinstance(t, AiMiSi):
                    t.check_teleport(self)

    def run(self):
        # 第一回合：堆叠顺序 = 行动顺序
        first_order = self.tuanzis[:]
        random.shuffle(first_order)
        self.build_initial_stack(first_order)
        self.round = 1
        self.log(f"第1回合行动顺序：{' → '.join(t.name for t in first_order)}")
        self.log(f"起点堆叠（底→顶）：{' → '.join(t.name for t in self.cell[START_TILE])}")
        actual_steps = self.step_order(first_order)
        self.process_turn(first_order, actual_steps)
        if self.champion:
            return self.champion

        self.round = 2
        while self.champion is None:
            # 安全检查：如果全员都 finished 但 champion 还是 None (罕见情况兜底)
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
            if not participants:
                break

            random.shuffle(participants)
            actual_steps = self.step_order(participants)
            self.log(f"\n=== 第{self.round}回合 行动顺序：{' → '.join(p.name for p in participants)} ===")
            self.process_turn(participants, actual_steps)
            self.ba_teleport()
            self.round += 1

        return self.champion


# ====================== 100次模拟统计 ======================
if __name__ == "__main__":
    wins = defaultdict(int)
    # 将 verbose 设为 False 可以关闭详细日志，只看最终结果
    # 设为 True 则打印完整的战况
    SIMULATION_COUNT = 1000

    for i in range(SIMULATION_COUNT):
        # 如果只需要结果，建议设 verbose=False，不然控制台输出会非常长
        r = Race(verbose=True)
        champion = r.run()
        wins[champion] += 1

    print(f"\n===== {SIMULATION_COUNT}轮模拟结果 =====")
    total = sum(wins.values())

    # 按胜率从高到低排序输出
    sorted_wins = sorted(wins.items(), key=lambda item: item[1], reverse=True)

    for name, w in sorted_wins:
        print(f"{name}: {w}胜, 胜率 {w / total * 100:.1f}%")