from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import IMAGE_CLASSIFIER_PROVIDER

logger = logging.getLogger("app.image_classification")

_KEYWORDS_HIGH = {
    "passport",
    "license",
    "drivers_license",
    "driver_license",
    "idcard",
    "ssn",
    "tax",
    "w2",
    "medical",
    "insurance",
    "bank",
    "statement",
    "billing",
}
_KEYWORDS_MEDIUM = {"face", "selfie", "portrait", "profile", "document", "invoice"}


@dataclass(frozen=True)
class ClassificationResult:
    tier: str
    score: float
    contains_sensitive_regions: bool
    model: str
    mask: object | None = None


def classify_upload(path: Path, original_filename: str | None) -> ClassificationResult:
    provider = IMAGE_CLASSIFIER_PROVIDER.strip().lower()
    if provider == "light":
        result = _classify_with_light(path, original_filename)
        if result is not None:
            return result
    if provider == "sam3":
        result = _classify_with_sam3(path, original_filename)
        if result is not None:
            return result
    return _classify_with_heuristics(path, original_filename)


def _classify_with_sam3(path: Path, original_filename: str | None) -> ClassificationResult | None:
    # Placeholder hook: this is where SAM3 model loading/inference should run.
    # Fallback is intentional so deployments can enable provider=sam3 before model wiring is complete.
    logger.warning(
        "sam3_provider_not_wired_falling_back",
        extra={
            "event_data": {
                "event": "image_classification",
                "provider": "sam3",
                "path": str(path),
                "filename": original_filename or "",
            }
        },
    )
    return None


def _classify_with_light(path: Path, original_filename: str | None) -> ClassificationResult | None:
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning(
            "light_provider_missing_deps",
            extra={
                "event_data": {
                    "event": "image_classification",
                    "provider": "light",
                    "path": str(path),
                    "filename": original_filename or "",
                    "error": str(exc),
                }
            },
        )
        return None

    try:
        with Image.open(path) as image:
            image = image.convert("RGB")
            image = _resize_for_light(image, max_dim=512)
            rgb = np.asarray(image)
            ycbcr = np.asarray(image.convert("YCbCr"))
    except Exception as exc:
        logger.warning(
            "light_provider_image_load_failed",
            extra={
                "event_data": {
                    "event": "image_classification",
                    "provider": "light",
                    "path": str(path),
                    "filename": original_filename or "",
                    "error": str(exc),
                }
            },
        )
        return None

    slic_available = True
    try:
        from skimage import graph
        from skimage.color import rgb2lab
        from skimage.segmentation import slic
    except Exception:
        slic_available = False

    if slic_available:
        try:
            mask, fg_ratio = _segment_with_slic(rgb, rgb2lab, slic, graph)
        except Exception as exc:
            logger.warning(
                "light_provider_slic_failed",
                extra={
                    "event_data": {
                        "event": "image_classification",
                        "provider": "light",
                        "path": str(path),
                        "filename": original_filename or "",
                        "error": str(exc),
                    }
                },
            )
            mask = None
            fg_ratio = 0.0

        if mask is not None:
            tier, score, contains_sensitive_regions = _tier_from_ratio(fg_ratio)
            return ClassificationResult(
                tier=tier,
                score=score,
                contains_sensitive_regions=contains_sensitive_regions,
                model="light-slic-v4",
                mask=mask,
            )

    skin_mask = _skin_mask(rgb, ycbcr)
    skin_ratio = float(skin_mask.mean()) if skin_mask.size else 0.0
    tier, score, contains_sensitive_regions = _tier_from_ratio(skin_ratio, skin=True)

    return ClassificationResult(
        tier=tier,
        score=score,
        contains_sensitive_regions=contains_sensitive_regions,
        model="light-skinmask-v1",
        mask=skin_mask,
    )


def _resize_for_light(image, max_dim: int):
    width, height = image.size
    longest = max(width, height)
    if longest <= max_dim:
        return image
    scale = max_dim / float(longest)
    new_size = (int(width * scale), int(height * scale))
    return image.resize(new_size, resample=3)


def _skin_mask(rgb, ycbcr):
    import numpy as np

    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)

    cb = ycbcr[:, :, 1].astype(np.int16)
    cr = ycbcr[:, :, 2].astype(np.int16)

    ycbcr_mask = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
    rgb_mask = (r > 95) & (g > 40) & (b > 20) & (r > g) & (r > b) & (np.abs(r - g) > 15)

    return ycbcr_mask & rgb_mask


def _segment_with_slic(rgb, rgb2lab, slic, graph):
    import numpy as np
    from scipy import ndimage

    rgb_float = rgb.astype(np.float32) / 255.0
    labels = slic(
        rgb_float,
        n_segments=200,
        compactness=10.0,
        sigma=1.0,
        start_label=0,
    )
    lab = rgb2lab(rgb_float)

    rag = graph.rag_mean_color(lab, labels)
    labels = graph.merge_hierarchical(
        labels,
        rag,
        thresh=25.0,
        rag_copy=False,
        in_place_merge=True,
        merge_func=_merge_mean_color,
        weight_func=_weight_mean_color,
    )

    height, width = labels.shape
    total_pixels = float(height * width)

    # Edge strength map (cheap and robust for foreground selection)
    gray = (
        0.2989 * rgb_float[:, :, 0]
        + 0.5870 * rgb_float[:, :, 1]
        + 0.1140 * rgb_float[:, :, 2]
    )
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:] = np.abs(gray[:, 1:] - gray[:, :-1])
    gy[1:, :] = np.abs(gray[1:, :] - gray[:-1, :])
    edge = gx + gy

    border = np.zeros_like(labels, dtype=bool)
    border[0, :] = True
    border[-1, :] = True
    border[:, 0] = True
    border[:, -1] = True
    border_labels = set(labels[border].tolist())

    unique = np.unique(labels)
    global_lab = lab.reshape(-1, 3).mean(axis=0)
    border_lab = lab[border].mean(axis=0)

    scores = {}
    sizes = {}
    for label in unique.tolist():
        region_mask = labels == label
        count = int(region_mask.sum())
        if count == 0:
            continue
        sizes[label] = count

        edge_mean = float(edge[region_mask].mean())
        region_lab = lab[region_mask].mean(axis=0)
        color_dist = float(np.linalg.norm(region_lab - global_lab))
        border_dist = float(np.linalg.norm(region_lab - border_lab))
        size_ratio = count / total_pixels
        border_penalty = 0.03 if label in border_labels else 0.0

        scores[label] = {
            "edge": edge_mean,
            "color": color_dist,
            "border": border_dist,
            "size": size_ratio,
            "border_penalty": border_penalty,
        }

    if not scores:
        return None, 0.0

    edge_max = max(v["edge"] for v in scores.values()) or 1e-6
    color_max = max(v["color"] for v in scores.values()) or 1e-6
    border_max = max(v["border"] for v in scores.values()) or 1e-6
    size_max = max(v["size"] for v in scores.values()) or 1e-6

    best_label = None
    best_score = -1.0
    for label, vals in scores.items():
        edge_norm = vals["edge"] / edge_max
        color_norm = vals["color"] / color_max
        border_norm = vals["border"] / border_max
        size_norm = vals["size"] / size_max
        score = (
            0.30 * edge_norm
            + 0.25 * color_norm
            + 0.35 * border_norm
            + 0.10 * size_norm
            - vals["border_penalty"]
        )
        if score > best_score:
            best_score = score
            best_label = label

    if best_label is None:
        return None, 0.0

    # If the border is fairly uniform (e.g., white background), use a background
    # flood mask and take the largest non-background component.
    border_std = lab[border].std(axis=0).mean()
    if border_std < 6.0:
        dist = np.linalg.norm(lab - border_lab, axis=2)
        border_dist = dist[border]
        median = float(np.median(border_dist))
        mad = float(np.median(np.abs(border_dist - median)))
        bg_thresh = max(3.0, median + 3.5 * mad)

        bg_candidate = dist <= bg_thresh
        labeled_bg, num_bg = ndimage.label(bg_candidate)
        if num_bg > 0:
            border_components = set(np.unique(labeled_bg[border]).tolist())
            bg_mask = np.isin(labeled_bg, list(border_components))
            fg_mask = ~bg_mask
            fg_mask = ndimage.binary_opening(fg_mask, iterations=1)
            fg_mask = ndimage.binary_closing(fg_mask, iterations=2)
            fg_mask = ndimage.binary_fill_holes(fg_mask)

            labeled_fg, num_fg = ndimage.label(fg_mask)
            if num_fg > 0:
                sizes = ndimage.sum(fg_mask, labeled_fg, index=range(1, num_fg + 1))
                largest = int(np.argmax(sizes)) + 1
                mask = labeled_fg == largest
                fg_ratio = float(mask.sum()) / total_pixels
                if 0.01 < fg_ratio < 0.95:
                    return mask, fg_ratio

    # Fallback: grayscale thresholding (potato-on-white style cases).
    gray = (
        0.2989 * rgb_float[:, :, 0]
        + 0.5870 * rgb_float[:, :, 1]
        + 0.1140 * rgb_float[:, :, 2]
    )
    try:
        from skimage.filters import threshold_otsu

        gray_thresh = float(threshold_otsu(gray))
    except Exception:
        gray_thresh = float(np.median(gray))

    candidate_a = gray < gray_thresh
    candidate_b = ~candidate_a

    best_mask, best_ratio = _choose_component(candidate_a, border, total_pixels)
    if best_mask is None or best_ratio < 0.01:
        best_mask, best_ratio = _choose_component(candidate_b, border, total_pixels)
    if best_mask is not None and 0.01 < best_ratio < 0.95:
        return best_mask, best_ratio

    # If the best region is tiny, fall back to the most border-different region.
    best_size = sizes.get(best_label, 0)
    if best_size / total_pixels < 0.02:
        best_label = max(scores.items(), key=lambda item: item[1]["border"])[0]
        best_size = sizes.get(best_label, 0)

    # Region grow from the best label to capture same-colored neighbors.
    rag_final = graph.rag_mean_color(lab, labels)
    seed_mean = rag_final.nodes[best_label].get("mean color")
    if seed_mean is None:
        seed_mean = lab[labels == best_label].mean(axis=0)

    color_thresh = 12.0
    visited = set([best_label])
    queue = [best_label]
    selected = set([best_label])

    while queue:
        node = queue.pop(0)
        for neighbor in rag_final.neighbors(node):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            neighbor_mean = rag_final.nodes[neighbor].get("mean color")
            if neighbor_mean is None:
                neighbor_mean = lab[labels == neighbor].mean(axis=0)
            if np.linalg.norm(neighbor_mean - seed_mean) <= color_thresh:
                selected.add(neighbor)
                queue.append(neighbor)

    mask = np.isin(labels, list(selected))
    fg_ratio = float(mask.sum()) / total_pixels
    return mask, fg_ratio


def _choose_component(mask, border, total_pixels):
    from scipy import ndimage
    import numpy as np

    cleaned = ndimage.binary_opening(mask, iterations=1)
    cleaned = ndimage.binary_closing(cleaned, iterations=2)
    cleaned = ndimage.binary_fill_holes(cleaned)

    labeled, num = ndimage.label(cleaned)
    if num == 0:
        return None, 0.0

    border_components = set(np.unique(labeled[border]).tolist())
    sizes = ndimage.sum(cleaned, labeled, index=range(1, num + 1))
    candidate = None
    candidate_size = 0.0
    for idx, size in enumerate(sizes, start=1):
        if idx in border_components:
            continue
        if size > candidate_size:
            candidate_size = float(size)
            candidate = idx

    if candidate is None:
        candidate = int(np.argmax(sizes)) + 1
        candidate_size = float(sizes[candidate - 1])

    mask = labeled == candidate
    ratio = candidate_size / total_pixels
    return mask, ratio


def _merge_mean_color(graph_obj, src, dst):
    graph_obj.nodes[dst]["total color"] += graph_obj.nodes[src]["total color"]
    graph_obj.nodes[dst]["pixel count"] += graph_obj.nodes[src]["pixel count"]
    graph_obj.nodes[dst]["mean color"] = (
        graph_obj.nodes[dst]["total color"] / graph_obj.nodes[dst]["pixel count"]
    )


def _weight_mean_color(graph_obj, src, dst, n):
    import numpy as np

    diff = graph_obj.nodes[dst]["mean color"] - graph_obj.nodes[n]["mean color"]
    diff = np.linalg.norm(diff)
    return {"weight": diff}


def _tier_from_ratio(ratio: float, skin: bool = False):
    if skin:
        if ratio >= 0.35:
            tier = "high"
        elif ratio >= 0.12:
            tier = "medium"
        else:
            tier = "low"
        score = min(0.95, max(0.05, ratio * 2.2))
        contains_sensitive_regions = ratio >= 0.08
        return tier, score, contains_sensitive_regions

    if ratio >= 0.45:
        tier = "high"
    elif ratio >= 0.2:
        tier = "medium"
    else:
        tier = "low"
    score = min(0.95, max(0.05, ratio * 1.8))
    contains_sensitive_regions = ratio >= 0.2
    return tier, score, contains_sensitive_regions


def _classify_with_heuristics(path: Path, original_filename: str | None) -> ClassificationResult:
    name = (original_filename or path.name).lower()
    size_bytes = path.stat().st_size if path.exists() else 0

    if any(keyword in name for keyword in _KEYWORDS_HIGH):
        return ClassificationResult(
            tier="high",
            score=0.95,
            contains_sensitive_regions=True,
            model="heuristic-v1",
        )
    if any(keyword in name for keyword in _KEYWORDS_MEDIUM):
        return ClassificationResult(
            tier="medium",
            score=0.65,
            contains_sensitive_regions=True,
            model="heuristic-v1",
        )
    if size_bytes >= 8 * 1024 * 1024:
        return ClassificationResult(
            tier="medium",
            score=0.45,
            contains_sensitive_regions=False,
            model="heuristic-v1",
        )
    return ClassificationResult(
        tier="low",
        score=0.1,
        contains_sensitive_regions=False,
        model="heuristic-v1",
    )
