"""Build, validate, deduplicate, and optionally sign model-profile registries."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile

from services import model_profiles


CONTRIBUTION_SCHEMA = "mobile-router-model-contribution-v1"


def profile_key(profile):
    return (
        model_profiles.key(profile.get("scope") or "exact"),
        model_profiles.key(profile.get("manufacturer")),
        model_profiles.key(profile.get("model")),
        model_profiles.key(profile.get("family")),
        model_profiles.clean(profile.get("hardware_revision"), 120),
        model_profiles.clean(profile.get("firmware_min"), 160),
        model_profiles.clean(profile.get("firmware_max"), 160),
    )


def rule_key(rule):
    return (
        int(rule.get("port")),
        model_profiles.valid_protocol(rule.get("protocol") or "tcp"),
        model_profiles.clean(rule.get("hardware_revision"), 120),
        model_profiles.clean(rule.get("firmware_min"), 160),
        model_profiles.clean(rule.get("firmware_max"), 160),
    )


def load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def profiles_from_payload(payload):
    schema = payload.get("schema") if isinstance(payload, dict) else None
    if schema == model_profiles.SCHEMA:
        model_profiles.verify_registry(payload, require_signature=False)
        return copy.deepcopy(payload.get("profiles") or [])
    if schema == CONTRIBUTION_SCHEMA:
        profile = copy.deepcopy(payload.get("profile") or {})
        profile["ports"] = copy.deepcopy(payload.get("ports") or [])
        return [profile]
    raise ValueError(
        f"Unsupported input schema {schema!r}; expected {model_profiles.SCHEMA} or {CONTRIBUTION_SCHEMA}"
    )


def merge_profiles(payloads):
    merged = {}
    conflicts = []
    for source_name, payload in payloads:
        for incoming in profiles_from_payload(payload):
            incoming = copy.deepcopy(incoming)
            incoming.setdefault("scope", "exact")
            incoming.setdefault("ports", [])
            item_key = profile_key(incoming)
            current = merged.get(item_key)
            if current is None:
                incoming["_sources"] = [source_name]
                merged[item_key] = incoming
                continue
            current["_sources"].append(source_name)
            current["aliases"] = sorted(
                set(current.get("aliases") or []) | set(incoming.get("aliases") or [])
            )
            current["manufacturer_aliases"] = sorted(
                set(current.get("manufacturer_aliases") or [])
                | set(incoming.get("manufacturer_aliases") or [])
            )
            current_rules = {rule_key(rule): rule for rule in current.get("ports") or []}
            for rule in incoming.get("ports") or []:
                incoming_rule_key = rule_key(rule)
                existing = current_rules.get(incoming_rule_key)
                if existing is None:
                    current.setdefault("ports", []).append(rule)
                    current_rules[incoming_rule_key] = rule
                    continue
                compared = (
                    existing.get("service"),
                    existing.get("classification"),
                    existing.get("risk"),
                    existing.get("description"),
                )
                proposed = (
                    rule.get("service"),
                    rule.get("classification"),
                    rule.get("risk"),
                    rule.get("description"),
                )
                if compared != proposed:
                    conflicts.append(
                        {
                            "profile": {
                                "manufacturer": current.get("manufacturer"),
                                "model": current.get("model"),
                                "family": current.get("family"),
                                "scope": current.get("scope"),
                            },
                            "port": incoming_rule_key[0],
                            "protocol": incoming_rule_key[1],
                            "current": existing,
                            "incoming": rule,
                            "source": source_name,
                        }
                    )
    profiles = []
    for profile in merged.values():
        profile.pop("_sources", None)
        profile["ports"] = sorted(
            profile.get("ports") or [],
            key=lambda rule: (
                str(rule.get("protocol") or "tcp"),
                int(rule.get("port") or 0),
            ),
        )
        profiles.append(profile)
    profiles.sort(
        key=lambda profile: (
            model_profiles.key(profile.get("manufacturer")),
            model_profiles.key(profile.get("model")),
            model_profiles.key(profile.get("family")),
            model_profiles.key(profile.get("scope")),
        )
    )
    return profiles, conflicts


def build_registry(profiles, publisher, version, signing_key=None):
    with tempfile.TemporaryDirectory() as tempdir:
        database = Path(tempdir) / "registry.sqlite3"
        for profile in profiles:
            created = model_profiles.upsert_profile(
                database,
                manufacturer=profile.get("manufacturer"),
                model=profile.get("model"),
                family=profile.get("family"),
                scope=profile.get("scope") or "exact",
                hardware_revision=profile.get("hardware_revision"),
                firmware_min=profile.get("firmware_min"),
                firmware_max=profile.get("firmware_max"),
                aliases=profile.get("aliases"),
                manufacturer_aliases=profile.get("manufacturer_aliases"),
                notes=profile.get("notes"),
                risk_notes=profile.get("risk_notes"),
                actor="registry-builder",
            )
            for rule in profile.get("ports") or []:
                model_profiles.add_port_rule(
                    database,
                    profile_id=created["id"],
                    port=rule.get("port"),
                    protocol=rule.get("protocol") or "tcp",
                    service=rule.get("service"),
                    description=rule.get("description"),
                    classification=rule.get("classification") or "expected",
                    exposure=rule.get("exposure") or "unknown",
                    authentication_expected=rule.get("authentication_expected"),
                    encryption_expected=rule.get("encryption_expected"),
                    risk=rule.get("risk") or "info",
                    remediation=rule.get("remediation"),
                    hardware_revision=rule.get("hardware_revision"),
                    firmware_min=rule.get("firmware_min"),
                    firmware_max=rule.get("firmware_max"),
                    source_name=rule.get("source_name"),
                    source_url=rule.get("source_url"),
                    source_reliability=rule.get("source_reliability") or 50,
                    confidence=rule.get("confidence") or "registry",
                    actor="registry-builder",
                    allow_replace=True,
                )
        return model_profiles.export_registry(
            database,
            publisher=publisher,
            version=version,
            signing_key=signing_key,
        )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a validated Mobile Router device-model registry."
    )
    parser.add_argument("inputs", nargs="+", help="Registry or contribution JSON files")
    parser.add_argument("--output", required=True, help="Output registry JSON")
    parser.add_argument("--publisher", required=True, help="Registry publisher name")
    parser.add_argument("--version", required=True, help="Registry version")
    parser.add_argument(
        "--signing-key-env",
        default="MOBILE_ROUTER_MODEL_REGISTRY_SIGNING_KEY",
        help="Environment variable containing the HMAC signing key",
    )
    parser.add_argument(
        "--allow-conflicts",
        action="store_true",
        help="Build even when conflicting port descriptions are found",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    payloads = [(path, load_payload(path)) for path in args.inputs]
    profiles, conflicts = merge_profiles(payloads)
    conflict_path = Path(args.output).with_suffix(".conflicts.json")
    conflict_path.write_text(json.dumps(conflicts, indent=2), encoding="utf-8")
    if conflicts and not args.allow_conflicts:
        print(
            f"Refusing to build: {len(conflicts)} conflict(s). Review {conflict_path}",
            file=sys.stderr,
        )
        return 2
    signing_key = os.environ.get(args.signing_key_env)
    registry = build_registry(
        profiles,
        publisher=args.publisher,
        version=args.version,
        signing_key=signing_key,
    )
    model_profiles.verify_registry(
        registry,
        trusted={args.publisher: signing_key} if signing_key else {},
        require_signature=bool(signing_key),
    )
    Path(args.output).write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(registry['profiles'])} profile(s) to {args.output}; "
        f"conflicts: {len(conflicts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
