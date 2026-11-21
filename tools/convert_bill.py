# -*- coding: utf-8 -*-
"""把支付宝/微信导出的账单 CSV 转成知几对账格式 (id,amount,desc)。

用法:
    python tools/convert_bill.py 支付宝账单.csv -o actual.csv
    python tools/convert_bill.py 微信账单.csv -o actual.csv --side 支出

自动识别支付宝/微信格式与 GBK/UTF-8 编码；默认只保留成功完成的交易。
对账用的 expected.json 需你自己提供"应有账目"，格式: {"entries":[{"id":"...","amount":12.5}]}
"""
import argparse
import sys as _s
if hasattr(_s.stdout, 'reconfigure'): _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import csv
import io
import sys
from pathlib import Path


def read_text(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    sys.exit("无法识别文件编码（支持 UTF-8 / GBK）")


def find_header(lines):
    for i, line in enumerate(lines):
        if ("交易单号" in line or "交易号" in line) and "金额" in line:
            return i
    sys.exit("未找到表头行：请确认是支付宝/微信官方导出的账单 CSV")


def clean_amount(s):
    s = s.replace("¥", "").replace("￥", "").replace(",", "").strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="actual.csv")
    ap.add_argument("--side", choices=["支出", "收入", "all"], default="all")
    args = ap.parse_args()

    lines = read_text(args.src).splitlines()
    h = find_header(lines)
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[h:]))))
    is_wechat = any("交易单号" in (r or {}) for r in rows[:1]) or "当前状态" in (rows[0] if rows else {})

    out, skipped = [], 0
    for r in rows:
        r = { (k or "").strip(): (v or "").strip() for k, v in r.items() }
        rid = r.get("交易单号") or r.get("交易号") or r.get("支付宝交易号")
        amount = clean_amount(r.get("金额(元)") or r.get("金额（元）") or "")
        if not rid or amount is None:
            skipped += 1
            continue
        side = r.get("收/支", "")
        if args.side != "all" and side and side != args.side:
            skipped += 1
            continue
        if is_wechat:
            status = r.get("当前状态", "")
            ok = any(k in status for k in ("支付成功", "已转账", "已收钱", "对方已收钱", "已存入零钱"))
            desc = (r.get("交易对方", "") + " " + r.get("商品", "")).strip()
        else:
            status = r.get("交易状态", "")
            ok = status in ("交易成功", "支付成功", "等待确认收货")
            desc = (r.get("交易对方", "") + " " + r.get("商品名称", "")).strip()
        if not ok:
            skipped += 1
            continue
        out.append({"id": rid, "amount": amount, "desc": desc or status})

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "amount", "desc"])
        w.writeheader()
        w.writerows(out)
    print(f"完成：{len(out)} 条写入 {args.out}，跳过 {skipped} 条（退款/关闭/非目标收支/无效行）")


if __name__ == "__main__":
    main()

