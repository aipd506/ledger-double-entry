"""Data models for double-entry ledger accounts, postings, and cryptographically chained journal entries."""

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Dict, List, Optional, Any


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class PostingDirection(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


@dataclass
class Account:
    id: str
    name: str
    type: AccountType
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_debit_normal(self) -> bool:
        """Assets and Expenses normally have debit balances."""
        return self.type in (AccountType.ASSET, AccountType.EXPENSE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, AccountType) else self.type,
            "currency": self.currency,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        return cls(
            id=data["id"],
            name=data["name"],
            type=AccountType(data["type"]),
            currency=data.get("currency", "USD"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Posting:
    account_id: str
    direction: PostingDirection
    amount: Decimal
    currency: str = "USD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "direction": self.direction.value if isinstance(self.direction, PostingDirection) else self.direction,
            "amount": str(self.amount),
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Posting":
        return cls(
            account_id=data["account_id"],
            direction=PostingDirection(data["direction"]),
            amount=Decimal(str(data["amount"])),
            currency=data.get("currency", "USD"),
        )


@dataclass
class JournalEntry:
    sequence: int
    prev_hash: str
    timestamp: str
    tx_id: str
    description: str
    postings: List[Posting]
    hash: str = ""

    def calculate_hash(self) -> str:
        """Compute deterministic SHA-256 hash of this journal entry."""
        postings_data = [
            f"{p.account_id}:{p.direction.value}:{p.amount}:{p.currency}"
            for p in self.postings
        ]
        raw_payload = (
            f"{self.sequence}|"
            f"{self.prev_hash}|"
            f"{self.timestamp}|"
            f"{self.tx_id}|"
            f"{self.description}|"
            f"{';'.join(postings_data)}"
        )
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp,
            "tx_id": self.tx_id,
            "description": self.description,
            "postings": [p.to_dict() for p in self.postings],
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JournalEntry":
        postings = [Posting.from_dict(p) for p in data.get("postings", [])]
        entry = cls(
            sequence=data["sequence"],
            prev_hash=data["prev_hash"],
            timestamp=data["timestamp"],
            tx_id=data["tx_id"],
            description=data["description"],
            postings=postings,
            hash=data.get("hash", ""),
        )
        if not entry.hash:
            entry.hash = entry.calculate_hash()
        return entry


@dataclass
class TrialBalanceRow:
    account_id: str
    name: str
    account_type: str
    currency: str
    total_debits: Decimal
    total_credits: Decimal
    net_balance: Decimal


@dataclass
class AuditResult:
    is_valid: bool
    entries_checked: int
    errors: List[str] = field(default_factory=list)
    broken_sequence: Optional[int] = None

    def summary(self) -> str:
        status = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"Audit Status:    {status}",
            f"Entries Verified: {self.entries_checked}",
        ]
        if self.broken_sequence is not None:
            lines.append(f"Chain Broken At: Sequence #{self.broken_sequence}")
        if self.errors:
            lines.append("Errors:")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)
