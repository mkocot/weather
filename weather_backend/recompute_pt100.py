#!/usr/bin/env python3
'''Re-derive temp_255 from the stored PT100 raw codes (pt100_255).

Rows without raw data keep their original temp_255; the 0xFFFF dead-channel
sentinel (ADR-0014) is also left untouched. Raw codes are never modified, so
the script can be re-run with a different --ref to compare
reference-resistor assumptions.

Examples:
    python3 recompute_pt100.py ../sensors_03.sqlite --dry-run --ref 400
    python3 recompute_pt100.py ../sensors_03.sqlite --ref 400
'''

import argparse
import sqlite3
import sys

from protocol import pt100_raw_to_temp

SENTINEL = 0xFFFF


def stats(values):
    return f'min={min(values):.3f} max={max(values):.3f} avg={sum(values) / len(values):.3f}'


def recompute(db_path, ref_resistor, dry_run, sample):
    db = sqlite3.connect(db_path)
    total, = db.execute('SELECT COUNT(*) FROM "values"').fetchone()
    rows = db.execute(
        'SELECT timestamp, temp_255, pt100_255 FROM "values" '
        'WHERE pt100_255 IS NOT NULL AND pt100_255 != ? '
        'ORDER BY timestamp', (SENTINEL,)).fetchall()
    retained = total - len(rows)

    print(f'db        : {db_path}')
    print(f'ref       : {ref_resistor} ohm (rtd_nominal=100)')
    print(f'rows      : {total} total, {len(rows)} with raw code, {retained} kept as-is (no raw / sentinel)')

    if not rows:
        print('nothing to update')
        return

    updates = [(pt100_raw_to_temp(code, ref_resistor), ts) for ts, _, code in rows]
    changed = sum(1 for (new, ts), (_, old, _) in zip(updates, rows) if abs(new - old) > 1e-9)
    old_temps = [old for _, old, _ in rows]
    new_temps = [new for new, _ in updates]

    print(f'old temp  : {stats(old_temps)}')
    print(f'new temp  : {stats(new_temps)}')
    print(f'changed   : {changed} of {len(rows)}')

    if sample:
        print(f'--- first {min(sample, len(rows))} rows (old -> new)')
        for (ts, old, code), (new, _) in list(zip(rows, updates))[:sample]:
            print(f'  {ts}  code={code:.0f}  {old:.4f} -> {new:.4f}')

    if dry_run:
        print('dry run: no changes written')
        return

    db.executemany('UPDATE "values" SET temp_255 = ? WHERE timestamp = ?', updates)
    db.commit()
    print(f'committed: {len(updates)} rows updated')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Re-derive temp_255 from pt100_255 raw codes.')
    ap.add_argument('db', nargs='?', default='sensors_03.sqlite', help='sqlite database (default: %(default)s)')
    ap.add_argument('--ref', type=float, default=430.0, help='reference resistor in ohm (default: %(default)s)')
    ap.add_argument('--dry-run', action='store_true', help='show the result without writing')
    ap.add_argument('--sample', type=int, default=5, help='rows to preview (0 disables, default: %(default)s)')
    args = ap.parse_args(argv)

    if args.ref <= 0:
        ap.error('--ref must be positive')
    try:
        recompute(args.db, args.ref, args.dry_run, args.sample)
    except sqlite3.Error as e:
        sys.exit(f'error: {e}')


if __name__ == '__main__':
    main()
