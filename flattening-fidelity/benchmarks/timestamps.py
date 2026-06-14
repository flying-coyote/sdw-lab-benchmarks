"""Failure mode 3 — floating (zone-naive) timestamps break correlation.

A cross-source attack chain can only be reconstructed by true event time. If one
source normalised to a zone-naive local wall-clock and another to a different
local zone, a "these events happened within 5 minutes" correlation window is
built from clocks that never agreed. We plant chains whose three events (EDR →
firewall → auth) are truly within a few minutes of each other in UTC, assign the
sources realistic timezone offsets, and load the corpus two ways:

  * floating : each event's local wall-clock, offset dropped, all compared as if
               in one zone (the lazy-pipeline default)
  * utc      : each event's true UTC instant, offset preserved

Then we run the same correlation query against both and score it against the
known chains. Cross-zone chains fall outside the window under the floating store
and are silently lost; same-zone chains survive either way.
"""

from common import new_rng, connect

WINDOW_SECONDS = 300  # "events within 5 minutes"
# Realistic hour-scale offsets (seconds). Frankfurt = +1h, Virginia = -5h, etc.
ZONES = {"UTC": 0, "Frankfurt": 3600, "Virginia": -5 * 3600, "Singapore": 8 * 3600}
SOURCES = ("edr", "firewall", "auth")


def _gen_corpus(n_chains: int, cross_zone_fraction: float, seed: int):
    """Return (events, chain_truth).

    events: list of dicts with true_utc, floating_local, source, chain_id
    chain_truth: {chain_id: [(source, true_utc), ...] in true order}
    """
    rng = new_rng(seed)
    events = []
    truth = {}
    base = 0  # seconds from an arbitrary fixed anchor; absolute value irrelevant

    for c in range(n_chains):
        # Three events truly 60–120s apart, well inside a 5-minute window in UTC.
        t0 = base + c * 10_000  # space chains apart so only intra-chain matters
        offsets_within = [0, rng.randint(45, 110), rng.randint(120, 240)]
        true_times = [t0 + o for o in offsets_within]

        cross = rng.random() < cross_zone_fraction
        if cross:
            # Each source in a different real timezone.
            zone_names = rng.sample(list(ZONES), 3)
        else:
            # All three sources in one zone (offset cancels out under floating).
            z = rng.choice(list(ZONES))
            zone_names = [z, z, z]

        chain_rows = []
        for src, tt, zn in zip(SOURCES, true_times, zone_names):
            floating_local = tt + ZONES[zn]  # local wall-clock, offset baked in then "forgotten"
            events.append(
                {
                    "chain_id": c,
                    "source": src,
                    "true_utc": tt,
                    "floating_local": floating_local,
                    "zone": zn,
                    "cross_zone": cross,
                }
            )
            chain_rows.append((src, tt))
        truth[c] = sorted(chain_rows, key=lambda r: r[1])
    return events, truth


def _score(events, truth, time_key):
    """Correlate each chain's events by `time_key` and score window + order."""
    by_chain = {}
    for e in events:
        by_chain.setdefault(e["chain_id"], []).append((e["source"], e[time_key]))

    correlated = 0  # all three events fall inside one 5-minute window
    order_correct = 0  # reconstructed order matches true order (among correlated)
    for cid, rows in by_chain.items():
        times = [t for _, t in rows]
        spread = max(times) - min(times)
        if spread <= WINDOW_SECONDS:
            correlated += 1
            reconstructed = [s for s, _ in sorted(rows, key=lambda r: r[1])]
            true_order = [s for s, _ in truth[cid]]
            if reconstructed == true_order:
                order_correct += 1
    total = len(truth)
    return {
        "chains": total,
        "correlated_within_window": correlated,
        "correlation_recall": round(correlated / total, 4) if total else None,
        "order_correct_of_correlated": order_correct,
    }


def run(scales=((200, 0.5), (1000, 0.5)), seed=303):
    out = {
        "name": "floating_timestamp_correlation_break",
        "title": "Floating (zone-naive) timestamps → cross-zone correlation silently lost",
        "scales": [],
    }
    for (n_chains, cross_frac) in scales:
        events, truth = _gen_corpus(n_chains, cross_frac, seed=seed)
        n_cross = sum(1 for e in events if e["cross_zone"]) // len(SOURCES)
        out["scales"].append(
            {
                "n_chains": n_chains,
                "cross_zone_chains": n_cross,
                "same_zone_chains": n_chains - n_cross,
                "utc_normalized": _score(events, truth, "true_utc"),
                "floating_local": _score(events, truth, "floating_local"),
            }
        )
    return out
