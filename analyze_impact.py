# -*- coding: utf-8 -*-
"""
تحليل الأثر النسبي لكل خاصية على السعر
(Feature Impact Analysis)
يحسب لكل feature: وسيط السعر مع الخاصية مقابل بدونها، ونسبة التأثير %.
"""

import sys
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path
from config import DB_PATH

plt.rcParams['figure.facecolor'] = '#0f0f1a'
plt.rcParams['axes.facecolor']   = '#1a1a2e'
plt.rcParams['axes.edgecolor']   = '#444466'
plt.rcParams['axes.labelcolor']  = '#ccccee'
plt.rcParams['xtick.color']      = '#aaaacc'
plt.rcParams['ytick.color']      = '#aaaacc'
plt.rcParams['text.color']       = '#eeeeee'
plt.rcParams['grid.color']       = '#2a2a4a'
plt.rcParams['grid.alpha']       = 0.5

EDA_DIR = Path("data/eda")
EDA_DIR.mkdir(parents=True, exist_ok=True)

# ─── تحميل البيانات ───
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("SELECT * FROM parsed_accounts", conn)
conn.close()

# نركز على الحسابات التي عندها سعر مصري واضح
df_priced = df[df['price_egp'].notna()].copy()
df_priced = df_priced[df_priced['price_egp'] > 100]  # فلتر القيم الصغيرة جداً
p95 = df_priced['price_egp'].quantile(0.95)
df_priced = df_priced[df_priced['price_egp'] <= p95]  # فلتر الـ Outliers

print(f"عدد الحسابات المسعّرة بعد الفلترة: {len(df_priced):,}")
base_median = df_priced['price_egp'].median()
print(f"الوسيط الأساسي للسعر: {base_median:,.0f} ج.م\n")

# ─── 1. Binary Features Impact ───
binary_features = {
    # العناصر الأقوى تأثيراً
    'has_joker_fox_locked':  'جوكر فوكس مقفول',
    'has_joker_fox':         'جوكر فوكس (أي)',
    'has_double_mummy':      'دبل موميا',
    'has_mummy':             'موميا (أي)',
    'has_plane_frame':       'إطار الطيارة',
    'has_re2_frame':         'إطار RE2',
    'has_conqueror_frame':   'إطار كونكر',
    'has_conqueror':         'كونكر (لقب)',
    'has_airdrop_car':       'سيارة إسقاط جوي',
    'has_car_mclaren':       'مكلارين',
    'has_car_dodge':         'دودج',
    'm4_is_max':             'امفور ماكس',
    'has_xsuit':             'بدلة إكس (أي)',
    'has_lobby_mythic':      'لوبي ميثك دائم',
    'has_ghazi':             'الغازي',
    'has_ghawas':            'الغواص',
    'has_face_girl':         'فيس بنت',
    'has_vehicle_dev':       'سيارة تطوير',
    'has_m4_glacier':        'امفور تلجي',
    'has_soap_blue':         'صابونه زرقاء',
    'has_soap_black':        'صابونه سوداء',
    'has_soap_rare':         'صابونه ألوان (نادر)',
    'has_soap_double':       'دبل صابونه',
    'has_scarf_tiger':       'وشاح النمر',
    'has_hair_qarnain':      'شعر القرنين',
    'has_hair_kaboria':      'شعر كابوريا',
    'has_hair_yellow':       'شعر أصفر',
}

results = []
for col, label in binary_features.items():
    if col not in df_priced.columns:
        continue
    yes = df_priced[df_priced[col] == 1]['price_egp']
    no  = df_priced[df_priced[col] == 0]['price_egp']
    if len(yes) < 10:
        continue
    med_yes = yes.median()
    med_no  = no.median()
    impact  = (med_yes - med_no) / med_no * 100 if med_no > 0 else 0
    results.append({
        'label':    label,
        'col':      col,
        'count':    len(yes),
        'med_yes':  med_yes,
        'med_no':   med_no,
        'impact':   impact,
    })

results_df = pd.DataFrame(results).sort_values('impact', ascending=True)

# ─── 2. رسم Binary Features Impact ───
fig, ax = plt.subplots(figsize=(13, 9))
colors = ['#f87171' if x < 0 else ('#a78bfa' if x < 50 else '#34d399') for x in results_df['impact']]
bars = ax.barh(results_df['label'], results_df['impact'], color=colors, edgecolor='#333355')

for bar, row in zip(bars, results_df.itertuples()):
    txt = f"+{row.impact:.0f}%  ({row.count:,} حساب)  وسيط: {row.med_yes:,.0f} ج"
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
            txt, va='center', fontsize=8.5, color='#ddddee')

ax.axvline(0, color='#6666aa', linewidth=1, linestyle='--')
ax.set_xlabel('نسبة التأثير على السعر الوسيط (%)')
ax.set_xlim(-20, results_df['impact'].max() * 1.55)
ax.grid(axis='x')
plt.suptitle('الأثر النسبي لكل خاصية على سعر الحساب (الجنيه المصري)', fontsize=14, fontweight='bold', color='#a78bfa')
plt.tight_layout()
plt.savefig(EDA_DIR / '09_feature_impact.png', dpi=150, bbox_inches='tight', facecolor='#0f0f1a')
plt.close()
print("[saved] data/eda/09_feature_impact.png")

# ─── 3. متغيرات رقمية: Correlation بالسعر ───
numeric_features = {
    'account_level':      'مستوى الحساب',
    'collection_level':   'لفل المجموعات',
    'mythics_count':      'عدد الميثكات',
    'guns_count':         'أسلحة المختبر',
    'xsuits_count':       'عدد بدلات الإكس',
    'cars_total':         'إجمالي السيارات',
    'cars_mythic':        'السيارات الميثك',
    'conqueror_frames_count': 'إطارات كونكر (عدد)',
    'm4_level':           'مستوى الامفور',
}

num_results = []
for col, label in numeric_features.items():
    if col not in df_priced.columns:
        continue
    sub = df_priced[[col, 'price_egp']].dropna()
    if len(sub) < 30:
        continue
    corr = sub[col].corr(sub['price_egp'])
    num_results.append({'label': label, 'col': col, 'corr': corr, 'n': len(sub)})

num_df = pd.DataFrame(num_results).sort_values('corr', ascending=True)

fig, ax = plt.subplots(figsize=(10, 6))
cols_color = ['#f87171' if c < 0 else '#a78bfa' for c in num_df['corr']]
bars = ax.barh(num_df['label'], num_df['corr'], color=cols_color, edgecolor='#333355')
for bar, row in zip(bars, num_df.itertuples()):
    ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
            f"r={row.corr:.2f}  (n={row.n:,})", va='center', fontsize=9, color='#ddddee')
ax.axvline(0, color='#6666aa', linewidth=1, linestyle='--')
ax.set_xlabel('Pearson Correlation مع سعر الجنيه المصري')
ax.set_xlim(-0.3, num_df['corr'].max() * 1.5)
ax.grid(axis='x')
plt.suptitle('ارتباط المتغيرات الرقمية بالسعر (Pearson r)', fontsize=14, fontweight='bold', color='#a78bfa')
plt.tight_layout()
plt.savefig(EDA_DIR / '10_numeric_correlation.png', dpi=150, bbox_inches='tight', facecolor='#0f0f1a')
plt.close()
print("[saved] data/eda/10_numeric_correlation.png")

# ─── 4. السعر مقابل عدد السيارات ولفل المجموعات ───
cars_col_exists   = 'cars_total' in df_priced.columns
collect_col_exists = 'collection_level' in df_priced.columns

if cars_col_exists or collect_col_exists:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    if cars_col_exists:
        df_cars = df_priced[df_priced['cars_total'].notna()].copy()
        if len(df_cars) > 50:
            axes[0].scatter(df_cars['cars_total'], df_cars['price_egp'],
                            alpha=0.35, s=20, color='#a78bfa')
            avg_by_cars = df_cars.groupby('cars_total')['price_egp'].median()
            axes[0].plot(avg_by_cars.index, avg_by_cars.values,
                         color='#34d399', linewidth=2.5, marker='o', markersize=5)
            axes[0].set_xlabel('عدد السيارات الإجمالي')
            axes[0].set_ylabel('السعر (جنيه مصري)')
            axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
            axes[0].set_title('السعر مقابل عدد السيارات')
            axes[0].grid()

    if collect_col_exists:
        sub_cl = df_priced[df_priced['collection_level'].notna()]
        if len(sub_cl) > 50:
            axes[1].scatter(sub_cl['collection_level'], sub_cl['price_egp'],
                            alpha=0.35, s=20, color='#34d399')
            avg_by_cl = sub_cl.groupby(sub_cl['collection_level'].round())['price_egp'].median()
            axes[1].plot(avg_by_cl.index, avg_by_cl.values,
                         color='#a78bfa', linewidth=2.5, marker='o', markersize=5)
            axes[1].set_xlabel('لفل المجموعات')
            axes[1].set_ylabel('')
            axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
            axes[1].set_title('السعر مقابل لفل المجموعات')
            axes[1].grid()

    plt.suptitle('تأثير السيارات ولفل المجموعات على السعر', fontsize=14, fontweight='bold', color='#a78bfa')
    plt.tight_layout()
    plt.savefig(EDA_DIR / '11_cars_and_collection.png', dpi=150, bbox_inches='tight', facecolor='#0f0f1a')
    plt.close()
    print("[saved] data/eda/11_cars_and_collection.png")

# ─── 5. طباعة التقرير النهائي ───
print()
print("=" * 60)
print("  التأثير النسبي لكل خاصية على سعر الحساب (بالجنيه المصري)")
print(f"  الوسيط الأساسي: {base_median:,.0f} ج.م | n={len(df_priced):,}")
print("=" * 60)
print(f"{'الخاصية':<35} {'العدد':>7} {'وسيط_مع':>10} {'تأثير%':>8}")
print("-" * 62)
for _, row in results_df.sort_values('impact', ascending=False).iterrows():
    bar = "█" * int(abs(row['impact']) / 5)
    sign = "+" if row['impact'] >= 0 else ""
    print(f"{row['label']:<35} {int(row['count']):>7,} {row['med_yes']:>10,.0f}  {sign}{row['impact']:>6.1f}%  {bar}")

print()
print("--- ارتباط المتغيرات الرقمية بالسعر ---")
for _, row in num_df.sort_values('corr', ascending=False).iterrows():
    print(f"  {row['label']:<30} r={row['corr']:.3f}  (n={int(row['n']):,})")
print("=" * 60)
