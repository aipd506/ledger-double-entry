# ledger-double-entry

Immutable, append-only double-entry core banking general ledger with SHA-256 cryptographic chaining.

Eliminates silent balance drift, transaction tampering, and unverified manual adjustments in core banking and fintech ledgers.

## Key Capabilities

1. Strict Double-Entry Equilibrium: Enforces \(\sum \text{Debits} \equiv \sum \text{Credits}\) mathematically on every transaction before posting.
2. Normal Balance Conventions:
   - Debit Normal: Assets, Expenses (\(\text{Balance} = \text{Debits} - \text{Credits}\)).
   - Credit Normal: Liabilities, Equity, Revenue (\(\text{Balance} = \text{Credits} - \text{Debits}\)).
3. Cryptographic Audit Chain: Every journal entry is bound to the preceding entry via a SHA-256 hash pointer (`prev_hash`), creating a tamper-evident sequential blockchain.
4. Tamper Detection: The audit engine traverses the chain from genesis, verifying that not a single byte, amount, timestamp, or account reference has been modified.
5. Real-Time Trial Balance: Generates instantaneous trial balances and checks mathematical parity across multiple currencies (fiat USD, EUR, GBP, and crypto SAT, BTC).
6. Zero External Dependencies: Pure Python standard library with zero runtime dependencies.

## Installation

```bash
pip install ledger-double-entry
```

Or install locally in editable mode:

```bash
git clone https://github.com/aipd506/ledger-double-entry.git
cd ledger-double-entry
pip install -e .
```

## Quick Start

### 1. Initialize Core Banking Ledger

```bash
ledgercore init --currency USD
```

Initializes standard banking accounts:
- `1000` Cash & Central Bank Reserves (Asset)
- `1100` Customer Loans & Advances (Asset)
- `2000` Customer Demand Deposits (Liability)
- `3000` Common Equity Tier 1 Capital (Equity)
- `4000` Interest & Fee Income (Revenue)
- `5000` Operational Expense (Expense)

### 2. Add an Account

```bash
ledgercore account add 1020 "Treasury Bills & Securities" asset
```

### 3. Post a Balanced Double-Entry Transaction

```bash
ledgercore post --desc "Customer deposit from external wire" \
  --debit 1000 50000.00 \
  --credit 2000 50000.00
```

Output:
```text
Transaction posted successfully!
  Sequence:    #1
  TX ID:       f8eae501-a98a-4a9e-808c-c2574aa55f3a
  Hash:        13617d1a0357f000...
  Debit:       [1000] 50000.00 USD
  Credit:      [2000] 50000.00 USD
```

### 4. Check Account Balances

```bash
ledgercore balance 1000
```

Output:
```text
Account [1000] Operating Cash & Central Bank Reserves: 50000.00 USD (Debit Normal)
```

### 5. Generate Trial Balance

```bash
ledgercore trial-balance
```

Output:
```text
================================================================================
TRIAL BALANCE
================================================================================
ACCOUNT    NAME                         TYPE             DEBITS      CREDITS          NET
--------------------------------------------------------------------------------
1000       Operating Cash & Central B   asset          50000.00         0.00     50000.00
2000       Customer Demand Deposits     liability          0.00     50000.00     50000.00
================================================================================
GRAND TOTALS:
  USD: Total Debits=50000.00, Total Credits=50000.00 -> BALANCED
================================================================================
```

### 6. Cryptographic Audit Verification

```bash
ledgercore audit
```

Output:
```text
Audit Status:    PASSED
Entries Verified: 1
```

## Python API Usage

```python
from decimal import Decimal
from ledger_double_entry import Ledger, AccountType, Posting, PostingDirection

ledger = Ledger()
ledger.add_account("1000", "Operating Cash", AccountType.ASSET)
ledger.add_account("2000", "Customer Deposits", AccountType.LIABILITY)

# Post transaction
postings = [
    Posting("1000", PostingDirection.DEBIT, Decimal("10000.00")),
    Posting("2000", PostingDirection.CREDIT, Decimal("10000.00")),
]
entry = ledger.post_transaction("Customer wire deposit", postings)

# Verify audit trail
audit_res = ledger.audit()
assert audit_res.is_valid
```

## License

Apache-2.0
