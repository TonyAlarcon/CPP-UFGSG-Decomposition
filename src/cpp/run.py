from cpp.global_optimizer import held_karp
from cpp.decomposition import greedy_partition, merge_partitions
from cpp.parallel_track import ParallelTrackSweepCartesian
from cpp.picklestore import PickleDecompStore
from cpp.utils.helpers import (
    count_turns,
    cells_inside_polygon_ids,
    distribute_cells_to_subclusters,
)
from cpp.utils.viz import plot_polygons
import os
import argparse
 
TOL = 1

def run_pipeline(poly, save_path = None, store=None):
    
    decomposition = 'ours'
    cell_size = 1
    max_depth = 40
    
   
    partitions, details = greedy_partition(poly, max_depth=max_depth, tolerance=TOL)
    merged_partitions, merge_log = merge_partitions(partitions, tolerance=1e-6)
    cell_ids = cells_inside_polygon_ids(poly, cell_size) 
    subcluster = distribute_cells_to_subclusters(cell_ids, cell_size, merged_partitions)
    
    path_options = []
    for subcluster_id, cell_list in subcluster.items():
        if not cell_list:
            print(f"Warning: Subcluster {subcluster_id} is empty.")
            continue
        polygon = merged_partitions[subcluster_id]

        candidate_opts = ParallelTrackSweepCartesian.get_candidate_options(cell_list, polygon)
        path_options.append(candidate_opts)


    best_cost, best_path = held_karp(path_options)
    print("Best global cost:", best_cost)
    
    
    paths = []
    for part_index, cand_index in best_path:
        print(f"  Partition {part_index}, candidate {cand_index}")        
        paths.append(path_options[part_index][cand_index].path)

    # Initialize lists to store the full path and the global connectors.
    global_path = []
    global_connectors = []

    # Iterate through the best candidate choices for each partition.
    for idx, (part_idx, cand_idx) in enumerate(best_path):
        candidate = path_options[part_idx][cand_idx]
        
        # For the first candidate, simply add its path.
        if idx == 0:
            global_path.extend(candidate.path)
        else:
            # For subsequent candidates, avoid duplicating the joining cell.
            if candidate.path[0] == global_path[-1]:
                global_path.extend(candidate.path[1:])
            else:
                global_path.extend(candidate.path)
        
        # If not the first candidate, append a global connector from the previous partition.
        if idx > 0:
            prev_part_idx, prev_cand_idx = best_path[idx - 1]
            prev_candidate = path_options[prev_part_idx][prev_cand_idx]
            global_connectors.append((prev_candidate.exit, candidate.entry))

    plot_polygons(merged_partitions, subclusters=subcluster, cell_size=cell_size, paths=paths, global_connectors=global_connectors, save_path=save_path)
    

    return global_path



if __name__ == "__main__":
    STORE_PATH = 'src/cpp/artifacts/decompositions.pkl'
    OUTDIR = 'src/cpp/artifacts/results'
    os.makedirs(OUTDIR, exist_ok=True)

    # ---- CLI  ----
    parser = argparse.ArgumentParser(description="Run CPP pipeline (ours) on selected polygons.")
    parser.add_argument("-p", "--polygon", nargs="*", help="Polygon names like P12. Supports multiple or comma-separated.")
    args = parser.parse_args()

    store = PickleDecompStore(STORE_PATH, autosave=False)
    print(store.summarize())

    valid_names = store.list_names()
    print(valid_names)

    # Build include from CLI or default to all
    if args.polygon:
        include = []
        for tok in args.polygon:
            include.extend([x for x in tok.split(",") if x])
        # filter to valid names
        include = [n for n in include if n in valid_names]
        if not include:
            print("No matching polygons found. Running all.")
            include = valid_names
    else:
        include = valid_names

    for name in include:
        print(f"Processing {name}")
        poly = store.get(name).base
        save_path = f'{OUTDIR}/{name}.png'
        path = run_pipeline(poly, save_path=save_path, store=store)
        print(f"#Number of Turns {count_turns(path)}")