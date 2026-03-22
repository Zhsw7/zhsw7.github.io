from mesa import Model
from mesa.time import RandomActivation
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
import random

from agents import UserAgent
from intervention import InterventionModule
from network_builder import build_network


class OpinionSpreadModel(Model):
    """
    舆情传播仿真主模型（基于SEIR + 干预衰减）。

    intervention_config 字段说明：
        delta0         初始干预强度
        lambda_        衰减系数
        alpha          信任折损系数
        trigger_step   固定步数触发干预（与 auto_threshold 二选一）
        auto_threshold 传播者占比超过该阈值时自动触发（0~1）
    """

    def __init__(
        self,
        n_agents=300,
        initial_infected=5,
        beta=0.3,
        sigma=0.5,
        gamma=0.05,
        incubation_period=2,
        network_type="small_world",
        kol_ratio=0.05,
        intervention_config=None,
        seed=42,
    ):
        # ✅ 修复一：将 seed 传给 super().__init__()，确保 Mesa 内部
        # RandomActivation 的 Agent 激活顺序也受 seed 控制，保证结果可复现。
        # 原代码 super().__init__() 未传 seed，导致 Mesa 的 self.random 实例
        # 使用未播种的随机源，每次运行激活顺序不同，SEIR 曲线无法复现。
        super().__init__(seed=seed)
        random.seed(seed)

        self.n_agents = n_agents
        self.beta = beta
        self.sigma = sigma
        self.gamma = gamma
        self.incubation_period = incubation_period
        self.current_step = 0
        self.running = True

        # 解析干预配置
        cfg = intervention_config or {}
        self.intervention = InterventionModule(
            delta0=cfg.get("delta0", 0.3),
            lambda_=cfg.get("lambda_", 0.1),
            alpha=cfg.get("alpha", 0.8),
        )
        self._trigger_step = cfg.get("trigger_step", None)
        self._auto_threshold = cfg.get("auto_threshold", None)
        self._already_triggered = False

        # 构建社交网络
        G = build_network(network_type, n_agents, seed=seed)
        self.G = G  # 保存引用供外部可视化使用
        self.grid = NetworkGrid(G)
        self.schedule = RandomActivation(self)

        # 创建 Agent
        n_kol = int(n_agents * kol_ratio)
        for i in range(n_agents):
            atype = "kol" if i < n_kol else "normal"
            agent = UserAgent(i, self, atype)
            self.schedule.add(agent)
            self.grid.place_agent(agent, i)

        # 随机设置初始感染源
        infected_ids = set(random.sample(range(n_agents), min(initial_infected, n_agents)))
        for agent in self.schedule.agents:
            if agent.unique_id in infected_ids:
                agent.state = "I"

        # 数据收集器
        # ✅ 修复二：Intervention reporter 改用 m.current_step - 1。
        # 原因：step() 中先执行 current_step += 1 再 collect()，导致收集时
        # current_step 已是 N+1，get_current_effect(N+1) 比 Agent 实际经历的
        # get_current_effect(N) 多衰减了一步，干预峰值 δ₀ 永远不会出现在图表上。
        # 用 current_step - 1 可还原 Agent 在该步实际感受到的干预强度。
        # 初始收集时 current_step=0，get_current_effect(-1) 因无干预记录返回 0.0，不受影响。
        self.datacollector = DataCollector(
            model_reporters={
                "S": lambda m: m._count("S"),
                "E": lambda m: m._count("E"),
                "I": lambda m: m._count("I"),
                "R": lambda m: m._count("R"),
                "Intervention": lambda m: m.intervention.get_current_effect(m.current_step - 1),
            }
        )
        self.datacollector.collect(self)

    # ── 仿真推进 ──────────────────────────────────────────

    def step(self):
        self._check_intervention()
        self.schedule.step()
        self.current_step += 1
        self.datacollector.collect(self)

        # 无传播者时自动停止
        if self._count("I") == 0 and self._count("E") == 0:
            self.running = False

    def run(self, steps=100):
        """运行指定步数，返回时序数据帧"""
        for _ in range(steps):
            if not self.running:
                break
            self.step()
        df = self.datacollector.get_model_vars_dataframe()
        df.index.name = "step"
        df = df.reset_index()
        return df

    # ── 干预触发逻辑 ──────────────────────────────────────

    def _check_intervention(self):
        if self._already_triggered:
            return
        # 固定时刻触发
        if self._trigger_step is not None and self.current_step == self._trigger_step:
            self.intervention.trigger(self.current_step)
            self._already_triggered = True
        # 阈值自动触发
        elif self._auto_threshold is not None:
            if self._count("I") / self.n_agents >= self._auto_threshold:
                self.intervention.trigger(self.current_step)
                self._already_triggered = True

    def trigger_now(self):
        """允许外部（如前端按钮）手动立即触发干预"""
        self.intervention.trigger(self.current_step)

    # ── 辅助方法 ──────────────────────────────────────────

    def _count(self, state):
        """统计特定状态的agent数量"""
        return sum(1 for a in self.schedule.agents if a.state == state)

    def get_agent_states(self):
        """返回 {node_id: state} 字典，供网络快照图使用"""
        return {a.unique_id: a.state for a in self.schedule.agents}
