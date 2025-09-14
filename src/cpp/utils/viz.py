# viz.py
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from typing import Dict, List, Optional, Sequence, Tuple

# ----------------------------
# Global configuration
# ----------------------------
FIGSIZE = (10, 10)
SHOW_AXIS = False

# Partition look
POLYGON_EDGE_COLOR = 'black'
POLYGON_VERT_COLOR = 'black'
POLYGON_EDGE_WIDTH = 4
POLYGON_VERT_MARKERSIZE = 2
PARTITION_ALPHA = 0.5
PARTITION_EDGE_COLOR = POLYGON_EDGE_COLOR
PARTITION_FACE_COLORS = ["#F0F0F0", "#D9D9D9", "#BDBDBD", "#A0A0A0"]

# Cell overlay (global, light)
RENDER_CELL_OUTLINES = True    # thin boxes
RENDER_CELL_CENTERS  = False   # tiny dots
RENDER_SUBCLUSTER_FILL = False # subtle wash; keep False for “light”


CELL_EDGE_COLOR = '#B0B0B0'
CELL_EDGE_WIDTH = 0.6
CELL_OUTLINE_ALPHA = 0.35
CELL_CENTER_SIZE = 0.8
CELL_CENTER_ALPHA = 0.6
SUBCLUSTER_ALPHA = 0.15
SUBCLUSTER_FILL_COLOR = 'white'

# Paths and connectors
PATH_LINEWIDTH = 4
PATH_COLOR = 'gray'
GLOBAL_CONNECTOR_COLOR = 'red'
GLOBAL_CONNECTOR_LINESTYLE = '-'
GLOBAL_CONNECTOR_LINEWIDTH = 4

# Sweep line / gap text
SWEEP_LINE_COLOR = 'red'
SWEEP_LINE_WIDTH = 3
SWEEP_LINE_STYLE = '-'
GAP_TEXT_COLOR = 'red'
GAP_TEXT_SIZE = 12

CellID = Tuple[int, int]
Point  = Tuple[float, float]

def plot_polygons(
    polygons: Sequence[Polygon],
    subclusters: Optional[Dict[int, List[CellID]]] = None,
    cell_size: Optional[float] = None,
    paths: Optional[List[List[CellID]]] = None,
    global_connectors: Optional[List[Tuple[CellID, CellID]]] = None,
    sweep_line_info: Optional[dict] = None,
    title: str = "Polygon Partition",
    save_path: Optional[str] = None,
):
    fig, ax = plt.subplots(figsize=FIGSIZE)

    def cell_center(cell: CellID, s: float) -> Point:
        r, c = cell
        return (c * s + s / 2.0, r * s + s / 2.0)

    def get_cell_polygon(cell_id: CellID, s: float) -> Polygon:
        r, c = cell_id
        return Polygon([
            (c * s,         r * s),
            ((c + 1) * s,   r * s),
            ((c + 1) * s,  (r + 1) * s),
            (c * s,        (r + 1) * s),
        ])

    # Partitions
    color_index = 0
    for poly in polygons:
        if not poly or poly.is_empty:
            continue
        if poly.geom_type == 'Polygon':
            face = PARTITION_FACE_COLORS[color_index % len(PARTITION_FACE_COLORS)]
            color_index += 1
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=PARTITION_ALPHA, edgecolor=PARTITION_EDGE_COLOR, facecolor=face)
            ax.plot(x, y, color=POLYGON_EDGE_COLOR, linewidth=POLYGON_EDGE_WIDTH)
            ax.plot(x, y, 'o', color=POLYGON_VERT_COLOR, markersize=POLYGON_VERT_MARKERSIZE)
        elif poly.geom_type == 'MultiPolygon':
            for sp in poly.geoms:
                face = PARTITION_FACE_COLORS[color_index % len(PARTITION_FACE_COLORS)]
                color_index += 1
                x, y = sp.exterior.xy
                ax.fill(x, y, alpha=PARTITION_ALPHA, edgecolor=PARTITION_EDGE_COLOR, facecolor=face)
                ax.plot(x, y, color=POLYGON_EDGE_COLOR, linewidth=POLYGON_EDGE_WIDTH)
                ax.plot(x, y, 'o', color=POLYGON_VERT_COLOR, markersize=POLYGON_VERT_MARKERSIZE)

    # Cells from subclusters only
    if subclusters and cell_size:
        if RENDER_CELL_OUTLINES:
            for cells in subclusters.values():
                for rc in cells:
                    cp = get_cell_polygon(rc, cell_size)
                    x, y = cp.exterior.xy
                    ax.plot(x, y, linewidth=CELL_EDGE_WIDTH, color=CELL_EDGE_COLOR, alpha=CELL_OUTLINE_ALPHA)

        if RENDER_CELL_CENTERS:
            xs, ys = [], []
            for cells in subclusters.values():
                for rc in cells:
                    x, y = cell_center(rc, cell_size)
                    xs.append(x); ys.append(y)
            if xs:
                ax.plot(xs, ys, '.', markersize=CELL_CENTER_SIZE, color=CELL_EDGE_COLOR, alpha=CELL_CENTER_ALPHA)

        if RENDER_SUBCLUSTER_FILL:
            for cells in subclusters.values():
                for rc in cells:
                    cp = get_cell_polygon(rc, cell_size)
                    x, y = cp.exterior.xy
                    ax.fill(x, y, alpha=SUBCLUSTER_ALPHA, edgecolor='none', facecolor=SUBCLUSTER_FILL_COLOR)

    # Paths
    if paths and cell_size:
        for path in paths:
            xs, ys = [], []
            for rc in path:
                x, y = cell_center(rc, cell_size)
                xs.append(x); ys.append(y)
            ax.plot(xs, ys, linewidth=PATH_LINEWIDTH, color=PATH_COLOR)

    # Global connectors
    if global_connectors and cell_size:
        for a, b in global_connectors:
            x1, y1 = cell_center(a, cell_size)
            x2, y2 = cell_center(b, cell_size)
            ax.plot([x1, x2], [y1, y2],
                    color=GLOBAL_CONNECTOR_COLOR,
                    linestyle=GLOBAL_CONNECTOR_LINESTYLE,
                    linewidth=GLOBAL_CONNECTOR_LINEWIDTH)

    # Sweep line
    if sweep_line_info:
        sweep_line = sweep_line_info.get("sweep_line")
        gap_value = sweep_line_info.get("gap_value")
        cand_idx = sweep_line_info.get("candidate_index", "")
        cand_dir = sweep_line_info.get("candidate_direction", "")
        cand_val = sweep_line_info.get("candidate_value", "")
        if sweep_line is not None:
            x_line, y_line = sweep_line.xy
            label = f"Sweep Line {cand_dir} (Idx: {cand_idx}, Value: {cand_val:.2f})"
            ax.plot(x_line, y_line, color=SWEEP_LINE_COLOR, linestyle=SWEEP_LINE_STYLE,
                    linewidth=SWEEP_LINE_WIDTH, label=label)
            mid_x = (x_line[0] + x_line[-1]) / 2
            mid_y = (y_line[0] + y_line[-1]) / 2
            if gap_value is not None:
                ax.annotate(f"Gap: {gap_value:.2f}", (mid_x, mid_y),
                            color=GAP_TEXT_COLOR, fontsize=GAP_TEXT_SIZE)

    if not SHOW_AXIS:
        ax.axis('off')
    ax.set_aspect('equal', adjustable='box')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
