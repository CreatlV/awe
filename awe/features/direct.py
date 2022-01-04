import re
from typing import TYPE_CHECKING

import torch

# pylint: disable=wildcard-import, unused-wildcard-import
from awe.features.context import *
from awe.features.feature import *
from awe.features.visual import visual_attribute

if TYPE_CHECKING:
    from awe import awe_graph


class Depth(DirectFeature):
    """Relative depth of node in DOM tree."""

    @property
    def labels(self):
        return ['relative_depth']

    @staticmethod
    def _get_max_depth(context: PageContext):
        if context.max_depth is None:
            context.max_depth = max(map(lambda n: n.depth, context.nodes))
        return context.max_depth

    def compute(self, node: 'awe_graph.HtmlNode', context: PageContext):
        return torch.FloatTensor([node.depth / self._get_max_depth(context)])

class IsLeaf(DirectFeature):
    """Whether node is leaf (text) node."""

    @property
    def labels(self):
        return ['is_leaf']

    def compute(self, node: 'awe_graph.HtmlNode', _):
        return torch.FloatTensor([node.is_text])

class CharCategories(DirectFeature):
    """Counts of different character categories."""

    @property
    def labels(self):
        return ['dollars', 'letters', 'digits']

    def compute(self, node: 'awe_graph.HtmlNode', _):
        def count_pattern(pattern: str):
            return len(re.findall(pattern, node.text)) if node.is_text else 0

        return torch.FloatTensor([
            count_pattern(r'[$]'),
            count_pattern(r'[a-zA-Z]'),
            count_pattern(r'\d')
        ])

class Visuals(DirectFeature):
    """Visual features."""

    @property
    def labels(self):
        return [
            l
            for a in visual_attribute.VISUAL_ATTRIBUTES.values()
            for l in a.get_labels()
        ]

    def prepare(self, node: 'awe_graph.HtmlNode', context: RootContext):
        Visuals._compute(node, context, freezed = False)

    def compute(self, node: 'awe_graph.HtmlNode', context: PageContext):
        return Visuals._compute(node, context.root, freezed = True)

    @staticmethod
    def _compute(node: 'awe_graph.HtmlNode', context: RootContext, freezed: bool):
        node = node.visual_node
        return torch.FloatTensor([
            a.selector(
                visual_attribute.AttributeContext(a, node, context, freezed))
            for a in visual_attribute.VISUAL_ATTRIBUTES.values()
        ])
