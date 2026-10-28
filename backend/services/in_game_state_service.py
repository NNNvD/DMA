"""Session-local calendar and descriptive environment; never campaign canon writes."""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GameStateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    location_name: str = Field(default="", max_length=200)
    map_id: str = Field(default="", max_length=200)
    location_type: Literal["outdoors", "indoors", "underground"] = "outdoors"
    climate: Literal["temperate", "cold", "arid", "tropical"] = "temperate"
    calendar_id: int | None = Field(default=None, ge=1)
    calendar_name: str = Field(default="", max_length=100)
    year: int | None = Field(default=None, ge=0, le=9999999)
    month: str = Field(default="", max_length=80)
    day: int | None = Field(default=None, ge=1, le=400)
    weekday: str = Field(default="", max_length=80)
    season: Literal["auto", "spring", "summer", "autumn", "winter"] = "auto"
    time_of_day: Literal[
        "unspecified", "dawn", "morning", "afternoon", "evening", "night"
    ] = "unspecified"
    weather_mode: Literal["auto", "manual"] = "auto"
    weather_text: str = Field(default="", max_length=1000)
    effects_mode: Literal["auto", "manual"] = "auto"
    effects_text: str = Field(default="", max_length=2000)
    weather_seed: int = Field(default=0, ge=0, le=2147483647)


class InGameStateService:
    def resolve(
        self,
        value: dict[str, Any] | None,
        calendars: list[dict[str, Any]],
        location: dict[str, Any] | None = None,
        *,
        strict: bool = True,
    ) -> dict[str, Any]:
        inputs = GameStateInput.model_validate(value or {}).model_dump()
        warnings = []
        if (
            inputs["calendar_id"] is not None
            and not any(item["id"] == inputs["calendar_id"] for item in calendars)
            and not strict
        ):
            # A removed calendar must not make the combat/workspace unreadable.
            inputs["calendar_id"] = None
            inputs["calendar_name"] = inputs["calendar_name"] or "Unavailable calendar"
            warnings.append(
                "Linked calendar is unavailable; select a calendar or keep a manual date."
            )
        calendar = self._calendar(inputs, calendars)
        details = (calendar or {}).get("details") or {}
        date = details.get("current_date") or {}
        if not any(inputs[key] not in (None, "") for key in ("year", "month", "day")):
            for key in ("year", "month", "day"):
                if date.get(key) not in (None, ""):
                    inputs[key] = date[key]
        if calendar and not inputs["calendar_name"]:
            inputs["calendar_name"] = calendar["name"]
            inputs["calendar_id"] = calendar["id"]
        if not inputs["location_name"] and location:
            inputs["location_name"] = location["name"]
            context = location.get("details") or {}
            if context.get("location_type") in ("outdoors", "indoors", "underground"):
                inputs["location_type"] = context["location_type"]
            if context.get("climate") in ("temperate", "cold", "arid", "tropical"):
                inputs["climate"] = context["climate"]
        # Validate inherited campaign values as well as operator inputs.
        inputs = GameStateInput.model_validate(inputs).model_dump()
        months = details.get("months") or []
        month = next(
            (
                item
                for item in months
                if isinstance(item, dict)
                and str(item.get("name", "")).casefold() == inputs["month"].casefold()
            ),
            {},
        )
        length = month.get("days")
        if isinstance(length, int) and inputs["day"] and inputs["day"] > length:
            message = f"{inputs['month']} has {length} days in this calendar"
            if strict:
                raise ValueError(message)
            warnings.append(message + "; reconcile the saved date.")
        season = inputs["season"]
        if season == "auto":
            season = month.get("season", "unspecified")
            if season not in ("spring", "summer", "autumn", "winter"):
                season = "unspecified"
        weekday = inputs["weekday"] or (
            self._weekday(inputs, details) if not warnings else ""
        )
        day_parts = [
            weekday,
            str(inputs["day"]) if inputs["day"] else "",
            inputs["month"],
            str(inputs["year"]) if inputs["year"] is not None else "",
        ]
        generation_context = {
            key: inputs[key]
            for key in (
                "location_name",
                "location_type",
                "climate",
                "calendar_name",
                "year",
                "month",
                "day",
                "time_of_day",
                "weather_seed",
            )
        }
        generation_context["season"] = season
        key = hashlib.sha256(
            json.dumps(generation_context, sort_keys=True).encode()
        ).hexdigest()
        weather = self._weather(inputs, season, random.Random(key))
        effects = self._effects(inputs, weather)
        return {
            **inputs,
            "inputs": inputs,
            "warnings": warnings,
            "weekday": weekday,
            "resolved_season": season,
            "day_label": " ".join(part for part in day_parts if part) or "Not set",
            "weather": weather,
            "environmental_effects": effects,
            "generation_key": key,
            "generation_basis": f"{inputs['climate'].capitalize()} climate · {season.replace('unspecified', 'season not set')} · {inputs['time_of_day'].replace('unspecified', 'time not set')}",
        }

    def _calendar(self, inputs, calendars):
        if inputs["calendar_id"] is not None:
            selected = next(
                (item for item in calendars if item["id"] == inputs["calendar_id"]),
                None,
            )
            if selected is None:
                raise ValueError("Selected campaign calendar was not found")
            return selected
        if inputs["calendar_name"]:
            return next(
                (
                    item
                    for item in calendars
                    if item["name"].casefold() == inputs["calendar_name"].casefold()
                ),
                None,
            )
        return next(
            iter(
                sorted(
                    calendars,
                    key=lambda item: item.get("updated_at") or "",
                    reverse=True,
                )
            ),
            None,
        )

    def _weekday(self, inputs, details):
        anchor = details.get("weekday_anchor") or details.get("current_date") or {}
        weekdays = details.get("weekdays") or []
        months = details.get("months") or []
        if all(inputs[key] == anchor.get(key) for key in ("year", "month", "day")):
            return str(anchor.get("weekday") or "")
        if (
            not weekdays
            or not all(isinstance(day, str) for day in weekdays)
            or anchor.get("weekday") not in weekdays
        ):
            return ""
        if not months or not all(
            isinstance(item, dict)
            and isinstance(item.get("days"), int)
            and item["days"] > 0
            for item in months
        ):
            return ""

        def ordinal(date):
            if date.get("year") is None or date.get("day") is None:
                return None
            offset = 0
            for month in months:
                if (
                    str(month.get("name", "")).casefold()
                    == str(date.get("month", "")).casefold()
                ):
                    return (
                        int(date["year"]) * sum(item["days"] for item in months)
                        + offset
                        + int(date["day"])
                        - 1
                    )
                offset += month["days"]
            return None

        current, origin = ordinal(inputs), ordinal(anchor)
        if current is None or origin is None:
            return ""
        return weekdays[
            (weekdays.index(anchor["weekday"]) + current - origin) % len(weekdays)
        ]

    def _weather(self, inputs, season, rng):
        if inputs["weather_mode"] == "manual":
            return inputs["weather_text"] or "Not set"
        if not inputs["location_name"]:
            return "Set a location to generate weather."
        if inputs["location_type"] == "indoors":
            return "Sheltered indoor conditions; outdoor precipitation and wind do not apply."
        if inputs["location_type"] == "underground":
            return "Sheltered underground conditions; no outdoor weather."
        climate = inputs["climate"]
        temperature = {
            "temperate": {"winter": "Cold", "summer": "Warm"}.get(season, "Mild"),
            "cold": "Freezing" if season != "summer" else "Cool",
            "arid": "Cool" if inputs["time_of_day"] == "night" else "Hot",
            "tropical": "Warm and humid",
        }[climate]
        roll = rng.random()
        wet_chance = (
            0.1
            if climate == "arid"
            else (
                0.55
                if climate == "tropical" or season in ("spring", "autumn")
                else 0.35
            )
        )
        if roll < wet_chance:
            sky = (
                "Snow"
                if climate == "cold" or (climate == "temperate" and season == "winter")
                else "Rain"
            )
        elif roll < wet_chance + (
            0.18
            if inputs["time_of_day"] in ("dawn", "morning") and climate != "arid"
            else 0.05
        ):
            sky = "Fog"
        else:
            sky = rng.choice(["Clear skies", "Partly cloudy", "Overcast"])
        wind = rng.choices(
            ["calm air", "a light breeze", "strong wind"], weights=[3, 6, 1]
        )[0]
        return f"{temperature}; {sky.lower()}; {wind}."

    def _effects(self, inputs, weather):
        if inputs["effects_mode"] == "manual":
            return inputs["effects_text"] or "Not set"
        if not inputs["location_name"]:
            return "Set a location to derive environmental effects."
        if inputs["location_type"] != "outdoors":
            return "Sheltered from outdoor weather. Lighting, terrain and local hazards depend on this location; override effects to record them."
        text, effects = weather.casefold(), []
        if inputs["time_of_day"] == "night":
            effects.append(
                "Natural darkness; consider available light and creature senses."
            )
        elif inputs["time_of_day"] in ("dawn", "evening"):
            effects.append("Low natural light; visibility may be reduced.")
        if "fog" in text:
            effects.append("Fog reduces visibility.")
        if "rain" in text:
            effects.append("Wet, potentially slippery surfaces.")
        if "snow" in text or "freezing" in text or "ice" in text:
            effects.append("Cold exposure or icy footing may matter.")
        if "strong wind" in text or "storm" in text:
            effects.append("Strong wind may affect exposed movement, sound and flames.")
        if "hot" in text:
            effects.append("Heat exposure may matter during prolonged exertion.")
        return (
            " ".join(effects)
            or "No additional weather-related effects suggested. Check local terrain and lighting."
        )


in_game_state_service = InGameStateService()
