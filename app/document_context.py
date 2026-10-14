"""Bounded source-only context selected by page, column and table row."""
import re


def translation_context(items, index):
    current = items[index]
    box = current.get('box')
    page = current.get('page')
    peers = [(i, item) for i, item in enumerate(items)
             if i != index and item.get('page') == page]
    context = {'role': 'table_cell' if current.get('table_cell') else
               'list_item' if current.get('list_marker') else 'text'}
    if not box:
        for key, offset in (('preceding', -1), ('following', 1)):
            candidate = index + offset
            if 0 <= candidate < len(items):
                context[key] = items[candidate]['text'][:300]
        return context
    def same_column(item):
        other = item.get('box')
        return bool(other and min(box[2], other[2]) > max(box[0], other[0]))
    if current.get('table_cell'):
        row = [(i, item) for i, item in peers if item.get('table_cell')
               and abs(item['table_cell'][1] - current['table_cell'][1]) <= 3
               and abs(item['table_cell'][3] - current['table_cell'][3]) <= 3
               and (item['table_cell'] == current['table_cell'] or
                    abs(item['table_cell'][2] - current['table_cell'][0]) <= 3 or
                    abs(item['table_cell'][0] - current['table_cell'][2]) <= 3)]
        if row:
            context['row'] = ' | '.join(item['text'] for _, item in
                                      sorted(row, key=lambda pair: pair[1]['box'][0]))[:500]
    preceding = [(i, item) for i, item in peers if same_column(item)
                 and item['box'][3] <= box[1]]
    def section_heading(item):
        cell = item.get('table_cell')
        current_cell = current.get('table_cell')
        spanning = not cell or (current_cell and
                                cell[2]-cell[0] > 1.25*(current_cell[2]-current_cell[0]))
        capitals = len(re.sub(r'[^a-zA-Z]', '', item['text'])) >= 4 and item['text'].isupper()
        return (item.get('source_bold') and not cell) or (capitals and spanning)
    headings = [(i, item) for i, item in peers
                if item.get('box') and item['box'][3] <= box[1] and section_heading(item)
                and (same_column(item) or
                     (item.get('table_cell') and item['table_cell'][0] <= box[0]
                      and item['table_cell'][2] >= box[2]))]
    if headings:
        context['section'] = max(headings, key=lambda pair: pair[1]['box'][3])[1]['text'][:250]
    # Table rows already give better context than unrelated neighbouring values.
    if not current.get('table_cell'):
        if preceding:
            context['preceding'] = max(preceding, key=lambda pair: pair[1]['box'][3])[1]['text'][:300]
        following = [(i, item) for i, item in peers if same_column(item)
                     and item['box'][1] >= box[3]]
        if following:
            context['following'] = min(following, key=lambda pair: pair[1]['box'][1])[1]['text'][:300]
    return context
