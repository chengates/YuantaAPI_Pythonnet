import os, repair_csv, csv, json
cwd = os.getcwd()
result = {
    'cwd': cwd,
    'exists': os.path.exists('6412.csv')
}
res = repair_csv.repair_file('6412.csv', fix_negative_volumes=True, backup=True, dry_run=False)
result['repair_result'] = res
result['backup_exists'] = os.path.exists('6412.csv.bak')
rows=[]
with open('6412.csv', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    for i,row in enumerate(reader):
        if i < 20 and int(row['deal_volume']) < 0:
            rows.append({'row': i, 'deal_volume': row['deal_volume'], 'deal_amount': row['deal_amount']})
        if i>=20:
            break
result['negative_rows'] = rows
with open('verify_repair.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('done')
