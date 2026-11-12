# /// script
# requires-python = ">=3.11"
# dependencies = ["selenium>=4.20", "beautifulsoup4", "requests"]
# ///
"""Walk a CGWB publications search (cgwb.gov.in/cgwbpnm/search) and download every result.

Run this on a machine that can reach cgwb.gov.in (the development container
cannot; the host times out at the TCP level). Needs Google Chrome or Chromium
installed; Selenium Manager fetches a matching chromedriver automatically.

    uv run scripts/fetch_cgwb_publications.py --dry-run           # list only (Jharkhand, state_id=20)
    uv run scripts/fetch_cgwb_publications.py                     # download
    uv run scripts/fetch_cgwb_publications.py --search-url "https://cgwb.gov.in/cgwbpnm/search?type=2&cat_id=&state_id=21&district_id=&year_of_issue=&name_of_author=&keywords=&search=search"   # Odisha
    uv run scripts/fetch_cgwb_publications.py --from-html page*.html   # parse saved pages offline

Each hit is a link of the form .../cgwbpnm/download/<id>. The script keeps the
server's filename (Content-Disposition) so files look like the manual
downloads already in downloaded_data/cgwb/, and writes a manifest CSV with
id, title text, url, filename and sha256 for seeding catalogue/sources.csv.
Afterwards run scripts/register_files.py; new PDFs will show as unclaimed
until a source row with a matching local_globs is added for each.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEARCH = (
    "https://cgwb.gov.in/cgwbpnm/search?type=2&cat_id=&state_id=20&district_id="
    "&year_of_issue=&name_of_author=&keywords=&search=search"
)
DOWNLOAD_RE = re.compile(r"/cgwbpnm/download/(\d+)")
MANIFEST_FIELDS = [
    "download_id", "state_id", "state", "title", "card_text", "posted_on", "download_count",
    "detail_url", "url", "page", "filename", "size_bytes", "sha256", "status", "fetched_on",
]
# Repository state_id values seen so far; extend as new states are crawled.
STATE_NAMES = {"20": "jharkhand", "21": "odisha"}


def page_url(base: str, page: int) -> str:
    parts = urlparse(base)
    query = parse_qs(parts.query, keep_blank_values=True)
    query["page"] = [str(page)]
    return urlunparse(parts._replace(query=urlencode(query, doseq=True)))


def _text(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def parse_results(html: str) -> tuple[list[dict], str | None, int | None, str]:
    """Parse one search-results page.

    The repository renders Bootstrap cards (div.card) with .post-date,
    .card-title, .card-text, a download counter, a publication-detail link and
    the download link. Returns (records, next_page_url, total_results).
    """
    soup = BeautifulSoup(html, "html.parser")
    records: dict[str, dict] = {}
    for a in soup.find_all("a", href=DOWNLOAD_RE):
        did = DOWNLOAD_RE.search(a["href"]).group(1)
        if did in records:
            continue
        card = a.find_parent(class_="card") or a.find_parent(["tr", "li", "article", "div"]) or a
        posted = _text(card.find(class_="post-date"))
        posted = re.sub(r"^Posted on\s*:\s*", "", posted, flags=re.I)
        detail = card.find("a", href=re.compile(r"/cgwbpnm/publication-detail/\d+"))
        counter = card.find(id=f"download-count-{did}")
        href = a["href"]
        if href.startswith("/"):
            href = "https://cgwb.gov.in" + href
        records[did] = {
            "download_id": did,
            "title": _text(card.find(class_="card-title")) or _text(a),
            "card_text": _text(card.find(class_="card-text")),
            "posted_on": posted,
            "download_count": _text(counter),
            "detail_url": detail["href"] if detail else "",
            "url": href,
        }

    nxt = soup.find("a", rel="next") or soup.find("a", attrs={"aria-label": re.compile("Next", re.I)})
    next_url = nxt["href"] if nxt and nxt.has_attr("href") else None

    total = None
    heading = soup.find(string=re.compile(r"Search Result\s*:\s*\d+", re.I))
    if heading:
        total = int(re.search(r"(\d+)", heading).group(1))

    state_id = ""
    for a in soup.select("a.page-link[href]"):
        m = re.search(r"[?&]state_id=(\d+)", a["href"])
        if m:
            state_id = m.group(1)
            break
    for r in records.values():
        r["state_id"] = state_id
        r["state"] = STATE_NAMES.get(state_id, "")
    return list(records.values()), next_url, total, state_id


def known_download_ids() -> set[str]:
    """Download ids of items already held locally (sources.csv rows with access_status downloaded)."""
    ids: set[str] = set()
    p = ROOT / "catalogue/sources.csv"
    if not p.exists():
        return ids
    with p.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("access_status") in ("downloaded", "extraction_complete", "qa_reviewed"):
                ids.update(DOWNLOAD_RE.findall(row.get("url") or ""))
    return ids


def load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {r["download_id"]: r for r in csv.DictReader(f)}


def save_manifest(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for did in sorted(rows, key=int):
            w.writerow({k: rows[did].get(k, "") for k in MANIFEST_FIELDS})


def make_driver(download_dir: Path, headless: bool) -> "webdriver.Chrome":
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,1000")
    opts.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir.resolve()),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        },
    )
    return webdriver.Chrome(options=opts)


def requests_session_from(driver) -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = driver.execute_script("return navigator.userAgent")
    s.headers["Referer"] = driver.current_url
    for c in driver.get_cookies():
        s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
    return s


def filename_from_disposition(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"filename\*=(?:UTF-8'')?\"?([^\";]+)", value, re.I) or re.search(
        r'filename="?([^";]+)"?', value, re.I
    )
    return Path(m.group(1).strip()).name if m else None


def download_with_requests(session: requests.Session, url: str, out_dir: Path, did: str) -> Path:
    with session.get(url, stream=True, timeout=120, allow_redirects=True) as r:
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:
            raise RuntimeError(f"server returned HTML instead of a file ({ctype})")
        name = filename_from_disposition(r.headers.get("Content-Disposition")) or f"{did}.pdf"
        target = out_dir / name
        if target.exists():
            target = out_dir / f"{target.stem}__{did}{target.suffix}"
        tmp = target.with_suffix(target.suffix + ".part")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        tmp.rename(target)
    return target


def download_with_browser(driver, url: str, out_dir: Path, timeout: int = 180) -> Path:
    before = {p.name for p in out_dir.iterdir()}
    driver.get(url)
    deadline = time.time() + timeout
    while time.time() < deadline:
        new = [p for p in out_dir.iterdir() if p.name not in before]
        done = [p for p in new if not p.name.endswith((".crdownload", ".tmp"))]
        if done and not any(p.name.endswith(".crdownload") for p in new):
            return done[0]
        time.sleep(1)
    raise TimeoutError("browser download did not finish")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--search-url", default=DEFAULT_SEARCH, help="search URL (page parameter is overridden)")
    ap.add_argument("--out", default="downloaded_data/cgwb/jharkhand", help="download directory, relative to repo root")
    ap.add_argument("--manifest", default="planning/cgwb_search_results.csv")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests")
    ap.add_argument("--include-known", action="store_true",
                    help="also download ids already present in catalogue/sources.csv or planning/source_queue.csv")
    ap.add_argument("--no-headless", action="store_true", help="show the browser window")
    ap.add_argument("--dry-run", action="store_true", help="list results and write the manifest, download nothing")
    ap.add_argument("--from-html", nargs="*", metavar="FILE",
                    help="parse saved result pages offline instead of browsing (implies --dry-run)")
    ap.add_argument("--state-id", help="state_id to record for --from-html pages that lack pagination links")
    ap.add_argument("--page", help="page number to record for --from-html pages whose filename does not contain it")
    args = ap.parse_args()

    search_state = re.search(r"[?&]state_id=(\d+)", args.search_url)
    search_state = search_state.group(1) if search_state else ""
    if args.out:
        out_dir = (ROOT / args.out).resolve()
    elif search_state in STATE_NAMES:
        out_dir = (ROOT / "downloaded_data/cgwb" / STATE_NAMES[search_state]).resolve()
    elif args.from_html:
        out_dir = (ROOT / "downloaded_data/cgwb").resolve()
    else:
        ap.error(f"state_id {search_state or '?'} is not in STATE_NAMES; pass --out explicitly")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / args.manifest
    manifest = load_manifest(manifest_path)
    known = set() if args.include_known else known_download_ids()
    today = time.strftime("%Y-%m-%d")

    def record_hits(hits: list[dict]) -> None:
        for r in hits:
            entry = manifest.setdefault(r["download_id"], {})
            entry.update({k: r[k] for k in r if k in MANIFEST_FIELDS})
            entry.setdefault("status", "listed")

    if args.from_html:
        hits = []
        for file in args.from_html:
            records, _, total, state_id = parse_results(Path(file).read_text(encoding="utf-8", errors="replace"))
            page = re.search(r"page[=_-]?(\d+)", Path(file).name)
            if not state_id and args.state_id:
                state_id = args.state_id
            for r in records:
                r["page"] = args.page or (page.group(1) if page else "")
                r["state_id"] = state_id
                r["state"] = STATE_NAMES.get(state_id, "")
            hits.extend(records)
            print(f"{file}: {len(records)} results (site total {total}, state_id {state_id or '?'}"
                  f"{' = ' + STATE_NAMES[state_id] if state_id in STATE_NAMES else ''})", file=sys.stderr)
        record_hits(hits)
        for r in hits:
            print(f"{r['download_id']:>6}  {r['posted_on']:<12} {r['title'][:95]}")
        save_manifest(manifest_path, manifest)
        return 0

    driver = make_driver(out_dir, headless=not args.no_headless)
    try:
        hits: list[dict] = []
        seen_ids: set[str] = set()
        url: str | None = page_url(args.search_url, args.start_page)
        page = args.start_page
        total = None
        while url and page < args.start_page + args.max_pages:
            print(f"page {page}: {url}", file=sys.stderr)
            driver.get(url)
            time.sleep(args.delay)
            results, next_url, total_here, _ = parse_results(driver.page_source)
            total = total or total_here
            fresh = [r for r in results if r["download_id"] not in seen_ids]
            if not fresh:
                print(f"page {page}: no new results, stopping", file=sys.stderr)
                break
            for r in fresh:
                r["page"] = page
                seen_ids.add(r["download_id"])
            hits.extend(fresh)
            print(f"page {page}: {len(fresh)} results", file=sys.stderr)
            url = next_url
            page += 1

        print(f"{len(hits)} distinct download links found (site reports {total})", file=sys.stderr)
        record_hits(hits)

        if args.dry_run:
            for r in hits:
                print(f"{r['download_id']:>6}  {r['posted_on']:<12} {r['title'][:95]}")
            save_manifest(manifest_path, manifest)
            return 0

        session = requests_session_from(driver)
        for r in hits:
            did = r["download_id"]
            entry = manifest[did]
            if entry.get("status") == "downloaded" and (out_dir / entry.get("filename", "")).exists():
                print(f"{did}: already downloaded ({entry['filename']})", file=sys.stderr)
                continue
            if did in known:
                entry["status"] = "skipped_known"
                print(f"{did}: already catalogued, skipping (use --include-known to force)", file=sys.stderr)
                continue
            try:
                try:
                    path = download_with_requests(session, r["url"], out_dir, did)
                except Exception as exc:  # fall back to a real browser download
                    print(f"{did}: requests failed ({exc}); trying browser download", file=sys.stderr)
                    path = download_with_browser(driver, r["url"], out_dir)
                entry.update(
                    filename=path.name,
                    size_bytes=path.stat().st_size,
                    sha256=sha256_of(path),
                    status="downloaded",
                    fetched_on=today,
                )
                print(f"{did}: {path.name} ({path.stat().st_size} bytes)", file=sys.stderr)
            except Exception as exc:
                entry.update(status=f"failed: {exc}", fetched_on=today)
                print(f"{did}: FAILED {exc}", file=sys.stderr)
            save_manifest(manifest_path, manifest)
            time.sleep(args.delay)
    finally:
        driver.quit()

    save_manifest(manifest_path, manifest)
    failed = [d for d, e in manifest.items() if str(e.get("status", "")).startswith("failed")]
    print(f"manifest written to {manifest_path} ({len(failed)} failures)", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
