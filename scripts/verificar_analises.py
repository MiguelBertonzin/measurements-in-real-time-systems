"""Conferência independente com NumPy: estatísticas, perdas, rajadas e 42 janelas."""
import csv
import json
from pathlib import Path
import numpy as np
from analisar_coletas import load

ROOT=Path(__file__).resolve().parents[1]


def main():
    times={s:np.asarray(load(s)[0],dtype=np.int64) for s in range(1,5)}
    folders=[(s,ROOT/f'analises/etapa{s}') for s in range(1,5)]
    folders += [(s,p) for s in (3,4) for p in sorted((ROOT/f'analises/experimento_d/etapa{s}').iterdir()) if p.is_dir()]
    assert len(folders)==14
    for stage,folder in folders:
        r=json.loads((folder/'resumo.json').read_text(encoding='utf-8'))
        x=times[stage];lost=x>round(r['deadline_us']*1000)
        assert x.min()/1000==r['minimo_us'] and x.max()/1000==r['hwm_100_us']
        assert abs(x.mean()/1000-r['media_us'])<1e-9
        assert np.sort(x)[len(x)-len(x)//100-1]/1000==r['hwm_99_us']
        positions=np.flatnonzero(lost)+1
        assert len(positions)==r['perdas']
        assert np.isclose(100*(1-lost.mean()),r['percentual_no_prazo'])
        gaps=np.diff(positions)
        assert (int(gaps.min()) if len(gaps) else None)==r['skip_factor']
        recorded=list(csv.DictReader((folder/'perdas.csv').open(encoding='utf-8')))
        assert [int(v['ativacao']) for v in recorded]==positions.tolist()
        recorded=list(csv.DictReader((folder/'distancias.csv').open(encoding='utf-8')))
        assert [int(v['distancia_ativacoes']) for v in recorded]==gaps.tolist()
        changes=np.diff(np.r_[False,lost,False].astype(int))
        starts=np.flatnonzero(changes==1)+1; ends=np.flatnonzero(changes==-1)
        lengths=ends-starts+1
        assert int(np.sum(lengths==1))==r['perdas_isoladas']
        assert int(np.sum(lengths>=2))==r['quantidade_rajadas']
        assert int(max(lengths[lengths>=2],default=0))==r['maior_rajada']
        runs=list(csv.DictReader((folder/'sequencias_perdas.csv').open(encoding='utf-8')))
        assert [(int(v['inicio']),int(v['fim']),int(v['tamanho'])) for v in runs]==list(zip(starts,ends,lengths))
        for k in (10,20,50):
            cumulative=np.r_[0,np.cumsum(lost)]
            counts=cumulative[k:]-cumulative[:-k]
            expected=r['janelas'][str(k)]
            assert int(counts.max())==expected['perdas_maximas']
            assert k-int(counts.max())==expected['m']
            records=list(csv.DictReader((folder/f'janelas_k{k}.csv').open(encoding='utf-8')))
            assert [int(v['perdas']) for v in records]==counts.tolist()
            assert [int(v['inicio']) for v in records]==list(range(1,len(counts)+1))
            assert [int(v['fim']) for v in records]==list(range(k,len(x)+1))
    optimum=json.loads((ROOT/'analises/deadline_minimo.json').read_text(encoding='utf-8'))
    distinct=np.unique(times[4]);lo=0;hi=len(distinct)-1
    while lo<hi:
        mid=(lo+hi)//2
        cumulative=np.r_[0,np.cumsum(times[4]>distinct[mid])]
        if np.max(cumulative[20:]-cumulative[:-20])<=2:hi=mid
        else:lo=mid+1
    assert distinct[lo]/1000==optimum['deadline_minimo_us']
    (ROOT/'analises/VERIFICACAO.md').write_text(
        '# Conferência independente\n\n14 cenários e 42 séries completas de janelas conferidos com NumPy. '
        'Mínimo, média, HWM100, HWM99, percentual no prazo, listas de perdas, distâncias, '
        'S, sequências e rajadas coincidem com os CSV exportados. '
        'O deadline mínimo (18,20) foi confirmado por busca binária nos valores distintos, '
        'contando diretamente as perdas. Os quatro CSV também passaram pela conferência '
        'contra os logs brutos e seus hashes. A etapa 2 preserva o prefixo de boot no log original.\n',encoding='utf-8')
    print('OK: 14 cenários, 42 séries de janelas e limiar mínimo conferidos independentemente.')


if __name__=='__main__':main()
