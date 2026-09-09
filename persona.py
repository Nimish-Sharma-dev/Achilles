import statistics


PERSONA_CACHE={}

PERSONA_MIN_SAMPLES = 30


def _mean(values):
    return statistics.mean(values) if values else 0.0


def _std(values):
    if len(values) < 2:
        return 1e-6
    return statistics.pstdev(values) or 1e-6


def _mean_delta(values):
    if len(values) < 2:
        return 0.0

    deltas = [
        abs(values[i] - values[i - 1])
        for i in range(1, len(values))
    ]

    return _mean(deltas)


def build_persona(rows):
    """
    Learn normal behavior for one device from historical telemetry.
    Rows must be oldest -> newest.
    """

    if len(rows) < PERSONA_MIN_SAMPLES:
        return {
            "ready": False,
            "sample_count": len(rows),
        }

    persona = {
        "ready": True,
        "sample_count": len(rows),
        "channels": {},
    }

    for field in ("voltage", "current", "temp"):
        values = [float(row[field]) for row in rows]

        persona["channels"][field] = {
            "mean": _mean(values),
            "std": _std(values),
            "mean_delta": _mean_delta(values),
        }

    return persona


def score_against_persona(persona, recent_rows):
    """
    Compare recent behavior against the learned per-device baseline.
    Returns a 0-100 persona deviation score.
    """

    if not persona.get("ready") or not recent_rows:
        return {
            "score": 0.0,
            "dominant_channel": None,
            "channel_scores": {},
        }

    channel_scores = {}

    for field in ("voltage", "current", "temp"):
        baseline = persona["channels"][field]

        recent_values = [
            float(row[field])
            for row in recent_rows
        ]

        recent_mean = _mean(recent_values)
        mean_deviation = abs(
            recent_mean - baseline["mean"]
        ) / baseline["std"]

        peak_deviation = max(
            abs(value - baseline["mean"]) / baseline["std"]
            for value in recent_values
        )

        recent_delta = _mean_delta(recent_values)

        expected_delta = max(
            baseline["mean_delta"],
            1e-6,
        )

        delta_ratio = recent_delta / expected_delta

        mean_score = min(mean_deviation / 5.0, 1.0) * 35.0
        peak_score = min(peak_deviation / 6.0, 1.0) * 45.0
        delta_score = min(
            max(delta_ratio - 1.0, 0.0) / 5.0,
            1.0,
        ) * 20.0

        channel_scores[field] = round(
            min(
                mean_score + peak_score + delta_score,
                100.0,
            ),
            2,
        )

    dominant_channel = max(
        channel_scores,
        key=channel_scores.get,
    )

    return {
        "score": channel_scores[dominant_channel],
        "dominant_channel": dominant_channel,
        "channel_scores": channel_scores,
    }

def get_or_build_persona(node_id, baseline_rows):
    """
    Build a device persona once from known-normal telemetry and
    keep that baseline fixed during runtime.
    """

    if node_id not in PERSONA_CACHE:
        persona = build_persona(baseline_rows)

        if persona.get("ready"):
            PERSONA_CACHE[node_id] = persona
            print(
                f"[PERSONA] Learned baseline for {node_id} "
                f"from {len(baseline_rows)} samples"
            )

    return PERSONA_CACHE.get(
        node_id,
        {
            "ready": False,
            "sample_count": len(baseline_rows),
        },
    )
