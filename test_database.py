"""Step 3 - Database tests.

Loads the MariaDB dump (DataSources/restaurant_conversational_agent_db.sql)
into an in-memory SQLite database, converting the MySQL-only DDL, then
verifies schema, row counts, keys, foreign keys, data validity and that the
application parser (retrieve.py) reads the same data.

Run:  python test_database.py
"""

from __future__ import annotations

import re
import sqlite3
import unittest
from pathlib import Path

from retrieve import DATA_DIR, SQL_DUMP_PATH, load_policy_lines, load_structured_data

ENTITY_TABLES = ("allergen", "dietary_type", "ingredient", "menu_item", "restaurant_policy")
JOIN_TABLES = ("item_allergen", "item_dietary", "menu_ingredient")
ALL_TABLES = ENTITY_TABLES + JOIN_TABLES

KNOWLEDGE_FILES = (
    "Restaurant Policies.txt",
    "Discount Policies.txt",
    "Restaurant FAQs.txt",
    "Allergy Guidelines.txt",
    "Restaurant Descriptions.txt",
    "Customer Reviews.txt",
)


def mysql_dump_to_sqlite(sql_text: str) -> str:
    """Convert the MySQL dump DDL/DML into SQLite-executable SQL."""
    sql_text = re.sub(r"/\*!\d+.*?\*/", "", sql_text, flags=re.S)
    sql_text = re.sub(r"^\s*(SET|START TRANSACTION|COMMIT)\b.*$", "", sql_text, flags=re.M)

    primary_keys = {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"ALTER TABLE `(\w+)`\s+ADD PRIMARY KEY \(([^)]+)\)", sql_text
        )
    }
    foreign_keys: dict[str, list[str]] = {}
    for block in re.finditer(r"ALTER TABLE `(\w+)`\s+(.*?);", sql_text, flags=re.S):
        table, body = block.group(1), block.group(2)
        for column, ref_table, ref_column in re.findall(
            r"FOREIGN KEY \(`(\w+)`\) REFERENCES `(\w+)` \(`(\w+)`\)", body
        ):
            foreign_keys.setdefault(table, []).append(
                f"  FOREIGN KEY (`{column}`) REFERENCES `{ref_table}` (`{ref_column}`)"
            )

    sql_text = re.sub(r"ALTER TABLE .*?;", "", sql_text, flags=re.S)
    sql_text = re.sub(r"\)\s*ENGINE=[^;]+;", ");", sql_text)

    for table in primary_keys:
        pattern = re.compile(
            rf"(CREATE TABLE `{re.escape(table)}`\s*\()(.*?)(\);)", re.S
        )

        def add_constraints(match: re.Match[str]) -> str:
            constraints = [f"  PRIMARY KEY ({primary_keys[table]})"]
            constraints.extend(foreign_keys.get(table, []))
            body = match.group(2).rstrip()
            return match.group(1) + body + ",\n" + ",\n".join(constraints) + "\n" + match.group(3)

        sql_text, count = pattern.subn(add_constraints, sql_text, count=1)
        if count != 1:
            raise ValueError(f"could not inject constraints into CREATE TABLE {table}")
    return sql_text


def load_sqlite_db() -> sqlite3.Connection:
    sql_text = mysql_dump_to_sqlite(SQL_DUMP_PATH.read_text(encoding="utf-8"))
    connection = sqlite3.connect(":memory:")
    connection.executescript(sql_text)
    return connection


class DatabaseTestCase(unittest.TestCase):
    db: sqlite3.Connection
    data: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = load_sqlite_db()
        cls.data = load_structured_data()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close()

    def query_one(self, sql: str) -> object:
        return self.db.execute(sql).fetchone()[0]

    def test_sql_dump_exists(self) -> None:
        self.assertTrue(SQL_DUMP_PATH.exists(), f"Missing SQL dump: {SQL_DUMP_PATH}")

    def test_dump_loads_into_sqlite(self) -> None:
        tables = {
            row[0]
            for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertEqual(tables, set(ALL_TABLES))

    def test_integrity_check(self) -> None:
        self.assertEqual(self.query_one("PRAGMA integrity_check"), "ok")

    def test_foreign_key_check_clean(self) -> None:
        violations = self.db.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(violations, [], f"foreign key violations: {violations}")

    def test_entity_tables_have_100_rows(self) -> None:
        for table in ENTITY_TABLES:
            self.assertEqual(self.query_one(f"SELECT COUNT(*) FROM {table}"), 100)

    def test_join_tables_not_empty(self) -> None:
        for table in JOIN_TABLES:
            self.assertGreater(self.query_one(f"SELECT COUNT(*) FROM {table}"), 0)

    def test_primary_keys_unique(self) -> None:
        keys = {
            "allergen": "allergen_id",
            "dietary_type": "dietary_id",
            "ingredient": "ingredient_id",
            "menu_item": "item_id",
            "restaurant_policy": "policy_id",
            "item_allergen": "item_id, allergen_id",
            "item_dietary": "item_id, dietary_id",
            "menu_ingredient": "item_id, ingredient_id",
        }
        for table, columns in keys.items():
            total = self.query_one(f"SELECT COUNT(*) FROM {table}")
            distinct = self.query_one(
                f"SELECT COUNT(*) FROM (SELECT DISTINCT {columns} FROM {table})"
            )
            self.assertEqual(total, distinct, f"{table} has duplicate primary keys")

    def test_primary_key_constraints_defined(self) -> None:
        expected = {
            "allergen": ["allergen_id"],
            "dietary_type": ["dietary_id"],
            "ingredient": ["ingredient_id"],
            "menu_item": ["item_id"],
            "restaurant_policy": ["policy_id"],
            "item_allergen": ["item_id", "allergen_id"],
            "item_dietary": ["item_id", "dietary_id"],
            "menu_ingredient": ["item_id", "ingredient_id"],
        }
        for table, columns in expected.items():
            pk_columns = sorted(
                row[1]
                for row in self.db.execute(f"PRAGMA table_info({table})")
                if row[5] > 0
            )
            self.assertEqual(pk_columns, sorted(columns), f"{table} primary key wrong")

    def test_foreign_key_constraints_defined(self) -> None:
        expected = {
            "item_allergen": {("item_id", "menu_item", "item_id"), ("allergen_id", "allergen", "allergen_id")},
            "item_dietary": {("item_id", "menu_item", "item_id"), ("dietary_id", "dietary_type", "dietary_id")},
            "menu_ingredient": {("item_id", "menu_item", "item_id"), ("ingredient_id", "ingredient", "ingredient_id")},
        }
        for table, want in expected.items():
            got = {
                (row[3], row[2], row[4])
                for row in self.db.execute(f"PRAGMA foreign_key_list({table})")
            }
            self.assertEqual(got, want, f"{table} foreign keys wrong")

    def test_menu_item_fields_valid(self) -> None:
        bad = self.db.execute(
            """
            SELECT item_id FROM menu_item
            WHERE item_name IS NULL OR TRIM(item_name) = ''
               OR category IS NULL OR TRIM(category) = ''
               OR description IS NULL OR TRIM(description) = ''
               OR price IS NULL OR price <= 0
               OR calories IS NULL OR calories < 0
            """
        ).fetchall()
        self.assertEqual(bad, [], f"invalid menu_item rows: {bad}")

    def test_policy_fields_valid(self) -> None:
        bad = self.db.execute(
            """
            SELECT policy_id FROM restaurant_policy
            WHERE policy_name IS NULL OR TRIM(policy_name) = ''
               OR policy_description IS NULL OR TRIM(policy_description) = ''
            """
        ).fetchall()
        self.assertEqual(bad, [], f"invalid restaurant_policy rows: {bad}")

    def test_reference_names_not_empty(self) -> None:
        for table, column in (
            ("allergen", "allergen_name"),
            ("dietary_type", "dietary_name"),
            ("ingredient", "ingredient_name"),
        ):
            empty = self.query_one(
                f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL OR TRIM({column}) = ''"
            )
            self.assertEqual(empty, 0, f"{table} has empty {column}")

    def test_every_menu_item_is_tagged(self) -> None:
        untagged = self.query_one(
            """
            SELECT COUNT(*) FROM menu_item m
            WHERE NOT EXISTS (SELECT 1 FROM item_allergen a WHERE a.item_id = m.item_id)
              AND NOT EXISTS (SELECT 1 FROM item_dietary d WHERE d.item_id = m.item_id)
            """
        )
        self.assertEqual(untagged, 0, "menu items without any allergen/dietary tag")

    def test_join_tables_reference_only_existing_items(self) -> None:
        for table in JOIN_TABLES:
            orphans = self.query_one(
                f"""
                SELECT COUNT(*) FROM {table} j
                LEFT JOIN menu_item m ON m.item_id = j.item_id
                WHERE m.item_id IS NULL
                """
            )
            self.assertEqual(orphans, 0, f"{table} references unknown menu items")

    def test_app_parser_matches_database(self) -> None:
        """retrieve.py's in-memory parse must agree with the SQL database."""
        for table in ALL_TABLES:
            parsed_rows = len(self.data["tables"][table])  # type: ignore[arg-type]
            db_rows = self.query_one(f"SELECT COUNT(*) FROM {table}")
            self.assertEqual(parsed_rows, db_rows, f"parser/DB row mismatch in {table}")

        self.assertEqual(
            len(self.data["menu_items_by_id"]),  # type: ignore[arg-type]
            self.query_one("SELECT COUNT(*) FROM menu_item"),
        )
        for item_id, allergens in self.data["item_allergens"].items():  # type: ignore[union-attr]
            db_count = self.query_one(
                f"SELECT COUNT(*) FROM item_allergen WHERE item_id = {int(item_id)}"
            )
            self.assertEqual(len(allergens), db_count, f"item {item_id} allergen mismatch")

    def test_knowledge_text_files_exist(self) -> None:
        for name in KNOWLEDGE_FILES:
            path = DATA_DIR / name
            self.assertTrue(path.exists(), f"missing knowledge file: {name}")
            self.assertGreater(
                len(path.read_text(encoding="utf-8").strip()), 0, f"{name} is empty"
            )

    def test_policy_lines_load(self) -> None:
        lines = load_policy_lines()
        self.assertGreater(len(lines), 0, "no policy lines loaded from text files")
        for label, line in lines:
            self.assertTrue(label.strip())
            self.assertTrue(line.strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
