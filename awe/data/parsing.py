import re
from typing import Callable

import selectolax
import selectolax.lexbor

import awe.data.html_utils

WHITESPACE_CHAR_REGEX = r'(\s|[\u200b])'
"""Matches whitespace character."""

ANY_WHITESPACE_REGEX = re.compile(fr'{WHITESPACE_CHAR_REGEX}+')

EMPTY_OR_WHITESPACE_REGEX = re.compile(fr'^{WHITESPACE_CHAR_REGEX}*$')

IGNORED_TAG_NAMES = [
    'script',
    'style',
    'head',
    'noscript',
    'iframe'
]

# pylint: disable=c-extension-no-member
Node = selectolax.lexbor.LexborNode
Tree = selectolax.lexbor.LexborHTMLParser
Error = selectolax.lexbor.SelectolaxError
# pylint: enable=c-extension-no-member

def find_nodes_with_text(tree: Tree, needle: str):
    """
    Finds nodes containing the specified `needle` as their text content.
    """

    normalized_needle = normalize_node_text(needle)
    return [
        node for node in tree.body.traverse(include_text=True)
        if node_contains_normalized_text(node, normalized_needle)
    ]

def node_contains_text(node: Node, needle: str):
    normalized_needle = normalize_node_text(needle)
    return node_contains_normalized_text(node, normalized_needle)

def node_contains_normalized_text(node: Node, normalized_needle: str):
    return (
        awe.data.html_utils.is_text(node) and
        normalize_node_text(node.text()) == normalized_needle
    )

def parse_html(html_text: str):
    # Note that unlike the default selectolax parser, the Lexbor parser can
    # correctly extract text fragments `X`, `Y`, `Z` from HTML
    # `<p>X<br>Y<br>Z</p>`.
    tree = Tree(html_text)

    # Ignore some tags.
    tree.strip_tags(IGNORED_TAG_NAMES)

    # Ignore comments.
    remove_where(tree, ignore_node)

    return tree

def filter_tree(tree: Tree):
    # Ignore more nodes.
    remove_where(tree, filter_node)

def normalize_node_text(text: str):
    return collapse_whitespace(text).strip()

def collapse_whitespace(text: str):
    return re.sub(ANY_WHITESPACE_REGEX, ' ', text)

def remove_whitespace(text: str):
    return re.sub(ANY_WHITESPACE_REGEX, '', text)

def is_empty_or_whitespace(text: str):
    return re.match(EMPTY_OR_WHITESPACE_REGEX, text) is not None

def remove_where(tree: Tree, predicate: Callable[[Node], bool]):
    to_destroy = [n
        for n in tree.root.traverse(include_text=True)
        if predicate(n)
    ]
    for n in to_destroy:
        n: Node
        n.decompose(recursive=False)

def ignore_node(node: Node):
    return (
        # Ignore comments.
        awe.data.html_utils.is_comment(node)
    )

def filter_node(node: Node):
    return (
        # Ignore text fragments containing only white space.
        (
            awe.data.html_utils.is_text(node) and
            is_empty_or_whitespace(node.text(deep=False))
        )
    )
