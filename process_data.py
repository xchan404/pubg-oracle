# -*- coding: utf-8 -*-
"""
معالج البيانات النهائي (Data Processor Orchestrator) - النسخة المحدثة
يقرأ البيانات الخام من قاعدة البيانات،
ويمررها عبر منظف النصوص (Cleaner) ثم محرك الاستخراج (Parser)،
ويحفظ البيانات المهيكلة في جدول parsed_accounts (مع الحقول الجديدة)
ويصدرها إلى CSV لتكون جاهزة لتدريب الـ AI.
"""

import sys
import logging
import csv
import sqlite3
from pathlib import Path

from config import DB_PATH
from database.db import SessionLocal, engine, init_db
from database.models import ParsedAccount, RawMessage
from parser.text_cleaner import clean_text
from parser.regex_parser import parse_account_data
from ml.features import FeatureEngineer

from ml.pipeline import pipeline_instance

import io

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# إعداد السجلات للطباعة على الشاشة
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("data_processor")


def init_parsed_db():
    """
    إعادة إنشاء قاعدة البيانات باستخدام SQLAlchemy.
    """
    try:
        init_db()
        # مسح البيانات القديمة لإعادة المعالجة بالذكاء الجديد
        db = SessionLocal()
        db.query(ParsedAccount).delete()
        db.commit()
        db.close()
        logger.info("تم تهيئة قاعدة البيانات وتنظيف جدول parsed_accounts بنجاح.")
    except Exception as e:
        logger.error(f"خطأ أثناء تهيئة قاعدة البيانات: {str(e)}")
        raise


def process_and_save_all():
    """
    قراءة جميع الرسائل الخام، تنظيفها، استخراج خصائصها ومحركات الذكاء، وحفظها.
    """
    db = SessionLocal()
    try:
        rows = db.query(RawMessage).all()
        logger.info(f"تم العثور على {len(rows):,} رسالة خام في قاعدة البيانات.")

        parsed_data_list = []
        skipped = 0

        for i, row in enumerate(rows, 1):
            raw_text = row.text
            if not raw_text or not raw_text.strip():
                skipped += 1
                continue

            # --- معالجة شاملة موحدة من خلال الـ FeaturePipeline ---
            data = pipeline_instance.process(raw_text)
            data['message_id'] = row.message_id
            data['channel_username'] = row.channel_username
            
            parsed_data_list.append(data)

            # --- الحفظ في SQLAlchemy ---
            account = ParsedAccount(
                message_id=row.message_id,
                channel_username=row.channel_username,
                price_egp=data.get('price_egp'),
                price_usd=data.get('price_usd'),
                account_level=data.get('account_level'),
                mythics_count=data.get('mythics_count'),
                prestige_score=data.get('prestige_score', 0),
                rarity_score=data.get('rarity_score', 0),
                combo_multiplier=data.get('combo_multiplier', 1.0),
                active_combos_str=data.get('active_combos_str', ''),
                extracted_items_str=data.get('extracted_items_str', '')
            )
            db.merge(account)

            if i % 1000 == 0:
                db.commit()
                logger.info(f"  تقدم: {i:,}/{len(rows):,} رسالة...")

        db.commit()
        logger.info(f"تمت المعالجة: {len(parsed_data_list):,} سجل محفوظ، {skipped} رسالة فارغة متجاهلة.")
        return parsed_data_list

    except Exception as e:
        db.rollback()
        logger.error(f"خطأ أثناء المعالجة: {str(e)}", exc_info=True)
        return []
    finally:
        db.close()


def export_parsed_to_csv(parsed_data_list: list):
    """تصدير البيانات المهيكلة إلى ملف CSV."""
    if not parsed_data_list:
        return

    export_dir = Path("data/parsed/csv")
    export_dir.mkdir(parents=True, exist_ok=True)
    csv_file = export_dir / "all_parsed_accounts.csv"

    headers = [
        "channel_username", "message_id",
        "account_level", "mythics_count", "guns_count", "xsuits_count",
        "price_egp", "price_usd",
        "m4_type", "m4_level", "m4_is_max",
        "rare_items_str",
        "has_xsuit", "has_m4_glacier", "has_joker_fox", "has_joker_fox_locked",
        "has_mummy", "has_double_mummy", "has_conqueror", "has_vehicle_dev",
        "has_face_girl", "has_lobby_mythic", "has_car_mclaren", "has_car_dodge",
        "has_ghazi", "has_ghawas",
        "has_soap_blue", "has_soap_black", "has_soap_rare", "has_soap_double",
        "has_scarf_tiger",
        "has_hair_qarnain", "has_hair_kaboria", "has_hair_yellow",
        "prestige_score", "rarity_score", "combo_multiplier", "active_combos_str",
        "has_m4_max_x_mummy", "has_m4_x_xsuit", "guns_per_mythic_ratio", "has_super_combo",
        "clean_text",
    ]

    try:
        with open(csv_file, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(parsed_data_list)
        logger.info(f"تم تصدير {len(parsed_data_list):,} سجل بنجاح إلى: {csv_file}")
    except Exception as e:
        logger.error(f"خطأ أثناء تصدير الـ CSV: {str(e)}")


def print_summary(parsed_data_list: list):
    """طباعة ملخص سريع بعد المعالجة."""
    total = len(parsed_data_list)
    if total == 0:
        return
    has_price  = sum(1 for d in parsed_data_list if d['price_egp'] or d['price_usd'])
    has_m4     = sum(1 for d in parsed_data_list if d['m4_type'])
    has_glacier= sum(1 for d in parsed_data_list if d['has_m4_glacier'])
    has_joker  = sum(1 for d in parsed_data_list if d['has_joker_fox'])
    has_xsuit  = sum(1 for d in parsed_data_list if d['has_xsuit'])
    has_mummy  = sum(1 for d in parsed_data_list if d['has_mummy'])
    has_conq   = sum(1 for d in parsed_data_list if d['has_conqueror'])

    m4_types = {}
    for d in parsed_data_list:
        t = d.get('m4_type')
        if t:
            m4_types[t] = m4_types.get(t, 0) + 1

    print()
    print("=" * 50)
    print("  ملخص نتائج المعالجة المحدثة")
    print("=" * 50)
    print(f"  إجمالي السجلات        : {total:,}")
    print(f"  لديه سعر              : {has_price:,}  ({has_price/total*100:.1f}%)")
    print(f"  لديه امفور (أي نوع)   : {has_m4:,}  ({has_m4/total*100:.1f}%)")
    print(f"  امفور تلجي            : {has_glacier:,}")
    print(f"  جوكر فوكس            : {has_joker:,}")
    print(f"  بدلة إكس             : {has_xsuit:,}")
    print(f"  موميا                : {has_mummy:,}")
    print(f"  كونكر                : {has_conq:,}")
    print()
    print("  توزيع أنواع الامفور:")
    for t, cnt in sorted(m4_types.items(), key=lambda x: -x[1]):
        print(f"    {t:<15}: {cnt:,}")
    print("=" * 50)


if __name__ == "__main__":
    logger.info("=== بدء مرحلة تنظيف واستخراج البيانات (نسخة محدثة) ===")
    init_parsed_db()
    data = process_and_save_all()
    if data:
        export_parsed_to_csv(data)
        print_summary(data)
    logger.info("=== انتهت العملية بنجاح ===")
