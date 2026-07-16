import json
from collections import Counter
from pathlib import Path


rows = json.loads(Path(r"E:\Aociety-NEW\ue5_project\Saved\forest_town_actor_report.json").read_text(encoding="utf-8"))
print("actors", len(rows))
print("classes")
for name, count in Counter(row["class"] for row in rows).most_common(20):
    print(count, name)

mesh_rows = [row for row in rows if row.get("mesh")]
for category, predicate in (
    ("modular", lambda row: "/Meshes/Modular/" in row.get("mesh", "")),
    ("roof", lambda row: "Roof" in row.get("mesh", "")),
    ("ground", lambda row: "Ground" in row.get("mesh", "") or "Landscape" in row["class"]),
    ("pine", lambda row: "Pine_Tree" in row.get("mesh", "")),
):
    selected = [row for row in mesh_rows if predicate(row)]
    print(f"\n{category} {len(selected)}")
    for row in selected[:80]:
        loc = row["location"]
        print(f"{row['label']} | {row['class']} | ({loc['x']:.1f},{loc['y']:.1f},{loc['z']:.1f}) | {row['mesh']}")
