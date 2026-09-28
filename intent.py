"""Small local learned router and a keyword baseline, sharing one safety policy."""

import re
import unicodedata

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from intent_data import TRAIN


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(c))


def build_model(ngrams=(2, 5), regularization=2):
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=ngrams, strip_accents="unicode", sublinear_tf=True),
        LogisticRegression(max_iter=1000, class_weight="balanced", C=regularization, random_state=42),
    )


def make_model():
    texts, labels = [], []
    for label, languages in TRAIN.items():
        for examples in languages.values():
            texts.extend(examples)
            labels.extend([label] * len(examples))
    model = build_model()
    return model.fit(texts, labels)


def learned(text, model):
    return learned_with_score(text, model)[0]


def learned_with_score(text: str, model: object) -> tuple[str, float]:
    """Expose the actual top class probability from one local inference.

    This is a classifier score, not calibrated confidence or permission.
    """
    scores = model.predict_proba([text])[0]
    ranking = sorted(zip(model.classes_, scores), key=lambda pair: pair[1], reverse=True)
    top, second = ranking[:2]
    # Local development policy; uncertainty is explicitly routed for clarification.
    if top[1] < 0.34 or top[1] - second[1] < 0.055:
        return "unclear", float(top[1])
    return str(top[0]), float(top[1])


def baseline(text, model=None):
    t = fold(text)
    if re.search(r"(no reconozco|nao reconheco|no autoric|nao autoriz|no hice|nao fiz|desconoz|desconhec|cobro indebido|cobranca indevida|fraud|disput|contestar)", t):
        return "new_dispute"
    if re.search(r"\b(asesor|agente|persona|humano|atendente|funcionario|representante|operador|especialista)\b", t):
        return "human"
    if re.search(r"(estado|status|reclam|reclamo|queja|protocolo|seguim|andamento|caso|atualiz|actualiz|resolv|respost|respuesta)", t):
        return "status"
    return "other"
