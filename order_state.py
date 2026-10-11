"""Per-session order memory for follow-up requests like "add one more".

The agent pipeline is stateless per request: each turn is answered from the
current prompt alone. A single-user chat needs one OrderState kept across
turns (streamlit stores it in st.session_state) so commands such as
"add one margherita pizza" extend the total computed in the previous turn.

Run:  python order_state.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _price(item: dict) -> float | None:
    value = item.get("price")
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class OrderState:
    """Mutable, in-place order accumulator shared across chat turns."""

    name: str = "order"
    items: list[dict] = field(default_factory=list)

    def add(self, item: dict, quantity: int = 1) -> None:
        """Add `quantity` of `item`, merging with any existing line."""
        item_id = item.get("item_id")
        price = _price(item)
        name = str(item.get("item_name") or "Unknown")
        if quantity <= 0:
            return
        for entry in self.items:
            if entry["item_id"] == item_id:
                entry["quantity"] += quantity
                return
        self.items.append(
            {"item_id": item_id, "name": name, "price": price, "quantity": quantity}
        )

    def replace(self, entries: list[tuple[dict, int]]) -> None:
        """Start a fresh order from parsed (item, quantity) pairs."""
        self.items = []
        for item, quantity in entries:
            self.add(item, quantity)

    def remove(self, item: dict) -> bool:
        """Remove the whole line for `item`; returns True if it existed."""
        item_id = item.get("item_id")
        for index, entry in enumerate(self.items):
            if entry["item_id"] == item_id:
                self.items.pop(index)
                return True
        return False

    def clear(self) -> None:
        self.items = []

    @property
    def total(self) -> float:
        return sum(
            (entry["price"] or 0) * entry["quantity"] for entry in self.items
        )

    def __bool__(self) -> bool:
        return bool(self.items)


def format_items(items: list[dict]) -> str:
    """One Markdown bullet per order line, plus the summed total."""
    lines = ["### Order total", ""]
    total = 0.0
    priced = 0
    for entry in items:
        quantity = entry.get("quantity") or 1
        name = entry.get("name") or "Unknown"
        price = entry.get("price")
        if price is None:
            lines.append(f"- {quantity} x **{name}** - price not listed")
            continue
        line_total = price * quantity
        total += line_total
        priced += 1
        lines.append(
            f"- {quantity} x **{name}** (${price:.2f} each) = ${line_total:.2f}"
        )
    lines.append("")
    if priced:
        lines.append(f"**Total: ${total:.2f}**")
        if priced < len(items):
            lines.append("")
            lines.append(
                "_Some items have no listed price, so they are not included in the total._"
            )
    else:
        lines.append("**Total unavailable** - none of those items has a listed price.")
    return "\n".join(lines)


if __name__ == "__main__":
    demo = OrderState()
    demo.add({"item_id": 31, "item_name": "Chicken Kottu", "price": 8.99}, 1)
    demo.add({"item_id": 21, "item_name": "Mushroom Soup", "price": 5.99}, 1)
    demo.add({"item_id": 61, "item_name": "Iced Tea", "price": 2.99}, 1)
    print(format_items(demo.items))
    print("\nJSON:", json.dumps(demo.items))