import argparse
import csv
import json
import math
import os
import shutil
from pathlib import Path

VOLUME_FIELDS = {
    'deal_volume',
    'total_in_volume',
    'total_out_volume',
    'buy_total_volume',
    'sell_total_volume',
    'estimated_day_volume',
}
PRICE_FIELDS = {
    'open_price',
    'high_price',
    'low_price',
    'close_price',
    'ma5',
    'ma10',
}
AMOUNT_FIELDS = {'deal_amount'}
IGNORE_DIRS = {'yesterday', '.git', '.vs', '.vscode', '.claude'}


def parse_number(value):
    if value is None:
        return None
    value = str(value).strip()
    if value == '' or value.lower() == 'nan':
        return None
    try:
        if '.' in value or 'e' in value.lower():
            return float(value)
        return int(value)
    except ValueError:
        try:
            return float(value.replace(',', ''))
        except ValueError:
            return None


def numeric_row(row):
    parsed = {}
    for key, raw in row.items():
        if raw is None or raw == '':
            parsed[key] = None
            continue
        if key in VOLUME_FIELDS or key in PRICE_FIELDS or key in AMOUNT_FIELDS or key in {'trade_count', 'participation_score'}:
            parsed[key] = parse_number(raw)
        else:
            parsed[key] = raw
    return parsed


def price_needs_normalization(row):
    close_price = row.get('close_price')
    if close_price is None:
        return False
    return abs(close_price) > 100000


def diagnose_row(parsed):
    issues = []

    if any(parsed.get(field) is not None and abs(parsed.get(field)) > 100000 for field in PRICE_FIELDS):
        issues.append('price_scale_suspect')

    for field in VOLUME_FIELDS:
        val = parsed.get(field)
        if val is not None and val < 0:
            issues.append(f'negative_{field}')
        if val is not None and val == 0 and field == 'deal_volume' and parsed.get('trade_count') not in (None, 0):
            issues.append('zero_deal_volume_with_trades')

    deal_amount = parsed.get('deal_amount')
    deal_volume = parsed.get('deal_volume')
    close_price = parsed.get('close_price')
    if deal_amount is not None and deal_volume and close_price:
        if deal_volume != 0:
            approx_price = deal_amount / deal_volume
            if close_price > 0 and not (0.1 * close_price <= approx_price <= 10 * close_price):
                issues.append('deal_amount_mismatch')

    volume_values = [parsed.get(field) for field in VOLUME_FIELDS if parsed.get(field) is not None]
    if volume_values:
        max_volume = max(volume_values)
        min_volume = min(volume_values)
        if min_volume > 0 and max_volume / min_volume > 1000:
            issues.append('volume_unit_suspect')

    return issues


def volume_row_is_suspect(row):
    issues = diagnose_row(row)
    return any(issue.startswith('negative_') or issue in {
        'deal_amount_mismatch',
        'volume_unit_suspect',
        'zero_deal_volume_with_trades',
    } for issue in issues)


def infer_file_causes(stats):
    causes = []
    if stats['price_scale_candidates'] > 0:
        causes.append('可能存在價格欄位單位錯誤，價格值應除以 10000')
    if stats['negative_volumes'] > 0:
        causes.append('資料中出現負值成交量或總量，可能為資料抓取錯誤或欄位解讀錯誤')
    if stats['volume_suspects'] > 0 and stats['price_suspects'] == 0:
        causes.append('成交量單位不一致或成交資訊不匹配，可能需檢查張/股轉換')
    if stats['price_suspects'] == 0 and stats['volume_suspects'] == 0:
        causes.append('未偵測到明顯價格/量值異常，建議手動比對異常行')
    return causes


def analyze_file(path):
    path = Path(path)
    if path.is_dir():
        return None

    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    stats = {
        'rows': len(rows),
        'price_suspects': 0,
        'volume_suspects': 0,
        'negative_prices': 0,
        'negative_volumes': 0,
        'price_scale_candidates': 0,
        'issue_samples': [],
        'causes': [],
    }
    for index, row in enumerate(rows, start=1):
        parsed = numeric_row(row)
        issues = diagnose_row(parsed)
        if 'price_scale_suspect' in issues:
            stats['price_suspects'] += 1
            stats['price_scale_candidates'] += 1
        if volume_row_is_suspect(parsed):
            stats['volume_suspects'] += 1
        for field in PRICE_FIELDS:
            val = parsed.get(field)
            if val is not None and val < 0:
                stats['negative_prices'] += 1
        for field in VOLUME_FIELDS:
            val = parsed.get(field)
            if val is not None and val < 0:
                stats['negative_volumes'] += 1
        if issues and len(stats['issue_samples']) < 5:
            stats['issue_samples'].append({
                'row_number': index,
                'issues': issues,
                'values': {field: parsed.get(field) for field in PRICE_FIELDS | VOLUME_FIELDS | AMOUNT_FIELDS | {'trade_count'}}
            })
    stats['causes'] = infer_file_causes(stats)
    return stats


def repair_row(parsed, fix_prices=False, fix_volumes=False, volume_unit=None, fix_negative_volumes=False):
    repaired = parsed.copy()
    if fix_prices:
        for field in PRICE_FIELDS:
            val = repaired.get(field)
            if val is not None and abs(val) > 100000:
                repaired[field] = round(val / 10000, 2)
    if fix_volumes and volume_unit == 'shares':
        # restore to shares when the CSV has lot-based volumes
        for field in VOLUME_FIELDS:
            val = repaired.get(field)
            if val is not None:
                repaired[field] = int(val * 1000)
    if fix_volumes and volume_unit == 'lots':
        for field in VOLUME_FIELDS:
            val = repaired.get(field)
            if val is not None:
                repaired[field] = int(val / 1000)
    if fix_negative_volumes:
        for field in VOLUME_FIELDS:
            val = repaired.get(field)
            if val is not None and val < 0:
                repaired[field] = abs(val)
        deal_amount = repaired.get('deal_amount')
        if deal_amount is not None and deal_amount < 0:
            repaired['deal_amount'] = abs(deal_amount)
    return repaired


def format_row_for_write(row, fieldnames):
    out = {}
    for key in fieldnames:
        value = row.get(key)
        if value is None:
            out[key] = ''
        elif isinstance(value, list):
            out[key] = json.dumps(value, ensure_ascii=False)
        else:
            out[key] = str(value)
    return out


def repair_file(path, *, fix_prices=False, fix_volumes=False, volume_unit=None, fix_negative_volumes=False, backup=True, dry_run=True):
    path = Path(path)
    if path.suffix.lower() != '.csv':
        return None

    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        original_fieldnames = reader.fieldnames or []

    if not rows:
        return {'path': str(path), 'rows': 0, 'skipped': True}

    parsed_rows = [numeric_row(row) for row in rows]
    repaired_rows = []
    changes = {
        'price_fix_count': 0,
        'volume_fix_count': 0,
        'negative_row_count': 0,
        'price_scale_rows': 0,
        'negative_volume_fix_count': 0,
        'negative_deal_amount_fix_count': 0,
    }

    for parsed in parsed_rows:
        repaired = repair_row(
            parsed,
            fix_prices=fix_prices,
            fix_volumes=fix_volumes,
            volume_unit=volume_unit,
            fix_negative_volumes=fix_negative_volumes,
        )
        if repaired != parsed:
            if fix_prices:
                for field in PRICE_FIELDS:
                    if repaired.get(field) != parsed.get(field):
                        changes['price_fix_count'] += 1
            if fix_volumes and volume_unit in {'shares', 'lots'}:
                if any(repaired.get(field) != parsed.get(field) for field in VOLUME_FIELDS):
                    changes['volume_fix_count'] += 1
            if fix_negative_volumes:
                changed_negative_volume_fields = sum(
                    1 for field in VOLUME_FIELDS
                    if parsed.get(field) is not None and parsed.get(field) < 0 and repaired.get(field) == abs(parsed.get(field))
                )
                changes['negative_volume_fix_count'] += changed_negative_volume_fields
                if parsed.get('deal_amount') is not None and parsed.get('deal_amount') < 0 and repaired.get('deal_amount') == abs(parsed.get('deal_amount')):
                    changes['negative_deal_amount_fix_count'] += 1
        if volume_row_is_suspect(repaired):
            changes['negative_row_count'] += 1
        if price_needs_normalization(parsed):
            changes['price_scale_rows'] += 1
        repaired_rows.append(repaired)

    if dry_run:
        return {'path': str(path), 'rows': len(rows), 'changes': changes, 'fieldnames': original_fieldnames}

    if backup:
        backup_path = path.with_suffix(path.suffix + '.bak')
        shutil.copy2(path, backup_path)
        print(f'備份原始 CSV: {backup_path}')

    output_path = path
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=original_fieldnames)
        writer.writeheader()
        for row in repaired_rows:
            writer.writerow(format_row_for_write(row, original_fieldnames))

    return {'path': str(path), 'rows': len(rows), 'changes': changes, 'written': True}


def collect_csv_paths(root, include_daily=True):
    root = Path(root)
    candidates = []
    for path in root.glob('*.csv'):
        if path.name.startswith('~$'):
            continue
        if path.parent.name in IGNORE_DIRS:
            continue
        if not include_daily and path.name.startswith('@'):
            continue
        candidates.append(path)
    return sorted(candidates)


def main():
    parser = argparse.ArgumentParser(description='Yuanta OneAPI CSV 修復工具')
    parser.add_argument('--path', '-p', default='.', help='掃描 CSV 的目錄，預設為當前目錄')
    parser.add_argument('--include-daily', action='store_true', help='包含 @stockID.csv 日結檔案')
    parser.add_argument('--fix-prices', action='store_true', help='修正超大價格欄位 (/10000)')
    parser.add_argument('--fix-volumes', action='store_true', help='修正整體量值單位')
    parser.add_argument('--volume-unit', choices=['shares', 'lots'], help='如果修正量值，指定目標單位：shares=股, lots=張')
    parser.add_argument('--fix-negative-volumes', action='store_true', help='修正負值成交量/內外盤量為正值')
    parser.add_argument('--apply', action='store_true', help='實際寫回 CSV，否則僅列出診斷結果')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True, help='預設不覆寫，僅診斷')
    parser.add_argument('--no-dry-run', dest='dry_run', action='store_false', help='關閉 dry run，會覆寫 CSV（需同時加 --apply）')
    args = parser.parse_args()

    csv_files = collect_csv_paths(args.path, include_daily=args.include_daily)
    if not csv_files:
        print('未找到任何 CSV 檔案。')
        return 1

    report = []
    for csv_path in csv_files:
        summary = analyze_file(csv_path)
        if summary is None:
            continue
        print(f"{csv_path.name}: rows={summary['rows']} price_suspects={summary['price_suspects']} volume_suspects={summary['volume_suspects']} negative_prices={summary['negative_prices']} negative_volumes={summary['negative_volumes']}")
        report.append({'file': str(csv_path), **summary})

    diagnostic_path = Path(args.path) / 'csv_repair_diagnostic.json'
    with open(diagnostic_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'診斷報告已寫入: {diagnostic_path}')

    if args.apply and not args.dry_run:
        print('\n開始修復 CSV 檔案...')
        for csv_path in csv_files:
            result = repair_file(
                csv_path,
                fix_prices=args.fix_prices,
                fix_volumes=args.fix_volumes,
                volume_unit=args.volume_unit,
                fix_negative_volumes=args.fix_negative_volumes,
                backup=True,
                dry_run=False,
            )
            print(f"修復完畢: {result['path']} rows={result['rows']} changes={result['changes']}")

        report_path = Path(args.path) / 'csv_repair_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'修復報告已寫入: {report_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
