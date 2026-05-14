import json
import os

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    wcag_path = os.path.join(base, 'wcag.json')
    examples_path = os.path.join(base, 'wcag_examples.json')
    out_path = os.path.join(base, 'guidelines_complete.json')

    with open(wcag_path, 'r', encoding='utf-8') as f:
        wcag = json.load(f)

    try:
        with open(examples_path, 'r', encoding='utf-8') as f:
            examples = json.load(f)
    except Exception:
        examples = {}

    guidelines = {}
    populated = 0
    placeholders = 0

    # High-frequency rules we want prefilled even if not present in examples
    high_freq = set(['1.1.1', '2.4.4', '4.1.2', '1.3.1', '3.1.1'])

    for section in wcag:
        for guideline in section.get('guidelines', []):
            for sc in guideline.get('success_criteria', []):
                ref = sc.get('ref_id')
                title = sc.get('title', '')

                if not ref:
                    continue

                if ref in examples:
                    ex = examples[ref]
                    guidelines[ref] = {
                        'title': ex.get('title', title),
                        'bad_code': ex.get('bad_code', ''),
                        'good_code': ex.get('good_code', '')
                    }
                    populated += 1
                elif ref in high_freq:
                    # Create a small heuristic placeholder example
                    heur_bad = f"<!-- BAD example for {ref} - replace with real code -->"
                    heur_good = f"<!-- GOOD example for {ref} - replace with real code -->"
                    guidelines[ref] = {
                        'title': title,
                        'bad_code': heur_bad,
                        'good_code': heur_good
                    }
                    populated += 1
                else:
                    guidelines[ref] = {
                        'title': title,
                        'bad_code': '<!-- TODO: add bad example -->',
                        'good_code': '<!-- TODO: add good example -->'
                    }
                    placeholders += 1

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(guidelines, f, indent=4, ensure_ascii=False)

    print(f"Wrote {out_path}: populated={populated}, placeholders={placeholders}")

if __name__ == '__main__':
    main()
