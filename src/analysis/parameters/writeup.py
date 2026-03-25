# src/analysis/parameters/writeup.py
import re
import json
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
from matplotlib.gridspec import GridSpec
import seaborn as sns

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY


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
    '#F2CC8F', '#6D597A', '#B56576', '#355070', '#EAAC8B',
]

PARAMETER_CLASS_DISPLAY = {
    'human_delay': 'Human Delay',
    'severity': 'Severity',
    'reproduction_number': 'Reproduction Number',
    'attack_rate': 'Attack Rate',
    'seroprevalence': 'Seroprevalence',
    'relative_contribution': 'Relative Contribution',
    'mutation_rate': 'Mutation Rate',
    'growth_rate': 'Growth Rate',
}

DELAY_TYPE_DISPLAY = {
    'incubation_period': 'Incubation period',
    'symptom_onset__to__death': 'Onset to death',
    'symptom_onset__to__admission': 'Onset to admission',
    'infectious_period': 'Infectious period',
    'time_in_care': 'Time in care',
    'admission__to__death': 'Admission to death',
    'admission__to__discharge_or_recovery': 'Admission to discharge',
    'generation_time': 'Generation time',
    'serial_interval': 'Serial interval',
    'symptom_onset__to__discharge_or_recovery': 'Onset to discharge',
    'other': 'Other',
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def norm_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def pct(n, d):
    if d == 0:
        return "0.0%"
    return f"{(100.0 * n / d):.1f}%"


def wrap_label(text, width=15):
    text = str(text)
    if len(text) <= width:
        return text
    return '\n'.join(textwrap.wrap(text, width=width))


def wrap_labels(labels, width=15):
    return [wrap_label(l, width) for l in labels]


def topk_with_other(counter, k=10, other_label="Other"):
    items = counter.most_common()
    if len(items) <= k:
        return items
    top = items[:k]
    rest = sum(v for _, v in items[k:])
    return top + [(other_label, rest)]


def add_panel_label(ax, label, x=-0.12, y=1.08):
    ax.text(x, y, label, transform=ax.transAxes, fontsize=14,
            fontweight='bold', va='top', ha='left')


def style_axis(ax, xlabel=None, ylabel=None, title=None):
    if xlabel:
        ax.set_xlabel(xlabel, fontweight='medium')
    if ylabel:
        ax.set_ylabel(ylabel, fontweight='medium')
    if title:
        ax.set_title(title, fontweight='medium', pad=10)
    ax.tick_params(axis='both', which='major', direction='out')


def display_param_class(cls):
    return PARAMETER_CLASS_DISPLAY.get(cls, cls.replace('_', ' ').title())


def display_delay_type(dt):
    return DELAY_TYPE_DISPLAY.get(dt, dt.replace('_', ' ').replace('  to  ', ' to ').title())


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_parameters(jsonl_path: str) -> pd.DataFrame:
    """Load the JSONL parameter extractions and flatten."""
    records = []
    with open(jsonl_path) as f:
        for line in f:
            raw = json.loads(line)
            flat = {
                'article_id': raw['article_id'],
                'parameter_class': raw['parameter_class'],
                'aggregated': raw.get('aggregated', False),
            }
            ext = raw.get('extraction', {})
            for k, v in ext.items():
                if k == 'id':
                    flat['extraction_id'] = v
                elif k == 'aggregated_ids':
                    continue
                elif isinstance(v, list):
                    flat[k] = '; '.join(str(x) for x in v)
                else:
                    flat[k] = v
            records.append(flat)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Figure: Overview (parameter class distribution + geographic)
# ---------------------------------------------------------------------------

def save_overview_figure(df, pathogen, outpath) -> FigureManifest:
    non_agg = df[~df['aggregated']]
    fig = plt.figure(figsize=(14, 6), dpi=300, layout='constrained')
    gs = GridSpec(1, 2, figure=fig, wspace=0.30)

    # Panel A: parameter class counts
    ax1 = fig.add_subplot(gs[0, 0])
    class_counts = non_agg['parameter_class'].value_counts()
    classes = class_counts.index.tolist()
    values = class_counts.values
    labels = [wrap_label(display_param_class(c), 18) for c in classes]
    colors_list = LANCET_PALETTE[:len(classes)]

    bars = ax1.barh(range(len(classes)), values, color=colors_list,
                    edgecolor='white', linewidth=0.5)
    ax1.set_yticks(range(len(classes)))
    ax1.set_yticklabels(labels)
    ax1.invert_yaxis()
    style_axis(ax1, xlabel="Number of extractions",
               title="Parameter Class Distribution")
    ax1.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax1.set_axisbelow(True)
    for bar, val in zip(bars, values):
        ax1.annotate(f'{val}', xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                     xytext=(3, 0), textcoords='offset points', ha='left', va='center',
                     fontsize=8, color='#333333')
    add_panel_label(ax1, "A")

    # Panel B: geographic distribution
    ax2 = fig.add_subplot(gs[0, 1])
    country_col = 'population_country'
    if country_col in non_agg.columns:
        country_counts = Counter()
        for c in non_agg[country_col].dropna():
            for part in re.split(r'[;,]', str(c)):
                part = part.strip()
                if part:
                    country_counts[part] += 1
        top_countries = topk_with_other(country_counts, k=10)
        c_labels = [wrap_label(k, 20) for k, _ in top_countries]
        c_values = [v for _, v in top_countries]
        c_colors = LANCET_PALETTE[:len(c_labels)]

        bars2 = ax2.barh(range(len(c_labels)), c_values, color=c_colors,
                         edgecolor='white', linewidth=0.5)
        ax2.set_yticks(range(len(c_labels)))
        ax2.set_yticklabels(c_labels)
        ax2.invert_yaxis()
        style_axis(ax2, xlabel="Number of extractions",
                   title="Geographic Distribution")
        ax2.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
        ax2.set_axisbelow(True)
        for bar, val in zip(bars2, c_values):
            ax2.annotate(f'{val}', xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                         xytext=(3, 0), textcoords='offset points', ha='left', va='center',
                         fontsize=8, color='#333333')
    add_panel_label(ax2, "B")

    fig.suptitle(f"{pathogen}: Extracted Epidemiological Parameters",
                 fontsize=14, fontweight='bold')
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(non_agg)
    return FigureManifest(
        path=str(outpath),
        title=f"{pathogen}: Parameter Extraction Overview",
        figure_number=1,
        panels=["Parameter class distribution", "Geographic distribution"],
        caption=(
            f"Overview of {n} individual parameter extractions for {pathogen}. "
            f"(A) Distribution across parameter classes. "
            f"(B) Geographic distribution of study populations."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Figure: Human delay forest plot
# ---------------------------------------------------------------------------

def save_human_delay_figure(df, pathogen, outpath) -> Optional[FigureManifest]:
    sub = df[(df['parameter_class'] == 'human_delay') & (~df['aggregated'])].copy()
    if len(sub) == 0:
        return None

    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub['paired_uncertainty_lower_bound'] = pd.to_numeric(sub.get('paired_uncertainty_lower_bound'), errors='coerce')
    sub['paired_uncertainty_upper_bound'] = pd.to_numeric(sub.get('paired_uncertainty_upper_bound'), errors='coerce')
    sub = sub.dropna(subset=['value'])

    # Cap extreme outliers for readability (>60 days)
    sub_plot = sub[sub['value'] <= 60].copy()
    if len(sub_plot) == 0:
        sub_plot = sub.copy()

    # Order by delay type
    delay_order = sub_plot.groupby('delay_type')['value'].median().sort_values().index.tolist()
    sub_plot['delay_type_display'] = sub_plot['delay_type'].map(display_delay_type)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), dpi=300,
                                    gridspec_kw={'width_ratios': [2, 1]})

    # Panel A: strip/forest plot of values by delay type
    palette = {display_delay_type(dt): LANCET_PALETTE[i % len(LANCET_PALETTE)]
               for i, dt in enumerate(delay_order)}

    ordered_display = [display_delay_type(dt) for dt in delay_order]
    sns.stripplot(data=sub_plot, y='delay_type_display', x='value',
                  order=ordered_display, hue='delay_type_display', hue_order=ordered_display,
                  palette=palette, size=5, alpha=0.7, jitter=0.2, legend=False, ax=ax1)

    # Add CI whiskers where available
    for _, row in sub_plot.iterrows():
        lo = row.get('paired_uncertainty_lower_bound')
        hi = row.get('paired_uncertainty_upper_bound')
        if pd.notna(lo) and pd.notna(hi) and lo <= 60 and hi <= 60:
            y_idx = ordered_display.index(row['delay_type_display'])
            ax1.plot([lo, hi], [y_idx, y_idx], color='gray', linewidth=0.5, alpha=0.4)

    style_axis(ax1, xlabel="Value (days)", title="Human Delay Parameters")
    ax1.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax1.set_axisbelow(True)
    ax1.set_ylabel('')
    add_panel_label(ax1, "A")

    # Panel B: count by delay type
    type_counts = sub['delay_type'].value_counts()
    type_counts = type_counts.reindex(delay_order)
    labels_b = [display_delay_type(dt) for dt in type_counts.index]
    values_b = type_counts.values
    colors_b = [palette.get(display_delay_type(dt), LANCET_COLORS['neutral'])
                for dt in type_counts.index]

    bars = ax2.barh(range(len(labels_b)), values_b, color=colors_b,
                    edgecolor='white', linewidth=0.5)
    ax2.set_yticks(range(len(labels_b)))
    ax2.set_yticklabels(labels_b)
    ax2.invert_yaxis()
    style_axis(ax2, xlabel="Count", title="Extractions by Delay Type")
    ax2.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax2.set_axisbelow(True)
    for bar, val in zip(bars, values_b):
        ax2.annotate(f'{val}', xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                     xytext=(3, 0), textcoords='offset points', ha='left', va='center',
                     fontsize=8, color='#333333')
    add_panel_label(ax2, "B")

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(sub)
    return FigureManifest(
        path=str(outpath),
        title="Human Delay Parameters",
        figure_number=2,
        panels=["Values by delay type", "Extraction counts by delay type"],
        caption=(
            f"Human delay parameter extractions for {pathogen} (n={n}). "
            f"(A) Distribution of reported values (days) stratified by delay type, "
            f"with horizontal whiskers indicating 95% confidence intervals where reported. "
            f"Values >60 days excluded from panel A for readability. "
            f"(B) Number of extractions per delay type."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Figure: Severity (CFR) forest plot
# ---------------------------------------------------------------------------

def _normalise_cfr(sub):
    """Normalise CFR values and their CIs to the 0-1 proportion scale."""
    sub = sub.copy()
    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub['ci_lo'] = pd.to_numeric(sub.get('paired_uncertainty_lower_bound'), errors='coerce')
    sub['ci_hi'] = pd.to_numeric(sub.get('paired_uncertainty_upper_bound'), errors='coerce')
    sub = sub.dropna(subset=['value'])

    # Values should be in [0, 1].  If they look like percentages, rescale.
    mask_pct = sub['value'] > 1
    sub.loc[mask_pct, 'value'] = sub.loc[mask_pct, 'value'] / 100
    sub.loc[mask_pct, 'ci_lo'] = sub.loc[mask_pct, 'ci_lo'] / 100
    sub.loc[mask_pct, 'ci_hi'] = sub.loc[mask_pct, 'ci_hi'] / 100

    # CIs that are still wildly inconsistent with the value are likely extraction
    # artefacts (e.g. value=0.88, CI=[1.9, 2.8]).  Drop those.
    for idx in sub.index:
        v = sub.at[idx, 'value']
        lo, hi = sub.at[idx, 'ci_lo'], sub.at[idx, 'ci_hi']
        if pd.notna(lo) and pd.notna(hi):
            # Accept CI only if it contains or is close to the point estimate
            if lo > v + 0.30 or hi < v - 0.30 or lo > 1 or hi > 1 or lo < 0 or hi < 0:
                sub.at[idx, 'ci_lo'] = np.nan
                sub.at[idx, 'ci_hi'] = np.nan

    return sub


METHOD_MARKERS = {
    'adjusted': 'o',       # circle
    'naive': '^',          # triangle
}
METHOD_MARKER_DEFAULT = 's'  # square for unknown/unspecified


def _method_marker(method_str):
    """Return the matplotlib marker for a given method string."""
    m = str(method_str).strip().lower() if pd.notna(method_str) else ''
    return METHOD_MARKERS.get(m, METHOD_MARKER_DEFAULT)


def _draw_cfr_forest_row(ax, row, y, bar_color, dot_color):
    """Draw a single row of the CFR forest plot.

    - Solid colour bar for CI range
    - Point estimate marker (shape encodes method) on top
    - Whisker ticks at ends of CI
    """
    v = row['value']
    lo, hi = row.get('ci_lo'), row.get('ci_hi')
    marker = _method_marker(row.get('method'))
    bar_height = 0.4

    if pd.notna(lo) and pd.notna(hi):
        # Solid colour bar for CI range
        ax.barh(y, width=hi - lo, left=lo, height=bar_height,
                color=bar_color, alpha=0.45, edgecolor='none', zorder=2)
        # Whisker ticks at CI ends
        tick_half = bar_height * 0.4
        ax.plot([lo, lo], [y - tick_half, y + tick_half],
                color=bar_color, linewidth=1.2, solid_capstyle='butt', zorder=3)
        ax.plot([hi, hi], [y - tick_half, y + tick_half],
                color=bar_color, linewidth=1.2, solid_capstyle='butt', zorder=3)

    # Point estimate with method-specific marker
    ax.plot(v, y, marker=marker, color=dot_color, markersize=5, zorder=4,
            markeredgecolor='white', markeredgewidth=0.4, linestyle='None')


def save_severity_figure(df, pathogen, outpath) -> Optional[FigureManifest]:
    sub = df[(df['parameter_class'] == 'severity') & (~df['aggregated'])].copy()
    if len(sub) == 0:
        return None

    sub = _normalise_cfr(sub)
    if len(sub) == 0:
        return None

    # Group by country, ordered by number of estimates (largest group first)
    country_groups = (
        sub.groupby('population_country')
        .apply(lambda g: g.sort_values('value').reset_index(drop=True),
               include_groups=False)
    )
    country_order = (
        sub['population_country']
        .value_counts()
        .index.tolist()
    )

    n_countries = len(country_order)
    rows_per_country = [len(sub[sub['population_country'] == c]) for c in country_order]
    total_rows = sum(rows_per_country)

    # Compute figure height: dense layout
    fig_height = max(4, total_rows * 0.2 + n_countries * 0.55 + 1.0)
    fig, axes = plt.subplots(
        n_countries, 1, figsize=(9, fig_height), dpi=300,
        gridspec_kw={'height_ratios': rows_per_country},
        squeeze=False,
    )

    global_median = sub['value'].median()

    for idx, country in enumerate(country_order):
        ax = axes[idx, 0]
        group = sub[sub['population_country'] == country].sort_values('value').reset_index(drop=True)
        n_rows = len(group)
        color = LANCET_PALETTE[idx % len(LANCET_PALETTE)]

        for i, (_, row) in enumerate(group.iterrows()):
            _draw_cfr_forest_row(ax, row, y=i, bar_color=color,
                                 dot_color=LANCET_COLORS['primary'])

        # Median line for this country if >1 estimate
        if n_rows > 1:
            grp_median = group['value'].median()
            ax.axvline(x=grp_median, color=color, linestyle='--',
                       linewidth=0.8, alpha=0.6)

        # Global median reference line
        ax.axvline(x=global_median, color=LANCET_COLORS['quaternary'],
                   linestyle=':', linewidth=0.8, alpha=0.5)

        # Y-axis labels: article_id
        y_labels = []
        for _, row in group.iterrows():
            aid = str(row.get('article_id', '')) if pd.notna(row.get('article_id')) else ''
            y_labels.append(aid[:30] if aid else '')

        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(y_labels, fontsize=6)
        ax.set_ylim(-0.5, n_rows - 0.5)
        ax.set_xlim(-0.02, 1.05)
        ax.xaxis.grid(True, linestyle='-', alpha=0.15, color='gray')
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Country name as subplot title
        ax.set_title(country, fontsize=9, fontweight='medium', loc='left', pad=4)

        # Only show x-axis label on bottom subplot
        if idx < n_countries - 1:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Case Fatality Ratio", fontweight='medium')

        # Add method legend to the first subplot
        if idx == 0:
            from matplotlib.lines import Line2D
            legend_handles = [
                Line2D([0], [0], marker='o', color='none',
                       markerfacecolor=LANCET_COLORS['primary'], markeredgecolor='white',
                       markeredgewidth=0.4, markersize=6, label='Adjusted'),
                Line2D([0], [0], marker='^', color='none',
                       markerfacecolor=LANCET_COLORS['primary'], markeredgecolor='white',
                       markeredgewidth=0.4, markersize=6, label='Naive'),
                Line2D([0], [0], marker='s', color='none',
                       markerfacecolor=LANCET_COLORS['primary'], markeredgecolor='white',
                       markeredgewidth=0.4, markersize=6, label='Unspecified'),
            ]
            ax.legend(handles=legend_handles, fontsize=7, loc='upper right',
                      frameon=True, fancybox=False, edgecolor='#cccccc',
                      title='Method', title_fontsize=8)

    fig.suptitle(f"{pathogen}: Severity (CFR) Estimates by Country",
                 fontsize=13, fontweight='bold', y=1.0)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(sub)
    return FigureManifest(
        path=str(outpath),
        title="Severity (CFR) Estimates by Country",
        figure_number=3,
        panels=[f"CFR estimates for {c}" for c in country_order],
        caption=(
            f"Case fatality ratio estimates for {pathogen} (n={n}), grouped by country. "
            f"Coloured bars indicate 95% confidence intervals with tick marks at bounds; "
            f"dots indicate point estimates. "
            f"Dashed coloured lines show within-country medians; "
            f"dotted orange line indicates the overall median ({global_median:.2f})."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Figure: Reproduction number range plot
# ---------------------------------------------------------------------------

def save_reproduction_number_figure(df, pathogen, outpath) -> Optional[FigureManifest]:
    sub = df[(df['parameter_class'] == 'reproduction_number') & (~df['aggregated'])].copy()
    if len(sub) == 0:
        return None

    # These records have value + uncertainty OR lower_bound/upper_bound
    has_value = 'value' in sub.columns and sub['value'].notna().any()
    has_bounds = all(c in sub.columns for c in ['lower_bound', 'upper_bound'])

    sub['val'] = pd.to_numeric(sub.get('value'), errors='coerce')
    sub['lo'] = pd.to_numeric(sub.get('lower_bound', sub.get('paired_uncertainty_lower_bound')), errors='coerce')
    sub['hi'] = pd.to_numeric(sub.get('upper_bound', sub.get('paired_uncertainty_upper_bound')), errors='coerce')

    # Use midpoint of bounds if no value
    sub['mid'] = sub['val']
    mask_no_val = sub['mid'].isna() & sub['lo'].notna() & sub['hi'].notna()
    sub.loc[mask_no_val, 'mid'] = (sub.loc[mask_no_val, 'lo'] + sub.loc[mask_no_val, 'hi']) / 2
    sub = sub.dropna(subset=['mid'])
    sub = sub.sort_values('mid').reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, max(6, len(sub) * 0.3)), dpi=300)

    y_positions = range(len(sub))
    ax.scatter(sub['mid'], y_positions, color=LANCET_COLORS['primary'],
               s=30, zorder=3)

    for i, (_, row) in enumerate(sub.iterrows()):
        lo, hi = row['lo'], row['hi']
        if pd.notna(lo) and pd.notna(hi):
            ax.plot([lo, hi], [i, i], color=LANCET_COLORS['secondary'],
                    linewidth=1.5, alpha=0.6)

    y_labels = []
    for _, row in sub.iterrows():
        country = str(row.get('population_country', ''))[:30] if pd.notna(row.get('population_country')) else ''
        y_labels.append(country or 'Unspecified')

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(y_labels, fontsize=7)
    ax.axvline(x=1.0, color=LANCET_COLORS['quinary'], linestyle='--',
               linewidth=1, alpha=0.7, label='R = 1')
    style_axis(ax, xlabel="Reproduction Number",
               title=f"{pathogen}: Reproduction Number Estimates")
    ax.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc='lower right')

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(sub)
    return FigureManifest(
        path=str(outpath),
        title="Reproduction Number Estimates",
        figure_number=4,
        panels=["Reproduction number estimates with uncertainty ranges"],
        caption=(
            f"Reproduction number estimates for {pathogen} (n={n}). "
            f"Points indicate central estimates (or midpoints of reported ranges). "
            f"Horizontal lines show reported uncertainty bounds. "
            f"Dashed vertical line at R=1 indicates the epidemic threshold."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Figure: Attack rate dot plot
# ---------------------------------------------------------------------------

def save_attack_rate_figure(df, pathogen, outpath) -> Optional[FigureManifest]:
    sub = df[(df['parameter_class'] == 'attack_rate') & (~df['aggregated'])].copy()
    if len(sub) == 0:
        return None

    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub['paired_uncertainty_lower_bound'] = pd.to_numeric(sub.get('paired_uncertainty_lower_bound'), errors='coerce')
    sub['paired_uncertainty_upper_bound'] = pd.to_numeric(sub.get('paired_uncertainty_upper_bound'), errors='coerce')
    sub = sub.dropna(subset=['value'])

    # Normalise: if unit is "percentage", values are already in %, otherwise treat as proportion
    sub['value_pct'] = sub['value']
    mask_prop = sub['value_pct'] <= 1
    sub.loc[mask_prop, 'value_pct'] = sub.loc[mask_prop, 'value_pct'] * 100

    sub = sub.sort_values('value_pct').reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, max(5, len(sub) * 0.25)), dpi=300)

    y_positions = range(len(sub))
    ax.scatter(sub['value_pct'], y_positions, color=LANCET_COLORS['tertiary'],
               s=30, zorder=3, alpha=0.8)

    y_labels = []
    for _, row in sub.iterrows():
        country = str(row.get('population_country', ''))[:30] if pd.notna(row.get('population_country')) else ''
        group = str(row.get('population_group', ''))[:20] if pd.notna(row.get('population_group')) else ''
        label = f"{country}" if country else 'Unspecified'
        if group and group.lower() != 'general population':
            label += f" ({group})"
        y_labels.append(label[:50])

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(y_labels, fontsize=7)
    style_axis(ax, xlabel="Attack Rate (%)",
               title=f"{pathogen}: Attack Rate Estimates")
    ax.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(sub)
    return FigureManifest(
        path=str(outpath),
        title="Attack Rate Estimates",
        figure_number=5,
        panels=["Attack rate estimates by study"],
        caption=(
            f"Attack rate estimates for {pathogen} (n={n}). "
            f"Values are shown as percentages."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Figure: Seroprevalence dot plot
# ---------------------------------------------------------------------------

def save_seroprevalence_figure(df, pathogen, outpath) -> Optional[FigureManifest]:
    sub = df[(df['parameter_class'] == 'seroprevalence') & (~df['aggregated'])].copy()
    if len(sub) == 0:
        return None

    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub['paired_uncertainty_lower_bound'] = pd.to_numeric(sub.get('paired_uncertainty_lower_bound'), errors='coerce')
    sub['paired_uncertainty_upper_bound'] = pd.to_numeric(sub.get('paired_uncertainty_upper_bound'), errors='coerce')
    sub = sub.dropna(subset=['value'])
    sub = sub.sort_values('value').reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, max(4, len(sub) * 0.4)), dpi=300)

    y_positions = range(len(sub))
    ax.scatter(sub['value'], y_positions, color=LANCET_COLORS['success'],
               s=40, zorder=3, alpha=0.8)

    for i, (_, row) in enumerate(sub.iterrows()):
        lo = row.get('paired_uncertainty_lower_bound')
        hi = row.get('paired_uncertainty_upper_bound')
        if pd.notna(lo) and pd.notna(hi):
            ax.plot([lo, hi], [i, i], color=LANCET_COLORS['success'],
                    linewidth=1.5, alpha=0.5)

    y_labels = []
    for _, row in sub.iterrows():
        country = str(row.get('population_country', ''))[:25] if pd.notna(row.get('population_country')) else ''
        location = str(row.get('population_location', ''))[:20] if pd.notna(row.get('population_location')) else ''
        label = location if location else country if country else 'Unspecified'
        y_labels.append(label)

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(y_labels, fontsize=8)
    style_axis(ax, xlabel="Seroprevalence (proportion)",
               title=f"{pathogen}: Seroprevalence Estimates")
    ax.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(sub)
    return FigureManifest(
        path=str(outpath),
        title="Seroprevalence Estimates",
        figure_number=6,
        panels=["Seroprevalence estimates with confidence intervals"],
        caption=(
            f"Seroprevalence estimates for {pathogen} (n={n}). "
            f"Points indicate reported seroprevalence proportions; "
            f"horizontal lines show 95% confidence intervals where reported."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Figure: Statistical approach breakdown
# ---------------------------------------------------------------------------

def save_methods_figure(df, pathogen, outpath) -> Optional[FigureManifest]:
    non_agg = df[~df['aggregated']]
    if 'statistical_approach' not in non_agg.columns:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)

    # Panel A: statistical approach
    approach_counts = Counter(
        norm_str(x) for x in non_agg['statistical_approach'].dropna()
        if norm_str(x)
    )
    if not approach_counts:
        plt.close(fig)
        return None

    items_a = approach_counts.most_common()
    labels_a = [wrap_label(k.replace('_', ' ').title(), 20) for k, _ in items_a]
    values_a = [v for _, v in items_a]
    colors_a = LANCET_PALETTE[:len(labels_a)]

    wedges, texts, autotexts = ax1.pie(
        values_a, labels=labels_a, colors=colors_a,
        autopct='%1.1f%%', startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5},
        textprops={'fontsize': 9},
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight('medium')
    ax1.set_title("Statistical Approach", fontweight='medium', pad=10)
    add_panel_label(ax1, "A", x=-0.1, y=1.05)

    # Panel B: value_type breakdown
    vt_counts = Counter(
        norm_str(x) for x in non_agg['value_type'].dropna()
        if norm_str(x) and norm_str(x).lower() != 'unspecified'
    ) if 'value_type' in non_agg.columns else Counter()

    if vt_counts:
        items_b = vt_counts.most_common(8)
        labels_b = [k.replace('_', ' ').title() for k, _ in items_b]
        values_b = [v for _, v in items_b]
        colors_b = LANCET_PALETTE[:len(labels_b)]

        bars = ax2.bar(range(len(labels_b)), values_b, color=colors_b,
                       edgecolor='white', linewidth=0.5)
        ax2.set_xticks(range(len(labels_b)))
        ax2.set_xticklabels(labels_b, rotation=45, ha='right', rotation_mode='anchor')
        style_axis(ax2, ylabel="Count", title="Value Type Reported")
        ax2.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
        ax2.set_axisbelow(True)
        ax2.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        for bar, val in zip(bars, values_b):
            if val > 0:
                ax2.annotate(f'{val}', xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                             xytext=(0, 3), textcoords='offset points', ha='center', va='bottom',
                             fontsize=8, color='#333333')
    add_panel_label(ax2, "B")

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    n = len(non_agg)
    return FigureManifest(
        path=str(outpath),
        title="Methodological Summary",
        figure_number=7,
        panels=["Statistical approach", "Value type reported"],
        caption=(
            f"Methodological characteristics of parameter extractions for {pathogen} (n={n}). "
            f"(A) Distribution of statistical approaches. "
            f"(B) Types of summary statistics reported."
        ),
        n_observations=n,
    )


# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------

def build_summary_tables(df) -> Tuple[Dict[str, pd.DataFrame], Dict[str, TableManifest]]:
    non_agg = df[~df['aggregated']]
    n_total = len(non_agg)
    n_articles = non_agg['article_id'].nunique()
    table_manifests = {}

    # Overview table
    overview = pd.DataFrame([
        ["Total parameter extractions", int(n_total)],
        ["Source articles", int(n_articles)],
        ["Parameter classes", int(non_agg['parameter_class'].nunique())],
    ], columns=["Metric", "Value"])

    # Parameter class counts
    class_counts = non_agg['parameter_class'].value_counts()
    param_class_df = pd.DataFrame([
        [display_param_class(cls), int(n), pct(n, n_total)]
        for cls, n in class_counts.items()
    ], columns=["parameter_class", "n", "%"])
    table_manifests["param_class"] = TableManifest(
        title="Parameter Classes",
        table_number=1,
        columns=["Parameter Class", "Count", "Proportion"],
        n_rows=len(param_class_df),
        caption=f"Distribution of parameter classes across {n_total} extractions from {n_articles} articles.",
    )

    # Human delay subtypes
    delay_sub = non_agg[non_agg['parameter_class'] == 'human_delay']
    delay_counts = delay_sub['delay_type'].value_counts() if 'delay_type' in delay_sub.columns else pd.Series(dtype=int)
    delay_df = pd.DataFrame([
        [display_delay_type(dt), int(n), pct(n, len(delay_sub))]
        for dt, n in delay_counts.items()
    ], columns=["delay_type", "n", "%"])
    table_manifests["delay_type"] = TableManifest(
        title="Human Delay Types",
        table_number=2,
        columns=["Delay Type", "Count", "Proportion"],
        n_rows=len(delay_df),
        caption=f"Distribution of human delay parameter types (n={len(delay_sub)}).",
    )

    # Severity breakdown
    sev_sub = non_agg[non_agg['parameter_class'] == 'severity']
    sev_type_counts = sev_sub['parameter_type'].value_counts() if 'parameter_type' in sev_sub.columns else pd.Series(dtype=int)
    severity_df = pd.DataFrame([
        [pt, int(n), pct(n, len(sev_sub))]
        for pt, n in sev_type_counts.items()
    ], columns=["parameter_type", "n", "%"])
    table_manifests["severity"] = TableManifest(
        title="Severity Parameter Types",
        table_number=3,
        columns=["Parameter Type", "Count", "Proportion"],
        n_rows=len(severity_df),
        caption=f"Types of severity parameters extracted (n={len(sev_sub)}).",
    )

    # Geographic distribution
    country_counts = Counter()
    for c in non_agg['population_country'].dropna():
        for part in re.split(r'[;,]', str(c)):
            part = part.strip()
            if part:
                country_counts[part] += 1
    geo_items = topk_with_other(country_counts, k=15)
    geo_df = pd.DataFrame([
        [k, int(v), pct(v, n_total)]
        for k, v in geo_items
    ], columns=["country", "n", "%"])
    table_manifests["geography"] = TableManifest(
        title="Geographic Distribution",
        table_number=4,
        columns=["Country", "Count", "Proportion"],
        n_rows=len(geo_df),
        caption=f"Countries represented in parameter extractions. Studies spanning multiple countries are counted for each (n={n_total}).",
    )

    # Statistical approach
    approach_counts = Counter(
        norm_str(x).replace('_', ' ').title()
        for x in non_agg['statistical_approach'].dropna()
        if norm_str(x)
    ) if 'statistical_approach' in non_agg.columns else Counter()
    approach_df = pd.DataFrame([
        [k, int(v), pct(v, n_total)]
        for k, v in approach_counts.most_common()
    ], columns=["statistical_approach", "n", "%"])
    table_manifests["approach"] = TableManifest(
        title="Statistical Approaches",
        table_number=5,
        columns=["Approach", "Count", "Proportion"],
        n_rows=len(approach_df),
        caption=f"Statistical approaches used across parameter extractions (n={n_total}).",
    )

    tables = {
        "overview": overview,
        "param_class": param_class_df,
        "delay_type": delay_df,
        "severity": severity_df,
        "geography": geo_df,
        "approach": approach_df,
    }
    return tables, table_manifests


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------

def build_narrative(pathogen, n_total, n_articles, tables, df) -> Dict[str, str]:
    non_agg = df[~df['aggregated']]
    sections = {}

    # Overview
    class_counts = non_agg['parameter_class'].value_counts()
    top_class = class_counts.index[0] if len(class_counts) else "unknown"
    top_class_n = int(class_counts.iloc[0]) if len(class_counts) else 0
    sections["overview"] = (
        f"A total of {n_total} individual epidemiological parameter estimates were extracted "
        f"from {n_articles} articles for {pathogen}. "
        f"The most frequently extracted parameter class was {display_param_class(top_class)} "
        f"(n={top_class_n}, {pct(top_class_n, n_total)}), "
        f"spanning {non_agg['parameter_class'].nunique()} distinct parameter classes."
    )

    # Delays
    delay_sub = non_agg[non_agg['parameter_class'] == 'human_delay']
    if len(delay_sub) > 0 and 'delay_type' in delay_sub.columns:
        dt_counts = delay_sub['delay_type'].value_counts()
        top_dt = display_delay_type(dt_counts.index[0])
        top_dt_n = int(dt_counts.iloc[0])
        delay_vals = pd.to_numeric(delay_sub['value'], errors='coerce').dropna()
        sections["delays"] = (
            f"Human delay parameters accounted for {len(delay_sub)} extractions. "
            f"The most common delay type was {top_dt} (n={top_dt_n}). "
            f"Reported delay values ranged from {delay_vals.min():.1f} to {delay_vals.max():.1f} days "
            f"(median {delay_vals.median():.1f} days)."
        )

    # Severity
    sev_sub = non_agg[non_agg['parameter_class'] == 'severity']
    if len(sev_sub) > 0:
        sev_vals = pd.to_numeric(sev_sub['value'], errors='coerce').dropna()
        # Normalise to proportion
        sev_prop = sev_vals.copy()
        sev_prop[sev_prop > 1] = sev_prop[sev_prop > 1] / 100
        sections["severity"] = (
            f"Severity estimates comprised {len(sev_sub)} extractions, "
            f"predominantly case fatality ratios (CFR). "
            f"CFR estimates ranged from {sev_prop.min():.1%} to {sev_prop.max():.1%} "
            f"(median {sev_prop.median():.1%})."
        )

    # R0
    r_sub = non_agg[non_agg['parameter_class'] == 'reproduction_number']
    if len(r_sub) > 0:
        r_vals = pd.to_numeric(r_sub.get('value', pd.Series(dtype=float)), errors='coerce')
        r_lo = pd.to_numeric(r_sub.get('lower_bound', pd.Series(dtype=float)), errors='coerce')
        r_hi = pd.to_numeric(r_sub.get('upper_bound', pd.Series(dtype=float)), errors='coerce')
        mid = r_vals.fillna((r_lo + r_hi) / 2).dropna()
        if len(mid) > 0:
            sections["reproduction_number"] = (
                f"A total of {len(r_sub)} reproduction number estimates were extracted, "
                f"with central estimates ranging from {mid.min():.2f} to {mid.max():.2f} "
                f"(median {mid.median():.2f})."
            )

    return sections


# ---------------------------------------------------------------------------
# Markdown table helper
# ---------------------------------------------------------------------------

def md_table(df):
    display_map = {
        'parameter_class': 'Parameter Class',
        'delay_type': 'Delay Type',
        'parameter_type': 'Parameter Type',
        'country': 'Country',
        'statistical_approach': 'Statistical Approach',
        'n': 'Count',
        '%': 'Proportion',
    }
    df_display = df.copy()
    df_display.columns = [display_map.get(c, c.replace('_', ' ').title()) for c in df_display.columns]
    try:
        return df_display.to_markdown(index=False)
    except Exception:
        return df_display.to_string(index=False)


# ---------------------------------------------------------------------------
# Markdown → PDF converter (reused from models writeup)
# ---------------------------------------------------------------------------

def md_to_pdf_with_assets(md_path, pdf_path, base_dir):
    md_text = Path(md_path).read_text(encoding="utf-8")
    base_dir = Path(base_dir)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=13,
                          spaceAfter=0, spaceBefore=0, alignment=TA_JUSTIFY)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, leading=20,
                         spaceAfter=0, spaceBefore=0)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=17,
                         spaceAfter=0, spaceBefore=0)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11.5, leading=15,
                         spaceAfter=0, spaceBefore=0)

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
            flush_paragraph(buf); buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            continue

        if line.strip() == "---":
            flush_paragraph(buf); buf = []
            story.append(Spacer(1, 12))
            i += 1
            continue

        if line.startswith("# "):
            flush_paragraph(buf); buf = []
            story.append(Paragraph(inline_md_to_rl(line[2:].strip()), h1))
            story.append(Spacer(1, 8))
            i += 1
            continue

        if line.startswith("## "):
            flush_paragraph(buf); buf = []
            story.append(Paragraph(inline_md_to_rl(line[3:].strip()), h2))
            story.append(Spacer(1, 6))
            i += 1
            continue

        if line.startswith("### "):
            flush_paragraph(buf); buf = []
            story.append(Paragraph(inline_md_to_rl(line[4:].strip()), h3))
            story.append(Spacer(1, 4))
            i += 1
            continue

        if line.strip().startswith("![") and "](" in line and line.strip().endswith(")"):
            flush_paragraph(buf); buf = []
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
            flush_paragraph(buf); buf = []
            tbl_data, next_i = parse_md_table(i)
            if tbl_data is not None:
                add_table(tbl_data)
                i = next_i
                continue

        if line.strip() == "":
            flush_paragraph(buf); buf = []
            i += 1
            continue

        buf.append(line)
        i += 1

    flush_paragraph(buf)

    total_h = sum(f.wrap(avail_w, max_page_h)[1] for f in story)
    page_h = min(max_page_h, max(min_page_h, total_h + top + bottom + 36))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=(page_w, page_h),
        rightMargin=right, leftMargin=left,
        topMargin=top, bottomMargin=bottom,
    )
    doc.build(story)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_for_pathogen(pathogen: str, jsonl_path: str, out_root=None) -> ContentManifest:
    df = load_parameters(jsonl_path)
    manifest = ContentManifest(
        pathogen=pathogen,
        generated_at=datetime.now().isoformat(),
    )

    non_agg = df[~df['aggregated']]
    n_total = len(non_agg)
    n_articles = non_agg['article_id'].nunique()

    out_root = Path(out_root) if out_root is not None else (Path("writeup") / pathogen)
    arte = out_root / "figures"
    arte.mkdir(parents=True, exist_ok=True)

    tables, table_manifests = build_summary_tables(df)
    manifest.tables = list(table_manifests.values())

    # --- Figures ---
    fig_num = 1

    fig1 = save_overview_figure(df, pathogen, arte / "fig1_overview.png")
    fig1.figure_number = fig_num
    manifest.figures.append(fig1)
    fig_num += 1

    fig2 = save_human_delay_figure(df, pathogen, arte / "fig2_human_delay.png")
    if fig2:
        fig2.figure_number = fig_num
        manifest.figures.append(fig2)
        fig_num += 1

    fig3 = save_severity_figure(df, pathogen, arte / "fig3_severity.png")
    if fig3:
        fig3.figure_number = fig_num
        manifest.figures.append(fig3)
        fig_num += 1

    fig4 = save_reproduction_number_figure(df, pathogen, arte / "fig4_reproduction_number.png")
    if fig4:
        fig4.figure_number = fig_num
        manifest.figures.append(fig4)
        fig_num += 1

    fig5 = save_attack_rate_figure(df, pathogen, arte / "fig5_attack_rate.png")
    if fig5:
        fig5.figure_number = fig_num
        manifest.figures.append(fig5)
        fig_num += 1

    fig6 = save_seroprevalence_figure(df, pathogen, arte / "fig6_seroprevalence.png")
    if fig6:
        fig6.figure_number = fig_num
        manifest.figures.append(fig6)
        fig_num += 1

    fig7 = save_methods_figure(df, pathogen, arte / "fig7_methods.png")
    if fig7:
        fig7.figure_number = fig_num
        manifest.figures.append(fig7)
        fig_num += 1

    # --- Summary statistics ---
    manifest.summary_statistics = {
        "n_extractions": n_total,
        "n_articles": n_articles,
        "n_parameter_classes": non_agg['parameter_class'].nunique(),
        "class_counts": non_agg['parameter_class'].value_counts().to_dict(),
    }

    # --- Narrative ---
    narrative_sections = build_narrative(pathogen, n_total, n_articles, tables, df)
    manifest.narrative_sections = list(narrative_sections.keys())

    # --- Assemble Markdown ---
    md = []
    md.append(f"# {pathogen} — Extracted Epidemiological Parameters\n")

    md.append("## Overview\n")
    md.append(narrative_sections.get("overview", "") + "\n")

    md.append("---\n")
    md.append("## Summary\n")
    md.append("| Metric | Value |")
    md.append("|:-------|------:|")
    md.append(f"| Parameter extractions | {n_total} |")
    md.append(f"| Source articles | {n_articles} |")
    md.append(f"| Parameter classes | {non_agg['parameter_class'].nunique()} |")
    md.append("")

    md.append("---\n")
    md.append("## Figure 1: Parameter Overview\n")
    md.append("![Parameter Overview](figures/fig1_overview.png)\n")
    md.append(f"**Figure 1.** {fig1.caption}\n")

    if fig2:
        md.append("---\n")
        md.append("## Human Delay Parameters\n")
        md.append(narrative_sections.get("delays", "") + "\n")
        md.append(f"## Figure {fig2.figure_number}: Human Delay Parameters\n")
        md.append("![Human Delay](figures/fig2_human_delay.png)\n")
        md.append(f"**Figure {fig2.figure_number}.** {fig2.caption}\n")

    if fig3:
        md.append("---\n")
        md.append("## Severity Estimates\n")
        md.append(narrative_sections.get("severity", "") + "\n")
        md.append(f"## Figure {fig3.figure_number}: Severity (CFR)\n")
        md.append("![Severity](figures/fig3_severity.png)\n")
        md.append(f"**Figure {fig3.figure_number}.** {fig3.caption}\n")

    if fig4:
        md.append("---\n")
        md.append("## Reproduction Number\n")
        md.append(narrative_sections.get("reproduction_number", "") + "\n")
        md.append(f"## Figure {fig4.figure_number}: Reproduction Number\n")
        md.append("![Reproduction Number](figures/fig4_reproduction_number.png)\n")
        md.append(f"**Figure {fig4.figure_number}.** {fig4.caption}\n")

    if fig5:
        md.append("---\n")
        md.append(f"## Figure {fig5.figure_number}: Attack Rate\n")
        md.append("![Attack Rate](figures/fig5_attack_rate.png)\n")
        md.append(f"**Figure {fig5.figure_number}.** {fig5.caption}\n")

    if fig6:
        md.append("---\n")
        md.append(f"## Figure {fig6.figure_number}: Seroprevalence\n")
        md.append("![Seroprevalence](figures/fig6_seroprevalence.png)\n")
        md.append(f"**Figure {fig6.figure_number}.** {fig6.caption}\n")

    if fig7:
        md.append("---\n")
        md.append(f"## Figure {fig7.figure_number}: Methodological Summary\n")
        md.append("![Methods](figures/fig7_methods.png)\n")
        md.append(f"**Figure {fig7.figure_number}.** {fig7.caption}\n")

    # Tables
    md.append("---\n")
    md.append("## Tables\n")

    tbl_num = 1
    md.append(f"### Table {tbl_num}: Parameter Classes\n")
    md.append(md_table(tables["param_class"]) + "\n")
    md.append(f"*{table_manifests['param_class'].caption}*\n")
    tbl_num += 1

    md.append(f"### Table {tbl_num}: Human Delay Types\n")
    md.append(md_table(tables["delay_type"]) + "\n")
    md.append(f"*{table_manifests['delay_type'].caption}*\n")
    tbl_num += 1

    if len(tables["severity"]):
        md.append(f"### Table {tbl_num}: Severity Parameter Types\n")
        md.append(md_table(tables["severity"]) + "\n")
        md.append(f"*{table_manifests['severity'].caption}*\n")
        tbl_num += 1

    md.append(f"### Table {tbl_num}: Geographic Distribution\n")
    md.append(md_table(tables["geography"]) + "\n")
    md.append(f"*{table_manifests['geography'].caption}*\n")
    tbl_num += 1

    if len(tables["approach"]):
        md.append(f"### Table {tbl_num}: Statistical Approaches\n")
        md.append(md_table(tables["approach"]) + "\n")
        md.append(f"*{table_manifests['approach'].caption}*\n")
        tbl_num += 1

    md.append("---\n")
    md.append("## Data Availability\n")
    md.append(
        f"The complete dataset of extracted epidemiological parameters for {pathogen} "
        f"(n={n_total}) has been made publicly available to support future modelling "
        f"efforts and outbreak preparedness.\n"
    )

    # Write outputs
    out_root.mkdir(parents=True, exist_ok=True)
    md_path = out_root / "parameters_writeup.md"
    pdf_path = out_root / "parameters_writeup.pdf"
    manifest_path = out_root / "content_manifest.json"

    md_path.write_text("\n".join(md), encoding="utf-8")
    md_to_pdf_with_assets(md_path, pdf_path, out_root)

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
                    "panels": fig.panels,
                }
                for fig in manifest.figures
            ],
            "tables": [
                {
                    "number": tbl.table_number,
                    "title": tbl.title,
                    "columns": tbl.columns,
                    "n_rows": tbl.n_rows,
                    "caption": tbl.caption,
                }
                for tbl in manifest.tables
            ],
        }, f, indent=2)

    print(f"Generated parameters writeup for {pathogen} in {out_root}")
    print(f"  - Markdown: {md_path}")
    print(f"  - PDF: {pdf_path}")
    print(f"  - Figures: {len(manifest.figures)}")
    print(f"  - Tables: {len(manifest.tables)}")

    return manifest


def run_parameters_writeup(config):
    config.report_parameters_dir.mkdir(parents=True, exist_ok=True)
    return run_for_pathogen(
        config.pathogen,
        str(config.data_extraction_parameters_path),
        out_root=config.report_parameters_dir,
    )
