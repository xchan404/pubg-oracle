# -*- coding: utf-8 -*-
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from parser.aliases import resolve_alias, resolve_text_items
from parser.regex_parser import extract_prices
from ml.pipeline import pipeline_instance
from ml.predict import EnsemblePricer

class TestNLPMLPipeline(unittest.TestCase):
    def test_fuzzy_alias_resolution(self):
        # Exact match
        self.assertEqual(resolve_alias("جليشر"), "glacier_m416")
        self.assertEqual(resolve_alias("فرعون"), "xsuit_pharaoh")
        
        # Fuzzy match
        self.assertEqual(resolve_alias("جلشير"), "glacier_m416")
        self.assertEqual(resolve_alias("بوسيدن"), "xsuit_poseidon")
        self.assertEqual(resolve_alias("مومياء صفرا"), "mummy_yellow")

    def test_price_extraction(self):
        # Shorthand k / K notation
        p1_egp, _ = extract_prices("امفور تلجي السعر 15k")
        self.assertEqual(p1_egp, 15000.0)
        
        p2_egp, _ = extract_prices("حساب ببجي طالب فيه 2.5k ج")
        self.assertEqual(p2_egp, 2500.0)
        
        # Arabic thousand
        p3_egp, _ = extract_prices("السعر 15 الف")
        self.assertEqual(p3_egp, 15000.0)
        
        # USD notation
        _, p4_usd = extract_prices("price $350")
        self.assertEqual(p4_usd, 350.0)

    def test_unified_pipeline(self):
        sample_text = "حساب ببجي لفل 75 ميثك 60 امفور تلجي ماكس بدلة بوسيدن السعر 12k"
        result = pipeline_instance.process(sample_text)
        
        self.assertEqual(result["account_level"], 75)
        self.assertEqual(result["mythics_count"], 60)
        self.assertEqual(result["price_egp"], 12000.0)
        self.assertIn("glacier_m416", result["canonical_items"])
        self.assertIn("xsuit_poseidon", result["canonical_items"])
        self.assertIn("has_m4_max_x_mummy", result)

    def test_modular_extractors(self):
        from parser.extractors.price import PriceExtractor
        from parser.extractors.skins import SkinExtractor
        from parser.extractors.vehicles import VehicleExtractor
        from parser.extractors.frames import FrameExtractor
        
        sample_text = "حساب ببجي لفل 80 ميثك 70 3 سيارات ميثك مكلارين اطار طيارة السعر 18k ج"
        
        price_res = PriceExtractor().extract(sample_text)
        self.assertEqual(price_res["price_egp"], 18000.0)
        
        skin_res = SkinExtractor().extract(sample_text)
        self.assertEqual(skin_res["m4_type"], None)
        
        veh_res = VehicleExtractor().extract(sample_text)
        self.assertEqual(veh_res["cars_mythic"], 3)
        
        frame_res = FrameExtractor().extract(sample_text)
        self.assertTrue(frame_res["has_plane_frame"])

    def test_security_extractor_and_schema(self):
        from parser.extractors.security import SecurityExtractor
        from schemas.account import ParsedAccountSchema
        
        sample_text = "حساب ببجي لفل 75 ربط داخلي فقط فيسبوك معطل تسليم وسيط"
        sec_res = SecurityExtractor().extract(sample_text)
        
        self.assertTrue(sec_res["has_internal_link"])
        self.assertTrue(sec_res["is_facebook_disabled"])
        self.assertTrue(sec_res["has_trusted_middleman"])
        self.assertEqual(sec_res["linkage_type"], "safe_internal_only")
        
        # Test Pydantic Schema Validation
        full_res = pipeline_instance.process(sample_text)
        schema_obj = ParsedAccountSchema(**full_res)
        self.assertEqual(schema_obj.account_level, 75)
        self.assertTrue(schema_obj.has_internal_link)

    def test_model_prediction(self):
        pricer = EnsemblePricer()
        sample_text = "حساب ببجي لفل 70 ميثك 45 امفور تلجي ماكس السعر 4000"
        pred = pricer.predict(sample_text, asking_price=4000)
        
        self.assertIn("fair_value_egp", pred)
        self.assertIn("flipping_advice", pred)
        self.assertGreater(pred["fair_value_egp"], 0)

if __name__ == '__main__':
    unittest.main()
