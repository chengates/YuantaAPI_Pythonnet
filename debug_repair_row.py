from repair_csv import numeric_row, repair_row
import csv
with open('6412.csv', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
for row in rows[:5]:
    parsed = numeric_row(row)
    repaired = repair_row(parsed, fix_negative_volumes=True)
    if repaired != parsed:
        print('changed', parsed['deal_volume'], repaired['deal_volume'], parsed['deal_amount'], repaired['deal_amount'])
    else:
        print('same', parsed['deal_volume'], parsed['deal_amount'])
