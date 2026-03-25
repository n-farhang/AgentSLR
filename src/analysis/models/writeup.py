# src/analysis/models/writeup.py
# utils/models_report_utils.py

import re
import textwrap
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
import seaborn as sns

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    Image, PageBreak, KeepTogether, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER


plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 13,
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'xtick.major.size': 4,
    'ytick.major.size': 4,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': False,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'savefig.facecolor': 'white',
    'savefig.edgecolor': 'white',
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

LANCET_COLORS = {
    'primary': '#1B4F72',
    'secondary': '#2E86AB',
    'tertiary': '#A23B72',
    'quaternary': '#F18F01',
    'quinary': '#C73E1D',
    'success': '#2D6A4F',
    'neutral': '#6C757D',
    'light': '#ADB5BD',
}

LANCET_PALETTE = [
    '#1B4F72', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#2D6A4F', '#7B2CBF', '#E07A5F', '#3D405B', '#81B29A',
    '#F2CC8F', '#6D597A', '#B56576', '#355070', '#EAAC8B'
]

COLUMN_DISPLAY_NAMES = {
    'model_type': 'Model Type',
    'compartmental_type': 'Compartmental Structure',
    'stoch_deter': 'Formulation',
    'transmission_route': 'Transmission Route',
    'spatial_model': 'Spatial Scale',
    'interventions_type': 'Interventions Modelled',
    'code_available': 'Code Available',
    'coding_language': 'Programming Language',
    'article_id': 'Article ID',
    'model_index': 'Model Index',
    'spillover_included': 'Spillover Included',
    'uncertainty_was_considered': 'Uncertainty Quantified',
    'theoretical_model': 'Theoretical Model',
    'is_data_used_available': 'Empirical Data Used',
    'assumptions': 'Key Assumptions',
    'n': 'Count',
    '%': 'Proportion',
    'interventions_type (split)': 'Intervention Type',
    'assumptions (split)': 'Assumption',
}


@dataclass
class FigureManifest:
    path: str
    title: str
    caption: str
    figure_number: int
    panels: List[str] = field(default_factory=list)
    data_source: str = ""
    n_observations: int = 0


@dataclass
class TableManifest:
    title: str
    table_number: int
    columns: List[str]
    n_rows: int
    caption: str
    data_source: str = ""


@dataclass
class ContentManifest:
    pathogen: str
    generated_at: str
    figures: List[FigureManifest] = field(default_factory=list)
    tables: List[TableManifest] = field(default_factory=list)
    narrative_sections: List[str] = field(default_factory=list)
    summary_statistics: Dict[str, Any] = field(default_factory=dict)


def get_display_name(col: str) -> str:
    return COLUMN_DISPLAY_NAMES.get(col, col.replace('_', ' ').title())


def norm_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def boolish(x):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    s = norm_str(x).lower()
    if s in {"true", "t", "1", "yes", "y"}:
        return True
    if s in {"false", "f", "0", "no", "n"}:
        return False
    return None


def split_multi(s):
    s = norm_str(s)
    if not s:
        return []
    if s.lower() in {"unspecified", "not available", "na", "n/a"}:
        return []
    parts = [p.strip() for p in re.split(r"\s*;\s*|\s*\|\s*|,\s*", s) if p.strip()]
    out = []
    for p in parts:
        if p.lower() in {"unspecified", "not available", "na", "n/a"}:
            continue
        out.append(p)
    return out


def yesish_data_used(s):
    s = norm_str(s)
    if not s:
        return None
    if s.lower().startswith("yes"):
        return True
    if s.lower() in {"not available", "no", "unspecified"}:
        return False
    return None


def topk_with_other(counter, k=10, other_label="Other"):
    items = counter.most_common()
    if len(items) <= k:
        return items
    top = items[:k]
    rest = sum(v for _, v in items[k:])
    return top + [(other_label, rest)]


def wrap_label(text, width=15):
    if len(text) <= width:
        return text
    return '\n'.join(textwrap.wrap(text, width=width))


def wrap_labels(labels, width=15):
    return [wrap_label(str(l), width) for l in labels]


def add_panel_label(ax, label, x=-0.12, y=1.08):
    ax.text(x, y, label, transform=ax.transAxes, fontsize=14, fontweight='bold',
            va='top', ha='left')


def style_axis(ax, xlabel=None, ylabel=None, title=None):
    if xlabel:
        ax.set_xlabel(xlabel, fontweight='medium')
    if ylabel:
        ax.set_ylabel(ylabel, fontweight='medium')
    if title:
        ax.set_title(title, fontweight='medium', pad=10)
    ax.tick_params(axis='both', which='major', direction='out')
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, nbins=6))


def pct(n, d):
    if d == 0:
        return "0.0%"
    return f"{(100.0*n/d):.1f}%"


def save_bar_lancet(counts, title, outpath, xlabel=None, ylabel="Count",
                    max_labels=12, wrap_width=18, panel_label=None, figsize=(8, 5)):
    labels = [k for k, _ in counts]
    values = [v for _, v in counts]
    if len(labels) > max_labels:
        labels = labels[:max_labels]
        values = values[:max_labels]

    wrapped_labels = wrap_labels(labels, width=wrap_width)
    colors_list = LANCET_PALETTE[:len(labels)]

    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    bars = ax.bar(range(len(labels)), values, color=colors_list, edgecolor='white', linewidth=0.5)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(wrapped_labels, rotation=45, ha='right', rotation_mode='anchor')

    style_axis(ax, xlabel=xlabel, ylabel=ylabel, title=title)

    ax.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.annotate(f'{val}', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                        xytext=(0, 3), textcoords='offset points', ha='center', va='bottom',
                        fontsize=8, color='#333333')

    if panel_label:
        add_panel_label(ax, panel_label)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)


def save_horizontal_bar_lancet(counts, title, outpath, xlabel="Count", ylabel=None,
                               max_labels=12, wrap_width=25, panel_label=None, figsize=(8, 6)):
    labels = [k for k, _ in counts]
    values = [v for _, v in counts]
    if len(labels) > max_labels:
        labels = labels[:max_labels]
        values = values[:max_labels]

    wrapped_labels = wrap_labels(labels, width=wrap_width)
    colors_list = LANCET_PALETTE[:len(labels)]

    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=colors_list, edgecolor='white', linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(wrapped_labels)
    ax.invert_yaxis()

    style_axis(ax, xlabel=xlabel, ylabel=ylabel, title=title)

    ax.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    for bar, val in zip(bars, values):
        ax.annotate(f'{val}', xy=(bar.get_width(), bar.get_y() + bar.get_height()/2),
                    xytext=(3, 0), textcoords='offset points', ha='left', va='center',
                    fontsize=8, color='#333333')

    if panel_label:
        add_panel_label(ax, panel_label)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)


def save_stacked_bar_lancet(category_to_counts, title, outpath, x_label="Group",
                            y_label="Count", wrap_width=12, panel_label=None):
    groups = list(category_to_counts.keys())
    series = sorted({s for g in groups for s in category_to_counts[g].keys()})
    colors_list = LANCET_PALETTE[:len(series)]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    bottoms = np.zeros(len(groups))
    for i, s in enumerate(series):
        vals = np.array([category_to_counts[g].get(s, 0) for g in groups])
        ax.bar(groups, vals, bottom=bottoms, color=colors_list[i], edgecolor='white',
               linewidth=0.5, label=wrap_label(s, 20))
        bottoms += vals

    wrapped_groups = wrap_labels(groups, width=wrap_width)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(wrapped_groups, rotation=45, ha='right', rotation_mode='anchor')

    style_axis(ax, xlabel=x_label, ylabel=y_label, title=title)

    ax.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    ax.legend(frameon=True, fancybox=False, edgecolor='#cccccc',
              fontsize=8, loc='upper right', ncol=min(2, len(series)))

    if panel_label:
        add_panel_label(ax, panel_label)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)


def save_pie_chart_lancet(data: List[Tuple[str, int]], title: str, outpath: Path,
                          panel_label: str = None, figsize: Tuple[float, float] = (6, 6)):
    labels = [k for k, _ in data]
    values = [v for _, v in data]
    colors_list = LANCET_PALETTE[:len(labels)]
    
    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors_list,
        autopct='%1.1f%%', startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5},
        textprops={'fontsize': 9}
    )
    
    for autotext in autotexts:
        autotext.set_fontsize(8)
        autotext.set_fontweight('medium')
    
    ax.set_title(title, fontweight='medium', pad=10)
    
    if panel_label:
        add_panel_label(ax, panel_label, x=-0.1, y=1.05)
    
    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)


def save_combined_overview(tables, pathogen, outpath, n_models) -> FigureManifest:
    fig = plt.figure(figsize=(14, 10), dpi=300)
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.25)

    ax1 = fig.add_subplot(gs[0, 0])
    model_data = [(r["model_type"], int(r["n"])) for _, r in tables["model_type"].iterrows()]
    labels = [wrap_label(k, 15) for k, _ in model_data]
    values = [v for _, v in model_data]
    colors_list = LANCET_PALETTE[:len(labels)]
    ax1.bar(range(len(labels)), values, color=colors_list, edgecolor='white', linewidth=0.5)
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, rotation=45, ha='right', rotation_mode='anchor')
    style_axis(ax1, ylabel="Number of models", title="Model Types")
    ax1.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax1.set_axisbelow(True)
    add_panel_label(ax1, "A")

    ax2 = fig.add_subplot(gs[0, 1])
    stoch_data = [(r["stoch_deter"], int(r["n"])) for _, r in tables["stoch"].iterrows()]
    labels2 = [k for k, _ in stoch_data]
    values2 = [v for _, v in stoch_data]
    colors2 = [LANCET_COLORS['primary'], LANCET_COLORS['secondary'], LANCET_COLORS['neutral']][:len(labels2)]
    ax2.bar(range(len(labels2)), values2, color=colors2, edgecolor='white', linewidth=0.5)
    ax2.set_xticks(range(len(labels2)))
    ax2.set_xticklabels(labels2)
    style_axis(ax2, ylabel="Number of models", title="Stochastic vs Deterministic")
    ax2.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax2.set_axisbelow(True)
    add_panel_label(ax2, "B")

    ax3 = fig.add_subplot(gs[1, 0])
    route_data = [(r["transmission_route"], int(r["n"])) for _, r in tables["route"].iterrows()][:6]
    labels3 = [wrap_label(k, 20) for k, _ in route_data]
    values3 = [v for _, v in route_data]
    colors3 = LANCET_PALETTE[:len(labels3)]
    ax3.barh(range(len(labels3)), values3, color=colors3, edgecolor='white', linewidth=0.5)
    ax3.set_yticks(range(len(labels3)))
    ax3.set_yticklabels(labels3)
    ax3.invert_yaxis()
    style_axis(ax3, xlabel="Number of models", title="Transmission Routes")
    ax3.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax3.set_axisbelow(True)
    add_panel_label(ax3, "C")

    ax4 = fig.add_subplot(gs[1, 1])
    if len(tables["code"]):
        code_data = [(r["code_available"], int(r["n"])) for _, r in tables["code"].iterrows()]
        labels4 = ["Available" if k == "True" else "Not available" for k, _ in code_data]
        values4 = [v for _, v in code_data]
        colors4 = [LANCET_COLORS['success'], LANCET_COLORS['neutral']]
        ax4.pie(values4, labels=labels4, colors=colors4,
                autopct='%1.1f%%', startangle=90,
                wedgeprops={'edgecolor': 'white', 'linewidth': 1})
        ax4.set_title("Code Availability", fontweight='medium', pad=10)
    add_panel_label(ax4, "D")

    fig.suptitle(f"{pathogen}: Extracted Transmission Models", fontsize=14, fontweight='bold', y=0.98)

    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    return FigureManifest(
        path=str(outpath),
        title=f"{pathogen}: Extracted Transmission Models Overview",
        figure_number=1,
        panels=[
            "Distribution of model types",
            "Stochastic versus deterministic formulation",
            "Transmission routes modelled",
            "Source code availability"
        ],
        caption=(
            f"Overview of {n_models} transmission models extracted for {pathogen}. "
            f"(A) Distribution of model architectures. "
            f"(B) Classification by stochastic or deterministic formulation. "
            f"(C) Primary transmission routes incorporated. "
            f"(D) Proportion of models with publicly available source code."
        ),
        n_observations=n_models
    )


def save_interventions_assumptions(tables, pathogen, outpath, n_models) -> FigureManifest:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)

    inter_data = [(r["interventions_type (split)"], int(r["n"]))
                  for _, r in tables["interventions"].iterrows()][:10]
    labels1 = [wrap_label(k, 18) for k, _ in inter_data]
    values1 = [v for _, v in inter_data]
    colors1 = LANCET_PALETTE[:len(labels1)]

    y_pos1 = range(len(labels1))
    bars1 = ax1.barh(y_pos1, values1, color=colors1, edgecolor='white', linewidth=0.5)
    ax1.set_yticks(y_pos1)
    ax1.set_yticklabels(labels1)
    ax1.invert_yaxis()
    style_axis(ax1, xlabel="Number of models", title="Interventions Modelled")
    ax1.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax1.set_axisbelow(True)
    add_panel_label(ax1, "A")

    for bar, val in zip(bars1, values1):
        ax1.annotate(f'{val}', xy=(bar.get_width(), bar.get_y() + bar.get_height()/2),
                     xytext=(3, 0), textcoords='offset points', ha='left', va='center',
                     fontsize=8, color='#333333')

    assump_data = [(r["assumptions (split)"], int(r["n"]))
                   for _, r in tables["assumptions"].iterrows()][:10]
    labels2 = [wrap_label(k, 25) for k, _ in assump_data]
    values2 = [v for _, v in assump_data]
    colors2 = LANCET_PALETTE[:len(labels2)]

    y_pos2 = range(len(labels2))
    bars2 = ax2.barh(y_pos2, values2, color=colors2, edgecolor='white', linewidth=0.5)
    ax2.set_yticks(y_pos2)
    ax2.set_yticklabels(labels2)
    ax2.invert_yaxis()
    style_axis(ax2, xlabel="Number of models", title="Model Assumptions")
    ax2.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax2.set_axisbelow(True)
    add_panel_label(ax2, "B")

    for bar, val in zip(bars2, values2):
        ax2.annotate(f'{val}', xy=(bar.get_width(), bar.get_y() + bar.get_height()/2),
                     xytext=(3, 0), textcoords='offset points', ha='left', va='center',
                     fontsize=8, color='#333333')

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    return FigureManifest(
        path=str(outpath),
        title="Interventions and Model Assumptions",
        figure_number=2,
        panels=[
            "Types of interventions modelled",
            "Common modelling assumptions"
        ],
        caption=(
            f"Interventions and assumptions in extracted {pathogen} transmission models (n={n_models}). "
            f"(A) Frequency of intervention types evaluated across models. "
            f"(B) Common modelling assumptions. "
            f"Categories are not mutually exclusive; individual models may incorporate multiple interventions or assumptions."
        ),
        n_observations=n_models
    )


def save_temporal_distribution(df, pathogen, outpath) -> Optional[FigureManifest]:
    if 'publication_year' not in df.columns:
        return None
    
    year_counts = df['publication_year'].value_counts().sort_index()
    
    if len(year_counts) < 2:
        return None
    
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    
    years = year_counts.index.astype(int)
    counts = year_counts.values
    
    ax.bar(years, counts, color=LANCET_COLORS['primary'], edgecolor='white', linewidth=0.5, width=0.8)
    
    ax.set_xlabel('Publication year', fontweight='medium')
    ax.set_ylabel('Number of models', fontweight='medium')
    ax.set_title(f'{pathogen}: Temporal Distribution of Extracted Models', fontweight='medium', pad=10)
    
    ax.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)
    
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    
    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    return FigureManifest(
        path=str(outpath),
        title=f"{pathogen}: Temporal Distribution",
        figure_number=3,
        panels=["Annual count of extracted transmission models"],
        caption=(
            f"Temporal distribution of {pathogen} transmission model publications included in the extraction, "
            f"spanning {int(min(years))} to {int(max(years))} (n={int(sum(counts))})."
        ),
        n_observations=int(sum(counts))
    )


def save_compartmental_breakdown(df, pathogen, outpath) -> Optional[FigureManifest]:
    if 'compartmental_type' not in df.columns:
        return None
    
    comp_counts = Counter([norm_str(x) for x in df['compartmental_type'].fillna("").tolist() if norm_str(x) and norm_str(x).lower() != "unspecified"])
    
    if not comp_counts:
        return None
    
    data = comp_counts.most_common(10)
    
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
    
    labels = [wrap_label(k, 15) for k, _ in data]
    values = [v for _, v in data]
    colors_list = LANCET_PALETTE[:len(labels)]
    
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors_list,
        autopct='%1.1f%%', startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5},
        textprops={'fontsize': 9}
    )
    
    ax.set_title(f'{pathogen}: Compartmental Model Structures', fontweight='medium', pad=10)
    
    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    return FigureManifest(
        path=str(outpath),
        title=f"{pathogen}: Compartmental Model Structures",
        figure_number=4,
        panels=["Distribution of compartmental model structures"],
        caption=(
            f"Distribution of compartmental model structures among extracted {pathogen} transmission models "
            f"(n={sum(values)}). The most common structure was {data[0][0]} ({pct(data[0][1], sum(values))})."
        ),
        n_observations=sum(values)
    )


def md_table_with_display_names(df):
    df_display = df.copy()
    df_display.columns = [get_display_name(c) for c in df_display.columns]
    try:
        return df_display.to_markdown(index=False)
    except Exception:
        return df_display.to_string(index=False)


def build_summary_tables(df) -> Tuple[Dict[str, pd.DataFrame], Dict[str, TableManifest]]:
    n_models = len(df)
    n_articles = df["article_id"].nunique() if "article_id" in df.columns else np.nan
    
    table_manifests = {}

    def freq(col, k=None):
        c = Counter([norm_str(x) for x in df[col].fillna("").tolist() if norm_str(x)])
        if k is None:
            items = c.most_common()
        else:
            items = topk_with_other(c, k=k)
        out = []
        for name, count in items:
            out.append([name, int(count), pct(count, n_models)])
        return pd.DataFrame(out, columns=[col, "n", "%"])

    overview = pd.DataFrame(
        [
            ["Models extracted", int(n_models)],
            ["Source articles", int(n_articles) if pd.notna(n_articles) else ""],
        ],
        columns=["Metric", "Value"],
    )

    model_type = freq("model_type")
    table_manifests["model_type"] = TableManifest(
        title="Model Types",
        table_number=1,
        columns=["Model Type", "Count", "Proportion"],
        n_rows=len(model_type),
        caption=f"Distribution of model architectures across {n_models} extracted transmission models."
    )
    
    stoch = freq("stoch_deter")
    table_manifests["stoch"] = TableManifest(
        title="Model Formulation",
        table_number=2,
        columns=["Formulation", "Count", "Proportion"],
        n_rows=len(stoch),
        caption=f"Classification of extracted models by stochastic versus deterministic formulation (n={n_models})."
    )
    
    route = freq("transmission_route")
    table_manifests["route"] = TableManifest(
        title="Transmission Routes",
        table_number=3,
        columns=["Transmission Route", "Count", "Proportion"],
        n_rows=len(route),
        caption=f"Primary transmission routes incorporated in extracted models (n={n_models})."
    )
    
    spatial = freq("spatial_model")

    spillover = pd.DataFrame(
        [["Yes", int((df["spillover_included"] == True).sum()), pct(int((df["spillover_included"] == True).sum()), n_models)],
         ["No", int((df["spillover_included"] == False).sum()), pct(int((df["spillover_included"] == False).sum()), n_models)]],
        columns=["spillover_included", "n", "%"],
    ) if "spillover_included" in df.columns else pd.DataFrame(columns=["spillover_included", "n", "%"])

    uncertainty = pd.DataFrame(
        [["Yes", int((df["uncertainty_was_considered"] == True).sum()), pct(int((df["uncertainty_was_considered"] == True).sum()), n_models)],
         ["No", int((df["uncertainty_was_considered"] == False).sum()), pct(int((df["uncertainty_was_considered"] == False).sum()), n_models)]],
        columns=["uncertainty_was_considered", "n", "%"],
    ) if "uncertainty_was_considered" in df.columns else pd.DataFrame(columns=["uncertainty_was_considered", "n", "%"])

    theoretical = pd.DataFrame(
        [["Yes", int((df["theoretical_model"] == True).sum()), pct(int((df["theoretical_model"] == True).sum()), n_models)],
         ["No", int((df["theoretical_model"] == False).sum()), pct(int((df["theoretical_model"] == False).sum()), n_models)]],
        columns=["theoretical_model", "n", "%"],
    ) if "theoretical_model" in df.columns else pd.DataFrame(columns=["theoretical_model", "n", "%"])

    code = pd.DataFrame(
        [["Yes", int((df["code_available"] == True).sum()), pct(int((df["code_available"] == True).sum()), n_models)],
         ["No", int((df["code_available"] == False).sum()), pct(int((df["code_available"] == False).sum()), n_models)]],
        columns=["code_available", "n", "%"],
    ) if "code_available" in df.columns else pd.DataFrame(columns=["code_available", "n", "%"])
    
    table_manifests["code"] = TableManifest(
        title="Code Availability",
        table_number=6,
        columns=["Code Available", "Count", "Proportion"],
        n_rows=len(code),
        caption=f"Availability of publicly accessible source code for extracted models (n={n_models})."
    )

    language = freq("coding_language") if "coding_language" in df.columns else pd.DataFrame(columns=["coding_language", "n", "%"])
    table_manifests["language"] = TableManifest(
        title="Programming Languages",
        table_number=7,
        columns=["Programming Language", "Count", "Proportion"],
        n_rows=len(language),
        caption=f"Programming languages used for model implementation (n={n_models})."
    )

    data_used = pd.DataFrame(
        [["Yes", int((df["data_used_bool"] == True).sum()), pct(int((df["data_used_bool"] == True).sum()), n_models)],
         ["No/Unspecified", int((df["data_used_bool"] == False).sum()), pct(int((df["data_used_bool"] == False).sum()), n_models)]],
        columns=["is_data_used_available", "n", "%"],
    ) if "data_used_bool" in df.columns else pd.DataFrame(columns=["is_data_used_available", "n", "%"])

    inter_counts = Counter()
    for s in df.get("interventions_type", pd.Series(dtype=str)).fillna("").astype(str).tolist():
        for p in split_multi(s):
            inter_counts[p] += 1
    interventions = pd.DataFrame(
        [[k, int(v), pct(v, n_models)] for k, v in topk_with_other(inter_counts, k=12)],
        columns=["interventions_type (split)", "n", "%"],
    )
    table_manifests["interventions"] = TableManifest(
        title="Interventions Modelled",
        table_number=4,
        columns=["Intervention Type", "Count", "Proportion"],
        n_rows=len(interventions),
        caption=f"Types of interventions evaluated in extracted models. Categories are not mutually exclusive (n={n_models})."
    )

    assump_counts = Counter()
    for s in df.get("assumptions", pd.Series(dtype=str)).fillna("").astype(str).tolist():
        for p in split_multi(s):
            assump_counts[p] += 1
    assumptions = pd.DataFrame(
        [[k, int(v), pct(v, n_models)] for k, v in topk_with_other(assump_counts, k=12)],
        columns=["assumptions (split)", "n", "%"],
    )
    table_manifests["assumptions"] = TableManifest(
        title="Model Assumptions",
        table_number=5,
        columns=["Assumption", "Count", "Proportion"],
        n_rows=len(assumptions),
        caption=f"Common modelling assumptions. Categories are not mutually exclusive (n={n_models})."
    )

    tables = {
        "overview": overview,
        "model_type": model_type,
        "stoch": stoch,
        "route": route,
        "spatial": spatial,
        "spillover": spillover,
        "uncertainty": uncertainty,
        "theoretical": theoretical,
        "data_used": data_used,
        "code": code,
        "language": language,
        "interventions": interventions,
        "assumptions": assumptions,
    }
    
    return tables, table_manifests


def build_inventory_table(df, max_rows=10):
    cols = [
        "article_id",
        "model_type",
        "compartmental_type",
        "stoch_deter",
        "transmission_route",
        "spatial_model",
        "code_available",
        "coding_language",
    ]
    keep = [c for c in cols if c in df.columns]
    inv = df[keep].copy()
    if len(inv) > max_rows:
        inv = inv.head(max_rows).copy()
    inv.columns = [get_display_name(c) for c in inv.columns]
    return inv


def pick_top(df, name_col, exclude=None):
    if df is None or len(df) == 0:
        return None, None, None
    ex = set([e.lower() for e in (exclude or [])])
    for _, r in df.iterrows():
        name = str(r[name_col])
        if name.lower() in ex:
            continue
        return name, int(r["n"]), str(r["%"])
    return None, None, None


def top_list_with_pct(df, name_col, n_models, k=3, exclude=None):
    if df is None or len(df) == 0:
        return "unspecified"
    ex = set([e.lower() for e in (exclude or [])])
    items = []
    for _, r in df.iterrows():
        name = str(r[name_col])
        if name.lower() in ex:
            continue
        n = int(r["n"])
        items.append(f"{name} ({pct(n, n_models)})")
        if len(items) >= k:
            break
    return ", ".join(items) if items else "unspecified"


def build_narrative(pathogen: str, n_models: int, n_articles: int, tables: Dict[str, pd.DataFrame]) -> Dict[str, str]:
    top_model_type, top_model_n, top_model_type_pct = pick_top(tables.get("model_type"), "model_type", exclude=["unspecified", "other"])
    top_route, top_route_n, top_route_pct = pick_top(tables.get("route"), "transmission_route", exclude=["unspecified", "other"])

    det_n = 0
    stoch_n = 0
    if "stoch" in tables and len(tables["stoch"]):
        det_row = tables["stoch"][tables["stoch"]["stoch_deter"] == "Deterministic"]
        stoch_row = tables["stoch"][tables["stoch"]["stoch_deter"] == "Stochastic"]
        det_n = int(det_row["n"].values[0]) if len(det_row) else 0
        stoch_n = int(stoch_row["n"].values[0]) if len(stoch_row) else 0

    code_yes = 0
    if "code" in tables and len(tables["code"]):
        code_row = tables["code"][tables["code"]["code_available"] == "Yes"]
        code_yes = int(code_row["n"].values[0]) if len(code_row) else 0

    data_yes = 0
    if "data_used" in tables and len(tables["data_used"]):
        drow = tables["data_used"][tables["data_used"]["is_data_used_available"] == "Yes"]
        data_yes = int(drow["n"].values[0]) if len(drow) else 0

    theo_yes = 0
    if "theoretical" in tables and len(tables["theoretical"]):
        trow = tables["theoretical"][tables["theoretical"]["theoretical_model"] == "Yes"]
        theo_yes = int(trow["n"].values[0]) if len(trow) else 0

    top_interventions_list = top_list_with_pct(
        tables.get("interventions"),
        "interventions_type (split)",
        n_models,
        k=3,
        exclude=["other", "unspecified", "not available", "na", "n/a"]
    )

    top_assumptions_list = top_list_with_pct(
        tables.get("assumptions"),
        "assumptions (split)",
        n_models,
        k=3,
        exclude=["other", "unspecified", "not available", "na", "n/a"]
    )

    sections = {}
    
    sections["overview"] = (
        f"A total of {n_models} transmission models were extracted from {n_articles} articles that were flagged for containing extractable transmission models. "
        f"The predominant model architecture was {top_model_type or 'not specified'} ({top_model_type_pct or '0.0%'}), "
        f"with {top_route or 'unspecified'} ({top_route_pct or '0.0%'}) representing the most commonly modelled transmission route."
    )
    
    sections["methodology"] = (
        f"Deterministic formulations were employed in {pct(det_n, n_models)} of models, "
        f"while stochastic approaches accounted for {pct(stoch_n, n_models)}. "
        f"Empirical data were incorporated in {pct(data_yes, n_models)} of the extracted models, "
        f"with {pct(theo_yes, n_models)} classified as purely theoretical."
    )
    
    sections["interventions"] = (
        f"The most frequently modelled interventions were {top_interventions_list}. "
        f"Common modelling assumptions included {top_assumptions_list}."
    )
    
    sections["reproducibility"] = (
        f"Source code was publicly available for {pct(code_yes, n_models)} of the extracted models."
    )
    
    return sections


def md_to_pdf_with_assets(md_path, pdf_path, base_dir):
    md_text = Path(md_path).read_text(encoding="utf-8")
    base_dir = Path(base_dir)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=13, spaceAfter=0, spaceBefore=0, alignment=TA_JUSTIFY)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, leading=20, spaceAfter=0, spaceBefore=0)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=17, spaceAfter=0, spaceBefore=0)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11.5, leading=15, spaceAfter=0, spaceBefore=0)
    caption_style = ParagraphStyle("Caption", parent=styles["Normal"], fontSize=9, leading=11, spaceAfter=6, spaceBefore=3, textColor=colors.gray)

    left = right = top = bottom = 54
    page_w = letter[0]
    min_page_h = letter[1]
    max_page_h = 200 * inch
    avail_w = page_w - left - right

    lines = md_text.splitlines()
    story = []
    i = 0

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline_md_to_rl(s):
        s = esc(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", s)
        return s

    def flush_paragraph(buf):
        txt = " ".join([b.strip() for b in buf if b.strip()]).strip()
        if txt:
            story.append(Paragraph(inline_md_to_rl(txt), body))
            story.append(Spacer(1, 6))

    def parse_md_table(start_idx):
        rows = []
        j = start_idx
        while j < len(lines) and lines[j].strip().startswith("|") and "|" in lines[j]:
            row = [c.strip() for c in lines[j].strip().strip("|").split("|")]
            rows.append(row)
            j += 1
        if len(rows) < 2:
            return None, start_idx
        data = rows[0:1] + rows[2:] if len(rows) >= 3 else rows
        return data, j

    def add_table(tbl_data):
        if not tbl_data:
            return
        col_count = max(len(r) for r in tbl_data)
        norm = [r + [""] * (col_count - len(r)) for r in tbl_data]
        t = Table(norm, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

    def add_image(img_rel):
        p = (base_dir / img_rel).resolve()
        if not p.exists():
            return
        img = Image(str(p))
        iw, ih = img.imageWidth, img.imageHeight
        scale = min(avail_w / iw, 1.0)
        img.drawWidth = iw * scale
        img.drawHeight = ih * scale
        story.append(img)
        story.append(Spacer(1, 10))

    buf = []
    while i < len(lines):
        line = lines[i].rstrip()

        if line.strip().startswith("```"):
            flush_paragraph(buf)
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            continue

        if line.strip() == "---":
            flush_paragraph(buf)
            buf = []
            story.append(Spacer(1, 12))
            i += 1
            continue

        if line.startswith("# "):
            flush_paragraph(buf)
            buf = []
            story.append(Paragraph(inline_md_to_rl(line[2:].strip()), h1))
            story.append(Spacer(1, 8))
            i += 1
            continue

        if line.startswith("## "):
            flush_paragraph(buf)
            buf = []
            story.append(Paragraph(inline_md_to_rl(line[3:].strip()), h2))
            story.append(Spacer(1, 6))
            i += 1
            continue

        if line.startswith("### "):
            flush_paragraph(buf)
            buf = []
            story.append(Paragraph(inline_md_to_rl(line[4:].strip()), h3))
            story.append(Spacer(1, 4))
            i += 1
            continue

        if line.strip().startswith("![") and "](" in line and line.endswith(")"):
            flush_paragraph(buf)
            buf = []
            try:
                inner = line.strip()[2:]
                _, rest = inner.split("](", 1)
                img_path = rest[:-1]
                add_image(img_path)
            except Exception:
                pass
            i += 1
            continue

        if line.strip().startswith("|"):
            flush_paragraph(buf)
            buf = []
            tbl_data, next_i = parse_md_table(i)
            if tbl_data is not None:
                add_table(tbl_data)
                i = next_i
                continue

        if line.strip() == "":
            flush_paragraph(buf)
            buf = []
            i += 1
            continue

        buf.append(line)
        i += 1

    flush_paragraph(buf)

    total_h = 0.0
    for f in story:
        _, h = f.wrap(avail_w, max_page_h)
        total_h += h

    page_h = min(max_page_h, max(min_page_h, total_h + top + bottom + 36))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=(page_w, page_h),
        rightMargin=right,
        leftMargin=left,
        topMargin=top,
        bottomMargin=bottom,
    )
    doc.build(story)


def run_for_pathogen(pathogen: str, csv_path: str, out_root=None) -> ContentManifest:
    df = pd.read_csv(csv_path)
    manifest = ContentManifest(
        pathogen=pathogen,
        generated_at=datetime.now().isoformat()
    )
    for c in ["code_available", "uncertainty_was_considered", "spillover_included", "theoretical_model"]:
        if c in df.columns:
            df[c] = df[c].apply(boolish)
    if "spatial_model" in df.columns:
        df["spatial_model"] = df["spatial_model"].apply(lambda x: norm_str(x) if norm_str(x) else "Unspecified")
    for c in ["model_type", "compartmental_type", "stoch_deter", "transmission_route", "coding_language"]:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: norm_str(x) if norm_str(x) else "Unspecified")
    if "is_data_used_available" in df.columns:
        df["data_used_bool"] = df["is_data_used_available"].apply(yesish_data_used)
        df["data_used_bool"] = df["data_used_bool"].fillna(False)

    out_root = Path(out_root) if out_root is not None else (Path("writeup") / pathogen)
    arte = out_root / "figures"
    arte.mkdir(parents=True, exist_ok=True)

    tables, table_manifests = build_summary_tables(df)
    manifest.tables = list(table_manifests.values())
    
    n_models = len(df)
    n_articles = df["article_id"].nunique() if "article_id" in df.columns else 0
    
    inventory = build_inventory_table(df, max_rows=10)

    fig1_manifest = save_combined_overview(tables, pathogen, arte / "fig1_overview.png", n_models)
    manifest.figures.append(fig1_manifest)
    
    fig2_manifest = save_interventions_assumptions(tables, pathogen, arte / "fig2_interventions_assumptions.png", n_models)
    manifest.figures.append(fig2_manifest)

    if len(tables["language"]) > 1:
        lang_counts = [(r["coding_language"], int(r["n"])) for _, r in tables["language"].iterrows()
                       if str(r["coding_language"]) != "Unspecified"]
        if len(lang_counts):
            save_bar_lancet(
                lang_counts[:8],
                "Programming Languages",
                arte / "fig3_languages.png",
                ylabel="Number of models",
                wrap_width=12,
                figsize=(7, 4.5)
            )
            manifest.figures.append(FigureManifest(
                path=str(arte / "fig3_languages.png"),
                title="Programming Languages",
                figure_number=3,
                panels=["Distribution of implementation languages"],
                caption=f"Programming languages used for model implementation among {sum(v for _, v in lang_counts)} models with specified language.",
                n_observations=sum(v for _, v in lang_counts)
            ))

    if all(c in df.columns for c in ["model_type", "stoch_deter"]):
        c2 = defaultdict(Counter)
        for _, row in df.iterrows():
            c2[row["model_type"]][row["stoch_deter"]] += 1
        save_stacked_bar_lancet(
            c2,
            "Model Type by Formulation",
            arte / "fig4_modeltype_stoch.png",
            x_label="Model type",
            y_label="Number of models"
        )
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig4_modeltype_stoch.png"),
            title="Model Type by Formulation",
            figure_number=4,
            panels=["Model architectures stratified by stochastic/deterministic formulation"],
            caption=f"Distribution of deterministic and stochastic formulations across model types (n={n_models}).",
            n_observations=n_models
        ))

    fig_temporal = save_temporal_distribution(df, pathogen, arte / "fig5_temporal.png")
    if fig_temporal:
        fig_temporal.figure_number = len(manifest.figures) + 1
        manifest.figures.append(fig_temporal)
    
    fig_compartmental = save_compartmental_breakdown(df, pathogen, arte / "fig6_compartmental.png")
    if fig_compartmental:
        fig_compartmental.figure_number = len(manifest.figures) + 1
        manifest.figures.append(fig_compartmental)

    manifest.summary_statistics = {
        "n_models": n_models,
        "n_articles": n_articles,
        "deterministic_n": int((df["stoch_deter"] == "Deterministic").sum()) if "stoch_deter" in df.columns else 0,
        "stochastic_n": int((df["stoch_deter"] == "Stochastic").sum()) if "stoch_deter" in df.columns else 0,
        "code_available_n": int((df["code_available"] == True).sum()) if "code_available" in df.columns else 0,
    }

    det_n = manifest.summary_statistics["deterministic_n"]
    stoch_n = manifest.summary_statistics["stochastic_n"]
    code_yes = manifest.summary_statistics["code_available_n"]

    narrative_sections = build_narrative(pathogen, n_models, n_articles, tables)
    manifest.narrative_sections = list(narrative_sections.keys())

    md = []
    md.append(f"# {pathogen} — Extracted Transmission Models\n")
    
    md.append("## Overview\n")
    md.append(narrative_sections["overview"] + "\n")

    md.append("---\n")
    md.append("## Summary\n")
    md.append(f"| Metric | Value |")
    md.append(f"|:-------|------:|")
    md.append(f"| Models extracted | {n_models} |")
    md.append(f"| Articles considered | {n_articles} |")
    md.append(f"| Deterministic models | {det_n} ({pct(det_n, n_models)}) |")
    md.append(f"| Stochastic models | {stoch_n} ({pct(stoch_n, n_models)}) |")
    md.append(f"| Models with available code | {code_yes} ({pct(code_yes, n_models)}) |")
    md.append("")

    md.append("---\n")
    md.append("## Figure 1: Model Overview\n")
    md.append("![Model Overview](figures/fig1_overview.png)\n")
    md.append(f"**Figure 1.** {fig1_manifest.caption}\n")

    md.append("## Model Formulation\n")
    md.append(narrative_sections["methodology"] + "\n")

    md.append("---\n")
    md.append("## Figure 2: Interventions and Assumptions\n")
    md.append("![Interventions and Assumptions](figures/fig2_interventions_assumptions.png)\n")
    md.append(f"**Figure 2.** {fig2_manifest.caption}\n")
    
    md.append("## Interventions and Assumptions\n")
    md.append(narrative_sections["interventions"] + "\n")

    if (arte / "fig3_languages.png").exists():
        md.append("---\n")
        md.append("## Figure 3: Programming Languages\n")
        md.append("![Programming Languages](figures/fig3_languages.png)\n")
        lang_fig = next((f for f in manifest.figures if "languages" in f.path.lower()), None)
        if lang_fig:
            md.append(f"**Figure 3.** {lang_fig.caption}\n")

    if (arte / "fig4_modeltype_stoch.png").exists():
        md.append("---\n")
        md.append("## Figure 4: Model Type by Formulation\n")
        md.append("![Model Type by Formulation](figures/fig4_modeltype_stoch.png)\n")
        stoch_fig = next((f for f in manifest.figures if "stoch" in f.path.lower()), None)
        if stoch_fig:
            md.append(f"**Figure 4.** {stoch_fig.caption}\n")
    
    md.append("## Reproducibility\n")
    md.append(narrative_sections["reproducibility"] + "\n")

    md.append("---\n")
    md.append("## Tables\n")

    md.append("### Table 1: Model Types\n")
    md.append(md_table_with_display_names(tables["model_type"]) + "\n")
    md.append(f"*{table_manifests['model_type'].caption}*\n")

    md.append("### Table 2: Model Formulation\n")
    md.append(md_table_with_display_names(tables["stoch"]) + "\n")
    md.append(f"*{table_manifests['stoch'].caption}*\n")

    md.append("### Table 3: Transmission Routes\n")
    md.append(md_table_with_display_names(tables["route"]) + "\n")
    md.append(f"*{table_manifests['route'].caption}*\n")

    md.append("### Table 4: Interventions Modelled\n")
    md.append(md_table_with_display_names(tables["interventions"]) + "\n")
    md.append(f"*{table_manifests['interventions'].caption}*\n")

    md.append("### Table 5: Model Assumptions\n")
    md.append(md_table_with_display_names(tables["assumptions"]) + "\n")
    md.append(f"*{table_manifests['assumptions'].caption}*\n")

    md.append("### Table 6: Code Availability\n")
    md.append(md_table_with_display_names(tables["code"]) + "\n")
    md.append(f"*{table_manifests['code'].caption}*\n")

    if len(tables["language"]) > 1:
        md.append("\n### Table 7: Programming Languages\n")
        md.append(md_table_with_display_names(tables["language"]) + "\n")
        md.append(f"*{table_manifests['language'].caption}*\n")

    if len(tables["data_used"]):
        md.append("### Table 8: Empirical Data Usage\n")
        md.append(md_table_with_display_names(tables["data_used"]) + "\n")

    md.append("---\n")
    md.append("## Model Inventory (Sample)\n")
    md.append(f"Table 9 presents a sample of 10 extracted model records. The complete dataset of {n_models} extracted transmission models for {pathogen} is publicly available.\n")
    md.append("\n### Table 9: Sample of Extracted Models\n")
    try:
        md.append(inventory.to_markdown(index=False) + "\n")
    except:
        md.append(inventory.to_string(index=False) + "\n")
    md.append(f"*Sample of 10 records from {n_models} extracted {pathogen} transmission models.*\n")

    md.append("---\n")
    md.append("## Data Availability\n")
    md.append(f"The complete dataset of extracted transmission models for {pathogen} (n={n_models}) has been made publicly available to support future modelling efforts and outbreak preparedness.\n")

    out_root.mkdir(parents=True, exist_ok=True)
    md_path = out_root / "models_writeup.md"
    pdf_path = out_root / "models_writeup.pdf"
    manifest_path = out_root / "content_manifest.json"

    md_path.write_text("\n".join(md), encoding="utf-8")
    md_to_pdf_with_assets(md_path, pdf_path, out_root)
    
    import json
    with open(manifest_path, 'w') as f:
        json.dump({
            "pathogen": manifest.pathogen,
            "generated_at": manifest.generated_at,
            "summary_statistics": manifest.summary_statistics,
            "narrative_sections": manifest.narrative_sections,
            "figures": [
                {
                    "number": fig.figure_number,
                    "title": fig.title,
                    "path": fig.path,
                    "caption": fig.caption,
                    "n_observations": fig.n_observations,
                    "panels": fig.panels
                }
                for fig in manifest.figures
            ],
            "tables": [
                {
                    "number": tbl.table_number,
                    "title": tbl.title,
                    "columns": tbl.columns,
                    "n_rows": tbl.n_rows,
                    "caption": tbl.caption
                }
                for tbl in manifest.tables
            ]
        }, f, indent=2)
    
    print(f"Generated writeup for {pathogen} in {out_root}")
    print(f"  - Markdown: {md_path}")
    print(f"  - PDF: {pdf_path}")
    print(f"  - Figures: {len(manifest.figures)}")
    print(f"  - Tables: {len(manifest.tables)}")
    
    return manifest


def run_models_writeup(config):
    config.report_models_dir.mkdir(parents=True, exist_ok=True)
    return run_for_pathogen(
        config.pathogen,
        str(config.data_extraction_models_path),
        out_root=config.report_models_dir,
    )
