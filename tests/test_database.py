from app.database.db import DatabaseSession


class FakeCursor:
    def __init__(self):
        self.query = None
        self.parameters = None

    def execute(self, query, parameters):
        self.query = query
        self.parameters = parameters


class FakeConnection:
    def __init__(self):
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = FakeCursor()
        return self.last_cursor


def test_postgres_session_translates_placeholders():
    connection = FakeConnection()
    session = DatabaseSession(connection, is_postgres=True)

    session.execute("SELECT * FROM tasks WHERE id = ? AND completed = ?", (4, 0))

    assert connection.last_cursor.query == (
        "SELECT * FROM tasks WHERE id = %s AND completed = %s"
    )
    assert connection.last_cursor.parameters == (4, 0)
