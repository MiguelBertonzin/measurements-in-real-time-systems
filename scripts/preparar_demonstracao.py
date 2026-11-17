"""Copia uma etapa para demonstração, sem alterar a campanha do relatório."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--etapa', required=True, type=int, choices=(1, 2, 3, 4))
    args = parser.parse_args()
    stage = args.etapa
    source = ROOT / 'dados' / f'etapa{stage}' / 'fontes'
    destination = ROOT / 'demonstracoes' / (
        f'etapa{stage}_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6])
    destination.parent.mkdir(exist_ok=True)
    shutil.copytree(source, destination)
    (destination / 'scripts').mkdir(exist_ok=True)
    collector = 'coletar_sistema.py' if stage == 4 else 'coletar_etapa.py'
    shutil.copyfile(ROOT / 'scripts' / collector, destination / 'scripts' / collector)
    campaign = json.loads((ROOT / 'campanha.json').read_text(encoding='utf-8'))
    campaign.update({
        'id': destination.name, 'estado': 'demonstracao_sem_medicoes_importadas',
        'etapa_preparada': stage, 'etapas_coletadas': list(range(1, stage)),
    })
    for key in ('etapa1_registro', 'etapa2_registro', 'etapa3_registro', 'etapa4_registro',
                'relatorio', 'sha256_fontes_iniciais'):
        campaign.pop(key, None)
    (destination / 'campanha.json').write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if stage == 4:
        prep = json.loads((ROOT / 'dados/etapa4/preparacao.json').read_text(encoding='utf-8'))
        prep['campanha'] = destination.name
        prep['compilacao_esp32'] = 'Pendente: demonstracao preparada, ainda nao compilada ou executada'
        prep.pop('sha256_build_preparado', None)
        prep.pop('revisao_documental_coletor', None)
        prep['sha256'] = {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                          for name in prep['sha256']}
        data = destination / 'dados/etapa4'
        data.mkdir(parents=True)
        (data / 'preparacao.json').write_text(
            json.dumps(prep, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for path in (source / 'main').glob('*'):
        if path.is_file():
            assert path.read_bytes() == (destination / 'main' / path.name).read_bytes()
    assert (source / 'sdkconfig').read_bytes() == (destination / 'sdkconfig').read_bytes()
    print('Demonstracao preparada; a ESP32 ainda nao foi gravada.')
    print('No terminal ESP-IDF, execute:')
    print(f"cd '{destination}'")
    if stage == 4:
        print('idf.py -p COM7 build flash')
        print('python scripts/coletar_sistema.py --porta COM7')
    else:
        print('idf.py -p COM7 build flash monitor')
        print('Para sair do monitor: Ctrl+]')
        print('Para salvar uma execucao, feche o monitor e execute:')
        print(f'python scripts/coletar_etapa.py --etapa {stage} --porta COM7')
    print('Resultados desta pasta sao demonstracoes, separados dos dados do relatorio.')


if __name__ == '__main__':
    main()
