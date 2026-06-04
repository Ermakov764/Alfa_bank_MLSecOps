# Windows

Нужен только **Docker Desktop**. Python и bash на хосте не требуются.

```powershell
Copy-Item .env.example .env
.\fortress.ps1 all
```

Или: `fortress.cmd all`

| Задача | Команда |
|--------|---------|
| Поднять стек | `.\fortress.ps1 up` |
| Bootstrap | `.\fortress.ps1 bootstrap` |
| Демо | `.\fortress.ps1 demo` |
| Тесты | `.\fortress.ps1 test` |

Старые `scripts\*.ps1` перенаправляют на `fortress.ps1`.

Порт Streamlit по умолчанию **8502** (`DASHBOARD_PORT` в `.env`).
