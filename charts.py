"""
所有 Plotly 图表函数。
每个函数接收数据，返回 go.Figure，由 app.py 调用 st.plotly_chart() 展示。
"""

import plotly.graph_objects as go
import plotly.express as px
import networkx as nx

# 状态颜色与标签
STATE_COLOR = {"S": "#4CAF50", "E": "#FF9800", "I": "#F44336", "R": "#2196F3"}
STATE_LABEL = {"S": "易感者 S", "E": "潜伏者 E", "I": "传播者 I", "R": "恢复者 R"}
PALETTE = px.colors.qualitative.Set2


def seir_curve(df, title="SEIR 状态变化"):
    """SEIR各状态随时间变化的折线图"""
    fig = go.Figure()
    for state in ["S", "E", "I", "R"]:
        fig.add_trace(go.Scatter(
            x=df["step"], y=df[state],
            mode="lines", name=STATE_LABEL[state],
            line=dict(color=STATE_COLOR[state], width=2),
        ))
    fig.update_layout(
        title=title, xaxis_title="时间步", yaxis_title="Agent 数量",
        hovermode="x unified", legend=dict(orientation="h", y=-0.25),
    )
    return fig


def intervention_curve(df, title="干预效果衰减曲线"):
    """干预效果随时间的衰减曲线（带填充）"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["step"], y=df["Intervention"],
        mode="lines", fill="tozeroy", name="干预效果",
        line=dict(color="#9C27B0", width=2),
    ))
    fig.update_layout(
        title=title, xaxis_title="时间步", yaxis_title="干预效果值",
        yaxis=dict(range=[0, 1]),
    )
    return fig


def comparison_curve(results: dict, metric="I", title="对比分析"):
    """
    多方案对比折线图。
    results: {label: DataFrame}
    """
    fig = go.Figure()
    for i, (label, df) in enumerate(results.items()):
        fig.add_trace(go.Scatter(
            x=df["step"], y=df[metric],
            mode="lines", name=label,
            line=dict(color=PALETTE[i % len(PALETTE)], width=2),
        ))
    fig.update_layout(
        title=title, xaxis_title="时间步",
        yaxis_title=STATE_LABEL.get(metric, metric),
        hovermode="x unified",
    )
    return fig


def sensitivity_bar(param_values, metric_values, param_label, metric_label="峰值传播数"):
    """单参数敏感性柱状图"""
    fig = go.Figure(go.Bar(
        x=[str(v) for v in param_values],
        y=metric_values,
        marker_color="#F44336",
        text=[str(v) for v in metric_values],
        textposition="outside",
    ))
    fig.update_layout(
        title=f"{param_label} 敏感性分析",
        xaxis_title=param_label,
        yaxis_title=metric_label,
    )
    return fig


def network_snapshot(G: nx.Graph, agent_states: dict, title="网络状态快照"):
    """
    社交网络节点状态快照图。
    agent_states: {node_id: state}
    """
    # 节点布局（固定seed保证一致）
    pos = nx.spring_layout(G, seed=42, k=1.0 / (len(G) ** 0.5))

    fig = go.Figure()

    # 先画边（限制数量避免卡顿）
    max_edges = min(len(G.edges()), 1000)
    ex, ey = [], []
    for u, v in list(G.edges())[:max_edges]:
        x0, y0 = pos[u]; x1, y1 = pos[v]
        ex += [x0, x1, None]; ey += [y0, y1, None]
    fig.add_trace(go.Scatter(
        x=ex, y=ey, mode="lines",
        line=dict(color="#CCCCCC", width=0.5),
        hoverinfo="none", showlegend=False,
    ))

    # 按状态画节点
    for state, color in STATE_COLOR.items():
        nodes = [n for n, s in agent_states.items() if s == state]
        if not nodes:
            continue
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in nodes],
            y=[pos[n][1] for n in nodes],
            mode="markers", name=STATE_LABEL[state],
            marker=dict(color=color, size=7, opacity=0.85),
        ))

    fig.update_layout(
        title=title,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


def multi_intervention_chart(df, trigger_points: list, title="多次干预叠加效果"):
    """多次干预仿真结果，在干预时刻处添加竖线标注"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["step"], y=df["I"],
        mode="lines", name="传播者 I",
        line=dict(color="#F44336", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df["step"], y=df["Intervention"],
        mode="lines", name="干预效果",
        line=dict(color="#9C27B0", width=2, dash="dash"),
        yaxis="y2",
    ))
    for t in trigger_points:
        fig.add_vline(x=t, line=dict(color="orange", dash="dot", width=1.5),
                      annotation_text=f"干预@{t}", annotation_position="top right")
    fig.update_layout(
        title=title, xaxis_title="时间步",
        yaxis=dict(title="传播者数量"),
        yaxis2=dict(title="干预效果", overlaying="y", side="right", range=[0, 1]),
        legend=dict(orientation="h", y=-0.25),
    )
    return fig
