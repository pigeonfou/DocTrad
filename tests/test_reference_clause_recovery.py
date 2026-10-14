import unittest
from unittest.mock import patch

from app.diagnostics import InferenceError
from app.translation import RemoteEngine


class ReferenceClauseRecoveryTests(unittest.TestCase):
    def test_recovers_complete_clauses_without_identifier_prompt(self):
        source = ('Windows®-based Communications Planning Application (CPA); '
                  'JENM and ATOM compatible WebUI for network monitoring and management')
        clauses = source.split(';')
        outputs = ['Application Windows avec JENM, ATOM et WebUI',
                   'Application de planification des communications (CPA) sous Windows®',
                   'WebUI compatible JENM et ATOM pour la surveillance et la gestion du réseau']
        engine = RemoteEngine()
        with patch.object(engine, '_request_translation', side_effect=outputs) as call:
            result = engine.recover_names(source, {})
        self.assertIn('(CPA)', result)
        self.assertIn(' ; WebUI', result)
        self.assertEqual(call.call_count, 3)
        self.assertEqual([args.args[0] for args in call.call_args_list],
                         [source, *(clause.strip() for clause in clauses)])
        self.assertTrue(all(args.kwargs == {'retry': True} for args in call.call_args_list))

    def test_failed_clause_never_returns_partial_translation(self):
        source = 'DSP processing supports PLI; TRL maturity is evaluated independently'
        engine = RemoteEngine()
        with patch.object(engine, '_request_translation',
                          side_effect=['Traitement PLI et TRL', 'Traitement PLI']) as call:
            with self.assertRaises(InferenceError):
                engine.recover_names(source, {})
        self.assertEqual(call.call_count, 2)

    def test_successful_whole_passage_needs_no_clause_recovery(self):
        source = 'DSP processing supports PLI; TRL maturity is evaluated independently'
        target = 'Le DSP prend en charge PLI ; la maturité TRL est évaluée indépendamment'
        with patch.object(RemoteEngine, '_request_translation', return_value=target) as call:
            self.assertEqual(RemoteEngine().recover_names(source, {}), target)
        self.assertEqual(call.call_count, 1)

    def test_lists_and_excessive_clauses_do_not_trigger_fragment_inference(self):
        sources = ['DSP; PLI; TRL', 'DSP processing supports PLI without segmentation',
                   '; '.join(['DSP processing supports PLI'] * 5)]
        for source in sources:
            with self.subTest(source=source):
                with patch.object(RemoteEngine, '_request_translation', return_value='Traitement') as call:
                    with self.assertRaises(InferenceError):
                        RemoteEngine().recover_names(source, {})
                self.assertEqual(call.call_count, 1)

    def test_user_glossary_applies_to_clause_validation(self):
        source = 'DSP processing supports PLI; TRL maturity is evaluated independently'
        outputs = ['Traitement sans références', 'Le DSP prend en charge position',
                   'La maturité TRL est évaluée indépendamment']
        with patch.object(RemoteEngine, '_request_translation', side_effect=outputs):
            target = RemoteEngine().recover_names(source, {'PLI': 'position'})
        self.assertIn('position', target)

    def test_remote_failure_remains_failure(self):
        source = 'DSP processing supports PLI; TRL maturity is evaluated independently'
        failure = InferenceError('http_error', {'http_status': 503})
        with patch.object(RemoteEngine, '_request_translation', side_effect=['Traitement', failure, failure, failure]), patch('time.sleep'):
            with self.assertRaises(InferenceError) as caught:
                RemoteEngine().recover_names(source, {})
        self.assertIs(caught.exception, failure)


def test_web_interface_expansion_retains_source_notation_without_inference_retry():
    source = 'JENM and ATOM compatible WebUI for network monitoring and management'
    target = 'Interface Web compatible JENM et ATOM pour la surveillance et la gestion du réseau'
    with patch.object(RemoteEngine, '_translate_prose', return_value=target), patch.object(RemoteEngine, 'recover_names') as retry:
        result = RemoteEngine().translate_contextual(source)
    assert result == 'Interface Web (WebUI) compatible JENM et ATOM pour la surveillance et la gestion du réseau'
    retry.assert_not_called()


def test_web_interface_restoration_requires_unique_source_and_target_anchors():
    from app.terminology import correct_network_terms, missing_names
    for source, target in [
        ('Network management', 'Interface Web pour la gestion'),
        ('WebUI for management', 'Gestion réseau'),
        ('WebUI for management', 'Interface Web et interface utilisateur Web'),
        ('WebUI and WebUI', 'Interface Web'),
        ('WebUI for management', 'Interface Web (WebUI) pour la gestion'),
    ]:
        assert correct_network_terms(source, target) == target
    result = correct_network_terms('WebUI for management', 'Interface utilisateur web pour la gestion')
    assert not missing_names('WebUI for management', result)


def test_user_interface_glossary_remains_authoritative():
    with patch.object(RemoteEngine, '_translate_prose', return_value='Interface Web pour la gestion'):
        result = RemoteEngine().translate_contextual('WebUI for management', {'WebUI': 'Interface Web'})
    assert result == 'Interface Web pour la gestion'
