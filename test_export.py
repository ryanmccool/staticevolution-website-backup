import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import export


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query):
        projection = re.split(r"\bFROM\b", query, maxsplit=1, flags=re.IGNORECASE)[0]
        projection = re.split(r"\bSELECT\b", projection, maxsplit=1, flags=re.IGNORECASE)[1]
        self.assert_explicit_projection(projection)
        columns = [part.strip().split(".")[-1] for part in projection.split(",")]
        return [{column: 1 if column == "id" else f"public-{column}" for column in columns}]

    @staticmethod
    def assert_explicit_projection(projection):
        if "*" in projection:
            raise AssertionError(f"Public export uses wildcard projection: {projection}")


class PublicExportBoundaryTests(unittest.TestCase):
    def test_exported_schema_omits_private_and_operational_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "staticevolution.db"
            with (
                patch.object(export, "OUTPUT", output),
                patch.object(export.psycopg, "connect", return_value=FakeConnection()),
                patch.dict(os.environ, {"DATABASE_URL": "postgresql://unused"}),
            ):
                export.main()

            connection = sqlite3.connect(output)
            schemas = {
                table: {
                    row[1]
                    for row in connection.execute(f'SELECT * FROM pragma_table_info("{table}")')
                }
                for table in export.TABLES
            }
            connection.close()

        forbidden = {
            "image",
            "import_ref",
            "is_draft",
            "is_unlisted",
            "live_timezone",
            "metadata",
            "search_document",
            "status",
            "custom_template",
        }
        for table, columns in schemas.items():
            self.assertTrue(columns, table)
            self.assertFalse(forbidden & columns, (table, forbidden & columns))
        self.assertEqual(
            schemas["blog_photo"],
            {"id", "created", "title", "alt_text", "caption", "width", "height"},
        )


if __name__ == "__main__":
    unittest.main()
