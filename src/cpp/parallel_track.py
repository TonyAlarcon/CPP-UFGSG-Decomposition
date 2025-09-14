import math
import statistics
from typing import List
from cpp.decomposition import  is_polygon_troublesome
from cpp.utils.helpers import count_turns,  CandidateOption
 
TOL = 1


class ParallelTrackSweepCartesian:
    @staticmethod
    def compute_cell_spacing(waypoints, axis_index, epsilon=1e-6):
        """
        Given a list of waypoints (each a tuple, e.g. (x, y, ...)) and an axis index (0 for x, 1 for y),
        compute the median spacing between adjacent waypoints along that axis.
        """
        coords = sorted(p[axis_index] for p in waypoints)
        diffs = [coords[i+1] - coords[i] for i in range(len(coords) - 1) if coords[i+1] - coords[i] > epsilon]
        if diffs:
            return statistics.median(diffs)
        else:
            return 0.0  # fallback if there is no variation

    @staticmethod
    def group_into_lanes(waypoints, axis_index, spacing):
        """
        Groups waypoints into lanes (bins) along the specified axis.
        Each waypoint p is assigned a lane key based on:
            key = round((p[axis_index] - min_value) / spacing)
        Returns a dictionary mapping lane keys to lists of waypoints.
        """
        if not waypoints:
            return {}
        
        min_val = min(p[axis_index] for p in waypoints)
        lanes = {}
        if spacing == 0.0:
            lanes[0] = list(waypoints)
        else:
            for p in waypoints:
                key = round((p[axis_index] - min_val) / spacing)
                lanes.setdefault(key, []).append(p)
        return lanes

    @staticmethod
    def compute_sweep_path(waypoints, bin_axis, sort_axis,
                        reverse_bin_order=False,
                        reverse_lane_order=False):
        """
        Create a sweep path by binning the waypoints along 'bin_axis'
        using an automatically derived spacing, then ordering each lane
        by 'sort_axis' in a zigzag pattern. We can also reverse the bin
        order or reverse the lane direction to simulate starting at a
        different corner.
        """
        spacing = ParallelTrackSweepCartesian.compute_cell_spacing(waypoints, bin_axis)
        lanes = ParallelTrackSweepCartesian.group_into_lanes(waypoints, bin_axis, spacing)
        
        # Get all lane keys, and maybe reverse them:
        ordered_keys = sorted(lanes.keys(), reverse=reverse_bin_order)
        
        path = []
        for i, key in enumerate(ordered_keys):
            lane = lanes[key]
            # Normally, if i is even, we go ascending on sort_axis; if odd, descending.
            # But if we want to "flip" the zigzag, we can incorporate reverse_lane_order:
            
            even_lane_should_ascend = ((i % 2 == 0) and not reverse_lane_order) or \
                                    ((i % 2 == 1) and reverse_lane_order)
            
            if even_lane_should_ascend:
                sorted_lane = sorted(lane, key=lambda p: p[sort_axis])
            else:
                sorted_lane = sorted(lane, key=lambda p: p[sort_axis], reverse=True)
            
            path.extend(sorted_lane)
        return path

    @staticmethod
    def euclidean_distance(p1, p2):
        """
        Compute the Euclidean distance between two points p1 and p2.
        """
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    @staticmethod
    def total_path_length(path):
        """
        Compute the total length of the path connecting the waypoints sequentially.
        """
        length = 0.0
        for i in range(1, len(path)):
            length += ParallelTrackSweepCartesian.euclidean_distance(path[i-1], path[i])
        return length




    def corner_variants_for_direction(waypoints, bin_axis, sort_axis):
        """
        Returns the 4 possible corner-start paths for a given sweep direction:
        1) normal bin order, normal lane order       # top left corner
        2) normal bin order, reversed lane order     # top right corner
        3) reversed bin order, normal lane order     # bottom left corner
        4) reversed bin order, reversed lane order   # bottom right corner
        """
        variants = []
        variants.append(ParallelTrackSweepCartesian.compute_sweep_path(
            waypoints, bin_axis, sort_axis,
            reverse_bin_order=False,
            reverse_lane_order=False
        ))
        variants.append(ParallelTrackSweepCartesian.compute_sweep_path(
            waypoints, bin_axis, sort_axis,
            reverse_bin_order=False,
            reverse_lane_order=True
        ))
        variants.append(ParallelTrackSweepCartesian.compute_sweep_path(
            waypoints, bin_axis, sort_axis,
            reverse_bin_order=True,
            reverse_lane_order=False
        ))
        variants.append(ParallelTrackSweepCartesian.compute_sweep_path(
            waypoints, bin_axis, sort_axis,
            reverse_bin_order=True,
            reverse_lane_order=True
        ))
        return variants
    
    
    @staticmethod
    def get_candidate_options(waypoints, polygon=None):
        """
        Build candidate sweep paths (corner variants) and return final
        CandidateOption objects (entry/exit/cost/turns/path).
        """
        # Decide allowed orientations
        if polygon:
            
            h_trouble, v_trouble = is_polygon_troublesome(polygon, 1)
            horizontal_ok, vertical_ok = (not h_trouble, not v_trouble)
        else:
            horizontal_ok, vertical_ok = True, True

        candidate_paths = []
        if horizontal_ok or (not horizontal_ok and not vertical_ok):
            candidate_paths.extend(
                ParallelTrackSweepCartesian.corner_variants_for_direction(
                    waypoints, bin_axis=0, sort_axis=1
                )
            )
        if vertical_ok or (not vertical_ok and not horizontal_ok):
            candidate_paths.extend(
                ParallelTrackSweepCartesian.corner_variants_for_direction(
                    waypoints, bin_axis=1, sort_axis=0
                )
            )

        # Convert each path to a CandidateOption (with turns)
        out: List[CandidateOption] = []
        for path in candidate_paths:
            if not path:
                continue
            cost = ParallelTrackSweepCartesian.total_path_length(path)
            turns = count_turns(path)
            entry = path[0]
            exit_ = path[-1]
            out.append(CandidateOption(entry=entry, exit=exit_, cost=cost, turns=turns, path=path))

        
        print(f"Generated {len(out)} candidate paths.")
        return out




    



        
   
        