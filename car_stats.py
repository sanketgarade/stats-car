#!/usr/bin/env python3
"""car_stats.py

Modifications requested:
- Do not plot the fuel type distribution (in the distribution grid).
- Plot the vehicle model distribution for top 20 models
- Replace deprecated applymap usage to avoid FutureWarning.
- Plot the model vs color heatmap in a separate image file.
- Do not print Cramer's V to terminal (but still compute/save contingency table).

Usage:
    python3 car_stats_cli_updated2.py --cardata cardata.csv --classes car_classes.csv --outdir ./car_stats_plots --show

Requirements: pandas, numpy, matplotlib, (optional scipy)
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys

try:
    from scipy.stats import chi2_contingency
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False

def normalize_string(s):
    if pd.isna(s):
        return ''
    return str(s).strip().lower()

def cramers_v(confusion_matrix):
    # kept for potential future use but will not be printed
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
    phi2corr = max(0, phi2 - ((k-1)*(r-1))/(n-1))
    rcorr = r - ((r-1)**2)/(n-1)
    kcorr = k - ((k-1)**2)/(n-1)
    denom = min((kcorr-1), (rcorr-1))
    if denom <= 0:
        return float('nan')
    v = np.sqrt(phi2corr / denom)
    return v

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
    df.columns = [c.strip() for c in df.columns]

    # Load classes
    if classes_path.exists():
        classes = pd.read_csv(classes_path)
        classes.columns = [c.strip() for c in classes.columns]
        classes['_maker_l'] = classes['Maker'].apply(normalize_string)
        classes['_model_l'] = classes['Model'].apply(normalize_string)
        classes_keyed = classes.set_index(['_maker_l','_model_l'])[['Class','Fuel']].drop_duplicates()
    else:
        classes_keyed = None
        classes = pd.DataFrame(columns=['Maker','Model','Class','Fuel'])

    # Prepare keys in survey data
    df['_maker_l'] = df['Maker'].apply(normalize_string)
    df['_model_l'] = df['Model'].apply(normalize_string)

    # Merge
    if classes_keyed is not None:
        merged = df.merge(classes_keyed, left_on=['_maker_l','_model_l'], right_index=True, how='left')
    else:
        merged = df.copy()
        merged['Class'] = pd.NA
        merged['Fuel'] = pd.NA

    # Loose model-only match for missing entries
    missing_mask = merged['Class'].isna() | merged['Fuel'].isna()
    if missing_mask.any() and not classes.empty:
        model_map = classes.set_index(classes['Model'].apply(normalize_string))[['Class','Fuel']].to_dict(orient='index')
        for idx, row in merged[missing_mask].iterrows():
            mkey = normalize_string(row['Model'])
            if mkey in model_map:
                if pd.isna(merged.at[idx, 'Class']):
                    merged.at[idx, 'Class'] = model_map[mkey]['Class']
                if pd.isna(merged.at[idx, 'Fuel']):
                    merged.at[idx, 'Fuel'] = model_map[mkey]['Fuel']

    merged['Class'] = merged['Class'].fillna('Unknown')
    merged['Fuel'] = merged['Fuel'].fillna('Unknown')

    # Save merged
    merged_out = outdir / 'cardata_merged.csv'
    merged.to_csv(merged_out, index=False)
    print(f"Merged data saved to: {merged_out}")

    # Print rows with any Unknown or missing values
    unknown_mask = merged[['Maker','Model','Color','Class','Fuel']].isna().any(axis=1)
    # Replace deprecated applymap usage: use column-wise comparison and combine
    contains_unknown = (
        (merged['Maker'].astype(str).str.strip().str.lower() == 'unknown') |
        (merged['Model'].astype(str).str.strip().str.lower() == 'unknown') |
        (merged['Color'].astype(str).str.strip().str.lower() == 'unknown') |
        (merged['Class'].astype(str).str.strip().str.lower() == 'unknown') |
        (merged['Fuel'].astype(str).str.strip().str.lower() == 'unknown')
    )
    problem_rows = merged[unknown_mask | contains_unknown]
    if not problem_rows.empty:
        print("\n=== Rows with missing or Unknown values ===")
        pd.set_option('display.max_columns', None)
        print(problem_rows.to_string(index=False))
    else:
        print("\nNo rows with missing or 'Unknown' values found.")

    # Frequency distributions
    model_counts = merged['Model'].value_counts()
    color_counts = merged['Color'].value_counts()
    maker_counts = merged['Maker'].value_counts()
    class_counts = merged['Class'].value_counts()
    fuel_counts = merged['Fuel'].value_counts()

    # Save frequency CSVs
    model_counts.to_csv(outdir / 'freq_model.csv', header=['Count'])
    color_counts.to_csv(outdir / 'freq_color.csv', header=['Count'])
    maker_counts.to_csv(outdir / 'freq_maker.csv', header=['Count'])
    class_counts.to_csv(outdir / 'freq_class.csv', header=['Count'])
    fuel_counts.to_csv(outdir / 'freq_fuel.csv', header=['Count'])

    # Contingency and heatmap
    ct = pd.crosstab(merged['Model'], merged['Color'])
    ct.to_csv(outdir / 'contingency_model_color.csv')

    # Compute Cramer's V silently (do not print)
    _ = cramers_v(ct)

    # --- Combined Boxplots (single image) ---
    box_out = outdir / 'combined_boxplots.png'
    fig, axes = plt.subplots(1, 3, figsize=(14,5))
    # Maker
    axes[0].boxplot(maker_counts.values)
    axes[0].set_title('Counts per Maker')
    axes[0].set_ylabel('Counts')
    # Class
    axes[1].boxplot(class_counts.values)
    axes[1].set_title('Counts per Class')
    # Fuel (kept in boxplots)
    axes[2].boxplot(fuel_counts.values)
    axes[2].set_title('Counts per Fuel')
    plt.tight_layout()
    plt.savefig(box_out)
    if show_plots:
        plt.show()
    plt.close()
    print(f"Saved combined boxplots to: {box_out}")

    # --- Combined Distribution Plots (single image) ---
    # Now include ALL models (not top X)
    dist_out = outdir / 'combined_distributions.png'
    fig, axes = plt.subplots(2, 2, figsize=(14,10))
    axes = axes.flatten()
    # Model (ALL)
    model_counts.nlargest(20).plot(kind='bar', ax=axes[0])
    axes[0].set_title('Model (top 20)')
    axes[0].tick_params(axis='x', rotation=45)
    # Color (top 12)
    color_counts.nlargest(12).plot(kind='bar', ax=axes[1])
    axes[1].set_title('Color (top 12)')
    axes[1].tick_params(axis='x', rotation=45)
    # Maker (all)
    maker_counts.plot(kind='bar', ax=axes[2])
    axes[2].set_title('Maker')
    axes[2].tick_params(axis='x', rotation=45)
    # Class
    class_counts.plot(kind='bar', ax=axes[3])
    axes[3].set_title('Class')
    axes[3].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(dist_out)
    if show_plots:
        plt.show()
    plt.close()
    print(f"Saved combined distribution plots to: {dist_out}")

    # --- Model vs Color heatmap (separate image) ---
    try:
        heatmap_path = outdir / 'heatmap_model_color.png'
        plt.figure(figsize=(12, max(6, ct.shape[0]*0.2)))
        plt.imshow(ct.values, aspect='auto')
        plt.colorbar()
        plt.xticks(ticks=np.arange(ct.shape[1]), labels=ct.columns, rotation=45, ha='right')
        plt.yticks(ticks=np.arange(ct.shape[0]), labels=ct.index)
        plt.title('Heatmap: Model vs Color (counts)')
        plt.tight_layout()
        plt.savefig(heatmap_path)
        if show_plots:
            plt.show()
        plt.close()
        print(f"Saved heatmap to: {heatmap_path}")
    except Exception as e:
        print('Could not draw heatmap:', e, file=sys.stderr)

    print(f"\nAll outputs saved in: {outdir.resolve()}")

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Compute statistics and combined plots for surveyed car data.')
    p.add_argument('--cardata', default='cardata.csv', help='CSV file with observed cars (default cardata.csv)')
    p.add_argument('--classes', default='car_classes.csv', help='CSV file with maker/model -> class,fuel (default car_classes.csv)')
    p.add_argument('--outdir', default='./car_stats_plots', help='Folder to save outputs (default ./car_stats_plots)')
    p.add_argument('--show', action='store_true', help='Show plots interactively')
    args = p.parse_args()
    main(args.cardata, args.classes, args.outdir, args.show)
