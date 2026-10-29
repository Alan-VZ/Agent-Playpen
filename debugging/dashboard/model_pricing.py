"""Display-only model rates, with provider identity, units, and provenance intact.

Public price data never receives credentials or prompts. Reference estimates are
not account quotes, and missing/variable prices must never become zero prices.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import threading
import time
from urllib.parse import urljoin, urlsplit

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
REFERENCE_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
REFERENCE_PAGE = "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json"
OFFICIAL_URLS = {
    "openrouter": "https://openrouter.ai/models",
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "groq": "https://groq.com/pricing/",
    "together": "https://www.together.ai/pricing",
    "azure_openai": "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/",
    "lm_studio": "https://lmstudio.ai/",
    "ollama": "https://ollama.com/",
}
REFERENCE_PROVIDERS = {"openai": "openai", "anthropic": "anthropic", "groq": "groq", "together_ai": "together"}
OFFICIAL_PAGES = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "groq": "https://console.groq.com/docs/models",
    "together": "https://docs.together.ai/docs/serverless/models",
}
_cache = {}
_locks = {name: threading.Lock() for name in ("openrouter", "reference", *("official_" + backend for backend in OFFICIAL_PAGES))}


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rate(value, multiplier=1):
    """Finite nonnegative USD rates only; -1 means variable, not free."""
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value)) * multiplier
        if not number.is_finite() or number < 0 or number > Decimal("1000000000"):
            return None
        converted = float(number)
        return None if number > 0 and converted == 0 else converted
    except (InvalidOperation, ValueError):
        return None


def fetch_public_text(url):
    parsed = urlsplit(url)
    if url not in {REFERENCE_URL, *OFFICIAL_PAGES.values()} and not (parsed.scheme == "https" and parsed.netloc == "openrouter.ai"
                                    and parsed.path == "/api/v1/models" and len(parsed.query) <= 2000):
        raise ValueError("Unsupported public price source")
    # Explicit headers: no saved credentials, cookies, or agent input.
    with requests.Session() as session:
        session.trust_env = False  # no .netrc credentials, environment auth, or proxy credentials
        with session.get(url, headers={"Accept": "application/json, text/html"}, timeout=15,
                         allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise RuntimeError("Public pricing source unavailable")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError("Price catalog exceeds size limit")
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8")


def fetch_public_json(url):
    data = json.loads(fetch_public_text(url))
    if not isinstance(data, dict):
        raise ValueError("Unexpected public price catalog")
    return data


def _money_cell(text):
    if text.strip().lower() == "free":
        return 0.0
    normalized = text.strip().replace(",", "")
    if normalized.count("$") != 1:
        return None  # do not silently select one endpoint of a range
    match = re.match(r"\$([0-9]+(?:\.[0-9]+)?)", normalized)
    return rate(match.group(1)) if match else None


def _official_price(backend, input_rate, output_rate, cache_read=None, cache_write=None, note=None):
    price = unknown_price(backend)
    price.update(input_per_million=rate(input_rate), output_per_million=rate(output_rate),
                 cache_read_per_million=rate(cache_read), cache_write_per_million=rate(cache_write),
                 status="published" if input_rate is not None or output_rate is not None else "account_specific",
                 source_label="Official pricing page", source_url=OFFICIAL_PAGES[backend],
                 notes=["Published base text rates; account terms, processing tiers, long context, cache duration, tools, and media can change the bill."])
    if note:
        price["notes"].append(note)
    return price


def parse_official_page(backend, html):
    """Parse explicit IDs/units only. Layout changes fail closed to other sources."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    prices = {}
    if backend == "openai":
        for island in soup.find_all("astro-island", attrs={"component-export": "TextTokenPricingTables"}):
            try:
                props = json.loads(island.get("props", "{}"))
                if props.get("tier") != [0, "standard"]:
                    continue  # never mix Batch/Flex/Priority with standard prices
                for encoded in props["rows"][1]:
                    raw_cells = encoded[1]
                    if not isinstance(raw_cells, list) or not all(isinstance(cell, list) and len(cell) == 2 and cell[0] == 0 for cell in raw_cells):
                        continue
                    cells = [cell[1] for cell in raw_cells]
                    if len(cells) not in {4, 5} or not isinstance(cells[0], str):
                        continue
                    model_id = cells[0].split(" (", 1)[0]
                    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", model_id):
                        continue
                    prices[model_id] = _official_price(backend, rate(cells[1]), rate(cells[-1]), rate(cells[2]), rate(cells[3]) if len(cells) == 5 else None,
                        "Standard processing. " + ("Rate condition: " + cells[0] + ". " if " (" in cells[0] else "") + "Cache writes shown use the listed base duration; longer retention can cost more.")
            except (ValueError, KeyError, TypeError, IndexError):
                continue
        return prices
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [cell.get_text(" ", strip=True).lower() for cell in rows[0].find_all(["th", "td"])]
        if backend == "together" and "api model string" in headers:
            indexes = {name: next((i for i, text in enumerate(headers) if text.startswith(prefix)), None)
                       for name, prefix in (("id", "api model string"), ("input", "input pricing (per 1m tokens)"), ("output", "output pricing (per 1m tokens)"), ("cache", "cached input pricing (per 1m tokens)"))}
            if indexes["input"] is None or indexes["output"] is None:
                continue
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) != len(headers):
                    continue
                text = [cell.get_text(" ", strip=True) for cell in cells]
                model_id = text[indexes["id"]]
                if model_id and len(model_id) <= 500:
                    prices.setdefault(model_id, _official_price(backend, _money_cell(text[indexes["input"]]), _money_cell(text[indexes["output"]]),
                        _money_cell(text[indexes["cache"]]) if indexes["cache"] is not None else None))
        elif backend == "groq" and any("model id" in text for text in headers) and any("1m tokens" in text for text in headers):
            price_index = next(i for i, text in enumerate(headers) if "1m tokens" in text)
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) <= price_index:
                    continue
                anchor = cells[0].find("a", href=True)
                href = anchor["href"] if anchor else ""
                if not href.startswith("/docs/model/"):
                    continue
                model_id = href[len("/docs/model/"):]
                text = cells[price_index].get_text(" ", strip=True)
                if "contact sales" in text.lower():
                    prices[model_id] = _official_price(backend, None, None, note="The official model page says Contact Sales; an old reference rate is not substituted.")
                    continue
                matches = dict((kind.lower(), rate(number)) for number, kind in re.findall(r"\$([0-9.]+)\s*(input|output)", text, re.I))
                if matches:
                    prices[model_id] = _official_price(backend, matches.get("input"), matches.get("output"))
        elif backend == "anthropic" and "base tokens" in headers:
            for row in rows[2:]:
                cells = row.find_all("td")
                if len(cells) < 6:
                    continue
                anchor = cells[0].find("a", href=True)
                if not anchor:
                    continue
                match = re.search(r"/models/([a-z0-9-]+)(?:/|$)", anchor["href"])
                if not match:
                    continue
                slug = match.group(1)
                model_id = slug if slug.startswith("claude-") else "claude-" + slug
                text = [cell.get_text(" ", strip=True) for cell in cells]
                prices[model_id] = _official_price(backend, _money_cell(text[1]), _money_cell(text[2]), _money_cell(text[5]), _money_cell(text[3]),
                    "Cache write is the 5-minute rate; 1-hour writes: " + text[4] + ". " + ("Prompt-length tiers apply: " + text[1] if "prompts" in text[1].lower() else ""))
    return prices


def official_index(source):
    return {name: {**price, "fetched_at": source["fetched_at"], "stale": source["stale"]}
            for name, price in source["data"].items() if isinstance(price, dict)
            and isinstance(price.get("status"), str) and price["status"] in {"published", "account_specific"}}


def _load_source(name):
    if name.startswith("official_"):
        backend = name[len("official_"):]
        data = parse_official_page(backend, fetch_public_text(OFFICIAL_PAGES[backend]))
        if not data:
            raise ValueError("Official pricing page layout was not recognized")
        return data
    if name == "reference":
        return fetch_public_json(REFERENCE_URL)
    data = fetch_public_json(OPENROUTER_URL)
    if not isinstance(data.get("data"), list):
        raise ValueError("Unexpected OpenRouter model catalog")
    entries = list(data["data"])
    next_link = data.get("links", {}).get("next")
    visited = {OPENROUTER_URL}
    while next_link:
        if not isinstance(next_link, str) or len(visited) >= 20:
            raise ValueError("Unexpected model catalog pagination")
        url = urljoin(OPENROUTER_URL, next_link)
        if url in visited:
            raise ValueError("Repeated model catalog page")
        page = fetch_public_json(url)  # validates host/path before fetching
        visited.add(url)
        if not isinstance(page.get("data"), list):
            raise ValueError("Unexpected model catalog page")
        entries.extend(page["data"])
        if len(entries) > 20_000:
            raise ValueError("Too many model catalog entries")
        next_link = page.get("links", {}).get("next")
    return {"data": entries}


def snapshot(name, refresh=False):
    """Memory-only cache; a failed refresh preserves explicitly stale old data."""
    with _locks[name]:
        cached = _cache.get(name)
        if cached and not refresh and time.monotonic() < cached["refresh_after"]:
            return cached
        try:
            data = _load_source(name)
            result = {"data": data, "fetched_at": timestamp(), "stale": False,
                      "refresh_after": time.monotonic() + (300 if name == "openrouter" else 3600)}
        except Exception:
            result = {"data": cached["data"] if cached else {},
                      "fetched_at": cached["fetched_at"] if cached else None, "stale": True,
                      "refresh_after": time.monotonic() + 60}
        _cache[name] = result
        return result


def unknown_price(backend):
    local = backend in {"lm_studio", "ollama"}
    azure = backend == "azure_openai"
    return {
        "input_per_million": None, "output_per_million": None, "cache_read_per_million": None,
        "cache_write_per_million": None, "currency": "USD", "unit": "1M text tokens",
        "status": "local" if local else "account_specific" if azure else "unavailable",
        "source_label": "Local / self-hosted" if local else "Account-specific quote" if azure else "Price unavailable",
        "source_url": OFFICIAL_URLS.get(backend), "official_url": OFFICIAL_URLS.get(backend),
        "fetched_at": None, "stale": False,
        "notes": ["No API token tariff reported here; hardware, power, and hosting costs are separate." if local else
                  "Azure prices depend on the deployed model, region, and contract; a deployment name is not a price lookup." if azure else
                  "No exact provider/model price match. Missing prices are not free."], "tiers": [],
    }


def provider_price(backend, entry, fetched_at, stale=False):
    result = unknown_price(backend)
    values = entry.get("pricing")
    if not isinstance(values, dict):
        return result
    if backend == "openrouter":
        fields = {"input_per_million": "prompt", "output_per_million": "completion",
                  "cache_read_per_million": "input_cache_read", "cache_write_per_million": "input_cache_write"}
        factor = 1_000_000
    elif backend == "together" and entry.get("type") in {"chat", "language", "code"}:
        # Together's serverless token price objects use USD per million tokens.
        fields, factor = {"input_per_million": "input", "output_per_million": "output"}, 1
    else:
        return result
    for target, source in fields.items():
        result[target] = rate(values.get(source), factor)
    if result["input_per_million"] is None and result["output_per_million"] is None:
        return result
    result.update(status="published", source_label="Provider catalog", fetched_at=fetched_at, stale=stale,
                  source_url=OPENROUTER_URL if backend == "openrouter" else "https://api.together.xyz/v1/models",
                  notes=["Base text-token rates. Routing, long context, caching, reasoning, media, tools, taxes, and account terms can change the bill."])
    if backend == "openrouter":
        extras = [name for name, value in values.items() if name not in set(fields.values()) and rate(value) not in (None, 0)]
        if extras:
            result["notes"].append("Additional catalog pricing fields: " + ", ".join(extras[:10]) + ". Check the provider for their billing units.")
    elif rate(values.get("hourly")) not in (None, 0):
        result["notes"].append("The catalog includes an hourly charge; token rates alone are not the total cost.")
    return result


class ModelCatalog(list):
    """Keep the existing list-of-names contract while retaining provider prices."""

    def __init__(self, backend, entries, fetched_at=None, stale=False):
        valid = {entry["id"]: entry for entry in entries if isinstance(entry, dict)
                 and isinstance(entry.get("id"), str) and 0 < len(entry["id"]) <= 500}
        super().__init__(sorted(valid))
        self.prices = {name: provider_price(backend, entry, fetched_at or timestamp(), stale) for name, entry in valid.items()}
        self.stale = stale


def reference_index(source):
    """Match provider and exact ID; never borrow another site's or fuzzy prices."""
    result = {}
    for name, entry in source["data"].items():
        if not isinstance(entry, dict) or not isinstance(entry.get("mode"), str) or entry["mode"] not in {"chat", "completion", "responses"}:
            continue
        provider = entry.get("litellm_provider")
        if not isinstance(provider, str):
            continue
        backend = REFERENCE_PROVIDERS.get(provider)
        if not backend or not isinstance(name, str) or len(name) > 500:
            continue
        prefix = provider + "/"
        model_id = name[len(prefix):] if name.startswith(prefix) else name
        if backend == "together" and (model_id.startswith("together-ai-") or "/" not in model_id):
            continue  # aggregate parameter-count categories are not model IDs
        price = unknown_price(backend)
        fields = {"input_per_million": "input_cost_per_token", "output_per_million": "output_cost_per_token",
                  "cache_read_per_million": "cache_read_input_token_cost", "cache_write_per_million": "cache_creation_input_token_cost"}
        for target, key in fields.items():
            price[target] = rate(entry.get(key), 1_000_000)
        if price["input_per_million"] is None and price["output_per_million"] is None:
            continue
        tiers = []
        for key, value in entry.items():
            if key.startswith(("input_cost_per_token_above_", "output_cost_per_token_above_")):
                normalized = rate(value, 1_000_000)
                if normalized is not None:
                    tiers.append({"field": key, "per_million": normalized})
        price.update(status="reference", source_label="Community reference estimate", source_url=REFERENCE_PAGE,
                     fetched_at=source["fetched_at"], stale=source["stale"], tiers=tiers,
                     notes=["Exact provider/model match in LiteLLM's community registry, not a live provider quote. Retrieval time is not the rate's review date. Verify official pricing and account terms."])
        if tiers:
            price["notes"].append("Long-context tier rates exist; the base rate may not apply to a large prompt.")
        result[(backend, model_id)] = price
    return result


def model_details(backend, models):
    published = getattr(models, "prices", {})
    candidates = [name for name in models if published.get(name, {}).get("status") != "published"]
    official = official_index(snapshot("official_" + backend)) if candidates and backend in OFFICIAL_PAGES else {}
    references = reference_index(snapshot("reference")) if any(name not in official for name in candidates) and backend in REFERENCE_PROVIDERS.values() else {}
    return [{"id": name, "backend": backend, "pricing": published.get(name)
             if published.get(name, {}).get("status") == "published" else official.get(name, references.get((backend, name), unknown_price(backend)))}
            for name in models]


def comparison_catalog(refresh=False):
    # Only public sources; never fetch private model catalogs or use saved keys.
    with ThreadPoolExecutor(max_workers=6) as pool:
        router_job = pool.submit(snapshot, "openrouter", refresh)
        reference_job = pool.submit(snapshot, "reference", refresh)
        official_jobs = {backend: pool.submit(snapshot, "official_" + backend, refresh) for backend in OFFICIAL_PAGES}
        router, reference = router_job.result(), reference_job.result()
        official = {backend: job.result() for backend, job in official_jobs.items()}
    catalog = ModelCatalog("openrouter", router["data"].get("data", []), router["fetched_at"], router["stale"])
    rows = model_details("openrouter", catalog)
    other_prices = reference_index(reference)
    for backend, data in official.items():
        other_prices.update({(backend, name): price for name, price in official_index(data).items()})
    rows += [{"backend": backend, "id": name, "pricing": price} for (backend, name), price in other_prices.items()]
    for backend in ("azure_openai", "lm_studio", "ollama"):
        rows.append({"backend": backend, "id": "Account deployment" if backend == "azure_openai" else "Installed / self-hosted models", "pricing": unknown_price(backend)})
    return {"models": rows, "sources": {
        "openrouter": {"fetched_at": router["fetched_at"], "stale": router["stale"]},
        "reference": {"fetched_at": reference["fetched_at"], "stale": reference["stale"]},
        **{"official_" + backend: {"fetched_at": data["fetched_at"], "stale": data["stale"]} for backend, data in official.items()}},
        "message": "Public price comparison, not model availability or an invoice. Community estimates require verification. Azure deployments and local infrastructure need separate pricing."}
