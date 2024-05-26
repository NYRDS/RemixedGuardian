def floodScore(s: str) -> int:
    score = 0
    score += s.count("\n")
    stats = {}
    words = s.split()
    for word in words:
        stats[word] = stats.get(word, 0) + 1

    for k, v in stats.items():
        if v >= len(words) / 10:
            score += v
        else:
            score -= v

    return score
