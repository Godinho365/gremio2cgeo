# Índice da Documentação — Patrimonia

Mapa de navegação. **Leia apenas o arquivo relevante** à sua tarefa (progressive disclosure = menos token).

| Precisa de… | Leia |
|---|---|
| Visão de produto, escopo, objetivos | `produto/prd.md` |
| Perfis de usuário e permissões | `produto/personas-perfis.md` |
| Arquitetura, camadas, padrões | `arquitetura/visao-geral.md` |
| Stack e versões | `arquitetura/stack.md` |
| Decisões técnicas (ADRs) | `arquitetura/adr/README.md` |
| **Vocabulário do domínio** | `dominio/glossario.md` |
| **Entidades e modelo de dados** | `dominio/entidades.md` |
| Regras de negócio (invariantes) | `dominio/regras-negocio.md` |
| **Fluxos + diagramas Mermaid** | `dominio/fluxos.md` |
| Detalhe de um módulo | `modulos/<nome>.md` |
| Convenções de API REST | `api/convencoes.md` |
| Sprints / roadmap | `processo/sprints.md` |
| Definição de pronto | `processo/definition-of-done.md` |

## Legenda de status
- ✅ **Completo** — pronto para guiar implementação
- 🟡 **Núcleo** — essencial escrito, faltam detalhes
- ⛔ **Stub** — estrutura pronta, conteúdo a preencher

## Estado atual
```
produto/
  prd.md ..................... ⛔
  personas-perfis.md ........ 🟡
arquitetura/
  visao-geral.md ............ ✅
  stack.md .................. ✅
  adr/README.md ............. 🟡 (template + índice)
dominio/
  glossario.md .............. ✅
  entidades.md .............. ✅
  regras-negocio.md ......... 🟡
  fluxos.md ................. ✅
modulos/
  _template.md .............. ✅ (modelo)
  patrimonio.md ............. 🟡  (Art.30 a)
  inventario.md ............. 🟡  (Art.30 b)
  manutencao.md ............. ⛔  (Art.30 c)
  cautelas.md ............... ✅  (Art.30 d)
  agenda.md ................. ⛔
  reservas.md ............... ⛔
  dashboard.md .............. ⛔
  relatorios.md ............. ⛔
api/
  convencoes.md ............. 🟡
processo/
  sprints.md ................ ✅
  definition-of-done.md ..... ✅
```

## Rastreabilidade legal (Estatuto Art. 30)
O sistema materializa as competências do Diretor(a) de Patrimônio:

| Alínea | Competência | Onde vive no sistema |
|---|---|---|
| a) | Identificar/catalogar bens + etiquetas/numeração | `modulos/patrimonio.md` |
| b) | Levantamentos periódicos (conferência de local) | `modulos/inventario.md` |
| c) | Acondicionamento e proteção dos bens | `modulos/manutencao.md` + atributos do bem |
| d) | Termos de cautela assinados + inspeção na devolução | `modulos/cautelas.md` |
