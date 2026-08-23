import sys

with open('pipeline/ensemble_predict.py', encoding='utf-8') as f:
    content = f.read()

old_block = '''            else:
                # Has M4
                m4_lvl = df['m4_level'].iloc[0] if 'm4_level' in df.columns and df['m4_level'].iloc[0] is not None else 1
                if not (has_joker_fox or has_mummy or has_mummy_helmet or has_xsuit or has_mythic_car):
                    if m4_lvl < 4:
                        # Basic M4 (Level 1-3) with no other anchors
                        cap = 2000 + extra_premium
                        fair_value = min(fair_value, cap)
                        if fair_value <= cap:
                            segment = "Capped: Basic M4 Solo (Dynamic)"
                            confidence_margin = 300
                    else:
                        # Check if it's Max or just Kill Message
                        is_max = ('m4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1) or (m4_lvl >= 7)
                        if not is_max:
                            # Kill Message M4 (Level 4-6) with no other anchors
                            cap = 2500 + extra_premium
                            fair_value = min(fair_value, cap)
                            if fair_value <= cap:
                                segment = "Capped: Kill Msg M4 Solo (Dynamic)"
                                confidence_margin = 350
                        else:
                            # Max M4 (Level 7) with no other anchors
                            cap = 4000 + extra_premium
                            fair_value = min(fair_value, cap)
                            if fair_value <= cap:
                                segment = "Capped: Max M4 Solo (Dynamic)"
                                confidence_margin = 400
                else:
                    # Has M4 AND Anchors.
                    if m4_lvl < 4:
                        cap = 3000 + extra_premium
                        fair_value = min(fair_value, cap)
                        if fair_value <= cap:
                            segment = "Capped: Basic M4 + Anchors"
                            confidence_margin = 500
                    else:
                        # M4 Kill Msg (lvl 4-6) or Max (lvl 7) + Anchors
                        base_m4_cap = 5000 if m4_lvl < 7 else 7500
                        cap = base_m4_cap + extra_premium
                        fair_value = min(fair_value, cap)
                        if fair_value <= cap:
                            segment = f"Capped: Kill/Max M4 + Anchors"
                            confidence_margin = 800'''

new_block = '''            else:
                # Has M4
                m4_lvl = df['m4_level'].iloc[0] if 'm4_level' in df.columns and df['m4_level'].iloc[0] is not None else 1
                is_max = ('m4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1) or (m4_lvl >= 7)
                
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
                    confidence_margin = conf_margin'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('pipeline/ensemble_predict.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("M4 logic replaced successfully.")
else:
    print("Could not find the old block. Maybe spacing or something is off.")
