"""
Reddit database query tool (read-only).

Provides CLI access to query reddit_posts and reddit_comments tables.
Strictly SELECT-only — no INSERT, UPDATE, or DELETE operations.

Usage:
    python query_db.py subreddits
    python query_db.py posts [--subreddit NAME] [--author NAME] [--search KEYWORD]
                             [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                             [--limit N] [--offset N] [--id ID] [--full]
    python query_db.py comments --post POST_ID [--limit N] [--offset N] [--full]
    python query_db.py stats [--subreddit NAME]
"""

import os
import sys
import json
import argparse

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_db_connection():
    """Create a read-only database connection using .env config."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_READONLY_USER", "hub_readonly"),
        password=os.getenv("POSTGRES_READONLY_PASSWORD", "hub_password"),
        dbname=os.getenv("POSTGRES_DB", "financial_hub"),
    )
    conn.set_session(readonly=True, autocommit=True)
    return conn


# ── Output formatting ─────────────────────────────────────────────────────────

ITEM_SEPARATOR = "\n" + "=" * 60 + "\n"


def format_post(row: dict, full: bool = False) -> str:
    title    = row.get("title") or "(无标题)"
    author   = row.get("author") or ""
    sub      = row.get("subreddit") or ""
    score    = row.get("score") or 0
    n_cmt    = row.get("num_comments") or 0
    created  = row.get("created_iso") or ""
    link     = row.get("permalink") or ""
    flair    = row.get("flair") or ""
    db_id    = row.get("id") or ""
    file_p   = row.get("file_path") or ""

    lines = [
        f"ID: {db_id}",
        f"标题: {title}",
        f"来源: reddit",
        f"子版块: r/{sub}",
        f"作者: u/{author}",
        f"评分: {score}  评论数: {n_cmt}",
        f"发布时间: {created}",
        f"永久链接: {link}",
    ]
    if flair:
        lines.append(f"Flair: {flair}")
    if file_p:
        lines.append(f"本地文件: {file_p}")

    body = row.get("selftext") or ""
    if full:
        lines.append("")
        lines.append("--- 正文 ---")
        lines.append(body if body else "(无正文 / 链接帖)")
    else:
        preview = body[:200].replace("\n", " ") if body else "(无正文 / 链接帖)"
        if len(body) > 200:
            preview += "..."
        lines.append(f"正文预览: {preview}")

    return "\n".join(lines)


def format_comment(row: dict, full: bool = False) -> str:
    author  = row.get("author") or ""
    score   = row.get("score") or 0
    created = row.get("created_iso") or ""
    depth   = row.get("depth") or 0
    c_id    = row.get("comment_id") or ""
    db_id   = row.get("id") or ""
    link    = row.get("permalink") or ""

    lines = [
        f"ID: {db_id}  comment_id: {c_id}",
        f"作者: u/{author}  评分: {score}  深度: {depth}",
        f"时间: {created}",
        f"链接: {link}",
    ]

    body = row.get("body") or ""
    if full:
        lines.append("")
        lines.append("--- 内容 ---")
        lines.append(body if body else "(无内容)")
    else:
        preview = body[:200].replace("\n", " ") if body else "(无内容)"
        if len(body) > 200:
            preview += "..."
        lines.append(f"内容预览: {preview}")

    return "\n".join(lines)


# ── Query commands ────────────────────────────────────────────────────────────

def cmd_subreddits(conn, args):
    """List all subreddits in the database."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT subreddit,
                   COUNT(*) AS post_count,
                   MIN(created_iso) AS earliest,
                   MAX(created_iso) AS latest
            FROM reddit_posts
            GROUP BY subreddit
            ORDER BY post_count DESC
        """)
        rows = cur.fetchall()

    if not rows:
        print("数据库中没有任何帖子。")
        return

    print(f"共 {len(rows)} 个子版块:\n")
    for r in rows:
        print(f"  r/{r['subreddit']}: {r['post_count']} 帖  "
              f"(最早: {r['earliest'] or 'N/A'}, 最新: {r['latest'] or 'N/A'})")


def cmd_posts(conn, args):
    """Query posts with optional filters."""
    conditions = []
    params = []

    if args.subreddit:
        conditions.append("subreddit = %s")
        params.append(args.subreddit.lstrip("r/"))

    if args.author:
        conditions.append("author = %s")
        params.append(args.author.lstrip("u/"))

    if args.search:
        conditions.append("(title ILIKE %s OR selftext ILIKE %s)")
        pattern = f"%{args.search}%"
        params.extend([pattern, pattern])

    if args.since:
        conditions.append("created_iso >= %s")
        params.append(args.since)

    if args.until:
        conditions.append("created_iso <= %s")
        params.append(args.until + "T23:59:59Z")

    if args.id:
        conditions.append("id = %s")
        params.append(args.id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    limit  = min(args.limit, 500)
    offset = args.offset

    sql = f"""
        SELECT *
        FROM reddit_posts
        {where}
        ORDER BY created_utc DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        print("没有找到匹配的帖子。")
        return

    count_sql = f"SELECT COUNT(*) FROM reddit_posts {where}"
    with conn.cursor() as cur:
        cur.execute(count_sql, params[:-2])
        total = cur.fetchone()[0]

    print(f"查询结果: {len(rows)} 条 (共 {total} 条匹配, offset={offset}, limit={limit})\n")
    print(ITEM_SEPARATOR.join(format_post(r, full=args.full) for r in rows))


def cmd_comments(conn, args):
    """Query comments for a post."""
    if not args.post:
        print("请用 --post POST_ID 指定帖子 ID。", file=sys.stderr)
        sys.exit(1)

    limit  = min(args.limit, 500)
    offset = args.offset

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM reddit_comments
            WHERE post_id = %s
            ORDER BY created_utc ASC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (args.post, limit, offset),
        )
        rows = cur.fetchall()

    if not rows:
        print(f"帖子 {args.post} 没有存储任何评论。")
        return

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM reddit_comments WHERE post_id = %s", (args.post,))
        total = cur.fetchone()[0]

    print(f"帖子 {args.post} 的评论: {len(rows)} 条 (共 {total} 条, offset={offset}, limit={limit})\n")
    print(ITEM_SEPARATOR.join(format_comment(r, full=args.full) for r in rows))


def cmd_stats(conn, args):
    """Show statistics overview."""
    sub_filter = ""
    params = []
    if args.subreddit:
        sub_filter = "WHERE subreddit = %s"
        params = [args.subreddit.lstrip("r/")]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM reddit_posts {sub_filter}", params)
        total_posts = cur.fetchone()["cnt"]

        cur.execute(f"""
            SELECT COUNT(DISTINCT subreddit) AS cnt FROM reddit_posts {sub_filter}
        """, params)
        total_subs = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM reddit_comments")
        total_comments = cur.fetchone()["cnt"]

        cur.execute(f"""
            SELECT MIN(created_iso) AS earliest, MAX(created_iso) AS latest
            FROM reddit_posts {sub_filter}
        """, params)
        date_row = cur.fetchone()

    header = "统计概览"
    if args.subreddit:
        header += f" (子版块: r/{args.subreddit.lstrip('r/')})"

    lines = [
        header,
        f"子版块数: {total_subs}",
        f"帖子总数: {total_posts}",
        f"评论总数: {total_comments}",
        f"最早帖子: {date_row['earliest'] or 'N/A'}",
        f"最新帖子: {date_row['latest'] or 'N/A'}",
    ]
    print("\n".join(lines))


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reddit 数据库只读查询工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # subreddits
    subparsers.add_parser("subreddits", help="列出数据库中所有子版块")

    # posts
    p_posts = subparsers.add_parser("posts", help="查询帖子")
    p_posts.add_argument("--subreddit", type=str, default=None, help="按子版块过滤 (e.g. python)")
    p_posts.add_argument("--author",    type=str, default=None, help="按作者过滤 (e.g. u/someone)")
    p_posts.add_argument("--search",    type=str, default=None, help="按关键词搜索标题和正文")
    p_posts.add_argument("--since",     type=str, default=None, help="起始日期 (含), 格式 YYYY-MM-DD")
    p_posts.add_argument("--until",     type=str, default=None, help="截止日期 (含), 格式 YYYY-MM-DD")
    p_posts.add_argument("--limit",     type=int, default=20,   help="返回条数上限 (默认 20, 最大 500)")
    p_posts.add_argument("--offset",    type=int, default=0,    help="跳过前 N 条 (分页用)")
    p_posts.add_argument("--id",        type=int, default=None, help="按数据库 ID 精确查询单条")
    p_posts.add_argument("--full",      action="store_true",    help="显示完整正文 (默认只显示预览)")

    # comments
    p_cmt = subparsers.add_parser("comments", help="查询某帖的评论")
    p_cmt.add_argument("--post",   type=str, required=True, help="帖子的 Reddit post_id (e.g. abc123)")
    p_cmt.add_argument("--limit",  type=int, default=50,    help="返回条数上限 (默认 50, 最大 500)")
    p_cmt.add_argument("--offset", type=int, default=0,     help="跳过前 N 条 (分页用)")
    p_cmt.add_argument("--full",   action="store_true",     help="显示完整评论内容")

    # stats
    p_stats = subparsers.add_parser("stats", help="查看统计信息")
    p_stats.add_argument("--subreddit", type=str, default=None, help="按子版块过滤统计")

    args = parser.parse_args()
    conn = get_db_connection()
    try:
        if args.command == "subreddits":
            cmd_subreddits(conn, args)
        elif args.command == "posts":
            cmd_posts(conn, args)
        elif args.command == "comments":
            cmd_comments(conn, args)
        elif args.command == "stats":
            cmd_stats(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
