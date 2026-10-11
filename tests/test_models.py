"""Unit tests for ledger data models."""

import unittest
from decimal import Decimal
from ledger_double_entry.models import (
    Account,
    AccountType,
    Posting,
    PostingDirection,
    JournalEntry,
)


class TestModels(unittest.TestCase):
    def test_account_normal_balances(self):
        asset = Account("1010", "Cash", AccountType.ASSET)
        self.assertTrue(asset.is_debit_normal())

        expense = Account("5010", "Salaries", AccountType.EXPENSE)
        self.assertTrue(expense.is_debit_normal())

        liability = Account("2010", "Customer Deposits", AccountType.LIABILITY)
        self.assertFalse(liability.is_debit_normal())

        equity = Account("3010", "Retained Earnings", AccountType.EQUITY)
        self.assertFalse(equity.is_debit_normal())

        revenue = Account("4010", "Fee Revenue", AccountType.REVENUE)
        self.assertFalse(revenue.is_debit_normal())

    def test_journal_entry_hash(self):
        p1 = Posting("1010", PostingDirection.DEBIT, Decimal("100.00"), "USD")
        p2 = Posting("2010", PostingDirection.CREDIT, Decimal("100.00"), "USD")
        entry = JournalEntry(
            sequence=1,
            prev_hash="0" * 64,
            timestamp="2026-10-11T12:00:00Z",
            tx_id="tx-1234",
            description="Initial deposit",
            postings=[p1, p2],
        )
        h1 = entry.calculate_hash()
        self.assertEqual(len(h1), 64)
        # Hash must be deterministic
        self.assertEqual(h1, entry.calculate_hash())


if __name__ == "__main__":
    unittest.main()
