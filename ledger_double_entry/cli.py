"""Command-line interface for ledger-double-entry."""

import argparse
from decimal import Decimal
from pathlib import Path
import sys
from .models import AccountType, Posting, PostingDirection
from .ledger import Ledger

DEFAULT_LEDGER_FILE = "ledger.json"


def _get_ledger(filepath: str) -> Ledger:
    p = Path(filepath)
    if not p.exists():
        sys.stderr.write(f"Ledger file '{filepath}' not found. Run 'ledgercore init' first.\n")
        sys.exit(1)
    return Ledger.load_from_file(str(p))


def cmd_init(args) -> int:
    p = Path(args.file)
    if p.exists() and not args.force:
        sys.stderr.write(f"Error: File '{p}' already exists. Use --force to overwrite.\n")
        return 1

    ledger = Ledger()
    cur = args.currency.upper()

    # Pre-seed standard core banking chart of accounts
    ledger.add_account("1000", "Operating Cash & Central Bank Reserves", AccountType.ASSET, currency=cur)
    ledger.add_account("1100", "Customer Loans & Advances", AccountType.ASSET, currency=cur)
    ledger.add_account("2000", "Customer Demand Deposits", AccountType.LIABILITY, currency=cur)
    ledger.add_account("3000", "Common Equity Tier 1 Capital", AccountType.EQUITY, currency=cur)
    ledger.add_account("4000", "Interest & Fee Income", AccountType.REVENUE, currency=cur)
    ledger.add_account("5000", "Interest & Operational Expense", AccountType.EXPENSE, currency=cur)

    ledger.save_to_file(str(p))
    print(f"Initialized blank double-entry ledger at {p} with 6 core banking accounts (Base currency: {cur})")
    return 0


def cmd_account_add(args) -> int:
    ledger = _get_ledger(args.file)
    try:
        acc_type = AccountType(args.type.lower())
        acc = ledger.add_account(args.id, args.name, acc_type, currency=args.currency.upper())
        ledger.save_to_file(args.file)
        print(f"Added account [{acc.id}] {acc.name} ({acc.type.value.upper()}, {acc.currency})")
        return 0
    except Exception as e:
        sys.stderr.write(f"Error adding account: {e}\n")
        return 1


def cmd_account_list(args) -> int:
    ledger = _get_ledger(args.file)
    print("=" * 70)
    print(f"CHART OF ACCOUNTS ({len(ledger.accounts)} accounts)")
    print("=" * 70)
    print(f"{'ID':<10} {'NAME':<35} {'TYPE':<12} {'CURRENCY'}")
    print("-" * 70)
    for acc in ledger.accounts.values():
        print(f"{acc.id:<10} {acc.name[:33]:<35} {acc.type.value.upper():<12} {acc.currency}")
    print("=" * 70)
    return 0


def cmd_post(args) -> int:
    ledger = _get_ledger(args.file)
    cur = args.currency.upper()

    try:
        deb_amt = Decimal(str(args.debit[1]))
        cred_amt = Decimal(str(args.credit[1]))

        postings = [
            Posting(account_id=args.debit[0], direction=PostingDirection.DEBIT, amount=deb_amt, currency=cur),
            Posting(account_id=args.credit[0], direction=PostingDirection.CREDIT, amount=cred_amt, currency=cur),
        ]

        entry = ledger.post_transaction(description=args.desc, postings=postings)
        ledger.save_to_file(args.file)

        print(f"Transaction posted successfully!")
        print(f"  Sequence:    #{entry.sequence}")
        print(f"  TX ID:       {entry.tx_id}")
        print(f"  Hash:        {entry.hash[:16]}...")
        print(f"  Debit:       [{args.debit[0]}] {deb_amt} {cur}")
        print(f"  Credit:      [{args.credit[0]}] {cred_amt} {cur}")
        return 0
    except Exception as e:
        sys.stderr.write(f"Transaction rejected: {e}\n")
        return 1


def cmd_balance(args) -> int:
    ledger = _get_ledger(args.file)
    cur = args.currency.upper() if args.currency else None

    if args.account:
        try:
            acc = ledger.get_account(args.account)
            bal = ledger.get_balance(args.account, currency=cur)
            currency_display = cur or acc.currency
            print(f"Account [{acc.id}] {acc.name}: {bal:.2f} {currency_display} ({'Debit' if acc.is_debit_normal() else 'Credit'} Normal)")
            return 0
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            return 1
    else:
        print("=" * 70)
        print("ACCOUNT BALANCES")
        print("=" * 70)
        for acc in ledger.accounts.values():
            currency_display = cur or acc.currency
            bal = ledger.get_balance(acc.id, currency=currency_display)
            print(f"{acc.id:<10} {acc.name[:35]:<37} {bal:>15.2f} {currency_display}")
        print("=" * 70)
        return 0


def cmd_trial_balance(args) -> int:
    ledger = _get_ledger(args.file)
    rows, grand_totals = ledger.trial_balance()

    print("=" * 80)
    print("TRIAL BALANCE")
    print("=" * 80)
    print(f"{'ACCOUNT':<10} {'NAME':<28} {'TYPE':<10} {'DEBITS':>12} {'CREDITS':>12} {'NET':>12}")
    print("-" * 80)
    for r in rows:
        print(f"{r.account_id:<10} {r.name[:26]:<28} {r.account_type[:8]:<10} {r.total_debits:>12.2f} {r.total_credits:>12.2f} {r.net_balance:>12.2f}")
    print("=" * 80)
    print("GRAND TOTALS:")
    for cur, val in grand_totals.items():
        status = "BALANCED" if val["imbalance"] == 0 else f"IMBALANCE: {val['imbalance']}"
        print(f"  {cur}: Total Debits={val['debits']:.2f}, Total Credits={val['credits']:.2f} -> {status}")
    print("=" * 80)
    return 0


def cmd_audit(args) -> int:
    ledger = _get_ledger(args.file)
    res = ledger.audit()
    print(res.summary())
    return 0 if res.is_valid else 1


def cmd_journal(args) -> int:
    ledger = _get_ledger(args.file)
    limit = args.limit or len(ledger.entries)

    print("=" * 80)
    print(f"JOURNAL ENTRIES ({len(ledger.entries)} total, showing last {limit})")
    print("=" * 80)
    for entry in ledger.entries[-limit:]:
        print(f"[Seq #{entry.sequence}] {entry.timestamp} | TX: {entry.tx_id[:8]} | Hash: {entry.hash[:12]}...")
        print(f"  Desc: {entry.description}")
        for p in entry.postings:
            dir_str = "DR" if p.direction == PostingDirection.DEBIT else "CR"
            print(f"    {dir_str} [{p.account_id}] {p.amount:.2f} {p.currency}")
        print()
    print("=" * 80)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ledgercore",
        description="Immutable, append-only double-entry core banking general ledger with SHA-256 cryptographic chaining",
    )
    parser.add_argument("-f", "--file", default=DEFAULT_LEDGER_FILE, help=f"Path to ledger file (default: {DEFAULT_LEDGER_FILE})")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new ledger file")
    p_init.add_argument("--currency", default="USD", help="Base currency code")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing ledger")
    p_init.set_defaults(func=cmd_init)

    # account
    p_acc = subparsers.add_parser("account", help="Manage chart of accounts")
    acc_sub = p_acc.add_subparsers(dest="acc_cmd", required=True)
    p_acc_add = acc_sub.add_parser("add", help="Add account to ledger")
    p_acc_add.add_argument("id", help="Unique account ID (e.g. 1010)")
    p_acc_add.add_argument("name", help="Account name")
    p_acc_add.add_argument("type", choices=["asset", "liability", "equity", "revenue", "expense"], help="Account type")
    p_acc_add.add_argument("--currency", default="USD", help="Account currency")
    p_acc_add.set_defaults(func=cmd_account_add)

    p_acc_list = acc_sub.add_parser("list", help="List all accounts")
    p_acc_list.set_defaults(func=cmd_account_list)

    # post
    p_post = subparsers.add_parser("post", help="Post a balanced double-entry transaction")
    p_post.add_argument("--desc", required=True, help="Transaction description")
    p_post.add_argument("--debit", nargs=2, metavar=("ACCOUNT", "AMOUNT"), required=True, help="Debit leg: ACCOUNT AMOUNT")
    p_post.add_argument("--credit", nargs=2, metavar=("ACCOUNT", "AMOUNT"), required=True, help="Credit leg: ACCOUNT AMOUNT")
    p_post.add_argument("--currency", default="USD", help="Currency code")
    p_post.set_defaults(func=cmd_post)

    # balance
    p_bal = subparsers.add_parser("balance", help="View account balances")
    p_bal.add_argument("account", nargs="?", help="Specific account ID")
    p_bal.add_argument("--currency", help="Filter by currency")
    p_bal.set_defaults(func=cmd_balance)

    # trial-balance
    p_tb = subparsers.add_parser("trial-balance", help="Display full trial balance and parity check")
    p_tb.set_defaults(func=cmd_trial_balance)

    # audit
    p_aud = subparsers.add_parser("audit", help="Verify cryptographic chain and mathematical balance")
    p_aud.set_defaults(func=cmd_audit)

    # journal
    p_jrn = subparsers.add_parser("journal", help="View journal log entries")
    p_jrn.add_argument("--limit", type=int, help="Limit number of displayed entries")
    p_jrn.set_defaults(func=cmd_journal)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
