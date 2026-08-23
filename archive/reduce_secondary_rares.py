import sys
import re

with open('pipeline/ensemble_predict.py', encoding='utf-8') as f:
    content = f.read()

old_block = '''        # Secondary Ultra Rares (Hair, Faces, Outfits, Scarfs)
        if re.search(r'فيس\\s*بنت|فيس\\s*البنت', raw_text, re.IGNORECASE):
            rare_premium += 1500
        if re.search(r'شعر\\s*القرنين', raw_text, re.IGNORECASE):
            rare_premium += 1000
        if re.search(r'صابونه\\s*زرقا|الصابونه\\s*الزرقا', raw_text, re.IGNORECASE):
            rare_premium += 1000
        if re.search(r'وشاح\\s*النمر', raw_text, re.IGNORECASE):
            rare_premium += 500
        if re.search(r'كابوريا|الكابوريا', raw_text, re.IGNORECASE):
            rare_premium += 500
        if re.search(r'بدلة\\s*جولد|راس\\s*جولد', raw_text, re.IGNORECASE):
            rare_premium += 1000
        if re.search(r'شنطة\\s*الغراب|شنطه\\s*الغراب', raw_text, re.IGNORECASE):
            rare_premium += 800'''

new_block = '''        # Secondary Ultra Rares (Hair, Faces, Outfits, Scarfs)
        if re.search(r'فيس\\s*بنت|فيس\\s*البنت', raw_text, re.IGNORECASE):
            rare_premium += 500
        if re.search(r'شعر\\s*القرنين', raw_text, re.IGNORECASE):
            rare_premium += 300
        if re.search(r'صابونه\\s*زرقا|الصابونه\\s*الزرقا', raw_text, re.IGNORECASE):
            rare_premium += 300
        if re.search(r'وشاح\\s*النمر', raw_text, re.IGNORECASE):
            rare_premium += 200
        if re.search(r'كابوريا|الكابوريا', raw_text, re.IGNORECASE):
            rare_premium += 200
        if re.search(r'بدلة\\s*جولد|راس\\s*جولد', raw_text, re.IGNORECASE):
            rare_premium += 400
        if re.search(r'شنطة\\s*الغراب|شنطه\\s*الغراب', raw_text, re.IGNORECASE):
            rare_premium += 300'''

content = content.replace(old_block, new_block)

with open('pipeline/ensemble_predict.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Reduced Secondary Ultra Rares to realistic trader values.")
