import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

ARCHS = ["Polyglot", "Graph", "Multimodel"]
COLORS = {"Polyglot": "#F56EA2", "Graph": "#14B8A6", "Multimodel": "#F59E0B"}
ARCH_LEGEND = {
    "Polyglot": "Polyglot (Postgres + Neo4j)",
    "Graph": "Graph (Neo4j)",
    "Multimodel": "Multimodel (ArangoDB)",
}
SHORT = {"Polyglot": "Polyglot", "Graph": "Graph", "Multimodel": "Multi"}

TASK_NAMES = {
    "t1": "Listagem filtrada",
    "t2": "Paginação + joins",
    "t3": "Processo completo",
    "t4": "Linha do tempo",
    "t5": "Co-participação",
    "t6": "Antes da abertura da empresa",
    "t7": "Versões de contrato",
    "t8": "Vencedoras x municípios",
    "t9": "Contrato x previsto",
    "t10": "Vencedor x menor cotação",
}

BG = "white"
INK = "#1F2433"
MUTED = "#6B7280"

sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": "white",
    "axes.edgecolor": "#E5E7EB",
    "grid.color": "#EEF0F4",
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "text.color": INK,
    "font.size": 10,
})

def task_label(task, short=False):
    name = TASK_NAMES.get(task, "")
    t = task.upper()
    return t if short or not name else f"{t} · {name}"

def fmt_ms(v):
    if v >= 1000:
        return f"{v / 1000:.2f} s"
    if v >= 100:
        return f"{v:.0f} ms"
    if v >= 1:
        return f"{v:.1f} ms"
    return f"{v:.3f} ms"

def ms_axis(ax, axis="y"):
    f = FuncFormatter(lambda v, _: fmt_ms(v) if v > 0 else "0")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)

def legend_handles():
    return [Patch(facecolor=COLORS[a], label=ARCH_LEGEND[a]) for a in ARCHS]

def finish(fig, path, show):
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  salvo: {path}")
    if show:
        plt.show()
    plt.close(fig)

def load(path):
    df = pd.read_csv(path)
    if "status" in df.columns:
        bad = df[df["status"] != "ok"]
        if len(bad):
            print(f"Aviso: {len(bad)} linhas com status != ok foram ignoradas.")
        df = df[df["status"] == "ok"]
    return df

def build_totals(df):
    rows = []
    for (task, arch), g in df.groupby(["task", "architecture"]):
        m = g.groupby("metric")["time_ms"].mean()
        if arch == "Polyglot":
            if "parallel_query" in m:
                total = m["parallel_query"]
            elif "ponte" in m:
                total = sum(m.get(k, 0.0) for k in ("neo4j", "ponte", "postgres"))
            else:
                total = m["postgres"]
        else:
            total = m.sum()
        rows.append({"task": task, "architecture": arch, "time_ms": total})
    tot = pd.DataFrame(rows)

    size = (df.dropna(subset=["response_size"]).groupby("task")["response_size"].first())
    tot["response_size"] = tot["task"].map(size)
    return tot

def task_order(tot):
    return sorted(tot["task"].unique(), key=lambda t: int(t[1:]))

def fig_per_task(tot, tasks, out, show):
    ncols = 3
    nrows = int(np.ceil(len(tasks) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(21, 4.9 * nrows))
    axes = np.atleast_2d(axes)

    for ax, task in zip(axes.flat, tasks):
        sub = tot[tot.task == task].set_index("architecture").reindex(ARCHS)
        vals = sub["time_ms"].to_numpy(dtype=float)
        bars = ax.bar(range(len(ARCHS)), vals, width=0.68,
                      color=[COLORS[a] for a in ARCHS],
                      edgecolor="white", linewidth=2, zorder=3)
        best = int(np.nanargmin(vals))
        for i, (b, v) in enumerate(zip(bars, vals)):
            if np.isnan(v):
                continue
            ax.annotate(fmt_ms(v) + (" ★" if i == best else ""),
                        (b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 5), textcoords="offset points",
                        ha="center", fontsize=9.5, fontweight="bold",
                        color=INK)
        ax.set_ylim(0, np.nanmax(vals) * 1.2)
        ax.set_xticks(range(len(ARCHS)))
        ax.set_xticklabels([SHORT[a] for a in ARCHS], fontsize=9.5)
        ms_axis(ax)
        ax.tick_params(axis="y", labelsize=8.5, length=0)
        ax.tick_params(axis="x", length=0)
        ax.grid(axis="x", visible=False)
        sns.despine(ax=ax, left=True)

    for ax in list(axes.flat)[len(tasks):]:
        ax.set_visible(False)

    fig.text(0.012, 1.005, "Cada gráfico tem escala própria  ·  ★ = mais rápido da task",
             fontsize=11, color=MUTED, ha="left")
    fig.legend(handles=legend_handles(), loc="lower center", ncol=3,
               frameon=False, fontsize=11, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0, 0.02, 1, 0.97), h_pad=2.5, w_pad=2)
    finish(fig, out, show)

def fig_overview_log(tot, tasks, out, show):
    fig, ax = plt.subplots(figsize=(18, 7))
    width = 0.26
    x = np.arange(len(tasks))
    for i, arch in enumerate(ARCHS):
        vals = [tot[(tot.task == t) & (tot.architecture == arch)]["time_ms"].sum()
                for t in tasks]
        pos = x + (i - 1) * width
        bars = ax.bar(pos, vals, width=width * 0.92, color=COLORS[arch],
                      label=ARCH_LEGEND[arch], edgecolor="white", linewidth=1.2,
                      zorder=3)
        for b, v in zip(bars, vals):
            ax.annotate(fmt_ms(v), (b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7.5, rotation=90,
                        color=INK)
    ax.set_yscale("log")
    ax.set_ylim(top=ax.get_ylim()[1] * 2.2)
    ms_axis(ax)
    ax.set_xticks(x)
    ax.set_xticklabels([task_label(t, short=True) for t in tasks], fontsize=11,
                       fontweight="bold")
    ax.set_ylabel("Tempo (escala log)")
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)
    sns.despine(ax=ax, left=True)
    ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=11)
    fig.tight_layout()
    finish(fig, out, show)

def fig_polyglot_breakdown(df, out, show):
    poly = df[df.architecture == "Polyglot"]
    piv = poly.groupby(["task", "metric"])["time_ms"].mean().unstack()
    tasks = [t for t in task_order(poly) if "neo4j" in piv.columns
             and pd.notna(piv.loc[t].get("neo4j"))]
    if not tasks:
        print("  (sem dados de Neo4j no Polyglot; pulando gráfico 4)")
        return

    comp_colors = {
        "Neo4j · execução no servidor": "#8B5CF6",
        "Neo4j · rede / driver": "#C4B5FD",
        "Ponte (transferência)": "#F472B6",
        "Postgres": "#3B82F6",
    }
    fig, ax = plt.subplots(figsize=(14, 1.15 * len(tasks) + 2.6))
    for y, t in enumerate(tasks):
        r = piv.loc[t]
        neo = r.get("neo4j", 0.0)
        srv = r.get("neo4j_server", np.nan)
        srv = neo if pd.isna(srv) else min(srv, neo)
        parallel = pd.notna(r.get("parallel_query"))
        comps = {
            "Neo4j · execução no servidor": srv,
            "Neo4j · rede / driver": neo - srv,
            "Ponte (transferência)": 0.0 if parallel else (r.get("ponte", 0.0) or 0.0),
            "Postgres": 0.0 if parallel else (r.get("postgres", 0.0) or 0.0),
        }
        total_shown = sum(comps.values())
        total = r["parallel_query"] if parallel else total_shown
        left = 0.0
        for name, v in comps.items():
            w = v / total_shown * 100
            if w <= 0:
                continue
            ax.barh(y, w, left=left, color=comp_colors[name], edgecolor="white",
                    linewidth=2, height=0.62, zorder=3)
            if w >= 7:
                dark = name.startswith("Neo4j · exec") or name == "Postgres"
                ax.text(left + w / 2, y, fmt_ms(v), ha="center", va="center",
                        fontsize=9, fontweight="bold",
                        color="white" if dark else INK)
            left += w
        note = f"total {fmt_ms(total)}"
        if parallel:
            note += f"   (Postgres em paralelo: {fmt_ms(r['postgres'])})"
        ax.text(101, y, note, va="center", fontsize=10, color=INK)

    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels([task_label(t) for t in tasks], fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", visible=False)
    ax.tick_params(length=0)
    sns.despine(ax=ax, left=True, bottom=True)
    ax.legend(handles=[Patch(facecolor=c, label=n) for n, c in comp_colors.items()],
              loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=4,
              frameon=False, fontsize=10)
    fig.tight_layout()
    finish(fig, out, show)

def fig_summary(tot, tasks, out, show):
    fig, axes = plt.subplots(1, 3, figsize=(20, 6.2),
                             gridspec_kw={"width_ratios": [1, 1, 1.5]})

    ax = axes[0]
    sums = tot.groupby("architecture")["time_ms"].sum().reindex(ARCHS)
    bars = ax.bar(range(3), sums.values, width=0.62,
                  color=[COLORS[a] for a in ARCHS], edgecolor="white",
                  linewidth=2, zorder=3)
    for b, v in zip(bars, sums.values):
        ax.annotate(fmt_ms(v), (b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 5), textcoords="offset points", ha="center",
                    fontsize=12, fontweight="bold")
    ax.set_xticks(range(3))
    ax.set_xticklabels([SHORT[a] for a in ARCHS], fontsize=11)
    ax.set_ylim(0, sums.max() * 1.15)
    ms_axis(ax)
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)
    sns.despine(ax=ax, left=True)

    ax = axes[1]
    winners = (tot.loc[tot.groupby("task")["time_ms"].idxmin()]
               ["architecture"].value_counts().reindex(ARCHS).fillna(0).astype(int))
    bars = ax.bar(range(3), winners.values, width=0.62,
                  color=[COLORS[a] for a in ARCHS], edgecolor="white",
                  linewidth=2, zorder=3)
    for b, v in zip(bars, winners.values):
        ax.annotate(str(v), (b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 5), textcoords="offset points", ha="center",
                    fontsize=14, fontweight="bold")
    ax.set_xticks(range(3))
    ax.set_xticklabels([SHORT[a] for a in ARCHS], fontsize=11)
    ax.set_ylim(0, max(winners.max() * 1.25, 1))
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)
    sns.despine(ax=ax, left=True)

    ax = axes[2]
    for arch in ARCHS:
        s = tot[(tot.architecture == arch)].dropna(subset=["response_size"])
        ax.scatter(s["response_size"], s["time_ms"], s=170, color=COLORS[arch],
                   edgecolor="white", linewidth=1.8, alpha=0.95, zorder=3,
                   label=ARCH_LEGEND[arch])
        for _, r in s.iterrows():
            ax.annotate(r["task"].upper(), (r["response_size"], r["time_ms"]),
                        xytext=(7, 5), textcoords="offset points", fontsize=8,
                        color=MUTED)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ms_axis(ax)
    ax.set_xlabel("Tamanho da resposta (response_size, log)")
    ax.set_ylabel("Tempo (log)")
    ax.legend(frameon=False, fontsize=9.5, loc="lower right")
    ax.tick_params(length=0)
    sns.despine(ax=ax)

    fig.tight_layout()
    finish(fig, out, show)

def find_latest_metrics():
    here = Path(__file__).resolve().parent
    for logs in (here.parent / "logs", here / "logs", Path.cwd() / "logs"):
        if not logs.is_dir():
            continue
        runs = sorted((d for d in logs.iterdir()
                       if d.is_dir() and (d / "metrics.csv").exists()),
                      key=lambda d: d.name, reverse=True)
        if runs:
            return runs[0] / "metrics.csv"
    return None

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=None, help="caminho do metrics.csv (padrão: logs/<pasta mais recente>/metrics.csv)")
    ap.add_argument("--out", default="graficos", help="pasta de saída")
    ap.add_argument("--show", action="store_true", help="abre as janelas dos gráficos")
    args = ap.parse_args()

    if args.csv is None:
        args.csv = find_latest_metrics()
        if args.csv is None:
            ap.error("nenhum logs/<timestamp>/metrics.csv encontrado; "
                    "passe o caminho do CSV como argumento")
        print(f"Usando: {args.csv}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = load(args.csv)
    tot = build_totals(df)
    tasks = task_order(tot)

    tot.pivot(index="task", columns="architecture", values="time_ms") \
       .reindex(index=tasks, columns=ARCHS).round(3).to_csv(out / "resumo_tempos.csv")

    print("Gerando gráficos...")
    fig_per_task(tot, tasks, out / "1_tempo_por_task.png", args.show)
    fig_overview_log(tot, tasks, out / "2_visao_geral_log.png", args.show)
    fig_polyglot_breakdown(df, out / "3_composicao_polyglot.png", args.show)
    fig_summary(tot, tasks, out / "4_resumo.png", args.show)
    print("Pronto.")

if __name__ == "__main__":
    main()