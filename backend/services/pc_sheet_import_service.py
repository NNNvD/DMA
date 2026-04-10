from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_service import campaign_service
from backend.services.ingestion_service import ingestion_service


@dataclass
class ParsedPCSheet:
    name: str
    source_format: str = "text"
    stable_key: Optional[str] = None
    summary: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    entity_details: dict[str, Any] = field(default_factory=dict)
    sheet_payload: dict[str, Any] = field(default_factory=dict)
    current_location_reference: Optional[str] = None
    faction_references: list[str] = field(default_factory=list)
    relationship_specs: list[tuple[str, str, Optional[str]]] = field(
        default_factory=list
    )
    notable_items: list[str] = field(default_factory=list)
    notable_item_details: dict[str, dict[str, Any]] = field(default_factory=dict)


PATHBUILDER_SKILL_KEYS = {
    "acrobatics",
    "arcana",
    "athletics",
    "computers",
    "crafting",
    "deception",
    "diplomacy",
    "intimidation",
    "medicine",
    "nature",
    "occultism",
    "performance",
    "piloting",
    "religion",
    "society",
    "stealth",
    "survival",
    "thievery",
}


class PCSheetImportService:
    async def import_sheet(
        self,
        db: AsyncSession,
        *,
        title: str,
        content: str,
        source_name: Optional[str] = None,
        document_url: Optional[str] = None,
        default_tags: Optional[list[str]] = None,
        store_document: bool = True,
    ) -> dict[str, Any]:
        parsed = self.parse_content(content, default_tags=default_tags)

        stored_document = None
        if store_document:
            stored_document = await ingestion_service.ingest_document(
                db,
                title=title,
                kind="pc_sheet",
                content=content,
                summary=self._document_summary(parsed),
                source_name=source_name,
                url=document_url,
                dedupe_on_url=bool(document_url),
            )

        warnings: list[str] = []
        location_id = None
        if parsed.current_location_reference:
            location = await self._ensure_reference_entity(
                db,
                parsed.current_location_reference,
                entity_type="location",
            )
            location_id = location.id

        pc_entity, pc_created = await campaign_service.upsert_entity(
            db,
            entity_type="pc",
            name=parsed.name,
            stable_key=parsed.stable_key,
            summary=parsed.summary,
            details=parsed.entity_details,
            tags=parsed.tags,
            current_location_id=location_id,
        )
        sheet_source_name = source_name or title
        latest_sheet_version = (
            pc_entity.sheet_versions[-1] if pc_entity.sheet_versions else None
        )
        if (
            latest_sheet_version is not None
            and latest_sheet_version.source_name == sheet_source_name
            and latest_sheet_version.payload == parsed.sheet_payload
        ):
            sheet_version = latest_sheet_version
            created_sheet_version = False
        else:
            sheet_version = await campaign_service.add_sheet_version(
                pc_entity.id,
                db,
                payload=parsed.sheet_payload,
                source_name=sheet_source_name,
            )
            created_sheet_version = True

        created_relationships = 0
        updated_relationships = 0
        for faction_name in parsed.faction_references:
            faction = await self._ensure_reference_entity(
                db, faction_name, entity_type="faction"
            )
            _, created = await campaign_service.ensure_relationship(
                db,
                source_entity_id=pc_entity.id,
                target_entity_id=faction.id,
                relationship_type="member",
            )
            if created:
                created_relationships += 1
            else:
                updated_relationships += 1

        for relationship_type, target_reference, notes in parsed.relationship_specs:
            target = await campaign_service.find_entity_by_reference(
                db, target_reference
            )
            if target is None:
                warnings.append(
                    f"Could not resolve relationship target '{target_reference}' for {parsed.name}."
                )
                continue
            _, created = await campaign_service.ensure_relationship(
                db,
                source_entity_id=pc_entity.id,
                target_entity_id=target.id,
                relationship_type=relationship_type,
                notes=notes,
            )
            if created:
                created_relationships += 1
            else:
                updated_relationships += 1

        created_artifacts = 0
        updated_artifacts = 0
        for item_name in parsed.notable_items:
            artifact, created = await campaign_service.upsert_entity(
                db,
                entity_type="artifact",
                name=item_name,
                details=parsed.notable_item_details.get(
                    item_name, {"artifact_type": "notable item"}
                ),
                owner_entity_id=pc_entity.id,
                current_location_id=location_id,
            )
            if created:
                created_artifacts += 1
            else:
                updated_artifacts += 1
            if artifact.owner_entity_id != pc_entity.id or (
                location_id is not None and artifact.current_location_id != location_id
            ):
                await campaign_service.update_entity(
                    artifact.id,
                    db,
                    owner_entity_id=pc_entity.id,
                    current_location_id=location_id,
                )

        reloaded_pc = await campaign_service.get_entity(pc_entity.id, db)
        if reloaded_pc is None:
            raise LookupError("PC entity could not be reloaded after import")

        return {
            "document": (
                {
                    "id": stored_document.id,
                    "title": stored_document.title,
                    "kind": stored_document.kind,
                    "source_name": stored_document.source_name,
                }
                if stored_document is not None
                else None
            ),
            "summary": {
                "created_pc": pc_created,
                "created_pcs": 1 if pc_created else 0,
                "updated_pcs": 0 if pc_created else 1,
                "created_entities": 1 if pc_created else 0,
                "updated_entities": 0 if pc_created else 1,
                "created_relationships": created_relationships,
                "updated_relationships": updated_relationships,
                "created_artifacts": created_artifacts,
                "updated_artifacts": updated_artifacts,
                "created_sheet_versions": 1 if created_sheet_version else 0,
                "reused_sheet_versions": 0 if created_sheet_version else 1,
            },
            "import_format": parsed.source_format,
            "pc": campaign_service.entity_to_dict(
                reloaded_pc,
                include_relationships=True,
                include_sheet_versions=True,
            ),
            "sheet_version": campaign_service.sheet_version_to_dict(sheet_version),
            "warnings": warnings,
        }

    def parse_content(
        self, content: str, *, default_tags: Optional[list[str]] = None
    ) -> ParsedPCSheet:
        pathbuilder_payload = self._parse_json(content)
        if self._looks_like_pathbuilder_export(pathbuilder_payload):
            assert pathbuilder_payload is not None
            return self._parse_pathbuilder_export(
                pathbuilder_payload, default_tags=default_tags
            )

        raw_fields = self._parse_key_values(content)
        name = raw_fields.get("name")
        if not name:
            raise ValueError("PC sheet import requires a 'Name:' field")

        role = (
            raw_fields.get("role")
            or raw_fields.get("class")
            or raw_fields.get("class name")
        )
        entity_details = {
            key: value
            for key, value in {
                "role": role.lower() if role else None,
                "pronouns": raw_fields.get("pronouns"),
                "status": raw_fields.get("status"),
                "languages": self._split_items(raw_fields.get("languages")),
                "scripts": self._split_items(raw_fields.get("scripts")),
                "goals": self._split_items(raw_fields.get("goals")),
                "hooks": self._split_items(raw_fields.get("hooks")),
            }.items()
            if value
        }

        items = self._split_items(raw_fields.get("items"))
        notable_items = self._split_items(
            raw_fields.get("notable items") or raw_fields.get("artifacts")
        )
        sheet_payload = {
            "ancestry": raw_fields.get("ancestry"),
            "background": raw_fields.get("background"),
            "class_name": raw_fields.get("class") or raw_fields.get("class name"),
            "subclass": raw_fields.get("subclass"),
            "level": self._parse_int(raw_fields.get("level"), default=1),
            "languages": self._split_items(raw_fields.get("languages")),
            "scripts": self._split_items(raw_fields.get("scripts")),
            "goals": self._split_items(raw_fields.get("goals")),
            "hooks": self._split_items(raw_fields.get("hooks")),
            "attributes": self._parse_mapping(raw_fields.get("attributes")),
            "skills": self._split_items(raw_fields.get("skills")),
            "spells": self._split_items(raw_fields.get("spells")),
            "items": [*items, *[item for item in notable_items if item not in items]],
            "notes": raw_fields.get("notes"),
        }

        return ParsedPCSheet(
            name=name,
            stable_key=raw_fields.get("stable key") or raw_fields.get("stable_key"),
            summary=raw_fields.get("summary"),
            tags=campaign_service._normalize_strings(
                [*(default_tags or []), *self._split_items(raw_fields.get("tags"))]
            ),
            entity_details=entity_details,
            sheet_payload={
                k: v for k, v in sheet_payload.items() if v not in (None, [])
            },
            current_location_reference=raw_fields.get("location"),
            faction_references=self._split_items(raw_fields.get("factions")),
            relationship_specs=self._parse_relationships(
                raw_fields.get("relationships")
            ),
            notable_items=notable_items,
        )

    def _parse_pathbuilder_export(
        self,
        payload: dict[str, Any],
        *,
        default_tags: Optional[list[str]] = None,
    ) -> ParsedPCSheet:
        build = payload["build"]
        languages = self._clean_pathbuilder_list(build.get("languages"))
        feats = self._pathbuilder_feat_names(build.get("feats"))
        lores = self._pathbuilder_lores(build.get("lores"))
        weapons = self._pathbuilder_weapons(build.get("weapons"))
        armor = self._pathbuilder_armor(build.get("armor"))
        equipment = self._pathbuilder_equipment(
            build.get("equipment"),
            build.get("equipmentContainers"),
        )
        items = [*weapons, *armor, *equipment]
        notable_item_records = self._pathbuilder_notable_items(weapons, armor)
        abilities = self._pathbuilder_abilities(build.get("abilities"))
        proficiencies = self._pathbuilder_proficiencies(build.get("proficiencies"))
        size_name = self._clean_pathbuilder_value(build.get("sizeName"))
        ancestry = self._clean_pathbuilder_value(build.get("ancestry"))
        heritage = self._clean_pathbuilder_value(build.get("heritage"))
        class_name = self._clean_pathbuilder_value(build.get("class"))
        background = self._clean_pathbuilder_value(build.get("background"))
        level = self._pathbuilder_int(build.get("level"), default=1)

        summary_parts = [f"Level {level}"]
        if ancestry:
            summary_parts.append(ancestry)
        if class_name:
            summary_parts.append(class_name)
        if heritage:
            summary_parts.append(f"({heritage})")

        entity_details = {
            key: value
            for key, value in {
                "role": class_name.lower() if class_name else None,
                "languages": languages,
                "heritage": heritage,
                "background": background,
                "alignment": self._clean_pathbuilder_value(build.get("alignment")),
                "deity": self._clean_pathbuilder_value(build.get("deity")),
                "size_name": size_name,
                "keyability": self._clean_pathbuilder_value(build.get("keyability")),
                "specials": self._clean_pathbuilder_list(build.get("specials")),
            }.items()
            if value not in (None, [])
        }

        sheet_payload = {
            "source_system": "pathbuilder2",
            "export_success": bool(payload.get("success")),
            "pathbuilder_build_name": self._clean_pathbuilder_value(build.get("name")),
            "class_name": class_name,
            "dual_class": self._clean_pathbuilder_value(build.get("dualClass")),
            "level": level,
            "xp": self._pathbuilder_int(build.get("xp"), default=0),
            "ancestry": ancestry,
            "heritage": heritage,
            "background": background,
            "alignment": self._clean_pathbuilder_value(build.get("alignment")),
            "gender": self._clean_pathbuilder_value(build.get("gender")),
            "age": self._clean_pathbuilder_value(build.get("age")),
            "deity": self._clean_pathbuilder_value(build.get("deity")),
            "size": {
                "value": self._pathbuilder_int(build.get("size"), default=0),
                "name": size_name,
            },
            "keyability": self._clean_pathbuilder_value(build.get("keyability")),
            "languages": languages,
            "attributes": abilities,
            "ability_breakdown": (
                build.get("abilities", {}).get("breakdown", {})
                if isinstance(build.get("abilities"), dict)
                else {}
            ),
            "vitals": {
                "ancestry_hp": self._pathbuilder_int(
                    build.get("attributes", {}).get("ancestryhp"),
                    default=0,
                ),
                "class_hp": self._pathbuilder_int(
                    build.get("attributes", {}).get("classhp"),
                    default=0,
                ),
                "bonus_hp": self._pathbuilder_int(
                    build.get("attributes", {}).get("bonushp"),
                    default=0,
                ),
                "bonus_hp_per_level": self._pathbuilder_int(
                    build.get("attributes", {}).get("bonushpPerLevel"),
                    default=0,
                ),
                "speed": self._pathbuilder_int(
                    build.get("attributes", {}).get("speed"),
                    default=0,
                ),
                "speed_bonus": self._pathbuilder_int(
                    build.get("attributes", {}).get("speedBonus"),
                    default=0,
                ),
            },
            "proficiencies": proficiencies,
            "skills": sorted(
                [
                    skill_name.title()
                    for skill_name, rank in proficiencies.items()
                    if skill_name in PATHBUILDER_SKILL_KEYS and rank > 0
                ]
            ),
            "feats": feats,
            "specials": self._clean_pathbuilder_list(build.get("specials")),
            "lores": lores,
            "items": items,
            "weapons": weapons,
            "armor": armor,
            "money": build.get("money", {}),
            "ac": self._pathbuilder_ac(build.get("acTotal")),
            "resistances": build.get("resistances", []),
            "spellcasters": build.get("spellCasters", []),
            "rituals": build.get("rituals", []),
            "focus_points": self._pathbuilder_int(build.get("focusPoints"), default=0),
        }

        return ParsedPCSheet(
            name=build["name"],
            source_format="pathbuilder2_json",
            summary=" ".join(part for part in summary_parts if part),
            tags=campaign_service._normalize_strings(
                [*(default_tags or []), "pathbuilder2", "pf2e"]
            ),
            entity_details=entity_details,
            sheet_payload=sheet_payload,
            notable_items=list(notable_item_records),
            notable_item_details=notable_item_records,
        )

    def _parse_key_values(self, content: str) -> dict[str, str]:
        raw_fields: dict[str, str] = {}
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                stripped = stripped[2:].strip()
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            normalized_key = key.strip().lower()
            existing = raw_fields.get(normalized_key)
            raw_fields[normalized_key] = (
                f"{existing}; {value.strip()}" if existing else value.strip()
            )
        return raw_fields

    def _split_items(self, value: Optional[str]) -> list[str]:
        if not value:
            return []
        return campaign_service._normalize_strings(re.split(r"\s*[;,]\s*", value))

    def _parse_mapping(self, value: Optional[str]) -> dict[str, int]:
        if not value:
            return {}
        parsed: dict[str, int] = {}
        for chunk in re.split(r"\s*[;,]\s*", value):
            if not chunk:
                continue
            if "=" in chunk:
                key, raw_value = chunk.split("=", 1)
            elif ":" in chunk:
                key, raw_value = chunk.split(":", 1)
            else:
                continue
            normalized_key = key.strip().lower()
            if raw_value.strip().isdigit():
                parsed[normalized_key] = int(raw_value.strip())
        return parsed

    def _parse_relationships(
        self, value: Optional[str]
    ) -> list[tuple[str, str, Optional[str]]]:
        if not value:
            return []
        relationships: list[tuple[str, str, Optional[str]]] = []
        for chunk in re.split(r"\s*;\s*", value):
            if not chunk:
                continue
            parts = [part.strip() for part in chunk.split("->", 2)]
            if len(parts) >= 2 and parts[0] and parts[1]:
                relationships.append(
                    (
                        parts[0],
                        parts[1],
                        parts[2] if len(parts) == 3 and parts[2] else None,
                    )
                )
        return relationships

    def _parse_int(self, value: Optional[str], *, default: int) -> int:
        if value and value.strip().isdigit():
            return int(value.strip())
        return default

    def _parse_json(self, content: str) -> Optional[dict[str, Any]]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _looks_like_pathbuilder_export(self, payload: Optional[dict[str, Any]]) -> bool:
        if not isinstance(payload, dict):
            return False
        build = payload.get("build")
        return (
            isinstance(build, dict)
            and isinstance(build.get("name"), str)
            and isinstance(build.get("class"), str)
            and build.get("level") is not None
        )

    def _clean_pathbuilder_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.casefold() in {"not set", "none selected", "null"}:
            return None
        return text

    def _clean_pathbuilder_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            normalized = self._clean_pathbuilder_value(item)
            if normalized:
                cleaned.append(normalized)
        return campaign_service._normalize_strings(cleaned)

    def _pathbuilder_int(self, value: Any, *, default: int) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return default

    def _pathbuilder_abilities(self, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        return {
            key: numeric_value
            for key, raw_value in value.items()
            if key != "breakdown"
            for numeric_value in [self._pathbuilder_int(raw_value, default=-1)]
            if numeric_value >= 0
        }

    def _pathbuilder_proficiencies(self, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): self._pathbuilder_int(raw_value, default=0)
            for key, raw_value in value.items()
        }

    def _pathbuilder_feat_names(self, feats: Any) -> list[str]:
        if not isinstance(feats, list):
            return []
        names: list[str] = []
        for feat in feats:
            if isinstance(feat, list) and feat:
                feat_name = self._clean_pathbuilder_value(feat[0])
                if feat_name:
                    names.append(feat_name)
            elif isinstance(feat, dict):
                feat_name = self._clean_pathbuilder_value(feat.get("name"))
                if feat_name:
                    names.append(feat_name)
        return campaign_service._normalize_strings(names)

    def _pathbuilder_lores(self, lores: Any) -> list[dict[str, Any]]:
        if not isinstance(lores, list):
            return []
        parsed: list[dict[str, Any]] = []
        for lore in lores:
            if isinstance(lore, list) and lore:
                name = self._clean_pathbuilder_value(lore[0])
                if name:
                    parsed.append(
                        {
                            "name": name,
                            "proficiency": self._pathbuilder_int(
                                lore[1] if len(lore) > 1 else None,
                                default=0,
                            ),
                        }
                    )
        return parsed

    def _pathbuilder_equipment(
        self,
        equipment: Any,
        containers: Any,
    ) -> list[dict[str, Any]]:
        container_names = {}
        if isinstance(containers, dict):
            for container_id, container in containers.items():
                if isinstance(container, dict):
                    container_name = self._clean_pathbuilder_value(
                        container.get("containerName")
                    )
                    if container_name:
                        container_names[container_id] = container_name

        parsed: list[dict[str, Any]] = []
        if not isinstance(equipment, list):
            return parsed
        for entry in equipment:
            if not isinstance(entry, list) or not entry:
                continue
            name = self._clean_pathbuilder_value(entry[0])
            if not name:
                continue
            parsed.append(
                {
                    "kind": "equipment",
                    "name": name,
                    "qty": self._pathbuilder_int(
                        entry[1] if len(entry) > 1 else None,
                        default=1,
                    ),
                    "container": (
                        container_names.get(entry[2])
                        if len(entry) > 2 and isinstance(entry[2], str)
                        else None
                    ),
                    "state": self._clean_pathbuilder_value(entry[-1]),
                }
            )
        return parsed

    def _pathbuilder_weapons(self, weapons: Any) -> list[dict[str, Any]]:
        if not isinstance(weapons, list):
            return []
        parsed: list[dict[str, Any]] = []
        for weapon in weapons:
            if not isinstance(weapon, dict):
                continue
            name = self._clean_pathbuilder_value(
                weapon.get("display") or weapon.get("name")
            )
            if not name:
                continue
            parsed.append(
                {
                    "kind": "weapon",
                    "name": name,
                    "qty": self._pathbuilder_int(weapon.get("qty"), default=1),
                    "prof": self._clean_pathbuilder_value(weapon.get("prof")),
                    "die": self._clean_pathbuilder_value(weapon.get("die")),
                    "damage_type": self._clean_pathbuilder_value(
                        weapon.get("damageType")
                    ),
                    "attack": self._pathbuilder_int(weapon.get("attack"), default=0),
                    "damage_bonus": self._pathbuilder_int(
                        weapon.get("damageBonus"), default=0
                    ),
                    "runes": weapon.get("runes", []),
                    "grade": self._clean_pathbuilder_value(weapon.get("grade")),
                }
            )
        return parsed

    def _pathbuilder_armor(self, armor: Any) -> list[dict[str, Any]]:
        if not isinstance(armor, list):
            return []
        parsed: list[dict[str, Any]] = []
        for piece in armor:
            if not isinstance(piece, dict):
                continue
            name = self._clean_pathbuilder_value(
                piece.get("display") or piece.get("name")
            )
            if not name:
                continue
            parsed.append(
                {
                    "kind": "armor",
                    "name": name,
                    "qty": self._pathbuilder_int(piece.get("qty"), default=1),
                    "prof": self._clean_pathbuilder_value(piece.get("prof")),
                    "worn": bool(piece.get("worn")),
                    "runes": piece.get("runes", []),
                    "grade": self._clean_pathbuilder_value(piece.get("grade")),
                }
            )
        return parsed

    def _pathbuilder_notable_items(
        self,
        weapons: list[dict[str, Any]],
        armor: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        notable: dict[str, dict[str, Any]] = {}
        for weapon in weapons:
            name = weapon["name"]
            notable[name] = {"artifact_type": "weapon", "properties": []}
            if weapon.get("runes"):
                notable[name]["properties"] = [str(rune) for rune in weapon["runes"]]
        for piece in armor:
            if not piece.get("worn"):
                continue
            name = piece["name"]
            kind = "shield" if piece.get("prof") == "shield" else "armor"
            notable[name] = {"artifact_type": kind, "properties": []}
            if piece.get("runes"):
                notable[name]["properties"] = [str(rune) for rune in piece["runes"]]
        return notable

    def _pathbuilder_ac(self, ac_total: Any) -> dict[str, Any]:
        if not isinstance(ac_total, dict):
            return {}
        normalized = dict(ac_total)
        shield_bonus = normalized.get("shieldBonus")
        if isinstance(shield_bonus, str) and shield_bonus.isdigit():
            normalized["shieldBonus"] = int(shield_bonus)
        return normalized

    async def _ensure_reference_entity(
        self,
        db: AsyncSession,
        reference: str,
        *,
        entity_type: str,
    ):
        existing = await campaign_service.find_entity_by_reference(
            db, reference, entity_types=[entity_type]
        )
        if existing is not None:
            return existing
        entity, _ = await campaign_service.upsert_entity(
            db, entity_type=entity_type, name=reference
        )
        return entity

    def _document_summary(self, parsed: ParsedPCSheet) -> str:
        prefix = (
            "Imported Pathbuilder 2 sheet"
            if parsed.source_format == "pathbuilder2_json"
            else "Imported PC sheet"
        )
        return f"{prefix} for {parsed.name} at level {parsed.sheet_payload.get('level', 1)}."


pc_sheet_import_service = PCSheetImportService()
