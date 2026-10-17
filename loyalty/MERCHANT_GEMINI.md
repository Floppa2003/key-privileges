# Исторический переход на Gemini

Текущий `merchant_extract.py` переключён на Qwen3.8 27B через Kilo по решению пользователя. Актуальные команды, входной контракт и ограничения: [MERCHANT_QWEN.md](MERCHANT_QWEN.md).

Прежняя миграция, параметры и результаты 503 сохранены без переписывания в [GEMINI_MIGRATION_RESULTS_20261003.md](experiments/cloud_json/GEMINI_MIGRATION_RESULTS_20261003.md). Исходная инструкция Gemini доступна в истории этого файла на коммите `b19c73aa7cd25aaa3e84f1f96a947de752f47e85`.

`GEMINI_API_KEY` не удалён, но текущий модельный CLI его не использует. Автоматического возврата к Gemini, merge в main и публикации в Sheets нет.
