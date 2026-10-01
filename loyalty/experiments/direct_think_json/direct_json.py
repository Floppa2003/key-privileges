"""Direct visual+text -> JSON probe with Qwen thinking enabled.

One model call per frozen document. No intermediate description, no Jev, no repair.
Experimental only; never publishes.
"""
from __future__ import annotations
import argparse, copy, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / p) for p in ("local_visual", "resolution", "prompt_ab", "simple_thinking")]
import run_cpu as common
import prompt_ab as frozen_io
from probe import infer

SYSTEM = """Извлеки из приложенных страниц условия предложения программы из TARGET у указанного партнёра. Верни только JSON по SCHEMA, по-русски. Используй только изображения и полный текст; условия соседних программ, общие льготы и фон страницы не включай. Не добавляй отсутствующие факты.

Поля:
- value/unit — величина и единица выгоды; неизвестная величина = null.
- basis — к чему применяется скидка или за что начисляются баллы; не полное предложение и не инструкция.
- audience — кто имеет право на предложение с учётом TARGET.
- restrictions — область действия, лимиты, исключения, несовместимость и другие условия, но не действия пользователя.
- redemption — только действия пользователя, прямо указанные для получения выгоды: оформить, предъявить, указать номер, применить код.
- promo_code — только буквальный промокод, не номер участника.
- valid_until — только опубликованный конец действия акции, не дата TARGET/публикации/бронирования.
- accrual_timing — когда поступят баллы/другая начисляемая выгода.
- evidence — короткие дословные цитаты только из блока целевой программы, подтверждающие выгоду и существенные условия.
- practical_advice — только отдельный необязательный разумный вывод, которого нет в источнике; не дублируй redemption. Если такого совета нет, [].
- unknowns — существенные неизвестные параметры целевого предложения.

Сохрани все существенные перечисления и ограничения. Один факт помещай по смыслу в правильное поле; не заменяй опубликованное действие советом и не выдавай назначение выгоды за действие пользователя."""


def build_request(frozen: dict, target: dict, text: str, schema: dict) -> dict:
    request = copy.deepcopy(frozen)
    request["think"] = True
    request["format"] = copy.deepcopy(schema)
    request["options"]["num_predict"] = 8192
    images = request["messages"][-1]["images"]
    request["messages"] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content":
            "TARGET: " + json.dumps(target, ensure_ascii=False)
            + "\nSCHEMA: " + json.dumps(schema, ensure_ascii=False)
            + "\nВсе изображения идут по порядку страниц. Полный текст:\n" + text,
         "images": images},
    ]
    return request


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--case", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ollama", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error("output_exists")

    plan = json.loads((HERE.parent / "simple_thinking" / "plan.json").read_text())
    specs = {c["id"]: c for c in plan["cases"]}
    if a.case not in specs:
        p.error("unknown_case")
    spec = specs[a.case]

    frozen = frozen_io.load_request(a.source, spec)
    target = json.loads(frozen["messages"][-1]["content"].split("\n", 1)[0])
    text = frozen_io.checked_bytes(a.source, spec["text"], spec["sha256"][spec["text"]]).decode("utf-8")
    schema = json.loads((HERE.parent / "prompt_ab" / "practical_schema.json").read_text())

    a.out.mkdir(parents=True)
    common.save(a.out / "frozen-input.json", spec)
    (a.out / "visible-text.txt").write_text(text, encoding="utf-8")
    for i, name in enumerate(spec["images"], 1):
        (a.out / f"page-{i}.png").write_bytes(
            frozen_io.checked_bytes(a.source, name, spec["sha256"][name])
        )

    request = build_request(frozen, target, text, schema)
    result = infer(request, a.ollama.resolve(), a.out / "direct", max_seconds=1800)
    result.update(case=a.case, stage="direct_json_think_true", publication_allowed=False)
    common.save(a.out / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("status") == "completed" and result.get("schema_valid") else 2


if __name__ == "__main__":
    raise SystemExit(main())
