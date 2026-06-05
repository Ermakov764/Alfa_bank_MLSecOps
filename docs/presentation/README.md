# Презентация FORTRESS

Диаграммы **рендерятся из Mermaid** — источник правды: `docs/architecture.md`, `docs/architecture_full.md`.

## Готовый файл

`FORTRESS_защита.pptx`

## Пересборка

```bash
python3 -m venv .venv-pres
.venv-pres/bin/pip install python-pptx
.venv-pres/bin/python3 docs/presentation/build_presentation.py
```

Требуется Node/npx для `@mermaid-js/mermaid-cli` (ставится автоматически).

## Карта диаграмм

| PNG | Источник в документации | Слайд презентации |
|-----|-------------------------|-------------------|
| `01_trust_zones` | architecture.md §3 | Где угрозы / зоны DEV→PROD |
| `02_compose_architecture` | architecture.md §2 | Архитектура Docker Compose |
| `03_security_gates_layers` | architecture.md §7 | Security Gates G0–G14 |
| `04_sequence_flow` | architecture.md §5 | Сквозной поток |
| `05_cicd_pipeline` | architecture_full.md §10 | CI/CD GitHub Actions |
| `06_model_lifecycle` | architecture.md §4 | Жизненный цикл модели |
| `07_demo_scenarios` | architecture_full.md §14 | Демо A–E |
| `08_visibility_er` | architecture.md §6 | Видимость активов (ER) |
| `09_threats_mapping` | architecture_full.md §4 | Угрозы T1–T10 → gates |
| `10_rbac` | architecture.md §8 | RBAC / роли |
| `11_analogs_market` | продуктовый слайд | Аналоги |

Исходники Mermaid: `mermaid/*.mmd` — при изменении архитектуры правьте **сначала docs**, затем синхронизируйте `.mmd`.

## Импорт в Google Slides

Файл → Импорт слайды → `FORTRESS_защита.pptx`
