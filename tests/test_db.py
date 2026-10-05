"""The database settings resolve as documented. Nothing connects to Postgres."""
import backend.db as db

NAMES = ("POSTGRES_DBNAME", "POSTGRES_USER", "POSTGRES_PASSWORD",
         "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT")


def connect_kwargs(monkeypatch, env):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    captured = {}
    monkeypatch.setattr(db.psycopg2, "connect", lambda **kwargs: captured.update(kwargs) or "connection")
    assert db.get_conn() == "connection"
    return captured


def test_documented_names_are_used(monkeypatch):
    kwargs = connect_kwargs(monkeypatch, {
        "DB_NAME": "atlas", "DB_USER": "atlas_user", "DB_PASSWORD": "secret",
        "DB_HOST": "db.internal", "DB_PORT": "6543",
    })
    assert kwargs == {"dbname": "atlas", "user": "atlas_user", "password": "secret",
                      "host": "db.internal", "port": 6543}


def test_older_names_take_precedence_for_existing_setups(monkeypatch):
    kwargs = connect_kwargs(monkeypatch, {
        "POSTGRES_DBNAME": "old_db", "POSTGRES_USER": "old_user", "POSTGRES_PASSWORD": "old_pw",
        "DB_NAME": "atlas", "DB_USER": "atlas_user", "DB_PASSWORD": "CHANGE_ME",
    })
    assert (kwargs["dbname"], kwargs["user"], kwargs["password"]) == ("old_db", "old_user", "old_pw")


def test_defaults_point_at_a_local_database(monkeypatch):
    kwargs = connect_kwargs(monkeypatch, {})
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 5432
    assert kwargs["dbname"] == "atlas"
