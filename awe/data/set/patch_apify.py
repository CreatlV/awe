# Run: `python -m awe.data.set.patch_apify`

import json
import os

import ijson
import pandas as pd
from tqdm.auto import tqdm


def main():
    patch_alza()
    patch_notino()

def patch_alza():
    """
    Patches two bugs in dataset `alzaEn`.
    1. Selector for category contains unnecessary space.
    2. Selector for params (`.params`) sometimes matches an empty node.
    """

    input_path = 'data/apify/alzaEn/augmented_dataset.json'
    print(f'Patching {input_path!r}...')
    df = pd.read_json(input_path)
    selector_category = df.columns.get_loc('selector_category')
    selector_specification = df.columns.get_loc('selector_specification')
    bug_1 = 0
    bug_2 = 0
    for idx in tqdm(range(len(df)), total=len(df), desc=input_path):
        # Bug 1.
        if df.iloc[idx, selector_category] == '.breadcrumbs .js-breadcrumbs':
            df.iloc[idx, selector_category] = '.breadcrumbs.js-breadcrumbs'
            bug_1 += 1

        # Bug 2.
        if df.iloc[idx, selector_specification] == '.params':
            df.iloc[idx, selector_specification] = '#cpcm_cpc_mediaParams > .params'
            bug_2 += 1

    if bug_1 > 0 or bug_2 > 0:
        print(f'Saving {input_path!r} ({bug_1=} {bug_2=})...')
        df.to_json(input_path)

def patch_notino():
    """
    Drops HTML from dataset `notinoEn`, it's not necessary (since exact HTML
    must be extracted by the visuals extractor anyway) and can cause
    out-of-memory when loading the JSON dataset.
    """

    input_path = 'data/apify/notinoEn/augmented_dataset.json'
    output_path = 'data/apify/notinoEn/slim_dataset.json'

    if os.path.exists(output_path):
        print(f'Skipping notino patching, the output exists ({output_path!r}).')
        return

    print(f'Patching {input_path!r}...')
    with open(input_path, mode='rb') as input_file:
        with open(output_path, mode='w', encoding='utf-8') as output_file:
            output_file.write('[\n')
            rows = ijson.items(input_file, 'item')
            after_first = False
            for input_row in tqdm(rows, desc=input_path, total=2000):
                output_row = {
                    k: v
                    for k, v in input_row.items()
                    if k == 'url' or k.startswith('selector_')
                }
                if after_first:
                    output_file.write(',\n')
                else:
                    after_first = True
                json.dump(output_row, output_file)
            output_file.write(']\n')

if __name__ == '__main__':
    main()
