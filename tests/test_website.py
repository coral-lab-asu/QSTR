"""Offline integrity checks for the paper-facing static website."""
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parents[1] / "website"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.links.append(attrs[key])


def test_website_links_and_ids():
    page = Page()
    page.feed((SITE / "index.html").read_text())
    assert len(page.ids) == len(set(page.ids)), "Duplicate HTML IDs"
    for link in page.links:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            assert parsed.scheme == "https"
            continue
        if parsed.path:
            assert (SITE / unquote(parsed.path)).is_file(), link
        elif parsed.fragment:
            assert parsed.fragment in page.ids, link


def test_manuscript_result_contract():
    data = json.loads((SITE / "results.json").read_text())
    rows = data["results"]
    assert len(rows) == 18
    counts = Counter(row["model"] for row in rows)
    assert sorted(counts.values()) == [2, 2, 7, 7]
    assert len({(r["model"], r["method"]) for r in rows}) == 18
    for row in rows:
        for metric in ("exact", "pk", "cell"):
            assert 0 <= row[metric] <= 100
        assert row["rmse"] >= 0
    lookup = {(r["model"], r["method"]): r for r in rows}
    assert lookup["Gemini-2.5-Flash", "Zero Shot"]["exact"] == 28.56
    assert lookup["Gemini-2.5-Flash", "Zero Shot"]["pk"] == 94.51
    for model in counts:
        assert (model, "Zero Shot") in lookup
        assert (model, "Guided CoT") in lookup
    for model, score in (("Llama-3.3-70B-Instruct", 38.98), ("Qwen2.5-72B-Instruct", 36.63)):
        assert lookup[model, "RowCoT"]["cell"] == score
        assert max(r["cell"] for r in rows if r["model"] == model) == score


def test_paper_is_bundled():
    paper = SITE / "assets/qstr-paper.pdf"
    assert paper.read_bytes().startswith(b"%PDF-")
    assert paper.stat().st_size > 10000
