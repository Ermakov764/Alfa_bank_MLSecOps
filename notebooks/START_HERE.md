# Data Scientist — старт

## Сервисы

| Сервис | URL |
|--------|-----|
| FORTRESS | http://localhost:8502 |
| MLflow | http://localhost:5000 |
| Jupyter (Docker) | http://localhost:8888 · пароль `fortress` |

Один логин Keycloak для FORTRESS и MLflow.

## Загрузить файлы с **вашего компьютера** в MLflow

### Вариант A — терминал (любой путь на диске)

```powershell
$env:MLFLOW_TRACKING_URI = "http://localhost:5000"

# один файл
python scripts/ds_log_to_mlflow.py --file "C:\Users\YOU\Documents\my_data.csv"

# целая папка
python scripts/ds_log_to_mlflow.py --dir "D:\projects\fraud\data" --experiment my-fraud --run-name v3

# несколько файлов
python scripts/ds_log_to_mlflow.py --file .\model.onnx --file .\metrics.json --run-name trial-7
```

Файлы появятся в MLflow → эксперимент `ds-experiments` (или `--experiment ваше_имя`).

### Вариант B — FORTRESS UI

Вкладка **Данные** → «В MLflow» → выберите файлы с компьютера.

### Вариант C — свой Jupyter на ПК

```python
import os
os.environ["MLFLOW_TRACKING_URI"] = "http://localhost:5000"
from pathlib import Path
from fortress.ds_mlflow_upload import log_local_files

run_id, _ = log_local_files(
    [Path(r"C:\Users\YOU\any\folder\data.csv")],
    experiment="my-exp",
    run_name="notebook-run-1",
    owner="ваш_логин",
)
print(run_id)
```

### Вариант D — Jupyter в Docker + ваши папки

В `.env` укажите путь к данным на хосте:

```
DS_DATA_HOST_PATH=C:\Users\YOU\Documents
```

После `docker compose up -d jupyter` папка доступна в контейнере как `/home/jovyan/host-data/`.

---

## DATA gate (только если нужен pipeline FORTRESS)

Отдельно от обычных эксперimentов MLflow. Проверяет poison / PII / схему колонок (если указали).

```powershell
python scripts/ds_upload_dataset.py upload "C:\path\to\data.csv" --name prod_train --actor ваш_логин
# опционально: --expected-cols col1,col2,target
```

Или FORTRESS → **Данные** → вкладка «Регистрация для pipeline».
