import networkx as nx


def build_network(network_type: str, n: int, **kwargs) -> nx.Graph:
    """
    构建社交网络拓扑。

    network_type:
        "small_world"  — Watts-Strogatz小世界网络（默认推荐）
        "scale_free"   — Barabási-Albert无标度网络
        "random"       — Erdős-Rényi随机网络

    **kwargs 可覆盖各类型的默认参数：
        small_world: k=4（近邻数）, p=0.1（重连概率）
        scale_free:  m=2（每新节点的连边数）
        random:      p=0.05（连边概率）
    """
    if network_type == "small_world":
        k = kwargs.get("k", 4)
        p = kwargs.get("p", 0.1)
        G = nx.watts_strogatz_graph(n, k, p, seed=kwargs.get("seed", 42))

    elif network_type == "scale_free":
        m = kwargs.get("m", 2)
        G = nx.barabasi_albert_graph(n, m, seed=kwargs.get("seed", 42))

    elif network_type == "random":
        p = kwargs.get("p", 0.05)
        G = nx.erdos_renyi_graph(n, p, seed=kwargs.get("seed", 42))

    else:
        raise ValueError(f"不支持的网络类型: {network_type}")

    return G


def get_network_stats(G: nx.Graph) -> dict:
    """返回网络统计信息"""
    degrees = [d for _, d in G.degree()]
    return {
        "节点数": G.number_of_nodes(),
        "边数": G.number_of_edges(),
        "平均度": round(sum(degrees) / len(degrees), 2),
        "平均聚类系数": round(nx.average_clustering(G), 4),
        "是否连通": nx.is_connected(G),
    }
