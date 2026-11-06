T1_NEO4J = """
MATCH (p:ProcessoLicitatorio)
WHERE ($edital IS NULL OR p.numero_edital = $edital)
  AND ($start_date IS NULL OR p.data_abertura >= $start_date)
  AND ($end_date IS NULL OR p.data_abertura <= $end_date)
RETURN p.id_processo_licitatorio AS id_processo_licitatorio,
       p.numero_processo_licitatorio AS numero_processo_licitatorio,
       p.numero_edital AS numero_edital,
       p.data_abertura AS data_abertura,
       p.descricao_objeto AS descricao_objeto,
       p.valor_previsto AS valor_previsto,
       p.fonte AS fonte
ORDER BY p.data_abertura, p.id_processo_licitatorio
LIMIT $limit
"""

T2_NEO4J = """
MATCH (p:ProcessoLicitatorio {codigo_fonte: 'PT'})
WHERE ($last_id IS NULL OR p.id_processo_licitatorio > $last_id)
WITH p
ORDER BY p.id_processo_licitatorio
LIMIT $size
RETURN p.id_processo_licitatorio AS id_processo_licitatorio,
       p.numero_edital AS numero_edital,
       p.numero_processo_licitatorio AS numero_processo_licitatorio,
       head([(p)-[:PROCESSO_LICITATORIO_MODALIDADE_LICITACAO]-(m:ModalidadeLicitacao) | m.descricao]) AS modalidade,
       head([(p)-[:PROCESSO_LICITATORIO_UNIDADE_GESTORA]-(ug:UnidadeGestora) | ug.nome_unidade]) AS unidade_gestora,
       p.data_abertura AS data_abertura,
       p.valor_previsto AS valor_previsto
ORDER BY id_processo_licitatorio
"""

T3_NEO4J = """
MATCH (p:ProcessoLicitatorio {id_processo_licitatorio: $id})
RETURN {
  processo_licitatorio: properties(p),
  modalidade_licitacao: head([(p)-[:PROCESSO_LICITATORIO_MODALIDADE_LICITACAO]-(m:ModalidadeLicitacao) | properties(m)]),
  unidade_gestora: head([(p)-[:PROCESSO_LICITATORIO_UNIDADE_GESTORA]-(ug:UnidadeGestora) | properties(ug)]),
  ente: head([(p)-[:PROCESSO_LICITATORIO_UNIDADE_GESTORA]-(ug:UnidadeGestora)-[:UNIDADE_GESTORA_ENTE]-(e:Ente) | properties(e)]),
  municipio: head([(p)-[:PROCESSO_LICITATORIO_UNIDADE_GESTORA]-(ug:UnidadeGestora)-[:UNIDADE_GESTORA_ENTE]-(e:Ente)-[:ENTE_MUNICIPIO]-(mu:Municipio) | properties(mu)]),
  documento: [(p)-[:DOCUMENTO_PROCESSO_LICITATORIO]-(d:Documento) | properties(d)],
  item_licitacao: [(p)-[:ITEM_LICITACAO_PROCESSO_LICITATORIO]-(i:ItemLicitacao) | properties(i)],
  contrato: [(p)-[:CONTRATO_PROCESSO_LICITATORIO]-(c:Contrato) | properties(c)],
  cotacao: [(p)-[:ITEM_LICITACAO_PROCESSO_LICITATORIO]-(i:ItemLicitacao)-[:ITEM_LICITACAO_COTACAO]-(ic:Cotacao) | properties(ic)]
} AS result
"""

T4_NEO4J = """
MATCH (n:ProcessoLicitatorio {id_processo_licitatorio: $id})
UNWIND keys(n) AS field
WITH n, field, n[field] AS val
WHERE valueType(val) STARTS WITH 'DATE'
   OR valueType(val) STARTS WITH 'LOCAL DATETIME'
   OR valueType(val) STARTS WITH 'ZONED DATETIME'
RETURN 'processo_licitatorio' AS entity_type, n.id_processo_licitatorio AS entity_id,
       field, n.fonte AS source, val AS date
UNION ALL
MATCH (:ProcessoLicitatorio {id_processo_licitatorio: $id})-[:CONTRATO_PROCESSO_LICITATORIO]-(n:Contrato)
UNWIND keys(n) AS field
WITH n, field, n[field] AS val
WHERE valueType(val) STARTS WITH 'DATE'
   OR valueType(val) STARTS WITH 'LOCAL DATETIME'
   OR valueType(val) STARTS WITH 'ZONED DATETIME'
RETURN 'contrato' AS entity_type, n.id_contrato AS entity_id,
       field, n.fonte AS source, val AS date
"""

T5_NEO4J = """
MATCH (pe:Pessoa)-[:PESSOA_PESSOA_JURIDICA]->(:PessoaJuridica)
MATCH (pe)-[:PESSOA_PROCESSO_LICITATORIO]->(p:ProcessoLicitatorio)
WITH p, collect(pe.id_pessoa) AS ids
WHERE size(ids) > 1
UNWIND range(0, size(ids) - 2) AS i
UNWIND range(i + 1, size(ids) - 1) AS j
WITH CASE WHEN ids[i] < ids[j] THEN ids[i] ELSE ids[j] END AS a,
     CASE WHEN ids[i] < ids[j] THEN ids[j] ELSE ids[i] END AS b
WITH a, b, count(*) AS qtd_licitacoes
WHERE qtd_licitacoes >= 2
RETURN a AS id_pessoa_a, b AS id_pessoa_b, qtd_licitacoes
ORDER BY qtd_licitacoes DESC, id_pessoa_a, id_pessoa_b
LIMIT 100
"""

T6_NEO4J = """
MATCH (e:Estabelecimento)-[:ESTABELECIMENTO_PESSOA_JURIDICA]->(pj:PessoaJuridica)
WHERE e.data_inicio_atividade IS NOT NULL
WITH pj, min(e.data_inicio_atividade) AS inicio
MATCH (pj)<-[:PESSOA_PESSOA_JURIDICA]-(:Pessoa)-[:PESSOA_PROCESSO_LICITATORIO]->(pm:ProcessoLicitatorio)
MATCH (v:ProcessoLicitatorio {id_processo_licitatorio: pm.id_processo_licitatorio})
WITH pj.id_pessoa AS id_pessoa, v, inicio,
     CASE WHEN v.codigo_fonte = 'PT' THEN v.data_abertura
          ELSE v[toLower(v.codigo_fonte) + '_data_abertura'] END AS data_abertura
WHERE data_abertura IS NOT NULL AND data_abertura < inicio
RETURN id_pessoa,
       v.id_processo_licitatorio AS id_processo_licitatorio,
       v.codigo_fonte AS codigo_fonte,
       toString(data_abertura) AS data_abertura,
       toString(inicio) AS data_inicio_atividade,
       duration.inDays(data_abertura, inicio).days AS dias_diferenca
ORDER BY id_pessoa, id_processo_licitatorio, codigo_fonte
"""

T7_NEO4J = """
MATCH (c:Contrato)
WITH c.id_contrato AS id_contrato, collect(c) AS versoes
WHERE size(versoes) > 1
WITH id_contrato, size(versoes) AS qtd, versoes
UNWIND versoes AS v
WITH id_contrato, qtd, v, toLower(v.codigo_fonte) + '_' AS prefixo
UNWIND [k IN keys(v) WHERE NOT k IN ['id_contrato', 'fonte', 'codigo_fonte']] AS k
WITH id_contrato, qtd,
     CASE WHEN v.codigo_fonte <> 'PT' AND k STARTS WITH prefixo
          THEN substring(k, size(prefixo)) ELSE k END AS atributo,
     v[k] AS valor
WITH id_contrato, qtd, atributo, count(*) AS presentes, count(DISTINCT valor) AS distintos
WITH id_contrato, qtd,
     max(CASE WHEN distintos > 1 THEN 1 ELSE 0 END) AS divergente,
     max(CASE WHEN presentes < qtd THEN 1 ELSE 0 END) AS parcial
RETURN id_contrato,
       qtd AS qtd_versoes,
       CASE WHEN divergente = 1 THEN 'divergente'
            WHEN parcial = 1 THEN 'complementar'
            ELSE 'identica' END AS classificacao
ORDER BY id_contrato
"""

T8_NEO4J = """
MATCH (c:Cotacao)
WHERE c.vencedor = true AND c.id_pessoa IS NOT NULL
MATCH (:PessoaJuridica {id_pessoa: c.id_pessoa})
MATCH (c)<-[:ITEM_LICITACAO_COTACAO]-(:ItemLicitacao)-[:ITEM_LICITACAO_PROCESSO_LICITATORIO]->(:ProcessoLicitatorio {codigo_fonte: 'PT'})
      -[:PROCESSO_LICITATORIO_UNIDADE_GESTORA]->(:UnidadeGestora)-[:UNIDADE_GESTORA_ENTE]->(en:Ente)
WHERE en.id_municipio IS NOT NULL
RETURN c.id_pessoa AS id_pessoa, count(DISTINCT en.id_municipio) AS qtd_municipios
ORDER BY qtd_municipios DESC, id_pessoa
"""

T9_NEO4J = """
MATCH (c:Contrato)
WITH c ORDER BY c.id_contrato, CASE WHEN c.codigo_fonte = 'PT' THEN 0 ELSE 1 END, c.codigo_fonte
WITH c.id_contrato AS id_contrato,
     head(collect(c.id_processo_licitatorio)) AS id_processo,
     head(collect(CASE WHEN c.codigo_fonte = 'PT' THEN c.valor_contrato
                       ELSE c[toLower(c.codigo_fonte) + '_valor_contrato'] END)) AS valor_contrato
WHERE id_processo IS NOT NULL AND valor_contrato IS NOT NULL
MATCH (p:ProcessoLicitatorio {id_processo_licitatorio: id_processo})
WITH id_contrato, id_processo, valor_contrato, p
ORDER BY id_contrato, CASE WHEN p.codigo_fonte = 'PT' THEN 0 ELSE 1 END, p.codigo_fonte
WITH id_contrato, id_processo, toFloat(valor_contrato) AS valor_contrato,
     toFloat(head(collect(CASE WHEN p.codigo_fonte = 'PT' THEN p.valor_previsto
                               ELSE p[toLower(p.codigo_fonte) + '_valor_previsto'] END))) AS valor_previsto
WHERE valor_previsto IS NOT NULL
RETURN id_processo AS id_processo_licitatorio,
       id_contrato AS id_contrato,
       valor_previsto AS valor_previsto,
       valor_contrato AS valor_contrato,
       round((valor_contrato - valor_previsto) * 100) / 100.0 AS diferenca
ORDER BY id_contrato
"""

T10_NEO4J = """
MATCH (i:ItemLicitacao)-[:ITEM_LICITACAO_COTACAO]->(c:Cotacao)
WHERE c.valor_cotado IS NOT NULL
WITH i.id_item AS id_item, min(c.valor_cotado) AS menor_valor, collect(c) AS cotacoes
UNWIND cotacoes AS w
WITH id_item, menor_valor, w
WHERE w.vencedor = true AND w.valor_cotado > menor_valor
RETURN id_item,
       w.id_cotacao AS id_cotacao_vencedora,
       w.valor_cotado AS valor_vencedor,
       menor_valor,
       round((w.valor_cotado - menor_valor) * 100) / 100 AS diferenca
ORDER BY id_item, id_cotacao_vencedora
"""