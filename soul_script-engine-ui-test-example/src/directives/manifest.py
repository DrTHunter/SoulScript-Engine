"""Directives manifest — generates and reads manifest.json.

The manifest catalogs every directive section with stable IDs, SHA-256
hashes, token estimates, and metadata.  It is the single source of truth
for governance, drift detection, and directive retrieval.

Usage (generate from CLI):
    python -m src.directives.manifest

Usage (programmatic):
    from src.directives.manifest import generate_manifest, load_manifest
    manifest = generate_manifest()   # build from live directive files
    manifest = load_manifest()       # read the persisted manifest.json
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.directives.parser import parse_directive_file

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_DIRECTIVES_DIR = os.path.join(_PROJECT_ROOT, "directives")
_MANIFEST_PATH = os.path.join(_DIRECTIVES_DIR, "manifest.json")

MANIFEST_VERSION = 1
HASH_ALGO = "sha256"

def _discover_scopes() -> tuple:
    """Build scope tuple from profile YAML files + 'shared'."""
    profiles_dir = os.path.join(_PROJECT_ROOT, "profiles")
    scopes = {"shared"}
    if os.path.isdir(profiles_dir):
        for fname in os.listdir(profiles_dir):
            if fname.endswith(".yaml"):
                scopes.add(fname[:-5])  # strip .yaml
    return tuple(sorted(scopes, key=lambda s: (s != "shared", s)))

SCOPES = _discover_scopes()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _sha256(text: str) -> str:
    """Return hex SHA-256 of *text* (UTF-8 encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate using chars/4 heuristic."""
    return max(len(text) // 4, 1) if text else 0


def _heading_to_id(scope: str, heading: str) -> str:
    """Convert scope + heading into a stable dotted ID.

    Example: scope="orion", heading="Humor & Play Mode"
    → "orion.humor_play_mode"
    """
    # Lowercase, strip non-alphanumeric (keep spaces/underscores)
    slug = heading.lower().strip()
    slug = re.sub(r"[^a-z0-9\s_]", "", slug)
    slug = re.sub(r"\s+", "_", slug).strip("_")
    # Collapse repeated underscores
    slug = re.sub(r"_+", "_", slug)
    return f"{scope}.{slug}"


# ------------------------------------------------------------------
# Generate
# ------------------------------------------------------------------

def generate_manifest(
    directives_dir: Optional[str] = None,
    scopes: Optional[tuple] = None,
) -> Dict[str, Any]:
    """Build a full manifest dict from live directive files.

    Scans each scope file, parses sections, computes hashes and
    token estimates.  Returns a dict ready to be serialized to JSON.
    """
    directives_dir = directives_dir or _DIRECTIVES_DIR
    scopes = scopes or SCOPES

    entries: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for scope in scopes:
        filepath = os.path.join(directives_dir, f"{scope}.md")
        sections = parse_directive_file(filepath, scope)

        for section in sections:
            full_content = section.heading + "\n" + section.body
            dir_id = _heading_to_id(scope, section.heading)

            # De-duplicate IDs (append counter if collision)
            base_id = dir_id
            counter = 2
            while dir_id in seen_ids:
                dir_id = f"{base_id}_{counter}"
                counter += 1
            seen_ids.add(dir_id)

            # Extract trigger keywords from heading + first 200 chars of body
            trigger_text = (section.heading + " " + section.body[:200]).lower()
            triggers = sorted({
                w for w in re.findall(r"[a-z]{3,}", trigger_text)
                if len(w) >= 4
            })[:10]  # cap at 10 keywords

            entry: Dict[str, Any] = {
                "id": dir_id,
                "name": section.heading,
                "scope": scope,
                "risk": "low",  # default; user can override in manifest
                "version": "1.0.0",
                "sha256": _sha256(full_content),
                "path": f"directives/{section.source_file}",
                "summary": section.body[:120].replace("\n", " ").strip(),
                "triggers": triggers,
                "dependencies": [],
                "status": "active",
                "token_estimate": _estimate_tokens(full_content),
            }
            entries.append(entry)

    manifest: Dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hash_algo": HASH_ALGO,
        "root_paths": ["directives/"],
        "default_retrieval_mode": "keyword_hybrid",
        "directives": entries,
    }
    return manifest


# ------------------------------------------------------------------
# Persist / Load
# ------------------------------------------------------------------

def save_manifest(
    manifest: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
) -> str:
    """Generate (if needed) and write manifest.json.  Returns the path."""
    manifest = manifest or generate_manifest()
    path = path or _MANIFEST_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return path


def load_manifest(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read the persisted manifest.json.  Returns None if missing."""
    path = path or _MANIFEST_PATH
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def manifest_path() -> str:
    """Return the default manifest file path."""
    return _MANIFEST_PATH


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

_REQUIRED_TOP_KEYS = {"manifest_version", "generated_utc", "hash_algo", "root_paths",
                      "default_retrieval_mode", "directives"}
_REQUIRED_ENTRY_KEYS = {"id", "name", "scope", "risk", "version", "sha256", "path",
                        "summary", "triggers", "dependencies", "status", "token_estimate"}
_VALID_SCOPES = set(SCOPES)  # dynamically discovered from profiles/
_VALID_STATUSES = {"active", "deprecated", "experimental"}
_VALID_RISKS = {"low", "medium", "high"}


def validate_manifest(
    manifest: Dict[str, Any],
    directives_dir: Optional[str] = None,
    check_hashes: bool = True,
) -> Dict[str, Any]:
    """Validate a manifest dict.  Returns ``{"valid": bool, "errors": [str]}``.

    Checks:
    - All required top-level and per-entry keys present
    - Enum values in range (scope, status, risk)
    - No duplicate IDs
    - Source files exist on disk
    - SHA-256 matches live content (if *check_hashes* is True)
    """
    directives_dir = directives_dir or _DIRECTIVES_DIR
    errors: List[str] = []

    # Top-level keys
    for key in _REQUIRED_TOP_KEYS:
        if key not in manifest:
            errors.append(f"missing top-level key: {key}")

    directives = manifest.get("directives", [])
    if not isinstance(directives, list):
        errors.append("'directives' must be a list")
        return {"valid": False, "errors": errors}

    seen_ids: set = set()

    for idx, entry in enumerate(directives):
        prefix = f"directives[{idx}]"

        # Required keys
        for key in _REQUIRED_ENTRY_KEYS:
            if key not in entry:
                errors.append(f"{prefix}: missing key '{key}'")

        # Enum checks
        scope = entry.get("scope", "")
        if scope and scope not in _VALID_SCOPES:
            errors.append(f"{prefix}: invalid scope '{scope}'")

        status = entry.get("status", "")
        if status and status not in _VALID_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")

        risk = entry.get("risk", "")
        if risk and risk not in _VALID_RISKS:
            errors.append(f"{prefix}: invalid risk '{risk}'")

        # Duplicate ID
        did = entry.get("id", "")
        if did in seen_ids:
            errors.append(f"{prefix}: duplicate id '{did}'")
        seen_ids.add(did)

        # Source file exists
        rel_path = entry.get("path", "")
        if rel_path:
            # path is like "directives/shared.md" — resolve from project root
            abs_path = os.path.join(
                os.path.dirname(directives_dir),  # parent of directives/
                rel_path,
            )
            if not os.path.isfile(abs_path):
                errors.append(f"{prefix}: source not found: {rel_path}")

        # SHA-256 verification
        if check_hashes and rel_path and os.path.isfile(abs_path):
            scope_name = entry.get("scope", "")
            heading = entry.get("name", "")
            sections = parse_directive_file(
                os.path.join(directives_dir, f"{scope_name}.md"),
                scope_name,
            )
            matched = [s for s in sections if s.heading == heading]
            if matched:
                live_hash = _sha256(matched[0].heading + "\n" + matched[0].body)
                if live_hash != entry.get("sha256"):
                    errors.append(
                        f"{prefix}: sha256 drift for '{did}' "
                        f"(manifest={entry.get('sha256', '')[:12]}… "
                        f"live={live_hash[:12]}…)"
                    )

    return {"valid": len(errors) == 0, "errors": errors}


# ------------------------------------------------------------------
# Change-control: diff two manifests
# ------------------------------------------------------------------

def diff_manifest(
    old: Dict[str, Any],
    new: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two manifests and return structured audit deltas.

    Returns a dict with:
      - ``added``   – directives present in *new* but not *old*
      - ``removed`` – directives present in *old* but not *new*
      - ``changed`` – directives present in both but whose sha256 differs
      - ``unchanged`` – count of directives with identical hashes
    """
    old_by_id = {d["id"]: d for d in old.get("directives", [])}
    new_by_id = {d["id"]: d for d in new.get("directives", [])}

    old_ids = set(old_by_id.keys())
    new_ids = set(new_by_id.keys())

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    common = old_ids & new_ids

    changed: List[Dict[str, Any]] = []
    unchanged_count = 0

    for did in sorted(common):
        old_d = old_by_id[did]
        new_d = new_by_id[did]
        if old_d.get("sha256") != new_d.get("sha256"):
            delta: Dict[str, Any] = {
                "id": did,
                "name": new_d.get("name", ""),
                "scope": new_d.get("scope", ""),
                "old_sha256": old_d.get("sha256", ""),
                "new_sha256": new_d.get("sha256", ""),
                "old_version": old_d.get("version", ""),
                "new_version": new_d.get("version", ""),
                "old_token_estimate": old_d.get("token_estimate", 0),
                "new_token_estimate": new_d.get("token_estimate", 0),
            }
            changed.append(delta)
        else:
            unchanged_count += 1

    return {
        "added": [
            {"id": aid, "name": new_by_id[aid].get("name", ""), "scope": new_by_id[aid].get("scope", "")}
            for aid in added
        ],
        "removed": [
            {"id": rid, "name": old_by_id[rid].get("name", ""), "scope": old_by_id[rid].get("scope", "")}
            for rid in removed
        ],
        "changed": changed,
        "unchanged_count": unchanged_count,
        "total_added": len(added),
        "total_removed": len(removed),
        "total_changed": len(changed),
    }


def audit_changes(
    directives_dir: Optional[str] = None,
    manifest_path_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Load persisted manifest, generate live, compute diff.

    Returns the diff dict.  If no persisted manifest exists, all
    directives are reported as 'added'.
    """
    persisted = load_manifest(path=manifest_path_override)
    live = generate_manifest(directives_dir=directives_dir)

    if persisted is None:
        persisted = {"directives": []}

    return diff_manifest(persisted, live)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    m = generate_manifest()
    p = save_manifest(m)
    count = len(m["directives"])
    print(f"[manifest] Generated {count} directive entries → {p}")
    for entry in m["directives"]:
        print(f"  {entry['id']:50s}  scope={entry['scope']:8s}  tokens≈{entry['token_estimate']}")
