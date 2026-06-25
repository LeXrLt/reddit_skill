"""
Reddit scraper — fetches posts and comments via Reddit's public JSON API.

Main entry points:
  fetch_subreddit_posts(subreddit, sort, time_filter, limit) -> list[dict]
  fetch_thread(post_id, comment_limit, max_depth) -> (post_dict, comments_list)
"""

import time
import random
import logging

import requests

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://www.reddit.com"

_session = requests.Session()
_session.headers.update({
    "User-Agent": config.USER_AGENT,
    "Accept": "application/json",
})


# ── Utilities ────────────────────────────────────────────────────────────────

def _sleep_jitter():
    lo = config.MIN_DELAY_MS / 1000.0
    hi = config.MAX_DELAY_MS / 1000.0
    time.sleep(lo + random.random() * (hi - lo))


def _to_iso(utc_seconds):
    if not utc_seconds:
        return None
    import datetime
    return datetime.datetime.utcfromtimestamp(utc_seconds).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_json(url, retries=None):
    """GET url, return parsed JSON. Retries on 429/5xx."""
    if retries is None:
        retries = config.MAX_RETRIES
    last_err = None
    for attempt in range(retries + 1):
        try:
            _sleep_jitter()
            resp = _session.get(url, timeout=config.TIMEOUT_MS / 1000.0)
            text = resp.text
            if not resp.ok:
                raise requests.HTTPError(f"HTTP {resp.status_code}: {text[:300]}")
            if text.strip().startswith("<"):
                raise ValueError("Reddit returned HTML instead of JSON. Try again later.")
            return resp.json()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            last_err = e
            msg = str(e)
            retryable = "429" in msg or "5" in msg[:10] or "Timeout" in msg
            if not retryable or attempt == retries:
                break
            backoff = 0.6 * (2 ** attempt) + random.uniform(0, 0.4)
            logger.warning("Retrying in %.1fs (attempt %d): %s", backoff, attempt + 1, e)
            time.sleep(backoff)
        except ValueError as e:
            last_err = e
            if attempt == retries:
                break
            time.sleep(0.6 * (2 ** attempt))
    raise last_err or RuntimeError(f"Request failed: {url}")


def _build_url(path, qs=None):
    """Build a Reddit JSON API URL from a path."""
    if not path.endswith(".json"):
        path = path + ".json"
    url = BASE_URL + path
    if qs:
        url += "?" + "&".join(f"{k}={v}" for k, v in qs.items())
    return url


# ── Post normalisation ────────────────────────────────────────────────────────

def _normalise_post(d):
    """Convert a Reddit post data dict to our schema shape."""
    created_utc = d.get("created_utc") or 0
    return {
        "post_id":      d.get("id", ""),
        "subreddit":    d.get("subreddit", ""),
        "title":        d.get("title", ""),
        "author":       d.get("author", ""),
        "score":        d.get("score", 0),
        "num_comments": d.get("num_comments", 0),
        "created_utc":  int(created_utc) if created_utc else None,
        "created_iso":  _to_iso(created_utc),
        "permalink":    _normalise_permalink(d.get("permalink")),
        "url":          d.get("url", ""),
        "is_self":      bool(d.get("is_self", False)),
        "over_18":      bool(d.get("over_18", False)),
        "flair":        d.get("link_flair_text") or None,
        "selftext":     d.get("selftext", ""),
        "_raw":         d,
    }


def _normalise_permalink(p):
    if not p:
        return ""
    if p.startswith("http"):
        return p
    return BASE_URL + p


# ── Comment normalisation ─────────────────────────────────────────────────────

def _parse_comments_tree(children, depth=0, max_depth=10, include_deleted=False):
    """Recursively flatten a Reddit comment tree into a list of dicts."""
    out = []
    if not isinstance(children, list):
        return out

    for node in children:
        if not node or not isinstance(node, dict):
            continue
        if node.get("kind") == "more":
            continue
        if node.get("kind") != "t1":
            continue

        d = node.get("data", {})
        author = d.get("author", "")
        body = d.get("body", "")
        is_deleted = author in ("[deleted]", "[removed]") or body in ("[deleted]", "[removed]")

        if not include_deleted and is_deleted:
            pass
        else:
            created_utc = d.get("created_utc") or 0
            out.append({
                "comment_id":  d.get("id", ""),
                "parent_id":   d.get("parent_id") or None,
                "author":      author,
                "score":       d.get("score", 0),
                "created_utc": int(created_utc) if created_utc else None,
                "created_iso": _to_iso(created_utc),
                "depth":       depth,
                "body":        body,
                "permalink":   _normalise_permalink(d.get("permalink")),
                "_raw":        d,
            })

        if depth < max_depth:
            replies = d.get("replies")
            if isinstance(replies, dict):
                reply_children = replies.get("data", {}).get("children", [])
                out.extend(_parse_comments_tree(reply_children, depth + 1, max_depth, include_deleted))

    return out


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_subreddit_posts(subreddit: str, sort: str = "new", time_filter: str = "all",
                          limit: int = 25, after: str = None) -> list:
    """
    Fetch posts from a subreddit.

    Returns a list of normalised post dicts.
    """
    qs = {"limit": str(min(limit, 100))}
    if sort in ("top", "controversial") and time_filter:
        qs["t"] = time_filter
    if after:
        qs["after"] = after

    url = _build_url(f"/r/{subreddit}/{sort}", qs)
    data = _fetch_json(url)
    children = data.get("data", {}).get("children", [])
    return [_normalise_post(c["data"]) for c in children if c.get("kind") == "t3"]


def fetch_thread(post_id: str, comment_limit: int = 100, max_depth: int = 10,
                 include_deleted: bool = False) -> tuple:
    """
    Fetch a Reddit thread (post + comments).

    Returns (post_dict, comments_list).
    """
    qs = {"limit": str(min(comment_limit, 500))}
    url = _build_url(f"/comments/{post_id}", qs)
    data = _fetch_json(url)

    if not isinstance(data, list) or len(data) < 1:
        raise ValueError(f"Unexpected response format for post {post_id}")

    post_listing = data[0]
    post_children = post_listing.get("data", {}).get("children", [])
    post_child = next((c for c in post_children if c.get("kind") == "t3"), None)
    if not post_child:
        raise ValueError(f"Post {post_id} not found in API response")

    post = _normalise_post(post_child["data"])

    comments = []
    if len(data) >= 2:
        comment_listing = data[1]
        children = comment_listing.get("data", {}).get("children", [])
        comments = _parse_comments_tree(children, max_depth=max_depth, include_deleted=include_deleted)

    return post, comments
