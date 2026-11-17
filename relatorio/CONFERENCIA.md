# Conferência dos 13 itens do enunciado

Revisão de 17/11/2026, com base nas seis páginas do PDF da atividade, no código,
nos logs, nos CSV e no relatório individual. A mudança para entrega individual
segue a orientação posterior do professor informada por Miguel.

O PDF tem oito páginas físicas: capa e sete páginas de conteúdo. Adota o estilo
da M2 (capa institucional, Latin Modern, seções numeradas, recuo e paginação
central), com corpo de 11 pt e sem sumário separado para respeitar o limite da M3.
Os números de página abaixo são os impressos no corpo; a capa não é numerada.

| Item do enunciado | Situação | Evidência e limite |
| --- | --- | --- |
| 1. Contexto | Atendido | Objetivo na p. 1; distinção entre HWM, WCRT e cobertura nas pp. 5 e 7. |
| 2. Objetivo | Atendido com a ressalva do experimento A | Quatro escopos, estatísticas, gráficos, perdas e janelas nas pp. 1–6. Não se afirma ter observado saturação em 100%; usa-se a justificativa permitida no item 7. |
| 3. Tarefa Huffman | Atendido | C, clock_gettime(CLOCK_MONOTONIC), codificação/decodificação/comparação, 4.096 bytes, semente 123456789 e tempo de cada ativação. Fontes e logs por etapa em dados/. |
| 4. Configuração | Atendido com limitação documentada | N = 1.000/1.000/1.000/10.000; quatro CSV ativacao,tempo_us; D = 32.440,8 µs fixo. CPU, núcleos, RTOS, energia e cargas descritos na p. 1. Não há inventário completo dos processos do computador gerador; essa limitação está na p. 7. Segunda plataforma é opcional. |
| 5. Etapas | Atendido | Caso, procedimento e critério de cada etapa na p. 1; evento simulado permitido, duas cargas periódicas adicionais, mutex e UART externa justificada. Contadores reais na p. 3. |
| 6. Análises obrigatórias | Atendido | Estatísticas e histograma na p. 2; temporal, perdas, distâncias, rajadas e S na p. 3; todas as janelas k=10/20/50 na p. 4. Listas integrais nos CSV de analises/etapaN/. |
| 7. Experimentos A–D | Atendido, usando a justificativa prevista em A | A: gcov de linhas/desvios e prova do ramo não alcançável; B: 10.000 amostras, prefixos e saltos; C: margens 10/25/50%; D: cinco deadlines nas etapas 3–4, listas e janelas completas, mínimo para (18,20), isoladas/rajadas e discussão da inércia. Pp. 5–6. |
| 8. Tabela-síntese | Atendido | Tabela 1, p. 2, com todas as colunas e quatro etapas. Cobertura é do módulo comum medido no computador, explicitamente identificada; não é cobertura de cada execução na ESP32. |
| 9. Entregáveis | Pendente de identificação final | PDF de oito páginas, fontes, README, CSV e ZIP preparados. Falta preencher o RA na capa e substituir PREENCHER no nome do pacote de entrega. |
| 10. Entrega | Pendente de confirmação/envio pelo aluno | Link do repositório na capa. O enunciado informa 12/11 às 11h35 no AVA 2.0; confirmar o prazo vigente após a orientação de trabalho individual. Não houve envio ao AVA por este processo. |
| 11. Avaliação | Evidências para os cinco critérios preparadas | Experimento (0,4), cobertura/HWM (0,3), estatísticas (0,3), perdas/(m,k) (0,7), conclusões/reprodutibilidade (0,3). A pontuação e a aceitação das justificativas cabem aos professores; não são garantidas por esta conferência. |
| 12. Evitar | Cuidados atendidos, com condições limitadas declaradas | Não se usa só tarefa isolada, D não muda entre etapas, há amostras suficientes e gráficos, (m,k) não é tratado como garantia, margens são comparadas aos dados. Processos do computador e estados ocultos não foram totalmente observados; isso não foi preenchido retroativamente como fato. |
| 13. Orientações finais | Reprodução conferida; revisão do aluno pendente | Código e link publicados. Tabelas e janelas foram verificadas contra os CSV. Miguel deve revisar o texto, concordar com as interpretações e saber explicar os resultados antes da entrega. |

## Verificações técnicas

- CSV conferidos linha a linha com os logs, incluindo integridade SHA-256 e índices completos.
- Mesmo huffman.c, huffman.h e sdkconfig nas quatro etapas; código coberto idêntico ao medido.
- Seis testes de métricas aprovados; verificação independente de 14 cenários e 42 séries de janelas.
- HWM1 = 27.034 µs; HWM4 = 40.304 µs; crescimento de 49,09%.
- D fixo = 32.440,8 µs; perdas = 0, 0, 179 e 1.786.
- Etapas 3–4: (7,10), (16,20), (40,50); mínimo observado para (18,20) na etapa 4 = 39.960 µs.
- Cobertura: 89/90 linhas e 79/80 resultados de desvio. O gcov registra somente a linha 131 como não executada; o teste da linha 130 foi avaliado 285.842 vezes, sempre sem overflow.

## Precisa repetir as coletas?

Não foi identificada falta de amostras, perda de integridade dos CSV ou ausência
de análise obrigatória que exija repetir as quatro coletas. O prefixo de boot da
etapa 2 está preservado; as 1.000 medições seguintes formam uma execução completa,
com firmware conferido, sem remover resultados lentos.

O experimento A não atingiu 100%. A justificativa é matemática: uma entrada aceita
tem no máximo UINT32_MAX bytes e cada símbolo tem até 255 bits. O limite
255 × (2^32 − 1) não transborda size_t de 64 bits no teste de cobertura. Na ESP32,
4.096 × 255 também cabe em 32 bits. O enunciado admite justificar a impossibilidade.
Repetir as mesmas coletas não torna esse ramo alcançável. Não se removeu a proteção
nem se mudou o algoritmo para obter artificialmente 100%.

Novas repetições podem fortalecer as conclusões, mas não são exigidas pelo número
mínimo de amostras do PDF. Se houver orientação adicional dos professores sobre
cobertura embarcada ou registro de processos, ela precisa ser considerada.

## Antes de enviar

1. Preencher o RA em texto_base.md e gerar novamente; no Overleaf, editar capa.tex.
2. Conferir o PDF final e nomear o pacote completo com o RA. O ZIP do Overleaf é
   apenas o projeto do relatório e não substitui o pacote com código e dados.
3. Confirmar o prazo atualizado e enviar o pacote completo no AVA.
4. Revisar as interpretações: HWM não prova WCRT; 98,75% não é 100%; (16,20)
   vale para as janelas observadas; D mínimo de 39.960 µs usa uma meta ilustrativa.
