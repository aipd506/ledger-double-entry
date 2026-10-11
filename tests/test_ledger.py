"""Unit tests for Ledger double-entry engine and audit chain validation."""

import unittest
from decimal import Decimal
from ledger_double_entry.ledger import Ledger
from ledger_double_entry.models import AccountType, Posting, PostingDirection


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.add_account("1000", "Cash", AccountType.ASSET, currency="USD")
        self.ledger.add_account("2000", "Customer Deposits", AccountType.LIABILITY, currency="USD")
        self.ledger.add_account("3000", "Common Equity", AccountType.EQUITY, currency="USD")
        self.ledger.add_account("4000", "Interest Income", AccountType.REVENUE, currency="USD")

    def test_post_valid_transaction(self):
        postings = [
            Posting("1000", PostingDirection.DEBIT, Decimal("5000.00"), "USD"),
            Posting("2000", PostingDirection.CREDIT, Decimal("5000.00"), "USD"),
        ]
        entry = self.ledger.post_transaction("Customer wire deposit", postings)
        self.assertEqual(entry.sequence, 1)
        self.assertEqual(entry.prev_hash, "0" * 64)
        self.assertEqual(len(entry.hash), 64)

        # Cash (Asset) should have debit balance 5000.00
        self.assertEqual(self.ledger.get_balance("1000"), Decimal("5000.00"))
        # Deposits (Liability) should have credit balance 5000.00
        self.assertEqual(self.ledger.get_balance("2000"), Decimal("5000.00"))

    def test_reject_imbalanced_transaction(self):
        postings = [
            Posting("1000", PostingDirection.DEBIT, Decimal("5000.00"), "USD"),
            Posting("2000", PostingDirection.CREDIT, Decimal("4999.00"), "USD"),
        ]
        with self.assertRaises(ValueError) as ctx:
            self.ledger.post_transaction("Imbalanced post", postings)
        self.assertIn("Double-entry imbalance", str(ctx.exception))

    def test_reject_negative_or_zero_amount(self):
        postings = [
            Posting("1000", PostingDirection.DEBIT, Decimal("-100.00"), "USD"),
            Posting("2000", PostingDirection.CREDIT, Decimal("-100.00"), "USD"),
        ]
        with self.assertRaises(ValueError) as ctx:
            self.ledger.post_transaction("Negative amount", postings)
        self.assertIn("strictly positive", str(ctx.exception))

    def test_reject_unknown_account(self):
        postings = [
            Posting("9999", PostingDirection.DEBIT, Decimal("100.00"), "USD"),
            Posting("2000", PostingDirection.CREDIT, Decimal("100.00"), "USD"),
        ]
        with self.assertRaises(KeyError):
            self.ledger.post_transaction("Unknown account", postings)

    def test_cryptographic_audit_clean(self):
        for i in range(5):
            self.ledger.post_transaction(
                f"Deposit #{i+1}",
                [
                    Posting("1000", PostingDirection.DEBIT, Decimal("1000.00"), "USD"),
                    Posting("2000", PostingDirection.CREDIT, Decimal("1000.00"), "USD"),
                ],
            )
        res = self.ledger.audit()
        self.assertTrue(res.is_valid, f"Audit failed: {res.errors}")
        self.assertEqual(res.entries_checked, 5)

    def test_cryptographic_audit_detects_tamper(self):
        for i in range(3):
            self.ledger.post_transaction(
                f"Tx #{i+1}",
                [
                    Posting("1000", PostingDirection.DEBIT, Decimal("100.00"), "USD"),
                    Posting("2000", PostingDirection.CREDIT, Decimal("100.00"), "USD"),
                ],
            )
        # Tamper entry 2 description (invalidating hash)
        self.ledger.entries[1].description = "Tampered unauthorized adjustment"
        res = self.ledger.audit()
        self.assertFalse(res.is_valid)
        self.assertEqual(res.broken_sequence, 2)
        self.assertTrue(any("corruption" in err for err in res.errors))

    def test_trial_balance(self):
        self.ledger.post_transaction(
            "Capital Injection",
            [
                Posting("1000", PostingDirection.DEBIT, Decimal("50000.00"), "USD"),
                Posting("3000", PostingDirection.CREDIT, Decimal("50000.00"), "USD"),
            ],
        )
        rows, grand_totals = self.ledger.trial_balance()
        self.assertIn("USD", grand_totals)
        usd_totals = grand_totals["USD"]
        self.assertEqual(usd_totals["debits"], Decimal("50000.00"))
        self.assertEqual(usd_totals["credits"], Decimal("50000.00"))
        self.assertEqual(usd_totals["imbalance"], Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
