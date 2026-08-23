import sys
import re

with open('pipeline/ensemble_predict.py', encoding='utf-8') as f:
    content = f.read()

# We want to replace from `# Has M4` up to `# --- NEW: Multiple M4s Premium ---`
pattern = re.compile(r'# Has M4\s*m4_lvl =.*?(?=# --- NEW: Multiple M4s Premium ---)', re.DOTALL)

match = pattern.search(content)
if not match:
    print("Could not find the block via regex")
    sys.exit(1)

new_block = '''# Has M4
                m4_lvl = df['m4_level'].iloc[0] if 'm4_level' in df.columns and pd.notna(df['m4_level'].iloc[0]) else 1
                is_max = ('m4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1) or (m4_lvl >= 7)
                
                # Base M4 Cap dynamically mapped to real market value
                if is_max:
                    base_m4_cap = 4500
                    seg_name = "Max M4"
                    conf_margin = 400
                elif m4_lvl >= 4:
                    base_m4_cap = 2500 + (m4_lvl - 4) * 500
                    seg_name = f"Kill Msg M4 (Lvl {int(m4_lvl)})"
                    conf_margin = 350
                else:
                    base_m4_cap = 1000 + (m4_lvl - 1) * 500
                    seg_name = f"Basic M4 (Lvl {int(m4_lvl)})"
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

new_content = content[:match.start()] + new_block + content[match.end():]

with open('pipeline/ensemble_predict.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Regex replace successful!")
