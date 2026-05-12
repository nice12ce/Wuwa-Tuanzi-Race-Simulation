from collections import defaultdict
from core import Race
from characters import create_tuanzi

def run_simulation(mode, num_simulations, tuanzi_names, start_cell=None):
    wins = defaultdict(int)
    interval = max(1, num_simulations // 10)
    for i in range(num_simulations):
        tuanzis = [create_tuanzi(name) for name in tuanzi_names]
        r = Race(mode=mode, tuanzis=tuanzis, start_cell=start_cell, verbose=False)
        wins[r.run()] += 1
        if (i + 1) % interval == 0: print(f"  进度：{i+1}/{num_simulations}")
    total = sum(wins.values())
    print(f"\n===== {mode}半场 {num_simulations}次模拟结果 =====")
    for name, w in sorted(wins.items(), key=lambda x: x[1], reverse=True):
        print(f"{name}: {w}胜, 胜率 {w/total*100:.1f}%")

if __name__ == "__main__":
    # ========== 配置 ==========
    MODE = 'second'          # 'first' / 'second'
    SIM_COUNT = 10000
    VERBOSE_SINGLE = True

    my_tuanzi_names = ["长离", "卡卡罗", "今汐", "弗洛洛", "尤诺", "奥古斯塔"]

    custom_start = {        # 仅下半场需要
        32: ["布大王", "奥古斯塔"],
        30: ["卡卡罗","今汐"],
        29: ["尤诺","弗洛洛"],
        28: ["长离"],
    }

    print(f"开始模拟：{MODE}半场，次数 {SIM_COUNT}，参赛 {my_tuanzi_names}")
    run_simulation(MODE, SIM_COUNT, my_tuanzi_names, custom_start)

    if VERBOSE_SINGLE:
        print("\n===== 单局详细演示 =====")
        demo = [create_tuanzi(n) for n in my_tuanzi_names]
        champ = Race(mode=MODE, tuanzis=demo, start_cell=custom_start, verbose=True).run()
        print(f"冠军：{champ}")