import os
import pickle
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple, Union

from shapely import wkt as _wkt
from shapely.geometry import Polygon, MultiPolygon

try:
    import fields2cover as f2c  # optional, only needed if you pass f2c.Cells in 
    _HAS_F2C = True
except Exception:
    _HAS_F2C = False


XY = Tuple[float, float]
Ring = List[XY]


# ----------------------------
# Conversions
# ----------------------------

def _strip_closure(coords: Iterable[Tuple[float, float]]) -> Ring:
    coords = list(coords)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]

def shapely_to_outer_holes(poly: Polygon) -> Tuple[Ring, List[Ring]]:
    outer = _strip_closure(poly.exterior.coords)
    holes = [_strip_closure(r.coords) for r in poly.interiors]
    return outer, holes

def dict_to_shapely(d: Dict[str, Any]) -> Polygon:
    outer = d.get("outer", [])
    holes = d.get("holes", [])
    # Allow single-hole shape
    if holes and holes and isinstance(holes[0][0], (int, float)):
        holes = [holes]
    return Polygon(shell=outer, holes=holes)

def _to_wkt(geom: Any) -> str:
    for name in ("toWKT", "to_wkt", "wkt"):
        if hasattr(geom, name):
            return getattr(geom, name)()
    for name in ("toString", "to_string", "__str__"):
        if hasattr(geom, name):
            s = getattr(geom, name)()
            if isinstance(s, str) and s[:3].isalpha():
                return s
    raise AttributeError("Could not obtain WKT from geometry")

def _cells_to_polys(cells: Any) -> List[Polygon]:
    # Accepts f2c.Cells or duck-typed equivalent
    if not hasattr(cells, "size") or not hasattr(cells, "getGeometry"):
        raise TypeError("Expected Fields2Cover Cells or equivalent")
    out: List[Polygon] = []
    for i in range(cells.size()):
        w = _to_wkt(cells.getGeometry(i))
        shp = _wkt.loads(w)
        if isinstance(shp, Polygon):
            out.append(shp)
        elif isinstance(shp, MultiPolygon):
            out.extend([p for p in shp.geoms if isinstance(p, Polygon)])
    return out

def _to_polygons_list(obj: Any) -> List[Polygon]:
    if obj is None:
        return []
    if hasattr(obj, "size") and hasattr(obj, "getGeometry"):
        return _cells_to_polys(obj)
    if isinstance(obj, Polygon):
        return [obj]
    if isinstance(obj, MultiPolygon):
        return [p for p in obj.geoms if isinstance(p, Polygon)]
    if isinstance(obj, str):
        return _to_polygons_list(_wkt.loads(obj))
    if isinstance(obj, dict) and "outer" in obj:
        return [dict_to_shapely(obj)]
    if isinstance(obj, Iterable):
        acc: List[Polygon] = []
        for x in obj:
            acc.extend(_to_polygons_list(x))
        return acc
    raise TypeError(f"Unsupported geometry type: {type(obj)}")

def _coerce_base(obj: Any) -> Polygon:
    polys = _to_polygons_list(obj)
    if len(polys) != 1:
        raise ValueError("Base must resolve to exactly one Polygon")
    return polys[0]


# ----------------------------
# Data model
# ----------------------------

@dataclass
class Record:
    name: str
    base: Polygon
    results: Dict[str, List[Polygon]] = field(
        default_factory=lambda: {"trapezoidal": [], "boustrophedon": [], "li": [], "ours": []}
    )
    meta: Dict[str, Any] = field(default_factory=dict)
    
_ALLOWED_KINDS = ("trapezoidal", "boustrophedon", "li", "ours")

# ----------------------------
# Store
# ----------------------------

class PickleDecompStore:
    """
    Compact pickle store for polygons and decompositions.
    Stores Shapely directly, so files stay small and fast to read.
    """

    def __init__(self, path: str, autosave: bool = True):
        self.path = path
        self.autosave = autosave
        self.records: Dict[str, Record] = {}
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                # Backward-compatible shape
                if isinstance(data, dict) and all(isinstance(v, Record) for v in data.values()):
                    self.records = data
                elif isinstance(data, dict) and "records" in data:
                    # older shape: {"records": {...}}
                    self.records = data["records"]
                else:
                    # Best effort
                    self.records = data  # type: ignore[assignment]
            except Exception as e:
                print("Warning: could not read store:", e)

    # ---- Persistence ----
    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump({"records": self.records}, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, self.path)

    def _maybe_save(self) -> None:
        if self.autosave:
            self.save()

    # ---- CRUD ----
    def upsert(
        self,
        name: str,
        base: Any | None = None,
        trapezoidal: Any | None = None,
        boustrophedon: Any | None = None,
        li: Any | None = None,
        ours: Any | None = None,
        meta: Dict[str, Any] | None = None,
        replace_parts: bool = True,
    ) -> Record:
        rec = self.records.get(name)
        if rec is None:
            if base is None:
                raise ValueError("Creating a new record needs a base polygon")
            rec = Record(name=name, base=_coerce_base(base))
            self.records[name] = rec
        else:
            if base is not None:
                rec.base = _coerce_base(base)

        if trapezoidal is not None:
            parts = _to_polygons_list(trapezoidal)
            if replace_parts:
                rec.results["trapezoidal"] = parts
            else:
                rec.results["trapezoidal"].extend(parts)

        if boustrophedon is not None:
            parts = _to_polygons_list(boustrophedon)
            if replace_parts:
                rec.results["boustrophedon"] = parts
            else:
                rec.results["boustrophedon"].extend(parts)

        if ours is not None:
            parts = _to_polygons_list(ours)
            if replace_parts:
                rec.results["ours"] = parts
            else:
                rec.results["ours"].extend(parts)

        if li is not None:
            parts = _to_polygons_list(li)
            if replace_parts:
                rec.results["li"] = parts
            else:
                rec.results["li"].extend(parts)



        if meta:
            rec.meta.update(meta)

        self._maybe_save()
        return rec

    def add_parts(self, name: str, kind: str, parts: Any, replace: bool = False) -> None:
        rec = self._need(name)
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"kind must be one of {_ALLOWED_KINDS}")
        lst = _to_polygons_list(parts)
        if replace:
            rec.results[kind] = lst
        else:
            rec.results[kind].extend(lst)
        self._maybe_save()

    def set_base(self, name: str, base: Any) -> None:
        rec = self._need(name)
        rec.base = _coerce_base(base)
        self._maybe_save()

    def delete(self, name: str) -> None:
        self.records.pop(name, None)
        self._maybe_save()

    def get(self, name: str) -> Record:
        return self._need(name)

    def list_names(self) -> List[str]:
        return sorted(self.records.keys())

    # ---- Exports for your loader ----
    def export_base_for_loader(self, name: str) -> Tuple[Ring, List[Ring]]:
        rec = self._need(name)
        return shapely_to_outer_holes(rec.base)

    def export_parts_for_loader(self, name: str, kind: str) -> List[Tuple[Ring, List[Ring]]]:
        rec = self._need(name)
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"kind must be one of {_ALLOWED_KINDS}")
        return [shapely_to_outer_holes(p) for p in rec.results.get(kind, [])]

    # ---- Summaries ----
    def summarize(self) -> str:
        lines: List[str] = []
        for name in self.list_names():
            r = self.records[name]
            holes = len(r.base.interiors)
            t_cnt = len(r.results.get("trapezoidal", []))
            b_cnt = len(r.results.get("boustrophedon", []))
            o_cnt = len(r.results.get("ours", []))
            l_cnt = len(r.results.get("li", []))
            parts = []
            if t_cnt:
                parts.append(f"trapezoidal={t_cnt}")
            if b_cnt:
                parts.append(f"boustrophedon={b_cnt}")
            if o_cnt:
                parts.append(f"ours={o_cnt}")
            if l_cnt:
                parts.append(f"li={l_cnt}")
            part_str = ", ".join(parts) if parts else "no decompositions"
            lines.append(f"- {name} | holes={holes} | {part_str}")
        return "\n".join(lines) if lines else "(empty store)"

    def print_summary(self) -> None:
        print(self.summarize())

    # ---- Internals ----
    def _need(self, name: str) -> Record:
        if name not in self.records:
            raise KeyError(f"No record named {name}")
        return self.records[name]
