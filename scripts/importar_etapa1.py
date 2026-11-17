"""Valida a primeira coleta real e fixa o deadline da campanha individual."""
import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re

from metricas import analyze, compact, ns

ROOT = Path(__file__).resolve().parents[1]


def sha(content):
    return hashlib.sha256(content).hexdigest()


def encoded_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def extract(text):
    for pattern in ('COLETA_INVALIDA', 'Guru Meditation', 'Task watchdog got triggered',
                    'Validacao falhou', 'Falha ao ler o relogio', 'COLETA_INICIO etapa='):
        if pattern in text:
            raise ValueError('Erro ou firmware de outra etapa encontrado: ' + pattern)
    for marker in ('Item 3: Huffman com codificacao, decodificacao e comparacao',
                   'entrada_bytes=4096; semente=123456789; ativacoes=1000',
                   'Validacao OK em todas as 1000 ativacoes; CSV abaixo',
                   'ativacao,tempo_us', 'Fim da tarefa sob teste'):
        if text.count(marker) != 1:
            raise ValueError('Marcador ausente ou repetido: ' + marker)
    if not re.search(r'cpu freq:\s+160000000 Hz', text):
        raise ValueError('Frequência de 160 MHz não confirmada no log.')
    block = text.split('ativacao,tempo_us', 1)[1]
    block, end = re.split(r'I \(\d+\) huffman: Fim da tarefa sob teste', block, maxsplit=1)
    if end.strip() and not re.fullmatch(r'I \(\d+\) main_task: Returned from app_main\(\)', end.strip()):
        raise ValueError('Conteúdo inesperado após o fim; conferir execuções repetidas.')
    rows = []
    for line in block.strip().splitlines():
        match = re.fullmatch(r'(\d+),(\d+\.\d{3})', line.strip())
        if not match:
            raise ValueError('Linha inválida no CSV: ' + line)
        rows.append(match.groups())
    if [int(r[0]) for r in rows] != list(range(1, 1001)):
        raise ValueError('CSV deve conter exatamente as ativações 1 a 1000, sem lacunas.')
    if any(ns(value) <= 0 for _, value in rows):
        raise ValueError('Tempo não positivo encontrado.')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--terminal', type=Path, required=True)
    args = parser.parse_args()
    campaign = json.loads((ROOT / 'campanha.json').read_text(encoding='utf-8'))
    if campaign['etapa_preparada'] != 1:
        parser.error('Importar antes de trocar o firmware da etapa 1.')
    original = args.log.read_bytes()
    text = original.decode('utf-8-sig')
    rows = extract(text)
    capture = json.loads(args.log.with_suffix('.json').read_text(encoding='utf-8'))
    if capture['campanha'] != campaign['id'] or capture['etapa'] != 1 or capture['sha256_log'] != sha(original):
        parser.error('Metadados da captura ou hash do log divergentes.')
    for name, expected in capture['sha256_fontes_no_inicio'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            parser.error('Fonte alterado desde a captura: ' + name)
    terminal = args.terminal.read_bytes()
    terminal_text = terminal.decode('utf-8-sig')
    if campaign['identificacao_hardware']['mac'] not in terminal_text or 'Hash of data verified.' not in terminal_text:
        parser.error('Evidência de gravação não confirma identificação/validação da placa.')
    elf = ROOT / 'build/M3_STR.elf'
    elf_hash = sha(elf.read_bytes())
    match = re.search(r'ELF file SHA256:\s*([a-f0-9]+)', text)
    if not match or not elf_hash.startswith(match[1]):
        parser.error('Prefixo SHA256 do ELF no log não corresponde ao build preservado.')
    times = [ns(value) for _, value in rows]
    deadline = Decimal(max(times)) * Decimal('1.2')
    if deadline != deadline.to_integral_value():
        parser.error('Deadline não representável em nanossegundos inteiros.')
    deadline = int(deadline)
    result = compact(analyze(times, deadline))
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(['ativacao', 'tempo_us'])
    writer.writerows(rows)
    folder = ROOT / 'dados/etapa1'
    sources = [ROOT/'CMakeLists.txt', ROOT/'sdkconfig', ROOT/'scripts/coletar_etapa.py',
               *[p for p in (ROOT/'main').rglob('*') if p.is_file()]]
    record = {
        'campanha': campaign['id'], 'etapa': 1, 'escopo': 'tarefa',
        'origem': 'Coleta real na ESP32 de Miguel; capturada por serial e validada contra o log',
        'sha256_log_original': sha(original), 'sha256_csv': sha(buffer.getvalue().encode('utf-8')),
        'ativacoes_validadas': len(rows), 'entrada_bytes': 4096, 'semente': 123456789,
        'identificacao_hardware': campaign['identificacao_hardware'],
        'deadline_fixo_us': deadline / 1000, 'regra_deadline': '1.2 * HWM desta etapa 1',
        'resultados_us': {'minimo': result['minimo_us'], 'media': result['media_us'], 'hwm_100': result['hwm_100_us']},
        'captura': capture, 'sha256_fontes': {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sources},
        'sha256_build': {name: sha((ROOT/'build'/name).read_bytes())
                         for name in ('M3_STR.elf', 'M3_STR.bin', 'bootloader/bootloader.bin', 'partition_table/partition-table.bin')},
        'sha256_terminal_build_flash': sha(terminal),
        'idf_no_log': re.search(r'app_init: ESP-IDF:\s*(\S+)', text)[1],
        'observacoes': [
            'Log confirma CPU 160 MHz, revisão v3.1, tarefa principal na CPU0 e validação completa.',
            'ESP-IDF v6.1-dirty registrado no boot e na aplicação.',
            'Flash física 4096 KiB, cabeçalho configurado para 2048 KiB.',
            'HWM calculado a partir das 1.000 ativações desta coleta.'
        ],
    }
    files = {
        folder/'etapa1_tarefa.csv': buffer.getvalue().encode('utf-8'),
        folder/'log_original.txt': original,
        folder/'registro.json': encoded_json(record),
        folder/'resumo.json': encoded_json(result),
        folder/'evidencias/terminal_build_flash.txt': terminal,
        folder/'evidencias/captura.json': encoded_json(capture),
        **{folder/'fontes'/p.relative_to(ROOT): p.read_bytes() for p in sources},
    }
    for path, content in files.items():
        if path.exists() and path.read_bytes() != content:
            parser.error('Coleta existente preservada; não sobrescrever: ' + str(path))
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        assert path.read_bytes() == content
    campaign['deadline_fixo_us'] = deadline / 1000
    campaign['etapas_coletadas'] = [1]
    campaign['etapa1_registro'] = 'dados/etapa1/registro.json'
    (ROOT/'campanha.json').write_bytes(encoded_json(campaign))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print('Etapa 1 preservada. Deadline fixado a partir das novas medições.')


if __name__ == '__main__':
    main()
