"""Synthetic untrained weights test local CPU execution, NOT translation quality."""
import pytest


def test_local_cpu_inference_without_network(tmp_path,monkeypatch):
    import socket
    def deny(*args,**kwargs): raise AssertionError('Network forbidden in local model test')
    monkeypatch.setattr(socket.socket,'connect',deny)
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast,T5Config,T5ForConditionalGeneration
    from app.translation import TransformersEngine
    vocabulary={'<pad>':0,'</s>':1,'<unk>':2,'Hello':3,'world':4,'Bonjour':5}
    token=Tokenizer(WordLevel(vocabulary,unk_token='<unk>'));token.pre_tokenizer=Whitespace()
    tokenizer=PreTrainedTokenizerFast(tokenizer_object=token,unk_token='<unk>',pad_token='<pad>',eos_token='</s>')
    tokenizer.save_pretrained(tmp_path)
    model=T5ForConditionalGeneration(T5Config(vocab_size=6,d_model=16,d_ff=32,num_layers=1,num_decoder_layers=1,num_heads=2,decoder_start_token_id=0,pad_token_id=0,eos_token_id=1))
    model.save_pretrained(tmp_path,safe_serialization=True)
    engine=TransformersEngine()
    manifest={'path':str(tmp_path),'id':'synthetic-test','revision':'a'*40,'family':'opus','device':'cpu'}
    engine.load(manifest)
    assert engine.health()['loaded']
    assert isinstance(engine.translate('Hello world'),str)
    engine.unload();assert not engine.health()['loaded']


def test_runtime_switch_rolls_back_on_failure(monkeypatch):
    from app.translation import Runtime
    runtime=Runtime();old={'id':'old','revision':'a'*40};new={'id':'new','revision':'b'*40}
    class Engine:
        manifest=old
        def unload(self):self.manifest=None
        def load(self,m):
            if m['id']=='new':raise ValueError('Unavailable')
            self.manifest=m
        def translate_batch(self,texts):return texts
    runtime.engine=Engine()
    with pytest.raises(ValueError):runtime.translate(new,['x'])
    assert runtime.engine.manifest==old
