import collections
from typing import TYPE_CHECKING, Optional

import torch
import torchmetrics

import awe.data.set.pages
import awe.model.metrics
import awe.utils

if TYPE_CHECKING:
    import awe.model.classifier
    import awe.training.trainer


class Evaluator:
    def __init__(self, trainer: 'awe.training.trainer.Trainer'):
        self.trainer = trainer

    def start_evaluation(self):
        return Evaluation(self)

class FloatMetric:
    total: float = 0.0
    count: int = 0

    def add(self, value: float):
        self.total += value
        self.count += 1

    def compute(self):
        return self.total / self.count

class Metrics:
    """Wrapper for `MetricCollection` handling some edge cases."""

    updated: bool = False

    def __init__(self, evaluator: Evaluator, *args, **kwargs):
        self.collection = torchmetrics.MetricCollection(*args, **kwargs) \
            .to(evaluator.trainer.device)

    def update(self, *args, **kwargs):
        self.collection.update(*args, **kwargs)
        self.updated = True

    def compute(self):
        d = self.collection.compute() if self.updated else {}
        return { k: v.item() for k, v in d.items() }

class Evaluation:
    metrics: dict[str, FloatMetric]

    def __init__(self, evaluator: Evaluator):
        self.evaluator = evaluator
        self.metrics = collections.defaultdict(FloatMetric)
        self.nodes = Metrics(evaluator, [
            torchmetrics.Accuracy(ignore_index=0),
            torchmetrics.F1(ignore_index=0)
        ])

    def clear(self):
        self.metrics.clear()

    def compute(self, pages: Optional[list[awe.data.set.pages.Page]] = None):
        metrics_dict = { k: v.compute() for k, v in self.metrics.items() }
        metrics_dict.update(self.nodes.compute())

        # Compute page-wide metrics.
        if pages is not None:
            per_label = {
                label_key: awe.model.metrics.PredStats() for label_key
                in self.evaluator.trainer.label_map.label_to_id.keys()
            }
            for page in pages:
                # Skip pages that haven't been predicted yet.
                if page.dom.num_predicted_nodes == 0:
                    continue

                for label_key, pred in page.dom.node_predictions.items():
                    stats = per_label[label_key]
                    gold = page.dom.labeled_nodes.get(label_key)
                    if not gold:
                        # Negative sample is when no node is labeled.
                        if not pred:
                            stats.true_negatives += 1
                        else:
                            stats.false_negatives += 1
                    else:
                        # Find most confident prediction.
                        best_pred = awe.utils.where_max(pred,
                            lambda p: p.confidence).node
                        if best_pred in gold:
                            stats.true_positives += 1
                        else:
                            stats.false_positives += 1

            # Average per-label stats.
            page_metrics = awe.model.metrics.F1Metrics.from_vector(sum(
                awe.model.metrics.F1Metrics.compute(stats).to_vector()
                for stats in per_label.values()) / len(per_label))

            metrics_dict.update(page_metrics.to_dict(prefix='page_'))

        return metrics_dict

    def add(self, pred: 'awe.model.classifier.Prediction'):
        self.add_fast(pred.outputs)
        self.add_slow(pred)

    def add_fast(self, outputs: 'awe.model.classifier.ModelOutput'):
        self.metrics['loss'].add(outputs.loss.item())

    def add_slow(self, pred: 'awe.model.classifier.Prediction'):
        self.nodes.update(preds=pred.outputs.logits, target=pred.outputs.gold_labels)

        # Save all predicted nodes.
        pred_labels = pred.outputs.get_pred_labels()
        for idx in torch.nonzero(pred_labels):
            label_id = pred_labels[idx]
            label_key = self.evaluator.trainer.label_map.id_to_label[label_id.item()]
            pred.batch[idx.item()].predict_as(
                label_key=label_key,
                confidence=pred.outputs.logits[idx, label_id]
            )
        for node in pred.batch:
            node.mark_predicted()
