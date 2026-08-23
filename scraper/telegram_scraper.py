"""
محرك سحب البيانات (Telegram Scraping Engine)
يحتوي هذا الملف على الكود المسؤول عن الاتصال بـ Telegram API عبر Telethon،
وحذف/تصفية الرسائل، وإدارة نقاط التوقف، والتعامل الذكي مع الـ Rate Limits و الـ FloodWait.
"""

import asyncio
import logging
from datetime import UTC, datetime

from telethon import TelegramClient
from telethon.errors import FloodWaitError, InviteHashExpiredError, InviteHashInvalidError, UserAlreadyParticipantError
from telethon.tl.functions.messages import ImportChatInviteRequest

from database import db as database

logger = logging.getLogger("pubg_scraper")

class TelegramScraper:
    def __init__(self, api_id: int, api_hash: str, session_name: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None

    async def start(self):
        """
        تشغيل العميل والتحقق من تسجيل الدخول.
        """
        logger.info("جاري بدء اتصال عميل تلجرام...")
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        logger.info("تم الاتصال بتلجرام بنجاح.")

    async def stop(self):
        """
        إغلاق الاتصال بأمان.
        """
        if self.client:
            await self.client.disconnect()
            logger.info("تم فصل الاتصال بتلجرام بأمان.")

    async def resolve_channel_entity(self, channel_info: dict):
        """
        يقوم بحل وتحليل معرف القناة (Entity) سواء كانت عامة أو رابط دعوة لقناة خاصة.

        المعاملات:
            channel_info (dict): القاموس الناتج من دالة parse_channel_input

        المخرجات:
            entity: كائن القناة من تليجرام، أو None إذا فشل الحل.
        """
        raw_input = channel_info["raw_input"]
        val = channel_info["value"]

        # 1. إذا كانت القناة عامة
        if channel_info["type"] == "public":
            try:
                entity = await self.client.get_entity(val)
                logger.info(f"تم العثور على القناة العامة بنجاح: {channel_info['display_name']}")
                return entity
            except Exception as e:
                logger.error(f"خطأ أثناء العثور على القناة العامة {val}: {str(e)}")
                return None

        # 2. إذا كانت القناة خاصة عبر رابط دعوة
        elif channel_info["type"] == "private":
            try:
                # محاولة جلب الكيان مباشرة (إذا كان الحساب منضماً بالفعل)
                entity = await self.client.get_entity(raw_input)
                logger.info(f"تم العثور على القناة الخاصة (منضم مسبقاً): {channel_info['display_name']}")
                return entity
            except Exception:
                # إذا لم يكن منضماً، سنحاول الانضمام باستخدام الهاش
                logger.info(f"الحساب ليس عضواً في القناة الخاصة، جاري محاولة الانضمام عبر الهاش {val}...")
                try:
                    await self.client(ImportChatInviteRequest(val))
                    logger.info("تم الانضمام للقناة الخاصة بنجاح!")
                    entity = await self.client.get_entity(raw_input)
                    return entity
                except UserAlreadyParticipantError:
                    # تحسباً لأي تداخل، إذا كان منضماً بالفعل
                    try:
                        # نحاول جلب القناة من محادثات المستخدم (Dialogs)
                        async for dialog in self.client.iter_dialogs():
                            if dialog.is_channel and dialog.title == channel_info["display_name"]:
                                return dialog.entity
                    except Exception as dialog_err:
                        logger.error(f"فشل جلب القناة من المحادثات النشطة: {str(dialog_err)}")
                except (InviteHashExpiredError, InviteHashInvalidError) as invite_err:
                    logger.error(f"رابط الدعوة الخاص بالقناة الخاصة منتهي أو غير صالح: {str(invite_err)}")
                except Exception as join_err:
                    logger.error(f"فشل الانضمام للقناة الخاصة عبر الهاش: {str(join_err)}")

            # محاولة أخيرة للبحث في المحادثات النشطة بالاسم
            try:
                async for dialog in self.client.iter_dialogs():
                    if dialog.is_channel and (val in str(dialog.id) or channel_info["display_name"] in dialog.name):
                        logger.info(f"تم العثور على القناة الخاصة في محادثاتك النشطة: {dialog.name}")
                        return dialog.entity
            except Exception as e:
                logger.error(f"فشل البحث في المحادثات النشطة: {str(e)}")

        return None

    async def scrape_channel(self, channel_info: dict, from_date: datetime, to_date: datetime) -> int:
        """
        تقوم بسحب الرسائل من قناة معينة وحفظها في قاعدة البيانات مع تطبيق فلاتر التاريخ والتحكم بالأخطاء.

        المعاملات:
            channel_info (dict): معلومات القناة المستخرجة من الإعدادات.
            from_date (datetime): تاريخ البدء (Timezone aware UTC).
            to_date (datetime): تاريخ النهاية (Timezone aware UTC).

        المخرجات:
            int: عدد الرسائل الجديدة التي تم حفظها بنجاح.
        """
        display_name = channel_info["display_name"]
        file_name = channel_info["file_name"]

        entity = await self.resolve_channel_entity(channel_info)
        if not entity:
            logger.error(f"تخطى القناة {display_name} لعدم إمكانية الوصول للكيان الخاص بها.")
            return 0

        # الاتصال بقاعدة البيانات وجلب نقطة التوقف الأخيرة
        conn = database.get_connection()
        checkpoint_id = database.get_checkpoint(conn, file_name)
        logger.info(f"نقطة التوقف الحالية للقناة {display_name} هي الرسالة رقم: {checkpoint_id}")

        scraped_count = 0
        total_processed = 0
        max_message_id_seen = checkpoint_id

        try:
            # سنقوم بالسحب من الأحدث إلى الأقدم (Backwards)
            # ونضع حد أدنى للمعرف (min_id) وهو الـ checkpoint لعدم تكرار سحب ما تم سحبه سابقاً
            kwargs = {
                "limit": None
            }
            if checkpoint_id > 0:
                kwargs["min_id"] = checkpoint_id

            logger.info(f"بدء سحب الرسائل للقناة {display_name}...")

            async for message in self.client.iter_messages(entity, **kwargs):
                total_processed += 1

                # تتبع أعلى معرف رسالة رأيناه لتحديث نقطة التوقف لاحقاً
                if message.id > max_message_id_seen:
                    max_message_id_seen = message.id

                # طباعة سجل التقدم كل 100 رسالة
                if total_processed % 100 == 0:
                    logger.info(f"تمت معالجة {total_processed} رسالة من القناة {display_name} حتى الآن...")

                # 1. التحقق من النطاق الزمني
                # تحويل تاريخ الرسالة إلى timezone aware UTC للمقارنة العادلة
                msg_date = message.date.astimezone(UTC)

                if msg_date > to_date:
                    # الرسالة أحدث من النطاق المطلوب، نتخطاها ونكمل للوصول للنطاق
                    continue

                if msg_date < from_date:
                    # بما أننا نسير للخلف (من الأحدث للأقدم)، فوصولنا لرسالة أقدم من تاريخ البداية
                    # يعني أن جميع الرسائل القادمة ستكون أقدم أيضاً، لذا نوقف السحب فوراً!
                    logger.info(f"تم الوصول لرسالة بتاريخ {msg_date.isoformat()} وهو أقدم من تاريخ البدء {from_date.isoformat()}. إيقاف السحب لهذه القناة.")
                    break

                # 2. فلترة الرسائل التي لا تحتوي على نصوص (مثل وسائط نقية بدون أي شرح)
                if not message.message or not message.message.strip():
                    continue

                # 3. تجهيز بيانات الرسالة للحفظ
                msg_data = {
                    "message_id": message.id,
                    "channel_username": file_name,
                    "date": msg_date.isoformat(),
                    "text": message.message,
                    "views": message.views or 0,
                    "forwards": message.forwards or 0,
                    "has_photo": bool(message.photo),
                    "photo_path": None,  # بناء على رغبة العميل، لن يتم تحميل أي صور
                    "is_grouped": bool(message.grouped_id)
                }

                # 4. حفظ في قاعدة البيانات مع تجنب التكرار
                is_saved = database.save_message(conn, msg_data)
                if is_saved:
                    scraped_count += 1

                # نوم خفيف جداً لتجنب الـ Rate Limits وتخفيف العبء على الـ API
                if total_processed % 20 == 0:
                    await asyncio.sleep(0.1)

        except FloodWaitError as flood_err:
            logger.warning(f"مواجهة حد معدل الطلبات (FloodWaitError). يجب الانتظار لـ {flood_err.seconds} ثانية...")
            await asyncio.sleep(flood_err.seconds + 2)
        except Exception as e:
            logger.error(f"حدث خطأ غير متوقع أثناء سحب القناة {display_name}: {str(e)}", exc_info=True)
        finally:
            # تحديث نقطة التوقف وحفظها حتى لو توقف السكربت بسبب خطأ
            if max_message_id_seen > checkpoint_id:
                database.save_checkpoint(conn, file_name, max_message_id_seen)
                logger.info(f"تم حفظ نقطة التوقف الجديدة للقناة {display_name}: {max_message_id_seen}")
            conn.close()

        logger.info(f"تم الانتهاء من القناة {display_name}. الرسائل الجديدة المحفوظة: {scraped_count}")
        return scraped_count
