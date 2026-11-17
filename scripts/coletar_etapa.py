"""Captura passiva das etapas 1–3; guarda cada tentativa sem sobrescrever arquivos.

Executar depois de build/flash, com o monitor fechado. A etapa 4 exige outro
coletor, pois precisa gerar tráfego UART durante a medição.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--porta', required=True)
    parser.add_argument('--etapa', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--timeout', type=float, default=240)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    campaign = json.loads((root / 'campanha.json').read_text(encoding='utf-8'))
    if args.etapa != campaign['etapa_preparada']:
        parser.error('A etapa solicitada não corresponde à etapa preparada no projeto.')
    folder = root / 'dados' / f'etapa{args.etapa}' / 'tentativas'
    folder.mkdir(parents=True, exist_ok=True)
    name = 'serial_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    path = folder / (name + '.txt')
    sources = [root / 'sdkconfig', *sorted((root / 'main').glob('*'))]
    metadata = {
        'campanha': campaign['id'], 'etapa': args.etapa, 'porta': args.porta,
        'baudrate': 115200, 'estado': 'iniciando',
        'sha256_fontes_no_inicio': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sources if p.is_file()},
        'nota': 'Hashes são dos fontes locais; conferir build/flash e identificação do firmware no log.',
    }
    sidecar = folder / (name + '.json')
    recent = b''
    started = time.monotonic()
    next_progress = started + 15
    end = (b'Fim da tarefa sob teste' if args.etapa == 1 else
           f'COLETA_CSV_FIM etapa={args.etapa} amostras=1000'.encode())
    print(f'Campanha: {campaign["id"]}. Etapa: {args.etapa}. Porta: {args.porta}', flush=True)
    print(f'Log: {path}', flush=True)
    print('Monitor ESP-IDF deve estar fechado. O CSV aparece somente após as medições.', flush=True)
    try:
        with path.open('xb') as log:
            # Define os sinais antes de abrir, evitando acionar GPIO0 por DTR.
            with serial.Serial(port=None, baudrate=115200, timeout=.2) as device:
                device.dtr = False
                device.rts = False
                device.port = args.porta
                device.open()
                device.rts = True
                time.sleep(.1)
                device.rts = False
                print('Aguardando boot. Se não iniciar, pressione EN/RESET uma vez.', flush=True)
                while time.monotonic() - started < args.timeout:
                    chunk = device.read(8192)
                    if chunk:
                        log.write(chunk)
                        log.flush()
                        recent = (recent + chunk)[-65536:]
                        if any(error in recent for error in (
                            b'COLETA_INVALIDA', b'Guru Meditation', b'Task watchdog got triggered',
                            b'Validacao falhou', b'Falha ao ler o relogio')):
                            raise RuntimeError('Firmware informou erro; log da tentativa preservado.')
                        if args.etapa == 1 and b'COLETA_INICIO etapa=' in recent:
                            raise RuntimeError('Firmware de outra etapa detectado. Conferir build/flash da etapa 1.')
                        if end in recent:
                            if b'Validacao OK em todas as 1000 ativacoes' not in recent:
                                raise RuntimeError('Fim recebido sem confirmação de validação das 1000 ativações.')
                            metadata['estado'] = 'captura_recebida_pendente_validacao_csv'
                            print(f'Captura concluída: {path}', flush=True)
                            print('Envie o caminho acima para validar o CSV e preparar a próxima etapa.', flush=True)
                            return
                    if time.monotonic() >= next_progress:
                        print(f'Aguardando resultado: {int(time.monotonic()-started)} s; {log.tell()} bytes salvos.', flush=True)
                        next_progress = time.monotonic() + 15
                raise TimeoutError('Tempo limite; captura parcial preservada. Não importar como coleta completa.')
    except (Exception, KeyboardInterrupt) as error:
        metadata['estado'] = 'tentativa_interrompida'
        metadata['erro'] = str(error) or 'Interrompida pelo usuário'
        raise
    finally:
        if path.exists():
            metadata['sha256_log'] = hashlib.sha256(path.read_bytes()).hexdigest()
        sidecar.write_text(json.dumps(metadata, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
