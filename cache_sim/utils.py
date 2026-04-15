def safe_mean(values):
    if not values:
        return float('nan')
    return sum(values) / len(values)
