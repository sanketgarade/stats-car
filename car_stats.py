#!/usr/bin/env python3
"""car_stats_cli.py

Usage:
    python3 car_stats_cli.py --cardata cardata.csv --classes car_classes.csv
Both arguments are optional; defaults are cardata.csv and car_classes.csv in the working directory.

What it does:
- Loads the survey data (cardata) and the car classes data (car_classes).
- Merges them on Maker+Model (case-insensitive) to attach Class and Fuel to each observed row.
- Produces frequency distributions for Model, Color, Maker, Class, and Fuel.
- Produces bar plots for these distributions and boxplots of counts per Maker, Class, and Fuel.
- Computes contingency table (Model x Color) and Cramér's V for association strength.
- Saves plots into ./car_stats_plots/ and prints summary to stdout.

Requirements:
- pandas, numpy, matplotlib
- scipy (optional, used for chi-square); script has fallback if scipy is not present.
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

try:
    from scipy.stats import chi2_contingency
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False

def cramers_v(confusion_matrix):
    """Compute Cramér's V statistic for categorical-categorical association."""
    n = confusion_matrix.sum().sum()
    if n == 0:
        return float('nan')
    if SCIPY_AVAILABLE:
        chi2, p, dof, expected = chi2_contingency(confusion_matrix)
    else:
        row_sums = confusion_matrix.sum(axis=1).values.reshape(-1,1)
        col_sums = confusion_matrix.sum(axis=0).values.reshape(1,-1)
        expected = row_sums.dot(col_sums) / n
        observed = confusion_matrix.values
        with np.errstate(divide='ignore', invalid='ignore'):
            chi2 = ((observed - expected) ** 2 / expected)
            chi2 = np.nansum(chi2)
    phi2 = chi2 / n
    r, k = confusion_matrix.shape
    # Bias correction
    phi2corr = max(0, phi2 - ((k-1)*(r-1))/(n-1))
    rcorr = r - ((r-1)**2)/(n-1)
    kcorr = k - ((k-1)**2)/(n-1)
    denom = min((kcorr-1), (rcorr-1))
    if denom <= 0:
        return float('nan')
    v = np.sqrt(phi2corr / denom)
    return v

def normalize_string(s):
    if pd.isna(s):
        return ''
    return str(s).strip().lower()

def main(cardata_path, classes_path, outdir, show_plots):
    cardata_path = Path(cardata_path)
    classes_path = Path(classes_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not cardata_path.exists():
        print(f"ERROR: cardata file not found: {cardata_path}", file=sys.stderr)
        sys.exit(1)
    if not classes_path.exists():
        print(f"WARNING: classes file not found: {classes_path}. Will proceed but Class/Fuel will be unknown.", file=sys.stderr)

    df = pd.read_csv(cardata_path)
    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Load classes if provided
    if classes_path.exists():
        classes = pd.read_csv(classes_path)
        classes.columns = [c.strip() for c in classes.columns]
        # Create lowercase keys for robust merge: maker+model
        classes['_maker_l'] = classes['Maker'].apply(normalize_string)
        classes['_model_l'] = classes['Model'].apply(normalize_string)
        classes_keyed = classes.set_index(['_maker_l','_model_l'])[['Class','Fuel']].drop_duplicates()
    else:
        classes = None
        classes_keyed = None

    # prepare df keys
    df['_maker_l'] = df['Maker'].apply(normalize_string)
    df['_model_l'] = df['Model'].apply(normalize_string)

    # Merge by maker+model (case-insensitive)
    if classes_keyed is not None:
        merged = df.merge(classes_keyed, left_on=['_maker_l','_model_l'], right_index=True, how='left')
    else:
        merged = df.copy()
        merged['Class'] = pd.NA
        merged['Fuel'] = pd.NA

    # If Class or Fuel missing, attempt a looser match on Model only (helps when Maker naming differs)
    missing_mask = merged['Class'].isna() | merged['Fuel'].isna()
    if missing_mask.any() and classes_keyed is not None:
        model_map = classes.set_index(classes['Model'].apply(normalize_string))[['Class','Fuel']].to_dict(orient='index')
        for idx, row in merged[missing_mask].iterrows():
            mkey = normalize_string(row['Model'])
            if mkey in model_map:
                if pd.isna(merged.at[idx, 'Class']):
                    merged.at[idx, 'Class'] = model_map[mkey]['Class']
                if pd.isna(merged.at[idx, 'Fuel']):
                    merged.at[idx, 'Fuel'] = model_map[mkey]['Fuel']

    # Fill remaining unknowns
    merged['Class'] = merged['Class'].fillna('Unknown')
    merged['Fuel'] = merged['Fuel'].fillna('Unknown')

    # Save merged file
    merged_out = outdir / 'cardata_merged.csv'
    merged.to_csv(merged_out, index=False)
    print(f"Merged data saved to: {merged_out}")

    # --- Frequency distributions ---
    print('\n=== Frequency distributions (top 20) ===')
    print('\nModels:')
    print(merged['Model'].value_counts().head(20))
    print('\nColors:')
    print(merged['Color'].value_counts().head(20))
    print('\nMakers:')
    print(merged['Maker'].value_counts().head(20))
    print('\nClasses:')
    print(merged['Class'].value_counts().head(20))
    print('\nFuels:')
    print(merged['Fuel'].value_counts().head(20))

    # Save frequency tables
    merged['Model'].value_counts().to_csv(outdir / 'freq_model.csv', header=['Count'])
    merged['Color'].value_counts().to_csv(outdir / 'freq_color.csv', header=['Count'])
    merged['Maker'].value_counts().to_csv(outdir / 'freq_maker.csv', header=['Count'])
    merged['Class'].value_counts().to_csv(outdir / 'freq_class.csv', header=['Count'])
    merged['Fuel'].value_counts().to_csv(outdir / 'freq_fuel.csv', header=['Count'])

    # --- Contingency and Cramér's V ---
    ct = pd.crosstab(merged['Model'], merged['Color'])
    ct.to_csv(outdir / 'contingency_model_color.csv')
    v = cramers_v(ct)
    print(f"\nCramér's V between Model and Color: {v:.4f}")

    # --- Plots ---
    def save_bar(series, title, fname):
        plt.figure(figsize=(10,5))
        series.sort_values(ascending=False).plot(kind='bar')
        plt.title(title)
        plt.xlabel(series.name if series.name is not None else 'Category')
        plt.ylabel('Count')
        plt.tight_layout()
        path = outdir / fname
        plt.savefig(path)
        if show_plots:
            plt.show()
        plt.close()
        print(f"Saved: {path}")

    def save_box_from_counts(counts_series, title, fname):
        # counts_series is Series indexed by group, values are counts
        plt.figure(figsize=(6,4))
        # Boxplot requires a sequence; we provide the counts
        plt.boxplot(counts_series.values, vert=True)
        plt.title(title)
        plt.ylabel('Counts')
        plt.tight_layout()
        path = outdir / fname
        plt.savefig(path)
        if show_plots:
            plt.show()
        plt.close()
        print(f"Saved: {path}")

    # Basic bar charts
    save_bar(merged['Model'].value_counts(), 'Model frequency', 'model_freq.png')
    save_bar(merged['Color'].value_counts(), 'Color frequency', 'color_freq.png')
    save_bar(merged['Maker'].value_counts(), 'Maker frequency', 'maker_freq.png')
    save_bar(merged['Class'].value_counts(), 'Class frequency', 'class_freq.png')
    save_bar(merged['Fuel'].value_counts(), 'Fuel frequency', 'fuel_freq.png')

    # Boxplots of per-group counts (numeric distribution of counts)
    save_box_from_counts(merged['Maker'].value_counts(), 'Boxplot of counts per Maker', 'box_maker_counts.png')
    save_box_from_counts(merged['Class'].value_counts(), 'Boxplot of counts per Class', 'box_class_counts.png')
    save_box_from_counts(merged['Fuel'].value_counts(), 'Boxplot of counts per Fuel', 'box_fuel_counts.png')

    # Heatmap for contingency table (Model x Color)
    try:
        plt.figure(figsize=(10,6))
        plt.imshow(ct.values, aspect='auto')
        plt.colorbar()
        plt.xticks(ticks=np.arange(ct.shape[1]), labels=ct.columns, rotation=45, ha='right')
        plt.yticks(ticks=np.arange(ct.shape[0]), labels=ct.index)
        plt.title('Heatmap: Model vs Color (counts)')
        plt.tight_layout()
        heatmap_path = outdir / 'heatmap_model_color.png'
        plt.savefig(heatmap_path)
        if show_plots:
            plt.show()
        plt.close()
        print(f"Saved: {heatmap_path}")
    except Exception as e:
        print('Could not draw heatmap:', e, file=sys.stderr)

    print('\nAll plots and CSVs are saved in the folder:', outdir.resolve())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Compute statistics and plots for surveyed car data.')
    p.add_argument('--cardata', default='cardata.csv', help='CSV file with observed cars (default cardata.csv)')
    p.add_argument('--classes', default='car_classes.csv', help='CSV file with maker/model -> class,fuel (default car_classes.csv)')
    p.add_argument('--outdir', default='./car_stats_plots', help='Folder to save outputs (default ./car_stats_plots)')
    p.add_argument('--show', action='store_true', help='Show plots interactively (can be used in notebook/desktop env)')
    args = p.parse_args()
    main(args.cardata, args.classes, args.outdir, args.show)
