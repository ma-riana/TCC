T1_ARANGO = """
FOR p IN processo_licitatorio
  FILTER (@edital == null OR p.numero_edital == @edital)
  FILTER (@start_date == null OR p.data_abertura >= @start_date)
  FILTER (@end_date == null OR p.data_abertura <= @end_date)
  SORT p.data_abertura ASC, p.id_processo_licitatorio ASC
  LIMIT @limit
  RETURN {
    id_processo_licitatorio: p.id_processo_licitatorio,
    numero_processo_licitatorio: p.numero_processo_licitatorio,
    numero_edital: p.numero_edital,
    data_abertura: p.data_abertura,
    descricao_objeto: p.descricao_objeto,
    valor_previsto: p.valor_previsto,
    fonte: p.fonte
  }
"""

T2_ARANGO = """
FOR p IN processo_licitatorio
  FILTER p.codigo_fonte == 'PT'
  FILTER (@last_id == null OR p.id_processo_licitatorio > @last_id)
  SORT p.id_processo_licitatorio ASC
  LIMIT @size

  LET modalidade = FIRST(
    FOR m IN 1..1 ANY p PROCESSO_LICITATORIO_MODALIDADE_LICITACAO
      SORT m.descricao ASC
      RETURN m.descricao
  )

  LET unidade = FIRST(
    FOR ug IN 1..1 ANY p PROCESSO_LICITATORIO_UNIDADE_GESTORA
      SORT ug.nome_unidade ASC
      RETURN ug.nome_unidade
  )

  RETURN {
    id_processo_licitatorio: p.id_processo_licitatorio,
    numero_edital: p.numero_edital,
    numero_processo_licitatorio: p.numero_processo_licitatorio,
    modalidade: modalidade,
    unidade_gestora: unidade,
    data_abertura: p.data_abertura,
    valor_previsto: p.valor_previsto
  }
"""

T3_ARANGO = """
FOR p IN processo_licitatorio
  FILTER p.id_processo_licitatorio == @id
  RETURN {
    processo_licitatorio: p,
    modalidade_licitacao: FIRST(FOR m IN 1..1 ANY p PROCESSO_LICITATORIO_MODALIDADE_LICITACAO RETURN m),
    unidade_gestora: FIRST(FOR ug IN 1..1 ANY p PROCESSO_LICITATORIO_UNIDADE_GESTORA RETURN ug),
    ente: FIRST(
      FOR ug IN 1..1 ANY p PROCESSO_LICITATORIO_UNIDADE_GESTORA
        FOR e IN 1..1 ANY ug UNIDADE_GESTORA_ENTE
          RETURN e
    ),
    municipio: FIRST(
      FOR ug IN 1..1 ANY p PROCESSO_LICITATORIO_UNIDADE_GESTORA
        FOR e IN 1..1 ANY ug UNIDADE_GESTORA_ENTE
          FOR mu IN 1..1 ANY e ENTE_MUNICIPIO
            RETURN mu
    ),
    documento: (FOR d IN 1..1 ANY p DOCUMENTO_PROCESSO_LICITATORIO RETURN d),
    item_licitacao: (FOR i IN 1..1 ANY p ITEM_LICITACAO_PROCESSO_LICITATORIO RETURN i),
    contrato: (FOR c IN 1..1 ANY p CONTRATO_PROCESSO_LICITATORIO RETURN c),
    cotacao: (
      FOR i IN 1..1 ANY p ITEM_LICITACAO_PROCESSO_LICITATORIO
        FOR ic IN 1..1 ANY i ITEM_LICITACAO_COTACAO
          RETURN ic
    )
  }
"""

T4_ARANGO = """
LET p_events = (
  FOR p IN processo_licitatorio
    FILTER p.id_processo_licitatorio == @id
    FOR field IN ATTRIBUTES(p, true)
      LET val = p[field]
      FILTER IS_STRING(val) AND REGEX_TEST(val, '^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T].*)?$')
      RETURN {
        entity_type: "processo_licitatorio",
        entity_id: p.id_processo_licitatorio,
        field: field,
        source: p.fonte,
        date: val
      }
)
 
LET contratos = UNIQUE(
  FOR p IN processo_licitatorio
    FILTER p.id_processo_licitatorio == @id
    FOR c IN 1..1 ANY p CONTRATO_PROCESSO_LICITATORIO
      RETURN c
)
 
LET c_events = (
  FOR c IN contratos
    FOR field IN ATTRIBUTES(c, true)
      LET val = c[field]
      FILTER IS_STRING(val) AND REGEX_TEST(val, '^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T].*)?$')
      RETURN {
        entity_type: "contrato",
        entity_id: c.id_contrato,
        field: field,
        source: c.fonte,
        date: val
      }
)
 
RETURN UNION(p_events, c_events)
"""

T5_ARANGO = """
FOR e IN PESSOA_PROCESSO_LICITATORIO
    LET pessoa_key = PARSE_IDENTIFIER(e._from).key
    FILTER DOCUMENT('pessoa_juridica', pessoa_key) != null
    COLLECT processo = e._to INTO membros = TO_NUMBER(pessoa_key)
    LET ids = SORTED_UNIQUE(membros)
    LET n = LENGTH(ids)
    FILTER n > 1
    FOR i IN 0..(n - 2)
        FOR j IN (i + 1)..(n - 1)
            COLLECT a = ids[i], b = ids[j] WITH COUNT INTO qtd_licitacoes
            FILTER qtd_licitacoes >= 2
            SORT qtd_licitacoes DESC, a, b
            LIMIT 100
            RETURN { id_pessoa_a: a, id_pessoa_b: b, qtd_licitacoes: qtd_licitacoes }
"""

T6_ARANGO = """
FOR est IN estabelecimento
    FILTER est.data_inicio_atividade != null
    FOR pj IN 1..1 OUTBOUND est ESTABELECIMENTO_PESSOA_JURIDICA
        COLLECT id_pessoa = pj.id_pessoa AGGREGATE inicio = MIN(LEFT(est.data_inicio_atividade, 10))
        FOR proc IN 1..1 OUTBOUND CONCAT('pessoa/', id_pessoa) PESSOA_PROCESSO_LICITATORIO
            FOR v IN processo_licitatorio
                FILTER v.id_processo_licitatorio == proc.id_processo_licitatorio
                LET bruta = v.codigo_fonte == 'PT'
                            ? v.data_abertura
                            : v[CONCAT(LOWER(v.codigo_fonte), '_data_abertura')]
                FILTER bruta != null AND LEFT(bruta, 10) < inicio
                SORT id_pessoa, v.id_processo_licitatorio, v.codigo_fonte
                RETURN {
                    id_pessoa: id_pessoa,
                    id_processo_licitatorio: v.id_processo_licitatorio,
                    codigo_fonte: v.codigo_fonte,
                    data_abertura: LEFT(bruta, 10),
                    data_inicio_atividade: inicio,
                    dias_diferenca: DATE_DIFF(LEFT(bruta, 10), inicio, 'days')
                }
"""

T7_ARANGO = """
FOR c IN contrato
    COLLECT id = c.id_contrato INTO grupo = c
    LET qtd = LENGTH(grupo)
    FILTER qtd > 1
    LET atributos = (
        FOR v IN grupo
            LET prefixo = CONCAT(LOWER(v.codigo_fonte), '_')
            FOR k IN ATTRIBUTES(v, true)
                FILTER k NOT IN ['id_contrato', 'fonte', 'codigo_fonte']
                LET nome = (v.codigo_fonte != 'PT' AND LEFT(k, LENGTH(prefixo)) == prefixo)
                           ? SUBSTRING(k, LENGTH(prefixo)) : k
                LET valor = (IS_STRING(v[k]) AND REGEX_TEST(v[k], '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T]'))
                            ? LEFT(v[k], 10) : v[k]
                COLLECT atributo = nome INTO valores = valor
                RETURN { presentes: LENGTH(valores), distintos: LENGTH(UNIQUE(valores)) }
    )
    LET divergente = LENGTH(FOR a IN atributos FILTER a.distintos > 1 LIMIT 1 RETURN 1) > 0
    LET parcial = LENGTH(FOR a IN atributos FILTER a.presentes < qtd LIMIT 1 RETURN 1) > 0
    SORT id
    RETURN {
        id_contrato: id,
        qtd_versoes: qtd,
        classificacao: divergente ? 'divergente' : (parcial ? 'complementar' : 'identica')
    }
"""

T8_ARANGO = """
FOR c IN cotacao
    FILTER c.vencedor == true AND c.id_pessoa != null
    FILTER DOCUMENT('pessoa_juridica', TO_STRING(c.id_pessoa)) != null
    FOR i IN 1..1 INBOUND c ITEM_LICITACAO_COTACAO
        FOR p IN 1..1 OUTBOUND i ITEM_LICITACAO_PROCESSO_LICITATORIO
            FILTER p.codigo_fonte == 'PT'
            FOR ug IN 1..1 OUTBOUND p PROCESSO_LICITATORIO_UNIDADE_GESTORA
                FOR en IN 1..1 OUTBOUND ug UNIDADE_GESTORA_ENTE
                    FILTER en.id_municipio != null
                    COLLECT id_pessoa = c.id_pessoa AGGREGATE qtd_municipios = COUNT_DISTINCT(en.id_municipio)
                    SORT qtd_municipios DESC, id_pessoa
                    RETURN { id_pessoa: id_pessoa, qtd_municipios: qtd_municipios }
"""

T9_ARANGO = """
FOR c IN contrato
    COLLECT id = c.id_contrato INTO versoes = {
        fonte: c.codigo_fonte,
        proc: c.id_processo_licitatorio,
        valor: c.codigo_fonte == 'PT'
               ? c.valor_contrato
               : c[CONCAT(LOWER(c.codigo_fonte), '_valor_contrato')]
    }
    LET ord = (FOR v IN versoes SORT (v.fonte == 'PT' ? 0 : 1), v.fonte RETURN v)
    LET id_processo = FIRST(FOR v IN ord FILTER v.proc != null LIMIT 1 RETURN v.proc)
    LET valor_contrato = FIRST(FOR v IN ord FILTER v.valor != null LIMIT 1 RETURN v.valor)
    FILTER id_processo != null AND valor_contrato != null
    LET valor_previsto = FIRST(
        FOR p IN processo_licitatorio
            FILTER p.id_processo_licitatorio == id_processo
            SORT (p.codigo_fonte == 'PT' ? 0 : 1), p.codigo_fonte
            LET val = p.codigo_fonte == 'PT'
                      ? p.valor_previsto
                      : p[CONCAT(LOWER(p.codigo_fonte), '_valor_previsto')]
            FILTER val != null
            LIMIT 1
            RETURN val
    )
    FILTER valor_previsto != null
    SORT id
    RETURN {
        id_processo_licitatorio: id_processo,
        id_contrato: id,
        valor_previsto: valor_previsto,
        valor_contrato: valor_contrato,
        diferenca: ROUND((valor_contrato - valor_previsto) * 100) / 100
    }
"""

T10_ARANGO = """
FOR e IN ITEM_LICITACAO_COTACAO
    LET c = DOCUMENT(e._to)
    FILTER c.valor_cotado != null
    COLLECT item = e._from INTO cotacoes = {
        id_cotacao: c.id_cotacao, valor: c.valor_cotado, vencedor: c.vencedor
    }
    LET menor_valor = MIN(cotacoes[*].valor)
    FOR w IN cotacoes
        FILTER w.vencedor == true AND w.valor > menor_valor
        LET id_item = TO_NUMBER(PARSE_IDENTIFIER(item).key)
        SORT id_item, w.id_cotacao
        RETURN {
            id_item: id_item,
            id_cotacao_vencedora: w.id_cotacao,
            valor_vencedor: w.valor,
            menor_valor: menor_valor,
            diferenca: ROUND((w.valor - menor_valor) * 100) / 100
        }
"""