from __future__ import annotations

from scorer.metrics import heuristic_perplexity


class PerplexityScorer:
    """Optional transformer-backed scorer with a deterministic fallback.

    The fallback keeps the CLI usable in fresh local environments. When
    transformers and torch are installed, pass a Chinese causal language model
    name such as ``uer/gpt2-chinese-cluecorpussmall``.
    """

    def __init__(self, model_name: str | None = None, revision: str = "main"):
        self.model_name = model_name
        self.revision = revision
        self._tokenizer = None
        self._model = None
        if model_name:
            self._load_transformer(model_name)

    def _load_transformer(self, model_name: str) -> None:
        try:
            import torch  # type: ignore
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception:
            return
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_name, revision=self.revision)
        self._model = AutoModelForCausalLM.from_pretrained(model_name, revision=self.revision)
        self._model.eval()

    def score(self, text: str) -> float:
        if self._tokenizer is None or self._model is None:
            return heuristic_perplexity(text)
        encodings = self._tokenizer(text, return_tensors="pt")
        with self._torch.no_grad():
            loss = self._model(**encodings, labels=encodings["input_ids"]).loss
        return float(self._torch.exp(loss).item())

    def improvement(self, original: str, rewritten: str) -> float:
        original_score = self.score(original)
        if original_score == 0:
            return 0.0
        return (self.score(rewritten) - original_score) / original_score
