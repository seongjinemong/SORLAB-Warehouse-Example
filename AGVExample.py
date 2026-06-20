import simpy
import random
import pygame
import sys

# --- 1. 설정 및 초기화 ---
WIDTH, HEIGHT = 7, 5
TILE_SIZE = 100
SCREEN_WIDTH = WIDTH * TILE_SIZE
SCREEN_HEIGHT = HEIGHT * TILE_SIZE
SIM_END_TIME = 100  # ⏱️ 시뮬레이션 종료 시간 (초)

WHITE, GRAY = (255, 255, 255), (200, 200, 200)
INBOUND_COLOR, OUTBOUND_COLOR = (100, 149, 237), (255, 99, 71)
RACK_COLOR, AGV_COLOR = (244, 164, 96), (50, 205, 50)

INBOUND, OUTBOUND = (0, 0), (6, 4)
RACKS = [(2, 1), (2, 3), (4, 1), (4, 3)]

# 📊 통계 추적용 데이터 딕셔너리
stats = {
    "inbound_completed": 0,    # 총 입고 처리량
    "outbound_completed": 0,   # 총 출고 처리량
    "agv_work_time": {}        # AGV별 실제 작업(이동+적재/피킹) 시간
}


class Warehouse:
    def __init__(self, env):
        self.env = env
        self.grid = {(x, y): simpy.Resource(env, capacity=1)
                     for x in range(WIDTH) for y in range(HEIGHT)}
        self.inventory = {loc: simpy.Container(
            env, capacity=5, init=2) for loc in RACKS}
        self.agvs = {}


def move_agv(env, wh, agv_id, start, end):
    curr_x, curr_y = start
    wh.agvs[agv_id] = (curr_x, curr_y)

    curr_req = wh.grid[(curr_x, curr_y)].request()
    yield curr_req

    while (curr_x, curr_y) != end:
        next_x, next_y = curr_x, curr_y
        if curr_x < end[0]:
            next_x += 1
        elif curr_x > end[0]:
            next_x -= 1
        elif curr_y < end[1]:
            next_y += 1
        elif curr_y > end[1]:
            next_y -= 1

        next_loc = (next_x, next_y)
        next_req = wh.grid[next_loc].request()
        yield next_req

        yield env.timeout(1)

        wh.grid[(curr_x, curr_y)].release(curr_req)
        curr_x, curr_y = next_x, next_y
        curr_req = next_req
        wh.agvs[agv_id] = (curr_x, curr_y)

    return curr_req


def supply_process(env, wh, agv_id):
    stats["agv_work_time"][agv_id] = 0  # 초기화
    while True:
        yield env.timeout(random.uniform(2, 5))

        available = [loc for loc in RACKS if wh.inventory[loc].level <
                     wh.inventory[loc].capacity]
        if not available:
            yield env.timeout(1)
            continue

        target = random.choice(available)

        # ⏱️ 작업 시작 시간 기록
        start_time = env.now

        req = yield env.process(move_agv(env, wh, agv_id, INBOUND, target))
        yield env.timeout(1.5)
        yield wh.inventory[target].put(1)

        wh.grid[target].release(req)
        req = yield env.process(move_agv(env, wh, agv_id, target, INBOUND))
        wh.grid[INBOUND].release(req)

        # ⏱️ 통계 업데이트: 작업 완료 후 누적 시간 및 처리량 증가
        stats["agv_work_time"][agv_id] += (env.now - start_time)
        stats["inbound_completed"] += 1


def demand_process(env, wh, agv_id):
    stats["agv_work_time"][agv_id] = 0  # 초기화
    while True:
        yield env.timeout(random.uniform(3, 6))

        stocked = [loc for loc in RACKS if wh.inventory[loc].level > 0]
        if not stocked:
            yield env.timeout(1)
            continue

        target = random.choice(stocked)

        # ⏱️ 작업 시작 시간 기록
        start_time = env.now

        req = yield env.process(move_agv(env, wh, agv_id, OUTBOUND, target))
        yield env.timeout(1.5)
        yield wh.inventory[target].get(1)

        wh.grid[target].release(req)
        req = yield env.process(move_agv(env, wh, agv_id, target, OUTBOUND))
        wh.grid[OUTBOUND].release(req)

        # ⏱️ 통계 업데이트: 작업 완료 후 누적 시간 및 처리량 증가
        stats["agv_work_time"][agv_id] += (env.now - start_time)
        stats["outbound_completed"] += 1

# --- 2. 시뮬레이션 요약 리포트 출력 함수 ---


def print_statistics():
    print("\n" + "="*40)
    print("📈 [시뮬레이션 최종 통계 리포트]")
    print(f"⏱️ 총 경과 시간 : {SIM_END_TIME} 초")
    print("-" * 40)
    print(f"📦 입고 완료 건수 : {stats['inbound_completed']} 건")
    print(f"🚚 출고 완료 건수 : {stats['outbound_completed']} 건")
    print(
        f"총 처리 물동량 : {stats['inbound_completed'] + stats['outbound_completed']} 건")
    print("-" * 40)
    print("🤖 [AGV별 가동률 (Utilization)]")
    for agv_id, work_time in stats["agv_work_time"].items():
        utilization = (work_time / SIM_END_TIME) * 100
        print(
            f" - {agv_id} : {utilization:.1f}% (작업 {work_time:.1f}초 / 대기 {SIM_END_TIME - work_time:.1f}초)")
    print("="*40 + "\n")


# --- 3. Pygame 루프 ---
def run_simulation():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("SimPy AGV Digital Twin w/ Analytics")
    clock = pygame.time.Clock()

    try:
        font = pygame.font.SysFont("malgungothic", 18, bold=True)
    except:
        font = pygame.font.SysFont("sans", 18, bold=True)

    env = simpy.Environment()
    wh = Warehouse(env)

    env.process(supply_process(env, wh, "S1"))
    env.process(demand_process(env, wh, "D1"))
    env.process(demand_process(env, wh, "D2"))

    sim_speed = 0.05
    running = True
    simulation_active = True  # 🛑 시뮬레이션 진행 상태 플래그

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 설정된 종료 시간에 도달하기 전까지만 환경(env) 업데이트
        if simulation_active:
            env.run(until=env.now + sim_speed)

            # 종료 조건 도달 시
            if env.now >= SIM_END_TIME:
                simulation_active = False
                print_statistics()  # 콘솔에 리포트 출력

        # 화면 렌더링
        screen.fill(WHITE)
        for x in range(WIDTH):
            for y in range(HEIGHT):
                rect = pygame.Rect(x * TILE_SIZE, y *
                                   TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(screen, GRAY, rect, 1)

                pos = (x, y)
                if pos == INBOUND:
                    pygame.draw.rect(screen, INBOUND_COLOR, rect)
                    screen.blit(font.render("IN", True, WHITE),
                                (x * TILE_SIZE + 35, y * TILE_SIZE + 40))
                elif pos == OUTBOUND:
                    pygame.draw.rect(screen, OUTBOUND_COLOR, rect)
                    screen.blit(font.render("OUT", True, WHITE),
                                (x * TILE_SIZE + 30, y * TILE_SIZE + 40))
                elif pos in RACKS:
                    pygame.draw.rect(screen, RACK_COLOR, rect)
                    stock = wh.inventory[pos].level
                    screen.blit(font.render(
                        f"Stock:{stock}", True, WHITE), (x * TILE_SIZE + 15, y * TILE_SIZE + 40))

        for agv_id, (ax, ay) in wh.agvs.items():
            center = (int(ax * TILE_SIZE + TILE_SIZE / 2),
                      int(ay * TILE_SIZE + TILE_SIZE / 2))
            pygame.draw.circle(screen, AGV_COLOR, center,
                               int(TILE_SIZE * 0.35))
            screen.blit(font.render(agv_id, True, WHITE),
                        (center[0] - 12, center[1] - 10))

        # UI 텍스트 출력
        time_text = font.render(
            f"Sim Time: {min(env.now, SIM_END_TIME):.1f} / {SIM_END_TIME}", True, (0, 0, 0))
        screen.blit(time_text, (10, 10))

        # 종료 시 화면 중앙에 알림 메시지 오버레이
        if not simulation_active:
            overlay = pygame.Surface(
                (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))
            screen.blit(overlay, (0, 0))
            end_msg = font.render("시뮬레이션 종료! 콘솔창의 통계를 확인하세요.", True, WHITE)
            screen.blit(end_msg, (SCREEN_WIDTH//2 -
                        180, SCREEN_HEIGHT//2 - 20))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    run_simulation()
