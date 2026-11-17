"""Valida um log enviado da ESP32 e preserva CSV, log e metadados da etapa."""

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re


NAMES = {2: "comportamental", 3: "intertarefas", 4: "sistema"}


def decode_log(original, boot_offset):
    """Permite isolar um prefixo de boot revisado, sem remover medições.

    O deslocamento é explícito, em bytes. O arquivo bruto continua preservado.
    Erros de firmware ou medições anteriores no prefixo impedem a importação.
    """
    if not 0 <= boot_offset < len(original):
        raise ValueError("Deslocamento de boot fora do arquivo.")
    prefix, body = original[:boot_offset], original[boot_offset:]
    if boot_offset:
        if not body.startswith(b"ets Jul 29 2019 12:21:46"):
            raise ValueError("O deslocamento deve apontar para o início do boot ROM completo.")
        forbidden = (b"COLETA_", b"ativacao,tempo_us", b"Validacao", b"Guru Meditation",
                     b"watchdog", b"Brownout", b"brownout", b"huffman:")
        if any(marker in prefix for marker in forbidden):
            raise ValueError("Prefixo contém execução da tarefa ou erro; não pode ser separado.")
    return body.decode("utf-8-sig")


def extract(text, stage, expected_count, version):
    """Rejeita logs incompletos, repetidos ou de um firmware diferente."""
    if "COLETA_INVALIDA" in text or "Guru Meditation" in text or "Task watchdog got triggered" in text:
        raise ValueError("O log contem erro de execucao; preservar como tentativa invalida.")
    start = re.findall(r"COLETA_CSV_INICIO etapa=(\d+) versao=(\S+) amostras=(\d+)", text)
    finish = re.findall(r"COLETA_CSV_FIM etapa=(\d+) amostras=(\d+)", text)
    if start != [(str(stage), version, str(expected_count))]:
        raise ValueError("Inicio ausente, repetido ou diferente da preparacao desta etapa.")
    if finish != [(str(stage), str(expected_count))]:
        raise ValueError("Fim ausente, repetido ou quantidade de amostras diferente.")
    if f"Validacao OK em todas as {expected_count} ativacoes" not in text:
        raise ValueError("Nao ha confirmacao de validacao de todas as ativacoes.")
    block = text.split("COLETA_CSV_INICIO", 1)[1].split("COLETA_CSV_FIM", 1)[0]
    if block.count("ativacao,tempo_us") != 1:
        raise ValueError("Cabecalho CSV ausente ou repetido.")
    lines = block.split("ativacao,tempo_us", 1)[1].strip().splitlines()
    rows = []
    for line in lines:
        match = re.fullmatch(r"\s*(\d+),(\d+(?:\.\d+)?)\s*", line)
        if not match:
            raise ValueError(f"Linha inesperada no bloco CSV: {line!r}")
        rows.append(match.groups())
    if [int(index) for index, _ in rows] != list(range(1, expected_count + 1)):
        raise ValueError("Ativacoes ausentes, repetidas ou fora de ordem.")
    if any(Decimal(value) <= 0 for _, value in rows):
        raise ValueError("Duracao nula ou negativa encontrada.")
    return rows


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Arquivo com uma execucao completa do monitor")
    parser.add_argument("--etapa", type=int, choices=NAMES, required=True)
    parser.add_argument("--boot-offset", type=int, default=0,
                        help="Offset em bytes de um boot completo, somente após revisão do prefixo")
    args = parser.parse_args()
    folder = root / "dados" / f"etapa{args.etapa}"
    preparation = folder / "preparacao.json"
    if not preparation.is_file():
        parser.error("Falta preparacao.json desta etapa: preparar o firmware primeiro.")
    expected = json.loads(preparation.read_text(encoding="utf-8-sig"))
    original = args.log.read_bytes()
    try:
        text = decode_log(original, args.boot_offset)
        rows = extract(text, args.etapa, expected["ativacoes"], expected["versao"])
    except (UnicodeError, ValueError) as error:
        parser.error(str(error))
    for key in ("entrada_bytes", "semente"):
        if not re.search(rf"\b{key}={expected[key]}\b", text):
            parser.error(f"Parametro {key} nao confere com a preparacao.")
    deadline = Decimal(str(expected["deadline_fixo_us"]))
    deadline_match = re.search(r"deadline_fixo_us=(\d+(?:\.\d+)?)", text)
    if not deadline_match or Decimal(deadline_match[1]) != deadline:
        parser.error("Deadline no log nao confere com a campanha.")
    times = [Decimal(value) for _, value in rows]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["ativacao", "tempo_us"])
    writer.writerows(rows)
    record = {
        "etapa": args.etapa,
        "escopo": NAMES[args.etapa],
        "sha256_log_original": hashlib.sha256(original).hexdigest(),
        "log_para_analise": "log_validado.txt",
        "sha256_log_validado": hashlib.sha256(original[args.boot_offset:]).hexdigest(),
        "offset_boot_validado_bytes": args.boot_offset,
        "observacao_prefixo": ("Prefixo de boot anterior à execução separado somente para leitura; "
                               "nenhuma amostra descartada; log_original.txt preserva todos os bytes"
                               if args.boot_offset else "Log integral sem prefixo separado"),
        "preparacao": expected,
        "ativacoes_validadas": len(rows),
        "resultados_us": {
            "minimo": float(min(times)),
            "media": float(sum(times) / len(times)),
            "hwm_100": float(max(times)),
        },
        "origem": "Log real fornecido pelo usuario; nao e simulacao",
    }
    files = {
        folder / f"etapa{args.etapa}_{NAMES[args.etapa]}.csv": buffer.getvalue().encode("utf-8"),
        folder / "log_original.txt": original,
        folder / "log_validado.txt": original[args.boot_offset:],
        folder / "registro.json": (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    }
    # Confere TODOS os destinos antes de escrever; nunca substitui uma coleta
    # diferente. Uma repeticao deve ser guardada como um novo cenario/tentativa.
    for path, content in files.items():
        if path.exists() and path.read_bytes() != content:
            parser.error(f"Coleta existente preservada: {path}. Use outra pasta para repeticoes.")
    for path, content in files.items():
        path.write_bytes(content)
        if path.read_bytes() != content:
            raise OSError(f"Falha na verificacao de escrita: {path}")
        print(f"Salvo: {path.relative_to(root)}")
    print(f"OK: {len(rows)} ativacoes consecutivas e validadas; log original preservado.")


if __name__ == "__main__":
    main()
