T1_POSTGRES = """
SELECT id_processo_licitatorio, numero_processo_licitatorio, numero_edital,
       data_abertura, descricao_objeto, valor_previsto, fonte
FROM processo_licitatorio
WHERE (%(edital)s::text IS NULL OR numero_edital = %(edital)s)
  AND (%(start_date)s::date IS NULL OR data_abertura >= %(start_date)s)
  AND (%(end_date)s::date IS NULL OR data_abertura <= %(end_date)s)
ORDER BY data_abertura, id_processo_licitatorio
LIMIT %(limit)s
"""

T2_POSTGRES = """
SELECT p.id_processo_licitatorio, p.numero_edital, p.numero_processo_licitatorio,
       m.descricao AS modalidade,
       ug.nome_unidade AS unidade_gestora,
       p.data_abertura, p.valor_previsto
FROM processo_licitatorio p
LEFT JOIN modalidade_licitacao m ON m.id_modalidade_licitacao = p.id_modalidade_licitacao
LEFT JOIN unidade_gestora ug ON ug.id_unidade_gestora = p.id_unidade_gestora
WHERE (%(last_id)s::bigint IS NULL OR p.id_processo_licitatorio > %(last_id)s)
ORDER BY p.id_processo_licitatorio
LIMIT %(size)s
"""

T3_POSTGRES = """
SELECT
    row_to_json(p.*) AS processo_licitatorio,
    row_to_json(m.*) AS modalidade_licitacao,
    row_to_json(ug.*) AS unidade_gestora,
    row_to_json(e.*) AS ente,
    row_to_json(mu.*) AS municipio,
    (
        SELECT json_agg(row_to_json(d.*))
        FROM documento d
        WHERE d.id_processo_licitatorio = p.id_processo_licitatorio
    ) AS documento,
    (
        SELECT json_agg(row_to_json(i.*))
        FROM item_licitacao i
        WHERE i.id_processo_licitatorio = p.id_processo_licitatorio
    ) AS item_licitacao,
    (
        SELECT json_agg(row_to_json(c.*))
        FROM contrato c
        WHERE c.id_processo_licitatorio = p.id_processo_licitatorio
    ) AS contrato,
    (
        SELECT json_agg(row_to_json(q.*))
        FROM item_licitacao i
        JOIN item_cotacao ic ON ic.id_item = i.id_item
        JOIN cotacao q ON q.id_cotacao = ic.id_cotacao
        WHERE i.id_processo_licitatorio = p.id_processo_licitatorio
    ) AS cotacao
FROM processo_licitatorio p
LEFT JOIN modalidade_licitacao m ON m.id_modalidade_licitacao = p.id_modalidade_licitacao
LEFT JOIN unidade_gestora ug ON ug.id_unidade_gestora = p.id_unidade_gestora
LEFT JOIN ente e ON e.id_ente = ug.id_ente
LEFT JOIN municipio mu ON mu.id_municipio = e.id_municipio
WHERE p.id_processo_licitatorio = %(id)s;
"""

T3_NEO4J = """
MATCH (n:ProcessoLicitatorio {id_processo_licitatorio: $id})
RETURN DISTINCT 'processo_licitatorio' AS entity_type, properties(n) AS props
UNION ALL
MATCH (n:ItemLicitacao {id_processo_licitatorio: $id})
RETURN DISTINCT 'item_licitacao' AS entity_type, properties(n) AS props
UNION ALL
MATCH (n:Contrato {id_processo_licitatorio: $id})
RETURN DISTINCT 'contrato' AS entity_type, properties(n) AS props
"""


T4_POSTGRES = """
SELECT 'processo_licitatorio' AS entity_type, p.id_processo_licitatorio AS entity_id,
       v.field, p.fonte AS source, v.date_val AS date
FROM processo_licitatorio p
CROSS JOIN LATERAL (VALUES
         ('data_limite_propostas', p.data_limite_propostas),
         ('data_aprovacao_acessoria_juridica', p.data_aprovacao_acessoria_juridica),
         ('data_abertura', p.data_abertura),
         ('data_planilha_custos', p.data_planilha_custos),
         ('data_homologacao', p.data_homologacao),
         ('competencia', p.competencia)
       ) AS v(field, date_val)
WHERE p.id_processo_licitatorio = %(id)s AND v.date_val IS NOT NULL
UNION ALL
SELECT 'contrato', c.id_contrato, v.field, c.fonte, v.date_val
FROM contrato c
CROSS JOIN LATERAL (VALUES
         ('data_assinatura', c.data_assinatura),
         ('data_vencimento', c.data_vencimento),
         ('competencia', c.competencia),
         ('data_autorizacao_estadual', c.data_autorizacao_estadual)
       ) AS v(field, date_val)
WHERE c.id_processo_licitatorio = %(id)s AND v.date_val IS NOT NULL
"""

T4_NEO4J = """
MATCH (n:ProcessoLicitatorio {id_processo_licitatorio: $id})
UNWIND keys(n) AS field
WITH n, field, n[field] AS val
WHERE valueType(val) STARTS WITH 'DATE'
   OR valueType(val) STARTS WITH 'LOCAL DATETIME'
   OR valueType(val) STARTS WITH 'ZONED DATETIME'
RETURN 'processo_licitatorio' AS entity_type, n.id_processo_licitatorio AS entity_id,
       field, n.codigo_fonte AS source, val AS date
UNION ALL
MATCH (n:Contrato {id_processo_licitatorio: $id})
UNWIND keys(n) AS field
WITH n, field, n[field] AS val
WHERE valueType(val) STARTS WITH 'DATE'
   OR valueType(val) STARTS WITH 'LOCAL DATETIME'
   OR valueType(val) STARTS WITH 'ZONED DATETIME'
RETURN 'contrato' AS entity_type, n.id_contrato AS entity_id,
       field, n.codigo_fonte AS source, val AS date
"""


T5_POSTGRES = """
WITH participantes AS (
    SELECT ppl.id_processo_licitatorio, ppl.id_pessoa
    FROM processo_licitatorio_pessoa ppl
    JOIN pessoa_juridica pj ON pj.id_pessoa = ppl.id_pessoa
)
SELECT a.id_pessoa AS id_pessoa_a,
       b.id_pessoa AS id_pessoa_b,
       COUNT(*)    AS qtd_licitacoes
FROM participantes a
JOIN participantes b
  ON b.id_processo_licitatorio = a.id_processo_licitatorio
 AND a.id_pessoa < b.id_pessoa
GROUP BY a.id_pessoa, b.id_pessoa
HAVING COUNT(*) >= 2
ORDER BY qtd_licitacoes DESC, id_pessoa_a, id_pessoa_b
LIMIT 100
"""

T6_NEO4J = """
MATCH (p:ProcessoLicitatorio)
WITH p, p[toLower(p.codigo_fonte) + '_data_abertura'] AS data_abertura
WHERE data_abertura IS NOT NULL
RETURN p.id_processo_licitatorio AS id_processo_licitatorio,
       p.codigo_fonte            AS codigo_fonte,
       toString(data_abertura)   AS data_abertura
"""

T6_POSTGRES = """
WITH inicio AS (
    SELECT e.id_pessoa_juridica AS id_pessoa,
           MIN(e.data_inicio_atividade::date) AS data_inicio_atividade
    FROM estabelecimento e
    WHERE e.data_inicio_atividade IS NOT NULL
    GROUP BY e.id_pessoa_juridica
),
versoes AS (
    SELECT id_processo_licitatorio, 'PT'::text AS codigo_fonte, data_abertura::date AS data_abertura
    FROM processo_licitatorio
    WHERE data_abertura IS NOT NULL
    UNION ALL
    SELECT s.id_processo_licitatorio, s.codigo_fonte, s.data_abertura
    FROM unnest(%(ids)s::bigint[], %(fontes)s::text[], %(datas)s::date[])
         AS s(id_processo_licitatorio, codigo_fonte, data_abertura)
)
SELECT ppl.id_pessoa,
       v.id_processo_licitatorio,
       v.codigo_fonte,
       v.data_abertura::text                 AS data_abertura,
       i.data_inicio_atividade::text         AS data_inicio_atividade,
       (i.data_inicio_atividade - v.data_abertura) AS dias_diferenca
FROM processo_licitatorio_pessoa ppl
JOIN inicio i  ON i.id_pessoa = ppl.id_pessoa
JOIN versoes v ON v.id_processo_licitatorio = ppl.id_processo_licitatorio
WHERE v.data_abertura < i.data_inicio_atividade
ORDER BY ppl.id_pessoa, v.id_processo_licitatorio, v.codigo_fonte
"""


T7_NEO4J = """
MATCH (c:Contrato)
WITH c, toLower(c.codigo_fonte) + '_' AS prefixo
RETURN c.id_contrato AS id_contrato,
       c.codigo_fonte AS codigo_fonte,
       [k IN keys(c) WHERE NOT k IN ['id_contrato', 'fonte', 'codigo_fonte'] |
           {a: CASE WHEN k STARTS WITH prefixo THEN substring(k, size(prefixo)) ELSE k END,
            v: c[k]}] AS atributos
"""

T7_POSTGRES = """
WITH sec AS (
    SELECT (s->>'id_contrato')::bigint AS id_contrato,
           s->>'codigo_fonte'          AS fonte,
           s->'atributos'              AS atributos
    FROM jsonb_array_elements(%(versoes)s::jsonb) AS s
),
todas_versoes AS (
    SELECT id_contrato, fonte FROM sec
    UNION ALL
    SELECT c.id_contrato, 'PT'
    FROM contrato c
    WHERE c.id_contrato IN (SELECT id_contrato FROM sec)
),
qtd AS (
    SELECT id_contrato, COUNT(*) AS qtd_versoes
    FROM todas_versoes
    GROUP BY id_contrato
    HAVING COUNT(*) > 1
),
atributos AS (
    SELECT sec.id_contrato, a->>'a' AS atributo, a->'v' AS valor
    FROM sec
    JOIN qtd USING (id_contrato)
    CROSS JOIN LATERAL jsonb_array_elements(sec.atributos) AS a
    UNION ALL
    SELECT c.id_contrato, kv.key, kv.value
    FROM contrato c
    JOIN qtd USING (id_contrato)
    CROSS JOIN LATERAL jsonb_each(jsonb_strip_nulls(to_jsonb(c))) AS kv
    WHERE kv.key NOT IN ('id_contrato', 'fonte', 'codigo_fonte')
),
agregado AS (
    SELECT id_contrato, atributo,
           COUNT(*)               AS presentes,
           COUNT(DISTINCT valor)  AS distintos
    FROM atributos
    GROUP BY id_contrato, atributo
)
SELECT q.id_contrato,
       q.qtd_versoes,
       CASE WHEN COALESCE(bool_or(a.distintos > 1), false)              THEN 'divergente'
            WHEN COALESCE(bool_or(a.presentes < q.qtd_versoes), false)  THEN 'complementar'
            ELSE 'identica'
       END AS classificacao
FROM qtd q
LEFT JOIN agregado a ON a.id_contrato = q.id_contrato
GROUP BY q.id_contrato, q.qtd_versoes
ORDER BY q.id_contrato
"""

T8_POSTGRES = """
SELECT c.id_pessoa,
       COUNT(DISTINCT e.id_municipio) AS qtd_municipios
FROM cotacao c
JOIN pessoa_juridica pj        ON pj.id_pessoa = c.id_pessoa
JOIN item_cotacao ic           ON ic.id_cotacao = c.id_cotacao
JOIN item_licitacao i          ON i.id_item = ic.id_item
JOIN processo_licitatorio p    ON p.id_processo_licitatorio = i.id_processo_licitatorio
JOIN unidade_gestora ug        ON ug.id_unidade_gestora = p.id_unidade_gestora
JOIN ente e                    ON e.id_ente = ug.id_ente
WHERE c.vencedor
  AND e.id_municipio IS NOT NULL
GROUP BY c.id_pessoa
ORDER BY qtd_municipios DESC, c.id_pessoa
"""


T9_NEO4J = """
MATCH (c:Contrato)
WITH c ORDER BY c.id_contrato, c.codigo_fonte
WITH c.id_contrato AS id,
     head(collect(c.id_processo_licitatorio)) AS id_processo,
     head(collect(c[toLower(c.codigo_fonte) + '_valor_contrato'])) AS valor
WHERE id_processo IS NOT NULL OR valor IS NOT NULL
RETURN 'contrato' AS tipo, id, id_processo, valor
UNION ALL
MATCH (p:ProcessoLicitatorio)
WITH p ORDER BY p.id_processo_licitatorio, p.codigo_fonte
WITH p.id_processo_licitatorio AS id,
     head(collect(p[toLower(p.codigo_fonte) + '_valor_previsto'])) AS valor
WHERE valor IS NOT NULL
RETURN 'processo' AS tipo, id, null AS id_processo, valor
"""

T9_POSTGRES = """
WITH sec AS (
    SELECT * FROM jsonb_to_recordset(%(sec)s::jsonb)
         AS x(tipo text, id bigint, id_processo bigint, valor numeric)
),
contratos AS (
    SELECT COALESCE(c.id_contrato, s.id)                              AS id_contrato,
           COALESCE(c.id_processo_licitatorio, s.id_processo)         AS id_processo_licitatorio,
           COALESCE(c.valor_contrato::numeric, s.valor)               AS valor_contrato
    FROM contrato c
    FULL JOIN (SELECT id, id_processo, valor FROM sec WHERE tipo = 'contrato') s
           ON s.id = c.id_contrato
),
processos AS (
    SELECT COALESCE(p.id_processo_licitatorio, s.id)                  AS id_processo_licitatorio,
           COALESCE(p.valor_previsto::numeric, s.valor)               AS valor_previsto
    FROM processo_licitatorio p
    FULL JOIN (SELECT id, valor FROM sec WHERE tipo = 'processo') s
           ON s.id = p.id_processo_licitatorio
)
SELECT c.id_processo_licitatorio,
       c.id_contrato,
       p.valor_previsto,
       c.valor_contrato,
       ROUND(c.valor_contrato - p.valor_previsto, 2) AS diferenca
FROM contratos c
JOIN processos p ON p.id_processo_licitatorio = c.id_processo_licitatorio
WHERE c.valor_contrato IS NOT NULL
  AND p.valor_previsto IS NOT NULL
ORDER BY c.id_contrato
"""


T10_POSTGRES = """
WITH cot AS (
    SELECT ic.id_item, c.id_cotacao, c.valor_cotado, c.vencedor,
           MIN(c.valor_cotado) OVER (PARTITION BY ic.id_item) AS menor_valor
    FROM item_cotacao ic
    JOIN cotacao c ON c.id_cotacao = ic.id_cotacao
    WHERE c.valor_cotado IS NOT NULL
)
SELECT id_item,
       id_cotacao                              AS id_cotacao_vencedora,
       valor_cotado                            AS valor_vencedor,
       menor_valor,
       ROUND((valor_cotado - menor_valor)::numeric, 2) AS diferenca
FROM cot
WHERE vencedor AND valor_cotado > menor_valor
ORDER BY id_item, id_cotacao
"""