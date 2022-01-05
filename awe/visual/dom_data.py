import json
import os
import re
from typing import TYPE_CHECKING, Any, Callable, Optional

from awe import awe_graph, utils
from awe.visual import visual_attribute

if TYPE_CHECKING:
    from awe import features

XPATH_ELEMENT_REGEX = r'^/(.*?)(\[\d+\])?$'

def get_tag_name(xpath_element: str):
    return re.match(XPATH_ELEMENT_REGEX, xpath_element).group(1)

class DomData:
    """Can load visual attributes saved by `extractor.ts`."""

    data: dict[str, Any]

    def __init__(self, path: str):
        self.path = path
        self.data = {}

    @property
    def exists(self):
        return os.path.exists(self.path)

    @property
    def contents(self):
        with open(self.path, mode='r', encoding='utf-8') as file:
            return file.read()

    def read(self):
        """Reads DOM data from JSON."""
        self.data = json.loads(self.contents)

    def load_all(self, ctx: 'features.PageContextBase'):
        for node in ctx.nodes:
            self.load_one(node)

        # Check that all extracted data were used.
        queue = [(self.data, '', None)]
        def get_xpath(tag_name: str, parent, suffix = ''):
            """Utility for reconstructing XPath in case of error."""
            xpath = f'{tag_name}{suffix}'
            if parent is not None:
                return get_xpath(parent[1], parent[2], xpath)
            return xpath
        while len(queue) > 0:
            item = queue.pop()
            node_data, tag_name, parent = item

            # Check this entry has node attached to it (so `load_one` was called
            # on it).
            node = node_data.get('_node')
            if node is None and tag_name != '':
                raise RuntimeError('Unused visual attributes for ' + \
                    f'{get_xpath(tag_name, parent)} in {self.path}')

            # Add children to queue.
            for child_name, child_data in node_data.items():
                if (
                    child_name.startswith('/') and
                    ctx.node_predicate.include_visual(child_data, child_name)
                ):
                    queue.insert(0, (child_data, child_name, item))

    def load_one(self, node: awe_graph.HtmlNode):
        node_data = self.find(node.xpath)
        node_data['_node'] = node

        # Check that IDs match.
        if not node.is_text:
            real_id = node.element.attrib.get('id')
            extracted_id = node_data.get('id')
            assert real_id == extracted_id, f'IDs of {node.xpath} do not ' + \
                f'match ("{real_id}" vs "{extracted_id}") in {self.path}.'

        # Load `node_data` into `node`.
        def load_attribute(
            target: object,
            snake_case: str,
            parser: Callable[[Any], Any] = lambda x: x,
            default: Optional[Any] = None
        ):
            camel_case = utils.to_camel_case(snake_case)
            val = node_data.get(camel_case) or default
            if val is not None:
                try:
                    result = parser(val)
                except ValueError as e:
                    print(f'Cannot parse {snake_case}="{val}", using ' + \
                        f'default="{val}" in {self.path}: {str(e)}')
                    result = default

                # Set attribute.
                if isinstance(target, dict):
                    target[snake_case] = result
                else:
                    setattr(target, snake_case, result)

        load_attribute(node, 'box',
            parser=lambda b: awe_graph.BoundingBox(b[0], b[1], b[2], b[3]))

        # Load visual attributes except for text fragments (they don't have
        # their own but inherit them from their container node instead).
        if not node.is_text:
            for a in visual_attribute.VISUAL_ATTRIBUTES.values():
                load_attribute(node.visuals, a.name, a.parse, a.get_default(node))
        return True

    def find(self, xpath: str):
        elements = xpath.split('/')[1:]
        current_data = self.data
        for index, element in enumerate(elements):
            current_data = current_data.get(f'/{element}')
            if current_data is None:
                current_xpath = '/'.join(elements[:index + 1])
                raise RuntimeError(
                    f'Cannot find visual attributes for /{current_xpath} ' + \
                    f'while searching for {xpath} in {self.path}')
        return current_data
