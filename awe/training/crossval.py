# 1. Set parameters in `data/params.json`.
# 2. Run `python -m awe.training.crossval`.

import numpy as np

import awe.training.params
import awe.training.trainer


def main():
    params = awe.training.params.Params.load_user(normalize=True)
    if params is None:
        return
    print(f'{params=}')

    # Like FreeDOM and SimpDOM, use cyclic permutations.
    trainer = awe.training.trainer.Trainer(params)
    trainer.load_pretrained()
    trainer.load_dataset()

    all_metrics: list[dict[str, float]] = []
    orig_name = params.version_name
    seed_len = len(params.train_website_indices)
    website_names = SWDE_VERTICAL_WEBSITES[params.vertical] \
        if params.dataset == awe.training.params.Dataset.swde \
        else [w.name for w in trainer.ds.verticals[0].websites]
    print(f'{website_names=}, {seed_len=}')
    for perm_idx in range(len(trainer.ds.verticals[0].websites)):
        trainer.params.version_name = f'{orig_name}-{perm_idx}'
        trainer.params.train_website_indices = get_cyclic_permutation_indices(
            seq_len=len(website_names),
            perm_idx=perm_idx,
            perm_len=seed_len
        )
        trainer.init_features()
        trainer.split_data()
        trainer.create_dataloaders()
        trainer.create_model()
        trainer.create_version()
        trainer.train()

        # Test on all pages.
        test_pages = [p for w in trainer.val_websites for p in w.pages]
        test_run = trainer.create_run(pages=test_pages, desc='test')
        all_metrics.append(trainer.validate(test_run))

    # Compute mean metrics.
    keys = { k for m in all_metrics for k in m.keys() }
    all_values = {
        k: [v for m in all_metrics if (v := m.get(k)) is not None]
        for k in keys
    }
    print('Mean metrics:')
    print({ k: np.mean(vs) for k, vs in all_values.items() })
    print('Counts:')
    print({ k: len(vs) for k, vs in all_values.items() })

def get_cyclic_permutation_indices(seq_len: int, perm_idx: int, perm_len: int):
    return [(perm_idx + idx) % seq_len for idx in range(perm_len)]

def get_cyclic_permutation(seq: list[str], perm_idx: int, perm_len: int):
    indices = get_cyclic_permutation_indices(
        seq_len=len(seq),
        perm_idx=perm_idx,
        perm_len=perm_len
    )
    return [seq[idx] for idx in indices]

# Ordering from SimpDOM source code.
SWDE_VERTICAL_WEBSITES = {
    "auto": [
        "msn", "aol", "kbb", "cars", "yahoo", "autoweb", "autobytel",
        "automotive", "carquotes", "motortrend"
    ],
    "book": [
        "abebooks", "amazon", "barnesandnoble", "bookdepository",
        "booksamillion", "borders", "buy", "christianbook", "deepdiscount",
        "waterstones"
    ],
    "camera": [
        "amazon", "beachaudio", "buy", "compsource", "ecost", "jr", "newegg",
        "onsale", "pcnation", "thenerds"
    ],
    "job": [
        "careerbuilder", "dice", "hotjobs", "job", "jobcircle", "jobtarget",
        "monster", "nettemps", "rightitjobs", "techcentric"
    ],
    "movie": [
        "allmovie", "amctv", "boxofficemojo", "hollywood", "iheartmovies",
        "imdb", "metacritic", "msn", "rottentomatoes", "yahoo"
    ],
    "nbaplayer": [
        "espn", "fanhouse", "foxsports", "msnca", "nba", "si", "slam",
        "usatoday", "wiki", "yahoo"
    ],
    "restaurant": [
        "fodors", "frommers", "gayot", "opentable", "pickarestaurant",
        "restaurantica", "tripadvisor", "urbanspoon", "usdiners", "zagat"
    ],
    "university": [
        "collegeboard", "collegenavigator", "collegeprowler", "collegetoolkit",
        "ecampustours", "embark", "matchcollege", "princetonreview",
        "studentaid", "usnews"
    ]
}

if __name__ == '__main__':
    main()
