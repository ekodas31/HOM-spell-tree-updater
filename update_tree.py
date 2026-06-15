import csv
import json
from collections import defaultdict

OLD_SCAN = "old_scan.json"
NEW_SCAN = "new_scan.json"
TREE_FILE = "tree.json"
OUTPUT_FILE = "new_tree.json"
CSV_OUTPUT = "formid_mismatches.csv"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


print("Loading files...")

old_scan = load_json(OLD_SCAN)
new_scan = load_json(NEW_SCAN)
tree = load_json(TREE_FILE)

# ------------------------------------------------------------------
# Build lookup from new scan
# ------------------------------------------------------------------

name_lookup = defaultdict(list)
plugin_name_lookup = defaultdict(list)
persistent_lookup = {}

for spell in new_scan["spells"]:
    name = spell.get("name", "")
    plugin = spell.get("plugin", "")
    formid = spell["formId"]
    persistent_id = spell.get("persistentId")

    name_lookup[name].append(formid)
    plugin_name_lookup[(plugin, name)].append(formid)
    if persistent_id:
        persistent_lookup[persistent_id] = formid

for name, ids in name_lookup.items():
    if len(ids) > 1:
        print(f"WARNING: duplicate spell name in new scan: {name}")
        print(ids)

for key, ids in plugin_name_lookup.items():
    if len(ids) > 1:
        print(f"WARNING: duplicate spell in new scan for plugin+name: {key}")
        print(ids)

# ------------------------------------------------------------------
# Build old -> new FormID mapping
# ------------------------------------------------------------------

formid_map = {}
missing = []
mismatch_info = {}

tree_mismatch_rows = []
seen_tree_mismatch_ids = set()

for spell in old_scan["spells"]:
    name = spell.get("name", "")
    plugin = spell.get("plugin", "")
    old_formid = spell["formId"]

    new_formid = None

    ids_by_name = name_lookup.get(name, [])
    if len(ids_by_name) == 1:
        new_formid = ids_by_name[0]
    else:
        ids_by_plugin_name = plugin_name_lookup.get((plugin, name), [])
        if len(ids_by_plugin_name) == 1:
            new_formid = ids_by_plugin_name[0]
        else:
            persistent_id = spell.get("persistentId")
            if persistent_id:
                new_formid = persistent_lookup.get(persistent_id)
                if new_formid:
                    print(f"Using persistentId fallback for {plugin} | {name}: {persistent_id}")

    if new_formid is None:
        missing.append((plugin, name))
        continue

    if old_formid != new_formid:
        formid_map[old_formid] = new_formid
        mismatch_info[old_formid] = {
            "plugin": plugin,
            "name": name,
            "old_formId": old_formid,
            "new_formId": new_formid
        }

print(f"\nMappings found: {len(formid_map)}")
print(f"Missing matches: {len(missing)}")

# ------------------------------------------------------------------
# Recursive replacement
# ------------------------------------------------------------------

def replace_formids(obj):

    if isinstance(obj, dict):
        return {
            k: replace_formids(v)
            for k, v in obj.items()
        }

    elif isinstance(obj, list):
        return [
            replace_formids(v)
            for v in obj
        ]

    elif isinstance(obj, str):
        if obj in formid_map:
            if obj not in seen_tree_mismatch_ids:
                seen_tree_mismatch_ids.add(obj)
                tree_mismatch_rows.append(mismatch_info[obj])
            return formid_map[obj]
        return obj

    return obj


print("Updating tree...")

new_tree = replace_formids(tree)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(new_tree, f, indent=2)

with open(CSV_OUTPUT, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["plugin", "name", "old_formId", "new_formId"])
    writer.writeheader()
    writer.writerows(tree_mismatch_rows)

print(f"Done.")
print(f"Saved to: {OUTPUT_FILE}")
print(f"CSV report saved to: {CSV_OUTPUT}")

if missing:
    print("\nUnmatched spells:")
    for plugin, name in missing[:50]:
        print(f"  {plugin} | {name}")

    if len(missing) > 50:
        print(f"... and {len(missing)-50} more")

