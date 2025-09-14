from pathlib import Path
from typing import Optional
import math
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from pathlib import Path
from shapely.geometry import Polygon

from cpp.picklestore import PickleDecompStore

Point2D = Tuple[float, float]
CellID = Tuple[int, int]  # (row, col)

@dataclass(frozen=True)
class CandidateOption:
    entry: Point2D
    exit: Point2D
    cost: float
    turns: int
    path: Optional[List[Point2D]] = None



def project_root(markers=("pyproject.toml", ".git")) -> Path:
    """Walk up from this file until we see a marker, else use CWD."""
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if any((p / m).exists() for m in markers):
            return p
    return Path.cwd()




def count_turns(path):
    # path is a list of (x, y) coordinates
    if len(path) < 3:
        return 0  # Not enough segments to have a turn
    
    # Compute orientations for each segment
    orientations = []
    for i in range(len(path) - 1):
        dx = path[i+1][0] - path[i][0]
        dy = path[i+1][1] - path[i][1]
        orientations.append(math.atan2(dy, dx))
    
    turn_count = 0
    for i in range(len(orientations) - 1):
        dtheta = orientations[i+1] - orientations[i]
        # Normalize angle to (-pi, pi]
        dtheta = (dtheta + math.pi) % (2*math.pi) - math.pi
        # Check if there's a change in direction (with small tolerance)
        if abs(dtheta) > 1e-7:
            turn_count += 1
    
    return turn_count



def calculate_path_cost(path):
    """
    Calculate the total Euclidean distance for a given path.
    """
    total_cost = 0.0
    for i in range(1, len(path)):
        x1, y1 = path[i-1]
        x2, y2 = path[i]
        total_cost += np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return total_cost






def get_cell_polygon(cell_id: CellID, cell_size: float) -> Polygon:
    """Square polygon for a grid cell. Used by rasterizing + distribution steps."""
    row, col = cell_id
    x0, y0 = col * cell_size, row * cell_size
    x1, y1 = (col + 1) * cell_size, (row + 1) * cell_size
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def cells_inside_polygon_ids(polygon_border, cell_size: float) -> List[CellID]:
    """Rasterize ROI into grid cells, return (row,col) ids that intersect the polygon.
    Used after partitioning/merging to sample the full region."""
    if cell_size <= 0:
        raise ValueError("cell_size must be > 0")
    if polygon_border is None or getattr(polygon_border, "is_empty", False):
        return []

    min_x, min_y, max_x, max_y = polygon_border.bounds
    col_min = int(math.floor(min_x / cell_size))
    row_min = int(math.floor(min_y / cell_size))
    col_max = int(math.ceil(max_x / cell_size))
    row_max = int(math.ceil(max_y / cell_size))

    cell_ids: List[CellID] = []
    for row in range(row_min, row_max):
        for col in range(col_min, col_max):
            if get_cell_polygon((row, col), cell_size).intersects(polygon_border):
                cell_ids.append((row, col))
    return cell_ids


def distribute_cells_to_subclusters(
    cell_ids: List[CellID],
    cell_size: float,
    partition_polygons: List[Polygon],
) -> Dict[int, List[CellID]]:
    """Assign each cell to the partition with max overlap area.
    Used to build per-partition cell sets before generating sweep candidates."""
    out: Dict[int, List[CellID]] = {i: [] for i in range(len(partition_polygons))}
    if not cell_ids or not partition_polygons:
        return out

    for cell_id in cell_ids:
        cell_poly = get_cell_polygon(cell_id, cell_size)
        best_idx, best_area = None, 0.0
        for idx, part_poly in enumerate(partition_polygons):
            if not part_poly or part_poly.is_empty:
                continue
            area = cell_poly.intersection(part_poly).area
            if area > best_area:
                best_idx, best_area = idx, area
        if best_idx is not None:
            out[best_idx].append(cell_id)
    return out


def cell_to_xy(cell_rc: CellID, cell_size: float = 1.0) -> Tuple[float, float]:
    """Center (x,y) of a cell. Used to convert cells to waypoints for sweep path gen."""
    row, col = cell_rc
    return (col * cell_size + cell_size / 2.0, row * cell_size + cell_size / 2.0)


def default_store_path() -> Path:
    # resolve to the package directory and look for artifacts/decompositions.pkl
    here = Path(__file__).resolve().parent
    return here / "artifacts" / "decompositions.pkl"

def print_store_summary(store_path: Optional[str | Path] = None) -> str:
    """
    Load the PickleDecompStore and print a human-readable summary.
    Returns the summary string for convenience.
    """
    p = Path(store_path) if store_path else default_store_path()
    store = PickleDecompStore(str(p), autosave=False)
    summary = store.summarize()
    text = summary if summary else "(empty store)"
    print(text)
    return text

if __name__ == "__main__":
    # Allow running as a tiny script: python -m cpp.utils
    print_store_summary()
