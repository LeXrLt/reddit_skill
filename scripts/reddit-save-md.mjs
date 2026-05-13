#!/usr/bin/env node

/**
 * reddit-save-md.mjs
 *
 * Fetch a Reddit post (with comments) and save the complete content
 * as a Markdown file using a unified template.
 *
 * Usage:
 *   node scripts/reddit-save-md.mjs <post_id|url> [options]
 *
 * Options:
 *   --outDir <path>         Output directory (default: ./saved_posts)
 *   --commentLimit <N>      Max top-level comments to fetch (default: 100)
 *   --depth <N>             Max comment nesting depth (default: 10)
 *   --maxChars <N>          Max chars per comment body (default: 20000, effectively no limit)
 *   --includeDeleted        Include deleted/removed comments (default: false)
 *   --noComments            Skip fetching comments entirely
 *   --template <path>       Custom template file path (default: references/POST_TEMPLATE.md)
 *
 * Output:
 *   Saves a markdown file at <outDir>/<subreddit>_<post_id>_<slugified_title>.md
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const BASE_DIR = resolve(__dirname, '..');

const BASE_URL = 'https://www.reddit.com';

const DEFAULTS = {
  minDelayMs: parseInt(process.env.REDDIT_RO_MIN_DELAY_MS || '500', 10),
  maxDelayMs: parseInt(process.env.REDDIT_RO_MAX_DELAY_MS || '1500', 10),
  timeoutMs: parseInt(process.env.REDDIT_RO_TIMEOUT_MS || '20000', 10),
  userAgent: process.env.REDDIT_RO_USER_AGENT || 'script:clawdbot-reddit-readonly:v1.0.0',
};

// -------------------- Utility Functions --------------------

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randInt(min, max) {
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  return lo + Math.floor(Math.random() * (hi - lo + 1));
}

function toIsoFromUtcSeconds(sec) {
  return new Date(sec * 1000).toISOString();
}

function clampInt(n, lo, hi, fallback) {
  const x = Number.isFinite(n) ? n : fallback;
  return Math.max(lo, Math.min(hi, x));
}

function slugify(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

function escapeYaml(val) {
  if (val === null || val === undefined) return 'null';
  const s = String(val);
  if (/[:\[\]{}&*!|>'"@`#%,]/.test(s) || s.includes('\n')) {
    return JSON.stringify(s);
  }
  return s;
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith('--')) {
        out[key] = next;
        i++;
      } else {
        out[key] = true;
      }
    } else {
      out._.push(a);
    }
  }
  return out;
}

function extractPostId(input) {
  const s = String(input || '').trim();
  if (!s) return null;
  if (/^[a-z0-9]{5,10}$/i.test(s)) return s;
  const m = s.match(/comments\/([a-z0-9]{5,10})/i);
  if (m) return m[1];
  return null;
}

function normalisePermalink(permalink) {
  if (!permalink) return null;
  if (permalink.startsWith('http')) return permalink;
  if (permalink.startsWith('/')) return `${BASE_URL}${permalink}`;
  return `${BASE_URL}/${permalink}`;
}

// -------------------- Fetch --------------------

async function fetchJson(url) {
  if (typeof fetch !== 'function') {
    throw new Error('This script requires Node.js 18+ (global fetch not found).');
  }

  await sleep(randInt(DEFAULTS.minDelayMs, DEFAULTS.maxDelayMs));

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), DEFAULTS.timeoutMs);
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': DEFAULTS.userAgent,
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    const text = await res.text();
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`);
    if (text.trim().startsWith('<')) {
      throw new Error('Reddit returned HTML instead of JSON. Try again later.');
    }
    return JSON.parse(text);
  } finally {
    clearTimeout(t);
  }
}

async function fetchJsonWithRetry(url, { retries = 3 } = {}) {
  let attempt = 0;
  let lastErr = null;
  while (attempt <= retries) {
    try {
      return await fetchJson(url);
    } catch (e) {
      lastErr = e;
      const msg = String(e?.message || e);
      const isRetryable = msg.includes('HTTP 429') || msg.includes('HTTP 5') || msg.includes('aborted') || msg.includes('HTML instead of JSON');
      if (!isRetryable || attempt === retries) break;
      const backoff = 600 * Math.pow(2, attempt) + randInt(0, 400);
      await sleep(backoff);
      attempt++;
    }
  }
  throw lastErr || new Error('Request failed');
}

function buildUrl(pathWithQuery) {
  if (/^https?:\/\//i.test(pathWithQuery)) return pathWithQuery;
  const [path, qs] = String(pathWithQuery).split('?');
  const jsonPath = path.endsWith('.json') ? path : `${path}.json`;
  return qs ? `${BASE_URL}${jsonPath}?${qs}` : `${BASE_URL}${jsonPath}`;
}

// -------------------- Data Extraction --------------------

function extractPost(postListing) {
  const postChild = postListing?.data?.children?.find((x) => x && x.kind === 't3');
  if (!postChild) return null;
  const d = postChild.data;
  const createdUtc = d.created_utc || 0;
  return {
    id: d.id,
    fullname: d.name || (d.id ? `t3_${d.id}` : null),
    subreddit: d.subreddit,
    title: d.title,
    author: d.author,
    score: d.score,
    num_comments: d.num_comments,
    created_utc: createdUtc,
    created_iso: createdUtc ? toIsoFromUtcSeconds(createdUtc) : null,
    permalink: normalisePermalink(d.permalink),
    url: d.url,
    is_self: d.is_self,
    over_18: d.over_18,
    flair: d.link_flair_text || null,
    selftext: d.selftext || '',
  };
}

function parseCommentsTree(children, { depth = 0, maxDepth = 10, includeDeleted = false, maxChars = 20000 }) {
  const out = [];
  let moreCount = 0;

  if (!Array.isArray(children)) return { comments: out, moreCount };

  for (const node of children) {
    if (!node) continue;

    if (node.kind === 'more') {
      const count = node?.data?.count;
      moreCount += typeof count === 'number' ? count : 0;
      continue;
    }

    if (node.kind !== 't1') continue;

    const d = node.data;
    const author = d?.author;
    const body = d?.body;
    const createdUtc = d.created_utc || 0;

    const isDeleted = author === '[deleted]' || body === '[deleted]' || body === '[removed]' || body == null;

    if (!includeDeleted && isDeleted) {
      // still traverse replies
    } else {
      out.push({
        id: d.id,
        author: d.author,
        score: d.score,
        created_utc: createdUtc,
        created_iso: createdUtc ? toIsoFromUtcSeconds(createdUtc) : null,
        depth,
        body: body ? String(body).slice(0, maxChars) : '',
      });
    }

    if (depth < maxDepth) {
      const replies = d?.replies;
      const replyChildren = replies && replies.data && Array.isArray(replies.data.children) ? replies.data.children : null;
      if (replyChildren) {
        const parsed = parseCommentsTree(replyChildren, {
          depth: depth + 1,
          maxDepth,
          includeDeleted,
          maxChars,
        });
        out.push(...parsed.comments);
        moreCount += parsed.moreCount;
      }
    }
  }

  return { comments: out, moreCount };
}

// -------------------- Markdown Rendering --------------------

function renderComment(comment) {
  const indent = '  '.repeat(comment.depth);
  const header = `${indent}> **u/${comment.author}** | Score: ${comment.score} | ${comment.created_iso}`;
  const bodyLines = comment.body
    .split('\n')
    .map((line) => `${indent}> ${line}`)
    .join('\n');
  return `${header}\n${indent}>\n${bodyLines}\n`;
}

function renderComments(comments) {
  if (!comments || comments.length === 0) return '*No comments available.*';
  return comments.map((c) => renderComment(c)).join('\n');
}

function applyTemplate(template, post, comments, moreCount, savedAt) {
  const commentsMarkdown = renderComments(comments);

  const replacements = {
    '{{id}}': post.id || '',
    '{{fullname}}': post.fullname || '',
    '{{subreddit}}': post.subreddit || '',
    '{{author}}': post.author || '',
    '{{score}}': String(post.score ?? 0),
    '{{num_comments}}': String(post.num_comments ?? 0),
    '{{created_utc}}': String(post.created_utc ?? 0),
    '{{created_iso}}': post.created_iso || '',
    '{{permalink}}': post.permalink || '',
    '{{url}}': post.url || '',
    '{{flair}}': post.flair || 'None',
    '{{is_self}}': String(post.is_self ?? false),
    '{{over_18}}': String(post.over_18 ?? false),
    '{{saved_at}}': savedAt,
    '{{title}}': post.title || 'Untitled',
    '{{selftext}}': post.selftext || '*No text content (link post).*',
    '{{comments_count}}': String(comments.length),
    '{{more_count}}': String(moreCount),
    '{{comments}}': commentsMarkdown,
  };

  let result = template;
  for (const [placeholder, value] of Object.entries(replacements)) {
    result = result.replaceAll(placeholder, value);
  }
  return result;
}

// -------------------- Main --------------------

function usage() {
  return [
    'Usage: node scripts/reddit-save-md.mjs <post_id|url> [options]',
    '',
    'Options:',
    '  --outDir <path>         Output directory (default: ./saved_posts)',
    '  --commentLimit <N>      Max top-level comments to fetch (default: 100)',
    '  --depth <N>             Max comment nesting depth (default: 10)',
    '  --maxChars <N>          Max chars per comment body (default: 20000)',
    '  --includeDeleted        Include deleted/removed comments',
    '  --noComments            Skip fetching comments',
    '  --template <path>       Custom template file path',
  ].join('\n');
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const [postIdOrUrl] = args._;

  if (args.help) {
    console.log(usage());
    process.exit(0);
  }

  if (!postIdOrUrl) {
    console.error(usage());
    process.exit(1);
  }

  const postId = extractPostId(postIdOrUrl);
  if (!postId) {
    console.error('Error: Could not parse post id. Provide a post id like "abc123" or a full Reddit URL.');
    process.exit(1);
  }

  const outDir = resolve(args.outDir || join(BASE_DIR, 'saved_posts'));
  const commentLimit = clampInt(parseInt(args.commentLimit || '100', 10), 1, 500, 100);
  const maxDepth = clampInt(parseInt(args.depth || '10', 10), 0, 20, 10);
  const maxChars = clampInt(parseInt(args.maxChars || '20000', 10), 50, 100000, 20000);
  const includeDeleted = args.includeDeleted === true;
  const noComments = args.noComments === true;

  const templatePath = args.template
    ? resolve(args.template)
    : join(BASE_DIR, 'references', 'POST_TEMPLATE.md');

  // Load template
  let template;
  try {
    template = readFileSync(templatePath, 'utf-8');
  } catch (e) {
    console.error(`Error: Could not read template file at ${templatePath}`);
    process.exit(1);
  }

  // Fetch post and comments
  console.log(`Fetching post ${postId}...`);

  const qs = new URLSearchParams();
  qs.set('limit', String(commentLimit));
  const url = buildUrl(`/comments/${postId}?${qs.toString()}`);

  let data;
  try {
    data = await fetchJsonWithRetry(url);
  } catch (e) {
    console.error(`Error fetching post: ${e.message}`);
    process.exit(1);
  }

  const postListing = Array.isArray(data) ? data[0] : null;
  const commentListing = Array.isArray(data) ? data[1] : null;

  const post = extractPost(postListing);
  if (!post) {
    console.error('Error: Could not extract post data from API response.');
    process.exit(1);
  }

  let comments = [];
  let moreCount = 0;

  if (!noComments && commentListing) {
    const children = commentListing?.data?.children || [];
    const parsed = parseCommentsTree(children, { maxDepth, includeDeleted, maxChars });
    comments = parsed.comments;
    moreCount = parsed.moreCount;
    console.log(`Fetched ${comments.length} comments (${moreCount} more hidden).`);
  } else {
    console.log('Skipping comments.');
  }

  // Apply template
  const savedAt = new Date().toISOString();
  const markdown = applyTemplate(template, post, comments, moreCount, savedAt);

  // Write file
  if (!existsSync(outDir)) {
    mkdirSync(outDir, { recursive: true });
  }

  const slug = slugify(post.title);
  const filename = `${post.subreddit}_${post.id}_${slug}.md`;
  const filepath = join(outDir, filename);

  writeFileSync(filepath, markdown, 'utf-8');
  console.log(`Saved: ${filepath}`);

  // Also output JSON summary to stdout for programmatic use
  const summary = {
    ok: true,
    data: {
      post_id: post.id,
      subreddit: post.subreddit,
      title: post.title,
      comments_saved: comments.length,
      more_count: moreCount,
      file: filepath,
    },
  };
  console.log(JSON.stringify(summary, null, 2));
}

main();
