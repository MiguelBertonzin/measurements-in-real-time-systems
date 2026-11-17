"""Métricas temporais puras. Tempos e deadlines internos são inteiros em ns."""

from decimal import Decimal
import statistics


def ns(value):
    scaled = Decimal(str(value)) * 1000
    if scaled != scaled.to_integral_value():
        raise ValueError("Tempo deve ser representável em nanossegundos inteiros")
    return int(scaled)


def us(value):
    return value / 1000


def windows(losses, k):
    if not 1 <= k <= len(losses):
        raise ValueError("Janela fora dos limites da amostra")
    current = sum(losses[:k])
    counts = [current]
    for i in range(k, len(losses)):
        current += losses[i] - losses[i - k]
        counts.append(current)
    worst = max(counts)
    first = counts.index(worst) + 1  # Índices de ativação começam em 1.
    return {"k": k, "m": k - worst, "perdas_maximas": worst,
            "primeira_pior_janela_inicio": first,
            "primeira_pior_janela_fim": first + k - 1,
            "quantidade_piores_janelas": counts.count(worst), "contagens": counts}


def analyze(times, deadline, ks=(10, 20, 50)):
    if not times or any(t < 0 for t in times) or deadline < 0:
        raise ValueError("Amostra vazia ou tempos negativos")
    # Cumpre em R <= D; igualdade nunca é tratada como perda.
    losses = [int(t > deadline) for t in times]
    positions = [i + 1 for i, lost in enumerate(losses) if lost]
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    runs = []
    for position in positions:
        if runs and runs[-1]["fim"] == position - 1:
            runs[-1]["fim"] = position
            runs[-1]["tamanho"] += 1
        else:
            runs.append({"inicio": position, "fim": position, "tamanho": 1})
    ordered = sorted(times)
    # Descartar floor(N/100) maiores valores, sem interpolar percentis.
    discarded = len(times) // 100
    return {
        "n": len(times), "deadline_us": us(deadline),
        "minimo_us": us(min(times)), "media_us": us(statistics.mean(times)),
        "mediana_us": us(statistics.median(times)),
        "desvio_padrao_populacional_us": us(statistics.pstdev(times)),
        "hwm_100_us": us(max(times)), "hwm_99_us": us(ordered[len(times) - discarded - 1]),
        "hwm_99_descartadas": discarded,
        "perdas": sum(losses), "cumpridas": len(times) - sum(losses),
        "percentual_no_prazo": 100 * (len(times) - sum(losses)) / len(times),
        "skip_factor": min(gaps) if gaps else None,
        "perdas_isoladas": sum(r["tamanho"] == 1 for r in runs),
        "quantidade_rajadas": sum(r["tamanho"] >= 2 for r in runs),
        "perdas_em_rajadas": sum(r["tamanho"] for r in runs if r["tamanho"] >= 2),
        "maior_rajada": max((r["tamanho"] for r in runs if r["tamanho"] >= 2), default=0),
        "maior_sequencia_perdas": max((r["tamanho"] for r in runs), default=0),
        "ativacoes_perdidas": positions, "distancias": gaps, "sequencias": runs,
        "janelas": {k: windows(losses, k) for k in ks},
    }


def compact(result):
    omitted = {"ativacoes_perdidas", "distancias", "sequencias", "janelas"}
    return {**{k: v for k, v in result.items() if k not in omitted},
            "janelas": {k: {a: b for a, b in v.items() if a != "contagens"}
                        for k, v in result["janelas"].items()}}


def minimum_deadline(times, m, k):
    """Menor D não negativo que satisfaz (m,k) em todas as janelas observadas.

    Em uma janela, o m-ésimo menor tempo é o mínimo necessário para m acertos.
    O máximo desses limiares garante que TODAS as janelas sejam satisfeitas.
    Não é uma garantia para ativações futuras.
    """
    if not 0 <= m <= k <= len(times) or k == 0:
        raise ValueError("Parâmetros (m,k) inválidos")
    if m == 0:
        return 0
    return max(sorted(times[i:i + k])[m - 1] for i in range(len(times) - k + 1))


def accumulated_max(times):
    best = -1
    result = []
    for value in times:
        best = max(best, value)
        result.append(best)
    return result
