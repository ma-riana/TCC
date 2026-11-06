## TASKS

O conjunto de dez tarefas foi projetado para avaliar o desempenho e a expressividade estrutural de três arquiteturas distintas: Poliglota (PostgreSQL + Neo4j), Grafo (Neo4j) e Multimodelo (ArangoDB). A regra fundamental estruturante é a restrição a apenas uma consulta por banco de dados dentro de cada task, forçando as linguagens (SQL, Cypher, AQL) a resolverem o problema em uma única viagem ao servidor. As tarefas estão divididas em dois grupos. O primeiro reflete operações transacionais e de leitura recorrentes em plataformas web, como listagens, paginações e renderização de perfis completos. O segundo grupo engloba operações analíticas complexas do domínio de compras públicas, inspiradas em investigações de fraudes, detecção de anomalias estruturais e auditoria de mercado.

A arquitetura poliglota divide fisicamente os dados, mantendo os registros da fonte principal estritamente no modelo relacional (PostgreSQL) e as versões de fontes secundárias no banco de grafos (Neo4j). Para que as arquiteturas de Grafo e Multimodelo isoladas gerem resultados rigorosamente equivalentes, elas precisam incluir filtros locais de fonte em consultas que, no poliglota, recaem implicitamente apenas sobre o PostgreSQL. Além disso, a separação poliglota impõe restrições de rede: embora o sistema tente executar as consultas em paralelo, essa estratégia é bloqueada em tarefas onde a lista de identificadores (`ids`) gerada pelo PostgreSQL é um insumo obrigatório para a parametrização da consulta no Neo4j, impondo um gargalo sequencial que não existe nos bancos unificados.

**Task 1 (T1): Busca por edital e período**

**Objetivo:** Simular um filtro de busca simples de um portal da transparência, retornando uma lista básica de processos licitatórios com base no número do edital ou em uma janela de tempo (data de início e fim da abertura), com suporte a ordenação e limite de resultados.

**Estratégias de busca:**

* **Poliglota:** A tarefa é resolvida exclusivamente no PostgreSQL via SQL. O Neo4j não é acionado, pois todos os metadados primários do processo estão na tabela relacional.
* **Somente Grafo (Neo4j):** Realiza um `MATCH` direto nos nós do tipo `ProcessoLicitatorio`, aplicando cláusulas `WHERE` para os parâmetros informados e retornando as propriedades solicitadas do nó.
* **Multimodelo (ArangoDB):** Executa um iterador `FOR` sobre a coleção de documentos `processo_licitatorio`, utilizando a sintaxe AQL `FILTER` para restringir datas e strings, finalizando com `SORT` e `LIMIT`.

**Motivo da equivalência:**
As três abordagens são equivalentes porque operam em complexidade $O(N)$ (ou $O(\log N)$ com índices adequados) sobre a mesma abstração de entidade única. Não há travessia de arestas, joins ou agregação complexa envolvida. O banco de dados atua apenas como um repositório de leitura plana, e as cláusulas condicionais de data e igualdade filtram o exato mesmo volume de propriedades tabulares (SQL), propriedades de nó (Cypher) ou atributos de documento (AQL), retornando as chaves exatas esperadas pelo sistema.

**Task 2 (T2): Listagem paginada**

**Objetivo:** Simular a renderização contínua de uma página de resultados, buscando um conjunto sequencial de processos licitatórios (utilizando um cursor `last_id` para paginação de alto desempenho) enriquecido com os nomes descritivos da modalidade e da unidade gestora associadas a cada processo.

**Estratégias de busca:**

* **Poliglota:** Resolvida inteiramente no PostgreSQL. Executa uma consulta tabular clássica empregando `LEFT JOIN` nas tabelas dimensionais `modalidade_licitacao` e `unidade_gestora`.
* **Somente Grafo (Neo4j):** Realiza uma travessia utilizando `OPTIONAL MATCH` a partir do nó `ProcessoLicitatorio` para buscar os vizinhos `ModalidadeLicitacao` e `UnidadeGestora`.
* **Multimodelo (ArangoDB):** Itera sobre os processos licitatórios e constrói o resultado projetando variáveis locais (`LET` com `FIRST()`), que executam uma travessia de arestas estrita de profundidade 1 (`IN 1..1 ANY`) para capturar os vértices conectados.

**Motivo da equivalência:**
A semântica da busca é a de enriquecimento opcional de cardinalidade N:1 (cada processo possui, no máximo, uma modalidade e uma unidade gestora). O uso de `LEFT JOIN` no relacional e o comportamento do `OPTIONAL MATCH` ou do sub-bloco `FIRST()` nos grafos garantem que o registro do processo retorne independentemente de os metadados de domínio existirem ou estarem nulos. O volume e o formato das chaves retornadas coincidem perfeitamente.

---

**Task 3 (T3): Ficha completa**

**Objetivo:** Montar a visão de 360 graus para renderização da página de detalhes de um processo licitatório específico. Isso exige a captura da hierarquia administrativa e geográfica completa (unidade gestora, ente, município), além de agregar simultaneamente múltiplos braços de cardinalidade 1:N (listas completas de documentos, contratos, itens de licitação, pessoas físicas/jurídicas e cotações).

**Estratégias de busca:**

* **Poliglota:** Aplica paralelismo em nível de aplicação. O sistema dispara uma *thread* para o PostgreSQL, que utiliza agregações JSON (`row_to_json`, `json_agg`) para serializar os dados da fonte principal em um único grande objeto; simultaneamente, dispara outra *thread* para o Neo4j usando múltiplos `UNION ALL` para recuperar as atualizações e entidades de fontes secundárias conectadas a esse ID, consolidando os retornos em memória.
* **Somente Grafo (Neo4j):** Partindo do nó do processo, realiza doze blocos de travessias distintas (algumas de profundidade 2 e 3, como processo $\to$ pessoa $\to$ pessoa_fisica) unidas por `UNION ALL`. A resposta devolve cada nó encontrado associado a uma *label* de tipo para que a aplicação cliente faça a montagem.
* **Multimodelo (ArangoDB):** Constrói a resposta inteira em um documento JSON hierárquico aninhado nativamente. O nó raiz é selecionado e múltiplos sub-loops de travessia em grafo (`FOR ... IN 1..1 ANY ...`) são injetados diretamente na projeção de retorno, comportando-se de maneira muito semelhante às agregações nativas JSON do PostgreSQL.

**Motivo da equivalência:**
Embora as ferramentas de serialização e transporte de dados divirjam (agregação JSON aninhada no Postgres e ArangoDB *versus* um conjunto de resultados achatado via `UNION` no Neo4j), todas as abordagens realizam o fecho transitivo das relações. Elas partem do mesmo nó central (identificador do processo) e caminham pelas mesmas ramificações e distâncias no modelo relacional ou de grafos. O agregado semântico obtido ao fim da execução encapsula rigorosamente a mesma árvore de documentos e sub-entidades.