from shapely.geometry import Polygon, LineString, Point
from shapely.ops import split

##############################################################################
# HELPER FUNCTIONS
##############################################################################

def gather_all_ring_coords(polygon):
    """
    Return a combined list of coordinates from the exterior and all interior rings
    of the given polygon. Useful for detecting holes (interior rings).
    """
    all_coords = list(polygon.exterior.coords)
    for interior in polygon.interiors:
        all_coords.extend(interior.coords)
    return all_coords

def extract_points_from_intersection(geom):
    """
    Given a Shapely geometry from an intersection operation,
    return a flat list of Point objects.
    """
    points = []
    if geom.is_empty:
        return points
    if geom.geom_type == 'Point':
        points.append(geom)
    elif geom.geom_type == 'MultiPoint':
        points.extend(list(geom.geoms))
    elif geom.geom_type == 'LineString':
        # If the sweep line overlaps an edge, take its endpoints.
        points.append(Point(geom.coords[0]))
        points.append(Point(geom.coords[-1]))
    elif geom.geom_type == 'GeometryCollection':
        for g in geom.geoms:
            points.extend(extract_points_from_intersection(g))
    return points

##############################################################################
# TROUBLESOME DETECTION
##############################################################################

def is_polygon_troublesome(polygon, tolerance):
    """
    Determines if a rectilinear polygon (including holes) is "troublesome" in both
    horizontal and vertical directions.

    For each candidate horizontal/vertical sweep (placed halfway between unique
    vertex coordinates from the exterior + any interior rings), we check how many
    times the sweep line intersects the polygon boundary. More than 2 intersections
    indicates concavity or a hole, making that direction troublesome.

    Returns True if the polygon is troublesome in BOTH directions.
    """
    minx, miny, maxx, maxy = polygon.bounds
    
    # Gather coords from exterior + interior rings.
    coords = gather_all_ring_coords(polygon)
    
    # Round them to avoid floating-point jitter, then get unique values.
    ys = sorted(set(round(pt[1] / tolerance) * tolerance for pt in coords))
    xs = sorted(set(round(pt[0] / tolerance) * tolerance for pt in coords))
    
    horizontal_trouble = False
    vertical_trouble = False
    
    # Check horizontal sweeps
    if len(ys) >= 2:
        for i in range(len(ys)-1):
            candidate_y = (ys[i] + ys[i+1]) / 2.0
            sweep_line = LineString([(minx - 1, candidate_y), (maxx + 1, candidate_y)])
            inter = polygon.boundary.intersection(sweep_line)
            pts = extract_points_from_intersection(inter)
            if len(pts) > 2:
                horizontal_trouble = True
                break
    
    # Check vertical sweeps
    if len(xs) >= 2:
        for i in range(len(xs)-1):
            candidate_x = (xs[i] + xs[i+1]) / 2.0
            sweep_line = LineString([(candidate_x, miny - 1), (candidate_x, maxy + 1)])
            inter = polygon.boundary.intersection(sweep_line)
            pts = extract_points_from_intersection(inter)
            if len(pts) > 2:
                vertical_trouble = True
                break
    
   
    return (horizontal_trouble, vertical_trouble)

def quantify_gap_severity(polygon, tolerance, candidate_source="exterior"):
    """
    Quantifies the "gap severity" in both horizontal and vertical directions.

    For each candidate sweep line compute the extra "gaps."
    
    """
    minx, miny, maxx, maxy = polygon.bounds
    if candidate_source == "all_rings":
        coords = gather_all_ring_coords(polygon)
    else:
        coords = list(polygon.exterior.coords)
    ys = sorted(set(round(pt[1]/tolerance)*tolerance for pt in coords))
    xs = sorted(set(round(pt[0]/tolerance)*tolerance for pt in coords))
    
 
    total_horizontal_gap = 0.0
    total_vertical_gap = 0.0
    max_horizontal_gap = 0.0
    max_vertical_gap = 0.0
    horizontal_union = None
    vertical_union = None
    details = {
        "horizontal": [],
        "vertical": []
    }
    
    
    # Horizontal Sweeps
    if len(ys) >= 2:
        for i in range(len(ys)-1):
            y_low = ys[i]
            y_high = ys[i+1]
            candidate_y = (y_low + y_high) / 2.0
            sweep_line = LineString([(minx - 1, candidate_y), (maxx + 1, candidate_y)])
            inter = polygon.boundary.intersection(sweep_line)
            pts = extract_points_from_intersection(inter)
            pts = sorted(pts, key=lambda p: p.x)
            
            gaps = []
            if len(pts) > 2:
                # Each pair of intersection points beyond the first can be a gap
                for j in range(1, len(pts)-1, 2):
                    if j+1 < len(pts):
                        gap = pts[j+1].x - pts[j].x
                        total_horizontal_gap += gap
                        max_horizontal_gap = max(max_horizontal_gap, gap)
                        gaps.append((pts[j], pts[j+1], gap))
                        
            band = Polygon([(minx, y_low), (maxx, y_low), (maxx, y_high), (minx, y_high)])
            band_in_poly = polygon.intersection(band)
            band_in_poly = band_in_poly if (not band_in_poly.is_empty) else None   
            is_troublesome = len(pts) > 2
            if is_troublesome and band_in_poly is not None:
                horizontal_union = band_in_poly if horizontal_union is None else horizontal_union.union(band_in_poly)
                
            details["horizontal"].append({
                    "direction": "horizontal",
                    "candidate_index": i,
                    "candidate_value": candidate_y,
                    "sweep_line": sweep_line,
                    "points": pts,
                    "gaps": gaps,
                    "total_gap": sum(g[2] for g in gaps) if gaps else 0.0,
                    "band": band_in_poly,
                    "is_troublesome": is_troublesome,
                })
    
    # Vertical
    if len(xs) >= 2:
        for i in range(len(xs)-1):
            x_left = xs[i]
            x_right = xs[i+1]
            candidate_x = (x_left + x_right) / 2.0
            sweep_line = LineString([(candidate_x, miny - 1), (candidate_x, maxy + 1)])
            inter = polygon.boundary.intersection(sweep_line)
            pts = extract_points_from_intersection(inter)
            pts = sorted(pts, key=lambda p: p.y)
            
            gaps = []
            if len(pts) > 2:
                for j in range(1, len(pts)-1, 2):
                    if j+1 < len(pts):
                        gap = pts[j+1].y - pts[j].y
                        total_vertical_gap += gap
                        max_vertical_gap = max(max_vertical_gap, gap)
                        gaps.append((pts[j], pts[j+1], gap))
                        
            band = Polygon([(x_left, miny), (x_right, miny), (x_right, maxy), (x_left, maxy)])
            band_in_poly = polygon.intersection(band)
            band_in_poly = band_in_poly if (not band_in_poly.is_empty) else None   
            is_troublesome = len(pts) > 2
            if is_troublesome and band_in_poly is not None:
                vertical_union = band_in_poly if vertical_union is None else vertical_union.union(band_in_poly)
                
            details["vertical"].append({
                    "direction": "vertical",
                    "candidate_index": i,
                    "candidate_value": candidate_x,
                    "sweep_line": sweep_line,
                    "points": pts,
                    "gaps": gaps,
                    "total_gap": sum(g[2] for g in gaps) if gaps else 0.0,
                    "band": band_in_poly,
                    "is_troublesome": is_troublesome,
                })
            
    aggregated_metrics = {
        "max_horizontal_gap": max_horizontal_gap,
        "total_horizontal_gap": total_horizontal_gap,
        "max_vertical_gap": max_vertical_gap,
        "total_vertical_gap": total_vertical_gap,
        "combined_gap": total_horizontal_gap + total_vertical_gap,
        "horizontal_union": horizontal_union,
        "vertical_union": vertical_union
    }
    return aggregated_metrics, details



##############################################################################
# GREEDY TROUBLESOME BAND SPLITTING
##############################################################################


def greedy_partition(polygon, max_depth=10, tolerance=1):
    """
    Returns:
        pieces: List[Polygon]
        greedy_info: {
            "passes": [
                {
                  "depth": int,
                  "subject_polygon": Polygon,   # polygon analyzed at this pass
                  "metrics": dict,              # from quantify_gap_severity(...)
                  "cut_line": LineString | None,
                  "horiz_union": Polygon | None,
                  "vert_union": Polygon | None,
                  "details": dict,              # per-candidate artifacts (H/V)
                },
                ...
            ]
        }
    """
    pieces, passes = _greedy_partition(polygon, depth=0, max_depth=max_depth, tolerance=tolerance)
    return pieces, {"passes": passes}


def _greedy_partition(polygon, depth, max_depth, tolerance):
    # Base case
    h_trouble, v_trouble = is_polygon_troublesome(polygon, tolerance)
    is_troublesome = (h_trouble and v_trouble)
    if depth >= max_depth or not is_troublesome:
        return [polygon], []

    # Compute unions + per-candidate details for THIS polygon at this depth
    aggregated_metrics, details = quantify_gap_severity(polygon, tolerance)
    horiz_union = aggregated_metrics["horizontal_union"]
    vert_union = aggregated_metrics["vertical_union"]

    minx, miny, maxx, maxy = polygon.bounds
    cut_line = None

    # Choose cut
    if horiz_union is not None and vert_union is not None:
        if aggregated_metrics["total_horizontal_gap"] >= aggregated_metrics["total_vertical_gap"]:
            candidate_y = (horiz_union.bounds[1] + horiz_union.bounds[3]) / 2.0
            cut_line = LineString([(minx - 1, candidate_y), (maxx + 1, candidate_y)])
        else:
            candidate_x = (vert_union.bounds[0] + vert_union.bounds[2]) / 2.0
            cut_line = LineString([(candidate_x, miny - 1), (candidate_x, maxy + 1)])
    elif horiz_union is not None:
        candidate_y = (horiz_union.bounds[1] + horiz_union.bounds[3]) / 2.0
        cut_line = LineString([(minx - 1, candidate_y), (maxx + 1, candidate_y)])
    elif vert_union is not None:
        candidate_x = (vert_union.bounds[0] + vert_union.bounds[2]) / 2.0
        cut_line = LineString([(candidate_x, miny - 1), (candidate_x, maxy + 1)])
    else:
        # Record the pass 
        return [polygon], [{
            "depth": depth,
            "subject_polygon": polygon,
            "metrics": aggregated_metrics,
            "cut_line": None,
            "horiz_union": None,
            "vert_union": None,
            "details": details,
        }]

    # Try split
    try:
        splitted = split(polygon, cut_line)
    except Exception as e:
        print("Splitting failed:", e)
        return [polygon], [{
            "depth": depth,
            "subject_polygon": polygon,
            "metrics": aggregated_metrics,
            "cut_line": cut_line,
            "horiz_union": horiz_union,
            "vert_union": vert_union,
            "details": details,
        }]

    # Fallback if line didn't split
    if len(splitted.geoms) <= 1:
        if cut_line.coords[0][1] == cut_line.coords[1][1]:  # horizontal
            if vert_union is not None:
                candidate_x = (vert_union.bounds[0] + vert_union.bounds[2]) / 2.0
                cut_line = LineString([(candidate_x, miny - 1), (candidate_x, maxy + 1)])
                splitted = split(polygon, cut_line)
        else:  # vertical
            if horiz_union is not None:
                candidate_y = (horiz_union.bounds[1] + horiz_union.bounds[3]) / 2.0
                cut_line = LineString([(minx - 1, candidate_y), (maxx + 1, candidate_y)])
                splitted = split(polygon, cut_line)

    if len(splitted.geoms) <= 1:
        return [polygon], [{
            "depth": depth,
            "subject_polygon": polygon,
            "metrics": aggregated_metrics,
            "cut_line": cut_line,
            "horiz_union": horiz_union,
            "vert_union": vert_union,
            "details": details,
        }]

    # Record this pass
    passes = [{
        "depth": depth,
        "subject_polygon": polygon,
        "metrics": aggregated_metrics,
        "cut_line": cut_line,
        "horiz_union": horiz_union,
        "vert_union": vert_union,
        "details": details,
    }]

    # Recurse on pieces
    pieces = []
    for piece in splitted.geoms:
        if piece.is_empty:
            continue
        if piece.geom_type == "Polygon":
            child_pieces, child_passes = _greedy_partition(piece, depth + 1, max_depth, tolerance)
            pieces.extend(child_pieces)
            passes.extend(child_passes)
        elif piece.geom_type == "MultiPolygon":
            for poly_sub in piece.geoms:
                child_pieces, child_passes = _greedy_partition(poly_sub, depth + 1, max_depth, tolerance)
                pieces.extend(child_pieces)
                passes.extend(child_passes)

    return pieces, passes



def merge_partitions(partitions, tolerance=1e-6):
    """
    Attempts to merge adjacent partitions if their union results satisfies uniaxial criterion
    Only partitions that share a border (with shared length >= tolerance) are considered.
    """
    iteration = 0
    merged_any = True
    merge_log = {"iterations": []}

    while merged_any:
        merged_any = False
        iteration += 1
        iter_info = {"index": iteration, "steps": []}

        new_partitions = []
        used_indices = set()

        for i in range(len(partitions)):
            if i in used_indices:
                continue

            poly_i = partitions[i]

            for j in range(i + 1, len(partitions)):
                if j in used_indices:
                    continue

                poly_j = partitions[j]
                inter = poly_i.boundary.intersection(poly_j.boundary)

                # Compute shared length
                shared_length = 0.0
                if not inter.is_empty:
                    if inter.geom_type == 'LineString':
                        shared_length = inter.length
                    elif inter.geom_type == 'MultiLineString':
                        shared_length = sum(line.length for line in inter.geoms)
                    elif inter.geom_type == 'GeometryCollection':
                        for geom in inter.geoms:
                            if geom.geom_type == 'LineString':
                                shared_length += geom.length
                            elif geom.geom_type == 'MultiLineString':
                                shared_length += sum(g.length for g in geom.geoms)

                step = {
                    "i": i,
                    "j": j,
                    "shared_length": shared_length,
                    "adjacent": shared_length >= tolerance,
                    "shared_geom": inter if (not inter.is_empty) else None,
                    "candidate_union": None,
                    "result": None,
                    "troublesome_flags": None,
                    "poly_i": poly_i,  # snapshot
                    "poly_j": poly_j,  # snapshot
                    "merged_result": None,
                }

                # If not adjacent, skip early
                if shared_length < tolerance:
                    step["result"] = "skip_nonadjacent"
                    iter_info["steps"].append(step)
                    continue

                # Compute union
                candidate_union = poly_i.union(poly_j)
                step["candidate_union"] = candidate_union

                if candidate_union.is_empty:
                    step["result"] = "skip_empty"
                    iter_info["steps"].append(step)
                    continue

                # Normalize union to a single Polygon if possible
                if candidate_union.geom_type == 'MultiPolygon':
                    step["result"] = "skip_multi"
                    iter_info["steps"].append(step)
                    continue
                if candidate_union.geom_type == 'GeometryCollection':
                    polys = [g for g in candidate_union.geoms if g.geom_type == 'Polygon']
                    if len(polys) == 1:
                        candidate_union = polys[0]
                    else:
                        step["result"] = "skip_multi"
                        iter_info["steps"].append(step)
                        continue

                # Check troublesome: require NOT troublesome (i.e., at least one direction OK)
                h_trouble, v_trouble = is_polygon_troublesome(candidate_union, tolerance)
                step["troublesome_flags"] = (h_trouble, v_trouble)
                is_troublesome_both = (h_trouble and v_trouble)
                if is_troublesome_both:
                    step["result"] = "skip_troublesome"
                    iter_info["steps"].append(step)
                    continue

                # Accept merge
                poly_i = candidate_union
                used_indices.add(j)
                merged_any = True
                step["result"] = "merged"
                step["merged_result"] = candidate_union
                iter_info["steps"].append(step)

            new_partitions.append(poly_i)
            used_indices.add(i)

        partitions = new_partitions
        merge_log["iterations"].append(iter_info)

    merge_log["final_partitions"] = partitions
    return partitions, merge_log





