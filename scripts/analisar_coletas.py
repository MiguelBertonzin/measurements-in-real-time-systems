"""Reproduz tabelas, evidências e gráficos dos experimentos A–D, sem alterar dados brutos."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys

from metricas import accumulated_max, analyze, compact, minimum_deadline, ns, us

ROOT = Path(__file__).resolve().parents[1]
NAMES = {1: "tarefa", 2: "comportamental", 3: "intertarefas", 4: "sistema"}
LABELS = {1: "Tarefa", 2: "Comportamental", 3: "Intertarefas", 4: "Sistema"}
FIXED_D = ns(json.loads((ROOT / "campanha.json").read_text(encoding="utf-8"))["deadline_fixo_us"])
KS = (10, 20, 50)
TARGET = (18, 20)  # Meta ilustrativa explícita, não requisito físico fornecido.


def csvwrite(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def jsonwrite(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def load(stage):
    path = ROOT / "dados" / f"etapa{stage}" / f"etapa{stage}_{NAMES[stage]}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["ativacao", "tempo_us"]:
            raise ValueError(f"Cabeçalho inesperado: {path}")
        rows = list(reader)
    count = 10000 if stage == 4 else 1000
    if [int(row["ativacao"]) for row in rows] != list(range(1, count + 1)):
        raise ValueError(f"Sequência incompleta: {path}")
    times = [ns(row["tempo_us"]) for row in rows]
    if any(value <= 0 for value in times):
        raise ValueError(f"Tempo inválido: {path}")
    folder = path.parent
    record = json.loads((folder / "registro.json").read_text(encoding="utf-8"))
    if hashlib.sha256((folder / "log_original.txt").read_bytes()).hexdigest() != record["sha256_log_original"]:
        raise ValueError(f"Hash do log alterado: {folder}")
    raw = (folder / "log_original.txt").read_bytes()
    if "log_para_analise" in record:
        validated = (folder / record["log_para_analise"]).read_bytes()
        if validated != raw[record["offset_boot_validado_bytes"]:]:
            raise ValueError(f"Sufixo validado diverge do log bruto: {folder}")
        if hashlib.sha256(validated).hexdigest() != record["sha256_log_validado"]:
            raise ValueError(f"Hash do log validado alterado: {folder}")
        log = validated.decode("utf-8-sig")
    else:
        log = raw.decode("utf-8-sig")
    marker = f"COLETA_CSV_INICIO etapa={stage} "
    if stage > 1:
        log = log.split(marker, 1)[1].split("COLETA_CSV_FIM", 1)[0]
    log = log.split("ativacao,tempo_us", 1)[1]
    original_rows = []
    for line in log.strip().splitlines():
        if len(original_rows) == count:
            break
        index, value = line.strip().split(",")
        original_rows.append((int(index), ns(value)))
    if original_rows != list(enumerate(times, 1)):
        raise ValueError(f"CSV diverge do log original: {path}")
    return times, {"csv": str(path.relative_to(ROOT)),
                   "sha256_csv": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "sha256_log": record["sha256_log_original"]}


def evidence(folder, times, result):
    folder.mkdir(parents=True, exist_ok=True)
    jsonwrite(folder / "resumo.json", compact(result))
    positions = result["ativacoes_perdidas"]
    csvwrite(folder / "perdas.csv", ["ativacao", "tempo_us", "excesso_us"],
             ({"ativacao": p, "tempo_us": us(times[p - 1]),
               "excesso_us": us(times[p - 1] - ns(result["deadline_us"]))} for p in positions))
    csvwrite(folder / "distancias.csv", ["perda_anterior", "perda_seguinte", "distancia_ativacoes"],
             ({"perda_anterior": a, "perda_seguinte": b, "distancia_ativacoes": b - a}
              for a, b in zip(positions, positions[1:])))
    csvwrite(folder / "sequencias_perdas.csv", ["inicio", "fim", "tamanho", "tipo"],
             ({**run, "tipo": "isolada" if run["tamanho"] == 1 else "rajada"}
              for run in result["sequencias"]))
    for k, info in result["janelas"].items():
        csvwrite(folder / f"janelas_k{k}.csv", ["inicio", "fim", "perdas", "cumpridas"],
                 ({"inicio": i, "fim": i + k - 1, "perdas": count, "cumpridas": k - count}
                  for i, count in enumerate(info["contagens"], 1)))


def fmt(value, places=3):
    if value is None:
        return "—"
    return f"{value:,.{places}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pair(info):
    return f"({info['m']},{info['k']})"


def mdtable(fields, rows):
    return "\n".join(["| " + " | ".join(fields) + " |",
                       "| " + " | ".join("---" for _ in fields) + " |",
                       *("| " + " | ".join(map(str, row)) + " |" for row in rows)])


from analise_texto import make_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=ROOT / "analises")
    args = parser.parse_args()
    output = args.saida.resolve()
    if output == ROOT / "dados" or ROOT / "dados" in output.parents:
        parser.error("A saída não pode ficar dentro dos dados brutos")
    output.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.ticker import MaxNLocator
    import numpy as np

    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": .18,
                         "savefig.dpi": 180, "pdf.fonttype": 42})
    color, red, gold = "#136f8a", "#c13e37", "#b77a16"
    figures = output / "figuras"
    figures.mkdir(exist_ok=True)
    times, sources, results = {}, {}, {}
    for stage in NAMES:
        times[stage], sources[stage] = load(stage)
        results[stage] = analyze(times[stage], FIXED_D)
        evidence(output / f"etapa{stage}", times[stage], results[stage])
    coverage = json.loads((ROOT / "dados/cobertura/resumo.json").read_text(encoding="utf-8"))
    for stage in NAMES:
        for name in ("main/huffman.c", "main/huffman.h", "sdkconfig"):
            value = (ROOT / f"dados/etapa{stage}/fontes" / name).read_bytes()
            reference = (ROOT / "dados/etapa1/fontes" / name).read_bytes()
            if value != reference:
                raise ValueError(f"Snapshot divergente: etapa{stage}/{name}")
        if hashlib.sha256((ROOT / f"dados/etapa{stage}/fontes/main/huffman.c").read_bytes()).hexdigest() != coverage["sha256"]["main/huffman.c"]:
            raise ValueError("Cobertura não corresponde ao módulo preservado")

    summary_rows = []
    for stage, r in results.items():
        row = {"etapa": stage, "escopo": LABELS[stage], "n": r["n"],
               "cobertura_linha_host": coverage["linhas_percentual"],
               "cobertura_desvio_host": coverage["desvios_tomados_percentual"]}
        for key in ("minimo_us", "media_us", "hwm_100_us", "hwm_99_us", "deadline_us", "percentual_no_prazo", "perdas", "skip_factor", "quantidade_rajadas", "maior_rajada"):
            row[key] = r[key]
        for k in KS:
            row[f"m_k{k}"] = r["janelas"][k]["m"]
        summary_rows.append(row)
    csvwrite(output / "tabela_sintese.csv", list(summary_rows[0]), summary_rows)
    jsonwrite(output / "resultados.json", {stage: compact(r) for stage, r in results.items()})
    equal_n = [{"etapa": stage, **{key: value for key, value in compact(analyze(t[:1000], FIXED_D)).items() if key != "janelas"}}
               for stage, t in times.items()]
    csvwrite(output / "comparacao_primeiras_1000.csv", list(equal_n[0]), equal_n)

    convergence, jumps = [], {}
    for stage, t in times.items():
        acc = accumulated_max(t)
        records = [{"ativacao": i, "tempo_us": us(v), "hwm_acumulado_us": us(h)}
                   for i, (v, h) in enumerate(zip(t, acc), 1)]
        csvwrite(output / f"etapa{stage}/hwm_acumulado.csv", list(records[0]), records)
        jumps[stage] = [row for i, row in enumerate(records) if i == 0 or acc[i] > acc[i - 1]]
        csvwrite(output / f"etapa{stage}/saltos_hwm.csv", list(records[0]), jumps[stage])
        if stage == 4:
            convergence = [{"n": n, "hwm_us": us(acc[n - 1]),
                            "subestimacao_us": us(max(t) - acc[n - 1]),
                            "subestimacao_percentual": 100 * (max(t) - acc[n - 1]) / max(t)}
                           for n in (10, 20, 100, 1000, 10000)]
    csvwrite(output / "convergencia_marcos.csv", list(convergence[0]), convergence)

    margins = []
    base_hwm = max(times[1])
    for percent in (10, 25, 50):
        limit = base_hwm * (100 + percent) // 100
        row = {"margem_percentual": percent, "limite_us": us(limit)}
        for stage in NAMES:
            row[f"etapa{stage}_cobre_hwm"] = max(times[stage]) <= limit
            row[f"etapa{stage}_folga_us"] = us(limit - max(times[stage]))
        row["primeira_etapa_insuficiente"] = next((stage for stage in NAMES if not row[f"etapa{stage}_cobre_hwm"]), None)
        margins.append(row)
    csvwrite(output / "margens_seguranca.csv", list(margins[0]), margins)

    opt = minimum_deadline(times[4], *TARGET)
    # Conferência independente: busca binária nas medições distintas, usando
    # diretamente a contagem de acertos em cada janela, sem estatísticas de ordem.
    candidates = sorted(set(times[4]))
    lo, hi = 0, len(candidates) - 1
    def meets(deadline):
        return max(sum(t > deadline for t in times[4][i:i + TARGET[1]])
                   for i in range(len(times[4]) - TARGET[1] + 1)) <= TARGET[1] - TARGET[0]
    while lo < hi:
        mid = (lo + hi) // 2
        if meets(candidates[mid]):
            hi = mid
        else:
            lo = mid + 1
    assert opt == candidates[lo] and meets(opt)
    previous = candidates[lo - 1] if lo else 0
    assert not meets(previous)
    optimum = {"meta_m": TARGET[0], "meta_k": TARGET[1], "meta_origem": "ilustrativa, escolhida para experimento D",
               "deadline_minimo_us": us(opt), "anterior_observado_us": us(previous),
               "resultado": compact(analyze(times[4], opt)),
               "resultado_anterior": compact(analyze(times[4], previous)),
               "reducao_us": us(max(times[4]) - opt),
               "reducao_percentual": 100 * (max(times[4]) - opt) / max(times[4])}
    jsonwrite(output / "deadline_minimo.json", optimum)
    frontier = [{"m": m, "k": 20, "deadline_minimo_us": us(minimum_deadline(times[4], m, 20))}
                for m in range(1, 21)]
    csvwrite(output / "fronteira_m20.csv", list(frontier[0]), frontier)
    deadlines = [("hwm_etapa1", "HWM etapa 1", base_hwm),
                 ("intermediario", "Intermediário", (base_hwm + ns(results[4]["hwm_99_us"])) // 2),
                 ("hwm99_etapa4", "HWM99 etapa 4", ns(results[4]["hwm_99_us"])),
                 ("fixo", "D fixo", FIXED_D), ("minimo_18_20", "Mínimo (18,20)", opt)]
    alternatives = []
    for stage in (3, 4):
        for slug, label, deadline in deadlines:
            result = analyze(times[stage], deadline)
            alternatives.append({"etapa": stage, "nome": label, "slug": slug, "resultado": result})
            evidence(output / "experimento_d" / f"etapa{stage}" / slug, times[stage], result)
    d_rows = [{"etapa": a["etapa"], "nome": a["nome"],
               **{key: value for key, value in compact(a["resultado"]).items() if key != "janelas"},
               **{f"m_k{k}": a["resultado"]["janelas"][k]["m"] for k in KS}} for a in alternatives]
    csvwrite(output / "experimento_d/resumo.csv", list(d_rows[0]), d_rows)

    with PdfPages(output / "graficos_completos.pdf") as book:
        def save(fig, name):
            fig.savefig(figures / f"{name}.png", bbox_inches="tight")
            fig.savefig(figures / f"{name}.pdf", bbox_inches="tight")
            book.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        for stage, t in times.items():
            r = results[stage]
            values = np.asarray(t, dtype=float) / 1000
            indices = np.arange(1, len(t) + 1)
            fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
            for ax in axes:
                ax.hist(values, bins=50, color=color, alpha=.85, edgecolor="white", linewidth=.25)
                ax.axvline(max(values), color=gold, ls=":", label=f"HWM {max(values):.0f} µs")
                ax.set(xlabel="Tempo de resposta (µs)", ylabel="Ativações")
            axes[0].axvline(us(FIXED_D), color=red, ls="--", label=f"D {us(FIXED_D):.1f} µs")
            axes[0].set_title("Distribuição e deadline fixo")
            axes[0].legend(fontsize=8)
            axes[1].set_title("Ampliação da faixa realmente observada")
            axes[1].set_yscale("log")
            axes[1].set_title("Faixa observada; frequência em escala log")
            axes[1].legend(fontsize=8)
            fig.suptitle(f"Etapa {stage} — {LABELS[stage]} | N={len(t)} | no prazo: {r['percentual_no_prazo']:.2f}%")
            save(fig, f"etapa{stage}_histograma")

            fig, ax = plt.subplots(figsize=(11, 4.2), layout="constrained")
            ax.plot(indices, values, lw=.5, color=color, label="Resposta")
            missed = values > us(FIXED_D)
            ax.scatter(indices[missed], values[missed], s=6, color=red, label="Perda de deadline", zorder=3)
            ax.axhline(us(FIXED_D), ls="--", color=red, label="D fixo")
            ax.axhline(max(values), ls=":", color=gold, label="HWM")
            ax.set(title=f"Etapa {stage} — {LABELS[stage]} | todas as {len(t)} ativações",
                   xlabel="Número da ativação", ylabel="Tempo de resposta (µs)", xlim=(1, len(t)))
            ax.legend(loc="upper right", ncol=2, fontsize=8)
            save(fig, f"etapa{stage}_temporal")

            fig, axes = plt.subplots(3, 1, figsize=(11, 7.5), layout="constrained")
            for ax, k in zip(axes, KS):
                info = r["janelas"][k]
                ax.step(range(1, len(info["contagens"]) + 1), info["contagens"], where="mid", lw=.65, color=color)
                ax.axhline(info["perdas_maximas"], ls="--", color=red, lw=1)
                ax.set(title=f"k={k}: máximo {info['perdas_maximas']} perdas; {pair(info)} observado",
                       ylabel="Perdas na janela", xlim=(1, len(t) - k + 1), ylim=(-.2, max(1, info["perdas_maximas"] + .7)))
                ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            axes[-1].set_xlabel("Ativação inicial da janela deslizante")
            fig.suptitle(f"Etapa {stage} — janelas completas, D={us(FIXED_D):.1f} µs")
            save(fig, f"etapa{stage}_janelas")

        fig, axes = plt.subplots(4, 1, figsize=(11, 9), layout="constrained", sharey=True)
        for ax, stage in zip(axes, NAMES):
            ax.plot(range(1, len(times[stage]) + 1), [us(t) for t in times[stage]], lw=.5, color=color)
            ax.axhline(us(FIXED_D), ls="--", color=red)
            ax.set(title=f"{stage}. {LABELS[stage]} — N={len(times[stage])}", ylabel="Resposta (µs)")
        axes[-1].set_xlabel("Número da ativação (escala horizontal própria por etapa)")
        fig.suptitle("Mesma escala vertical; linha vermelha = deadline fixo")
        save(fig, "comparacao_temporal")

        fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
        for ax, stage in zip(axes.flat, NAMES):
            acc = accumulated_max(times[stage])
            ax.step(range(1, len(acc) + 1), [us(t) for t in acc], where="post", color=color)
            ax.set_xscale("log")
            ax.scatter([row["ativacao"] for row in jumps[stage]], [row["hwm_acumulado_us"] for row in jumps[stage]], s=13, color=red, zorder=3)
            ax.set(title=f"Etapa {stage}: último aumento em n={jumps[stage][-1]['ativacao']}",
                   xlabel="Amostras acumuladas (escala log)", ylabel="HWM acumulado (µs)")
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        fig.suptitle("Convergência observada do HWM — patamar não garante WCRT")
        save(fig, "convergencia_hwm")

        fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout="constrained")
        acc = accumulated_max(times[4])
        axes[0].step(range(1, len(acc) + 1), [us(t) for t in acc], where="post", color=color)
        axes[0].set(title="Todas as 10000 ativações", ylabel="HWM acumulado (µs)")
        axes[1].step(range(100, len(acc) + 1), [us(t) for t in acc[99:]], where="post", color=color)
        for row in jumps[4]:
            if row["ativacao"] >= 100:
                axes[1].scatter(row["ativacao"], row["hwm_acumulado_us"], color=red, s=20)
        axes[1].set(title="Ampliação após 100 amostras: saltos tardios continuam presentes",
                    xlabel="Número de amostras", ylabel="HWM acumulado (µs)",
                    ylim=(us(acc[99]) - 15, us(max(acc)) + 20))
        for ax in axes:
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        fig.suptitle(f"Etapa 4 — patamares temporários e último aumento em n={jumps[4][-1]['ativacao']}")
        save(fig, "convergencia_etapa4_detalhe")

        fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
        ax.plot(list(NAMES), [results[s]["hwm_100_us"] for s in NAMES], "o-", color=color, label="HWM observado")
        for item, style in zip(margins, ("--", "-.", ":")):
            ax.axhline(item["limite_us"], ls=style, label=f"HWM etapa 1 + {item['margem_percentual']}% = {item['limite_us']:.1f} µs")
        ax.set(xticks=list(NAMES), xticklabels=[LABELS[s] for s in NAMES], ylabel="Tempo (µs)", title="Margens fixadas a partir da etapa 1")
        ax.legend(fontsize=9)
        save(fig, "margens_seguranca")

        fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
        ax.plot([r["m"] for r in frontier], [r["deadline_minimo_us"] for r in frontier], "o-", color=color)
        ax.scatter([TARGET[0]], [us(opt)], color=red, s=65, label=f"Meta (18,20): {us(opt):.3f} µs", zorder=3)
        ax.axhline(us(max(times[4])), ls=":", color=gold, label="HWM100 etapa 4")
        ax.set(xlabel="m exigido em cada janela de k=20", ylabel="Menor D observado (µs)",
               title="Etapa 4 — fronteira exata na amostra, sem garantia futura", xticks=range(1, 21))
        ax.legend(fontsize=9)
        save(fig, "deadline_minimo_m20")

        fig, axes = plt.subplots(len(deadlines), 2, figsize=(13, 12), layout="constrained")
        for row, (slug, label, deadline) in enumerate(deadlines):
            for col, stage in enumerate((3, 4)):
                ax = axes[row, col]
                r = next(a["resultado"] for a in alternatives if a["etapa"] == stage and a["slug"] == slug)
                info = r["janelas"][20]
                ax.step(range(1, len(info["contagens"]) + 1), info["contagens"], where="mid", color=color, lw=.6)
                ax.set(title=f"Etapa {stage}: {label}, D={us(deadline):.1f}; {pair(info)}",
                       ylabel="Perdas / 20", ylim=(-.5, 20.5))
                ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        for ax in axes[-1]:
            ax.set_xlabel("Ativação inicial da janela")
        fig.suptitle("Experimento D — efeito do deadline na concentração de perdas")
        save(fig, "deadlines_alternativos_janelas")

    thresholds = {"primeiro_hwm_final": jumps[4][-1]["ativacao"],
                  "margem_observada_etapa4_percentual": 100 * (max(times[4]) / base_hwm - 1)}
    make_report(output, results, alternatives, thresholds, optimum, convergence, margins, coverage)
    manifest = {"fontes": sources, "deadline_fixo_us": us(FIXED_D),
                "meta_ilustrativa": list(TARGET), "python": platform.python_version(),
                "matplotlib": matplotlib.__version__, "numpy": np.__version__,
                "modulo_huffman_e_sdkconfig_preservados_iguais": True,
                "cobertura": coverage,
                "sha256_scripts": {name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
                                   for name in ("metricas.py", "analisar_coletas.py")}}
    jsonwrite(output / "manifesto.json", manifest)
    print(f"Analises geradas em: {output}")
    print(f"Menor deadline para (18,20) na etapa 4: {us(opt):.3f} us")
    print("18 figuras PNG/PDF e caderno de graficos; tabelas, evidencias e RELATORIO_ANALISE.md.")


if __name__ == "__main__":
    main()
