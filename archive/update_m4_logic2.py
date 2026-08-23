import sys
import re

with open('pipeline/ensemble_predict.py', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find("                if not (has_joker_fox or has_mummy")
end_idx = content.find("            # --- NEW: Multiple M4s Premium ---")

if start_idx == -1 or end_idx == -1:
    print("Could not find start or end")
    sys.exit(1)

new_block = '''                is_max = ('m4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1) or (m4_lvl >= 7)
                
                if is_max:
                    base_m4_cap = 4500
                    seg_name = "Max M4"
                    conf_margin = 400
                elif m4_lvl >= 4:
                    base_m4_cap = 2500 + (m4_lvl - 4) * 500
                    seg_name = f"Kill Msg M4 (Lvl {m4_lvl})"
                    conf_margin = 350
                else:
                    base_m4_cap = 1000 + (m4_lvl - 1) * 500
                    seg_name = f"Basic M4 (Lvl {m4_lvl})"
                    conf_margin = 300
                
                cap = base_m4_cap + extra_premium
                fair_value = min(fair_value, cap)
                
                if fair_value <= cap:
                    if not (has_joker_fox or has_mummy or has_mummy_helmet or has_xsuit or has_mythic_car):
                        segment = f"Capped: {seg_name} Solo (Dynamic)"
                    else:
                        segment = f"Capped: {seg_name} + Anchors (Dynamic)"
                    confidence_margin = conf_margin
                    
'''

content = content[:start_idx] + new_block + content[end_idx:]

with open('pipeline/ensemble_predict.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced with precision")
