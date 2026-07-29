# Módulo: Manutenção ⛔

## Objetivo
Garantir o correto acondicionamento, conservação e proteção dos bens (preventiva, corretiva e proteção elétrica/física).

## Base legal
**Art. 30, c)** — acondicionamento de bens e proteção (segurança / proteção elétrica quando for o caso).

## Entidades
`Maintenance`, `Asset`, `Attachment`. Campo `Asset.protection_notes`. Ver `dominio/entidades.md`.

## Casos de uso (a detalhar)
- [ ] UC-M1 Abrir ordem (preventiva/corretiva/proteção); origem: agendada ou inspeção com dano.
- [ ] UC-M2 Registrar custo, fornecedor, conclusão → bem volta a `disponível`.
- [ ] UC-M3 Plano de manutenção preventiva recorrente (Celery Beat).

## Regras
- [ ] Bem em `manutenção` não pode ser reservado/cautelado.
- [ ] Inspeção com dano (Art.30 d) abre ordem automaticamente.

## Endpoints (a definir)
`POST /api/maintenances` · `PATCH /api/maintenances/{id}` · `POST /api/maintenances/{id}/close`.

## Permissões
Abrir/fechar: Admin, Diretor.
