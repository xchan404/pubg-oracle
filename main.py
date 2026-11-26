"""
المشغل الرئيسي (Main Execution Orchestrator)
نقطة انطلاق النظام. يتعامل مع واجهة السطر البرمجي (CLI CLI Args)،
ويهيئ السجلات (Logging)، ويبدأ قاعدة البيانات، ثم يطلق عملية السحب لكل قناة،
ويختم بتصدير البيانات تلقائياً لملفات CSV و JSON.
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from datetime import UTC, datetime, timedelta

# استيراد الوحدات الخاصة بنا
import config
from database import db as database
from scraper.channels import get_active_channels
from scraper.telegram_scraper import TelegramScraper


def setup_logging():
    """
    تهيئة وإعداد السجلات (Logging) للكتابة في ملف السجلات وفي الكونسول (الشاشة).
    """
    # التأكد من وجود مجلد السجلات
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pubg_scraper")
    logger.setLevel(logging.INFO)

    # تنسيق الرسائل في السجل
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. مخرج الملف (File Handler)
    file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 2. مخرج الشاشة (Console Handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

def export_backup_files(channel_file_name: str, display_name: str):
    """
    تقوم بجلب كافة بيانات قناة معينة من SQLite وتصديرها كنسخ احتياطية بصيغة CSV و JSON.

    المعاملات:
        channel_file_name (str): اسم ملف القناة الموحد للاستخدام في التخزين.
        display_name (str): اسم القناة للعرض في السجلات.
    """
    logger = logging.getLogger("pubg_scraper")
    logger.info(f"بدء تصدير البيانات الاحتياطية للقناة {display_name}...")

    try:
        conn = database.get_connection()
        messages = database.get_all_messages_for_channel(conn, channel_file_name)
        conn.close()

        if not messages:
            logger.warning(f"لا توجد بيانات مسحوبة في قاعدة البيانات للقناة {display_name} لتصديرها.")
            return

        # 1. التصدير لصيغة CSV
        csv_file_path = config.CSV_DIR / f"{channel_file_name}.csv"
        headers = [
            "message_id", "channel_username", "date", "text",
            "views", "forwards", "has_photo", "photo_path",
            "is_grouped", "scraped_at"
        ]

        with open(csv_file_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for msg in messages:
                writer.writerow(msg)

        # 2. التصدير لصيغة JSON
        # نستخدم ensure_ascii=False للحفاظ على النصوص العربية واضحة دون تشفير
        json_file_path = config.JSON_DIR / f"{channel_file_name}.json"
        with open(json_file_path, mode="w", encoding="utf-8") as f:
            json.dump(messages, f, indent=4, ensure_ascii=False)

        logger.info(f"تم تصدير {len(messages)} سجل بنجاح للقناة {display_name}:")
        logger.info(f"   - CSV: {csv_file_path.relative_to(config.BASE_DIR)}")
        logger.info(f"   - JSON: {json_file_path.relative_to(config.BASE_DIR)}")

    except Exception as e:
        logger.error(f"خطأ أثناء تصدير النسخ الاحتياطية للقناة {display_name}: {str(e)}")

async def run_scrape_cycle(scraper, channel_list, from_date, to_date, logger) -> int:
    """One pass over all configured channels. Returns new message count."""
    total_new_messages = 0
    for channel_info in channel_list:
        logger.info("=" * 60)
        logger.info(f"بدء معالجة القناة: {channel_info['display_name']}")

        new_msgs = await scraper.scrape_channel(channel_info, from_date, to_date)
        total_new_messages += new_msgs

        # تصدير ملفات النسخ الاحتياطي (CSV و JSON) تلقائياً للقناة فور انتهاء سحبها
        export_backup_files(channel_info["file_name"], channel_info["display_name"])

    try:
        from intelligence.freshness import get_freshness

        fresh = get_freshness()
        logger.info(
            "حالة حداثة البيانات: %s | آخر إعلان: %s | آخر 24 ساعة: %s | قنوات نشطة: %s",
            fresh["status"], fresh["last_listing_at"],
            fresh["listings_24h"], fresh["channels_24h"],
        )
    except Exception as fresh_err:
        logger.warning(f"تعذر قراءة حداثة البيانات: {fresh_err}")

    return total_new_messages


async def main_async(args, logger):
    """
    المشغل الرئيسي غير المتزامن لإدارة الاتصال والدورة الحياتية للـ Scraper.
    """
    # 1. تهيئة قاعدة البيانات SQLite
    database.init_db()

    # 2. تفكيك وتحليل القنوات المستهدفة
    channel_list = []
    if args.channels:
        # إذا تم توفير قنوات عبر الـ CLI
        raw_list = args.channels.split(",")
        logger.info("تم استقبال قائمة قنوات مخصصة عبر معامِلات الـ CLI.")
    else:
        # استخدام القنوات الافتراضية
        raw_list = get_active_channels()
        logger.info("استخدام قائمة القنوات الافتراضية المحددة في النظام.")

    for raw_ch in raw_list:
        parsed = config.parse_channel_input(raw_ch)
        channel_list.append(parsed)
        logger.info(f"تجهيز القناة: {parsed['display_name']} ({parsed['type']})")

    # 3. تفكيك تواريخ البدء والنهاية للفلترة (للدورة الأولى)
    try:
        from_date = datetime.fromisoformat(args.from_date).astimezone(UTC)
        to_date = datetime.fromisoformat(args.to_date).astimezone(UTC)
    except ValueError as val_err:
        logger.error(f"خطأ في صيغة التاريخ الممرر. يرجى استخدام الصيغة ISO (YYYY-MM-DD): {str(val_err)}")
        return

    logger.info(f"نطاق تصفية التواريخ المعتمد: من {from_date.isoformat()} إلى {to_date.isoformat()}")

    # 4. بدء عميل تليجرام وسحب البيانات
    scraper = TelegramScraper(config.API_ID, config.API_HASH, config.SESSION_NAME)

    try:
        await scraper.start()

        if not args.continuous:
            total_new_messages = await run_scrape_cycle(
                scraper, channel_list, from_date, to_date, logger
            )
            logger.info("=" * 60)
            logger.info("تم الانتهاء من تشغيل النظام بالكامل بنجاح!")
            logger.info(f"إجمالي الرسائل الجديدة المضافة في هذه الجلسة: {total_new_messages}")
            return

        # الوضع المستمر: دورة كل N دقيقة، مع نافذة lookback لالتقاط التعديلات
        interval = max(1, int(args.interval_minutes))
        lookback = max(1, int(args.lookback_days))
        logger.info(f"الوضع المستمر مفعّل: كل {interval} دقيقة، نافذة {lookback} يوم.")

        while True:
            cycle_to = datetime.now(UTC)
            cycle_from = cycle_to - timedelta(days=lookback)
            logger.info(
                f"--- دورة جديدة {cycle_to.isoformat()} ---"
            )
            try:
                new_msgs = await run_scrape_cycle(
                    scraper, channel_list, cycle_from, cycle_to, logger
                )
                logger.info(f"دورة مكتملة: {new_msgs} رسالة جديدة.")
            except Exception as cycle_err:
                logger.error(f"خطأ في الدورة: {cycle_err}", exc_info=True)

            logger.info(f"النوم {interval} دقيقة قبل الدورة التالية...")
            await asyncio.sleep(interval * 60)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("تم إيقاف الوضع المستمر بواسطة المستخدم.")
    except Exception as run_err:
        logger.critical(f"خطأ حرج أدى إلى توقف نظام السحب: {str(run_err)}", exc_info=True)
    finally:
        await scraper.stop()

def main():
    """
    نقطة الدخول وإعداد الـ Argparse لتفسير معامِلات الـ CLI.
    """
    parser = argparse.ArgumentParser(
        description="PUBG Mobile Telegram Scraper for AI Price Evaluation Dataset"
    )
    parser.add_argument(
        "--channels",
        type=str,
        default=None,
        help="قائمة القنوات المطلوب سحبها مفصولة بفاصلة (مثال: channel1,https://t.me/channel2)"
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default="2025-01-01T00:00:00",
        help="تاريخ البدء لسحب البيانات بالصيغة (YYYY-MM-DD أو YYYY-MM-DDTHH:MM:SS) - افتراضي 2025-01-01"
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default="2026-12-31T23:59:59",
        help="تاريخ النهاية لسحب البيانات بالصيغة (YYYY-MM-DD أو YYYY-MM-DDTHH:MM:SS) - افتراضي 2026-12-31"
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="تنبيه: الكود معد افتراضياً لعدم تحميل أي صور لتوفير المساحة وسرعة السحب."
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="تشغيل السحب في وضع مستمر (دورة كل --interval-minutes دقيقة)."
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=30,
        help="الفاصل الزمني بين الدورات في الوضع المستمر (افتراضي 30 دقيقة)."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=3,
        help="نافذة إعادة الفحص في الوضع المستمر بال أيام (افتراضي 3)."
    )

    args = parser.parse_args()
    logger = setup_logging()

    # تشغيل الدورة البرمجية غير المتزامنة
    asyncio.run(main_async(args, logger))

if __name__ == "__main__":
    main()
