# Computes mean metrics after running `crossval` several times.
# Run: `python -m awe.training.crossval_mean <first_version_num>`.

import argparse
import json
import os

import numpy as np

import awe.training.params
import awe.training.versioning


def main():
    args = parse_args()
    awe.training.versioning.LOG_DIR = args.logdir

    params = awe.training.params.Params.load_user()

    # Load all saved metrics.
    last_version = None
    all_metrics = []
    idx = 0
    while True:
        version = awe.training.versioning.Version(
            number=args.version_num + idx,
            name=f'{params.version_name}-{idx}'
        )
        if not version.exists():
            break
        results_path = version.get_results_path('test')
        if not os.path.exists(results_path):
            break
        with open(results_path, mode='r', encoding='utf-8') as f:
            all_metrics.append(json.load(f))
        idx += 1
        last_version = version

    if last_version is None:
        print('Cannot find any version.')
        return

    # Compute mean metrics.
    keys = { k for m in all_metrics for k in m.keys() }
    all_values = {
        k: [v for m in all_metrics if (v := m.get(k)) is not None]
        for k in keys
    }
    aggregated_metrics = {
        k: {
            'mean': np.mean(vs),
            'count': len(vs)
        }
        for k, vs in all_values.items()
    }

    # Save under the last version dir.
    file_path = last_version.get_results_path('crossval')
    with open(file_path, mode='w', encoding='utf-8') as f:
        json.dump(aggregated_metrics, f, indent=2, sort_keys=True)
    print(f'Saved to {file_path!r}.')

def parse_args():
    parser = argparse.ArgumentParser(
        description='Evaluates cross-validation training',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--logdir',
        default=awe.training.versioning.LOG_DIR,
        help='directory where versions are stored'
    )
    parser.add_argument('version_num',
        type=int,
        help='first cross-validation version number'
    )
    return parser.parse_args()

if __name__ == '__main__':
    main()
