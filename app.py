import streamlit as st
import pandas as pd

from model import OpinionSpreadModel
from experiment import (
    run_single, compare_intervention_timing,
    sensitivity_analysis, compare_network_types,
    multi_intervention_decay, extract_metrics,
    export_dashboard_data,
)
from charts import (
    seir_curve, intervention_curve, comparison_curve,
    sensitivity_bar, network_snapshot, multi_intervention_chart,
)

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(page_title="舆情干预仿真平台", layout="wide", page_icon="🌐")
st.title("🌐 多智能体舆情干预衰减仿真平台")

# ── 侧边栏：全局参数配置 ─────────────────────────────────
st.sidebar.header("⚙️ 参数配置")

with st.sidebar.expander("👥 人群参数", expanded=True):
    n_agents = st.slider("Agent 总数", 100, 800, 300, 50)
    kol_ratio = st.slider("KOL 比例", 0.01, 0.2, 0.05, 0.01)
    initial_infected = st.slider("初始感染数", 1, 20, 5)

with st.sidebar.expander("📡 传播参数", expanded=True):
    beta = st.slider("传播率 β", 0.05, 0.9, 0.3, 0.05)
    sigma = st.slider("潜伏→传播率 σ", 0.1, 1.0, 0.5, 0.05)
    gamma = st.slider("自然恢复率 γ", 0.01, 0.3, 0.05, 0.01)
    network_type = st.selectbox("网络拓扑", ["small_world", "scale_free", "random"],
                                 format_func=lambda x: {"small_world": "小世界网络",
                                                         "scale_free": "无标度网络",
                                                         "random": "随机网络"}[x])

with st.sidebar.expander("🛡️ 干预参数", expanded=True):
    delta0 = st.slider("初始干预强度 δ₀", 0.1, 1.0, 0.4, 0.05)
    lambda_ = st.slider("衰减系数 λ", 0.01, 0.5, 0.1, 0.01)
    alpha = st.slider("信任折损 α", 0.5, 1.0, 0.8, 0.05)
    trigger_step = st.slider("干预触发时刻（步）", 0, 90, 20, 5)

sim_steps = st.sidebar.slider("仿真总步数", 50, 200, 100)
seed = int(st.sidebar.number_input("随机种子", value=42, step=1))

# 构造通用参数字典（供各 Tab 使用）
BASE_PARAMS = dict(
    n_agents=n_agents, initial_infected=initial_infected,
    beta=beta, sigma=sigma, gamma=gamma,
    network_type=network_type, kol_ratio=kol_ratio, seed=seed,
)
INT_CFG = dict(delta0=delta0, lambda_=lambda_, alpha=alpha, trigger_step=trigger_step)

# ── 标签页 ────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 基础仿真",
    "⏱️ 干预时机对比",
    "📈 参数敏感性",
    "🔁 多次干预",
    "🌐 网络快照",
])

# ════════════════ Tab1: 基础仿真 ════════════════════════════
with tab1:
    st.subheader("单次仿真 — SEIR 动态与干预效果")
    if st.button("▶ 运行仿真", type="primary"):
        with st.spinner("仿真运行中..."):
            df = run_single({**BASE_PARAMS, "intervention_config": INT_CFG}, sim_steps)
            st.session_state["df_basic"] = df
        with st.spinner("导出大屏数据..."):
            try:
                export_dashboard_data(BASE_PARAMS, INT_CFG, steps=sim_steps)
                st.toast("✅ dashboard_data.json 已更新", icon="💾")
            except Exception as e:
                st.toast(f"⚠️ 大屏数据导出失败: {e}", icon="⚠️")

    if "df_basic" in st.session_state:
        df = st.session_state["df_basic"]
        m = extract_metrics(df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("峰值传播数", m["peak_infected"])
        c2.metric("峰值时刻", f"第 {m['peak_step']} 步")
        c3.metric("最终恢复数", m["final_recovered"])
        c4.metric("感染率", f"{m['attack_rate']*100:.1f}%")

        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(seir_curve(df), use_container_width=True)
        with col_r:
            st.plotly_chart(intervention_curve(df), use_container_width=True)

# ════════════════ Tab2: 干预时机对比 ════════════════════════
with tab2:
    st.subheader("不同干预时刻的效果对比（实验一）")
    timing_list = st.multiselect(
        "选择干预时刻", list(range(5, 91, 5)), default=[10, 25, 45]
    )
    if st.button("▶ 运行对比", type="primary", key="cmp"):
        if not timing_list:
            st.warning("请至少选择一个时刻")
        else:
            with st.spinner("运行中..."):
                cfg_no_step = {k: v for k, v in INT_CFG.items() if k != "trigger_step"}
                results = compare_intervention_timing(
                    {**BASE_PARAMS, "intervention_config": cfg_no_step},
                    sorted(timing_list), sim_steps
                )
                st.session_state["cmp_results"] = results

    if "cmp_results" in st.session_state:
        results = st.session_state["cmp_results"]
        st.plotly_chart(
            comparison_curve(results, "I", "不同干预时刻 — 传播者数量对比"),
            use_container_width=True
        )
        rows = [{"方案": k, **extract_metrics(v)} for k, v in results.items()]
        st.dataframe(
            pd.DataFrame(rows).rename(columns={
                "peak_infected": "峰值传播数", "peak_step": "峰值时刻",
                "final_recovered": "最终恢复数", "attack_rate": "感染率"
            }),
            use_container_width=True, hide_index=True
        )

# ════════════════ Tab3: 参数敏感性 ══════════════════════════
with tab3:
    st.subheader("干预参数敏感性分析（实验二）")
    target = st.selectbox("选择分析参数", ["delta0", "lambda_", "alpha"],
                           format_func=lambda x: {"delta0": "初始干预强度 δ₀",
                                                   "lambda_": "衰减系数 λ",
                                                   "alpha": "信任折损 α"}[x])
    n_pts = st.slider("采样点数", 5, 12, 8)

    if st.button("▶ 运行敏感性分析", type="primary", key="sens"):
        ranges = {
            "delta0":  [round(0.1 + 0.9 * i / (n_pts - 1), 2) for i in range(n_pts)],
            "lambda_": [round(0.01 + 0.49 * i / (n_pts - 1), 3) for i in range(n_pts)],
            "alpha":   [round(0.5 + 0.5 * i / (n_pts - 1), 2) for i in range(n_pts)],
        }
        vals = ranges[target]
        with st.spinner("运行中..."):
            sens = sensitivity_analysis(
                {**BASE_PARAMS, "intervention_config": INT_CFG}, target, vals, sim_steps
            )
            peaks = [extract_metrics(df)["peak_infected"] for df in sens.values()]
            st.session_state["sens_data"] = (vals, peaks, target)

    if "sens_data" in st.session_state:
        vals, peaks, tgt = st.session_state["sens_data"]
        label_map = {"delta0": "δ₀", "lambda_": "λ", "alpha": "α"}
        st.plotly_chart(
            sensitivity_bar(vals, peaks, label_map[tgt]),
            use_container_width=True
        )

# ════════════════ Tab4: 多次干预 ════════════════════════════
with tab4:
    st.subheader("多次干预叠加的边际递减效应（实验四）")
    n_times = st.slider("干预次数", 1, 5, 3)
    first_t = st.slider("首次干预时刻", 5, 50, 15, 5)
    gap = st.slider("每次干预间隔（步）", 5, 30, 10, 5)

    if st.button("▶ 运行多次干预", type="primary", key="multi"):
        intervals = [first_t] + [gap] * (n_times - 1)
        with st.spinner("运行中..."):
            df_multi, tpoints = multi_intervention_decay(
                {**BASE_PARAMS, "intervention_config": INT_CFG}, intervals, sim_steps
            )
            st.session_state["multi_data"] = (df_multi, tpoints)

    if "multi_data" in st.session_state:
        df_m, tps = st.session_state["multi_data"]
        st.plotly_chart(
            multi_intervention_chart(df_m, tps),
            use_container_width=True
        )
        st.info(f"干预触发时刻：{tps}  |  信任折损系数 α={alpha}，每次干预初始强度递减")

# ════════════════ Tab5: 网络快照 ════════════════════════════
with tab5:
    st.subheader("社交网络传播状态快照")
    snap_step = st.slider("查看第几步", 0, sim_steps, 30)

    if st.button("▶ 生成快照", type="primary", key="snap_btn"):
        with st.spinner("运行仿真..."):
            try:
                snap_n = min(n_agents, 300)  # 节点过多时图会很卡
                model = OpinionSpreadModel(
                    **{**BASE_PARAMS, "n_agents": snap_n,
                       "intervention_config": INT_CFG}
                )
                for _ in range(snap_step):
                    if model.running:
                        model.step()
                
                # 检查模型是否有必要的属性
                if not hasattr(model, 'G'):
                    st.error("模型缺少网络图 G 属性")
                    st.stop()
                
                st.session_state["snap"] = (model.G, model.get_agent_states(), snap_step)
                st.success("✅ 快照生成成功！")
                
            except Exception as e:
                st.error(f"生成快照时出错: {e}")
                import traceback
                st.code(traceback.format_exc())

    if "snap" in st.session_state and isinstance(st.session_state["snap"], tuple):
        try:
            G, states, sv = st.session_state["snap"]
            counts = {s: sum(1 for v in states.values() if v == s) for s in "SEIR"}
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("易感 S", counts["S"])
            c2.metric("潜伏 E", counts["E"])
            c3.metric("传播 I", counts["I"])
            c4.metric("恢复 R", counts["R"])
            st.plotly_chart(
                network_snapshot(G, states, f"第 {sv} 步网络状态"),
                use_container_width=True
            )
        except Exception as e:
            st.error(f"显示快照时出错: {e}")
            if st.button("清除快照数据"):
                st.session_state.pop("snap", None)
                st.rerun()
