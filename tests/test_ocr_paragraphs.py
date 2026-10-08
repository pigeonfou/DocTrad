from app.ocr import paragraphs


def line(text, box, group=(1, 1), part=0):
    return dict(text=text, box=box, confidence=.95, page=1, ocr_group=list(group), cell_part=part)


def test_paragraph_keeps_original_ink_boxes():
    source = [line('Reliable communications with', [10,10,250,30]), line('steady throughput across multiple hops.', [10,35,280,55])]
    grouped = paragraphs(source)
    assert len(grouped) == 1
    assert grouped[0]['text'] == 'Reliable communications with steady throughput across multiple hops.'
    assert grouped[0]['box'] == [10,10,280,55]
    assert [item['box'] for item in grouped[0]['lines']] == [item['box'] for item in source]
    assert 'lines' not in source[0]


def test_columns_headings_bullets_and_paragraphs_remain_separate():
    cases = [
        [line('Left', [10,10,100,30]), line('Right', [200,35,300,55])],
        [line('Title', [10,10,100,40]), line('Small text', [10,45,200,55])],
        [line('• First item', [10,10,200,30]), line('• Second item', [10,35,200,55])],
        [line('First paragraph', [10,10,200,30]), line('Second paragraph', [10,35,200,55],group=(1,2))],
        [line('Left cell', [10,10,200,30]), line('Other cell', [10,35,200,55],part=1)],
    ]
    for source in cases:
        assert len(paragraphs(source)) == 2
