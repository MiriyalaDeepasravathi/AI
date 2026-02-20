import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    created_at: str


@dataclass
class Profile:
    id: int
    user_id: int

    full_name: str
    age: int
    gender: str
    height_cm: Optional[int]
    marital_status: str
    location: str

    highest_education: str
    occupation: str
    income_range: str

    smoking: str
    drinking: str
    medical_conditions: str
    fitness_level: str

    pref_age_min: int
    pref_age_max: int
    pref_location: str
    pref_education_level: str

    image_filename: Optional[str]
    created_at: str
    updated_at: str


def _dict_factory(cursor: sqlite3.Cursor, row: Tuple[Any, ...]) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    """Create tables if they don't exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,

                full_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                height_cm INTEGER,
                marital_status TEXT NOT NULL,
                location TEXT NOT NULL,

                highest_education TEXT NOT NULL,
                occupation TEXT NOT NULL,
                income_range TEXT NOT NULL,

                smoking TEXT NOT NULL,
                drinking TEXT NOT NULL,
                medical_conditions TEXT NOT NULL,
                fitness_level TEXT NOT NULL,

                pref_age_min INTEGER NOT NULL,
                pref_age_max INTEGER NOT NULL,
                pref_location TEXT NOT NULL,
                pref_education_level TEXT NOT NULL,

                image_filename TEXT,

                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),

                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_profiles_location ON profiles(location);
            CREATE INDEX IF NOT EXISTS idx_profiles_gender ON profiles(gender);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    # PRAGMA table_info returns columns: cid, name, type, notnull, dflt_value, pk
    return [r["name"] for r in rows]


def migrate_db(db_path: str) -> None:
    """Apply safe, additive-only migrations.

    Rules:
    - NEVER rename existing columns.
    - Only add missing columns if required by newer code.
    - Use ALTER TABLE ... ADD COLUMN.

    This keeps existing `database/matrimony.db` consistent without resets.
    """
    conn = get_connection(db_path)
    try:
        # 1) Additive column migrations
        profile_cols = set(_table_columns(conn, "profiles"))
        if "is_verified" not in profile_cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0;")

        message_cols = set(_table_columns(conn, "messages")) if "messages" in {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()} else set()
        if message_cols and "attachment_filename" not in message_cols:
            conn.execute("ALTER TABLE messages ADD COLUMN attachment_filename TEXT;")

        # 2) New tables (additive only)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                responded_at TEXT,
                UNIQUE(from_user_id, to_user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_interests_from_to ON interests(from_user_id, to_user_id);
            CREATE INDEX IF NOT EXISTS idx_interests_to_status ON interests(to_user_id, status);

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                body TEXT,
                attachment_filename TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_messages_pair_time
            ON messages(from_user_id, to_user_id, created_at);
            """
        )

        # 3) One-time safety cleanup:
        # Remove duplicate non-accepted interests for the same unordered pair,
        # keeping the smallest id. Never delete accepted interests.
        # NOTE: This does not modify existing accepted rows.
        conn.execute(
            """
            DELETE FROM interests
            WHERE status != 'accepted'
              AND id NOT IN (
                SELECT MIN(id)
                FROM interests
                WHERE status != 'accepted'
                GROUP BY
                  CASE WHEN from_user_id < to_user_id THEN from_user_id ELSE to_user_id END,
                  CASE WHEN from_user_id < to_user_id THEN to_user_id ELSE from_user_id END
              );
            """
        )

        conn.commit()
    finally:
        conn.close()


def list_users(db_path: str) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT id, email, created_at FROM users ORDER BY id").fetchall()
    finally:
        conn.close()


def list_profiles(db_path: str) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM profiles ORDER BY id").fetchall()
    finally:
        conn.close()





def get_user_by_email(db_path: str, email: str) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()


def get_user_by_id(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()


def create_user(db_path: str, email: str, password_hash: str) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, password_hash)
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def update_user_password_hash(db_path: str, email: str, password_hash: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (password_hash, email),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_profile(db_path: str, user_id: int, data: Dict[str, Any]) -> None:
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

        fields = [
            "full_name",
            "age",
            "gender",
            "height_cm",
            "marital_status",
            "location",
            "highest_education",
            "occupation",
            "income_range",
            "smoking",
            "drinking",
            "medical_conditions",
            "fitness_level",
            "pref_age_min",
            "pref_age_max",
            "pref_location",
            "pref_education_level",
            "image_filename",
        ]

        values = [data.get(f) for f in fields]

        if existing:
            set_clause = ", ".join([f"{f} = ?" for f in fields])
            conn.execute(
                f"UPDATE profiles SET {set_clause}, updated_at = datetime('now') WHERE user_id = ?",
                (*values, user_id),
            )
        else:
            cols = ", ".join(["user_id"] + fields)
            placeholders = ", ".join(["?"] * (1 + len(fields)))
            conn.execute(
                f"INSERT INTO profiles ({cols}) VALUES ({placeholders})",
                (user_id, *values),
            )

        conn.commit()
    finally:
        conn.close()


def update_profile_image(db_path: str, user_id: int, image_filename: Optional[str]) -> bool:
    """Update only the profile image filename.

    Returns True if a profile row existed and was updated.
    """
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE profiles SET image_filename = ?, updated_at = datetime('now') WHERE user_id = ?",
            (image_filename, user_id),
        )
        conn.commit()
        return bool(cur.rowcount)
    finally:
        conn.close()


def get_profile_by_user_id(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    finally:
        conn.close()


def list_other_profiles(db_path: str, current_user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute(
            "SELECT * FROM profiles WHERE user_id != ? ORDER BY updated_at DESC",
            (current_user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_profile_by_id(db_path: str, profile_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    finally:
        conn.close()


def set_profile_verified(db_path: str, profile_id: int, value: bool) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE profiles SET is_verified = ? WHERE id = ?",
            (1 if value else 0, profile_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_message(db_path: str, from_user_id: int, to_user_id: int, body: str) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO messages (from_user_id, to_user_id, body) VALUES (?, ?, ?)",
            (from_user_id, to_user_id, body),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def insert_message_v2(
    db_path: str,
    from_user_id: int,
    to_user_id: int,
    body: str | None,
    attachment_filename: str | None,
) -> int:
    conn = get_connection(db_path)
    try:
        # Back-compat: existing SQLite may have `messages.body TEXT NOT NULL`.
        # Use empty string to satisfy NOT NULL when sending attachment-only.
        safe_body = body if body is not None else ""
        cur = conn.execute(
            """
            INSERT INTO messages (from_user_id, to_user_id, body, attachment_filename)
            VALUES (?, ?, ?, ?)
            """,
            (from_user_id, to_user_id, safe_body, attachment_filename),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_messages_between_users(
    db_path: str,
    user_a_id: int,
    user_b_id: int,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        return conn.execute(
            """
            SELECT *
            FROM messages
            WHERE (from_user_id = ? AND to_user_id = ?)
               OR (from_user_id = ? AND to_user_id = ?)
            ORDER BY datetime(created_at) ASC
            LIMIT ?
            """,
            (user_a_id, user_b_id, user_b_id, user_a_id, limit),
        ).fetchall()
    finally:
        conn.close()


def create_interest(db_path: str, from_user_id: int, to_user_id: int) -> Optional[int]:
    """Create an interest request.

    Returns the new interest id, or existing interest id if already exists.
    """
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM interests WHERE from_user_id = ? AND to_user_id = ?",
            (from_user_id, to_user_id),
        ).fetchone()
        if existing:
            return int(existing["id"])

        cur = conn.execute(
            "INSERT INTO interests (from_user_id, to_user_id, status) VALUES (?, ?, 'pending')",
            (from_user_id, to_user_id),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        # Unique constraint hit in a race: treat as already created.
        row = conn.execute(
            "SELECT id FROM interests WHERE from_user_id = ? AND to_user_id = ?",
            (from_user_id, to_user_id),
        ).fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def get_interest_status(db_path: str, user_a_id: int, user_b_id: int) -> Optional[Dict[str, Any]]:
    """Get interest status between two users.

    Returns a dict containing:
    - `status`: pending/accepted/rejected
    - `direction`: 'outgoing' if a->b exists, 'incoming' if b->a exists
    - `interest`: the raw interest row
    """
    conn = get_connection(db_path)
    try:
        outgoing = conn.execute(
            "SELECT * FROM interests WHERE from_user_id = ? AND to_user_id = ?",
            (user_a_id, user_b_id),
        ).fetchone()
        if outgoing:
            return {"status": outgoing["status"], "direction": "outgoing", "interest": outgoing}

        incoming = conn.execute(
            "SELECT * FROM interests WHERE from_user_id = ? AND to_user_id = ?",
            (user_b_id, user_a_id),
        ).fetchone()
        if incoming:
            return {"status": incoming["status"], "direction": "incoming", "interest": incoming}

        return None
    finally:
        conn.close()


def get_interest_between_users(db_path: str, user_a_id: int, user_b_id: int) -> Optional[Dict[str, Any]]:
    """Return the interest row between two users, regardless of direction.

    Ensures we can enforce ONE interest per unordered pair.
    """
    conn = get_connection(db_path)
    try:
        return conn.execute(
            """
            SELECT * FROM interests
            WHERE (from_user_id = ? AND to_user_id = ?)
               OR (from_user_id = ? AND to_user_id = ?)
            ORDER BY id ASC
            LIMIT 1
            """,
            (user_a_id, user_b_id, user_b_id, user_a_id),
        ).fetchone()
    finally:
        conn.close()


def respond_to_interest(db_path: str, interest_id: int, action: str) -> None:
    if action not in {"accepted", "rejected"}:
        raise ValueError("Invalid interest response action")

    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE interests SET status = ?, responded_at = datetime('now') WHERE id = ?",
            (action, interest_id),
        )
        conn.commit()
    finally:
        conn.close()
