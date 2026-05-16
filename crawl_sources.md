# 期刊爬取方案

共 **8 个可用来源**，分 3 类：GitHub epub、RSS、Guardian API。

---

## 一、GitHub epub 来源（4 个）

仓库: `hehonghui/awesome-english-ebooks`

从 GitHub API 下载 epub → ebooklib 解析 → 提取正文。

### 通用代码

```python
import requests, ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

GITHUB_API = "https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents"
HEADERS = {"Accept": "application/vnd.github.v3.raw"}

def download_epub(api_path: str) -> bytes:
    url = f"{GITHUB_API}/{api_path}"
    resp = requests.get(url, headers=HEADERS, stream=True, timeout=120)
    resp.raise_for_status()
    return resp.content

def parse_epub(data: bytes) -> list[dict]:
    """返回 [{"title": str, "text": str, "word_count": int}, ...]"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        book = epub.read_epub(tmp.name)

    articles = []
    for item in book.get_items():
        # Economist 用 type=0, Atlantic/Wired/NewYorker 用 type=9
        if item.get_type() not in (0, 9):
            continue
        if not item.get_name().endswith(".html"):
            continue

        soup = BeautifulSoup(item.get_content(), "lxml")
        # 清理导航
        for tag in soup(["script","style","nav","header","footer","aside","noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\| Next \|.*?\| Previous \|", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        wc = len(text.split())
        if wc < 100:
            continue

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "Untitled"

        articles.append({"title": title, "text": text, "word_count": wc})
    return articles
```

### The Economist

| 字段 | 值 |
|------|-----|
| 路径 | `01_economist/te_YYYY.MM.DD/TheEconomist.YYYY.MM.DD.epub` |
| 最新 | `te_2026.05.09`（5.7 MB） |
| 文章数 | ~75 篇 |
| 文章类型 | type=0 |
| 特点 | 短新闻多，涵盖商业/科技/国际 |

获取最新期：

```python
# 先列出目录
resp = requests.get(
    "https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents/01_economist",
    headers={"Accept": "application/vnd.github.v3+json"}
)
folders = sorted(resp.json(), key=lambda x: x["name"], reverse=True)
latest = folders[0]  # -> {"name": "te_2026.05.09", ...}

# 再列文件
resp2 = requests.get(latest["url"], headers={"Accept": "application/vnd.github.v3+json"})
files = resp2.json()
epub_info = [f for f in files if f["name"].endswith(".epub")][0]
api_path = "01_economist/" + latest["name"] + "/" + epub_info["name"]
```

### The Atlantic

| 字段 | 值 |
|------|-----|
| 路径 | `04_atlantic/YYYY.MM.DD/Atlantic_YYYY.MM.DD.epub` |
| 最新 | `2026.05.02`（8.2 MB） |
| 文章数 | ~12 篇 |
| 文章类型 | type=9 |
| 特点 | 深度长文为主 |

### Wired

| 字段 | 值 |
|------|-----|
| 路径 | `05_wired/YYYY.MM.DD/wired_YYYY.MM.DD.epub` |
| 最新 | `2026.05.02`（35.6 MB） |
| 文章数 | ~55 篇 |
| 文章类型 | type=9 |
| 特点 | 科技类文章多 |

### The New Yorker

| 字段 | 值 |
|------|-----|
| 路径 | `02_new_yorker/YYYY.MM.DD/new_yorker.YYYY.MM.DD.epub` |
| 最新 | `2026.05.11`（8.2 MB） |
| 文章数 | ~24 篇 |
| 文章类型 | type=0 |
| 特点 | 文化/评论/小说，有短篇栏目 |

---

## 二、RSS 来源（3 个）

直接从 RSS 获取 feed 条目，再逐个抓取正文。

### 通用代码

```python
import feedparser, requests
from bs4 import BeautifulSoup

def fetch_rss_articles(feed_url: str, max_articles: int = 5) -> list[dict]:
    feed = feedparser.parse(feed_url)
    articles = []

    for entry in feed.entries:
        if len(articles) >= max_articles:
            break

        title = entry.get("title", "")
        link = entry.get("link", "")

        # 抓取正文
        try:
            resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script","style","nav","header","footer","aside"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        except Exception:
            text = entry.get("summary", "")

        articles.append({"title": title, "text": text, "word_count": len(text.split())})

    return articles
```

### Scientific American

| 字段 | 值 |
|------|-----|
| Feed | `https://www.scientificamerican.com/platform/syndication/rss/` |
| 文章数 | 50+ 篇每次 |
| 内容 | ✅ 内网可获取 |
| 特点 | 科技/环境/健康，文章 500–2000 词 |

### Nautilus

| 字段 | 值 |
|------|-----|
| Feed | `https://nautil.us/feed/` |
| 文章数 | ~10 篇每次 |
| 内容 | ✅ 内网可获取 |
| 特点 | 科普/哲学，部分在 500–900 词 |

### Nature

| 字段 | 值 |
|------|-----|
| Feed | `https://www.nature.com/nature.rss` |
| 文章数 | 50+ 篇每次 |
| 内容 | ✅ 内网可获取 |
| 特点 | 学术/科学新闻 |

---

## 三、Guardian API

不通过 RSS（被屏蔽），使用 Guardian 官方开放 API。

```python
import requests

API = "https://content.guardianapis.com/search"
PARAMS = {
    "section": "technology|science|books|environment|global-development|business|lifeandstyle",
    "page-size": 10,
    "show-fields": "bodyText,headline,wordCount,shortUrl",
    "order-by": "newest",
    "api-key": "test",      # free tier, 无需注册
}

resp = requests.get(API, params=PARAMS, timeout=15)
data = resp.json()

for article in data["response"]["results"]:
    title = article["webTitle"]
    body = article["fields"]["bodyText"]
    section = article["sectionName"]
    wc = len(body.split())
    print(f"[{section}] {title} ({wc}w)")
```

| 字段 | 值 |
|------|-----|
| Endpoint | `content.guardianapis.com` |
| Key | `test`（免费可用，有速率限制） |
| 内容 | ✅ 内网可达，返回完整 bodyText |
| 排除 | 可指定 section 排除 politics/sport/culture |

---

## 四、不可用来源

| 来源 | 原因 |
|------|------|
| **Aeon** | RSS 可读但正文获取被 CDN 屏蔽 |
| **BBC News** | 域名被屏蔽 |
| **NYT** | 域名被屏蔽 |
| **ScienceMag** | RSS 可读但正文获取被屏蔽 |
| **Reuters** | 需要订阅/付费墙 |

---

## 五、仓库目录结构

```
01_economist/
  te_2026.05.09/
    TheEconomist.2026.05.09.epub
02_new_yorker/
  2026.05.11/
    new_yorker.2026.05.11.epub
04_atlantic/
  2026.05.02/
    Atlantic_2026.05.02.epub
05_wired/
  2026.05.02/
    wired_2026.05.02.epub
```

> 注意：序号 03 不存在（可能是 removed 了）

---

## 六、排除关键词

政治/体育/娱乐类文章自动跳过：

```
politics, sports, entertainment, football, election,
trump, biden, nfl, nba, soccer, baseball,
olympic, movie, film, celebrity, hollywood,
tv show, netflix, disney, oscar, kardashian,
fashion week, reality tv, box office
```
