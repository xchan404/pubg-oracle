import sys
import os

with open('pipeline/ensemble_predict.py', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if '# --- NEW: Fluff Guns Override ---' in line:
        skip = True
    if skip and '# Ensure all columns exist' in line:
        skip = False
    
    if not skip:
        new_lines.append(line)

content = ''.join(new_lines)

# Now, introduce extra_premium
old_premium = '''        # Frames (Only Gold/Silver/2018 are mega expensive)
        if 'has_plane_frame' in df.columns and df['has_plane_frame'].iloc[0] == 1:'''

new_premium = '''        # Frames (Only Gold/Silver/2018 are mega expensive)
        if 'has_plane_frame' in df.columns and df['has_plane_frame'].iloc[0] == 1:'''

# Actually, I'll just append extra_premium calculation right before the caps block
old_caps = '''        # Apply Tiered Caps based on M4 presence
        if not has_m4:'''

new_caps = '''        # Calculate extra premiums for raw stats (Guns/Mythics)
        guns_val = int(df['guns_count'].iloc[0]) if 'guns_count' in df.columns and pd.notna(df['guns_count'].iloc[0]) else 0
        mythics_val = int(df['mythics_count'].iloc[0]) if 'mythics_count' in df.columns and pd.notna(df['mythics_count'].iloc[0]) else 0
        guns_premium = max(0, guns_val - 2) * 200
        mythics_premium = max(0, mythics_val - 20) * 30
        extra_premium = rare_premium + guns_premium + mythics_premium

        # Apply Tiered Caps based on M4 presence
        if not has_m4:'''

content = content.replace(old_caps, new_caps)

# Replace all rare_premium with extra_premium in the caps logic
# Be careful to only replace it in the caps block!
caps_start = content.find('# Apply Tiered Caps based on M4 presence')
caps_end = content.find('# --- NEW: Multiple M4s Premium ---')

caps_block = content[caps_start:caps_end]
new_caps_block = caps_block.replace('rare_premium', 'extra_premium')
# Wait, for the static caps like `cap = 3000` we should change them to `cap = 3000 + extra_premium` if we want it to scale!
# Let's manually replace the block in python

with open('pipeline/ensemble_predict.py', 'w', encoding='utf-8') as f:
    f.write(content.replace(caps_block, new_caps_block))

print("Success")
