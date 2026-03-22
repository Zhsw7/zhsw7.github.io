"""
实验运行器：封装4类对比实验，供 app.py 调用。
每个函数都返回 {label: DataFrame} 字典，可直接传给 charts.py。
"""

import json
import numpy as np
from model import OpinionSpreadModel


def run_single(params: dict, steps=100):
    """运行单次仿真，返回时序 DataFrame"""
    model = OpinionSpreadModel(**params)
    return model.run(steps)


def compare_intervention_timing(base_params: dict, timing_steps: list, steps=100):
    """
    实验一：对比不同干预时刻的效果。
    timing_steps: 干预触发步数列表，例如 [10, 20, 40]
    """
    results = {}

    # 无干预基准
    no_cfg = {**base_params, "intervention_config": None}
    results["无干预"] = run_single(no_cfg, steps)

    # 不同时机
    for t in timing_steps:
        cfg = dict(base_params.get("intervention_config") or {})
        cfg["trigger_step"] = t
        params = {**base_params, "intervention_config": cfg}
        results[f"第{t}步干预"] = run_single(params, steps)

    return results


def sensitivity_analysis(base_params: dict, param_name: str, param_values: list, steps=100):
    """
    实验二：单参数敏感性分析。
    param_name:   intervention_config 中的键，如 "delta0" / "lambda_" / "alpha"
    param_values: 该参数的取值列表
    """
    results = {}
    for val in param_values:
        cfg = dict(base_params.get("intervention_config") or {})
        cfg[param_name] = val
        params = {**base_params, "intervention_config": cfg}
        results[round(val, 3)] = run_single(params, steps)
    return results


def compare_network_types(base_params: dict, network_types: list, steps=100):
    """实验三：对比不同网络拓扑下干预效果的差异"""
    results = {}
    for ntype in network_types:
        params = {**base_params, "network_type": ntype}
        results[ntype] = run_single(params, steps)
    return results


def multi_intervention_decay(base_params: dict, intervals: list, steps=100):
    """
    实验四：多次干预叠加的边际递减效应。
    intervals: 每次干预间隔步数列表，例如 [15, 10, 10] 表示第15步第一次干预，之后每隔10步一次
    """
    from model import OpinionSpreadModel

    cfg = dict(base_params.get("intervention_config") or {})
    cfg.pop("trigger_step", None)
    cfg.pop("auto_threshold", None)

    params = {**base_params, "intervention_config": cfg}
    model = OpinionSpreadModel(**params)

    trigger_points = []
    t = 0
    for gap in intervals:
        t += gap
        trigger_points.append(t)

    step_count = 0
    trigger_idx = 0
    while step_count < steps and model.running:
        if trigger_idx < len(trigger_points) and step_count == trigger_points[trigger_idx]:
            model.intervention.trigger(step_count)
            trigger_idx += 1
        model.step()
        step_count += 1

    df = model.datacollector.get_model_vars_dataframe()
    df.index.name = "step"
    df = df.reset_index()
    return df, trigger_points


def extract_metrics(df) -> dict:
    """从时序 DataFrame 提取关键指标"""
    total = df[["S", "E", "I", "R"]].iloc[0].sum()
    peak_I = int(df["I"].max())
    peak_step = int(df["I"].idxmax())
    final_R = int(df["R"].iloc[-1])
    return {
        "peak_infected": peak_I,
        "peak_step": peak_step,
        "final_recovered": final_R,
        "attack_rate": round(final_R / total, 4) if total > 0 else 0,
    }


# ── 大屏数据导出 ──────────────────────────────────────────────────────────────

def export_dashboard_data(
    base_params: dict,
    int_cfg: dict,
    steps: int = 80,
    output_path: str = "dashboard_data.json",
):
    """
    跑完4组实验，把结果打包成 dashboard_data.json，供大屏 HTML 直接读取。

    用法（在项目根目录执行一次即可）：
        from experiment import export_dashboard_data
        BASE = dict(n_agents=300, initial_infected=5, beta=0.3, sigma=0.5,
                    gamma=0.05, network_type="small_world", kol_ratio=0.05, seed=42)
        INT  = dict(delta0=0.4, lambda_=0.1, alpha=0.8, trigger_step=20)
        export_dashboard_data(BASE, INT)
    """

    def df_to_cols(df, target_len=None):
        """
        DataFrame -> {列名: [值, ...]}
        target_len: 若指定，将所有序列 pad/截断到该长度，保证 Chart.js 各系列等长。
        pad 时 S/R 用最后一个值填充（状态冻结），E/I 用 0（已消退），
        Intervention 用 0（效果归零），step 正常递增。
        """
        cols = ["step", "S", "E", "I", "R", "Intervention"]
        result = {c: [round(float(v), 4) for v in df[c]] for c in cols if c in df.columns}
        if target_len is not None:
            cur = len(result["step"])
            if cur < target_len:
                pad = target_len - cur
                last_step = int(result["step"][-1])
                last_S = result["S"][-1]
                last_R = result["R"][-1]
                result["step"]         += [last_step + i + 1 for i in range(pad)]
                result["S"]            += [last_S] * pad
                result["E"]            += [0.0] * pad
                result["I"]            += [0.0] * pad
                result["R"]            += [last_R] * pad
                if "Intervention" in result:
                    result["Intervention"] += [0.0] * pad
            elif cur > target_len:
                result = {c: v[:target_len] for c, v in result.items()}
        return result

    # ── 实验一：SEIR基础曲线（有干预 & 无干预）──
    df_with = run_single({**base_params, "intervention_config": int_cfg}, steps)
    df_none = run_single({**base_params, "intervention_config": None}, steps)

    m_with = extract_metrics(df_with)
    m_none = extract_metrics(df_none)

    # 以两条基础曲线中较长的为基准长度，后续所有序列都对齐到这个长度
    base_len = max(len(df_with), len(df_none))

    # ── 实验一：干预时机对比 ──
    timing_steps_list = [10, 20, 30, 45]
    cfg_no_step = {k: v for k, v in int_cfg.items() if k != "trigger_step"}
    timing_results = compare_intervention_timing(
        {**base_params, "intervention_config": cfg_no_step},
        timing_steps_list, steps
    )

    # ── 实验二：δ₀ 敏感性 ──
    delta0_vals = [round(0.1 + 0.9 * i / 9, 2) for i in range(10)]
    sens_results = sensitivity_analysis(
        {**base_params, "intervention_config": int_cfg}, "delta0", delta0_vals, steps
    )
    delta0_peaks = {
        str(k): extract_metrics(v)["peak_infected"]
        for k, v in sens_results.items()
    }

    # ── 实验三：网络拓扑对比 ──
    network_types = ["small_world", "scale_free", "random"]
    net_labels = {"small_world": "小世界网络", "scale_free": "无标度网络", "random": "随机网络"}

    net_with, net_none = {}, {}
    for ntype in network_types:
        p_with = {**base_params, "network_type": ntype, "intervention_config": int_cfg}
        p_none = {**base_params, "network_type": ntype, "intervention_config": None}
        net_with[net_labels[ntype]] = extract_metrics(run_single(p_with, steps))["peak_infected"]
        net_none[net_labels[ntype]] = extract_metrics(run_single(p_none, steps))["peak_infected"]

    # ── 实验四：多次干预 ──
    intervals = [15, 15, 15]  # 第15、30、45步各触发一次
    df_multi, trigger_points = multi_intervention_decay(
        {**base_params, "intervention_config": int_cfg}, intervals, steps
    )

    # ── 组装输出 ──
    payload = {
        "meta": {
            "n_agents":         base_params.get("n_agents", 300),
            "network_type":     base_params.get("network_type", "small_world"),
            "beta":             base_params.get("beta", 0.3),
            "sigma":            base_params.get("sigma", 0.5),
            "gamma":            base_params.get("gamma", 0.05),
            "seed":             base_params.get("seed", 42),
            "delta0":           int_cfg.get("delta0", 0.4),
            "lambda_":          int_cfg.get("lambda_", 0.1),
            "alpha":            int_cfg.get("alpha", 0.8),
            "trigger_step":     int_cfg.get("trigger_step", 20),
        },
        "seir_with":    df_to_cols(df_with, base_len),
        "seir_none":    df_to_cols(df_none, base_len),
        "metrics_with": m_with,
        "metrics_none": m_none,
        "timing": {
            label: df_to_cols(df, base_len)
            for label, df in timing_results.items()
        },
        "sensitivity_delta0": {
            "values":  [str(v) for v in delta0_vals],
            "peaks":   [delta0_peaks[str(v)] for v in delta0_vals],
        },
        "network": {
            "labels":     list(net_labels.values()),
            "peaks_with": [net_with[net_labels[n]] for n in network_types],
            "peaks_none": [net_none[net_labels[n]] for n in network_types],
        },
        "multi": {
            "seir":           df_to_cols(df_multi, base_len),
            "trigger_points": trigger_points,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ 导出完成 → {output_path}")
    print(f"   有干预峰值: {m_with['peak_infected']}  无干预峰值: {m_none['peak_infected']}")
    print(f"   感染率: {m_with['attack_rate']*100:.1f}% → {m_none['attack_rate']*100:.1f}%")
    return payload


if __name__ == "__main__":
    # 直接运行此文件即可生成 dashboard_data.json
    # python experiment.py
    BASE = dict(
        n_agents=300, initial_infected=5,
        beta=0.3, sigma=0.5, gamma=0.05,
        network_type="small_world", kol_ratio=0.05, seed=42,
    )
    INT = dict(delta0=0.4, lambda_=0.1, alpha=0.8, trigger_step=20)
    export_dashboard_data(BASE, INT)
