import math

class InterventionModule:
    """
    管理舆情干预效果及其随时间的衰减。

    衰减公式：
        E(t) = sum_k [ delta_k * exp(-lambda * (t - t_k)) ]

    其中 delta_k = delta0 * alpha^(k-1)，体现多次干预的信任折损。
    """

    def __init__(self, delta0=0.3, lambda_=0.1, alpha=0.8):
        """
        delta0:  首次干预初始强度 (0~1)
        lambda_: 衰减系数，越大效果消退越快
        alpha:   信任折损系数 (0~1)，每次干预的初始强度乘以 alpha
        """
        self.delta0 = delta0
        self.lambda_ = lambda_
        self.alpha = alpha

        self._interventions = []  # 记录每次干预：(触发时刻, 该次初始强度)
        self.count = 0

    # ── 外部接口 ──────────────────────────────────────────

    def trigger(self, t):
        """在第t步触发一次新干预"""
        self.count += 1
        effective_delta = self.delta0 * (self.alpha ** (self.count - 1))
        self._interventions.append((t, effective_delta))

    def get_current_effect(self, t):
        """计算第t步所有干预叠加的总效果"""
        if not self._interventions:
            return 0.0
        total = sum(
            d0 * math.exp(-self.lambda_ * (t - t0))
            for t0, d0 in self._interventions
            if t >= t0
        )
        return min(total, 1.0)

    def get_effect_series(self, t_max):
        """返回从0到t_max的每步效果列表，用于图表"""
        return [self.get_current_effect(t) for t in range(t_max)]

    def reset(self):
        self._interventions = []
        self.count = 0

    @property
    def triggered(self):
        return self.count > 0

    def summary(self):
        return {
            "count": self.count,
            "delta0": self.delta0,
            "lambda": self.lambda_,
            "alpha": self.alpha,
            "records": self._interventions,
        }
