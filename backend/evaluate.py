from __future__ import annotations

from collections import defaultdict
from typing import List, Tuple

from sklearn.metrics import accuracy_score, log_loss, brier_score_loss

from config import P_L0, P_T, P_G, P_S
from core.bkt import bkt_update, predict_correct
from core.data import load_interactions


def build_sequences() -> dict[tuple[str, str], List[int]]:
    """
    Group raw CSV rows into one response-sequence per (student_id, skill),
    preserving the order they appear in the CSV (assumed chronological).
    """
    sequences: dict[tuple[str, str], List[int]] = defaultdict(list)

    for row in load_interactions():
        key = (row["student_id"], row["skill"])
        sequences[key].append(int(row["response"]))

    return sequences


def predict_and_update_sequence(
    responses: List[int],
) -> Tuple[List[float], List[int]]:
    """
    Replay one student's response sequence through BKT, exactly like a
    live session would see it: predict BEFORE each answer, update AFTER.

    This is the same predict-then-update order as /api/state -> /api/answer.
    Any other order leaks the answer into its own prediction.
    """
    predictions: List[float] = []
    mastery = P_L0

    for response in responses:
        predicted = predict_correct(mastery, P_G, P_S)
        predictions.append(predicted)

        mastery = bkt_update(mastery, response, P_T, P_G, P_S)

    return predictions, responses


def evaluate() -> None:
    sequences = build_sequences()

    all_predictions: List[float] = []
    all_actuals: List[int] = []

    for (student_id, skill), responses in sequences.items():
        predictions, actuals = predict_and_update_sequence(responses)
        all_predictions.extend(predictions)
        all_actuals.extend(actuals)

    # Added safety check for empty database to prevent ZeroDivisionError
    if not all_actuals:
        print("No interaction data found in database. Answer some questions in the UI first.")
        return

    predicted_classes = [1 if p >= 0.5 else 0 for p in all_predictions]

    accuracy = accuracy_score(all_actuals, predicted_classes)
    logloss = log_loss(all_actuals, all_predictions, labels=[0, 1])
    brier = brier_score_loss(all_actuals, all_predictions)

    avg_predicted = sum(all_predictions) / len(all_predictions)
    avg_actual = sum(all_actuals) / len(all_actuals)

    print(f"Sequences evaluated : {len(sequences)}")
    print(f"Total (pred, actual) pairs : {len(all_actuals)}")
    print()
    print(f"Average predicted P(correct) : {avg_predicted:.4f}")
    print(f"Actual correctness rate      : {avg_actual:.4f}")
    print(f"Calibration gap               : {avg_predicted - avg_actual:+.4f}")
    print()
    print(f"Accuracy   : {accuracy:.4f}")
    print(f"Log loss   : {logloss:.4f}")
    print(f"Brier score: {brier:.4f}")


if __name__ == "__main__":
    evaluate()