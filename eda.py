# -*- coding: utf-8 -*-
"""
تحليل واستكشاف البيانات (EDA - Exploratory Data Analysis)
يقوم هذا الملف بتحليل شامل لـ Dataset حسابات ببجي المجمعة،
ويُنتج مجموعة من الرسوم البيانية المحفوظة كـ PNG في مجلد data/eda/
بالإضافة إلى تقرير نصي مفصل بالأرقام والإحصاءات.
"""

import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')   # بدون نافذة واجهة رسومية - يحفظ مباشرة كملف
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import warnings
import os
from pathlib import Path

warnings.filterwarnings('ignore')

# ========================
# إعدادات بصرية عامة
# ========================
plt.rcParams['figure.facecolor'] = '#0f0f1a'
plt.rcParams['axes.facecolor']   = '#1a1a2e'
plt.rcParams['axes.edgecolor']   = '#444466'
plt.rcParams['axes.labelcolor']  = '#ccccee'
plt.rcParams['xtick.color']      = '#aaaacc'
plt.rcParams['ytick.color']      = '#aaaacc'
plt.rcParams['text.color']       = '#eeeeee'
plt.rcParams['grid.color']       = '#2a2a4a'
plt.rcParams['grid.linestyle']   = '--'
plt.rcParams['grid.alpha']       = 0.5

ACCENT   = '#a78bfa'   # بنفسجي فاتح - للعناصر الرئيسية
ACCENT2  = '#34d399'   # أخضر نعناعي - للمقارنات
ACCENT3  = '#f87171'   # أحمر وردي - للتحذيرات والقيم الشاذة
PALETTE  = [ACCENT, ACCENT2, ACCENT3, '#60a5fa', '#fbbf24']

EDA_DIR = Path("data/eda")
EDA_DIR.mkdir(parents=True, exist_ok=True)

# ========================
# تحميل البيانات
# ========================
from config import DB_PATH
conn = sqlite3.connect(DB_PATH)

df = pd.read_sql_query("""
    SELECT
        p.channel_username,
        p.message_id,
        p.account_level,
        p.mythics_count,
        p.guns_count,
        p.price_egp,
        p.price_usd,
        p.has_m4_glacier,
        p.has_xsuit,
        p.has_mummy,
        r.views,
        r.forwards,
        r.date
    FROM parsed_accounts p
    LEFT JOIN raw_messages r
        ON p.channel_username = r.channel_username AND p.message_id = r.message_id
""", conn)
conn.close()

df['date'] = pd.to_datetime(df['date'], utc=True)
df['month'] = df['date'].dt.to_period('M').astype(str)
total = len(df)

print(f"تم تحميل {total:,} سجل بنجاح.")

# ========================
# دالة مساعدة لحفظ وتنسيق الرسوم
# ========================
def save_fig(filename, title):
    plt.suptitle(title, fontsize=14, fontweight='bold', color=ACCENT, y=1.01)
    plt.tight_layout()
    path = EDA_DIR / filename
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=plt.rcParams['figure.facecolor'])
    plt.close()
    print(f"  [saved] {path}")

# =====================================
# 1. نظرة عامة - تغطية الخصائص (Coverage)
# =====================================
print("\n[1/8] رسم تغطية استخراج الخصائص...")
features = {
    'Price EGP\n(سعر بالمصري)':     df['price_egp'].notna().sum(),
    'Price USD\n(سعر بالدولار)':     df['price_usd'].notna().sum(),
    'Level\n(المستوى)':              df['account_level'].notna().sum(),
    'Mythics\n(الميثك)':             df['mythics_count'].notna().sum(),
    'Guns Lab\n(المختبر)':           df['guns_count'].notna().sum(),
    'X-Suit\n(بدلة إكس)':            df['has_xsuit'].sum(),
    'M4 Glacier\n(تلجي ماكس)':       df['has_m4_glacier'].sum(),
    'Mummy\n(موميا)':                df['has_mummy'].sum(),
}
fig, ax = plt.subplots(figsize=(12, 5))
bars = ax.barh(list(features.keys()), list(features.values()), color=ACCENT, edgecolor='#6d28d9')
for bar, val in zip(bars, features.values()):
    pct = val / total * 100
    ax.text(bar.get_width() + 50, bar.get_y() + bar.get_height()/2,
            f'{val:,}  ({pct:.1f}%)', va='center', fontsize=9, color='#ccccee')
ax.set_xlabel('عدد السجلات')
ax.set_xlim(0, total * 1.18)
ax.axvline(total, color=ACCENT3, linestyle='--', alpha=0.6, label=f'إجمالي السجلات ({total:,})')
ax.legend(fontsize=9)
ax.grid(axis='x')
save_fig('01_feature_coverage.png', 'تغطية استخراج الخصائص من الداتا')

# ============================
# 2. توزيع الرسائل لكل قناة
# ============================
print("[2/8] رسم توزيع الرسائل لكل قناة...")
ch_counts = df.groupby('channel_username').size().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(9, 4))
colors_ch = [ACCENT, ACCENT2, ACCENT3]
bars = ax.barh(ch_counts.index, ch_counts.values, color=colors_ch[:len(ch_counts)], edgecolor='#333355')
for bar, val in zip(bars, ch_counts.values):
    ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
            f'{val:,}', va='center', fontsize=10, color='#eeeeee')
ax.set_xlabel('عدد الرسائل')
ax.grid(axis='x')
save_fig('02_messages_by_channel.png', 'توزيع الرسائل لكل قناة')

# =====================================
# 3. توزيع الأسعار - جنيه مصري
# =====================================
print("[3/8] رسم توزيع أسعار الجنيه المصري...")
egp = df[df['price_egp'].notna()]['price_egp']
# تصفية القيم الشاذة الواضحة (فوق 95th percentile)
egp_clean = egp[egp <= egp.quantile(0.95)]
egp_outliers = egp[egp > egp.quantile(0.95)]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Histogram
axes[0].hist(egp_clean, bins=40, color=ACCENT, edgecolor='#6d28d9', alpha=0.85)
axes[0].set_xlabel('السعر (جنيه مصري)')
axes[0].set_ylabel('عدد الحسابات')
axes[0].set_title(f'توزيع الأسعار بالجنيه (بدون القيم الشاذة)\nn={len(egp_clean):,}')
axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
axes[0].grid(axis='y')

# Box Plot لإظهار الوسيط والنطاق الربيعي
axes[1].boxplot(egp_clean, vert=False, patch_artist=True,
                boxprops=dict(facecolor=ACCENT, color='#6d28d9'),
                medianprops=dict(color=ACCENT2, linewidth=2),
                whiskerprops=dict(color='#aaaacc'),
                capprops=dict(color='#aaaacc'),
                flierprops=dict(marker='o', color=ACCENT3, alpha=0.4, markersize=3))
axes[1].set_xlabel('السعر (جنيه مصري)')
axes[1].set_title(f'نطاق الأسعار (Box Plot)\nالوسيط: {egp_clean.median():,.0f} جنيه')
axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
axes[1].grid(axis='x')

save_fig('03_price_egp_distribution.png', 'توزيع الأسعار بالجنيه المصري')

# =====================================
# 4. توزيع الأسعار - دولار
# =====================================
print("[4/8] رسم توزيع أسعار الدولار...")
usd = df[df['price_usd'].notna()]['price_usd']
usd_clean = usd[usd <= usd.quantile(0.95)]

fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(usd_clean, bins=35, color=ACCENT2, edgecolor='#065f46', alpha=0.85)
ax.set_xlabel('السعر (دولار أمريكي)')
ax.set_ylabel('عدد الحسابات')
ax.axvline(usd_clean.median(), color=ACCENT3, linestyle='--', linewidth=2,
           label=f'الوسيط: ${usd_clean.median():.0f}')
ax.axvline(usd_clean.mean(), color='#fbbf24', linestyle=':', linewidth=2,
           label=f'المتوسط: ${usd_clean.mean():.0f}')
ax.legend()
ax.grid(axis='y')
save_fig('04_price_usd_distribution.png', f'توزيع الأسعار بالدولار (n={len(usd_clean):,})')

# =====================================
# 5. السعر مقابل المستوى
# =====================================
print("[5/8] رسم السعر مقابل مستوى الحساب...")
df_both = df[df['price_egp'].notna() & df['account_level'].notna()].copy()
df_both = df_both[df_both['price_egp'] <= df_both['price_egp'].quantile(0.95)]

fig, ax = plt.subplots(figsize=(10, 5))
sc = ax.scatter(df_both['account_level'], df_both['price_egp'],
                alpha=0.35, s=18, c=df_both['mythics_count'],
                cmap='plasma', linewidths=0)
cbar = plt.colorbar(sc, ax=ax)
cbar.set_label('عدد الميثكات', color='#ccccee')
ax.set_xlabel('مستوى الحساب (Level)')
ax.set_ylabel('السعر بالجنيه المصري')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
ax.grid()
save_fig('05_price_vs_level.png', 'السعر مقابل المستوى (ملون بعدد الميثكات)')

# =====================================
# 6. السعر مقابل الميثك
# =====================================
print("[6/8] رسم السعر مقابل عدد الميثكات...")
df_m = df[df['price_egp'].notna() & df['mythics_count'].notna()].copy()
df_m = df_m[df_m['price_egp'] <= df_m['price_egp'].quantile(0.95)]
df_m = df_m[df_m['mythics_count'] <= df_m['mythics_count'].quantile(0.98)]

# حساب متوسط السعر لكل نطاق ميثك
bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 100, 150, 200]
df_m['mythic_bin'] = pd.cut(df_m['mythics_count'], bins=bins)
avg_by_mythic = df_m.groupby('mythic_bin', observed=True)['price_egp'].median().dropna()

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

axes[0].scatter(df_m['mythics_count'], df_m['price_egp'],
                alpha=0.3, s=15, color=ACCENT)
axes[0].set_xlabel('عدد الميثكات')
axes[0].set_ylabel('السعر (جنيه مصري)')
axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
axes[0].set_title('السعر مقابل الميثك (كل سجل)')
axes[0].grid()

avg_by_mythic.plot(kind='bar', ax=axes[1], color=ACCENT, edgecolor='#6d28d9')
axes[1].set_xlabel('نطاق عدد الميثكات')
axes[1].set_ylabel('متوسط السعر (جنيه)')
axes[1].set_title('متوسط السعر لكل نطاق ميثك')
axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
axes[1].tick_params(axis='x', rotation=45)
axes[1].grid(axis='y')

save_fig('06_price_vs_mythics.png', 'السعر مقابل عدد الميثكات')

# =====================================
# 7. تأثير المميزات النادرة على السعر
# =====================================
print("[7/8] رسم تأثير المميزات النادرة على السعر...")
df_price = df[df['price_egp'].notna()].copy()
df_price = df_price[df_price['price_egp'] <= df_price['price_egp'].quantile(0.95)]

features_flags = ['has_xsuit', 'has_m4_glacier', 'has_mummy']
labels = ['بدلة إكس\n(X-Suit)', 'تلجي ماكس\n(M4 Glacier)', 'موميا\n(Mummy)']

fig, axes = plt.subplots(1, 3, figsize=(14, 5))
for ax, feat, lbl in zip(axes, features_flags, labels):
    data_yes = df_price[df_price[feat] == 1]['price_egp']
    data_no  = df_price[df_price[feat] == 0]['price_egp']
    bp = ax.boxplot([data_no, data_yes], patch_artist=True, vert=True,
                    labels=['بدون', 'معه'],
                    boxprops=dict(facecolor=ACCENT, color='#6d28d9'),
                    medianprops=dict(color=ACCENT2, linewidth=2.5),
                    whiskerprops=dict(color='#aaaacc'),
                    capprops=dict(color='#aaaacc'),
                    flierprops=dict(marker='.', color=ACCENT3, alpha=0.3, markersize=4))
    bp['boxes'][0].set_facecolor('#2d2d4e')
    ax.set_title(lbl)
    ax.set_ylabel('السعر (جنيه)' if feat == features_flags[0] else '')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
    ax.grid(axis='y')
    med_yes = data_yes.median()
    med_no  = data_no.median()
    diff_pct = (med_yes - med_no) / med_no * 100 if med_no > 0 else 0
    ax.text(0.5, 0.96, f'+{diff_pct:.0f}% مع المميزة', transform=ax.transAxes,
            ha='center', va='top', fontsize=9, color=ACCENT2)

save_fig('07_rare_features_impact.png', 'تأثير المميزات النادرة على السعر')

# =====================================
# 8. نشاط النشر عبر الزمن (شهرياً)
# =====================================
print("[8/8] رسم نشاط النشر عبر الزمن...")
monthly = df.groupby('month').size()
fig, ax = plt.subplots(figsize=(12, 4))
ax.fill_between(monthly.index, monthly.values, alpha=0.3, color=ACCENT)
ax.plot(monthly.index, monthly.values, color=ACCENT, linewidth=2, marker='o', markersize=5)
ax.set_xlabel('الشهر')
ax.set_ylabel('عدد المنشورات')
ax.tick_params(axis='x', rotation=45)
ax.grid(axis='y')
save_fig('08_posts_over_time.png', 'نشاط النشر في القنوات عبر الزمن (شهرياً)')

# =====================================
# تقرير نصي مفصل
# =====================================
egp_all = df['price_egp'].dropna()
usd_all = df['price_usd'].dropna()
report_path = EDA_DIR / "eda_report.txt"
with open(report_path, 'w', encoding='utf-8') as f:
    def w(line=""): f.write(line + '\n'); print(line)
    w("=" * 55)
    w("  تقرير تحليل داتا حسابات ببجي موبايل  ")
    w("  PUBG Mobile Account Dataset EDA Report ")
    w("=" * 55)
    w()
    w(f"إجمالي السجلات الخام       : {total:,}")
    w()
    w("--- تغطية استخراج الأسعار ---")
    w(f"لديه سعر بالجنيه           : {egp_all.notna().sum():,} ({egp_all.notna().sum()/total*100:.1f}%)")
    w(f"لديه سعر بالدولار          : {usd_all.notna().sum():,} ({usd_all.notna().sum()/total*100:.1f}%)")
    w(f"بدون أي سعر                : {df['price_egp'].isna().sum() - df['price_usd'].notna().sum():,} ≈{(df['price_egp'].isna() & df['price_usd'].isna()).sum()/total*100:.1f}%")
    w()
    w("--- إحصاءات الأسعار - جنيه مصري ---")
    w(f"  الوسيط   : {egp_all.median():,.0f} ج.م")
    w(f"  المتوسط  : {egp_all.mean():,.0f} ج.م")
    w(f"  الأدنى   : {egp_all.min():,.0f} ج.م")
    w(f"  الأعلى   : {egp_all.max():,.0f} ج.م")
    w(f"  الربع 25% : {egp_all.quantile(0.25):,.0f} ج.م")
    w(f"  الربع 75% : {egp_all.quantile(0.75):,.0f} ج.م")
    w()
    w("--- إحصاءات الأسعار - دولار أمريكي ---")
    w(f"  الوسيط   : ${usd_all.median():,.0f}")
    w(f"  المتوسط  : ${usd_all.mean():,.0f}")
    w(f"  الأدنى   : ${usd_all.min():,.0f}")
    w(f"  الأعلى   : ${usd_all.max():,.0f}")
    w()
    w("--- تغطية المميزات ---")
    w(f"  المستوى (Level)            : {df['account_level'].notna().sum():,} ({df['account_level'].notna().sum()/total*100:.1f}%)")
    w(f"  الميثك (Mythics Count)     : {df['mythics_count'].notna().sum():,} ({df['mythics_count'].notna().sum()/total*100:.1f}%)")
    w(f"  المختبر (Guns Lab Count)   : {df['guns_count'].notna().sum():,} ({df['guns_count'].notna().sum()/total*100:.1f}%)")
    w(f"  بدلة إكس (X-Suit)          : {df['has_xsuit'].sum():,} ({df['has_xsuit'].sum()/total*100:.1f}%)")
    w(f"  تلجي ماكس (M4 Glacier)     : {df['has_m4_glacier'].sum():,} ({df['has_m4_glacier'].sum()/total*100:.1f}%)")
    w()
    w("--- الوسيط حسب المميزة ---")
    for feat, lbl in zip(features_flags, ['X-Suit', 'M4 Glacier', 'Mummy']):
        med_yes = df[df[feat]==1]['price_egp'].median()
        med_no  = df[df[feat]==0]['price_egp'].median()
        if med_no and med_yes:
            diff = (med_yes - med_no) / med_no * 100
            w(f"  {lbl}: بدون={med_no:,.0f} ج  مع={med_yes:,.0f} ج  (+{diff:.0f}%)")
    w()
    w("--- الرسائل لكل قناة ---")
    for ch, cnt in df.groupby('channel_username').size().items():
        w(f"  {ch}: {cnt:,}")
    w()
    w(f"الرسوم البيانية محفوظة في: {EDA_DIR.resolve()}")
    w("=" * 55)

print(f"\n✅ تم إنشاء جميع الرسوم والتقرير في: {EDA_DIR.resolve()}")
