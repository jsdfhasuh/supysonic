import os
import sqlite3
import tempfile
import unittest
import importlib


migration20260502 = importlib.import_module("supysonic.schema.migration.sqlite.20260502")


class SqliteMigration20260502TestCase(unittest.TestCase):
    def test_adds_real_artist_foreign_key_constraint(self):
        fd, db_path = tempfile.mkstemp()
        os.close(fd)

        try:
            with sqlite3.connect(db_path) as connection:
                cursor = connection.cursor()
                cursor.execute("CREATE TABLE artist (id CHAR(36) PRIMARY KEY, name VARCHAR(256) NOT NULL)")
                cursor.execute("CREATE TABLE album (id CHAR(36) PRIMARY KEY, name VARCHAR(256) NOT NULL, artist_id CHAR(36) NOT NULL REFERENCES artist)")
                cursor.execute("CREATE TABLE track (id CHAR(36) PRIMARY KEY)")
                cursor.execute("CREATE TABLE user (id CHAR(36) PRIMARY KEY)")
                connection.commit()

            migration20260502.apply({"database": db_path})

            with sqlite3.connect(db_path) as connection:
                foreign_keys = connection.execute("PRAGMA foreign_key_list(artist)").fetchall()

            self.assertTrue(
                any(
                    row[2] == "artist" and row[3] == "real_artist_id" and row[4] == "id"
                    for row in foreign_keys
                )
            )
        finally:
            os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
