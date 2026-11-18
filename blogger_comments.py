#!/usr/bin/env python3
"""
Ler comentarios completos de blogs Blogger/Blogspot, sem browser.

Porque e que o RSS nao chega:
  - todos os feeds de comentarios do Blogger (rss/atom/json) cortam o texto
    de CADA comentario aos ~400 caracteres (campo summary). Nao ha opcao
    nem URL que devolva o texto todo no feed.
  - o feed tem todos os comentarios do blog (dezenas de milhares), paginado
    por start-index, max 500 por pedido.
  - o texto completo existe no HTML do post, 200 comentarios por pagina:
        https://blog.blogspot.com/2026/07/post.html?commentPage=N
    e e HTML estatico (nao precisa de JS).

Uso:
  blogger_comments.py URL                 # ultimos 10 comentarios, texto completo
  blogger_comments.py URL -n 30           # ultimos 30
  blogger_comments.py URL --id 123456789  # um comentario especifico
  blogger_comments.py URL --page 3        # uma pagina inteira (200)
  blogger_comments.py URL --feed -n 200   # Atom com texto completo (para o leitor RSS)
"""

import argparse
import gzip
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64) blogger_comments/1.0"
PER_PAGE = 200
STATS = {"requests": 0, "bytes": 0}

COMMENT_RE = re.compile(
    r"<dt class='comment-author[^>]*id='c(?P<id>\d+)'>(?P<head>.*?)</dt>\s*"
    r"<dd class='comment-body' id='Blog1_cmt-(?P=id)'>(?P<body>.*?)</dd>\s*"
    r"<dd class='comment-footer'>(?P<foot>.*?)</dd>",
    re.S,
)
AUTHOR_RE = re.compile(r"rel='nofollow'>(?P<name>[^<]*)</a>\s*said")
TS_RE = re.compile(r"showComment=(?P<ms>\d+)#c\d+'\s*title='comment permalink'>\s*(?P<date>.*?)\s*</a>", re.S)
RANGE_RE = re.compile(r"(\d+)\s*&ndash;\s*(\d+)\s*of\s*(\d+)")


def fetch(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                STATS["requests"] += 1
                STATS["bytes"] += len(raw)
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 500, 502, 503, 504) and i < tries - 1:
                wait = exc.headers.get("Retry-After")
                wait = int(wait) if wait and wait.isdigit() else 3 * 2**i
                time.sleep(min(wait, 60) + random.random())
                continue
            raise
        except Exception as exc:  # timeouts, DNS, ligacoes cortadas
            last = exc
            if i < tries - 1:
                time.sleep(3 * 2**i + random.random())
    raise last


def post_url(url):
    """Normaliza para o URL do post, sem query."""
    url = url.split("#")[0].split("?")[0]
    if url.endswith("/"):
        url = url[:-1]
    return url


def page_url(base, page):
    return f"{base}?commentPage={page}"


def to_text(fragment):
    s = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    s = re.sub(r"(?i)</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse(html_text, base=""):
    out = []
    for m in COMMENT_RE.finditer(html_text):
        head, body, foot = m.group("head"), m.group("body"), m.group("foot")
        a = AUTHOR_RE.search(head)
        t = TS_RE.search(foot)
        if not t:
            continue
        ms = int(t.group("ms"))
        out.append(
            {
                "id": m.group("id"),
                "author": html.unescape(a.group("name")).strip() if a else "?",
                "ts": ms,
                "date": html.unescape(re.sub(r"\s+", " ", t.group("date"))),
                "html": body.strip(),
                "text": to_text(body),
                "post": base,
            }
        )
    return out


def total_comments(html_text):
    m = RANGE_RE.search(html_text)
    return int(m.group(3)) if m else None


def render(c, base):
    lines = [f"### {c['author']} - {c['date']}  (#{c['id']})"]
    lines.append(f"{base}?showComment={c['ts']}#c{c['id']}")
    lines.append("")
    lines.append(c["text"])
    lines.append("")
    return "\n".join(lines)


def load_feed(path):
    """Le um feed Atom ja gerado, para aproveitar o que ja temos (cache)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError, ValueError):
        return []
    ns = "{http://www.w3.org/2005/Atom}"
    out = []
    for e in root.findall(ns + "entry"):
        try:
            cid = e.find(ns + "id").text.rsplit("comment-", 1)[-1]
            link = e.find(ns + "link").get("href")
            author, _, date = (e.find(ns + "title").text or "").partition(" - ")
            content = e.find(ns + "content").text or ""
            ts = int(datetime.fromisoformat(e.find(ns + "published").text).timestamp() * 1000)
        except (AttributeError, TypeError, ValueError):
            continue
        out.append(
            {
                "id": cid,
                "author": author,
                "date": date,
                "ts": ts,
                "html": content,
                "text": to_text(content),
                "post": link.split("?")[0],
            }
        )
    return out


def post_total(blog_id, post_id):
    """Numero de comentarios de um post, via feed minusculo (sem HTML)."""
    url = f"https://www.blogger.com/feeds/{blog_id}/{post_id}/comments/default?alt=json&max-results=1"
    data = json.loads(fetch(url))
    return int(data["feed"]["openSearch$totalResults"]["$t"])


def blog_latest(blog, n, cache_path=None):
    """Ultimos n comentarios do blog inteiro, com texto completo."""
    cached = load_feed(cache_path) if cache_path else []

    if cached:
        # sonda barata: se o comentario mais recente ja e o que temos, nao ha nada a fazer
        head = json.loads(fetch(f"{blog}/feeds/comments/default?alt=json&max-results=1"))
        h = head["feed"]["entry"][0]
        link = next(l["href"] for l in h["link"] if "showComment=" in l["href"])
        if int(re.search(r"showComment=(\d+)", link).group(1)) <= max(c["ts"] for c in cached):
            print(
                f"-- sonda: feed={link.split('showComment=')[1].split('#')[0]} "
                f"cache={max(c['ts'] for c in cached)} -> sem novidades",
                file=sys.stderr,
            )
            return cached[:n]

    want = 100 if cached else n
    data = json.loads(fetch(f"{blog}/feeds/comments/default?alt=json&max-results={min(500, want)}"))
    entries = data["feed"].get("entry", [])

    known = {c["id"] for c in cached}
    missing = [e for e in entries if e["id"]["$t"].rsplit("-", 1)[-1] not in known]

    groups = {}
    for e in missing:
        links = [l["href"] for l in e["link"]]
        show = next(h for h in links if "showComment=" in h)
        post = show.split("?")[0]
        m = next((re.search(r"/feeds/(\d+)/(\d+)/comments/default", h) for h in links if "/feeds/" in h), None)
        g = groups.setdefault(post, {"ids": m.groups() if m else None, "entries": []})
        g["entries"].append(e)

    found = {}
    skipped = 0
    for post, g in groups.items():
        es = g["entries"]
        try:
            total = post_total(*g["ids"]) if g["ids"] else (total_comments(fetch(post)) or 0)
            pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
            # os k comentarios mais recentes deste post estao nas ultimas paginas
            start = max(1, (total - len(es) + PER_PAGE) // PER_PAGE)
            for p in range(start, pages + 1):
                for c in parse(fetch(page_url(post, p)), post):
                    found[c["id"]] = c
        except Exception as exc:  # 429 ou falha de rede: tentar na proxima execucao
            skipped += 1
            print(f"-- aviso: {post} falhou ({exc}); fica para a proxima", file=sys.stderr)

    ids = [e["id"]["$t"].rsplit("-", 1)[-1] for e in missing]
    fresh = [found[i] for i in ids if i in found]
    out = sorted(cached + fresh, key=lambda c: c["ts"], reverse=True)
    if skipped:
        print(f"-- {skipped} post(s) adiado(s); feed mantem o que ja tinha", file=sys.stderr)
    return out[:n]


def as_atom(comments, base, title):
    entries = []
    for c in comments:
        dt = datetime.fromtimestamp(c["ts"] / 1000, tz=timezone.utc)
        entries.append(
            "<entry>"
            f"<id>tag:blogger.com,1999:comment-{c['id']}</id>"
            f"<title>{html.escape(c['author'] + ' - ' + c['date'])}</title>"
            f"<published>{dt.isoformat()}</published>"
            f"<updated>{dt.isoformat()}</updated>"
            f"<author><name>{html.escape(c['author'])}</name></author>"
            f"<link rel='alternate' href='{c.get('post') or base}?showComment={c['ts']}#c{c['id']}'/>"
            f"<content type='html'>{html.escape(c['html'], quote=False)}</content>"
            "</entry>"
        )
    newest = max((c["ts"] for c in comments), default=0)
    stamp = datetime.fromtimestamp(newest / 1000, tz=timezone.utc).isoformat()
    return (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<feed xmlns='http://www.w3.org/2005/Atom'>"
        f"<title>{html.escape(title)}</title>"
        f"<id>{base}</id>"
        f"<updated>{stamp}</updated>"
        f"<link rel='alternate' href='{base}'/>"
        + "".join(entries)
        + "</feed>\n"
    )


def main():
    ap = argparse.ArgumentParser(description="Comentarios completos de Blogger.")
    ap.add_argument("url", help="URL do post (ou do comentario)")
    ap.add_argument("-n", "--number", type=int, default=10, help="quantos comentarios (default 10)")
    ap.add_argument("--id", help="ID do comentario a procurar")
    ap.add_argument("--page", type=int, help="mostrar uma pagina inteira (1..N)")
    ap.add_argument("--feed", action="store_true", help="emitir Atom com texto completo")
    ap.add_argument("--blog", action="store_true", help="URL e o blog: ultimos N comentarios de todos os posts")
    ap.add_argument("--merge-from", metavar="FEED", help="aproveitar comentarios ja presentes neste Atom (cache)")
    ap.add_argument("--verbose", action="store_true", help="mostrar pedidos e bytes no stderr")
    args = ap.parse_args()

    if args.blog:
        blog = args.url.split("?")[0].split("#")[0].rstrip("/")
        comments = blog_latest(blog, args.number, args.merge_from)
        if args.feed:
            print(as_atom(comments, blog, f"Comentarios completos: {blog}"))
        else:
            print("".join(render(c, c["post"]) for c in comments))
        print(f"-- {len(comments)} comentario(s) de {blog}", file=sys.stderr)
        if args.verbose:
            print(f"-- {STATS['requests']} pedidos, {STATS['bytes'] / 1024:.0f} KB", file=sys.stderr)
        return

    base = post_url(args.url)
    first = fetch(base)
    total = total_comments(first) or 0
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    if args.page:
        comments = parse(fetch(page_url(base, args.page)))
    elif args.id:
        comments = []
        for p in range(pages, 0, -1):
            page = parse(fetch(page_url(base, p)))
            hit = [c for c in page if c["id"] == args.id]
            if hit:
                comments = hit
                break
        if not comments:
            sys.exit(f"comentario {args.id} nao encontrado em {pages} paginas")
    elif args.feed:
        comments = []
        for p in range(1, pages + 1):
            comments.extend(parse(fetch(page_url(base, p))))
    else:
        comments = parse(fetch(page_url(base, pages)))[-args.number:]

    if args.feed:
        title = re.search(r"<title>(.*?)</title>", first, re.S)
        title = html.unescape(title.group(1)).strip() if title else base
        print(as_atom(comments, base, f"Comentarios: {title}"))
    else:
        print("".join(render(c, base) for c in comments))
        print(f"-- {len(comments)} comentario(s); total no post: {total}; paginas: {pages}", file=sys.stderr)


if __name__ == "__main__":
    main()
