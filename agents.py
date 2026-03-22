from mesa import Agent
import random
import math


class UserAgent(Agent):
    """
    用户智能体，持有SEIR状态和个体属性。
    agent_type: "normal" | "kol" | "official"
    """

    def __init__(self, unique_id, model, agent_type="normal"):
        super().__init__(unique_id, model)
        self.agent_type = agent_type
        self.state = "S"          # S易感 / E潜伏 / I传播 / R恢复
        self.state_timer = 0      # 当前状态已持续步数

        # 个体异质属性
        self.trust = self._init_trust()           # 对干预信息的信任度
        self.activeness = random.uniform(0.1, 1.0)  # 活跃度（影响转发概率）
        self.conformity = random.uniform(0.2, 0.8)  # 从众性（放大感染概率）
        self.influence = self._init_influence()    # 对邻居的影响力

    # ── 属性初始化 ────────────────────────────────────────

    def _init_trust(self):
        if self.agent_type == "official":
            return 1.0
        if self.agent_type == "kol":
            return random.uniform(0.5, 0.9)
        return random.uniform(0.2, 0.8)

    def _init_influence(self):
        if self.agent_type == "official":
            return random.uniform(0.7, 1.0)
        if self.agent_type == "kol":
            return random.uniform(0.4, 0.8)
        return random.uniform(0.05, 0.3)

    # ── 每步行为 ──────────────────────────────────────────

    def step(self):
        self.state_timer += 1
        if self.state == "S":
            self._try_get_exposed()
        elif self.state == "E":
            self._try_become_infected()
        elif self.state == "I":
            self._try_recover()

    def _try_get_exposed(self):
        """从传播者邻居处接触舆情信息"""
        neighbors = self.model.grid.get_neighbors(self.pos, include_center=False)
        spreaders = [n for n in neighbors if n.state == "I"]
        if not spreaders:
            return

        # 邻居影响力之和决定暴露概率，从众性放大效果
        influence_sum = sum(n.influence for n in spreaders)
        prob = 1 - math.exp(-self.model.beta * influence_sum)
        prob *= (0.5 + self.conformity * 0.5)  # conformity 在 [0.5, 1.0] 范围内放大

        if random.random() < prob:
            self.state = "E"
            self.state_timer = 0

    def _try_become_infected(self):
        """潜伏期结束后转为主动传播"""
        if self.state_timer >= self.model.incubation_period:
            if random.random() < self.model.sigma:
                self.state = "I"
                self.state_timer = 0

    def _try_recover(self):
        """
        尝试恢复：基础恢复率 + 干预加成。
        信任度高的Agent更容易被干预说服。
        """
        base = self.model.gamma
        bonus = self.model.intervention.get_current_effect(self.model.current_step) * self.trust
        prob = min(base + bonus, 0.95)

        if random.random() < prob:
            self.state = "R"
            self.state_timer = 0
