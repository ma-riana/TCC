# Avaliação de arquiteturas de bancos de dados no contexto de Licitações Públicas

Este repositório contém o código para o Trabalho de Conclusão de Curso (TCC) focado na análise comparativa de desempenho entre persistência poliglota, bancos multimodelo e bancos de dados em grafo no contexto de licitações públicas brasileiras.

## Estrutura 

* `data_insertion/`: Scripts de inserção de dados para as diferentes arquiteturas (`graph_insertion.py`, `multimodel_insertion.py`, `polyglot_insertion.py`).
* `fake_data/`: Módulo responsável pelo gerador de dados sintéticos (`csv_generator.py`) e armazenamento dos CSVs gerados.
* `run_tasks/`: Orquestrador central dos testes de benchmark (`main.py`) e serviços de execução.
* `schemas/`: Scripts e definições de esquema (DDL) exigidos pelos bancos estruturados (como o PostgreSQL).
* `utils/`: Consultas das tarefas (queries) específicas de cada banco, conexões e utilitários para a plotagem dos gráficos de resultados.

## Pré-requisitos

* Python 3+
* Docker e Docker Compose configurados no ambiente.
* Variáveis de ambiente configuradas no arquivo `.env` (credenciais e portas dos bancos rodando no Docker).

---

## Instruções de Uso

### 1. Geração dos Dados Sintéticos

```bash
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
cd fake_data
python csv_generator.py
cd ..
```

### 2. Inicialização e População dos Bancos de Dados

**Detalhe da Arquitetura Poliglota:** 
Antes de executar o script de inserção da arquitetura poliglota, é necessário rodar o esquema no PostgreSQL (localizado em `schemas/`) para estruturar as tabelas relacionais.

Com os bancos online e o esquema do Postgres pronto, execute as inserções:

```bash
cd data_insertion
python polyglot_insertion.py
python multimodel_insertion.py
python graph_insertion.py

cd ..
```
*(Rodar separadamente as inserções nos volumes maiores, com apenas um container ativo, para evitar sobrecarga do sistema).*

### 3. Execução das Tasks
As tarefas (T1 a T10) são controladas pelo script `main.py` dentro do diretório `run_tasks/`. O orquestrador permite testar as arquiteturas de forma isolada ou conjunta, controlando também o número de repetições.

**Parâmetros suportados:**
* `--arch`: Define qual arquitetura será testada. 
  * Escolhas: `polyglot`, `graph`, `multimodel`, `all`
  * Padrão: `all`
* `--runs`: Define o número de execuções (repetições) para cada consulta para extração de médias de tempo.
  * Padrão: `1`

**Exemplos de execução:**

```bash
python run_tasks/main.py --arch all
python run_tasks/main.py --arch polyglot --runs 5
python run_tasks/main.py --arch multimodel --runs 10
```

Os gráficos de desempenho e os *logs* de saída serão armazenados em suas respectivas pastas (`utils/graficos_*` e `run_tasks/logs/`).