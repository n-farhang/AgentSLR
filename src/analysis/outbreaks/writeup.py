# src/analysis/outbreaks/writeup.py
# outbreaks/analysis/writeup.py

import re
import textwrap
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import calendar

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap, Normalize
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature

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
    'outbreak_start_year': 'Start Year',
    'outbreak_start_month': 'Start Month',
    'outbreak_start_day': 'Start Day',
    'outbreak_end_year': 'End Year',
    'outbreak_end_month': 'End Month',
    'outbreak_end_day': 'End Day',
    'outbreak_duration_months': 'Duration (months)',
    'outbreak_is_currently_ongoing': 'Ongoing',
    'outbreak_country': 'Country',
    'outbreak_location': 'Location',
    'outbreak_location_type': 'Location Type',
    'outbreak_source': 'Source',
    'mode_of_detection': 'Detection Mode',
    'method_of_case_definition': 'Case Definition',
    'pre_outbreak': 'Pre-outbreak Context',
    'cases_confirmed': 'Confirmed Cases',
    'cases_probable': 'Probable Cases',
    'cases_suspected': 'Suspected Cases',
    'cases_unspecified': 'Unspecified Cases',
    'cases_asymptomatic': 'Asymptomatic Cases',
    'cases_severe': 'Severe Cases',
    'deaths': 'Deaths',
    'asymptomatic_transmission_described': 'Asymptomatic Transmission',
    'population_size_geographical_area': 'Population Size',
    'type_cases_sex_disagg': 'Sex Disaggregation Type',
    'male_cases': 'Male Cases',
    'prop_male_cases': 'Male Proportion',
    'female_cases': 'Female Cases',
    'prop_female_cases': 'Female Proportion',
    'notes': 'Notes',
    'article_id': 'Article ID',
    'n': 'Count',
    '%': 'Proportion',
    'cfr': 'CFR (%)',
    'total_cases': 'Total Cases',
}

MONTH_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

COUNTRY_COORDS = {
    'Nigeria': (9.08, 8.68), 'Sierra Leone': (8.46, -11.78), 'Liberia': (6.43, -9.43),
    'Guinea': (9.95, -9.70), 'Benin': (9.31, 2.32), 'Ghana': (7.95, -1.02),
    'Mali': (17.57, -4.00), 'Côte d\'Ivoire': (7.54, -5.55), 'Togo': (8.62, 0.82),
    'Senegal': (14.50, -14.45), 'Brazil': (-14.24, -51.93), 'Colombia': (4.57, -74.30),
    'Mexico': (23.63, -102.55), 'United States of America': (37.09, -95.71),
    'France': (46.23, 2.21), 'French Polynesia': (-17.68, -149.41),
    'Puerto Rico': (18.22, -66.59), 'Dominican Republic': (18.74, -70.16),
    'El Salvador': (13.79, -88.90), 'Guatemala': (15.78, -90.23),
    'Honduras': (15.20, -86.24), 'Nicaragua': (12.87, -85.21),
    'Panama': (8.54, -80.78), 'Venezuela': (6.42, -66.59),
    'Ecuador': (-1.83, -78.18), 'Peru': (-9.19, -75.02),
    'Bolivia': (-16.29, -63.59), 'Paraguay': (-23.44, -58.44),
    'Argentina': (-38.42, -63.62), 'Chile': (-35.68, -71.54),
    'Suriname': (3.92, -56.03), 'Guyana': (4.86, -58.93),
    'Trinidad and Tobago': (10.69, -61.22), 'Jamaica': (18.11, -77.30),
    'Haiti': (18.97, -72.29), 'Cuba': (21.52, -77.78),
    'India': (20.59, 78.96), 'Thailand': (15.87, 100.99),
    'Vietnam': (14.06, 108.28), 'Singapore': (1.35, 103.82),
    'Indonesia': (-0.79, 113.92), 'Philippines': (12.88, 121.77),
    'China': (35.86, 104.20), 'Japan': (36.20, 138.25),
    'Australia': (-25.27, 133.78), 'Fiji': (-17.71, 178.07),
    'New Caledonia': (-20.90, 165.62), 'Micronesia': (7.43, 150.55),
    'Cabo Verde': (16.00, -24.01), 'Angola': (-11.20, 17.87),
    'Kenya': (-0.02, 37.91), 'Gabon': (-0.80, 11.61),
    'Central African Republic': (6.61, 20.94), 'Cameroon': (7.37, 12.35),
    'Sweden': (60.13, 18.64), 'Germany': (51.17, 10.45),
    'United Kingdom': (55.38, -3.44), 'Spain': (40.46, -3.75),
    'Italy': (41.87, 12.57), 'Netherlands': (52.13, 5.29),
    'Maldives': (3.20, 73.22), 'Canada': (56.13, -106.35),
    'Costa Rica': (9.75, -83.75), 'Belize': (17.19, -88.50),
    'Barbados': (13.19, -59.54), 'Martinique': (14.64, -61.02),
    'Guadeloupe': (16.27, -61.55), 'Curacao': (12.17, -68.99),
    'Aruba': (12.52, -69.97), 'Saint Martin': (18.07, -63.05),
    'United States Virgin Islands': (18.34, -64.90),
}

LOCATION_COORDS = {
    'Rio de Janeiro': (-22.91, -43.17), 'São Paulo': (-23.55, -46.64),
    'Salvador': (-12.97, -38.50), 'Recife': (-8.05, -34.88),
    'Fortaleza': (-3.72, -38.54), 'Manaus': (-3.12, -60.02),
    'Brasília': (-15.79, -47.88), 'Belo Horizonte': (-19.92, -43.94),
    'Pernambuco': (-8.05, -34.88), 'Bahia': (-12.97, -38.50),
    'Mato Grosso do Sul': (-20.51, -54.54), 'Maranhão': (-2.53, -44.27),
    'Sao Luis': (-2.53, -44.27), 'Minas Gerais': (-19.82, -43.17),
    'Edo state': (6.34, 5.62), 'Edo': (6.34, 5.62),
    'Ondo state': (7.25, 5.19), 'Ondo': (7.25, 5.19),
    'Lagos': (6.52, 3.38), 'Kano': (12.00, 8.52),
    'Abuja': (9.08, 7.40), 'FCT Abuja': (9.08, 7.40),
    'Ebonyi': (6.26, 8.01), 'Ebonyi State': (6.26, 8.01),
    'Plateau': (9.22, 9.52), 'Plateau state': (9.22, 9.52),
    'Bauchi': (10.31, 9.84), 'Bauchi State': (10.31, 9.84),
    'Kaduna': (10.52, 7.44), 'Nasarawa': (8.54, 8.11),
    'Benue': (7.34, 8.77), 'Taraba': (7.87, 10.77),
    'Kogi': (7.73, 6.69), 'Rivers': (4.84, 7.03),
    'French Polynesia': (-17.68, -149.41), 'Tahiti': (-17.65, -149.45),
    'Moorea': (-17.54, -149.83), 'Bora Bora': (-16.50, -151.74),
    'Cali': (3.45, -76.53), 'Medellín': (6.25, -75.56),
    'Bogotá': (4.71, -74.07), 'Barranquilla': (10.96, -74.80),
    'Cartagena': (10.39, -75.48), 'Cúcuta': (7.89, -72.50),
    'Girardot': (4.30, -74.80), 'San Andrés': (12.58, -81.70),
    'Puerto Rico': (18.22, -66.59), 'San Juan': (18.47, -66.11),
    'French Guiana': (3.93, -53.13), 'Cayenne': (4.92, -52.31),
    'Martinique': (14.64, -61.02), 'Guadeloupe': (16.27, -61.55),
    'Saint Martin': (18.07, -63.05),
    'Freetown': (8.48, -13.23), 'Kenema': (7.88, -11.19),
    'Bo': (7.96, -11.74), 'Tonkolili': (8.99, -11.86),
    'Conakry': (9.64, -13.58), 'Gueckedou': (8.57, -10.13),
    'Monrovia': (6.29, -10.76), 'Bong County': (6.83, -9.37),
    'Suakoko': (6.99, -9.59),
    'Abakaliki': (6.33, 8.10), 'Enugu': (6.44, 7.50),
    'Jos': (9.93, 8.89), 'Owo': (7.20, 5.59),
    'Santiago': (-33.45, -70.67), 'Valparaíso': (-33.05, -71.62),
    'Florida': (27.66, -81.52), 'Texas': (31.97, -99.90),
    'Cameron County': (26.15, -97.50), 'Miami': (25.76, -80.19),
    'Singapore': (1.35, 103.82),
    'Yiwu City': (29.31, 120.07), 'Zhejiang': (29.14, 119.79),
    'Guangzhou': (23.13, 113.26),
    'Manitoba': (53.76, -98.81),
    'Austral Islands': (-22.44, -151.34), 'Marquesas Islands': (-9.77, -139.08),
    'Tuamotu': (-18.03, -141.38), 'Society Islands': (-17.53, -149.57),
    'Sous-le-vent Islands': (-16.77, -151.42),
    'New Caledonia': (-20.90, 165.62),
    'Yap Island': (9.53, 138.13),
    'Borgou': (9.89, 2.62), 'Donga': (9.57, 1.57), 'Ouémé': (6.58, 2.50),
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


def parse_month(x):
    if pd.isna(x):
        return None
    s = norm_str(x).lower()
    if s in MONTH_MAP:
        return MONTH_MAP[s]
    try:
        m = int(float(s))
        if 1 <= m <= 12:
            return m
    except:
        pass
    return None


def month_name(m):
    if m is None or pd.isna(m):
        return "Unknown"
    try:
        return calendar.month_abbr[int(m)]
    except:
        return str(m)


def pct(n, d):
    if d == 0:
        return "0.0%"
    return f"{(100.0*n/d):.1f}%"


def pct_val(n, d):
    if d == 0:
        return 0.0
    return 100.0 * n / d


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


def compute_total_cases(row):
    vals = []
    for col in ['cases_confirmed', 'cases_probable', 'cases_suspected', 'cases_unspecified']:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                try:
                    val = float(val)
                    if val > 0:
                        vals.append(val)
                except (ValueError, TypeError):
                    pass
    if not vals:
        return np.nan
    return sum(vals)


def compute_cfr(row, denominator='confirmed'):
    deaths = row.get('deaths', np.nan)
    if pd.isna(deaths):
        return np.nan
    try:
        deaths = float(deaths)
    except (ValueError, TypeError):
        return np.nan
    if deaths <= 0:
        return np.nan

    if denominator == 'confirmed':
        denom = row.get('cases_confirmed', np.nan)
    elif denominator == 'total':
        denom = compute_total_cases(row)
    else:
        denom = row.get('cases_confirmed', np.nan)

    if pd.isna(denom):
        return np.nan
    try:
        denom = float(denom)
    except (ValueError, TypeError):
        return np.nan
    if denom <= 0:
        return np.nan

    return 100.0 * deaths / denom


def compute_completeness(df, cols=None):
    if cols is None:
        cols = df.columns.tolist()

    results = []
    for col in cols:
        if col not in df.columns:
            continue
        n_total = len(df)
        n_present = df[col].notna().sum()
        n_missing = n_total - n_present
        pct_complete = pct_val(n_present, n_total)
        results.append({
            'variable': col,
            'n_present': int(n_present),
            'n_missing': int(n_missing),
            'pct_complete': round(pct_complete, 1)
        })

    return pd.DataFrame(results)


def parse_locations(location_str):
    if pd.isna(location_str) or not location_str:
        return []
    location_str = str(location_str)
    delimiters = [';', ',', '/', '|']
    locations = [location_str]
    for delim in delimiters:
        new_locations = []
        for loc in locations:
            new_locations.extend([l.strip() for l in loc.split(delim) if l.strip()])
        locations = new_locations
    return locations


def get_location_coords(location):
    location_clean = location.strip()
    if location_clean in LOCATION_COORDS:
        return LOCATION_COORDS[location_clean]
    for key in LOCATION_COORDS:
        if key.lower() in location_clean.lower() or location_clean.lower() in key.lower():
            return LOCATION_COORDS[key]
    return None


def save_choropleth_map(df, pathogen, outpath, figsize=(16, 7)):
    
    countries = df['outbreak_country'].dropna()
    if len(countries) < 1:
        return None

    country_counts = Counter([norm_str(c) for c in countries if norm_str(c)])
    if not country_counts:
        return None

    country_cases = defaultdict(float)
    country_deaths = defaultdict(float)
    country_locations = defaultdict(set)
    
    for _, row in df.iterrows():
        country = norm_str(row.get('outbreak_country', ''))
        if country:
            cases = row.get('total_cases', 0)
            if pd.notna(cases) and cases > 0:
                country_cases[country] += cases
            deaths = row.get('deaths', 0)
            if pd.notna(deaths) and deaths > 0:
                country_deaths[country] += deaths
            location = row.get('outbreak_location', '')
            if pd.notna(location) and location:
                locs = parse_locations(location)
                for loc in locs:
                    country_locations[country].add(loc)

    mapped_coords = []
    for country in country_counts.keys():
        if country in COUNTRY_COORDS:
            lat, lon = COUNTRY_COORDS[country]
            mapped_coords.append((lon, lat))

    if not mapped_coords:
        return None

    lons, lats = zip(*mapped_coords)
    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)
    
    pad_x = max(15, (lon_max - lon_min) * 0.25)
    pad_y = max(10, (lat_max - lat_min) * 0.25)

    fig = plt.figure(figsize=figsize, dpi=300)
    
    for panel_idx, (metric_data, title_suffix, cmap_name) in enumerate([
        (country_cases, 'Total Cases', 'YlOrRd'),
        (country_deaths, 'Total Deaths', 'OrRd')
    ]):
        ax = fig.add_subplot(1, 2, panel_idx + 1, projection=ccrs.PlateCarree())
        
        ax.set_extent([
            max(-180, lon_min - pad_x),
            min(180, lon_max + pad_x),
            max(-60, lat_min - pad_y),
            min(85, lat_max + pad_y)
        ], crs=ccrs.PlateCarree())
        
        ax.add_feature(cfeature.LAND, facecolor='#F5F5F5', zorder=0)
        ax.add_feature(cfeature.OCEAN, facecolor='#E8F4F8', zorder=0)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='#999999', zorder=1)
        ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor='#CCCCCC', zorder=1)
        
        max_metric = max(metric_data.values()) if metric_data else 1
        if max_metric == 0:
            max_metric = 1
        
        norm = Normalize(vmin=0, vmax=max_metric)
        cmap = plt.cm.get_cmap(cmap_name)
        
        for country in country_counts.keys():
            if country in COUNTRY_COORDS:
                lat, lon = COUNTRY_COORDS[country]
                metric_val = metric_data.get(country, 0)
                
                if metric_val > 0:
                    size = 200 + (metric_val / max_metric) * 2000
                    color = cmap(norm(metric_val))
                    ax.scatter(lon, lat, s=size, c=[color], alpha=0.75,
                              edgecolors='white', linewidth=2, zorder=5,
                              transform=ccrs.PlateCarree())
                    
                    ax.text(lon, lat + 2.5, country, fontsize=7, fontweight='medium',
                           ha='center', va='bottom', color='#333333', zorder=10,
                           transform=ccrs.PlateCarree())
                else:
                    ax.scatter(lon, lat, s=100, c='#CCCCCC', alpha=0.5,
                              edgecolors='white', linewidth=1, zorder=4,
                              transform=ccrs.PlateCarree())
        
        if 'outbreak_location' in df.columns and panel_idx == 0:
            location_plotted = set()
            for country in list(country_counts.keys())[:5]:
                for loc in list(country_locations.get(country, []))[:3]:
                    if loc in location_plotted:
                        continue
                    coords = get_location_coords(loc)
                    if coords:
                        loc_lat, loc_lon = coords
                        ax.plot(loc_lon, loc_lat, 's', markersize=4, 
                               color='#2E86AB', markeredgecolor='white', 
                               markeredgewidth=0.5, zorder=6,
                               transform=ccrs.PlateCarree())
                        location_plotted.add(loc)
        
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, orientation='horizontal', 
                           pad=0.05, shrink=0.7, aspect=30)
        cbar.set_label(title_suffix, fontsize=10, fontweight='medium')
        cbar.ax.tick_params(labelsize=8)
        
        ax.set_title(title_suffix, fontsize=12, fontweight='bold', pad=10)
    
    fig.suptitle(f'{pathogen}: Geographic Concentration of Disease Burden', 
                fontsize=14, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return {
        'n_countries': len(country_counts),
        'total_cases': int(sum(country_cases.values())),
        'total_deaths': int(sum(country_deaths.values())),
        'n_locations_mapped': len(set().union(*country_locations.values())) if country_locations else 0
    }


def save_geographic_bar_complete(df, pathogen, outpath, figsize=(10, None)):
    countries = df['outbreak_country'].dropna()
    if len(countries) < 1:
        return None

    country_counts = Counter([norm_str(c) for c in countries if norm_str(c)])
    if not country_counts:
        return None

    counts_sorted = country_counts.most_common()
    n_countries = len(counts_sorted)

    fig_height = max(6, n_countries * 0.35 + 2)
    fig, ax = plt.subplots(figsize=(figsize[0], fig_height), dpi=300)

    labels = [c for c, _ in counts_sorted]
    values = [v for _, v in counts_sorted]

    colors_list = [LANCET_PALETTE[i % len(LANCET_PALETTE)] for i in range(len(labels))]

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=colors_list, edgecolor='white', linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()

    style_axis(ax, xlabel="Number of outbreak records",
              title=f"{pathogen}: Outbreak Records by Country (n={len(countries)})")

    ax.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    for bar, val in zip(bars, values):
        ax.annotate(f'{val}', xy=(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2),
                   va='center', ha='left', fontsize=8, color='#333333')

    ax.set_xlim(0, max(values) * 1.15)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return {
        'n_countries': n_countries,
        'top_countries': counts_sorted[:5]
    }

def remove_temporal_outliers(df, percentile=95):
    df_filtered = df.copy()
    if 'outbreak_start_year' in df_filtered.columns:
        valid_years = df_filtered['outbreak_start_year'].dropna()
        if len(valid_years) > 0:
            year_threshold = valid_years.quantile(percentile / 100.0)
            year_min = valid_years.min()
            df_filtered = df_filtered[
                (df_filtered['outbreak_start_year'].isna()) | 
                ((df_filtered['outbreak_start_year'] >= year_min) & 
                 (df_filtered['outbreak_start_year'] <= year_threshold))
            ]
    return df_filtered


def save_temporal_burden(df, pathogen, outpath, figsize=(10, 6)):
    if 'outbreak_start_year' not in df.columns:
        return None
    
    df_filtered = remove_temporal_outliers(df, percentile=95)

    yearly_data = df.groupby('outbreak_start_year').agg({
        'cases_confirmed': 'sum',
        'cases_suspected': 'sum',
        'deaths': 'sum'
    }).reset_index()

    yearly_data = yearly_data[yearly_data['outbreak_start_year'].notna()]
    yearly_data['outbreak_start_year'] = yearly_data['outbreak_start_year'].astype(int)
    yearly_data = yearly_data.sort_values('outbreak_start_year')

    if len(yearly_data) < 2:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, dpi=300, height_ratios=[2, 1])

    years = yearly_data['outbreak_start_year']
    confirmed = yearly_data['cases_confirmed'].fillna(0)
    suspected = yearly_data['cases_suspected'].fillna(0)

    ax1.bar(years, confirmed, label='Confirmed', color=LANCET_COLORS['primary'],
           edgecolor='white', linewidth=0.5)
    ax1.bar(years, suspected, bottom=confirmed, label='Suspected',
           color=LANCET_COLORS['secondary'], edgecolor='white', linewidth=0.5, alpha=0.7)

    ax1.set_ylabel('Reported Cases')
    ax1.set_title(f'{pathogen}: Annual Case Burden from Extracted Records', fontweight='bold')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.yaxis.grid(True, linestyle='-', alpha=0.2)
    ax1.set_axisbelow(True)
    add_panel_label(ax1, 'A')

    deaths = yearly_data['deaths'].fillna(0)
    ax2.bar(years, deaths, color=LANCET_COLORS['quinary'], edgecolor='white', linewidth=0.5)
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Deaths')
    ax2.yaxis.grid(True, linestyle='-', alpha=0.2)
    ax2.set_axisbelow(True)
    add_panel_label(ax2, 'B')

    for ax in [ax1, ax2]:
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return {
        'years': len(yearly_data),
        'total_confirmed': int(confirmed.sum()),
        'total_suspected': int(suspected.sum()),
        'total_deaths': int(deaths.sum())
    }


def save_missingness_heatmap(df, pathogen, outpath, figsize=(12, 8)):
    key_cols = [
        'outbreak_start_year', 'outbreak_start_month', 'outbreak_end_year',
        'outbreak_country', 'outbreak_location', 'outbreak_source',
        'mode_of_detection', 'pre_outbreak',
        'cases_confirmed', 'cases_suspected', 'deaths',
        'male_cases', 'female_cases'
    ]
    cols_present = [c for c in key_cols if c in df.columns]

    if len(cols_present) < 3 or len(df) < 5:
        return None

    missingness = df[cols_present].isna().astype(int)

    if 'outbreak_country' in df.columns:
        missingness['_country'] = df['outbreak_country'].fillna('Unknown')
        missingness = missingness.sort_values('_country')
        missingness = missingness.drop('_country', axis=1)

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    cmap = LinearSegmentedColormap.from_list('missingness',
                                              ['#2D6A4F', '#F4F4F4'])

    display_cols = [get_display_name(c) for c in cols_present]

    n_records = len(missingness)
    n_vars = len(cols_present)

    im = ax.imshow(missingness.values, aspect='auto', cmap=cmap,
                   interpolation='nearest')

    ax.set_xticks(range(n_vars))
    ax.set_xticklabels(display_cols, rotation=45, ha='right', fontsize=9)

    if n_records > 30:
        ax.set_yticks([0, n_records//2, n_records-1])
        ax.set_yticklabels(['1', str(n_records//2), str(n_records)])
    else:
        ax.set_yticks(range(n_records))
        ax.set_yticklabels(range(1, n_records + 1), fontsize=7)

    ax.set_ylabel('Outbreak Record')
    ax.set_title(f'{pathogen}: Data Completeness Matrix (n={n_records} records)',
                fontweight='bold', pad=15)

    legend_elements = [
        mpatches.Patch(facecolor='#2D6A4F', label='Data present'),
        mpatches.Patch(facecolor='#F4F4F4', edgecolor='gray', label='Missing'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    pct_missing_by_var = missingness.mean() * 100
    return {
        'n_records': n_records,
        'n_variables': n_vars,
        'worst_variables': pct_missing_by_var.nlargest(3).to_dict()
    }


def save_evidence_gaps(df, pathogen, outpath, figsize=(10, 6)):
    key_groups = {
        'Temporal': ['outbreak_start_year', 'outbreak_start_month', 'outbreak_end_year', 'outbreak_end_month'],
        'Geographic': ['outbreak_country', 'outbreak_location', 'outbreak_location_type'],
        'Case Burden': ['cases_confirmed', 'cases_suspected', 'cases_probable', 'deaths'],
        'Demographics': ['male_cases', 'female_cases', 'cases_asymptomatic', 'cases_severe'],
        'Context': ['outbreak_source', 'mode_of_detection', 'pre_outbreak']
    }

    results = []
    for group_name, cols in key_groups.items():
        for col in cols:
            if col in df.columns:
                pct_present = (df[col].notna().sum() / len(df)) * 100
                results.append({
                    'group': group_name,
                    'variable': get_display_name(col),
                    'pct_present': pct_present
                })

    if not results:
        return None

    results_df = pd.DataFrame(results)

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    groups = results_df['group'].unique()
    group_colors = {g: LANCET_PALETTE[i % len(LANCET_PALETTE)] for i, g in enumerate(groups)}

    y_pos = range(len(results_df))
    colors_list = [group_colors[g] for g in results_df['group']]

    bars = ax.barh(y_pos, results_df['pct_present'], color=colors_list,
                  edgecolor='white', linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(results_df['variable'], fontsize=9)
    ax.invert_yaxis()

    ax.axvline(x=50, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax.axvline(x=75, color='gray', linestyle=':', alpha=0.5, linewidth=1)

    ax.set_xlim(0, 105)
    ax.set_xlabel('Records with data available (%)')
    ax.set_title(f'{pathogen}: Evidence Availability by Variable (n={len(df)} records)',
                fontweight='bold', pad=15)

    legend_elements = [mpatches.Patch(facecolor=c, label=g)
                      for g, c in group_colors.items()]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)

    ax.xaxis.grid(True, linestyle='-', alpha=0.2)
    ax.set_axisbelow(True)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    low_availability = results_df[results_df['pct_present'] < 25]['variable'].tolist()
    return {
        'n_variables': len(results_df),
        'low_availability_vars': low_availability
    }


def save_cfr_by_country(df, pathogen, outpath, figsize=(10, 6)):
    if 'cfr_confirmed' not in df.columns or 'outbreak_country' not in df.columns:
        return None

    df_valid = df[['outbreak_country', 'cfr_confirmed']].dropna()
    df_valid = df_valid[(df_valid['cfr_confirmed'] >= 0) & (df_valid['cfr_confirmed'] <= 100)]

    country_counts = df_valid.groupby('outbreak_country').size()
    countries_with_data = country_counts[country_counts >= 2].index.tolist()

    if len(countries_with_data) < 2:
        return None

    df_plot = df_valid[df_valid['outbreak_country'].isin(countries_with_data)]

    country_order = df_plot.groupby('outbreak_country')['cfr_confirmed'].median().sort_values(ascending=False).index

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    positions = range(len(country_order))
    for i, country in enumerate(country_order):
        country_data = df_plot[df_plot['outbreak_country'] == country]['cfr_confirmed']
        ax.scatter([i] * len(country_data), country_data, alpha=0.6,
                  color=LANCET_COLORS['primary'], s=50, edgecolors='white', linewidth=0.5)
        median_val = country_data.median()
        ax.hlines(median_val, i - 0.3, i + 0.3, color=LANCET_COLORS['quinary'],
                 linewidth=2, label='Median' if i == 0 else '')

    ax.set_xticks(positions)
    ax.set_xticklabels([wrap_label(c, 12) for c in country_order], rotation=45, ha='right')

    ax.set_ylabel('Case Fatality Ratio (%)')
    ax.set_title(f'{pathogen}: CFR Distribution by Country (deaths/confirmed cases)',
                fontweight='bold', pad=15)

    ax.yaxis.grid(True, linestyle='-', alpha=0.2)
    ax.set_axisbelow(True)

    overall_median = df_valid['cfr_confirmed'].median()
    ax.axhline(y=overall_median, color='gray', linestyle='--', alpha=0.7,
              label=f'Overall median: {overall_median:.1f}%')
    ax.legend(loc='upper right', fontsize=8)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return {
        'n_countries': len(country_order),
        'overall_median': round(overall_median, 1)
    }


def save_outbreak_timeline(df, pathogen, outpath, figsize=(12, 8)):
    required_cols = ['outbreak_start_year', 'outbreak_country']
    if not all(c in df.columns for c in required_cols):
        return None

    df_valid = df[df['outbreak_start_year'].notna()].copy()
    if len(df_valid) < 3:
        return None

    df_valid['start_year'] = df_valid['outbreak_start_year'].astype(int)

    if 'outbreak_end_year' in df_valid.columns:
        df_valid['end_year'] = df_valid['outbreak_end_year'].fillna(df_valid['start_year']).astype(int)
    else:
        df_valid['end_year'] = df_valid['start_year']

    df_valid['duration'] = df_valid['end_year'] - df_valid['start_year'] + 1

    country_first_year = df_valid.groupby('outbreak_country')['start_year'].min().sort_values()
    countries_ordered = country_first_year.index.tolist()

    if len(countries_ordered) > 20:
        top_countries = df_valid['outbreak_country'].value_counts().head(20).index.tolist()
        df_valid = df_valid[df_valid['outbreak_country'].isin(top_countries)]
        countries_ordered = [c for c in countries_ordered if c in top_countries]

    n_countries = len(countries_ordered)
    fig_height = max(5, n_countries * 0.4 + 2)
    fig, ax = plt.subplots(figsize=(figsize[0], fig_height), dpi=300)

    country_to_y = {c: i for i, c in enumerate(countries_ordered)}

    for _, row in df_valid.iterrows():
        country = row['outbreak_country']
        if country not in country_to_y:
            continue
        y = country_to_y[country]
        start = row['start_year']
        duration = row['duration']

        has_cases = pd.notna(row.get('total_cases', np.nan)) and row.get('total_cases', 0) > 0
        color = LANCET_COLORS['primary'] if has_cases else LANCET_COLORS['light']
        alpha = 0.8 if has_cases else 0.5

        ax.barh(y, duration, left=start, height=0.6, color=color, alpha=alpha,
               edgecolor='white', linewidth=0.5)

    ax.set_yticks(range(n_countries))
    ax.set_yticklabels(countries_ordered, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel('Year')
    ax.set_title(f'{pathogen}: Outbreak Timeline by Country', fontweight='bold', pad=15)

    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.xaxis.grid(True, linestyle='-', alpha=0.2)
    ax.set_axisbelow(True)

    legend_elements = [
        mpatches.Patch(facecolor=LANCET_COLORS['primary'], alpha=0.8, label='With case data'),
        mpatches.Patch(facecolor=LANCET_COLORS['light'], alpha=0.5, label='No case data'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    year_range = (int(df_valid['start_year'].min()), int(df_valid['end_year'].max()))
    return {
        'n_outbreaks': len(df_valid),
        'n_countries': n_countries,
        'year_range': year_range
    }


def save_seasonality_plot(df, pathogen, outpath, figsize=(8, 5)):
    months = df['outbreak_start_month'].apply(parse_month).dropna()
    if len(months) < 5:
        return None

    month_counts = months.value_counts().sort_index()
    all_months = pd.Series(0, index=range(1, 13))
    for m, c in month_counts.items():
        all_months[int(m)] = c

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    month_labels = [calendar.month_abbr[i] for i in range(1, 13)]
    ax.bar(range(1, 13), all_months.values, color=LANCET_COLORS['secondary'],
           edgecolor='white', linewidth=0.5)

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)

    style_axis(ax, xlabel="Month", ylabel="Number of outbreak records",
               title=f"{pathogen}: Seasonality of Outbreak Start (n={len(months)})")

    ax.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    top_months = month_counts.nlargest(3)
    return {
        'n_records': len(months),
        'top_months': [(month_name(m), int(c)) for m, c in top_months.items()]
    }


def save_completeness_bar(df_completeness, pathogen, outpath, figsize=(10, 6)):
    df_plot = df_completeness.copy()
    df_plot = df_plot.sort_values('pct_complete', ascending=True)

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    colors_map = []
    for pct_val in df_plot['pct_complete']:
        if pct_val >= 75:
            colors_map.append(LANCET_COLORS['success'])
        elif pct_val >= 50:
            colors_map.append(LANCET_COLORS['quaternary'])
        elif pct_val >= 25:
            colors_map.append(LANCET_COLORS['tertiary'])
        else:
            colors_map.append(LANCET_COLORS['quinary'])

    labels = [get_display_name(v) for v in df_plot['variable']]
    y_pos = range(len(labels))

    bars = ax.barh(y_pos, df_plot['pct_complete'], color=colors_map,
                   edgecolor='white', linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 105)
    ax.axvline(x=50, color='gray', linestyle='--', alpha=0.5, linewidth=1)

    for bar, pct_v in zip(bars, df_plot['pct_complete']):
        ax.annotate(f'{pct_v:.0f}%',
                   xy=(bar.get_width() + 1, bar.get_y() + bar.get_height()/2),
                   va='center', ha='left', fontsize=8, color='#333333')

    style_axis(ax, xlabel="Completeness (%)",
              title=f"{pathogen}: Data Completeness by Variable")

    legend_elements = [
        mpatches.Patch(facecolor=LANCET_COLORS['success'], label='≥75%'),
        mpatches.Patch(facecolor=LANCET_COLORS['quaternary'], label='50-74%'),
        mpatches.Patch(facecolor=LANCET_COLORS['tertiary'], label='25-49%'),
        mpatches.Patch(facecolor=LANCET_COLORS['quinary'], label='<25%'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)


def save_cfr_histogram(df, pathogen, outpath, figsize=(8, 5)):
    if 'cfr_confirmed' not in df.columns:
        return None

    cfr_vals = df['cfr_confirmed'].dropna()
    cfr_vals = cfr_vals[(cfr_vals >= 0) & (cfr_vals <= 100)]

    if len(cfr_vals) < 5:
        return None

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    ax.hist(cfr_vals, bins=20, color=LANCET_COLORS['tertiary'],
            edgecolor='white', linewidth=0.5, alpha=0.8)

    median_cfr = cfr_vals.median()
    ax.axvline(x=median_cfr, color=LANCET_COLORS['quinary'], linestyle='--',
               linewidth=2, label=f'Median: {median_cfr:.1f}%')

    style_axis(ax, xlabel="Case Fatality Ratio (%)", ylabel="Number of outbreak records",
               title=f"{pathogen}: CFR Distribution (deaths/confirmed cases, n={len(cfr_vals)})")

    ax.legend(loc='upper right')
    ax.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return {
        'n_records': len(cfr_vals),
        'median': round(cfr_vals.median(), 1),
        'q25': round(cfr_vals.quantile(0.25), 1),
        'q75': round(cfr_vals.quantile(0.75), 1),
        'min': round(cfr_vals.min(), 1),
        'max': round(cfr_vals.max(), 1)
    }


def save_outbreak_size_histogram(df, pathogen, outpath, figsize=(8, 5)):
    if 'total_cases' not in df.columns:
        return None

    cases = df['total_cases'].dropna()
    cases = cases[cases > 0]

    if len(cases) < 5:
        return None

    fig, ax = plt.subplots(figsize=figsize, dpi=300)

    log_cases = np.log10(cases)
    ax.hist(log_cases, bins=20, color=LANCET_COLORS['primary'],
            edgecolor='white', linewidth=0.5, alpha=0.8)

    style_axis(ax, xlabel="Total cases (log₁₀ scale)", ylabel="Number of outbreak records",
               title=f"{pathogen}: Outbreak Size Distribution (n={len(cases)})")

    ax.yaxis.grid(True, linestyle='-', alpha=0.2, color='gray')
    ax.set_axisbelow(True)

    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return {
        'n_records': len(cases),
        'median': int(cases.median()),
        'q25': int(cases.quantile(0.25)),
        'q75': int(cases.quantile(0.75)),
        'min': int(cases.min()),
        'max': int(cases.max())
    }


def build_summary_tables(df) -> Tuple[Dict[str, pd.DataFrame], Dict[str, TableManifest]]:
    n_records = len(df)
    n_articles = df["article_id"].nunique() if "article_id" in df.columns else np.nan

    table_manifests = {}

    def freq(col, k=None):
        vals = [norm_str(x) for x in df[col].fillna("").tolist() if norm_str(x) and
                norm_str(x).lower() not in ['unspecified', 'not available', 'na', 'n/a', 'unknown']]
        c = Counter(vals)
        if k is None:
            items = c.most_common()
        else:
            items = c.most_common(k)
        out = []
        for name, count in items:
            out.append([name, int(count), pct(count, n_records)])
        return pd.DataFrame(out, columns=[col, "n", "%"])

    overview = pd.DataFrame([
        ["Outbreak records extracted", int(n_records)],
        ["Source articles", int(n_articles) if pd.notna(n_articles) else ""],
    ], columns=["Metric", "Value"])

    country = freq("outbreak_country") if "outbreak_country" in df.columns else pd.DataFrame()
    table_manifests["country"] = TableManifest(
        title="Geographic Distribution",
        table_number=1,
        columns=["Country", "Count", "Proportion"],
        n_rows=len(country),
        caption=f"Distribution of extracted outbreak records by country (n={n_records})."
    )

    detection = freq("mode_of_detection", k=10) if "mode_of_detection" in df.columns else pd.DataFrame()
    table_manifests["detection"] = TableManifest(
        title="Detection Mode",
        table_number=2,
        columns=["Detection Mode", "Count", "Proportion"],
        n_rows=len(detection),
        caption=f"Modes of outbreak detection reported (n={n_records})."
    )

    source = freq("outbreak_source", k=10) if "outbreak_source" in df.columns else pd.DataFrame()
    table_manifests["source"] = TableManifest(
        title="Outbreak Source",
        table_number=3,
        columns=["Source", "Count", "Proportion"],
        n_rows=len(source),
        caption=f"Reported outbreak sources (n={n_records})."
    )

    pre_outbreak = freq("pre_outbreak", k=10) if "pre_outbreak" in df.columns else pd.DataFrame()
    table_manifests["pre_outbreak"] = TableManifest(
        title="Pre-outbreak Context",
        table_number=4,
        columns=["Context", "Count", "Proportion"],
        n_rows=len(pre_outbreak),
        caption=f"Pre-outbreak epidemiological context (n={n_records})."
    )

    location_type = freq("outbreak_location_type", k=10) if "outbreak_location_type" in df.columns else pd.DataFrame()

    ongoing_yes = int((df["outbreak_is_currently_ongoing"] == True).sum()) if "outbreak_is_currently_ongoing" in df.columns else 0
    ongoing_no = int((df["outbreak_is_currently_ongoing"] == False).sum()) if "outbreak_is_currently_ongoing" in df.columns else 0
    ongoing = pd.DataFrame([
        ["Yes", ongoing_yes, pct(ongoing_yes, n_records)],
        ["No", ongoing_no, pct(ongoing_no, n_records)],
    ], columns=["outbreak_is_currently_ongoing", "n", "%"])
    table_manifests["ongoing"] = TableManifest(
        title="Ongoing Outbreaks",
        table_number=5,
        columns=["Ongoing Status", "Count", "Proportion"],
        n_rows=2,
        caption=f"Status of outbreaks at time of extraction (n={n_records})."
    )

    burden_cols = ['cases_confirmed', 'cases_probable', 'cases_suspected', 'cases_unspecified', 'deaths']
    burden_stats = []
    for col in burden_cols:
        if col in df.columns:
            vals = df[col].dropna()
            vals = vals[vals > 0]
            if len(vals) > 0:
                burden_stats.append({
                    'Variable': get_display_name(col),
                    'N reported': len(vals),
                    'Median': f"{vals.median():.0f}",
                    'IQR': f"{vals.quantile(0.25):.0f}–{vals.quantile(0.75):.0f}",
                    'Range': f"{vals.min():.0f}–{vals.max():.0f}"
                })
    burden = pd.DataFrame(burden_stats)
    table_manifests["burden"] = TableManifest(
        title="Case Burden Summary",
        table_number=6,
        columns=["Variable", "N reported", "Median", "IQR", "Range"],
        n_rows=len(burden),
        caption=f"Summary statistics for reported case counts and deaths across extracted outbreaks."
    )

    cfr_stats = []
    if 'cfr_confirmed' in df.columns:
        cfr_vals = df['cfr_confirmed'].dropna()
        cfr_vals = cfr_vals[(cfr_vals >= 0) & (cfr_vals <= 100)]
        if len(cfr_vals) >= 3:
            cfr_stats.append({
                'Denominator': 'Confirmed cases',
                'N': len(cfr_vals),
                'Median (%)': f"{cfr_vals.median():.1f}",
                'IQR (%)': f"{cfr_vals.quantile(0.25):.1f}–{cfr_vals.quantile(0.75):.1f}",
                'Range (%)': f"{cfr_vals.min():.1f}–{cfr_vals.max():.1f}"
            })
    if 'cfr_total' in df.columns:
        cfr_vals = df['cfr_total'].dropna()
        cfr_vals = cfr_vals[(cfr_vals >= 0) & (cfr_vals <= 100)]
        if len(cfr_vals) >= 3:
            cfr_stats.append({
                'Denominator': 'Total reported cases',
                'N': len(cfr_vals),
                'Median (%)': f"{cfr_vals.median():.1f}",
                'IQR (%)': f"{cfr_vals.quantile(0.25):.1f}–{cfr_vals.quantile(0.75):.1f}",
                'Range (%)': f"{cfr_vals.min():.1f}–{cfr_vals.max():.1f}"
            })
    cfr_summary = pd.DataFrame(cfr_stats)
    table_manifests["cfr"] = TableManifest(
        title="Case Fatality Ratio Summary",
        table_number=7,
        columns=["Denominator", "N", "Median (%)", "IQR (%)", "Range (%)"],
        n_rows=len(cfr_summary),
        caption=f"Summary of case fatality ratios computed from extracted outbreak data."
    )

    sex_n = 0
    if 'male_cases' in df.columns and 'female_cases' in df.columns:
        sex_data = df[['male_cases', 'female_cases']].dropna(how='all')
        sex_n = len(sex_data[(sex_data['male_cases'].notna()) | (sex_data['female_cases'].notna())])

    asymptomatic_n = df['cases_asymptomatic'].dropna().shape[0] if 'cases_asymptomatic' in df.columns else 0
    severe_n = df['cases_severe'].dropna().shape[0] if 'cases_severe' in df.columns else 0

    severity_reporting = pd.DataFrame([
        ['Sex-disaggregated data', sex_n, pct(sex_n, n_records)],
        ['Asymptomatic cases', asymptomatic_n, pct(asymptomatic_n, n_records)],
        ['Severe cases', severe_n, pct(severe_n, n_records)],
    ], columns=['Data type', 'N available', '%'])
    table_manifests["severity"] = TableManifest(
        title="Severity and Demographic Reporting",
        table_number=8,
        columns=["Data type", "N available", "Proportion"],
        n_rows=3,
        caption=f"Availability of severity and demographic data across extracted outbreak records (n={n_records})."
    )

    tables = {
        "overview": overview,
        "country": country,
        "detection": detection,
        "source": source,
        "pre_outbreak": pre_outbreak,
        "location_type": location_type,
        "ongoing": ongoing,
        "burden": burden,
        "cfr": cfr_summary,
        "severity": severity_reporting,
    }

    return tables, table_manifests


def build_line_list(df, max_rows=15):
    cols = [
        "outbreak_country",
        "outbreak_location",
        "outbreak_start_year",
        "outbreak_start_month",
        "cases_confirmed",
        "cases_suspected",
        "deaths",
        "mode_of_detection",
        "article_id",
    ]
    keep = [c for c in cols if c in df.columns]
    inv = df[keep].copy()
    if len(inv) > max_rows:
        inv = inv.head(max_rows).copy()
    inv.columns = [get_display_name(c) for c in inv.columns]
    return inv


def md_table_with_display_names(df):
    df_display = df.copy()
    df_display.columns = [get_display_name(c) for c in df_display.columns]
    try:
        return df_display.to_markdown(index=False)
    except Exception:
        return df_display.to_string(index=False)


def build_narrative(pathogen: str, df: pd.DataFrame, tables: Dict[str, pd.DataFrame], stats: Dict) -> Dict[str, str]:
    n_records = len(df)
    n_articles = df["article_id"].nunique() if "article_id" in df.columns else 0
    n_countries = df["outbreak_country"].nunique() if "outbreak_country" in df.columns else 0

    years = df['outbreak_start_year'].dropna() if 'outbreak_start_year' in df.columns else pd.Series()
    year_range = f"{int(years.min())}–{int(years.max())}" if len(years) > 0 else "unspecified"

    ongoing_n = int((df["outbreak_is_currently_ongoing"] == True).sum()) if "outbreak_is_currently_ongoing" in df.columns else 0

    sections = {}

    sections["coverage"] = (
        f"A total of {n_records} outbreak records were extracted from {n_articles} articles reporting on {pathogen} outbreaks. "
        f"The extracted records span {n_countries} countries, covering the period {year_range}. "
        + (f"At the time of extraction, {ongoing_n} outbreaks were reported as ongoing." if ongoing_n > 0 else "No outbreaks were reported as ongoing at the time of extraction.")
    )

    temporal_text = ""
    if len(years) > 0:
        peak_year = int(years.value_counts().idxmax())
        peak_count = int(years.value_counts().max())
        temporal_text = f"Outbreak reporting peaked in {peak_year} with {peak_count} records. "

    geo_text = ""
    if 'country' in tables and len(tables['country']) > 0:
        top_countries = tables['country'].head(3)
        countries_list = ", ".join([f"{row['outbreak_country']} (n={row['n']})" for _, row in top_countries.iterrows()])
        geo_text = f"The majority of outbreak records were from {countries_list}. "

    season_text = ""
    if 'seasonality' in stats and stats['seasonality']:
        top_months = stats['seasonality'].get('top_months', [])
        if top_months:
            month_str = ", ".join([f"{m} (n={c})" for m, c in top_months[:3]])
            season_text = f"Among records with known start month (n={stats['seasonality']['n_records']}), outbreak starts clustered in {month_str}."

    sections["temporal_geographic"] = temporal_text + geo_text + season_text

    burden_text = ""
    if 'burden' in tables and len(tables['burden']) > 0:
        for _, row in tables['burden'].iterrows():
            burden_text += f"{row['Variable']} were reported in {row['N reported']} records (median {row['Median']}, IQR {row['IQR']}). "

    cfr_text = ""
    if 'cfr' in tables and len(tables['cfr']) > 0:
        for _, row in tables['cfr'].iterrows():
            cfr_text += f"The CFR using {row['Denominator'].lower()} as denominator had a median of {row['Median (%)']}% (IQR {row['IQR (%)']}, n={row['N']}). "

    sections["burden_severity"] = burden_text + cfr_text if (burden_text or cfr_text) else "Case burden data were incompletely reported across extracted records."

    detection_text = ""
    if 'detection' in tables and len(tables['detection']) > 0:
        top_det = tables['detection'].iloc[0]
        detection_text = f"The most commonly reported mode of detection was {top_det['mode_of_detection']} ({top_det['%']}). "

    source_text = ""
    if 'source' in tables and len(tables['source']) > 0:
        top_src = tables['source'].iloc[0]
        source_text = f"The predominant reported outbreak source was {top_src['outbreak_source']} ({top_src['%']}). "

    context_text = ""
    if 'pre_outbreak' in tables and len(tables['pre_outbreak']) > 0:
        top_ctx = tables['pre_outbreak'].iloc[0]
        context_text = f"Pre-outbreak epidemiological context was predominantly described as {top_ctx['pre_outbreak']} ({top_ctx['%']})."

    sections["detection_context"] = detection_text + source_text + context_text if (detection_text or source_text or context_text) else "Detection methods and epidemiological context were inconsistently reported."

    completeness = stats.get('completeness', pd.DataFrame())
    if len(completeness) > 0:
        low_complete = completeness[completeness['pct_complete'] < 25]['variable'].tolist()
        if low_complete:
            low_str = ", ".join([get_display_name(v) for v in low_complete[:5]])
            gaps_text = f"Key variables with low reporting completeness (<25%) included: {low_str}. "
        else:
            gaps_text = "Most key variables had moderate to high reporting completeness. "
    else:
        gaps_text = ""

    sections["evidence_gaps"] = (
        gaps_text +
        "Heterogeneity in case definitions, detection methods, and reporting practices limits direct comparability across extracted outbreak records. "
        "These data should be interpreted with caution given the underlying variability in source article quality and completeness."
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


def yesish_data_used(x):
    if x is None:
        return False
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return x == 1
    s = str(x).strip().lower()
    return s in {"yes", "y", "true", "1"}


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

    n_records = len(df)
    n_articles = df["article_id"].nunique() if "article_id" in df.columns else 0

    key_cols = [
        'outbreak_start_year', 'outbreak_start_month', 'outbreak_end_year',
        'outbreak_country', 'outbreak_location', 'outbreak_source',
        'mode_of_detection', 'pre_outbreak',
        'cases_confirmed', 'cases_probable', 'cases_suspected', 'deaths',
        'cases_asymptomatic', 'cases_severe',
        'male_cases', 'female_cases'
    ]
    completeness = compute_completeness(df, [c for c in key_cols if c in df.columns])

    tables, table_manifests = build_summary_tables(df)
    manifest.tables = list(table_manifests.values())

    stats = {
        'completeness': completeness,
        'n_records': n_records,
        'n_articles': n_articles,
    }

    figure_number = 1

    choropleth_stats = save_choropleth_map(df, pathogen, arte / "fig1_choropleth_map.png")
    if choropleth_stats:
        stats['choropleth'] = choropleth_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig1_choropleth_map.png"),
            title="Disease Burden Choropleth Map",
            figure_number=figure_number,
            panels=["(A) Total cases by country", "(B) Total deaths by country"],
            caption=f"Geographic concentration of {pathogen} disease burden with country-level choropleth fill. Total cases: {choropleth_stats['total_cases']:,}; Total deaths: {choropleth_stats['total_deaths']:,}. Sub-national locations annotated where available ({choropleth_stats['n_locations_mapped']} locations mapped).",
            n_observations=n_records
        ))
        figure_number += 1

    timeline_stats = save_outbreak_timeline(df, pathogen, arte / "fig2_timeline.png")
    if timeline_stats:
        stats['timeline'] = timeline_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig2_timeline.png"),
            title="Outbreak Timeline",
            figure_number=figure_number,
            panels=["Gantt-style timeline by country"],
            caption=f"Timeline of {pathogen} outbreaks by country ({timeline_stats['year_range'][0]}–{timeline_stats['year_range'][1]}). Darker bars indicate records with case data available. n={timeline_stats['n_outbreaks']} records across {timeline_stats['n_countries']} countries.",
            n_observations=timeline_stats['n_outbreaks']
        ))
        figure_number += 1

    burden_stats = save_temporal_burden(df, pathogen, arte / "fig3_temporal_burden.png")
    if burden_stats:
        stats['temporal_burden'] = burden_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig3_temporal_burden.png"),
            title="Annual Case Burden",
            figure_number=figure_number,
            panels=["(A) Cases by year", "(B) Deaths by year"],
            caption=f"Annual reported case burden from extracted {pathogen} outbreak records. (A) Confirmed and suspected cases stacked by year. (B) Reported deaths by year. Total confirmed: {burden_stats['total_confirmed']:,}; total suspected: {burden_stats['total_suspected']:,}; total deaths: {burden_stats['total_deaths']:,}.",
            n_observations=n_records
        ))
        figure_number += 1

    geo_bar_stats = save_geographic_bar_complete(df, pathogen, arte / "fig4_geographic_bar.png")
    if geo_bar_stats:
        stats['geographic'] = geo_bar_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig4_geographic_bar.png"),
            title="Outbreak Records by Country",
            figure_number=figure_number,
            panels=["All countries with outbreak records"],
            caption=f"Complete geographic distribution of {pathogen} outbreak records across {geo_bar_stats['n_countries']} countries.",
            n_observations=n_records
        ))
        figure_number += 1

    season_stats = save_seasonality_plot(df, pathogen, arte / "fig5_seasonality.png")
    if season_stats:
        stats['seasonality'] = season_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig5_seasonality.png"),
            title="Seasonality of Outbreak Start",
            figure_number=figure_number,
            panels=["Monthly distribution of outbreak starts"],
            caption=f"Seasonality of {pathogen} outbreak start month among records with available data (n={season_stats['n_records']}).",
            n_observations=season_stats['n_records']
        ))
        figure_number += 1

    cfr_stats = save_cfr_histogram(df, pathogen, arte / "fig6_cfr.png")
    if cfr_stats:
        stats['cfr'] = cfr_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig6_cfr.png"),
            title="CFR Distribution",
            figure_number=figure_number,
            panels=["Distribution of case fatality ratios"],
            caption=f"Distribution of case fatality ratios (deaths/confirmed cases) among {pathogen} outbreaks with available data (n={cfr_stats['n_records']}). Median CFR {cfr_stats['median']}% (IQR {cfr_stats['q25']}–{cfr_stats['q75']}%).",
            n_observations=cfr_stats['n_records']
        ))
        figure_number += 1

    cfr_country_stats = save_cfr_by_country(df, pathogen, arte / "fig7_cfr_country.png")
    if cfr_country_stats:
        stats['cfr_country'] = cfr_country_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig7_cfr_country.png"),
            title="CFR by Country",
            figure_number=figure_number,
            panels=["CFR distribution by country"],
            caption=f"Case fatality ratio by country for {pathogen} (n={cfr_country_stats['n_countries']} countries with ≥2 records). Overall median CFR: {cfr_country_stats['overall_median']}%.",
            n_observations=cfr_country_stats['n_countries']
        ))
        figure_number += 1

    size_stats = save_outbreak_size_histogram(df, pathogen, arte / "fig8_size.png")
    if size_stats:
        stats['size'] = size_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig8_size.png"),
            title="Outbreak Size Distribution",
            figure_number=figure_number,
            panels=["Distribution of outbreak sizes (log scale)"],
            caption=f"Distribution of outbreak sizes (total reported cases) for {pathogen} (n={size_stats['n_records']}). Median {size_stats['median']} cases (IQR {size_stats['q25']}–{size_stats['q75']}).",
            n_observations=size_stats['n_records']
        ))
        figure_number += 1

    evidence_stats = save_evidence_gaps(df, pathogen, arte / "fig9_evidence_gaps.png")
    if evidence_stats:
        stats['evidence_gaps'] = evidence_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig9_evidence_gaps.png"),
            title="Evidence Availability",
            figure_number=figure_number,
            panels=["Percentage of records with each variable"],
            caption=f"Evidence availability by variable group for {pathogen} extracted records (n={n_records}). Vertical lines at 50% and 75% thresholds.",
            n_observations=n_records
        ))
        figure_number += 1

    missingness_stats = save_missingness_heatmap(df, pathogen, arte / "fig10_missingness.png")
    if missingness_stats:
        stats['missingness'] = missingness_stats
        manifest.figures.append(FigureManifest(
            path=str(arte / "fig10_missingness.png"),
            title="Data Completeness Matrix",
            figure_number=figure_number,
            panels=["Records × variables missingness heatmap"],
            caption=f"Data completeness matrix for {pathogen} outbreak records (n={missingness_stats['n_records']} records × {missingness_stats['n_variables']} variables). Green indicates data present; light indicates missing.",
            n_observations=missingness_stats['n_records']
        ))
        figure_number += 1

    save_completeness_bar(completeness, pathogen, arte / "fig11_completeness.png")
    manifest.figures.append(FigureManifest(
        path=str(arte / "fig11_completeness.png"),
        title="Data Completeness Summary",
        figure_number=figure_number,
        panels=["Completeness by variable"],
        caption=f"Completeness of extracted outbreak variables for {pathogen} (n={n_records}). Colors indicate completeness thresholds: ≥75% (green), 50-74% (yellow), 25-49% (orange), <25% (red).",
        n_observations=n_records
    ))

    manifest.summary_statistics = {
        "n_records": n_records,
        "n_articles": n_articles,
        "n_countries": df["outbreak_country"].nunique() if "outbreak_country" in df.columns else 0,
        "year_min": int(df['outbreak_start_year'].min()) if 'outbreak_start_year' in df.columns and df['outbreak_start_year'].notna().any() else None,
        "year_max": int(df['outbreak_start_year'].max()) if 'outbreak_start_year' in df.columns and df['outbreak_start_year'].notna().any() else None,
    }

    line_list = build_line_list(df, max_rows=15)
    narrative_sections = build_narrative(pathogen, df, tables, stats)
    manifest.narrative_sections = list(narrative_sections.keys())

    md = []
    md.append(f"# {pathogen} — Extracted Outbreak Records\n")

    md.append("## Overview\n")
    md.append(narrative_sections["coverage"] + "\n")

    md.append("---\n")
    md.append("## Summary\n")
    md.append(f"| Metric | Value |")
    md.append(f"|:-------|------:|")
    md.append(f"| Outbreak records extracted | {n_records} |")
    md.append(f"| Source articles | {n_articles} |")
    n_countries = manifest.summary_statistics.get('n_countries', 0)
    md.append(f"| Countries represented | {n_countries} |")
    year_min = manifest.summary_statistics.get('year_min')
    year_max = manifest.summary_statistics.get('year_max')
    if year_min and year_max:
        md.append(f"| Year range | {year_min}–{year_max} |")
    md.append("")

    md.append("---\n")
    md.append("## Figure 1: Disease Burden Choropleth Map\n")
    md.append("![Choropleth Map](figures/fig1_choropleth_map.png)\n")
    if choropleth_stats:
        md.append(f"**Figure 1.** Geographic concentration of {pathogen} disease burden with country-level choropleth fill. Sub-national locations annotated where available.\n")

    md.append("---\n")
    md.append("## Figure 2: Outbreak Timeline\n")
    md.append("![Timeline](figures/fig2_timeline.png)\n")
    if timeline_stats:
        md.append(f"**Figure 2.** Timeline of {pathogen} outbreaks by country ({timeline_stats['year_range'][0]}–{timeline_stats['year_range'][1]}).\n")

    md.append("---\n")
    md.append("## Temporal and Geographic Distribution\n")
    md.append(narrative_sections["temporal_geographic"] + "\n")

    if (arte / "fig3_temporal_burden.png").exists():
        md.append("---\n")
        md.append("## Figure 3: Annual Case Burden\n")
        md.append("![Temporal Burden](figures/fig3_temporal_burden.png)\n")
        if burden_stats:
            md.append(f"**Figure 3.** Annual case burden. (A) Confirmed and suspected cases. (B) Deaths. Total confirmed: {burden_stats['total_confirmed']:,}; deaths: {burden_stats['total_deaths']:,}.\n")

    if (arte / "fig4_geographic_bar.png").exists():
        md.append("---\n")
        md.append("## Figure 4: Outbreak Records by Country\n")
        md.append("![Geographic Bar](figures/fig4_geographic_bar.png)\n")
        md.append(f"**Figure 4.** Complete distribution of outbreak records across all {geo_bar_stats['n_countries'] if geo_bar_stats else n_countries} reporting countries.\n")

    if (arte / "fig5_seasonality.png").exists():
        md.append("---\n")
        md.append("## Figure 5: Seasonality\n")
        md.append("![Seasonality](figures/fig5_seasonality.png)\n")

    md.append("---\n")
    md.append("## Burden and Severity\n")
    md.append(narrative_sections["burden_severity"] + "\n")

    if (arte / "fig6_cfr.png").exists():
        md.append("---\n")
        md.append("## Figure 6: CFR Distribution\n")
        md.append("![CFR Distribution](figures/fig6_cfr.png)\n")

    if (arte / "fig7_cfr_country.png").exists():
        md.append("---\n")
        md.append("## Figure 7: CFR by Country\n")
        md.append("![CFR by Country](figures/fig7_cfr_country.png)\n")

    if (arte / "fig8_size.png").exists():
        md.append("---\n")
        md.append("## Figure 8: Outbreak Size Distribution\n")
        md.append("![Outbreak Size](figures/fig8_size.png)\n")

    md.append("---\n")
    md.append("## Detection and Epidemiological Context\n")
    md.append(narrative_sections["detection_context"] + "\n")

    md.append("---\n")
    md.append("## Evidence Gaps and Limitations\n")
    md.append(narrative_sections["evidence_gaps"] + "\n")

    if (arte / "fig9_evidence_gaps.png").exists():
        md.append("---\n")
        md.append("## Figure 9: Evidence Availability\n")
        md.append("![Evidence Gaps](figures/fig9_evidence_gaps.png)\n")

    if (arte / "fig10_missingness.png").exists():
        md.append("---\n")
        md.append("## Figure 10: Data Completeness Matrix\n")
        md.append("![Missingness](figures/fig10_missingness.png)\n")

    if (arte / "fig11_completeness.png").exists():
        md.append("---\n")
        md.append("## Figure 11: Data Completeness Summary\n")
        md.append("![Completeness](figures/fig11_completeness.png)\n")

    md.append("---\n")
    md.append("## Tables\n")

    md.append("### Table 1: Geographic Distribution\n")
    if len(tables["country"]) > 0:
        md.append(md_table_with_display_names(tables["country"]) + "\n")
        md.append(f"*{table_manifests['country'].caption}*\n")

    md.append("### Table 2: Detection Mode\n")
    if len(tables["detection"]) > 0:
        md.append(md_table_with_display_names(tables["detection"]) + "\n")
        md.append(f"*{table_manifests['detection'].caption}*\n")

    md.append("### Table 3: Outbreak Source\n")
    if len(tables["source"]) > 0:
        md.append(md_table_with_display_names(tables["source"]) + "\n")
        md.append(f"*{table_manifests['source'].caption}*\n")

    md.append("### Table 4: Pre-outbreak Context\n")
    if len(tables["pre_outbreak"]) > 0:
        md.append(md_table_with_display_names(tables["pre_outbreak"]) + "\n")
        md.append(f"*{table_manifests['pre_outbreak'].caption}*\n")

    md.append("### Table 5: Case Burden Summary\n")
    if len(tables["burden"]) > 0:
        md.append(md_table_with_display_names(tables["burden"]) + "\n")
        md.append(f"*{table_manifests['burden'].caption}*\n")

    md.append("### Table 6: CFR Summary\n")
    if len(tables["cfr"]) > 0:
        md.append(md_table_with_display_names(tables["cfr"]) + "\n")
        md.append(f"*{table_manifests['cfr'].caption}*\n")

    md.append("### Table 7: Severity and Demographic Reporting\n")
    if len(tables["severity"]) > 0:
        md.append(md_table_with_display_names(tables["severity"]) + "\n")
        md.append(f"*{table_manifests['severity'].caption}*\n")

    md.append("---\n")
    md.append("## Outbreak Line List (Sample)\n")
    md.append(f"Table presents a sample of {len(line_list)} extracted outbreak records. The complete dataset of {n_records} records is available in the supplementary data.\n")
    md.append("\n### Sample of Extracted Outbreak Records\n")
    try:
        md.append(line_list.to_markdown(index=False) + "\n")
    except:
        md.append(line_list.to_string(index=False) + "\n")
    md.append(f"*Sample of {len(line_list)} records from {n_records} extracted {pathogen} outbreak records.*\n")

    md.append("---\n")
    md.append("## Data Availability\n")
    md.append(f"The complete dataset of extracted outbreak records for {pathogen} (n={n_records}) has been made available to support future epidemiological research and outbreak preparedness efforts.\n")

    out_root.mkdir(parents=True, exist_ok=True)
    md_path = out_root / "outbreaks_writeup.md"
    pdf_path = out_root / "outbreaks_writeup.pdf"
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

def run_outbreaks_writeup(config):
    config.report_outbreaks_dir.mkdir(parents=True, exist_ok=True)
    return run_for_pathogen(
        config.pathogen,
        str(config.data_extraction_outbreaks_path),
        out_root=config.report_outbreaks_dir,
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        pathogen_name = sys.argv[2] if len(sys.argv) > 2 else "Pathogen"
        run_for_pathogen(pathogen_name, csv_path)
    else:
        print("Usage: python writeup.py <csv_path> [pathogen_name]")
        print("Example: python writeup.py data.csv Zika")
