"""
Reddit skill — database write helpers (read-write).

Provides:
  ensure_tables(conn)            — create tables from schema.sql if not exist
  save_post(conn, post)          — upsert a reddit_posts row
  save_comments(conn, post_id, comments) — bulk-insert reddit_comments rows
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def ensure_tables(conn):
    """Execute schema.sql to create tables if they don't exist."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Schema initialized.")


def save_post(conn, post: dict, file_path: str = None) -> bool:
    """
    Upsert a reddit_posts row.

    Returns True if a new row was inserted, False if skipped (already exists).
    The file_path argument records the local Markdown file path if the post
    was previously saved via reddit-save-md.mjs.
    """
    raw = post.get("_raw", {})
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reddit_posts (
                post_id, subreddit, title, author, score, num_comments,
                created_utc, created_iso, permalink, url, is_self, over_18,
                flair, selftext, file_path, status, raw_data
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (post_id) DO NOTHING
            RETURNING id
            """,
            (
                post.get("post_id", ""),
                post.get("subreddit", ""),
                post.get("title", ""),
                post.get("author", ""),
                post.get("score", 0),
                post.get("num_comments", 0),
                post.get("created_utc"),
                post.get("created_iso"),
                post.get("permalink", ""),
                post.get("url", ""),
                post.get("is_self", False),
                post.get("over_18", False),
                post.get("flair"),
                post.get("selftext", ""),
                file_path,
                "ready",
                json.dumps(raw, ensure_ascii=False),
            ),
        )
        inserted = cur.fetchone() is not None
    conn.commit()
    return inserted


def save_comments(conn, post_id: str, comments: list) -> tuple:
    """
    Bulk-insert reddit_comments rows for the given post.

    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0
    for c in comments:
        raw = c.get("_raw", {})
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reddit_comments (
                    comment_id, post_id, parent_id, author, score,
                    created_utc, created_iso, depth, body, permalink,
                    status, raw_data
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s::jsonb
                )
                ON CONFLICT (comment_id) DO NOTHING
                RETURNING id
                """,
                (
                    c.get("comment_id", ""),
                    post_id,
                    c.get("parent_id"),
                    c.get("author", ""),
                    c.get("score", 0),
                    c.get("created_utc"),
                    c.get("created_iso"),
                    c.get("depth", 0),
                    c.get("body", ""),
                    c.get("permalink"),
                    "ready",
                    json.dumps(raw, ensure_ascii=False),
                ),
            )
            if cur.fetchone() is not None:
                inserted += 1
            else:
                skipped += 1
    conn.commit()
    return inserted, skipped
