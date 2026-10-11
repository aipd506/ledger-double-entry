"""Unit tests for the ledgercore CLI."""

import unittest
import tempfile
from pathlib import Path
from ledger_double_entry.cli import main


class TestCLI(unittest.TestCase):
    def test_cli_full_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file = Path(tmpdir) / "test_ledger.json"

            # 1. Init
            ret_init = main(["-f", str(ledger_file), "init", "--currency", "USD"])
            self.assertEqual(ret_init, 0)
            self.assertTrue(ledger_file.exists())

            # 2. Account list
            ret_acc_list = main(["-f", str(ledger_file), "account", "list"])
            self.assertEqual(ret_acc_list, 0)

            # 3. Post transaction
            ret_post = main([
                "-f", str(ledger_file),
                "post",
                "--desc", "Customer loan origination",
                "--debit", "1100", "25000",
                "--credit", "2000", "25000",
            ])
            self.assertEqual(ret_post, 0)

            # 4. Check balance
            ret_bal = main(["-f", str(ledger_file), "balance", "1100"])
            self.assertEqual(ret_bal, 0)

            # 5. Check trial balance
            ret_tb = main(["-f", str(ledger_file), "trial-balance"])
            self.assertEqual(ret_tb, 0)

            # 6. Audit
            ret_aud = main(["-f", str(ledger_file), "audit"])
            self.assertEqual(ret_aud, 0)

            # 7. Journal
            ret_jrn = main(["-f", str(ledger_file), "journal"])
            self.assertEqual(ret_jrn, 0)


if __name__ == "__main__":
    unittest.main()
