"""D2-T2: Random Forest over every model variable (monthly bands and indices plus the shape of the season curve).
Its settings are fixed in config/training.json before seeing any test result."""

from sklearn.ensemble import RandomForestClassifier


def columns(feature_columns: list[str], settings: dict) -> list[str]:
    return list(feature_columns)


def make(settings: dict, seed: int) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=settings["trees"],
        max_depth=settings["max_depth"],
        min_samples_leaf=settings["min_samples_leaf"],
        n_jobs=-1,
        random_state=seed,
    )
