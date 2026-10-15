# Migração da nomenclatura de agentes para a tese (CogScore)

## Escopo

Os nomes `CS` identificam **Cognitive Strategies** conforme a tese; `SubstageN` também é parâmetro operacional em alguns controladores de aprendizagem. Não renomear diretórios, arquivos brutos, stages de execução, valores de métricas, colunas numéricas, IDs históricos de runs ou dados do banco.

| Nome de exibição | Identificadores de origem aceitos |
| --- | --- |
| CS1 | Substage1, Substage1_DQN |
| CS1_T | Substage1_Theoretic |
| CS2 | Substage2, Substage2_DQN |
| CS3 | Substage3, Substage3_DQN |
| CS3_T | Substage3_Theoretic |
| CS4 | Substage4, Substage4_DQN |
| CS5 | Substage5, Substage5_DQN |
| CS6 | Substage1_QL, 1st_ql |
| CS7 | Substage2_QL, 2nd_ql |
| CS8 | Substage3_QL, 3rd_ql |
| CS6_nEC | Substage1_QL_Noise, 1st_ql_noise |

A substituição acontece **somente na apresentação** das figuras geradas pelos quatro scripts de comparação (`scripts/{sperling,posner,mot,learning}.py`) e na identificação canônica usada para agrupar as matrizes CogScore. Aliases não listados permanecem inalterados. Os aliases históricos `Substage1_Theoretic` e `Substage3_Theoretic` são exibidos como `CS1_T` e `CS3_T` respectivamente, sem modificar a origem ou caracterização dos respectivos resultados. Resultados importados anteriormente mantêm o nome bruto para proveniência. A grafia `CS6_nEC` é exibida exatamente como solicitada, sem inferir o significado de `nEC`.

## Aplicação (pasta `cogscore/` do repositório)

1. Faça um snapshot separado do diretório `playground/data/` e do banco SQLite. Execute `git status --short` e registre o commit original.
2. Aplique `git apply --check ../cogscore_nomenclatura.patch` e depois `git apply ../cogscore_nomenclatura.patch` (ajuste o caminho se necessário). O patch não contém dados brutos.
3. Execute `python -m compileall -q playground/scripts playground/services/api/app/cogscore_matrix.py`.
4. Instale dependências de teste existentes e execute `cd playground && python -m pytest -q tests/test_agent_names.py`.
5. Gere um inventário/hashes dos `.csv`, `.json`, `.yaml` originais em `playground/data`, excluindo a pasta `plots`. Exemplo: `find playground/data/results playground/data/uploads -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/cogscore_raw_before.sha256`.
6. Recrie plots **em nova geração**, nunca sobrescrevendo a geração de referência: use o botão **Generate a new comparison / Rebuild** na página Plots; ou, no mesmo ambiente da API/banco em execução, `python playground/tools/create_comparison_replot_jobs.py --benchmark sensory_buffer --benchmark attention_posner --benchmark motivation --benchmark learning`. O script apenas agenda jobs: o worker precisa estar ativo. Verifique no dashboard o status dos jobs.
7. Compare, para cada benchmark e agente, a contagem de séries, pontos, distribuição dos eixos, intervalos, médias e erros nos arquivos antes/depois. Para conjuntos intermediários CSV gerados, compare colunas **numéricas** por `pandas.testing.assert_frame_equal` após alinhamento das linhas, ignorando apenas campos de identificação do agente. Gráficos raster antigos e novos não devem ser comparados por hash: o texto alterado muda os pixels.
8. Execute `sha256sum -c /tmp/cogscore_raw_before.sha256` a partir da mesma pasta de trabalho; todos os hashes brutos devem coincidir.
9. Revise todas as legendas, títulos, labels e cards. Preste atenção a `CS1` versus `CS6` (ambos derivam de `Substage1`, mas **somente** `_QL` indica `CS6`), `CS3` versus `CS8` e `CS6_nEC` versus `CS6`.
10. Valide as matrizes CogScore e os resultados da API após reiniciar API/worker. O agrupamento canônico agora combina aliases históricos. Se houver runs anteriormente distintos com a mesma identidade CS, confirme que a política de seleção temporal é a pretendida.
11. Confira `git diff --check` e `git status --short` antes do commit. Guarde os hashes, commit base, versão do patch, log de testes, IDs dos jobs e relatório de comparação.

## Separação recomendada

**Não** renomeie todos os dados e dispare um replot em um único script de migração. Primeiro atualize o código de apresentação e rode testes; depois agende replot explicitamente, preservando o histórico. Se for indispensável disponibilizar uma exportação CSV já com identificadores CS, faça uma **cópia derivada** sob outro caminho, com apenas as colunas textuais autorizadas alteradas, validação de conflitos e comparação bit a bit de valores numéricos; nunca edite o material experimental original.

## Notas sobre limites

Os `.png` existentes são artefatos rasterizados; a mudança dos scripts só aparece ao **regenerá-los**. O patch não repinta nem altera os PNGs de origem. Os diretórios de `data/` e os IDs de jobs permanecem como estavam. Metadados gerados por etapas externas ao replot podem preservar IDs históricos: isso é intencional para a rastreabilidade.

## Complemento incremental: variantes `_Theoretic`

Os identificadores históricos `Substage1_Theoretic` e `Substage3_Theoretic` também são normalizados para `CS1_T` e `CS3_T` em legendas e matrizes. As variantes teóricas permanecem distintas das estratégias DQN (`CS1` e `CS3`) também na identificação canônica usada pelas matrizes. Os IDs históricos continuam disponíveis para proveniência. Nenhum registro bruto é reescrito.
