import sys

with open('pipeline/ensemble_predict.py', encoding='utf-8') as f:
    content = f.read()

# Replace static caps with cap + extra_premium
replacements = [
    ("cap = 3000\n                fair_value = min(fair_value, cap)\n                if fair_value <= cap:\n                    segment = \"Capped: Joker/Mummy Only (Max 3k)\"",
     "cap = 3000 + extra_premium\n                fair_value = min(fair_value, cap)\n                if fair_value <= cap:\n                    segment = \"Capped: Joker/Mummy Only (Max 3k)\""),
    
    ("fair_value = min(fair_value, 2000)\n                if fair_value <= 2000:\n                    segment = \"Capped: X-Suit/Mythic Car Only (Max 2k)\"",
     "cap = 2000 + extra_premium\n                fair_value = min(fair_value, cap)\n                if fair_value <= cap:\n                    segment = \"Capped: X-Suit/Mythic Car Only (Max 2k)\""),
    
    ("fair_value = min(fair_value, 1500)\n                if fair_value <= 1500:\n                    segment = \"Capped: Girl Face Only (Max 1.5k)\"",
     "cap = 1500 + extra_premium\n                fair_value = min(fair_value, cap)\n                if fair_value <= cap:\n                    segment = \"Capped: Girl Face Only (Max 1.5k)\""),
    
    ("fair_value = min(fair_value, 1000)\n                if fair_value <= 1000:\n                    segment = \"Capped: No Anchors (<1k)\"",
     "cap = 1000 + extra_premium\n                fair_value = min(fair_value, cap)\n                if fair_value <= cap:\n                    segment = \"Capped: No Anchors (<1k)\""),
    
    ("fair_value = min(fair_value, 2000)\n                    if fair_value <= 2000:\n                        segment = \"Capped: Basic M4 Solo (<2k)\"",
     "cap = 2000 + extra_premium\n                    fair_value = min(fair_value, cap)\n                    if fair_value <= cap:\n                        segment = \"Capped: Basic M4 Solo (<2k)\""),
    
    ("fair_value = min(fair_value, 2500)\n                        if fair_value <= 2500:\n                            segment = \"Capped: Kill Msg M4 Solo (Max 2.5k)\"",
     "cap = 2500 + extra_premium\n                        fair_value = min(fair_value, cap)\n                        if fair_value <= cap:\n                            segment = \"Capped: Kill Msg M4 Solo (Max 2.5k)\""),
    
    ("fair_value = min(fair_value, 4000)\n                        if fair_value <= 4000:\n                            segment = \"Capped: Max M4 Solo (Max 4k)\"",
     "cap = 4000 + extra_premium\n                        fair_value = min(fair_value, cap)\n                        if fair_value <= cap:\n                            segment = \"Capped: Max M4 Solo (Max 4k)\"")
]

for old, new in replacements:
    content = content.replace(old, new)

with open('pipeline/ensemble_predict.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Caps updated successfully.")
