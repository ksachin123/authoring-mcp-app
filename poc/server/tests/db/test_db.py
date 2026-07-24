from research_authoring.db.connection import create_db


def test_create_db_creates_all_six_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = create_db(str(db_path))

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [row["name"] for row in rows]

    assert table_names == [
        "artefacts",
        "audit_log",
        "claims",
        "report_sections",
        "reports",
        "sources",
    ]
    conn.close()
