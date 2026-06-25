-- Reddit 爬虫数据表
-- 遵循抓取系统设计原则：
-- - 各来源独立建表
-- - 保留 raw_data JSONB 字段存储原始 API 响应
-- - 保留 status 字段跟踪爬取状态

-- Reddit 帖子表
CREATE TABLE IF NOT EXISTS reddit_posts (
    id              SERIAL PRIMARY KEY,
    post_id         VARCHAR(20)     NOT NULL,               -- Reddit post id (e.g. "abc123")
    subreddit       VARCHAR(255)    NOT NULL DEFAULT '',
    title           TEXT            NOT NULL DEFAULT '',
    author          VARCHAR(255)    NOT NULL DEFAULT '',
    score           INTEGER         NOT NULL DEFAULT 0,
    num_comments    INTEGER         NOT NULL DEFAULT 0,
    created_utc     BIGINT          DEFAULT NULL,           -- Unix timestamp
    created_iso     VARCHAR(50)     DEFAULT NULL,           -- ISO 8601 string
    permalink       VARCHAR(2000)   NOT NULL DEFAULT '',
    url             VARCHAR(2000)   NOT NULL DEFAULT '',
    is_self         BOOLEAN         NOT NULL DEFAULT FALSE,
    over_18         BOOLEAN         NOT NULL DEFAULT FALSE,
    flair           VARCHAR(500)    DEFAULT NULL,
    selftext        TEXT            NOT NULL DEFAULT '',
    file_path       VARCHAR(2000)   DEFAULT NULL,           -- 本地保存的 Markdown 文件路径
    status          VARCHAR(50)     NOT NULL DEFAULT 'ready',
    raw_data        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_reddit_posts_id UNIQUE (post_id)
);

-- Reddit 评论表
CREATE TABLE IF NOT EXISTS reddit_comments (
    id              SERIAL PRIMARY KEY,
    comment_id      VARCHAR(20)     NOT NULL,               -- Reddit comment id
    post_id         VARCHAR(20)     NOT NULL REFERENCES reddit_posts(post_id),
    parent_id       VARCHAR(30)     DEFAULT NULL,           -- parent fullname (t1_xxx or t3_xxx)
    author          VARCHAR(255)    NOT NULL DEFAULT '',
    score           INTEGER         NOT NULL DEFAULT 0,
    created_utc     BIGINT          DEFAULT NULL,
    created_iso     VARCHAR(50)     DEFAULT NULL,
    depth           INTEGER         NOT NULL DEFAULT 0,
    body            TEXT            NOT NULL DEFAULT '',
    permalink       VARCHAR(2000)   DEFAULT NULL,
    status          VARCHAR(50)     NOT NULL DEFAULT 'ready',
    raw_data        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_reddit_comments_id UNIQUE (comment_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_reddit_posts_subreddit
    ON reddit_posts (subreddit);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_author
    ON reddit_posts (author);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_created
    ON reddit_posts (created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_status
    ON reddit_posts (status);

CREATE INDEX IF NOT EXISTS idx_reddit_comments_post_id
    ON reddit_comments (post_id);
CREATE INDEX IF NOT EXISTS idx_reddit_comments_author
    ON reddit_comments (author);
CREATE INDEX IF NOT EXISTS idx_reddit_comments_created
    ON reddit_comments (created_utc DESC);
