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


def test_interleaved_columns_read_each_physical_cell_before_next_column():
    left = [line('Supported Software Defined', [10,10,180,30],part=0),
            line('Radio (SDR) Platforms', [10,35,175,55],part=0)]
    right = [line('TrellisWare products:', [210,10,440,30],part=1),
             line('» TW-870 TSM Ghost Radio', [210,35,460,55],part=1)]
    for item in left: item['table_cell'] = [0,0,190,80]
    for item in right: item['table_cell'] = [200,0,480,80]
    grouped = paragraphs([left[0],right[0],left[1],right[1]])
    assert [g['text'] for g in grouped] == ['Supported Software Defined Radio (SDR) Platforms', 'TrellisWare products:', '» TW-870 TSM Ghost Radio']


def test_same_cell_can_continue_across_ocr_paragraph_ids_but_not_row_border():
    source = [line('Works as a black', [210,10,450,30],group=(1,1)),
              line('relay for the network.', [210,35,460,55],group=(2,1)),
              line('New row', [210,70,350,90],group=(2,1))]
    source[0]['table_cell'] = source[1]['table_cell'] = [200,0,480,60]
    source[2]['table_cell'] = [200,60,480,100]
    assert [g['text'] for g in paragraphs(source)] == ['Works as a black relay for the network.', 'New row']
