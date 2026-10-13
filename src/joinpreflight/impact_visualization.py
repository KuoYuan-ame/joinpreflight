"""A single publication-style monetary inflation comparison chart."""
from __future__ import annotations

from pathlib import Path


def render_impact_figure(summary: dict, output_prefix: str | Path, currency: str = "BRL") -> dict:
    """Export a high-resolution PNG and vector PDF for metric inflation."""
    # Lazy import: users doing JOIN-only analysis need no matplotlib install.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    correct = float(summary["correct_payment_total"])
    extra = float(summary["inflation_amount"])
    naive = float(summary["naive_payment_total"])
    rate = summary["inflation_rate_pct"]

    fig, ax = plt.subplots(figsize=(10.7, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    blue = "#337DA0"
    pale = "#DDE7EC"
    orange = "#DF7446"
    ink = "#183550"

    ax.barh(1, correct, height=0.35, color=blue, label="Order-level total")
    ax.barh(0, correct, height=0.35, color=blue)
    if extra > 0:
        ax.barh(0, extra, left=correct, height=0.35, color=orange,
                label="Duplicated payment amount")
    ax.set_yticks([0, 1], ["Naive post-JOIN SUM", "Correct order-level SUM"])
    ax.set_xlim(0, max(naive, correct, 1) * 1.21)
    ax.set_ylim(-0.6, 1.55)
    ax.set_xlabel(f"Payment value ({currency})", color=ink)
    ax.tick_params(axis="y", colors=ink, length=0, pad=12)
    ax.tick_params(axis="x", colors="#5D7185")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.grid(axis="x", color="#E5EDF2", lw=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    offset = max(naive, correct, 1) * 0.015
    ax.text(correct + offset, 1, f"{correct:,.2f}", va="center", fontsize=11, color=ink)
    ax.text(naive + offset, 0, f"{naive:,.2f}", va="center", fontsize=11, color=ink)
    rate_label = f"{rate:.2f}%" if rate is not None else "undefined (zero baseline)"
    fig.suptitle("JoinPreflight  |  Payment Metric Inflation",
                 fontsize=16, color=ink, weight="bold", y=0.965)
    ax.set_title(f"Overcount: +{extra:,.2f} {currency}   |   Inflation: {rate_label}",
                 loc="left", fontsize=11, color=orange, pad=18)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.text(0.055, 0.025,
             "Method: sum payments per order first; then simulate LEFT JOIN duplication by item count.\n"
             "Payment metric is not accounting-recognized revenue.",
             color="#62768A", size=9, va="bottom")
    fig.subplots_adjust(left=0.26, right=0.94, top=0.74, bottom=0.22)

    prefix = Path(output_prefix)
    if prefix.suffix:
        raise ValueError("--figure expects a prefix without an extension")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    png = prefix.with_suffix(".png").resolve()
    pdf = prefix.with_suffix(".pdf").resolve()
    try:
        fig.savefig(png, dpi=220, facecolor="white")
        fig.savefig(pdf, facecolor="white")
    finally:
        plt.close(fig)
    return {"png": png, "pdf": pdf}
