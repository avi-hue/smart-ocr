import os

path = 'src/ocr_engine/field_extractor.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: alt_match
old_alt = '        alt_match = re.search(r"(?i)([ \\t]*)(to:)([ \\t]*)(ship\\s+to:)([ \\t]*)\\n", text)\n        if alt_match:\n            split_pos = alt_match.group(0).lower().index("ship to:")'
new_alt = '        alt_match = re.search(r"(?i)^([ \\t]*)(bill\\s+to:?|to:)([ \\t]*)(ship\\s+to:?)([ \\t]*)$", text, flags=re.MULTILINE)\n        if alt_match:\n            split_pos = alt_match.group(0).lower().index("ship")'
if old_alt in content:
    content = content.replace(old_alt, new_alt)
else:
    print('Failed to find old_alt')

# Fix 2: vendor fallback
old_vend = '        if not result["vendor_name"]:\n            first_line = text.strip().split("\\n")[0]\n            if first_line and "invoice" not in first_line.lower():\n                result["vendor_name"] = first_line\n            elif len(text.strip().split("\\n")) > 1:\n                result["vendor_name"] = text.strip().split("\\n")[0].replace("INVOICE", "").strip() or text.strip().split("\\n")[1]'
new_vend = '        if not result["vendor_name"]:\n            for line in text.strip().split("\\n")[:10]:\n                line = line.strip()\n                if not line: continue\n                if __import__("re").match(r"(?i)^(date|#|invoice\\s*#|no\\.)", line): continue\n                v_name = __import__("re").sub(r"(?i)\\binvoice\\b", "", line).strip()\n                if v_name:\n                    result["vendor_name"] = v_name\n                    break'
if old_vend in content:
    content = content.replace(old_vend, new_vend)
else:
    print('Failed to find old_vend')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
