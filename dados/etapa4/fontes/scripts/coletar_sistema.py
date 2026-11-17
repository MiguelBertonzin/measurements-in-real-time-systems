"""Gera carga UART externa e salva o log real da etapa 4, sem usar monitor."""

import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

import serial
from serial.tools import list_ports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--porta", help="Exemplo: COM3; omitida, tenta detectar uma unica USB/serial")
    parser.add_argument("--timeout", type=float, default=1500, help="Limite total em segundos")
    args = parser.parse_args()
    port = args.porta
    if not port:
        ports = [p for p in list_ports.comports() if p.vid is not None]
        if len(ports) != 1:
            parser.error("Informe --porta COMx. Portas disponiveis: " +
                         ", ".join(p.device for p in list_ports.comports()))
        port = ports[0].device
    root = Path(__file__).resolve().parents[1]
    campaign = json.loads((root / "campanha.json").read_text(encoding="utf-8"))
    if campaign["etapa_preparada"] != 4 or campaign["etapas_coletadas"] != [1, 2, 3]:
        parser.error("Concluir as etapas 1–3 e preparar a etapa 4 antes de coletar.")
    preparation = json.loads((root / "dados/etapa4/preparacao.json").read_text(encoding="utf-8"))
    for name, expected in preparation["sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            parser.error("Arquivo alterado desde a preparação: " + name)
    folder = root / "dados/etapa4/tentativas"
    folder.mkdir(parents=True, exist_ok=True)
    # Cada tentativa tem nome proprio e nunca substitui outra captura.
    path = folder / ("uart_" + time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8] + ".txt")
    metadata = {
        "campanha": campaign["id"], "etapa": 4, "porta": port, "baudrate": 115200,
        "estado": "iniciando", "sha256_fontes_no_inicio": preparation["sha256"],
        "sha256_bin_no_inicio": hashlib.sha256((root / "build/M3_STR.bin").read_bytes()).hexdigest(),
        "carga_nominal": {"bytes_por_envio": 128, "intervalo_ms": 20,
                          "duracao_rajada_s": 1, "periodo_rajada_s": 3},
        "nota": "Carga nominal: 128 bytes a cada 20 ms, durante 1 s, com pausa de 2 s; recebimento conferido no log da placa.",
    }
    payload = bytes(range(32, 160))  # 128 bytes, sem comandos de controle da console.
    print(f"Porta: {port}. Log: {path}", flush=True)
    print("Carga: 128 bytes/20 ms durante 1 s a cada 3 s; coleta ~17 minutos.", flush=True)
    print("Nao abra o monitor do ESP-IDF enquanto este script estiver conectado.", flush=True)
    started = time.monotonic()
    next_send = started
    next_progress = started + 30
    recent = b""
    measuring_since = None
    receiving_csv = False
    try:
        with path.open("xb") as log, serial.Serial(port, 115200, timeout=0.01, write_timeout=2) as device:
            device.dtr = False
            device.rts = False
            # Reinicia por EN se a placa nao tiver reiniciado ao abrir a porta.
            # DTR baixo mantem GPIO0 fora do modo de download no circuito usual.
            device.rts = True
            time.sleep(0.1)
            device.rts = False
            # Espere boot/driver: os primeiros bytes de carga podem chegar
            # antes do driver estar instalado e sao simplesmente ignorados.
            while time.monotonic() - started < args.timeout:
                now = time.monotonic()
                if now >= next_send:
                    if (now - started) % 3 < 1:
                        device.write(payload)
                    # Nao acumula rajadas atrasadas quando o computador estiver ocupado.
                    next_send = now + 0.02
                data = device.read(8192)
                if data:
                    log.write(data)
                    log.flush()
                    recent = (recent + data)[-8192:]
                    if measuring_since is None and b"CARGA_UART_INICIADA" in recent:
                        measuring_since = time.monotonic()
                        print("ESP32 confirmou o inicio. Medindo por cerca de 1000 segundos (16 min 40 s).", flush=True)
                        print("O arquivo pode ficar do mesmo tamanho durante esse periodo: o CSV so sai no final.", flush=True)
                    if not receiving_csv and b"COLETA_CSV_INICIO etapa=4" in recent:
                        receiving_csv = True
                        print("Medicoes encerradas. Recebendo as 10000 linhas do CSV...", flush=True)
                    if b"COLETA_INVALIDA" in recent or b"Guru Meditation" in recent:
                        raise RuntimeError("Firmware reportou erro. Tentativa preservada no log.")
                    if b"COLETA_CSV_FIM etapa=4 amostras=10000" in recent:
                        metadata["estado"] = "captura_recebida_pendente_validacao_csv"
                        print("Captura concluida. Log preservado em:", path, flush=True)
                        print("Envie esse arquivo para validar e importar as 10000 medicoes.")
                        return
                if now >= next_progress:
                    if receiving_csv:
                        print(f"Recebendo CSV... {log.tell()} bytes salvos.", flush=True)
                    elif measuring_since is not None:
                        elapsed = max(0, int(now - measuring_since))
                        remaining = max(0, 1000 - elapsed)
                        print(f"Medindo: {elapsed}/1000 s; faltam aproximadamente {remaining // 60} min {remaining % 60} s. "
                              "Sem novas linhas durante a medicao e esperado.", flush=True)
                    else:
                        print(f"Aguardando confirmacao da ESP32... {int(now - started)} segundos; {log.tell()} bytes salvos.", flush=True)
                    next_progress = now + 30
            raise TimeoutError("Tempo limite sem marcador final. Log parcial preservado.")
    except KeyboardInterrupt:
        metadata["estado"] = "tentativa_interrompida"
        print("Interrompido. Log parcial preservado em:", path)
        raise SystemExit(1)
    except Exception as error:
        metadata["estado"] = "tentativa_com_erro"
        metadata["erro"] = str(error)
        raise
    finally:
        if path.exists():
            metadata["sha256_log"] = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
