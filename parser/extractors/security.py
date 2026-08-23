# -*- coding: utf-8 -*-
"""
Security Extractor Module
Extracts account security status, linkages (Twitter, Facebook, Internal), and middleman trust indicators.
"""

import re
from typing import Dict, Any
from parser.extractors.base import BaseExtractor

class SecurityExtractor(BaseExtractor):
    def extract(self, text: str) -> Dict[str, Any]:
        if not text:
            return self._empty_security_report()

        text_lower = text.lower()

        # Link types detection
        has_internal = bool(re.search(r'ربط\s*داخلي|داخلي\s*موجود|الربط\s*الداخلي|داخلي\s*فقط', text_lower))
        has_twitter = bool(re.search(r'تويتر|twitter|ربط\s*تويتر', text_lower))
        has_facebook = bool(re.search(r'فيسبوك|فيس|facebook|fb', text_lower))
        has_google = bool(re.search(r'جوجل|جيميل|google|gmail', text_lower))
        has_gamecenter = bool(re.search(r'جيم\s*سنتر|game\s*center|apple|ابل', text_lower))
        has_email = bool(re.search(r'إيميل|ايميل|email|mail', text_lower))
        has_phone = bool(re.search(r'رقم|موبايل|هاتف|phone', text_lower))
        has_vk = bool(re.search(r'فكونتاكتي|vk', text_lower))

        # Linkage statuses & assurances
        is_single_link = bool(re.search(r'ربط\s*واحد|سنجل\s*ربط|ربط\s*نقي|ربط\s*واحد\s*فقط|single\s*link', text_lower))
        is_fb_disabled = bool(re.search(r'فيسبوك\s*معطل|فيس\s*معطل|الفيس\s*معطل|طيرت\s*الفيس|fb\s*disabled|معطل', text_lower))
        has_dead_link = bool(re.search(r'ربط\s*ميت|مفقود|ضائع|مضائع|بدون\s*وصول|ميت', text_lower))
        has_full_access = bool(re.search(r'تسليم\s*بالكامل|تسليم\s*كافة\s*الروابط|مع\s*الإيميل\s*الأساسي|مع\s*الايميل|كامل\s*الروابط', text_lower))
        has_middleman = bool(re.search(r'وسيط\s*معتمد|تأمين\s*وسيط|تسليم\s*وسيط|وسيط', text_lower))
        is_clean_linkage = is_single_link or (has_internal and is_fb_disabled) or has_full_access

        # Trust Score calculation (0 to 100)
        trust_score = 70  # Baseline

        if has_full_access:
            trust_score += 20
        if is_single_link:
            trust_score += 15
        if has_internal and is_fb_disabled:
            trust_score += 10
        if has_middleman:
            trust_score += 10
        if is_clean_linkage:
            trust_score += 5

        # Penalties
        if has_dead_link:
            trust_score -= 35
        if has_facebook and not is_fb_disabled and not has_full_access:
            trust_score -= 15
        if not has_middleman:
            trust_score -= 10
        if not (has_internal or has_twitter or has_email or is_single_link):
            trust_score -= 10

        trust_score = max(5, min(100, trust_score))

        # Categorical Risk Rating
        if trust_score >= 88:
            risk_level = "VERY_LOW"
            verdict_arabic = "حساب آمن جداً ومضمون للنقل 🟢"
        elif trust_score >= 70:
            risk_level = "LOW"
            verdict_arabic = "حساب جيد ومقبول الأمان 🟢"
        elif trust_score >= 50:
            risk_level = "MODERATE"
            verdict_arabic = "مخاطرة متوسطة - يوصى بالتأكد عبر وسيط معتمد 🟡"
        elif trust_score >= 30:
            risk_level = "HIGH"
            verdict_arabic = "مخاطرة عالية - توجد روابط غير مؤمنة 🔴"
        else:
            risk_level = "CRITICAL"
            verdict_arabic = "مخاطرة حرجة جداً - احذر من سحب الحساب 🚨"

        # Verified links list
        verified_links = []
        if has_internal: verified_links.append("ربط داخلي (Internal)")
        if has_twitter: verified_links.append("تويتر (Twitter)")
        if has_google: verified_links.append("جوجل (Google)")
        if has_gamecenter: verified_links.append("Game Center / Apple")
        if has_email: verified_links.append("إيميل متصل (Email)")
        if has_phone: verified_links.append("رقم هاتف (Phone)")
        if not verified_links: verified_links.append("ربط قياسي عام")

        # Risk Warnings & Safety Assurances
        warnings = []
        assurances = []
        precautions = []

        if has_dead_link:
            warnings.append("يوجد ربط ميت/مفقود (قد يتعرض الحساب للمطالبة بالسحب)")
        if has_facebook and not is_fb_disabled and not has_full_access:
            warnings.append("حساب الفيسبوك نشط ولم يتم تسليمه بالكامل")
        if not has_middleman:
            warnings.append("لم يتم ذكر تسليم عبر وسيط معتمد")

        if is_single_link:
            assurances.append("حساب ربط واحد نقي (سهولة ونظافة النقل)")
        if is_fb_disabled:
            assurances.append("حساب الفيسبوك معطل/مستبعد لضمان عدم السحب")
        if has_full_access:
            assurances.append("تسليم كامل الروابط والإيميل الأساسي")
        if has_middleman:
            assurances.append("معاملة مدعومة عبر وسيط معتمد وتأمين")

        precautions.append("قم بتغيير إيميل وكلمة سر الربط الداخلي فور الاستلام")
        precautions.append("تأكد من ربط رقم هاتفك وتفعيل التحقق بخطوتين (2FA)")
        precautions.append("لا تقم بتحويل الأموال إلا بعد تأكيد الاستلام من خلال وسيط معتمد")

        # Derived legacy linkage type
        if has_internal and is_fb_disabled:
            linkage_type = "safe_internal_only"
        elif is_single_link:
            linkage_type = "single_link"
        elif has_internal:
            linkage_type = "internal_linked"
        elif has_twitter:
            linkage_type = "twitter_linked"
        else:
            linkage_type = "standard"

        return {
            "has_internal_link": has_internal,
            "has_twitter_linked": has_twitter,
            "has_facebook_linked": has_facebook,
            "has_google_linked": has_google,
            "has_email_linked": has_email,
            "has_phone_linked": has_phone,
            "is_single_link": is_single_link,
            "is_facebook_disabled": is_fb_disabled,
            "has_dead_link": has_dead_link,
            "has_full_access": has_full_access,
            "has_trusted_middleman": has_middleman,
            "is_clean_linkage": is_clean_linkage,
            "linkage_type": linkage_type,
            "trust_score": trust_score,
            "security_risk_level": risk_level,
            "transferability_verdict": verdict_arabic,
            "verified_links": verified_links,
            "risk_warnings": warnings,
            "safety_assurances": assurances,
            "recommended_precautions": precautions
        }

    def _empty_security_report(self) -> Dict[str, Any]:
        return {
            "has_internal_link": False,
            "has_twitter_linked": False,
            "has_facebook_linked": False,
            "has_google_linked": False,
            "has_email_linked": False,
            "has_phone_linked": False,
            "is_single_link": False,
            "is_facebook_disabled": False,
            "has_dead_link": False,
            "has_full_access": False,
            "has_trusted_middleman": False,
            "is_clean_linkage": False,
            "linkage_type": "unknown",
            "trust_score": 50,
            "security_risk_level": "MODERATE",
            "transferability_verdict": "تفاصيل غير كافية لتقييم الأمان",
            "verified_links": [],
            "risk_warnings": ["لم يتم العثور على معلومات روابط في النص"],
            "safety_assurances": [],
            "recommended_precautions": ["اطلب من البائع توضيح حالة الروابط والوسيط"]
        }
