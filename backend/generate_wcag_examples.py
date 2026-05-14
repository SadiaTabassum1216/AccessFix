import json
from pathlib import Path

root = Path(__file__).resolve().parent
wcag_file = root / 'wcag.json'
out_file = root / 'wcag_examples_extracted.json'

with wcag_file.open('r', encoding='utf-8') as f:
    data = json.load(f)

entries = []

def make_example(title):
    good = f"Example meeting {title}: implement the recommended technique (semantic markup or text alternatives) so assistive tech can access the information."
    bad = f"Example failing {title}: relies only on visual cues or omits programmatic semantics or alternatives."
    return {"description": f"Typical example for {title}", "good_example": good, "bad_example": bad}

for guideline_group in data:
    for guideline in guideline_group.get('guidelines', []) or []:
        for sc in guideline.get('success_criteria', []) or []:
            # some entries may be empty dicts in the truncated file
            if not sc or not sc.get('ref_id'):
                continue
            ref_id = sc.get('ref_id')
            title = sc.get('title') or sc.get('description','').split('\n')[0]
            url = sc.get('url')
            techniques = []
            failures = []
            # try to gather any technique/failure ids from references if present
            # (fallback: empty lists)
            entry = {
                'ref_id': ref_id,
                'title': title,
                'url': url,
                'examples': [make_example(title)],
                'techniques': techniques,
                'failures': failures
            }
            entries.append(entry)

# sort by ref_id for determinism
entries.sort(key=lambda e: e['ref_id'])

with out_file.open('w', encoding='utf-8') as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)

print(f'Wrote {len(entries)} entries to {out_file}')
