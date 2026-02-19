"""Pure computation functions for quality metrics.

These functions have no external dependencies and can be tested directly.
"""


def bbox_iou(b1: dict, b2: dict) -> float:
    """Calculate Intersection over Union for two bounding boxes."""
    x1 = max(b1.get("x", 0), b2.get("x", 0))
    y1 = max(b1.get("y", 0), b2.get("y", 0))
    x2 = min(b1.get("x", 0) + b1.get("w", 0), b2.get("x", 0) + b2.get("w", 0))
    y2 = min(b1.get("y", 0) + b1.get("h", 0), b2.get("y", 0) + b2.get("h", 0))

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = b1.get("w", 0) * b1.get("h", 0)
    area2 = b2.get("w", 0) * b2.get("h", 0)
    union = area1 + area2 - intersection

    return intersection / max(union, 1e-6)


def compute_label_agreement(annotations: list[dict]) -> float:
    """Compute label agreement between annotators."""
    by_user: dict[str, set] = {}
    for a in annotations:
        uid = a["user_id"]
        if uid not in by_user:
            by_user[uid] = set()
        by_user[uid].add(a["label"])

    users = list(by_user.keys())
    if len(users) < 2:
        return 1.0

    agreements = 0
    total = 0
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            overlap = by_user[users[i]] & by_user[users[j]]
            union = by_user[users[i]] | by_user[users[j]]
            agreements += len(overlap) / max(len(union), 1)
            total += 1

    return agreements / max(total, 1)


def compute_iou_agreement(annotations: list[dict]) -> float:
    """Compute IoU agreement for bounding box annotations."""
    bboxes_by_user: dict[str, list] = {}
    for a in annotations:
        if a.get("type") != "bbox" or not a.get("geometry"):
            continue
        uid = a["user_id"]
        if uid not in bboxes_by_user:
            bboxes_by_user[uid] = []
        bboxes_by_user[uid].append(a["geometry"])

    users = list(bboxes_by_user.keys())
    if len(users) < 2:
        return 1.0

    total_iou = 0.0
    count = 0
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            for b1 in bboxes_by_user[users[i]]:
                for b2 in bboxes_by_user[users[j]]:
                    total_iou += bbox_iou(b1, b2)
                    count += 1

    return total_iou / max(count, 1)


def compute_percent_agreement(annotations: list[dict]) -> float:
    """Simple percent agreement on labels."""
    by_user: dict[str, list] = {}
    for a in annotations:
        uid = a["user_id"]
        if uid not in by_user:
            by_user[uid] = []
        by_user[uid].append(a["label"])

    users = list(by_user.keys())
    if len(users) < 2:
        return 1.0

    agreements = 0
    total = 0
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            labels_i = sorted(by_user[users[i]])
            labels_j = sorted(by_user[users[j]])
            if labels_i == labels_j:
                agreements += 1
            total += 1

    return agreements / max(total, 1)


def transform_geometry(geometry: dict, ann_type: str, transforms: list, width: int, height: int) -> dict:
    """Apply geometric transforms to annotation geometry."""
    geom = dict(geometry)

    for t in transforms:
        if t["type"] == "horizontal_flip":
            if ann_type == "bbox" and "x" in geom and "w" in geom:
                geom["x"] = width - geom["x"] - geom["w"]
            elif ann_type == "point" and "x" in geom:
                geom["x"] = width - geom["x"]
            elif ann_type == "polygon" and "points" in geom:
                geom["points"] = [[width - p[0], p[1]] for p in geom["points"]]

        elif t["type"] == "vertical_flip":
            if ann_type == "bbox" and "y" in geom and "h" in geom:
                geom["y"] = height - geom["y"] - geom["h"]
            elif ann_type == "point" and "y" in geom:
                geom["y"] = height - geom["y"]
            elif ann_type == "polygon" and "points" in geom:
                geom["points"] = [[p[0], height - p[1]] for p in geom["points"]]

        elif t["type"] == "scale":
            factor = t["factor"]
            if ann_type == "bbox":
                for k in ("x", "y", "w", "h"):
                    if k in geom:
                        geom[k] = geom[k] * factor
            elif ann_type == "point":
                if "x" in geom:
                    geom["x"] = geom["x"] * factor
                if "y" in geom:
                    geom["y"] = geom["y"] * factor
            elif ann_type == "polygon" and "points" in geom:
                geom["points"] = [[p[0] * factor, p[1] * factor] for p in geom["points"]]

    return geom
