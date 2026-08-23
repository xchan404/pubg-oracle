import sys; sys.path.append('pipeline')
import re
with open('pipeline/parser.py', encoding='utf-8') as f:
    content = f.read()

# Update extract_mythics
old_mythics = '''    patterns = [
        r'(?:ميثيك|ميثك|مثك|مسك|mythic)ات?\\s*(?:في|ف|ب|مجموع|عددهم|عدد)?\\s*[:\\-]?\\s*(\\d{1,3})',
        r'(\\d{1,3})\\s*(?:ميثيك|ميثك|مثك|مسك|mythic)',
        r'(?:عدد\\s*)?(?:ميثيك|ميثك|مثك|مسك|mythic)ات?.*?(\\d{1,3})',
        r'(?:ميثيك|ميثك|مثك|مسك|mythic).{0,15}?(\\d{1,3})'
    ]'''
new_mythics = '''    patterns = [
        r'(?:ميثيك|ميثك|مثيك|مثك|مسك|mythic)ات?\\s*(?:في|ف|ب|مجموع|عددهم|عدد)?\\s*[:\\-]?\\s*(\\d{1,3})',
        r'(\\d{1,3})\\s*(?:ميثيك|ميثك|مثيك|مثك|مسك|mythic)',
        r'(?:عدد\\s*)?(?:ميثيك|ميثك|مثيك|مثك|مسك|mythic)ات?.*?(\\d{1,3})',
        r'(?:ميثيك|ميثك|مثيك|مثك|مسك|mythic).{0,15}?(\\d{1,3})'
    ]'''
content = content.replace(old_mythics, new_mythics)

# Update extract_guns_count
old_guns = '''def extract_guns_count(text: str) -> Optional[int]:
    """استخراج عدد الأسلحة في مختبر التطوير."""
    m = re.search(
        r'(?:مختبر\\s*التطوير|المختبر\\s*المطور|التطوير|اسلح[هة]?\\s*التطوير|الالسلح[هة]?\\s*المطو[ره]+|اسلحه\\s*بيطور)\\s*[:\\-\\(]?\\s*(\\d{1,3})',
        text, re.IGNORECASE
    )'''
new_guns = '''def extract_guns_count(text: str) -> Optional[int]:
    """استخراج عدد الأسلحة في مختبر التطوير."""
    m = re.search(
        r'(?:مختبر\\s*التطوير|المختبر\\s*المطور|التطوير|اسلح[هة]?\\s*التطوير|الا?سلح[هة]?\\s*المطور[هة]?|اسلحه\\s*بيطور)\\s*[\\]:\\-\\(]?\\s*(\\d{1,3})',
        text, re.IGNORECASE
    )'''
content = content.replace(old_guns, new_guns)

with open('pipeline/parser.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
