# Fluxos de Negócio ✅

## 1. Ciclo de vida do Bem (máquina de estados)

```mermaid
stateDiagram-v2
    [*] --> disponivel : cadastro + etiqueta (Art.30 a)
    disponivel --> reservado : reserva aprovada
    reservado --> em_uso : cautela assinada (Art.30 d)
    reservado --> disponivel : cancelamento
    em_uso --> disponivel : devolução + inspeção OK (Art.30 d)
    em_uso --> manutencao : inspeção com dano (Art.30 c)
    disponivel --> manutencao : manutenção preventiva
    manutencao --> disponivel : manutenção concluída
    disponivel --> baixado : baixa
    manutencao --> baixado : inservível
    baixado --> [*]
```

## 2. Fluxo principal: Pesquisar → Cautela → Inspeção (Art.30 d) ⭐

```mermaid
sequenceDiagram
    actor U as Usuário
    participant A as Agenda/Busca
    participant B as Reserva (Booking)
    participant D as Diretor Patrimonial
    participant C as Cautela (Custody)
    participant I as Inspeção

    U->>A: pesquisa bem + disponibilidade
    U->>B: solicita reserva (período)
    B->>D: notifica aprovação pendente
    D-->>B: aprova / recusa
    Note over B: sem sobreposição de horários
    D->>C: gera termo de responsabilidade
    C->>U: coleta assinatura (holder)
    C->>D: coleta assinatura (issuer)
    Note over C: bem → em_uso · condition_out registrada
    U->>C: devolve bem no prazo
    C->>I: inspeção (condition_in, fotos)
    alt sem dano
        I-->>C: outcome=ok → bem disponível
    else com dano/faltante
        I-->>C: abre Manutenção ou registra extravio (Art.30 c)
    end
```

**Invariantes deste fluxo** (ver `regras-negocio.md`):
- Cautela só existe com **as duas assinaturas** (associado + diretor).
- `condition_out` é obrigatório na entrega; `condition_in` obrigatório na devolução — a comparação alimenta a inspeção.
- Bem não pode ser cautelado se `status != reservado/disponível`.
- Prazo vencido (`due_at < now` e `status=ativa`) → cautela vira `atrasada` (job Celery) e notifica.

## 3. Inventário periódico (Art.30 b)

```mermaid
flowchart TD
    A[Diretor abre Inventário<br/>escopo: local/categoria] --> B[Gera lista esperada<br/>de bens no escopo]
    B --> C[Inventariante escaneia<br/>etiquetas QR em campo]
    C --> D{Bem bate com<br/>local esperado?}
    D -->|sim| E[Item conferido ✓]
    D -->|não / não achado| F[Registra Divergência]
    F --> G{Tipo}
    G -->|local divergente| H[Atualiza location após aprovação]
    G -->|não encontrado| I[Marca p/ apuração / possível extravio]
    G -->|não cadastrado| J[Sugere cadastro do bem]
    E --> K[Fechar inventário]
    H --> K
    I --> K
    K --> L[Relatório de conformidade<br/>+ AuditLog]
```

## 4. Aquisição e catalogação (Art.30 a)

```mermaid
flowchart LR
    A[Compra ou Doação] --> B[Registra Acquisition<br/>NF/termo, valor]
    B --> C[Cria Asset<br/>categoria, local, estado]
    C --> D[Gera asset_tag<br/>PAT-ano-seq]
    D --> E[Emite Etiqueta QR]
    E --> F[Fixa etiqueta no bem<br/>printed_at]
    F --> G[Bem: disponível]
```

## Notas de implementação
- Diagramas Mermaid renderizam no GitHub e em artifacts. Mantenha-os atualizados junto com o código.
- Cada fluxo acima tem casos de uso detalhados no `modulos/<nome>.md` correspondente.
