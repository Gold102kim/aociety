import json
import struct
import sys
from pathlib import Path


def read_glb_json(path: Path):
    with path.open("rb") as stream:
        magic, version, total_length = struct.unpack("<4sII", stream.read(12))
        if magic != b"glTF" or version != 2:
            raise RuntimeError(f"{path} is not a GLB/VRM 2.0 container")
        chunk_length, chunk_type = struct.unpack("<II", stream.read(8))
        if chunk_type != 0x4E4F534A:
            raise RuntimeError(f"{path} does not start with a JSON chunk")
        payload = json.loads(stream.read(chunk_length).decode("utf-8").rstrip(" \t\r\n\0"))
        return payload, total_length


for name in sys.argv[1:]:
    path = Path(name)
    payload, total_length = read_glb_json(path)
    extensions = payload.get("extensions", {})
    vrm0 = extensions.get("VRM", {})
    vrm1 = extensions.get("VRMC_vrm", {})
    meta = vrm0.get("meta", {}) or vrm1.get("meta", {})
    report = {
        "file": str(path),
        "bytes": total_length,
        "title": meta.get("title") or meta.get("name"),
        "author": meta.get("author") or meta.get("authors"),
        "version": meta.get("version"),
        "allowed_user": meta.get("allowedUserName"),
        "violent_usage": meta.get("violentUssageName"),
        "sexual_usage": meta.get("sexualUssageName"),
        "commercial_usage": meta.get("commercialUssageName") or meta.get("commercialUsage"),
        "license": meta.get("licenseName"),
        "license_url": meta.get("otherLicenseUrl") or meta.get("licenseUrl"),
        "contact": meta.get("contactInformation"),
        "reference": meta.get("reference"),
        "mesh_count": len(payload.get("meshes", [])),
        "skin_count": len(payload.get("skins", [])),
        "material_count": len(payload.get("materials", [])),
        "vertex_count": sum(
            payload["accessors"][primitive["attributes"]["POSITION"]].get("count", 0)
            for mesh in payload.get("meshes", [])
            for primitive in mesh.get("primitives", [])
            if "POSITION" in primitive.get("attributes", {})
        ),
        "triangle_count": sum(
            payload["accessors"][primitive["indices"]].get("count", 0) // 3
            for mesh in payload.get("meshes", [])
            for primitive in mesh.get("primitives", [])
            if "indices" in primitive
        ),
    }
    print(json.dumps(report, ensure_ascii=False))
