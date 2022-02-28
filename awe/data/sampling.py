from typing import TYPE_CHECKING

from tqdm.auto import tqdm

import awe.data.graph.dom
import awe.data.set.pages
import awe.features.extraction

if TYPE_CHECKING:
    import awe.training.trainer

Sample = awe.data.graph.dom.Node

class Sampler:
    """
    Prepares data samples for training. When called, takes pages and returns
    list of samples.
    """

    def __init__(self, trainer: 'awe.training.trainer.Trainer'):
        self.trainer = trainer

    def __call__(self, pages: list[awe.data.set.pages.Page], desc: str):
        result = [
            node
            for page in tqdm(pages, desc=desc)
            for node in self.get_nodes_for_page(page)
        ]
        self.trainer.extractor.initialize()
        return result

    def get_nodes_for_page(self, page: awe.data.set.pages.Page) -> list[Sample]:
        if page.cache_dom().root is None:
            page.dom.init_nodes()

            page.dom.init_labels()

        for label_key in page.labels.label_keys:
            self.trainer.label_map.map_label_to_id(label_key)

        self.trainer.extractor.prepare_page(page.dom)

        return page.dom.nodes

class Collater:
    """
    Prepares data for model. When called, takes batch of samples and returns
    batch of model inputs.
    """

    def __call__(self, samples: list[Sample]):
        return samples
