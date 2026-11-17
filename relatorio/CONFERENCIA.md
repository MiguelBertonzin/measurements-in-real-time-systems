# Conferência da entrega individual

O PDF tem oito páginas e identifica somente Miguel Bertonzin como acadêmico.
Professores: Michael Douglas Cabral Alves e Felipe Viel. RA pendente de preenchimento.

| Exigência | Página |
| --- | --- |
| Identificação, plataforma, entrada, semente e instrumentação | 1 |
| Caso, procedimento e critério das quatro etapas; D fixo | 2 |
| Tabela-síntese e quatro histogramas | 3 |
| Séries temporais, perdas, distâncias e rajadas | 4 |
| Janelas k=10/20/50 e limites do (m,k) medido | 5 |
| Experimentos A, B e C | 6 |
| Experimento D, cinco deadlines e menor D para (18,20) | 7 |
| Reprodutibilidade, ameaças, conclusão e referências | 8 |

Listas integrais de perdas e janelas estão nos CSV anexos. O caderno de gráficos
contém 18 páginas; ele é complementar ao relatório de oito páginas.

Todos os CSV foram confrontados com os logs reais. O prefixo de boot da etapa 2
permanece no log original e foi documentado no relatório. Nova execução de gcov
e seis testes de métricas passaram. A conferência NumPy validou 14 cenários e
42 séries completas de janelas e confirmou o menor deadline por busca independente.
O PDF deve manter oito páginas após a atualização do RA.

Antes do envio, preencher o RA em texto_base.md, regenerar o PDF e o pacote,
nomear o ZIP com o RA e revisar as conclusões.
