import unittest
from unittest.mock import patch
from app.document_context import translation_context
from app.remote_ai import translation_payload
from app.translation import RemoteEngine


def item(text, box, cell=None, page=1, **extra):
    return dict(text=text, box=box, page=page, **({'table_cell':cell} if cell else {}), **extra)


class DocumentContextTests(unittest.TestCase):
    def test_table_context_pairs_only_touching_cells_of_same_row_and_page(self):
        items = [item('ENVIRONMENT', [0,0,190,15], source_bold=True),
                 item('Immersion', [0,25,90,35], [0,20,100,40]),
                 item('2-meter salt water (MIL-STD-810G)', [110,25,190,35], [100,20,200,40]),
                 item('Unrelated antenna', [400,25,490,35], [400,20,500,40]),
                 item('Other page', [0,25,90,35], [0,20,100,40], page=2)]
        context = translation_context(items,2)
        self.assertEqual(context['row'],'Immersion')
        self.assertEqual(context['section'],'ENVIRONMENT')
        self.assertNotIn('Unrelated',str(context))
        self.assertNotIn('Other page',str(context))

    def test_columns_are_not_mixed_and_context_is_bounded(self):
        items = [item('Previous '*100, [0,0,100,20]),
                 item('Wrong column', [200,25,300,45]),
                 item('Current', [0,50,100,70]),
                 item('Next', [0,80,100,100])]
        context=translation_context(items,2)
        self.assertEqual(len(context['preceding']),300)
        self.assertEqual(context['following'],'Next')
        self.assertNotIn('Wrong column',str(context))

    def test_spanning_table_header_is_section_but_uppercase_value_is_not(self):
        items=[item('ENVIRONMENTAL',[0,0,90,15],[0,0,200,20]),
               item('MIL-STD-810G',[110,25,190,35],[100,20,200,40]),
               item('Depth',[0,45,90,55],[0,40,100,60]),
               item('2 m',[110,45,190,55],[100,40,200,60])]
        context=translation_context(items,3)
        self.assertEqual(context['section'],'ENVIRONMENTAL')
        self.assertEqual(context['row'],'Depth')

    def test_text_documents_have_adjacent_passages(self):
        context=translation_context([{'text':'First'},{'text':'Second'},{'text':'Third'}],1)
        self.assertEqual(context['preceding'],'First')
        self.assertEqual(context['following'],'Third')

    def test_prompts_have_context_but_no_fixed_identifier_protection_lists(self):
        for model in ('translategemma','other-model'):
            prompt=translation_payload(model,'2-meter salt water',context={'row':'Immersion','secret':'ignored'})['messages'][0]['content']
            self.assertIn('Immersion',prompt)
            self.assertTrue(prompt.endswith('2-meter salt water'))
            for phrase in ('Preserve these source identifiers','National Security Agency','WREN Security','SOCOM','ignored'):
                self.assertNotIn(phrase,prompt)

    def test_context_is_reset_even_if_inference_fails(self):
        engine=RemoteEngine()
        with patch.object(engine,'_translate_prose',side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):
                engine.translate_contextual('A passage',context={'section':'PRIVATE'})
        self.assertEqual(engine.document_context,{})
        self.assertEqual(engine.context_terms,{})

    def test_remote_inference_receives_context_without_changing_source(self):
        engine=RemoteEngine()
        def inference(text):
            self.assertEqual(text,'A passage')
            self.assertEqual(engine.document_context,{'section':'Context'})
            return 'Un passage'
        with patch.object(engine,'_translate_prose',side_effect=inference):
            self.assertEqual(engine.translate_contextual('A passage',context={'section':'Context'}),'Un passage')
