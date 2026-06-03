from repair_csv import repair_file
result = repair_file('6412.csv', fix_negative_volumes=True, backup=True, dry_run=False)
print(result)
