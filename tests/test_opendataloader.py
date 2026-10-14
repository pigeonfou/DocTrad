import unittest
from pathlib import Path
from pypdf import PdfWriter
from app.opendataloader import normalize, pixel_box, analyze_pdf
from app.document_context import translation_context


class OpenDataLoaderTests(unittest.TestCase):
    def page(self):
        return PdfWriter().add_blank_page(width=600,height=800)

    def test_coordinates_and_rotation(self):
        page=self.page()
        self.assertEqual(pixel_box([60,640,180,720],page,[1500,2000]),[150,200,450,400])
        page.rotate(90)
        self.assertEqual(pixel_box([60,640,180,720],page,[2000,1500]),[1600,150,1800,450])
        with self.assertRaises(ValueError):pixel_box([0,0,float('nan'),4],page,[2000,1500])

    def test_structural_heading_and_table_context(self):
        def node(kind,text,box):return {'type':kind,'content':text,'page number':1,'bounding box':box,'font size':10}
        heading=node('heading','ENVIRONMENT',[10,740,250,760])
        label=node('paragraph','Immersion',[10,680,100,700])
        value=node('paragraph','2-meter salt water',[120,680,300,700])
        cell=lambda child:{'type':'table cell','page number':1,'bounding box':child['bounding box'],'kids':[child]}
        table={'type':'table','page number':1,'rows':[{'cells':[cell(label),cell(value)]}]}
        items,bad=normalize({'kids':[heading,table]},[self.page()],[[1500,2000]])
        self.assertFalse(bad)
        self.assertEqual(translation_context(items,2),{'role':'table_cell','section':'ENVIRONMENT','row':'Immersion'})

    def test_merged_table_is_flagged_for_geometric_recovery(self):
        paragraph={'type':'paragraph','page number':1,'bounding box':[10,10,100,200],'content':'\n'.join(['line']*8)}
        table={'type':'table','page number':1,'rows':[{'cells':[{'type':'table cell','page number':1,'bounding box':[10,10,100,200],'kids':[paragraph]}]}]}
        _,bad=normalize({'kids':[table]},[self.page()],[[1500,2000]])
        self.assertEqual(bad,{1})

    def test_actual_local_parser_on_native_pdf(self):
        import tempfile
        from reportlab.pdfgen import canvas
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'native.pdf'
            document=canvas.Canvas(str(source));document.drawString(50,700,'Temperature measurement and technical documentation.');document.save()
            items=analyze_pdf(source)
        self.assertTrue(any(x['analysis_backend']=='opendataloader' for x in items))
        self.assertIn('Temperature measurement', ' '.join(x['text'] for x in items))

    def test_real_public_pdf_has_coordinate_aware_fallback(self):
        fixture=Path(__file__).parent/'fixtures/tsm-waveform-reference.pdf'
        items=analyze_pdf(fixture)
        self.assertTrue(items)
        self.assertTrue(all('box' in x and 'page' in x and 'image_size' in x for x in items))
