import dataclasses
import os
import warnings
from typing import Optional

import json5
import pandas as pd
import slugify
from tqdm.auto import tqdm

import awe.data.constants
import awe.data.parsing
import awe.data.set.db
import awe.data.set.labels
import awe.data.set.pages

DIR = f'{awe.data.constants.DATA_DIR}/apify'
SELECTOR_PREFIX = 'selector_'

@dataclasses.dataclass
class Dataset(awe.data.set.pages.Dataset):
    verticals: list['Vertical'] = dataclasses.field(repr=False)

    def __init__(self,
        only_websites: Optional[list[str]] = None,
        convert: bool = True,
        only_label_keys: Optional[list[str]] = None
    ):
        super().__init__(
            name='apify',
            dir_path=DIR,
        )
        self.only_websites = only_websites
        self.convert = convert
        self.only_label_keys = only_label_keys
        self.verticals = [
            Vertical(dataset=self, name='products', prev_page_count=0)
        ]

    def filter_label_keys(self, df: pd.DataFrame):
        if (label_keys := self.only_label_keys) is not None:
            all_label_keys = {
                col[len(SELECTOR_PREFIX):]
                for col in df.columns
                if col.startswith(SELECTOR_PREFIX)
            }
            for excluded_label_key in all_label_keys.difference(label_keys):
                del df[excluded_label_key]
                del df[f'{SELECTOR_PREFIX}{excluded_label_key}']

@dataclasses.dataclass
class Vertical(awe.data.set.pages.Vertical):
    dataset: Dataset
    websites: list['Website'] = dataclasses.field(repr=False, default_factory=list)

    def __post_init__(self):
        self.websites = list(self._iterate_websites())

    @property
    def dir_path(self):
        return self.dataset.dir_path

    def _iterate_websites(self):
        if not os.path.exists(self.dir_path):
            warnings.warn(
                f'Dataset directory does not exist ({self.dir_path}).')
            return

        page_count = 0
        for subdir in tqdm(sorted(os.listdir(self.dir_path)), desc='websites'):
            if (self.dataset.only_websites is not None
                and subdir not in self.dataset.only_websites):
                continue

            # Ignore some directories.
            if (not os.path.isdir(os.path.join(self.dir_path, subdir)) or
                subdir.startswith('.') or subdir == 'Datasets'):
                continue

            website = Website(
                vertical=self,
                dir_name=subdir,
                prev_page_count=page_count
            )
            yield website
            page_count += website.page_count

@dataclasses.dataclass
class Website(awe.data.set.pages.Website):
    vertical: Vertical
    db: Optional[awe.data.set.db.Database] = dataclasses.field(repr=False, default=None)
    df: Optional[pd.DataFrame] = dataclasses.field(repr=False, default=None)

    def __init__(self, vertical: Vertical, dir_name: str, prev_page_count: int):
        super().__init__(
            vertical=vertical,
            name=dir_name,
            prev_page_count=prev_page_count,
        )

        if not self.vertical.dataset.convert:
            self.df = self.read_json_df()
            self.vertical.dataset.filter_label_keys(self.df)
            self.page_count = len(self.df)
            print(f'Loaded {self.dataset_json_path!r}.')
        else:
            # Convert dataset.
            self.db = awe.data.set.db.Database(self.dataset_db_path)
            if not self.db.fresh:
                self.page_count = len(self.db)
            else:
                df = self.read_json_df()
                self.vertical.dataset.filter_label_keys(df)
                self.page_count = len(df)

                # Gather DataFrame columns to convert into metadata.
                selector_cols = {
                    col for col in df.columns
                    if col.startswith(SELECTOR_PREFIX)
                }
                metadata_cols = selector_cols | {
                    col[len(SELECTOR_PREFIX):]
                    for col in selector_cols
                }

                # Add rows to database.
                progress = tqdm(enumerate(df.iloc),
                    desc=self.dataset_db_path,
                    total=self.page_count
                )
                for idx, row in progress:
                    metadata_dict = {
                        k: v
                        for k, v in row.items()
                        if k in metadata_cols
                    }
                    metadata_json = json5.dumps(metadata_dict)
                    visuals_path = f'{self.dir_path}/pages/localized_html_{slugify.slugify(row.url)}-exact.json'
                    with open(visuals_path, mode='r', encoding='utf-8') as file:
                        visuals = file.read()
                    self.db.add(idx,
                        url=row.url,
                        html_text=row.localizedHtml,
                        visuals=visuals,
                        metadata=metadata_json
                    )
                    if idx % 100 == 1:
                        self.db.save()
                self.db.save()

        self.pages = [
            Page(website=self, index=idx)
            for idx in range(self.page_count)
        ]

    @property
    def dir_path(self):
        return f'{self.vertical.dir_path}/{self.name}'

    @property
    def dataset_json_path(self):
        return f'{self.dir_path}/augmented_dataset.json'

    @property
    def dataset_db_path(self):
        return f'{self.dir_path}/dataset.db'

    def read_json_df(self):
        if not os.path.exists(self.dataset_json_path):
            raise RuntimeError(
                f'JSON not found ({self.dataset_json_path!r}).')
        return pd.read_json(self.dataset_json_path)

    def save_json_df(self):
        self.df.to_json(self.dataset_json_path)

@dataclasses.dataclass(eq=False)
class Page(awe.data.set.pages.Page):
    website: Website
    index: int = None

    @property
    def db(self):
        return self.website.db

    @property
    def row(self):
        return self.website.df.iloc[self.index]

    @property
    def metadata(self):
        if self.db is not None:
            json_text = self.db.get_metadata(self.index)
            return json5.loads(json_text)
        return self.row

    @property
    def url_slug(self):
        return slugify.slugify(self.url)

    @property
    def file_name_no_extension(self):
        return f'localized_html_{self.url_slug}'

    @property
    def visuals_suffix(self):
        return '-exact'

    @property
    def dir_path(self):
        return f'{self.website.dir_path}/pages'

    @property
    def url(self) -> str:
        if self.db is not None:
            return self.db.get_url(self.index)
        return self.row.url

    def get_html_text(self):
        if self.db is not None:
            return self.db.get_html_text(self.index)
        return self.row.localizedHtml

    def get_labels(self):
        return PageLabels(self)

    def get_visuals_json_text(self):
        if self.db is not None:
            return self.db.get_visuals(self.index)
        return self.create_visuals().get_json_str()

    def load_visuals(self):
        visuals = self.create_visuals()
        visuals.load_json_str(self.get_visuals_json_text())
        return visuals

class PageLabels(awe.data.set.labels.PageLabels):
    page: Page

    @property
    def label_keys(self):
        keys: list[str] = self.page.metadata.keys()
        return [
            k[len(SELECTOR_PREFIX):]
            for k in keys
            if k.startswith(SELECTOR_PREFIX)
        ]

    def get_selector(self, label_key: str):
        return self.page.metadata[f'{SELECTOR_PREFIX}{label_key}']

    def has_label(self, label_key: str):
        return self.get_selector(label_key) != ''

    def get_label_values(self, label_key: str):
        label_value = self.page.metadata[label_key]

        # Check that when CSS selector is empty string, gold value is empty.
        if not self.has_label(label_key):
            assert label_value == '', \
                f'Unexpected non-empty {label_value=} for {label_key=}.'
            return []

        # HACK: Sometimes in the dataset, the node does not exist even though it
        # has a selector specified. Then we don't want to return `['']` (one
        # empty node), but `[]` (no nodes) instead. Prerequisite for this
        # situation is that the value is empty (but it can be string or list).
        if not label_value and len(self.get_labeled_nodes(label_key)) == 0:
            selector = self.get_selector(label_key)
            warnings.warn(f'Ignoring non-existent {selector=} for ' + \
                f'{label_key=} ({self.page.url}).')
            return []

        return [label_value]

    def get_labeled_nodes(self, label_key: str):
        if not self.has_label(label_key):
            return []
        selector = self.get_selector(label_key)

        # HACK: If selector contains `+`, replace it by `~` as there is a bug in
        # Lexbor's implementation of the former (a segfault occurs in
        # `lxb_selectors_sibling` at source/lexbor/selectors/selectors.c:266).
        # Note the space, so we don't match  `:has(+...)` which is fine.
        if ' + ' in selector:
            new_selector = selector.replace(' + ', ' ~ ')
            warnings.warn(f'Patched selector {selector!r} to {new_selector!r}.')
            selector = new_selector

        try:
            return self.page.dom.tree.css(selector)
        except awe.data.parsing.Error as e:
            raise RuntimeError(
                f'Invalid selector {repr(selector)} for {label_key=} ' + \
                f'({self.page.url}).') from e
