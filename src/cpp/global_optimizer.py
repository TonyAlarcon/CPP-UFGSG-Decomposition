import math
from functools import lru_cache
from typing import List, Sequence

from cpp.utils.helpers import CandidateOption

def adjust_candidate_options(candidate_options: Sequence[Sequence[CandidateOption]],
                             penalty: float = 10, tol: float = 1e-7
                             ) -> List[List[CandidateOption]]:
    """
    If candidates have nearly equal cost, add a penalty to the ones with more turns.
    Preserves optional fields (e.g., path).
    """
    adjusted: List[List[CandidateOption]] = []
    for partition in candidate_options:
        part_adj: List[CandidateOption] = []
        for cand in partition:
            same_cost_turns = [c.turns for c in partition if abs(c.cost - cand.cost) < tol]
            min_turns = min(same_cost_turns) if same_cost_turns else cand.turns
            extra = penalty * max(0, cand.turns - min_turns)
            part_adj.append(CandidateOption(
                entry=cand.entry,
                exit=cand.exit,
                cost=cand.cost + extra,
                turns=cand.turns,
                path=cand.path  # keep it if present
            ))
        adjusted.append(part_adj)
    return adjusted

def held_karp(candidate_options: Sequence[Sequence[CandidateOption]]):
    """
    Choose ordering + one candidate per partition to minimize total cost:
      sum(candidate.cost) + sum(connection_costs between consecutive picks).
    """
    candidate_options = adjust_candidate_options(candidate_options, penalty=1)

    N = len(candidate_options)

    @lru_cache(maxsize=None)
    def dp(mask: int, last_part: int, last_cand: int):
        if mask == (1 << N) - 1:
            return 0.0, []

        best_cost = float('inf')
        best_path = None
        prev_cand = candidate_options[last_part][last_cand]
        for j in range(N):
            if (mask >> j) & 1:
                continue    
            for cand_idx, cand in enumerate(candidate_options[j]):
                conn = math.hypot(prev_cand.exit[0] - cand.entry[0],
                                  prev_cand.exit[1] - cand.entry[1])
                new_mask = mask | (1 << j)
                sub_cost, sub_path = dp(new_mask, j, cand_idx)
                total = conn + cand.cost + sub_cost
                if total < best_cost:
                    best_cost = total
                    best_path = [(j, cand_idx)] + sub_path
        return best_cost, best_path

    overall_best = float('inf')
    overall_path = None
    for i in range(N):
        for cand_idx, cand in enumerate(candidate_options[i]):
            init_mask = 1 << i
            cost_rest, path_rest = dp(init_mask, i, cand_idx)
            total = cand.cost + cost_rest
            if total < overall_best:
                overall_best = total
                overall_path = [(i, cand_idx)] + path_rest

    return overall_best, overall_path
