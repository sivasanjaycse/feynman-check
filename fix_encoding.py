import re, pathlib
p = pathlib.Path("scripts/feynman.py")
# Read as latin-1 to see raw bytes
raw = p.read_bytes()
text = raw.decode("utf-8", errors="replace")
# Replace common unicode punctuation with ASCII equivalents
replacements = {
    "\u2014": "--",  # em dash
    "\u2013": "-",   # en dash
    "\u2019": "'",   # right single quote
    "\u2018": "'",   # left single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u00e2\u0080\u0094": "--",  # mojibake em dash
}
for bad, good in replacements.items():
    text = text.replace(bad, good)
p.write_text(text, encoding="utf-8")
print("Done. Lines:", text.count("\n"))
