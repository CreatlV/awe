from typing import TYPE_CHECKING, Optional

from awe import filtering

if TYPE_CHECKING:
    from awe import awe_graph


class RootContext:
    """
    Data stored here are scoped to all pages. Initialized in `Feature.prepare`.
    """

    pages: set[str]
    """Identifiers of pages used for feature preparation against this object."""

    chars: set[str]
    """
    All characters present in processed nodes. Stored by `CharacterIdentifiers`.
    """

    max_word_len: int = 0
    """Length of the longest word. Stored by `CharacterIdentifiers`."""

    max_num_words: int = 0
    """
    Number of words in the longest node (up to `cutoff_words`). Stored by
    `CharacterIdentifiers` and `WordIdentifiers`.
    """

    cutoff_words: Optional[int] = None
    """
    Maximum number of words to preserve in each node (or `None` to preserve
    all). Used by `CharacterIdentifiers` and `WordIdentifiers`.
    """

    cutoff_word_length: Optional[int] = None
    """
    Maximum number of characters to preserve in each token (or `None` to
    preserve all). Used by `CharacterIdentifiers`.
    """

    def __init__(self):
        self.pages = set()
        self.chars = set()

    def options_from(self, other: 'RootContext'):
        self.cutoff_words = other.cutoff_words
        self.cutoff_word_length = other.cutoff_word_length

    def merge_with(self, other: 'RootContext'):
        self.pages.update(other.pages)
        self.chars.update(other.chars)
        self.max_word_len = max(self.max_word_len, other.max_word_len)
        self.max_num_words = max(self.max_num_words, other.max_num_words)
        assert self.cutoff_words == other.cutoff_words, \
            f'Option `cutoff_words` does not match ({self.cutoff_words} ' + \
            'vs. {other.cutoff_words})'

    def extract_options(self):
        return {
            'cutoff_words': self.cutoff_words,
            'cutoff_word_length': self.cutoff_word_length
        }

    def describe(self):
        return {
            'pages': len(self.pages),
            'chars': len(self.chars),
            'max_num_words': self.max_num_words,
            'max_word_len': self.max_word_len
        }

class LiveContext:
    """
    Non-persisted (live) data scoped to all pages. Initialized in
    `Feature.initialize`.
    """

    char_dict: dict[str, int]
    """Used by `CharacterEmbedding`."""

    token_dict: dict[str, int]
    """Used by `WordEmbedding`."""

    def __init__(self, root: RootContext):
        self.root = root
        self.char_dict = {}
        self.word_dict = {}

class PageContextBase:
    """Everything needed to prepare `HtmlPage`."""

    _nodes: list['awe_graph.HtmlNode'] = None

    def __init__(self,
        page: 'awe_graph.HtmlPage',
        node_predicate: filtering.NodePredicate
    ):
        self.page = page
        self.node_predicate = node_predicate

    @property
    def nodes(self):
        """Cached list of `page.nodes`."""
        if self._nodes is None:
            root = self.page.initialize_tree()
            self._nodes = list(root.iterate_descendants(
                self.node_predicate.include_node_itself,
                self.node_predicate.include_node_descendants
            ))
        return self._nodes

    def prepare(self):
        # Assign indices to nodes (different from `HtmlNode.index` as that
        # one is from before filtering). This is needed to compute edges.
        for index, node in enumerate(self.nodes):
            node.dataset_index = index

class PageContext(PageContextBase):
    """
    Everything needed to compute a `HtmlNode`'s `Feature`s.

    Data stored here are scoped to one `HtmlPage`.
    """

    max_depth: Optional[int] = None
    """Maximum DOM tree depth. Stored by `Depth`."""

    def __init__(self,
        live: LiveContext,
        page: 'awe_graph.HtmlPage',
        node_predicate: filtering.NodePredicate
    ):
        self.live = live
        super().__init__(page, node_predicate)

    @property
    def root(self):
        return self.live.root
