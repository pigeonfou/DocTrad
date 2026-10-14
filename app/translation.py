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

    def translate_contextual(self, text, glossary=None, context=None):
        """Translate complete source sentences, including their technical context.

        Exact glossary entries bypass inference. Inline replacements apply only
        to English terms the model actually retained; QA reports lost values.
        """
        import re
        from .quality import segment, split_sentences
        terms = glossary or {}
        # QR captions can be extracted as "SCAN M E" or spaced letters.
        # Match the entire caption only; do not rewrite prose or identifiers.
        if re.fullmatch(r"\s*S\s*C\s*A\s*N\s+M\s*E\s*", text, re.IGNORECASE):
            return terms.get(text.strip(), terms.get("SCAN ME", "SCANNEZ-MOI"))
        if text.strip() in terms:
            return terms[text.strip()]
        bullet = re.match(r'^([•●▪*–—»«-]\s*)(.+)$', text.strip())
        if bullet and bullet[2].strip() in terms:
            return bullet[1] + terms[bullet[2].strip()]
        from .terminology import preserved_name, reference_label, compact_image_notice
        notice = compact_image_notice(text)
        if notice is not None:
            return notice
        from .terminology import structured_technical_text
        literal = structured_technical_text(text, terms)
        if literal is not None:
            return literal
        if preserved_name(text.strip()) or reference_label(text, terms):
            return text
        if not re.search(r"[^\W\d_]", text):
            return text
        # OPUS is trained on sentences and can omit later sentences in a block.
        # Preserve paragraph layout while translating every complete sentence.
        sentences = split_sentences(text.strip())
        chunks = [chunk for sentence in sentences for chunk in segment(sentence, max_chars=1000)]
        translated = " ".join(self._translate_prose(chunk) for chunk in chunks)
        # A single pass avoids matching inside replacements or shorter names.
        present = [term for term in sorted(terms, key=len, reverse=True)
                   if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)]
        if present:
            pattern = re.compile("|".join(r"(?<!\w)" + re.escape(term) + r"(?!\w)" for term in present), re.IGNORECASE)
            replacements = {term.casefold(): terms[term] for term in present}
            translated = pattern.sub(lambda match: replacements[match.group().casefold()], translated)
        from .terminology import correct_network_terms
        translated = correct_network_terms(text, translated)
        # Keep full-sentence inference first. If it loses a protected name,
        # retry once with technical spans kept outside inference altogether.
        # Random placeholders are split by translate() and never sent upstream.
        from .terminology import required_names, missing_names
        if missing_names(text,translated,terms):
            from .quality import protect, restore
            translated = correct_network_terms(text, self.recover_names(text, terms))
        # Glossary headings at the start of a colon-separated paragraph keep
        # their preferred wording without fragmenting the model's source.
        source_heading, separator, _ = text.partition(':')
        if separator and source_heading.strip() in terms and ':' in translated:
            translated = terms[source_heading.strip()] + ' :' + translated.partition(':')[2]
        return translated

    def recover_names(self, text, terms):
        from .quality import protect, restore
        from .terminology import required_names
        protected, mapping = protect(text, required_names(text, terms))
        return restore(self.translate(protected), mapping)

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


class RemoteEngine(TransformersEngine):
    """Reuse terminology protection, with inference on an explicitly configured LAN host."""
    def translate_contextual(self, text, glossary=None, context=None):
        self.context_terms = glossary or {}
        self.document_context = context or {}
        try:
            return super().translate_contextual(text, glossary)
        finally:
            self.context_terms = {}
            self.document_context = {}

    def load(self, manifest):
        from .remote_ai import settings, manifest as configured_manifest
        self.settings = settings()
        current = configured_manifest()
        if not current or current["revision"] != manifest["revision"]:
            raise ValueError("Configuration IA distante modifiée")
        from .remote_ai import ensure_model
        ensure_model(self.settings, unload_images=False)
        self.manifest = manifest
    def unload(self):
        self.manifest = None
        self.settings = None
    def health(self):
        return {"loaded": self.manifest is not None, "model": self.manifest and self.manifest["id"], "remote": True}
    def recover_names(self, text, terms):
        # A chat model needs the complete sentence, including names and units.
        # Translating fragments independently can glue names onto French words.
        from .terminology import missing_names
        from .diagnostics import InferenceError
        from .terminology import correct_network_terms
        target = correct_network_terms(text, self._request_translation(text, retry=True))
        if missing_names(text, target, terms):
            # Recover independent clauses only after full-passage inference
            # failed twice. Never split at a name or arbitrary character limit.
            import re
            clauses = text.split(';')
            if (2 <= len(clauses) <= 4
                    and all(len(re.findall(r'[^\W\d_]+', clause)) >= 3
                            and len(clause.strip()) >= 12 for clause in clauses)):
                recovered = []
                for clause in clauses:
                    candidate = correct_network_terms(
                        clause, self._request_translation(clause.strip(), retry=True))
                    if missing_names(clause, candidate, terms):
                        break
                    recovered.append(candidate.strip())
                if len(recovered) == len(clauses):
                    target = ' ; '.join(recovered)
            if not missing_names(text, target, terms):
                return target
            raise InferenceError('missing_identifier', {'characters': len(text), 'attempt': 2})
        return target

    def _translate_prose(self, text):
        from .diagnostics import InferenceError
        try:
            return self._request_translation(text)
        except InferenceError as first:
            if ((first.diagnostic.get("code") == "http_error" and first.diagnostic.get("http_status") in (500, 502, 503, 504))
                    or (first.diagnostic.get("code") == "remote_error" and first.diagnostic.get("exception") in ("URLError", "ConnectionResetError"))):
                # Translation is read-only: retry one transient server failure with
                # the identical payload, never authentication or arbitrary failures.
                import time
                time.sleep(1)
                try:
                    return self._request_translation(text)
                except InferenceError as last:
                    last.diagnostic["attempt"] = 2
                    raise
            if first.diagnostic.get("code") not in (
                    "incomplete_response", "invalid_control_tokens", "empty_response", "foreign_script", "invented_identifier", "prompt_echo"):
                raise
            # One recovery round only; no recursion or partial-answer export.
            try:
                return self._request_translation(text, retry=True)
            except InferenceError as last:
                last.diagnostic["attempt"] = 2
                raise

    def _request_translation(self, text, retry=False):
        import json
        import urllib.request
        from pathlib import Path
        if not self.manifest:
            raise ValueError("Moteur distant absent")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        from .remote_ai import translation_payload
        payload = translation_payload(self.settings["model"], text, None if retry else getattr(self, "context_terms", None), None if retry else getattr(self, "document_context", None))
        if self.settings.get("auto_load"):
            payload["max_tokens"] = min(payload["max_tokens"], self.settings["context_length"] // 2)
        if retry and "translategemma" in self.settings["model"].lower():
            payload["repetition_penalty"] = 1.0
            payload["max_tokens"] = 512
            payload["messages"][0]["content"] = (
                "Translate the complete source faithfully; return only its translation.\n"
                + payload["messages"][0]["content"])

        key = Path(self.settings["key_file"]).read_text().strip()
        request = urllib.request.Request(self.settings["base_url"] + "/chat/completions",
            data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + key,
            "Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        diagnostic = {"characters": len(text)}
        code = "remote_error"
        try:
            with opener.open(request, timeout=180) as response:
                raw = response.read(1024*1024 + 1)
                if len(raw) > 1024*1024:
                    code = "response_too_large"
                    raise ValueError("Réponse IA trop volumineuse")
            choice = json.loads(raw)["choices"][0]
            diagnostic["finish_reason"] = choice.get("finish_reason")
            translated = choice.get("message", {}).get("content")
            if isinstance(translated, str):
                import re
                diagnostic["response_characters"] = len(translated)
                diagnostic["markers"] = re.findall(r"<\|[^>]*\|>|<(?:end_of_turn|eos)>", translated)
            if choice.get("finish_reason") != "stop":
                code = "incomplete_response"
                raise ValueError("Traduction IA incomplète")
            translated = choice["message"]["content"]
            if not isinstance(translated, str) or not translated.strip():
                code = "empty_response"
                raise ValueError("Traduction IA vide")
            import re
            diagnostic["response_characters"] = len(translated)
            diagnostic["markers"] = re.findall(r"<\|[^>]*\|>|<(?:end_of_turn|eos)>", translated)
            code = "invalid_control_tokens"
            from .remote_ai import clean_translation
            translated = clean_translation(translated)
            from .quality import strip_identifier_echo
            from .terminology import required_names
            source_names = list(required_names(text, getattr(self, "context_terms", None)).values())
            translated = strip_identifier_echo(text, translated, source_names)
            from .quality import inference_defects
            defects = inference_defects(text, translated)
            if defects:
                code = defects[0]
                raise ValueError("Réponse hors contraintes de traduction")
            return translated
        except Exception as exc:
            # Never expose a key, source text or server response through error messages.
            from .diagnostics import InferenceError
            diagnostic["exception"] = type(exc).__name__
            if hasattr(exc, "code"):
                diagnostic["http_status"] = exc.code
                code = "http_error"
            elif isinstance(exc, TimeoutError):
                code = "timeout"
            raise InferenceError(code, diagnostic) from exc


class Runtime:
    """A single process owns weights; all switches and inference are serialized."""
    def __init__(self): self.engine = TransformersEngine(); self.lock = RLock()
    def translate(self, manifest, texts, *, contextual=False, glossary=None, contexts=None):
        if contexts and len(contexts) != len(texts): raise ValueError("Contextes incohérents")
        with self.lock:
            old = self.engine.manifest
            if not old or (old["id"], old["revision"]) != (manifest["id"], manifest["revision"]):
                previous = self.engine
                previous.unload()
                if manifest.get("family") == "remote":
                    self.engine = RemoteEngine()
                elif isinstance(previous, RemoteEngine):
                    self.engine = TransformersEngine()
                try: self.engine.load(manifest)
                except Exception:
                    self.engine.unload()
                    self.engine = previous
                    if old: self.engine.load(old)
                    raise
            if contextual:
                if isinstance(self.engine, RemoteEngine):
                    return [self.engine.translate_contextual(text, glossary, context=contexts[i] if contexts else None)
                            for i, text in enumerate(texts)]
                return [self.engine.translate_contextual(text, glossary) for text in texts]
            return self.engine.translate_batch(texts)


