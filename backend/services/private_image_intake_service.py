from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Any

from backend.services.private_campaign_data_service import private_campaign_data_service
from backend.services.private_index_service import private_index_service


IMAGE_CATEGORIES = {
    "portrait_pc",
    "portrait_npc",
    "portrait_creature",
    "scene_illustration",
    "map",
    "location_illustration",
    "item_illustration",
    "symbol_or_sigils",
    "handout_candidate",
    "ui_or_layout",
    "cover_or_chapter_art",
    "token_or_marker",
    "table_or_diagram",
    "duplicate_or_variant",
    "decorative_noise",
    "unknown",
}

IMAGE_REVIEW_STATUSES = {
    "unreviewed",
    "candidate",
    "confirmed",
    "rejected",
    "wrong_match",
    "duplicate",
    "needs_better_extraction",
}

IMAGE_VISIBILITY = {"gm_only", "player_safe", "spoiler", "copyright_private"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class PrivateImageIntakeService:
    """Extract, classify, review, and promote private-local campaign images."""

    def __init__(self) -> None:
        self.data = private_campaign_data_service

    def private_root(self) -> Path:
        return self.data.private_root()

    def campaign_id(self) -> str:
        return self.data.campaign_id()

    def raw_reference_root(self) -> Path:
        return self.private_root() / "reference" / "raw"

    def extracted_reference_root(self) -> Path:
        return self.private_root() / "reference" / "extracted"

    def campaigns_root(self) -> Path:
        return self.private_root() / "campaigns" / self.campaign_id()

    def list_image_runs(self) -> list[dict[str, Any]]:
        runs_by_id: dict[str, dict[str, Any]] = {}
        for path in sorted(self.extracted_reference_root().glob("*/image-intake-run.json"), reverse=True):
            run = self._read_json(path, {})
            run_id = str(run.get("run_id") or "")
            if run_id:
                runs_by_id[run_id] = run
        return sorted(
            runs_by_id.values(),
            key=lambda run: str(run.get("created_at") or run.get("run_id") or ""),
            reverse=True,
        )

    def create_image_intake_run(self, *, source_id: str | None = None) -> dict[str, Any]:
        sources = self._source_pdfs(source_id)
        if source_id and not sources:
            raise ValueError(f"No source PDF matched source_id: {source_id}")
        if not sources:
            raise ValueError(
                "No source PDFs found in private-local/reference/raw. "
                "Add campaign PDFs there before running image intake."
            )
        run_id = self._new_run_id()
        totals = {"sources": 0, "images": 0, "candidates": 0}
        source_results = []
        for source_path in sources:
            result = self._process_source(source_path, run_id)
            source_results.append(result)
            totals["sources"] += 1
            totals["images"] += int(result.get("image_count") or 0)
            totals["candidates"] += int(result.get("candidate_count") or 0)
        run = {
            "run_id": run_id,
            "campaign_id": self.campaign_id(),
            "status": "draft",
            "scope": "images",
            "created_at": self._now_iso(),
            "updated_at": time(),
            "totals": totals,
            "sources": source_results,
        }
        for result in source_results:
            self._write_json(self._source_root(result["source_id"]) / "image-intake-run.json", run)
        return run

    def image_candidates(
        self,
        *,
        source_id: str | None = None,
        review_status: str | None = None,
        category: str | None = None,
        q: str | None = None,
        limit: int = 300,
    ) -> dict[str, Any]:
        query = (q or "").strip().casefold()
        status_filter = (review_status or "").strip().casefold()
        category_filter = (category or "").strip().casefold()
        items = []
        for path in self._candidate_paths(source_id):
            payload = self._read_json(path, {"items": []})
            for item in payload.get("items") or []:
                if status_filter and str(item.get("review_status") or "").casefold() != status_filter:
                    continue
                if category_filter and str(item.get("category") or "").casefold() != category_filter:
                    continue
                if query and query not in self._candidate_search_text(item):
                    continue
                items.append(item)
        items.sort(
            key=lambda item: (
                str(item.get("source_id") or ""),
                int(item.get("page") or 0),
                str(item.get("id") or ""),
            )
        )
        return {
            "campaign_id": self.campaign_id(),
            "items": items[:limit],
            "total": len(items),
            "categories": sorted(IMAGE_CATEGORIES),
            "review_statuses": sorted(IMAGE_REVIEW_STATUSES),
        }

    def update_image_candidate(
        self,
        image_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        for path in self._candidate_paths(None):
            payload = self._read_json(path, {"items": []})
            for item in payload.get("items") or []:
                if str(item.get("id") or "") != image_id:
                    continue
                if "category" in updates:
                    category = str(updates.get("category") or "unknown").strip()
                    if category not in IMAGE_CATEGORIES:
                        raise ValueError(f"Unsupported image category: {category}")
                    item["category"] = category
                if "review_status" in updates:
                    status = str(updates.get("review_status") or "unreviewed").strip()
                    if status not in IMAGE_REVIEW_STATUSES:
                        raise ValueError(f"Unsupported image review status: {status}")
                    item["review_status"] = status
                if "visibility" in updates:
                    visibility = str(updates.get("visibility") or "gm_only").strip()
                    if visibility not in IMAGE_VISIBILITY:
                        raise ValueError(f"Unsupported image visibility: {visibility}")
                    item["visibility"] = visibility
                if "proposed_match" in updates and isinstance(updates["proposed_match"], dict):
                    item["confirmed_match"] = updates["proposed_match"]
                if "reviewer_notes" in updates:
                    item["reviewer_notes"] = str(updates.get("reviewer_notes") or "").strip()
                item["updated_at"] = time()
                self._write_json(path, payload)
                self._write_image_audit(path.parent)
                return item
        return None

    def promote_confirmed_images(self) -> dict[str, Any]:
        existing = self._read_json(
            self.campaigns_root() / "images.json",
            {"campaign_id": self.campaign_id(), "items": []},
        )
        items = existing.get("items") if isinstance(existing.get("items"), list) else []
        by_id = {str(item.get("id") or item.get("private_path") or ""): item for item in items}
        promoted = []
        for candidate in self.image_candidates(review_status="confirmed", limit=100000)["items"]:
            promoted_item = self._promoted_image(candidate)
            key = str(promoted_item.get("id") or promoted_item.get("private_path"))
            by_id[key] = promoted_item
            promoted.append(key)
        payload = {
            "campaign_id": self.campaign_id(),
            "items": sorted(by_id.values(), key=lambda item: str(item.get("name") or item.get("id") or "")),
            "updated_at": time(),
        }
        self._write_json(self.campaigns_root() / "images.json", payload)
        private_index_service.build_all()
        return {
            "promoted_count": len(promoted),
            "promoted_ids": promoted,
        }

    def image_audit(self) -> dict[str, Any]:
        issues = []
        seen_hashes: dict[str, str] = {}
        confirmed_by_entity: dict[str, list[str]] = {}
        for candidate in self.image_candidates(limit=100000)["items"]:
            image_hash = str(candidate.get("sha256") or "")
            if image_hash:
                if image_hash in seen_hashes:
                    issues.append(self._issue(candidate, "duplicate_hash", "warning", "Image duplicates another extracted candidate."))
                else:
                    seen_hashes[image_hash] = str(candidate.get("id"))
            if not candidate.get("proposed_matches") and candidate.get("review_status") in {"unreviewed", "candidate"}:
                issues.append(self._issue(candidate, "no_proposed_match", "info", "No proposed entity match is available."))
            if candidate.get("confidence") == "high" and candidate.get("review_status") not in {"confirmed", "rejected", "wrong_match", "duplicate"}:
                issues.append(self._issue(candidate, "high_confidence_unreviewed", "warning", "High-confidence image candidate still needs review."))
            if candidate.get("category") in {"decorative_noise", "ui_or_layout", "duplicate_or_variant"} and candidate.get("review_status") not in {"rejected", "duplicate", "confirmed"}:
                issues.append(self._issue(candidate, "likely_noncanonical_unreviewed", "info", "Likely decorative or duplicate image should be classified."))
            path = self.private_root() / str(candidate.get("private_path") or "")
            if candidate.get("review_status") == "confirmed" and not path.exists():
                issues.append(self._issue(candidate, "confirmed_file_missing", "error", "Confirmed image file is missing."))
            match = candidate.get("confirmed_match") or {}
            entity_key = f"{match.get('entity_type')}:{match.get('entity_id')}"
            if candidate.get("review_status") == "confirmed" and match:
                confirmed_by_entity.setdefault(entity_key, []).append(str(candidate.get("id")))
        for entity_key, image_ids in confirmed_by_entity.items():
            if len(image_ids) > 1:
                issues.append(
                    {
                        "id": f"{entity_key}:multiple_confirmed",
                        "image_id": None,
                        "code": "multiple_confirmed_for_entity",
                        "severity": "warning",
                        "message": f"{entity_key} has multiple confirmed images; mark variants deliberately.",
                    }
                )
        summary: dict[str, int] = {}
        for issue in issues:
            severity = str(issue.get("severity") or "info")
            summary[severity] = summary.get(severity, 0) + 1
        return {
            "campaign_id": self.campaign_id(),
            "summary": summary,
            "issues": issues,
            "updated_at": time(),
        }

    def _process_source(self, source_path: Path, run_id: str) -> dict[str, Any]:
        source_id = self._source_id(source_path)
        root = self._source_root(source_id)
        image_root = root / "images"
        image_root.mkdir(parents=True, exist_ok=True)
        page_layout = self._extract_page_layout(source_path)
        image_items = self._extract_images(source_path, source_id, image_root, page_layout)
        candidates = [self._candidate_from_image(item, page_layout) for item in image_items]
        manifest = {
            "source_id": source_id,
            "source_path": source_path.relative_to(self.private_root()).as_posix(),
            "sha256": self._sha256(source_path),
            "run_id": run_id,
            "image_count": len(image_items),
            "candidate_count": len(candidates),
            "updated_at": time(),
        }
        self._write_json(root / "image-manifest.json", {**manifest, "items": image_items})
        self._write_json(root / "page-layout.json", page_layout)
        self._write_json(root / "image-candidates.json", {"campaign_id": self.campaign_id(), "source_id": source_id, "items": candidates, "updated_at": time()})
        self._write_image_audit(root)
        return manifest

    def _extract_page_layout(self, source_path: Path) -> dict[str, Any]:
        pages = []
        extractor = "none"
        warnings = []
        try:
            import fitz  # type: ignore

            extractor = "pymupdf"
            document = fitz.open(str(source_path))
            for page_index, page in enumerate(document, start=1):
                blocks = []
                for block in page.get_text("blocks"):
                    if len(block) < 5:
                        continue
                    text = re.sub(r"\s+", " ", str(block[4] or "")).strip()
                    if not text:
                        continue
                    blocks.append(
                        {
                            "bbox": [float(block[0]), float(block[1]), float(block[2]), float(block[3])],
                            "text": text,
                        }
                    )
                pages.append(
                    {
                        "page": page_index,
                        "width": float(page.rect.width),
                        "height": float(page.rect.height),
                        "text": " ".join(block["text"] for block in blocks),
                        "blocks": blocks,
                    }
                )
            document.close()
        except Exception as exc:
            warnings.append(f"PyMuPDF layout extraction unavailable: {exc}")
        return {
            "source_path": source_path.relative_to(self.private_root()).as_posix(),
            "extractor": extractor,
            "pages": pages,
            "warnings": warnings,
            "updated_at": time(),
        }

    def _extract_images(
        self,
        source_path: Path,
        source_id: str,
        image_root: Path,
        page_layout: dict[str, Any],
    ) -> list[dict[str, Any]]:
        items = self._extract_images_with_pymupdf(source_path, source_id, image_root)
        if items:
            return items
        items = self._extract_images_with_pdfimages(source_path, source_id, image_root)
        if items:
            return items
        return self._render_pages_with_pymupdf(source_path, source_id, image_root, page_layout)

    def _extract_images_with_pymupdf(self, source_path: Path, source_id: str, image_root: Path) -> list[dict[str, Any]]:
        try:
            import fitz  # type: ignore
        except Exception:
            return []
        items = []
        document = fitz.open(str(source_path))
        seen_hashes: set[str] = set()
        for page_index, page in enumerate(document, start=1):
            for image_index, image in enumerate(page.get_images(full=True), start=1):
                xref = image[0]
                try:
                    extracted = document.extract_image(xref)
                except Exception:
                    continue
                data = extracted.get("image")
                if not data:
                    continue
                digest = hashlib.sha256(data).hexdigest()
                extension = str(extracted.get("ext") or "png").lower()
                if extension == "jpeg":
                    extension = "jpg"
                if digest in seen_hashes:
                    duplicate = True
                else:
                    duplicate = False
                    seen_hashes.add(digest)
                width = int(extracted.get("width") or 0)
                height = int(extracted.get("height") or 0)
                filename = f"page-{page_index:03d}-image-{image_index:03d}.{extension}"
                path = image_root / filename
                if not path.exists():
                    path.write_bytes(data)
                bboxes = []
                for rect in page.get_image_rects(xref):
                    bboxes.append([float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)])
                items.append(self._image_item(source_id, path, page_index, image_index, width, height, digest, duplicate, bboxes, "pymupdf"))
        document.close()
        return items

    def _extract_images_with_pdfimages(self, source_path: Path, source_id: str, image_root: Path) -> list[dict[str, Any]]:
        items = []
        with tempfile.TemporaryDirectory(prefix="dma-image-intake-") as temp_dir:
            prefix = Path(temp_dir) / "image"
            try:
                subprocess.run(
                    ["pdfimages", "-png", str(source_path), str(prefix)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return []
            for image_index, source_image in enumerate(sorted(Path(temp_dir).glob("image-*.png")), start=1):
                data = source_image.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                width, height = self._image_dimensions(source_image)
                filename = f"page-000-image-{image_index:03d}.png"
                path = image_root / filename
                if not path.exists():
                    shutil.copy2(source_image, path)
                items.append(self._image_item(source_id, path, 0, image_index, width, height, digest, False, [], "pdfimages"))
        return items

    def _render_pages_with_pymupdf(
        self,
        source_path: Path,
        source_id: str,
        image_root: Path,
        page_layout: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            import fitz  # type: ignore
        except Exception:
            return []
        rendered_root = image_root / "rendered-pages"
        rendered_root.mkdir(parents=True, exist_ok=True)
        items = []
        document = fitz.open(str(source_path))
        matrix = fitz.Matrix(1.35, 1.35)
        for page_index, page in enumerate(document, start=1):
            filename = f"page-{page_index:03d}-render.png"
            path = rendered_root / filename
            if not path.exists():
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                pixmap.save(str(path))
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            context = self._page_context(page_layout, page_index)
            bbox = [
                0.0,
                0.0,
                float(context.get("width") or page.rect.width),
                float(context.get("height") or page.rect.height),
            ]
            width, height = self._image_dimensions(path)
            items.append(
                self._image_item(
                    source_id,
                    path,
                    page_index,
                    0,
                    width,
                    height,
                    digest,
                    False,
                    [bbox],
                    "pymupdf_page_render",
                )
            )
        document.close()
        return items

    def _image_item(
        self,
        source_id: str,
        path: Path,
        page: int,
        image_index: int,
        width: int,
        height: int,
        digest: str,
        duplicate: bool,
        bboxes: list[list[float]],
        extractor: str,
    ) -> dict[str, Any]:
        relative = path.relative_to(self.private_root()).as_posix()
        return {
            "id": f"image:{source_id}:p{page:03d}:i{image_index:03d}",
            "source_id": source_id,
            "page": page,
            "image_number": image_index,
            "private_path": relative,
            "url": self.data.private_file_url(relative),
            "width": width,
            "height": height,
            "area": width * height,
            "aspect_ratio": round(width / height, 3) if height else None,
            "sha256": digest,
            "duplicate": duplicate,
            "bboxes": bboxes,
            "extractor": extractor,
        }

    def _candidate_from_image(self, image: dict[str, Any], page_layout: dict[str, Any]) -> dict[str, Any]:
        page = int(image.get("page") or 0)
        page_context = self._page_context(page_layout, page)
        context_window = self._page_context_window(page_layout, page)
        nearby_text = self._nearby_text(page_context, image.get("bboxes") or [])
        visual_features = self._visual_features(image, page_context)
        category = self._guess_category(image, page_context, nearby_text, visual_features)
        matches = self._proposed_matches(context_window, nearby_text, category)
        confidence = self._candidate_confidence(matches, nearby_text, image)
        return {
            **image,
            "category": category,
            "review_status": "unreviewed",
            "visibility": "copyright_private",
            "confidence": confidence,
            "allocation_status": self._allocation_status(category, matches, confidence),
            "visual_features": visual_features,
            "nearby_text": nearby_text,
            "page_text_excerpt": (page_context.get("text") or "")[:1200],
            "proposed_matches": matches,
            "reviewer_notes": "",
            "created_at": self._now_iso(),
            "updated_at": time(),
        }

    def _page_context(self, page_layout: dict[str, Any], page: int) -> dict[str, Any]:
        for item in page_layout.get("pages") or []:
            if int(item.get("page") or 0) == page:
                return item
        return {"page": page, "text": "", "blocks": []}

    def _page_context_window(self, page_layout: dict[str, Any], page: int) -> dict[str, Any]:
        current = self._page_context(page_layout, page)
        previous_page = self._page_context(page_layout, page - 1) if page > 1 else {}
        next_page = self._page_context(page_layout, page + 1)
        adjacent_text = " ".join(
            str(item.get("text") or "")
            for item in [previous_page, next_page]
            if item
        )
        return {
            "page": page,
            "current": current,
            "adjacent_text": re.sub(r"\s+", " ", adjacent_text).strip(),
        }

    def _nearby_text(self, page_context: dict[str, Any], bboxes: list[list[float]]) -> str:
        if not bboxes:
            return (page_context.get("text") or "")[:800]
        blocks = page_context.get("blocks") or []
        selected = []
        for bbox in bboxes[:2]:
            x0, y0, x1, y1 = bbox
            for block in blocks:
                bx0, by0, bx1, by1 = block.get("bbox") or [0, 0, 0, 0]
                horizontally_close = bx1 >= x0 - 80 and bx0 <= x1 + 80
                vertically_close = abs(by1 - y0) < 90 or abs(by0 - y1) < 90 or (by0 >= y0 and by1 <= y1)
                if horizontally_close and vertically_close:
                    selected.append(str(block.get("text") or ""))
        text = " ".join(dict.fromkeys(text for text in selected if text))
        return re.sub(r"\s+", " ", text).strip()[:1200]

    def _visual_features(self, image: dict[str, Any], page_context: dict[str, Any]) -> dict[str, Any]:
        width = int(image.get("width") or 0)
        height = int(image.get("height") or 0)
        area = width * height
        aspect = width / height if height else 0
        page_width = float(page_context.get("width") or 0)
        page_height = float(page_context.get("height") or 0)
        bbox_coverage = 0.0
        for bbox in image.get("bboxes") or []:
            if len(bbox) != 4 or not page_width or not page_height:
                continue
            x0, y0, x1, y1 = bbox
            bbox_area = max(0.0, float(x1) - float(x0)) * max(0.0, float(y1) - float(y0))
            bbox_coverage = max(bbox_coverage, bbox_area / (page_width * page_height))
        flags = []
        if image.get("duplicate"):
            flags.append("duplicate_hash")
        if image.get("extractor") == "pymupdf_page_render":
            flags.append("rendered_page")
        if area < 20_000 or width < 80 or height < 80:
            flags.append("tiny_or_low_signal")
        if 0.45 <= aspect <= 1.35 and area > 35_000:
            flags.append("portrait_aspect")
        if aspect > 1.6 and area > 80_000:
            flags.append("wide_illustration")
        if bbox_coverage >= 0.6:
            flags.append("large_page_coverage")
        if not int(image.get("page") or 0):
            flags.append("page_unknown")
        return {
            "pixel_area": area,
            "aspect_ratio": round(aspect, 3) if height else None,
            "bbox_page_coverage": round(bbox_coverage, 3),
            "flags": flags,
        }

    def _guess_category(
        self,
        image: dict[str, Any],
        page_context: dict[str, Any],
        nearby_text: str,
        visual_features: dict[str, Any],
    ) -> str:
        area = int(visual_features.get("pixel_area") or 0)
        aspect = float(visual_features.get("aspect_ratio") or 0)
        text = f"{nearby_text} {page_context.get('text') or ''}".casefold()
        is_rendered_page = "rendered_page" in visual_features.get("flags", [])
        if image.get("duplicate"):
            return "duplicate_or_variant"
        if "tiny_or_low_signal" in visual_features.get("flags", []):
            return "decorative_noise"
        if "large_page_coverage" in visual_features.get("flags", []) and any(
            marker in text for marker in ["chapter", "part ", "adventure toolbox", "cover"]
        ):
            return "cover_or_chapter_art"
        if "map" in text and area > 80_000:
            return "map"
        if is_rendered_page:
            return "handout_candidate"
        if any(marker in text for marker in ["creature", "hazard", "initiative", "ac ", "hp "]):
            return "portrait_creature"
        if any(marker in text for marker in ["npc", "mayor", "captain", "owner", "leader"]):
            return "portrait_npc"
        if any(marker in text for marker in ["amulet", "wand", "potion", "weapon", "key", "item"]):
            return "item_illustration"
        if 0.45 <= aspect <= 1.35 and area > 35_000:
            return "portrait_npc"
        if aspect > 1.6 and area > 80_000:
            return "scene_illustration"
        return "unknown"

    def _proposed_matches(self, context_window: dict[str, Any], nearby_text: str, category: str) -> list[dict[str, Any]]:
        current_text = str((context_window.get("current") or {}).get("text") or "")
        adjacent_text = str(context_window.get("adjacent_text") or "")
        text = f"{nearby_text} {current_text} {adjacent_text}"
        entities = private_index_service._read_json(private_index_service.indexes_root() / "entity-catalog.json", {"items": []}).get("items") or []
        matches = []
        for entity in entities:
            name = str(entity.get("name") or "").strip()
            if not name or len(name) < 3:
                continue
            score, evidence = self._name_score(name, current_text, nearby_text, adjacent_text)
            if score <= 0:
                continue
            matches.append(
                {
                    "entity_type": entity.get("entity_type"),
                    "entity_id": entity.get("id"),
                    "entity_name": name,
                    "confidence": "high" if score >= 4 else "medium" if score >= 2 else "low",
                    "score": score,
                    "evidence": evidence,
                }
            )
        matches.sort(
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(item["confidence"], 3),
                -int(item.get("score") or 0),
                str(item.get("entity_name") or ""),
            )
        )
        return matches[:8]

    def _name_score(
        self,
        name: str,
        current_text: str,
        nearby_text: str,
        adjacent_text: str,
    ) -> tuple[int, list[str]]:
        normalized_name = re.escape(name.casefold())
        if re.search(rf"\b{normalized_name}\b", nearby_text.casefold()):
            return 5, ["nearby_caption_or_label_text"]
        if re.search(rf"\b{normalized_name}\b", current_text.casefold()):
            return 4, ["same_page_text_match"]
        if re.search(rf"\b{normalized_name}\b", adjacent_text.casefold()):
            return 2, ["adjacent_page_text_match"]
        parts = [part for part in re.split(r"\s+", name) if len(part) >= 4]
        if parts and any(re.search(rf"\b{re.escape(part.casefold())}\b", nearby_text.casefold()) for part in parts):
            return 2, ["partial_name_nearby_text_match"]
        if parts and any(re.search(rf"\b{re.escape(part.casefold())}\b", current_text.casefold()) for part in parts):
            return 1, ["partial_name_same_page_text_match"]
        return 0, []

    def _candidate_confidence(self, matches: list[dict[str, Any]], nearby_text: str, image: dict[str, Any]) -> str:
        if matches and matches[0].get("confidence") == "high":
            return "high"
        if matches:
            return "medium"
        if image.get("duplicate") or not nearby_text:
            return "low"
        return "low"

    def _allocation_status(self, category: str, matches: list[dict[str, Any]], confidence: str) -> str:
        if category in {"decorative_noise", "ui_or_layout"}:
            return "ignore_candidate"
        if category in {"duplicate_or_variant"}:
            return "duplicate_review"
        if matches and confidence in {"high", "medium"}:
            return "ready_for_review"
        if matches:
            return "weak_match_review"
        return "needs_identification"

    def _promoted_image(self, candidate: dict[str, Any]) -> dict[str, Any]:
        match = candidate.get("confirmed_match") or (candidate.get("proposed_matches") or [{}])[0]
        return {
            "id": candidate.get("id"),
            "name": match.get("entity_name") or Path(str(candidate.get("private_path") or "")).stem,
            "private_path": candidate.get("private_path"),
            "url": candidate.get("url"),
            "category": candidate.get("category"),
            "status": "confirmed",
            "visibility": candidate.get("visibility") or "copyright_private",
            "source_id": candidate.get("source_id"),
            "source_page": candidate.get("page"),
            "image_source": "campaign PDF extraction",
            "image_match_basis": ", ".join(match.get("evidence") or []),
            "image_confidence": candidate.get("confidence"),
            "entity_type": match.get("entity_type"),
            "entity_id": match.get("entity_id"),
            "entity_name": match.get("entity_name"),
            "reviewer_notes": candidate.get("reviewer_notes") or "",
            "updated_at": time(),
        }

    def _write_image_audit(self, source_root: Path) -> None:
        payload = self._read_json(source_root / "image-candidates.json", {"items": []})
        issues = []
        seen: dict[str, str] = {}
        for item in payload.get("items") or []:
            if item.get("sha256") in seen:
                issues.append(self._issue(item, "duplicate_hash", "warning", "Duplicate extracted image hash."))
            elif item.get("sha256"):
                seen[str(item["sha256"])] = str(item.get("id"))
            if not item.get("proposed_matches"):
                issues.append(self._issue(item, "no_proposed_match", "info", "No proposed entity match."))
        self._write_json(source_root / "image-match-audit.json", {"campaign_id": self.campaign_id(), "issues": issues, "updated_at": time()})

    def _issue(self, candidate: dict[str, Any], code: str, severity: str, message: str) -> dict[str, Any]:
        return {
            "id": f"{candidate.get('id')}:{code}",
            "image_id": candidate.get("id"),
            "code": code,
            "severity": severity,
            "message": message,
        }

    def _source_pdfs(self, source_id: str | None) -> list[Path]:
        paths = sorted(self.raw_reference_root().rglob("*.pdf"))
        if source_id:
            return [path for path in paths if self._source_id(path) == source_id]
        return paths

    def _candidate_paths(self, source_id: str | None) -> list[Path]:
        root = self.extracted_reference_root()
        if source_id:
            return [root / source_id / "image-candidates.json"]
        return sorted(root.glob("*/image-candidates.json"))

    def _source_root(self, source_id: str) -> Path:
        return self.extracted_reference_root() / source_id

    def _candidate_search_text(self, item: dict[str, Any]) -> str:
        return json.dumps(
            [
                item.get("id"),
                item.get("source_id"),
                item.get("category"),
                item.get("review_status"),
                item.get("nearby_text"),
                item.get("page_text_excerpt"),
                item.get("proposed_matches"),
            ],
            ensure_ascii=False,
            default=str,
        ).casefold()

    def _image_dimensions(self, path: Path) -> tuple[int, int]:
        try:
            from PIL import Image

            with Image.open(path) as image:
                return int(image.width), int(image.height)
        except Exception:
            return 0, 0

    def _source_id(self, path: Path) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", path.stem.casefold()).strip("-")
        return slug or hashlib.sha1(str(path).encode()).hexdigest()[:12]

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_run_id(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return dict(default)
        return payload if isinstance(payload, dict) else dict(default)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)


private_image_intake_service = PrivateImageIntakeService()
