# Reddit Readonly Skill

一个用于 [OpenClaw](https://openclaw.com) 的 Reddit 只读浏览技能。让你的 AI 助手帮你浏览 Reddit、搜索帖子、查看评论，还能把感兴趣的帖子保存为 Markdown 文件。

> **全程不需要你敲任何命令！** 只需要用自然语言跟 AI 助手对话就行。

## 📦 安装

跟你的 AI 助手说：

> 帮我安装这个 skill：https://github.com/LeXrLt/reddit_skill

助手会自动完成下载和配置，装好之后就能直接使用了。

## 🚀 使用方法

安装完成后，你只需要用自然语言告诉 AI 助手你想做什么。下面是一些常见的使用场景：

### 浏览热门帖子

> 帮我看看 r/python 上最热门的 5 个帖子

> r/javascript 最近有什么新帖子？

### 搜索帖子

> 帮我在 r/MachineLearning 搜索关于 "transformer" 的帖子

> 在整个 Reddit 搜索 "Gemini AI"，只看最近一周的

### 查看帖子评论

> 帮我看看这个帖子的评论：https://www.reddit.com/r/python/comments/abc123/...

> 把帖子 abc123 的评论拉出来看看，只看前 10 条

### 多子版块批量查找

> 帮我在 r/python、r/golang、r/rust 这三个子版块里找跟 "web framework" 有关的帖子，只要最近 48 小时内的，分数大于 5 的

### 保存帖子为 Markdown

> 帮我把这个帖子保存为 Markdown 文件：https://www.reddit.com/r/Bard/comments/xyz789/...

> 把刚才搜到的第一个帖子保存下来，评论也要

保存的文件会自动存放在 `saved_posts/` 目录下，文件名格式为 `子版块_帖子ID_标题.md`，包含完整的帖子内容和评论。

## 📁 保存的 Markdown 长什么样？

每个保存的帖子都遵循统一的模板格式：

- **文件头部** — 包含帖子的元信息（ID、作者、分数、时间等），方便后续程序化处理
- **帖子正文** — 完整的帖子内容
- **评论区** — 按嵌套层级排列的评论，保留回复关系

## ⚠️ 注意事项

- **这是一个只读技能** — 它只能浏览和搜索 Reddit，不会帮你发帖、回复或投票
- **请温和使用** — Reddit 对频繁请求有限制，建议每次查询少量帖子（5-10 个），需要更多时再追加
- **需要网络** — 脚本需要访问 Reddit 的公共接口，请确保网络通畅
- **结果包含永久链接** — 如果你想回复某个帖子，助手会给你链接，你可以自己打开 Reddit 手动操作

## 📄 许可

MIT
