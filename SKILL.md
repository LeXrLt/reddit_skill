---
name: reddit-query
description: Query Reddit posts and comments stored in the local PostgreSQL database using natural language. Search by subreddit, author, keyword, or date range; list subreddits; view comments; and get statistics. Read-only — no data modification.
metadata:
  openclaw:
    emoji: "🔎"
    requires:
      bins:
        - python3
---

# Reddit Database Query Skill

This skill answers natural-language questions about Reddit posts and comments that have been previously crawled and stored in a PostgreSQL database (`reddit_posts` and `reddit_comments` tables).

**This skill is strictly read-only. It never inserts, updates, or deletes any data.**

## When to use

Use this skill when the user wants to:
- Read or search Reddit posts from the database
- List subreddits that have been crawled
- Find posts by subreddit, author, keyword, or date range
- View the full text of a specific post
- Query comments for a post
- Get statistics on crawled Reddit data

Do **NOT** use this skill when the user wants to crawl/download new content from Reddit (that is the crawler workflow in `main.py`).

If the database is not yet set up (no `.venv/` or `.env`, or connection errors),
run the **`reddit-setup`** skill (`SKILL_SETUP.md`) first.

## How to use

Translate the user's natural-language request into one of the commands below.
All commands share the same base invocation:

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py <command> [options]
```

### 1. List subreddits

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py subreddits
```

Returns all crawled subreddits with post counts and date ranges.

### 2. Query posts

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py posts [options]
```

Options:
- `--subreddit NAME` — Filter by subreddit (e.g. `python` or `r/python`)
- `--author NAME` — Filter by author username (e.g. `someone` or `u/someone`)
- `--search KEYWORD` — Search in title and post body (case-insensitive)
- `--since YYYY-MM-DD` — Start date (inclusive)
- `--until YYYY-MM-DD` — End date (inclusive)
- `--limit N` — Max results (default: 20, max: 500)
- `--offset N` — Skip first N results (for pagination)
- `--id ID` — Fetch a single post by its database ID
- `--full` — Show complete post body instead of preview

### 3. Query comments

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py comments --post POST_ID [options]
```

Options:
- `--post POST_ID` — Reddit post ID (required, e.g. `abc123`)
- `--limit N` — Max results (default: 50, max: 500)
- `--offset N` — Skip first N results
- `--full` — Show complete comment body instead of preview

### 4. View statistics

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py stats [--subreddit NAME]
```

Returns total post count, comment count, subreddit count, and date ranges.

## Output format

Each post is output in a stable structured format:

```
ID: <id>
标题: <title>
来源: reddit
子版块: r/<subreddit>
作者: u/<author>
评分: <score>  评论数: <num_comments>
发布时间: <datetime>
永久链接: <url>
Flair: <flair>              (if present)
本地文件: <path>            (if present)
正文预览: <first 200 chars> (default)
--- 正文 ---                (with --full flag)
<full body text>
```

Posts and comments are separated by `============` lines.

## Examples

User says: "数据库里抓了哪些子版块"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py subreddits`

User says: "查看 r/python 最近 10 篇帖子"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py posts --subreddit python --limit 10`

User says: "搜索关于 fastapi 的帖子"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py posts --search fastapi`

User says: "查 u/someuser 发布的所有帖子"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py posts --author someuser`

User says: "看 2025 年 1 月到 3 月 r/MachineLearning 的帖子"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py posts --subreddit MachineLearning --since 2025-01-01 --until 2025-03-31`

User says: "看看 ID 为 42 的帖子全文"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py posts --id 42 --full`

User says: "查看帖子 abc123 的评论"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py comments --post abc123`

User says: "数据库里有多少 Reddit 内容"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py stats`

User says: "r/golang 子版块的统计数据"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py stats --subreddit golang`

## Setup

This skill uses the virtual environment at `{baseDir}/.venv`.
If the environment is missing, run the `reddit-setup` skill (`SKILL_SETUP.md`).
Database connection is configured via `{baseDir}/.env` (read-only user).
