"""
Reddit crawler main execution flow.

Steps:
1. Connect to the database (config from .env).
2. Initialize schema (create tables if needed).
3. Query crawl targets filtered by source_type='reddit'.
4. For each enabled target, run a crawl cycle:
   a. notify_crawl_start
   b. Fetch posts from Reddit API
   c. Optionally fetch comments for each post
   d. Save posts and comments to database
   e. notify_crawl_end
5. Print final target state.
"""

import os
import sys
import time
import argparse
import logging

import psycopg2
from dotenv import load_dotenv
from financial_hub_postgres import FinancialHubClient

import config
import db
from scraper import fetch_subreddit_posts, fetch_thread

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

COMPONENT_NAME = config.COMPONENT_NAME


def get_db_connection():
    """Create a database connection using config."""
    return psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        dbname=config.POSTGRES_DB,
    )


def crawl_target(conn, client: FinancialHubClient, target,
                 max_posts: int = 25, fetch_comments: bool = False,
                 comment_limit: int = 100, file_path: str = None):
    """Execute one full crawl cycle for a single Reddit target."""
    print(f"\n{'─' * 50}")
    print(f"Target: [{target.id}] {target.target_name} ({target.target_identifier})")
    print(f"{'─' * 50}")

    # target_identifier is expected to be the subreddit name (e.g. "python")
    subreddit = target.target_identifier.lstrip("r/")

    # ── Step 1: notify_crawl_start ──────────────────────────────
    print("[1/4] notify_crawl_start ...")
    run = client.notify_crawl_start(
        target_id=target.id,
        component_name=COMPONENT_NAME,
        metadata={
            "trigger": "manual",
            "max_posts": max_posts,
            "fetch_comments": fetch_comments,
        },
    )
    print(f"      crawl_run id={run.id}, status=running")

    start_time = time.time()
    items_found = 0
    items_new = 0
    items_failed = 0

    try:
        # ── Step 2: Fetch posts ──────────────────────────────────
        print(f"[2/4] Fetching up to {max_posts} posts from r/{subreddit} ...")
        posts = fetch_subreddit_posts(subreddit, sort="new", limit=max_posts)
        items_found = len(posts)
        print(f"      Got {items_found} posts from API")

        # ── Step 3: Save posts (+ optional comments) ────────────
        print("[3/4] Saving posts to database ...")
        for i, post in enumerate(posts, 1):
            try:
                post_file_path = None
                if file_path:
                    post_file_path = os.path.join(
                        file_path, post["subreddit"],
                        f"{post['post_id']}.md"
                    )

                inserted = db.save_post(conn, post, file_path=post_file_path)
                if inserted:
                    items_new += 1
                    print(f"      [{i}/{items_found}] New: {post['post_id']} — {post['title'][:60]}")
                else:
                    print(f"      [{i}/{items_found}] Skipped (exists): {post['post_id']}")

                # Optionally fetch and save comments
                if fetch_comments and inserted:
                    try:
                        _, comments = fetch_thread(
                            post["post_id"],
                            comment_limit=comment_limit,
                        )
                        c_ins, c_skip = db.save_comments(conn, post["post_id"], comments)
                        print(f"        Comments: {c_ins} new, {c_skip} skipped")
                    except Exception as ce:
                        logger.warning("Failed to fetch comments for %s: %s", post["post_id"], ce)

            except Exception as e:
                items_failed += 1
                logger.error("Failed to save post %s: %s", post.get("post_id"), e)

        duration_ms = int((time.time() - start_time) * 1000)

        # ── Step 4: notify_crawl_end ─────────────────────────────
        print("[4/4] notify_crawl_end ...")
        client.notify_crawl_end(
            run_id=run.id,
            target_id=target.id,
            component_name=COMPONENT_NAME,
            success=True,
            items_found=items_found,
            items_new=items_new,
            items_failed=items_failed,
            duration_ms=duration_ms,
        )
        print(f"\n  ✓ Success: found={items_found}, new={items_new}, "
              f"failed={items_failed}, duration={duration_ms}ms")

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        client.notify_crawl_end(
            run_id=run.id,
            target_id=target.id,
            component_name=COMPONENT_NAME,
            success=False,
            error_message=str(e),
            duration_ms=duration_ms,
        )
        print(f"\n  ✗ Failed: {e} (duration={duration_ms}ms)")


def main():
    parser = argparse.ArgumentParser(description="Reddit crawler — fetch and store posts.")
    parser.add_argument(
        "-n", "--max-posts",
        type=int,
        default=25,
        help="Maximum number of posts to fetch per target (default: 25)",
    )
    parser.add_argument(
        "-c", "--fetch-comments",
        action="store_true",
        default=False,
        help="Also fetch and store comments for each new post",
    )
    parser.add_argument(
        "--comment-limit",
        type=int,
        default=100,
        help="Max comments to fetch per post when --fetch-comments is set (default: 100)",
    )
    parser.add_argument(
        "-f", "--file-path",
        type=str,
        default=None,
        help="Root directory for saving post files (default: None)",
    )
    parser.add_argument(
        "--target-id",
        type=int,
        default=None,
        help="Crawl only the specified crawl_target ID",
    )
    args = parser.parse_args()

    file_path = args.file_path
    if file_path:
        file_path = os.path.abspath(file_path)
        os.makedirs(file_path, exist_ok=True)
        print(f"Files will be saved to: {file_path}")

    conn = get_db_connection()
    try:
        db.ensure_tables(conn)

        client = FinancialHubClient(conn)

        # ── Discover targets ──────────────────────────────────────
        print("=== Discovering Reddit Targets ===")
        if args.target_id:
            target = client.get_crawl_target_by_id(args.target_id)
            if not target:
                print(f"[ERROR] 未找到 target_id={args.target_id}", file=sys.stderr)
                sys.exit(1)
            targets = [target]
        else:
            targets = client.get_crawl_targets(source_type="reddit", enabled=True)

        if not targets:
            print("No enabled reddit targets found. Exiting.")
            return

        for t in targets:
            print(f"  [{t.id}] {t.target_name} ({t.target_identifier})")

        # ── Crawl each target ─────────────────────────────────────
        for target in targets:
            crawl_target(
                conn, client, target,
                max_posts=args.max_posts,
                fetch_comments=args.fetch_comments,
                comment_limit=args.comment_limit,
                file_path=file_path,
            )

        # ── Final state ───────────────────────────────────────────
        print(f"\n{'=' * 50}")
        print("=== Final Target States ===")
        print(f"{'=' * 50}")
        for target in targets:
            t = client.get_crawl_target_by_id(target.id)
            if t:
                print(f"\n  [{t.id}] {t.target_name}")
                print(f"    last_crawl_status: {t.last_crawl_status}")
                print(f"    last_crawl_at:     {t.last_crawl_at}")
                print(f"    last_error:        {t.last_error}")
                print(f"    total_items:       {t.total_items}")

    finally:
        conn.close()
        print("\nDone.")


if __name__ == "__main__":
    main()
