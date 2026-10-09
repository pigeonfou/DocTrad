from abc import ABC, abstractmethod
from threading import RLock

class TranslationEngine(ABC):
    @abstractmethod
    def load(self, manifest): ...
    @abstractmethod
    def unload(self): ...
    @abstractmethod
    def translate(self, text): ...
    def translate_batch(self, texts): return [self.translate(t) for t in texts]
    @abstractmethod
    def health(self): ...
    def capabilities(self): return {"source": "en", "target": "fr", "cpu": True, "gpu": True}

class TransformersEngine(TranslationEngine):
    def __init__(self): self.model = self.tokenizer = self.manifest = None
    def load(self, manifest):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        device = manifest.get("device", "cpu")
        if device == "cuda" and not torch.cuda.is_available(): raise ValueError("GPU CUDA indisponible")
        torch.set_num_threads(max(1, min(4, ( __import__('os').cpu_count() or 2) - 1)))
        tokenizer = AutoTokenizer.from_pretrained(manifest["path"], local_files_only=True, trust_remote_code=False)
        model = AutoModelForSeq2SeqLM.from_pretrained(manifest["path"], local_files_only=True, trust_remote_code=False, use_safetensors=True)
        model = model.to(device).eval()
        self.model, self.tokenizer, self.manifest = model, tokenizer, manifest
    def unload(self):
        self.model = self.tokenizer = self.manifest = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available(): torch.cuda.empty_cache()
        except ImportError: pass
    def health(self): return {"loaded": self.model is not None, "model": self.manifest and self.manifest["id"]}
    def translate(self, text):
        import re
        # Keep protected technical values and glossary replacements out of the model.
        marker = r"(ZXQ[0-9a-f]{8}Q[0-9]+QXZ)"
        parts = re.split(marker, text)
        if len(parts) == 1:
            return self._translate_prose(text)
        output = []
        for index, part in enumerate(parts):
            if index % 2 or not re.search(r"[^\W\d_]", part):
                output.append(part)
                continue
            leading = part[:len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()):]
            output.append(leading + self._translate_prose(part.strip()).strip() + trailing)
        return "".join(output)

    def translate_contextual(self, text, glossary=None):
        """Translate complete source sentences, including their technical context.

        Exact glossary entries bypass inference. Inline replacements apply only
        to English terms the model actually retained; QA reports lost values.
        """
        import re
        from .quality import segment
        terms = glossary or {}
        if text.strip() in terms:
            return terms[text.strip()]
        bullet = re.match(r'^([•●▪*–—»«-]\s*)(.+)$', text.strip())
        if bullet and bullet[2].strip() in terms:
            return bullet[1] + terms[bullet[2].strip()]
        from .terminology import preserved_name, reference_label
        if preserved_name(text.strip()) or reference_label(text, terms):
            return text
        if not re.search(r"[^\W\d_]", text):
            return text
        # OPUS is trained on sentences and can omit later sentences in a block.
        # Preserve paragraph layout while translating every complete sentence.
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())
        chunks = [chunk for sentence in sentences for chunk in segment(sentence, max_chars=1000)]
        translated = " ".join(self._translate_prose(chunk) for chunk in chunks)
        # A single pass avoids matching inside replacements or shorter names.
        present = [term for term in sorted(terms, key=len, reverse=True)
                   if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)]
        if present:
            pattern = re.compile("|".join(r"(?<!\w)" + re.escape(term) + r"(?!\w)" for term in present))
            translated = pattern.sub(lambda match: terms[match.group()], translated)
        from .terminology import correct_network_terms
        translated = correct_network_terms(text, translated)
        # Glossary headings at the start of a colon-separated paragraph keep
        # their preferred wording without fragmenting the model's source.
        source_heading, separator, _ = text.partition(':')
        if separator and source_heading.strip() in terms and ':' in translated:
            translated = terms[source_heading.strip()] + ' :' + translated.partition(':')[2]
        return translated

    def _translate_prose(self, text):
        if self.model is None: raise ValueError("Modèle absent")
        import torch
        family = self.manifest["family"]
        if family == "m2m100": self.tokenizer.src_lang = "en"
        inputs = self.tokenizer(("<2fr> " if family == "madlad" else "") + text, return_tensors="pt", truncation=False)
        if inputs.input_ids.shape[1] > 480: raise ValueError("Segment trop long pour le modèle ; réduire sa taille")
        inputs = inputs.to(self.model.device)
        kwargs = {"forced_bos_token_id": self.tokenizer.get_lang_id("fr")} if family == "m2m100" else {}
        with torch.inference_mode(): output = self.model.generate(**inputs, max_new_tokens=512, **kwargs)
        return self.tokenizer.decode(output[0], skip_special_tokens=True)

class Runtime:
    """A single process owns weights; all switches and inference are serialized."""
    def __init__(self): self.engine = TransformersEngine(); self.lock = RLock()
    def translate(self, manifest, texts, *, contextual=False, glossary=None):
        with self.lock:
            old = self.engine.manifest
            if not old or (old["id"], old["revision"]) != (manifest["id"], manifest["revision"]):
                self.engine.unload()
                try: self.engine.load(manifest)
                except Exception:
                    self.engine.unload()
                    if old: self.engine.load(old)
                    raise
            if contextual:
                return [self.engine.translate_contextual(text, glossary) for text in texts]
            return self.engine.translate_batch(texts)

