import math
import statistics


MIN_TEMPORAL_SAMPLES = 12


def _safe_mean(values):
    return statistics.mean(values) if values else 0.0


def _safe_std(values):
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _slope(values):
    """
    Simple least-squares slope over equally spaced samples.
    Positive = rising trend
    Negative = falling trend
    """
    n = len(values)
    if n < 2:
        return 0.0

    x = list(range(n))
    x_mean = statistics.mean(x)
    y_mean = statistics.mean(values)

    numerator = sum(
        (xi - x_mean) * (yi - y_mean)
        for xi, yi in zip(x, values)
    )

    denominator = sum(
        (xi - x_mean) ** 2
        for xi in x
    )

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _ewma(values, alpha=0.30):
    """
    Exponentially weighted moving average.
    Recent observations receive more weight.
    """
    if not values:
        return 0.0

    value = values[0]

    for observation in values[1:]:
        value = alpha * observation + (1 - alpha) * value

    return value


def _normalized(value, scale):
    if abs(scale) < 1e-9:
        return 0.0
    return value / scale


def extract_series_features(values):
    """
    Extract temporal characteristics from one telemetry series.

    Expected ordering:
        oldest -> newest
    """

    if len(values) < MIN_TEMPORAL_SAMPLES:
        return {
            "ready": False,
            "sample_count": len(values),
        }

    previous = values[-2]
    latest = values[-1]

    baseline = values[:-1]

    mean = _safe_mean(baseline)
    std = _safe_std(baseline) or 1e-6

    delta = latest - previous
    z_score = abs(latest - mean) / std

    recent_window = values[-6:]
    trend = _slope(recent_window)

    ewma_value = _ewma(baseline)
    ewma_deviation = abs(latest - ewma_value) / std

    recent_changes = [
        abs(values[i] - values[i - 1])
        for i in range(1, len(values))
    ]

    typical_change = _safe_mean(recent_changes[:-1]) or 1e-6
    rate_change_score = abs(delta) / typical_change

    recent_mean = _safe_mean(values[-5:])
    older_mean = _safe_mean(values[-10:-5])

    persistence = abs(recent_mean - older_mean) / std

    volatility_recent = _safe_std(values[-6:])
    volatility_baseline = _safe_std(values[:-6]) or 1e-6

    volatility_ratio = volatility_recent / volatility_baseline

    return {
        "ready": True,
        "sample_count": len(values),

        "latest": latest,
        "mean": mean,
        "std": std,

        "delta": delta,
        "z_score": z_score,

        "trend": trend,

        "ewma": ewma_value,
        "ewma_deviation": ewma_deviation,

        "rate_change_score": rate_change_score,

        "persistence": persistence,

        "volatility_ratio": volatility_ratio,
    }


def score_temporal_features(features):
    """
    Convert temporal behavior into a conservative 0-100 anomaly score.

    Scores should stay low during normal stochastic operation and rise
    strongly when several temporal characteristics become abnormal.
    """

    if not features.get("ready"):
        return 0.0

    z = features["z_score"]
    ewma_dev = features["ewma_deviation"]
    rate = features["rate_change_score"]
    persistence = features["persistence"]
    volatility = features["volatility_ratio"]

    score = 0.0

    # Instantaneous deviation
    score += min(z / 6.0, 1.0) * 25.0

    # Recent-state deviation
    score += min(ewma_dev / 5.0, 1.0) * 20.0

    # Sudden rate change
    score += min(rate / 7.0, 1.0) * 20.0

    # Persistent movement matters more than a single spike
    score += min(persistence / 4.0, 1.0) * 25.0

    # Volatility contributes, but should rarely dominate.
    excess_volatility = max(0.0, volatility - 1.5)
    score += min(excess_volatility / 4.0, 1.0) * 10.0

    return round(min(score, 100.0), 2)
def analyze_series(values):
    """
    Run the complete temporal analysis pipeline for one telemetry channel.
    """
    features = extract_series_features(values)

    return {
        "features": features,
        "score": score_temporal_features(features),
    }

def analyze_node(rows):
    """
    Analyze all telemetry channels for a node.

    rows must contain:
        voltage
        current
        temp

    ordered oldest -> newest
    """

    result = {}

    for field in ("voltage", "current", "temp"):
        values = [float(row[field]) for row in rows]

        result[field] = analyze_series(values)

    ready_scores = [
        result[field]["score"]
        for field in result
        if result[field]["features"].get("ready")
    ]

    overall = max(ready_scores) if ready_scores else 0.0

    return {
        "channels": result,
        "score": round(overall, 2),
    }