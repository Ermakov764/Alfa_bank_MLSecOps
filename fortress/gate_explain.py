"""Человекочитаемые объяснения падений гейтов + фрагмент лога."""

from __future__ import annotations

import json
from typing import Any

# gate → (заголовок, что означает, что делать)
_GATE_HELP: dict[str, tuple[str, str, str]] = {
    "DATA": (
        "Проверка датасета",
        "Данные содержат признаки отравления, PII или неверную схему колонок.",
        "Используйте чистый датасет (например train_clean.csv), уберите poison-колонки.",
    ),
    "G0": (
        "Секреты в коде",
        "В репозитории найдены паттерны API-ключей или токенов.",
        "Удалите секреты, используйте .env / vault, перезапустите pipeline.",
    ),
    "G1": (
        "Небезопасный код",
        "Обнаружен опасный паттерн (например pickle.loads в сервисах).",
        "Замените pickle на безопасную сериализацию (ONNX, JSON).",
    ),
    "G3": (
        "CVE в зависимостях",
        "pip-audit нашёл уязвимые версии пакетов в requirements.",
        "Обновите зависимости до версий из отчёта pip-audit.",
    ),
    "G3b": (
        "Typosquat пакетов",
        "В requirements подозрительное имя пакета (подделка PyPI).",
        "Проверьте requirements.txt на опечатки в именах пакетов.",
    ),
    "G5": (
        "Скан модели",
        "Файл модели содержит опасный pickle или не прошёл modelaudit.",
        "Экспортируйте в ONNX/joblib из доверенного train-скрипта.",
    ),
    "G6": (
        "Формат артефактов",
        "В каталоге артефактов запрещённый формат (сырой .pkl).",
        "Оставьте только ONNX + manifest / разрешённые форматы.",
    ),
    "G7": (
        "Manifest ONNX",
        "Нет подписанного SHA256 manifest для ONNX.",
        "Запустите gate G7 / pipeline — manifest создаётся автоматически.",
    ),
    "G8": (
        "Валидация модели",
        "Метрики на holdout не прошли порог качества.",
        "Переобучите модель, проверьте данные и гиперпараметры.",
    ),
    "G9": (
        "Adversarial robustness",
        "Модель неустойчива к возмущениям входа (ART/G9).",
        "Усильте регуляризацию или adversarial training.",
    ),
    "G10": (
        "LLM red-team",
        "Jailbreak-промпт не заблокирован или M3 API недоступен.",
        "Поднимите litellm; проверьте G13 middleware.",
    ),
    "G11": (
        "Скан образа",
        "Trivy нашёл уязвимости в Docker-образе при deploy.",
        "Обновите base image и зависимости сервиса.",
    ),
    "G12": (
        "Политика Production",
        "Не все обязательные теги security.* в MLflow или нет attestation.",
        "Дождитесь успешного pipeline и sync в MLflow.",
    ),
}


def _excerpt(details: Any, max_len: int = 600) -> str:
    if not details:
        return ""
    if isinstance(details, str):
        return details[:max_len]
    if isinstance(details, dict):
        for key in ("message", "log", "rule", "error", "reason"):
            if details.get(key):
                return str(details[key])[:max_len]
        try:
            return json.dumps(details, ensure_ascii=False, indent=2)[:max_len]
        except Exception:
            return str(details)[:max_len]
    return str(details)[:max_len]


def explain_gate(
    gate: str,
    status: str,
    details: Any = None,
    *,
    raw_rule: str = "",
) -> dict[str, str]:
    """Возвращает title, explanation, fix, log_excerpt для UI."""
    g = (gate or "pipeline").upper()
    title, meaning, fix = _GATE_HELP.get(g, (
        f"Гейт {g}",
        "Проверка безопасности не пройдена.",
        "См. лог pipeline и Findings.",
    ))
    if status == "passed":
        return {
            "title": title,
            "explanation": "Проверка пройдена успешно.",
            "fix": "",
            "log_excerpt": "",
            "status_human": "OK",
        }
    rule = raw_rule or _excerpt(details)
    return {
        "title": title,
        "explanation": meaning,
        "fix": fix,
        "log_excerpt": rule,
        "status_human": "ОШИБКА",
    }
