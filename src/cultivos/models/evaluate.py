"""D2: train and measure a model with spatial block cross-validation (05-evaluacion.md).

Run: docker compose run --rm api python -m cultivos.models.evaluate [model]
"""

import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from cultivos.config import load_processing_config, load_training_config
from cultivos.models import baseline, blocks, importance, random_forest
from cultivos.training import dataset

MODELS = {"baseline": baseline, "random_forest": random_forest}
ID_FIELDS = ["pixel_id", "class", "lon", "lat"]
FEATURES_COMMAND = "docker compose run --rm api python -m cultivos.training.features"


class ModelError(RuntimeError):
    """Missing variables or unknown model."""


def models_folder(config: dict):
    return dataset.folder(config) / "models"


def load_features(config: dict) -> dict:
    root = dataset.folder(config)
    path, report_path = root / "features.csv", root / "features.json"
    if not path.exists() or not report_path.exists():
        raise ModelError(f"Faltan las variables del modelo. Ejecutá: {FEATURES_COMMAND}")
    rows = dataset.read_rows(path)
    names = [name for name in rows[0] if name not in ID_FIELDS]
    values = np.array([[float(row[name]) if row[name] != "" else np.nan for name in names] for row in rows])
    return {
        "pixel_ids": [row["pixel_id"] for row in rows],
        "classes": np.array([row["class"] for row in rows]),
        "lon": np.array([float(row["lon"]) for row in rows]),
        "lat": np.array([float(row["lat"]) for row in rows]),
        "columns": names,
        "values": values,
        "month_keys": dataset.read_json(report_path)["month_keys"],
    }


def scores(truth: np.ndarray, predicted: np.ndarray, classes: list[str], decimals: int) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(truth, predicted, labels=classes, zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(truth, predicted)), decimals),
        "macro_f1": round(float(np.mean(f1)), decimals),
        "per_class": {
            name: {
                "precision": round(float(precision[n]), decimals),
                "recall": round(float(recall[n]), decimals),
                "f1": round(float(f1[n]), decimals),
                "pixels": int(support[n]),
            }
            for n, name in enumerate(classes)
        },
        "confusion": {"labels": classes, "matrix": confusion_matrix(truth, predicted, labels=classes).tolist()},
    }


def cross_validate(values: np.ndarray, truth: np.ndarray, split: dict, make_model, classes: list[str], decimals: int, measure_importance=None) -> dict:
    """Out-of-fold prediction of every pixel; the model of each round sees only its training pixels.
    If given, measure_importance(model, test values, test truth) runs on each round's test pixels and is averaged."""
    predicted = np.empty(len(truth), dtype=object)
    rounds, importances = [], []
    for number, current in enumerate(split["rounds"]):
        model = make_model()
        model.fit(values[current["train"]], truth[current["train"]])
        predicted[current["test"]] = model.predict(values[current["test"]])
        if measure_importance:
            importances.append(measure_importance(model, values[current["test"]], truth[current["test"]]))
        test_blocks = {block for block, is_test in zip(split["blocks"], current["test"]) if is_test}
        round_scores = scores(truth[current["test"]], predicted[current["test"]], classes, decimals)
        rounds.append({
            "round": number + 1,
            "blocks": len(test_blocks),
            "test": int(current["test"].sum()),
            "train": int(current["train"].sum()),
            "excluded": int(current["excluded"].sum()),
            "f1": {name: metrics["f1"] for name, metrics in round_scores["per_class"].items()},
        })
    mean_importance = importance.average(importances, decimals) if importances else None
    return {"predicted": predicted, "rounds": rounds, "importance": mean_importance, **scores(truth, predicted, classes, decimals)}


def kind_titles(config: dict) -> dict:
    """Readable name of each kind of variable: bands, indices and the shape of the curve."""
    indices = load_processing_config()["indices"]
    phenology_index = config["features"]["phenology_index"]
    return {
        **config["features"]["band_titles"],
        **{name.lower(): info["title"] for name, info in indices.items()},
        importance.PHENOLOGY_KIND: f"Forma de la curva ({phenology_index})",
    }


def run(name: str) -> dict:
    if name not in MODELS:
        raise ModelError(f"Modelo desconocido: {name}. Opciones: {', '.join(MODELS)}.")
    config = load_training_config()
    module, settings, evaluation = MODELS[name], config["models"][name], config["evaluation"]
    decimals = config["summary"]["decimals"]
    data = load_features(config)
    classes = list(config["labels"]["classes"])
    used = module.columns(data["columns"], settings)
    values = data["values"][:, [data["columns"].index(column) for column in used]]

    split = blocks.split(data["lon"], data["lat"], evaluation)
    make_model = lambda: module.make(settings, evaluation["seed"])
    measure = None
    if "importance" in settings:
        grouping = importance.groups(used, data["month_keys"])
        options = settings["importance"]
        measure = lambda model, test_values, test_truth: importance.group_drops(
            model, test_values, test_truth, grouping, options["scoring"], options["repeats"], evaluation["seed"]
        )
    result = cross_validate(values, data["classes"], split, make_model, classes, decimals, measure)

    final = make_model().fit(values, data["classes"])
    targets = [key for key, info in config["labels"]["classes"].items() if not info.get("rest")]
    for key in targets:
        result["per_class"][key]["meets_target"] = result["per_class"][key]["f1"] >= evaluation["target_f1"]

    folder = models_folder(config)
    dataset.write_rows(
        folder / "folds.csv",
        ["pixel_id", "block", "fold"],
        [{"pixel_id": pid, "block": block, "fold": int(fold) + 1} for pid, block, fold in zip(data["pixel_ids"], split["blocks"], split["fold"])],
    )
    dataset.write_rows(
        folder / f"{name}-predictions.csv",
        ["pixel_id", "class", "predicted"],
        [{"pixel_id": pid, "class": truth, "predicted": guess} for pid, truth, guess in zip(data["pixel_ids"], data["classes"], result["predicted"])],
    )
    report = {
        "model": name,
        "title": settings["title"],
        "description": settings["description"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "columns": len(used),
        "evaluation": {**evaluation, "crs": split["crs"], "blocks": len(set(split["blocks"])), "targets": targets},
        "accuracy": result["accuracy"],
        "macro_f1": result["macro_f1"],
        "per_class": result["per_class"],
        "confusion": result["confusion"],
        "rounds": result["rounds"],
        "rule": module.describe(final, used, data["month_keys"], decimals) if hasattr(module, "describe") else None,
        "importance": None,
    }
    if result["importance"] is not None:
        report["importance"] = {
            "scoring": settings["importance"]["scoring"],
            "kind_titles": kind_titles(config),
            **result["importance"],
        }
    dataset.write_json(folder / f"{name}.json", report)
    return report


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    try:
        report = run(name)
    except ModelError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    evaluation = report["evaluation"]
    print(f"{report['title']}: {report['columns']} variables.")
    print(
        f"Validación por bloques: {evaluation['blocks']} bloques de {evaluation['block_size_m']} m en {evaluation['folds']} rondas, "
        f"franja de {evaluation['buffer_m']} m."
    )
    for item in report["rounds"]:
        f1 = ", ".join(f"{key} {value}" for key, value in item["f1"].items())
        print(f"  Ronda {item['round']}: prueba {item['test']}, entrena {item['train']}, fuera por la franja {item['excluded']} · F1 {f1}")
    print(f"Exactitud global {report['accuracy']} · F1 promedio {report['macro_f1']}")
    for key, metrics in report["per_class"].items():
        mark = {True: " (cumple)", False: f" (no llega a {evaluation['target_f1']})"}.get(metrics.get("meets_target"), "")
        print(f"  {key}: precisión {metrics['precision']}, recall {metrics['recall']}, F1 {metrics['f1']}{mark}")
    if report["importance"]:
        titles = report["importance"]["kind_titles"]
        print("Qué pesa más (cuánto baja el F1 promedio al mezclar el grupo entero):")
        months = sorted(report["importance"]["by_month"], key=lambda item: item["value"], reverse=True)
        print("  Por mes: " + ", ".join(f"{item['month']} {item['value']}" for item in months[:4]))
        print("  Por tipo: " + ", ".join(f"{titles[item['kind']]} {item['value']}" for item in report["importance"]["by_kind"][:4]))


if __name__ == "__main__":
    main()
