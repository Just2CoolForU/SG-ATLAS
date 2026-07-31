import numpy as np
from scipy.stats import binom, false_discovery_control

def score_all_candidates(user_fragments, cached_structures, min_trials_threshold=3):
    """
    Scores all cached PDB structures against user-provided cleavage fragment boundaries.
    Applies Benjamini-Hochberg FDR correction to handle multiple testing across ~200 structures.
    """
    results = []
    raw_p_values = []
    
    # Step 1: Compute raw p-values for each candidate structure
    for struct in cached_structures:
        # Evaluate boundary matches (k) out of total trials (n)
        k_matches, n_trials, p_cut = evaluate_structure_matches(user_fragments, struct)
        
        # Survival function sf = 1 - cdf (probability of getting >= k matches by chance)
        # We subtract 1 from k to include k in the upper tail probability
        raw_p = binom.sf(k_matches - 1, n_trials, p_cut) if n_trials > 0 else 1.0
        raw_p_values.append(raw_p)
        
        results.append({
            "pdb_id": struct["pdb_id"],
            "title": struct["title"],
            "polymorph": struct["polymorph"],
            "disease": struct["disease"],
            "matches": f"{k_matches}/{n_trials}",
            "k_matches": k_matches,
            "n_trials": n_trials,
            "raw_p": raw_p,
            "raw_confidence": (1.0 - raw_p) * 100.0
        })
        
    # Step 2: Apply Benjamini-Hochberg FDR Correction across all hypothesis tests
    if raw_p_values:
        adjusted_p_values = false_discovery_control(raw_p_values, method='bh')
    else:
        adjusted_p_values = []
        
    # Step 3: Compute FDR-adjusted confidence scores & check power
    for i, res in enumerate(results):
        adj_p = adjusted_p_values[i]
        # Adjusted confidence cannot exceed raw confidence
        adj_p = max(adj_p, res["raw_p"]) 
        adj_confidence = max(0.0, (1.0 - adj_p) * 100.0)
        
        res["adj_p"] = adj_p
        res["confidence"] = round(adj_confidence, 1)
        res["low_power_warning"] = res["n_trials"] <= min_trials_threshold

    # Sort results by FDR-adjusted confidence (descending)
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results