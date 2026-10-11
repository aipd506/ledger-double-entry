"""Core double-entry general ledger engine with cryptographic SHA-256 hash chaining."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import uuid

from .models import (
    Account,
    AccountType,
    Posting,
    PostingDirection,
    JournalEntry,
    TrialBalanceRow,
    AuditResult,
)

GENESIS_HASH = "0" * 64


class Ledger:
    """Core banking general ledger implementing immutable double-entry invariants and audit chaining."""

    def __init__(self):
        self.accounts: Dict[str, Account] = {}
        self.entries: List[JournalEntry] = []

    def add_account(
        self,
        account_id: str,
        name: str,
        account_type: AccountType,
        currency: str = "USD",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Account:
        """Register a new account into the chart of accounts."""
        if account_id in self.accounts:
            raise ValueError(f"Account ID '{account_id}' already exists")

        acc = Account(
            id=account_id,
            name=name,
            type=account_type,
            currency=currency.upper(),
            metadata=metadata or {},
        )
        self.accounts[account_id] = acc
        return acc

    def get_account(self, account_id: str) -> Account:
        if account_id not in self.accounts:
            raise KeyError(f"Account ID '{account_id}' not found in ledger")
        return self.accounts[account_id]

    def post_transaction(
        self,
        description: str,
        postings: List[Posting],
        tx_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> JournalEntry:
        """Post a multi-leg transaction, verifying debit/credit equilibrium per currency."""
        if len(postings) < 2:
            raise ValueError("A double-entry transaction must have at least two postings")

        # Validate accounts and amounts
        currency_debits = defaultdict(Decimal)
        currency_credits = defaultdict(Decimal)

        for p in postings:
            if p.account_id not in self.accounts:
                raise KeyError(f"Posting references unknown account '{p.account_id}'")
            if p.amount <= 0:
                raise ValueError(f"Posting amount must be strictly positive, got {p.amount}")

            cur = p.currency.upper()
            if p.direction == PostingDirection.DEBIT:
                currency_debits[cur] += p.amount
            elif p.direction == PostingDirection.CREDIT:
                currency_credits[cur] += p.amount
            else:
                raise ValueError(f"Invalid posting direction: {p.direction}")

        # Invariant check: Debits == Credits per currency leg
        all_currencies = set(currency_debits.keys()).union(set(currency_credits.keys()))
        for cur in all_currencies:
            deb = currency_debits[cur]
            cred = currency_credits[cur]
            if deb != cred:
                raise ValueError(
                    f"Double-entry imbalance for currency {cur}: debits={deb}, credits={cred} (diff: {deb - cred})"
                )

        seq = len(self.entries) + 1
        prev_hash = self.entries[-1].hash if self.entries else GENESIS_HASH
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        t_id = tx_id or str(uuid.uuid4())

        entry = JournalEntry(
            sequence=seq,
            prev_hash=prev_hash,
            timestamp=ts,
            tx_id=t_id,
            description=description,
            postings=postings,
        )
        entry.hash = entry.calculate_hash()
        self.entries.append(entry)
        return entry

    def get_balance(self, account_id: str, currency: Optional[str] = None) -> Decimal:
        """Calculate net balance for an account respecting normal balance conventions."""
        account = self.get_account(account_id)
        cur = (currency or account.currency).upper()

        total_debits = Decimal("0")
        total_credits = Decimal("0")

        for entry in self.entries:
            for p in entry.postings:
                if p.account_id == account_id and p.currency.upper() == cur:
                    if p.direction == PostingDirection.DEBIT:
                        total_debits += p.amount
                    else:
                        total_credits += p.amount

        if account.is_debit_normal():
            # Asset or Expense: Debit increases, Credit decreases
            return total_debits - total_credits
        else:
            # Liability, Equity, Revenue: Credit increases, Debit decreases
            return total_credits - total_debits

    def trial_balance(self) -> Tuple[List[TrialBalanceRow], Dict[str, Dict[str, Decimal]]]:
        """Compute trial balance across all accounts and verify total debit/credit parity."""
        # Map: (account_id, currency) -> (total_debits, total_credits)
        totals = defaultdict(lambda: {"debits": Decimal("0"), "credits": Decimal("0")})

        for entry in self.entries:
            for p in entry.postings:
                key = (p.account_id, p.currency.upper())
                if p.direction == PostingDirection.DEBIT:
                    totals[key]["debits"] += p.amount
                else:
                    totals[key]["credits"] += p.amount

        rows: List[TrialBalanceRow] = []
        grand_totals = defaultdict(lambda: {"debits": Decimal("0"), "credits": Decimal("0"), "imbalance": Decimal("0")})

        for acc_id, acc in self.accounts.items():
            # Collect currencies used by this account
            acc_keys = [k for k in totals.keys() if k[0] == acc_id]
            if not acc_keys:
                # Include at least default currency with 0
                acc_keys = [(acc_id, acc.currency.upper())]

            for _, cur in acc_keys:
                d = totals[(acc_id, cur)]["debits"]
                c = totals[(acc_id, cur)]["credits"]
                net = (d - c) if acc.is_debit_normal() else (c - d)

                rows.append(
                    TrialBalanceRow(
                        account_id=acc_id,
                        name=acc.name,
                        account_type=acc.type.value,
                        currency=cur,
                        total_debits=d,
                        total_credits=c,
                        net_balance=net,
                    )
                )
                grand_totals[cur]["debits"] += d
                grand_totals[cur]["credits"] += c

        for cur, val in grand_totals.items():
            val["imbalance"] = val["debits"] - val["credits"]

        return rows, dict(grand_totals)

    def audit(self) -> AuditResult:
        """Verify cryptographic chain continuity and double-entry invariants from genesis to tip."""
        errors: List[str] = []
        expected_prev = GENESIS_HASH

        for idx, entry in enumerate(self.entries, start=1):
            if entry.sequence != idx:
                errors.append(f"Sequence mismatch at index {idx}: entry declared sequence {entry.sequence}")
                return AuditResult(is_valid=False, entries_checked=idx - 1, errors=errors, broken_sequence=idx)

            if entry.prev_hash != expected_prev:
                errors.append(
                    f"Cryptographic chain broken at sequence #{entry.sequence}: prev_hash '{entry.prev_hash}' does not match expected '{expected_prev}'"
                )
                return AuditResult(is_valid=False, entries_checked=idx - 1, errors=errors, broken_sequence=entry.sequence)

            computed_hash = entry.calculate_hash()
            if entry.hash != computed_hash:
                errors.append(
                    f"Entry hash corruption at sequence #{entry.sequence}: record hash '{entry.hash}' != computed '{computed_hash}'"
                )
                return AuditResult(is_valid=False, entries_checked=idx - 1, errors=errors, broken_sequence=entry.sequence)

            # Check debit/credit equilibrium of entry
            currency_debits = defaultdict(Decimal)
            currency_credits = defaultdict(Decimal)
            for p in entry.postings:
                cur = p.currency.upper()
                if p.direction == PostingDirection.DEBIT:
                    currency_debits[cur] += p.amount
                else:
                    currency_credits[cur] += p.amount

            for cur in set(currency_debits.keys()).union(set(currency_credits.keys())):
                if currency_debits[cur] != currency_credits[cur]:
                    errors.append(
                        f"Mathematical imbalance in sequence #{entry.sequence} for {cur}: debits={currency_debits[cur]}, credits={currency_credits[cur]}"
                    )
                    return AuditResult(is_valid=False, entries_checked=idx - 1, errors=errors, broken_sequence=entry.sequence)

            expected_prev = entry.hash

        return AuditResult(is_valid=len(errors) == 0, entries_checked=len(self.entries), errors=errors)

    def save_to_file(self, filepath: str):
        """Persist chart of accounts and journal entries to JSON."""
        data = {
            "version": "0.1.0",
            "accounts": [a.to_dict() for a in self.accounts.values()],
            "entries": [e.to_dict() for e in self.entries],
        }
        Path(filepath).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load_from_file(cls, filepath: str) -> "Ledger":
        """Load ledger from JSON file."""
        text = Path(filepath).read_text(encoding="utf-8")
        data = json.loads(text)

        ledger = cls()
        for a_data in data.get("accounts", []):
            acc = Account.from_dict(a_data)
            ledger.accounts[acc.id] = acc

        for e_data in data.get("entries", []):
            entry = JournalEntry.from_dict(e_data)
            ledger.entries.append(entry)

        return ledger
