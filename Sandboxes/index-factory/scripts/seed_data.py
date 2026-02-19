#!/usr/bin/env python3
"""
Seed script: creates mock data for local development.
Run with: python scripts/seed_data.py

Requires the API to be running at http://localhost:8000.
"""
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API = "http://localhost:8000/api"

def api(method: str, path: str, data: dict | None = None, token: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = Request(f"{API}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            if resp.status == 204:
                return {}
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        print(f"  Error {e.code}: {body}")
        return {}


def main():
    print("=== Index Factory Seed Data ===\n")

    # 1. Register user
    print("[1/5] Creating demo user...")
    user = api("POST", "/auth/register", {
        "email": "demo@indexfactory.dev",
        "username": "demo",
        "password": "demo1234",
    })
    if not user.get("id"):
        print("  User may already exist, trying login...")

    # Login
    token_data = api("POST", "/auth/login", {
        "email": "demo@indexfactory.dev",
        "password": "demo1234",
    })
    token = token_data.get("access_token", "")
    if not token:
        print("  Failed to get token!")
        sys.exit(1)
    print(f"  Logged in as demo user")

    # 2. Create objects
    print("\n[2/5] Creating objects...")
    objects_data = [
        {"name": "Trees", "description": "Collection of tree species and their properties"},
        {"name": "Flowers", "description": "Flowering plants classification and references"},
        {"name": "Rocks", "description": "Geological samples and mineral identification"},
    ]
    objects = []
    for obj in objects_data:
        result = api("POST", "/objects/", obj, token)
        if result.get("id"):
            objects.append(result)
            print(f"  Created: {obj['name']}")

    if not objects:
        print("  No objects created, loading existing...")
        objects = api("GET", "/objects/", token=token)
        if isinstance(objects, list):
            print(f"  Found {len(objects)} existing objects")

    # 3. Create ontology for Trees
    if objects:
        tree_obj = objects[0]
        obj_id = tree_obj["id"]
        print(f"\n[3/5] Creating ontology for '{tree_obj['name']}'...")

        ontology = [
            {"name": "Species", "description": "Tree species classification", "color": "#3b82f6"},
            {"name": "Leaf Type", "description": "Leaf shape and arrangement", "color": "#10b981"},
            {"name": "Bark Pattern", "description": "Bark texture and color", "color": "#f59e0b"},
            {"name": "Habitat", "description": "Natural growing environment", "color": "#8b5cf6"},
            {"name": "Size Class", "description": "Height and canopy size", "color": "#ef4444"},
        ]
        created_nodes = []
        for node in ontology:
            result = api("POST", f"/objects/{obj_id}/ontology", node, token)
            if result.get("id"):
                created_nodes.append(result)
                print(f"  Created node: {node['name']}")

        # Add child nodes under Species
        if created_nodes:
            species_id = created_nodes[0]["id"]
            sub_species = [
                {"name": "Oak", "description": "Quercus genus", "color": "#6366f1", "parent_id": species_id},
                {"name": "Maple", "description": "Acer genus", "color": "#ec4899", "parent_id": species_id},
                {"name": "Pine", "description": "Pinus genus", "color": "#06b6d4", "parent_id": species_id},
                {"name": "Birch", "description": "Betula genus", "color": "#f97316", "parent_id": species_id},
            ]
            for sub in sub_species:
                result = api("POST", f"/objects/{obj_id}/ontology", sub, token)
                if result.get("id"):
                    print(f"    Created sub-node: {sub['name']}")

    # 4. Create documents
    print("\n[4/5] Creating documents...")
    documents = [
        {
            "source_type": "text",
            "title": "Oak Tree Identification Guide",
            "raw_text": """Oak trees belong to the genus Quercus and the beech family Fagaceae.
There are approximately 500 extant species of oaks. The common name "oak" also
appears in the names of species in related genera. Oaks have spirally arranged
leaves, with lobate margins in many species; some have serrated leaves or entire
leaves with smooth margins. Many deciduous species are marcescent, not dropping
dead leaves until spring. In spring, a single oak tree produces both male flowers
(in the form of catkins) and small female flowers. The fruit is a nut called an
acorn, borne in a cup-like structure known as a cupule. Each acorn contains one
seed and takes 6-18 months to mature depending on their species.""",
        },
        {
            "source_type": "text",
            "title": "Maple Tree Characteristics",
            "raw_text": """Maples are trees or shrubs in the genus Acer. There are approximately
132 species, most of which are native to Asia. Maples are variously classified
in a family of their own, the Aceraceae, or together with the Hippocastanaceae
included in the family Sapindaceae. Most maple species are deciduous, and many
are renowned for their autumn leaf color. The distinctive fruit, called samaras
or maple keys, are paired and form the shape of helicopter rotors when they fall.
Maple syrup is made from the sap of some maple species, primarily the sugar maple.""",
        },
        {
            "source_type": "text",
            "title": "Photosynthesis in Trees",
            "raw_text": """Photosynthesis is the process used by plants, algae and certain bacteria
to convert light energy into chemical energy. Trees perform photosynthesis
primarily in their leaves, where chlorophyll absorbs light. The process involves
the absorption of carbon dioxide and water, producing glucose and oxygen.
Different tree species have varying rates of photosynthesis depending on leaf
structure, chlorophyll content, and environmental conditions. Deciduous trees
typically have higher rates during summer months, while evergreen trees maintain
photosynthesis throughout the year, though at reduced rates during winter.""",
        },
        {
            "source_type": "webpage",
            "title": "Tree Bark Identification Methods",
            "source_url": "https://example.com/tree-bark-guide",
            "raw_text": """Tree bark is the outermost layers of stems and roots of woody plants.
It serves multiple functions: protection against physical damage, prevention of
water loss, and defense against pathogens. Bark patterns are key identifiers:
- Smooth bark: Beech, birch (young), cherry
- Furrowed bark: Oak, elm, ash (deep ridges)
- Scaly bark: Pine, spruce (flaking plates)
- Peeling bark: Birch, sycamore (papery sheets)
- Corky bark: Cork oak, sweetgum (thick spongy texture)
The color, texture, and pattern of bark change as a tree ages, making
identification more complex for mature specimens.""",
        },
        {
            "source_type": "markdown",
            "title": "Conifer vs Deciduous Trees",
            "raw_text": """# Conifer vs Deciduous Trees

## Key Differences

### Leaf Type
- **Conifers**: Needles or scales, typically evergreen
- **Deciduous**: Broad, flat leaves that fall in autumn

### Reproduction
- **Conifers**: Bear cones (hence the name)
- **Deciduous**: Produce flowers and fruits

### Wood Properties
- **Conifers**: Softwood, lighter, used for construction
- **Deciduous**: Hardwood, denser, used for furniture

### Geographic Distribution
- **Conifers**: Dominant in boreal forests, high altitudes
- **Deciduous**: Prevalent in temperate regions""",
        },
    ]

    for doc in documents:
        result = api("POST", "/documents/", doc, token)
        if result.get("id"):
            print(f"  Created: {doc['title']}")

    # 5. Summary
    print("\n[5/5] Seed complete!")
    print(f"\n  Login credentials:")
    print(f"    Email:    demo@indexfactory.dev")
    print(f"    Password: demo1234")
    print(f"\n  API:  http://localhost:8000/docs")
    print(f"  App:  http://localhost")
    print(f"  RMQ:  http://localhost:15672")


if __name__ == "__main__":
    main()
