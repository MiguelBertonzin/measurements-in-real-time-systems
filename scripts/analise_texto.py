"""Resumo textual calculado exclusivamente com os resultados da campanha atual."""


def make_report(output, results, alternatives, thresholds, optimum, convergence, margins, coverage):
    def fmt(x):
        return '—' if x is None else f'{x:,.3f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    def table(header, rows):
        return '\n'.join('| '+' | '.join(map(str,row))+' |' for row in [header,['---']*len(header),*rows])
    def pair(r,k):
        return f"({r['janelas'][k]['m']},{k})"
    s=results
    text=['# Análise das medições de Huffman na ESP32',
          'As quatro coletas foram executadas na ESP32-D0WD-V3. Logs brutos, hashes, CSV e fontes estão preservados. Nenhuma amostra foi descartada. Na etapa 2, o registro documenta um prefixo de boot separado somente para leitura; o arquivo bruto permanece intacto.',
          '## Convenções',
          f'D fixo = {fmt(s[1]["deadline_us"])} µs, calculado como 1,2 × HWM1. Cumpre em R ≤ D; perde em R > D. HWM99 remove floor(N/100) valores do topo e toma o maior restante. S é a menor distância entre perdas; fica indefinido com menos de duas. Rajada tem pelo menos duas perdas consecutivas. São avaliadas todas as N−k+1 janelas completas; m = k − máximo de perdas.',
          '## Resultados',
          table(['Etapa','N','Mín. µs','Média µs','HWM µs','HWM99 µs','Prazo %','S','k=10','k=20','k=50'],
                [[i,r['n'],*[fmt(r[k]) for k in ('minimo_us','media_us','hwm_100_us','hwm_99_us','percentual_no_prazo')],r['skip_factor'] or '—',*[pair(r,k) for k in (10,20,50)]] for i,r in s.items()])]
    for i,r in s.items():
        text += [f'### Etapa {i}',
                 f"Perdas: {r['perdas']}; isoladas: {r['perdas_isoladas']}; rajadas: {r['quantidade_rajadas']}; maior rajada: {r['maior_rajada']}. Mediana: {fmt(r['mediana_us'])} µs; desvio padrão populacional: {fmt(r['desvio_padrao_populacional_us'])} µs.",
                 *[f'![Etapa {i}: {name}](figuras/etapa{i}_{name}.png)' for name in ('histograma','temporal','janelas')],
                 f'Listas integrais: etapa{i}/perdas.csv, distancias.csv, sequencias_perdas.csv e janelas_k10/k20/k50.csv.']
    text += ['## A — cobertura e HWM',
             f"Nova execução de gcov: {coverage['linhas_percentual']}% das linhas e {coverage['desvios_tomados_percentual']}% dos resultados de desvio do algoritmo no computador. A proteção contra overflow não é alcançável pelos limites de entrada da suíte nessa plataforma. Não houve marco de 100%. O mesmo algoritmo tem HWMs diferentes conforme o contexto; cobertura de linhas/desvios não esgota estados temporais, nem representa todos os caminhos.",
             '## B — convergência',
             table(['Amostras','HWM µs','Abaixo do HWM final %'],[[r['n'],fmt(r['hwm_us']),fmt(r['subestimacao_percentual'])] for r in convergence]),
             f"O último aumento ocorreu na ativação {thresholds['primeiro_hwm_final']}. Os patamares e a subestimação dos prefixos descrevem a amostra, sem demonstrar WCRT. A cronologia completa está em etapa4/saltos_hwm.csv.",
             '![Convergência](figuras/convergencia_etapa4_detalhe.png)',
             '## C — margens',
             table(['Margem %','Limite µs','Primeira etapa insuficiente'],[[r['margem_percentual'],fmt(r['limite_us']),r['primeira_etapa_insuficiente'] or 'nenhuma observada'] for r in margins]),
             f"Margem necessária para cobrir somente o HWM4 observado: {fmt(thresholds['margem_observada_etapa4_percentual'])}%. Maior variabilidade exige reavaliar a margem; cobrir os máximos desta campanha não garante execuções futuras.",
             '## D — deadlines alternativos',
             table(['Etapa','Escolha','D µs','Prazo %','S','(m,20)','Isoladas','Rajadas','Maior rajada'],
                   [[a['etapa'],a['nome'],fmt(a['resultado']['deadline_us']),fmt(a['resultado']['percentual_no_prazo']),a['resultado']['skip_factor'] or '—',pair(a['resultado'],20),a['resultado']['perdas_isoladas'],a['resultado']['quantidade_rajadas'],a['resultado']['maior_rajada']] for a in alternatives]),
             f"A meta (18,20) é ilustrativa. O menor D observado é {fmt(optimum['deadline_minimo_us'])} µs; o valor distinto anterior, {fmt(optimum['anterior_observado_us'])} µs, falha. A redução frente ao HWM100 é {fmt(optimum['reducao_us'])} µs. O cálculo toma o máximo dos 18º menores tempos das janelas de 20. As listas completas para os cinco deadlines estão em experimento_d/.",
             'Percentual global não caracteriza o espaçamento das perdas. Para uma planta com inércia, perdas isoladas e longas rajadas podem ter efeitos diferentes. S e (m,k) descrevem a concentração, mas não validam fisicamente uma tolerância.',
             '## Limitações e reprodução',
             'Uma campanha por cenário, semente e tamanho; N diferente entre etapas; jitter antes do envio excluído; cache, interrupções e processos do computador não rastreados. Cobertura é do algoritmo no computador. ESP-IDF v6.1-dirty aparece na nova campanha. O volume UART real deve ser consultado em dados/etapa4/evidencias/validacao.json. HWM e (m,k) são observados, sem garantia futura.',
             'Execute scripts/analisar_coletas.py na raiz do projeto para reproduzir as tabelas e os gráficos.']
    (output/'RELATORIO_ANALISE.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')
