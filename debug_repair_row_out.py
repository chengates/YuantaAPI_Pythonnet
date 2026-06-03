from repair_csv import numeric_row, repair_row
import csv
results=[]
with open('6412.csv', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    for row in list(reader)[:10]:
        parsed = numeric_row(row)
        repaired = repair_row(parsed, fix_negative_volumes=True)
        results.append({
            'deal_volume': parsed['deal_volume'],
            'deal_amount': parsed['deal_amount'],
            'repaired_deal_volume': repaired['deal_volume'],
            'repaired_deal_amount': repaired['deal_amount'],
            'changed': repaired != parsed,
        })
with open('debug_repair_output.json','w',encoding='utf-8') as f:
    import json
    json.dump(results,f,ensure_ascii=False,indent=2)
