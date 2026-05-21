"""
Read src/lib/venues.ts and build a venue name -> address lookup.

Scrapers call lookup_venue_address(name) and get back a street address
if the venue is known. Single source of truth lives in venues.ts; this
module just parses it.
"""
import re
import os
from functools import lru_cache


VENUES_TS_PATH = os.path.join(os.path.dirname(__file__), "src", "lib", "venues.ts")


@lru_cache(maxsize=1)
def _load_venue_table():
    """
    Parse venues.ts into a dict: lowercased name/alias -> {name, address}.
    Cached for the life of the process.
    """
    try:
        with open(VENUES_TS_PATH) as f:
            text = f.read()
    except IOError:
        return {}

    table = {}
    # Walk venue-by-venue: find each `name: "..."` and look ahead within
    # the same { ... } block for `address: "..."` and optional matchAliases.
    name_iter = re.finditer(r"name:\s*\"([^\"]+)\"", text)
    matches = list(name_iter)
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        # Block ends at next name: or end of text
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]

        addr_m = re.search(r"address:\s*\"([^\"]+)\"", block)
        if not addr_m:
            continue
        address = addr_m.group(1)

        keys = [name.lower()]
        alias_m = re.search(r"matchAliases:\s*\[([^\]]+)\]", block)
        if alias_m:
            for a in re.findall(r"\"([^\"]+)\"", alias_m.group(1)):
                keys.append(a.lower())

        for k in keys:
            table[k] = {"name": name, "address": address}
    return table


def lookup_venue_address(location_str):
    """
    Given an event's location string (often just the venue name, possibly
    embedded in a longer string), return (venue_name, address) if known,
    else (None, None).

    Matches in priority order:
      1. Exact match (lowercased)
      2. Table key found inside location_str (longest key wins to avoid
         "spur" matching "Snowbird Spur Trail" before "the spur bar").
    """
    if not location_str:
        return None, None
    table = _load_venue_table()
    loc_lo = location_str.lower()

    # Exact match
    if loc_lo in table:
        v = table[loc_lo]
        return v["name"], v["address"]

    # Contains match: prefer the longest matching key (more specific)
    best_key = None
    for key in table:
        if key in loc_lo:
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if best_key:
        v = table[best_key]
        return v["name"], v["address"]
    return None, None


def lookup_venue_by_address(address_str):
    """
    Given an address string, return (venue_name, canonical_address) if a
    known venue lives at that address, else (None, None).

    Useful for scrapers like Mountain Town Music that publish only an
    address (e.g. "1361 Woodside Ave") without the venue name.
    """
    if not address_str:
        return None, None
    table = _load_venue_table()
    raw_addr = address_str.strip().lower()

    def _norm(s):
        # Strip punctuation that varies between sources (periods in "E.", commas)
        # and collapse whitespace so "3925 e. snowbasin rd" matches "3925 e snowbasin rd"
        s = re.sub(r"[.,]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        # Normalize common street suffix abbreviations so "Park Avenue" matches "Park Ave"
        for full, abbr in [
            ("avenue", "ave"), ("street", "st"), ("boulevard", "blvd"),
            ("road", "rd"), ("drive", "dr"), ("lane", "ln"),
            ("place", "pl"), ("court", "ct"), ("highway", "hwy"),
        ]:
            s = re.sub(rf"\b{full}\b", abbr, s)
        return s

    addr_lo = _norm(raw_addr)

    # Inputs that don't start with a street number are city-level strings
    # (e.g. "Jackson, WY"). Allow exact alias match only.
    if not re.match(r"^\d+\s+\w", addr_lo):
        for key, v in table.items():
            if addr_lo == _norm(key):
                return v["name"], v["address"]
        return None, None

    # Street-level address — match by prefix on normalized canonical
    for key, v in table.items():
        canonical = _norm(v["address"].lower())
        if canonical.startswith(addr_lo):
            return v["name"], v["address"]
        # Also check matchAliases (the value's address may be longer than the alias)
        # Aliases include things like "3925 E. Snowbasin Rd" stored as alias keys
        if addr_lo == _norm(key):
            return v["name"], v["address"]
    return None, None


if __name__ == "__main__":
    table = _load_venue_table()
    print(f"Loaded {len(table)} venue entries")
    for sample in ["The Spur Bar and Grill", "egyptian theatre", "Deer Valley Resort", "Kimball Arts Center", "Side Door"]:
        name, addr = lookup_venue_address(sample)
        print(f"  {sample!r} -> {name}, {addr}")
