# Gestão da Equipe

Ambiente para desenvolver ferramentas de gestão de equipe. Cada ferramenta
(férias, 1:1s, metas/OKRs, escala, avaliações…) é um módulo independente
que compartilha o mesmo banco, o mesmo cadastro de pessoas e o mesmo layout.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy · SQLite · Jinja2 (HTML server-side)

## Começando

```bash
make setup      # cria .venv e instala dependências
cp .env.example .env
make exemplo    # (opcional) popula com uma equipe fictícia — LIMPAR=1 recria do zero
make dev        # http://localhost:8000  (docs da API em /docs)
make test
```

## Estrutura

```
app/
  main.py               # cria o app e registra as ferramentas
  config.py             # configurações (.env)
  database.py           # engine, sessão e Base do SQLAlchemy
  web.py                # templates Jinja compartilhados
  ferramentas/
    __init__.py         # FERRAMENTAS = [...]  ← registro
    equipe/             # ferramenta base: cadastro de membros
      models.py  schemas.py  router.py
  templates/            # base.html, index.html, <ferramenta>/*.html
  static/style.css
scripts/nova_ferramenta.py
tests/
data/                   # banco SQLite local (não versionado)
```

## Criando uma nova ferramenta

```bash
make nova NOME=ferias
```

Isso gera `app/ferramentas/ferias/` (models, router, template) já registrada
no menu. Os modelos podem referenciar `membros.id` para ligar dados às pessoas.

Convenções:
- API JSON em `/api/<slug>`; páginas HTML em `/<slug>`.
- Tabelas prefixadas com o slug (`ferias_periodos`, …).
- Um arquivo de teste por ferramenta em `tests/`.

## Ferramentas

### Equipe
Cadastro de pessoas (cargo, área, admissão, nascimento), perfil individual que reúne os dados de
todas as ferramentas, aniversários e tempo de casa.

### Férias e Ausências (`/ausencias`)
- Pedidos de férias, folgas, licenças e treinamentos com fluxo **solicitada → aprovada/recusada/cancelada**
- **Saldo de férias pela CLT**: períodos aquisitivo/concessivo, alerta 60 dias antes do vencimento,
  férias vencidas, antecipadas e venda de até 10 dias (abono pecuniário)
- Avisos automáticos: início nos 2 dias antes de feriado/domingo (art. 134 §3º), parcelas < 5 dias,
  nenhuma parcela ≥ 14 dias, mais de 3 parcelas, saldo insuficiente
- **Cobertura mínima por área** e alerta de conflitos com colegas
- Calendário mensal com feriados nacionais (inclusive móveis), exportação CSV e iCal

### 1:1s (`/um_a_um`)
- Cadência configurável por pessoa (ou pausada), com situação **em dia / atrasada / agendada / nunca realizada**
- Registro de **humor** e **carga de trabalho** com gráficos de tendência e alertas
  (humor ≤ 2, queda de 2+ pontos, sobrecarga)
- **Tópicos** anotados entre conversas entram automaticamente na pauta da próxima 1:1
- **Ações combinadas** com responsável e prazo; as abertas são revisadas na reunião seguinte
- Notas privadas do gestor e banco de perguntas sugeridas

### Metas e OKRs (`/okrs`)
- Ciclos (ex.: trimestres) com objetivos da equipe ou individuais
- KRs numéricos, percentuais, em R$ ou sim/não — inclusive metas de **redução** (alvo menor que o inicial)
- **Check-ins** com confiança (1–10); status automático comparando progresso × tempo decorrido
  (no ritmo / atenção / em risco), **projeção** de fechamento e gráfico realizado × ritmo ideal
- Alerta de KRs sem check-in há mais de 14 dias; **duplicação de ciclo** partindo dos valores atuais

### Escalas (`/escalas`)
- Várias escalas (semanal, diária, quinzenal…) com ordem de rodízio ajustável
- Geração automática que **pula quem está de férias/ausente** (integra com Ausências) e compensa
  a pessoa no próximo turno; opção de apenas dias úteis (com feriados)
- **Trocas** e **permutas** de turno com histórico; trocas e turnos manuais são preservados ao regerar
- Alerta de **conflito** quando uma ausência é registrada depois da escala gerada
- Quadro de **equilíbrio** (turnos e dias por pessoa vs. média) e exportação iCal

### Avaliações (`/avaliacoes`)
- Ciclos com **critérios e pesos** configuráveis (modelo padrão com 6 critérios) e prazo de preenchimento
- **Autoavaliação × avaliação do gestor** lado a lado, com destaque de divergências ≥ 2 pontos
- **Nine-box** (desempenho × potencial), calibração com ranking e distribuição, exportação CSV
- **Feedback contínuo** (modelo SCI) que aparece como evidência na hora de avaliar;
  alerta de pessoas sem feedback há 45+ dias
- **PDI** no modelo 70-20-10 com prazos; resultado individual pronto para imprimir/PDF

### Competências (`/competencias`)
- Catálogo por categoria com **nível esperado**, marcação de **crítica** e meta de pessoas que dominam
- **Matriz** pessoas × competências (níveis 0–4) editável em uma tela, com marcação de interesse (♥)
- **Fator ônibus**: quantas pessoas dominam cada competência e o risco associado
- Cruza com Ausências: alerta de **dias sem ninguém que domine** uma competência crítica (próximos 30 dias)
- **Sugestões de mentoria** (referência → interessado) que viram item de PDI com um clique

## Como as ferramentas se conectam

- **Painel inicial**: cada ferramenta publica seus indicadores e alertas
- **Perfil da pessoa** (`/equipe/<id>`): reúne férias, 1:1s, OKRs, turnos, avaliação, PDI e competências
- Escalas pulam quem está ausente; Competências alertam dias críticos sem cobertura;
  mentorias de Competências geram itens de PDI em Avaliações

## API

Toda a funcionalidade também está disponível via API JSON (documentação interativa em `/docs`),
útil para integrar com planilhas, Qlik ou automações.

## Segurança

Os dados são sensíveis (avaliações, notas privadas de 1:1). Se for rodar fora da sua máquina,
defina `APP_USUARIO` e `APP_SENHA` no `.env` para exigir login, e use HTTPS.
