"""D2-T1: baseline. A decision tree with two questions over one index per month, fitted only on training pixels.
Any later model has to beat it."""

import re

import numpy as np
from sklearn.tree import DecisionTreeClassifier


def columns(feature_columns: list[str], settings: dict) -> list[str]:
    monthly = re.compile(rf"^{re.escape(settings['index'])}_m\d{{2}}$")
    return [name for name in feature_columns if monthly.match(name)]


def make(settings: dict, seed: int) -> DecisionTreeClassifier:
    return DecisionTreeClassifier(max_depth=settings["max_depth"], random_state=seed)


def describe(model: DecisionTreeClassifier, used_columns: list[str], month_keys: list[str], decimals: int) -> dict:
    """The fitted tree as nested questions: '<index> of <month> <= threshold', with where pixels without data go."""
    tree = model.tree_
    classes = list(model.classes_)

    def node(number: int) -> dict:
        counts = tree.value[number][0] * tree.n_node_samples[number] / tree.value[number][0].sum()
        if tree.children_left[number] == -1:
            return {
                "leaf": True,
                "class": classes[int(np.argmax(counts))],
                "pixels": int(tree.n_node_samples[number]),
                "counts": {name: int(round(count)) for name, count in zip(classes, counts)},
            }
        column = used_columns[tree.feature[number]]
        position = int(column.rsplit("_m", 1)[1]) - 1
        return {
            "leaf": False,
            "column": column,
            "index": column.rsplit("_m", 1)[0].upper(),
            "month": month_keys[position],
            "threshold": round(float(tree.threshold[number]), decimals),
            "missing_goes": "yes" if tree.missing_go_to_left[number] else "no",
            "yes": node(tree.children_left[number]),
            "no": node(tree.children_right[number]),
        }

    return node(0)
