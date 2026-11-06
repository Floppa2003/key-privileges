"""Small, read-only observations of four known public source endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qsl, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "loyalty"))

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
from public_transport import PublicSource
from read_budget import within_source_budget
from source_diagnostics import error_record

SOURCES = ("rgo", "hse_alumni", "flystation_public", "af_vtb_rules")
RGO_SNAPSHOT = """() => ({
  card_count: document.querySelectorAll('.loyalty-card').length,
  hrefs: Array.from(document.querySelectorAll('.loyalty-card__link[href]')).map(n => n.getAttribute('href')),
  more: Array.from(document.querySelectorAll('.pagination-more .btn')).slice(0, 4).map(n => ({
    tag: n.tagName, href: n.getAttribute('href'), type: n.getAttribute('type'),
    visible: !!n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden',
    disabled: !!n.disabled || n.getAttribute('aria-disabled') === 'true'
  })),
  more_count: document.querySelectorAll('.pagination-more .btn').length,
  next_hrefs: Array.from(document.querySelectorAll('a[rel="next"], .pagination a[href], .pagination-more a[href]')).slice(0, 16).map(n => n.getAttribute('href'))
})"""
RGO_CHANGED = """before => Array.from(new Set(Array.from(
  document.querySelectorAll('.loyalty-card__link[href]')).map(n => n.getAttribute('href'))
)).sort().join('\\n') !== before"""


def emit(kind, value):
    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(value) > 65536:
        raise ValueError("probe_output_bound")
    print(kind + " " + value, flush=True)


def safe_url(value, base):
    target = urlsplit(urljoin(base, value or ""))
    return {
        "host": target.hostname, "path": target.path[:240],
        "pages": {k: v for k, v in parse_qsl(target.query)
                  if re.fullmatch(r"(?:PAGEN_\d+|page|paged)", k, re.I)
                  and re.fullmatch(r"\d{1,6}", v)},
    }


async def rgo_snapshot(client):
    client.check_url(client.page.url)
    value = await client.page.evaluate(RGO_SNAPSHOT)
    hrefs = frozenset(value.pop("hrefs"))
    value["unique_links"] = len(hrefs)
    value["href_set_sha256"] = hashlib.sha256("\n".join(sorted(hrefs)).encode()).hexdigest()
    value["page"] = safe_url(client.page.url, client.source_url)
    for button in value["more"]:
        button["href"] = safe_url(button["href"], client.page.url) if button["href"] else None
    value["next_hrefs"] = [safe_url(href, client.page.url) for href in value["next_hrefs"]]
    return value, hrefs


async def probe_rgo(client, cfg):
    page = client.page
    started = time.monotonic()
    events = []
    omitted = [0]
    def response(res):
        if urlsplit(res.url).hostname != client.host or res.request.resource_type not in ("document", "xhr", "fetch"):
            return
        event = {"path": urlsplit(res.url).path[:240], "status": res.status,
                 "kind": res.request.resource_type,
                 "seconds": round(time.monotonic() - started, 3)}
        if len(events) < 80:
            events.append(event)
        else:
            omitted[0] += 1
    def failed(req):
        if urlsplit(req.url).hostname == client.host and req.resource_type in ("document", "xhr", "fetch"):
            if len(events) < 80:
                events.append({"kind": req.resource_type, "seconds": round(time.monotonic() - started, 3),
                               **error_record(RuntimeError(req.failure or "request_failed"), "native_request", req.url)})
            else:
                omitted[0] += 1
    page.on("response", response)
    page.on("requestfailed", failed)
    await client.read(cfg["url"], render=True)
    before, before_links = await rgo_snapshot(client)
    all_links = set(before_links)
    emit("RGO_INITIAL", {"snapshot": before, "network": events[:]})
    reason = "click_limit_reached"
    for index in range(1, 31):
        if not before["more"] or not before["more"][0]["visible"]:
            reason = "native_more_absent_or_hidden"
            break
        if before["more"][0]["disabled"]:
            reason = "native_more_disabled"
            break
        event_start = len(events)
        click_started = time.monotonic()
        await page.locator(".pagination-more .btn").first.click(timeout=5000)
        await page.wait_for_timeout(1500)
        after_short, short_links = await rgo_snapshot(client)
        short_seconds = round(time.monotonic() - click_started, 3)
        late, late_links = after_short, short_links
        waited = False
        timed_out = False
        refused = any(e.get("status", 0) >= 400 for e in events[event_start:])
        if not short_links.difference(before_links) and not refused:
            waited = True
            remaining_ms = min(10000, int((client.deadline - time.monotonic() - 5) * 1000))
            if remaining_ms <= 0:
                raise RuntimeError("source_time_budget_reached")
            try:
                await page.wait_for_function(RGO_CHANGED, arg="\n".join(sorted(before_links)), timeout=remaining_ms)
            except BrowserTimeout:
                timed_out = True
            late, late_links = await rgo_snapshot(client)
        added = late_links.difference(before_links)
        all_links.update(short_links)
        all_links.update(late_links)
        emit("RGO_STEP", {
            "click": index, "before": before, "after_1500ms": after_short,
            "short_seconds": short_seconds, "additional_wait": waited,
            "additional_wait_timed_out": timed_out,
            "after_wait": late, "total_seconds": round(time.monotonic() - click_started, 3),
            "added_unique_links": len(added), "removed_unique_links": len(before_links - late_links),
            "union_unique_links": len(all_links), "network": events[event_start:],
        })
        before, before_links = late, late_links
        if refused or any(e.get("status", 0) >= 400 for e in events[event_start:]):
            reason = "native_request_http_failure"
            break
        if not added:
            reason = "no_new_links_after_bounded_wait"
            break
    emit("RGO_END", {"reason": reason, "last_snapshot": before,
                     "union_unique_links": len(all_links), "omitted_network_events": omitted[0]})


async def probe_hse(client, cfg):
    from hse_alumni import blocks
    raw = await client.read(cfg["url"], render=True)
    soup = BeautifulSoup(raw, "html.parser")
    roots = soup.select(".post__text.builder_content")
    parsed = blocks(raw)
    emit("HSE_META", {"root_count": len(roots), "native_blocks": len(parsed),
                      "raw_sha256": hashlib.sha256(raw.encode()).hexdigest()})
    for anchor in ("skyeng", "skillcup", "academiya"):
        owned = [block for block in parsed if block["anchor"] == anchor]
        card_links = soup.select(".fa-person__name[href]")
        emit("HSE_ANCHOR", {
            "anchor": anchor,
            "source_card_exists": any(urlsplit(urljoin(cfg["url"], node["href"])).fragment == anchor for node in card_links),
            "name_anchor_count": len(soup.find_all("a", attrs={"name": anchor})),
            "id_anchor_count": len(soup.find_all(id=anchor)),
            "block_count": len(owned),
            "detail_state": owned[0]["detail_state"] if len(owned) == 1 else None,
            "body_chars": len(owned[0]["body"]) if len(owned) == 1 else None,
        })


async def probe_flystation(client, cfg):
    from content_discovery import clean_dom
    for rendered in (False, True):
        raw = await client.read(cfg["url"], render=rendered)
        soup = clean_dom(raw)
        roots = soup.select("section.promotions")
        emit("FLYSTATION_COUNTS", {
            "rendered": rendered, "root_count": len(roots),
            "panel_count": sum(len(root.select(".promotions__slider-item-text")) for root in roots),
            "document_panel_count": len(soup.select(".promotions__slider-item-text")),
            "root_child_nodes": [len(root.find_all(True)) for root in roots[:4]],
            "raw_bytes": len(raw.encode()), "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        })


def probe_vtb(cfg, deadline, now):
    from html_text import html_text
    from recovered_sources import ScopedReader, scoped_bank_sections, parse_bank_page
    with ScopedReader(cfg, {}, deadline) as reader:
        _, data = reader.read(cfg["url"])
    raw = data.decode("utf-8")
    titles = BeautifulSoup(raw, "html.parser").select("h1")
    emit("VTB_META", {"raw_sha256": hashlib.sha256(data).hexdigest(), "raw_bytes": len(data),
                      "h1_count": len(titles), "title_identity": [html_text(node)[:240] for node in titles[:4]]})
    nodes = scoped_bank_sections(cfg["id"], raw)
    earning = [html_text(node) for node in nodes if html_text(node).startswith("Как начисляются мили")]
    emit("VTB_EARNING", {"section_count": len(earning),
                         "text": earning[0][:4000] if len(earning) == 1 else None,
                         "text_chars": len(earning[0]) if len(earning) == 1 else None,
                         "truncated": len(earning[0]) > 4000 if len(earning) == 1 else None})
    try:
        parse_bank_page(cfg["id"], raw, now)
        emit("VTB_PARSE", {"status": "ok", "record_count": 1})
    except Exception as exc:
        emit("VTB_PARSE", {"status": "error", **error_record(exc, "parse", cfg["url"])})


async def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SOURCES:
        raise SystemExit("expected_one_configured_probe_source")
    sid = sys.argv[1]
    configs = json.loads((ROOT / "loyalty/sources_normalized.json").read_text())
    cfg = next(item for item in configs if item["id"] == sid)
    # These four sources use the collector's default 420s or an explicit budget.
    budget = cfg.get("timeout_seconds", 420)
    now = datetime.now(timezone.utc).isoformat()
    deadline = time.monotonic() + budget
    emit("PROBE_START", {"source_id": sid, "observed_at": now,
                         "budget_seconds": budget, "commit": os.environ.get("GITHUB_SHA")})
    try:
        async with asyncio.timeout(budget):
            if sid == "af_vtb_rules":
                await asyncio.to_thread(probe_vtb, cfg, deadline, now)
            else:
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    browser._loyalty_read_locks = {}
                    try:
                        client = PublicSource(browser, cfg["url"])
                        client.deadline = deadline
                        async with client:
                            probe = {"rgo": probe_rgo, "hse_alumni": probe_hse,
                                     "flystation_public": probe_flystation}[sid]
                            await within_source_budget(client, lambda: probe(client, cfg))
                    finally:
                        await browser.close()
    except Exception as exc:
        emit("PROBE_ERROR", {"source_id": sid, **error_record(exc, "probe", cfg["url"])})
        return 1
    emit("PROBE_DONE", {"source_id": sid})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
