"""
sg_atlas_fragments.py — predicts Proteinase K fragment ladders from cached
SASA profiles, and matches a lab's real observed fragment masses (from a
gel or mass spec) against every cached structure to infer likely strain.

This is the translational piece the whole project has been building
toward: everything so far computes accessibility. This module is what
actually turns that into something a wet-lab researcher can compare
against their own bench data.

METHOD (and its real limitations -- read before trusting output):
  1. Convert raw SASA to Relative Solvent Accessibility (RSA) using the
     Tien et al. 2013 theoretical MaxASA reference values (PLOS ONE,
     verified against the published table, not estimated) -- this
     normalizes for the fact that a big residue like Trp has more
     absolute SASA than a small one like Ala even at equal *relative*
     exposure, so comparing raw SASA across different amino acids would
     be misleading.
  2. Residues above an RSA threshold are predicted PK cleavage sites.
     Proteinase K is broad-specificity and cleaves preferentially at
     exposed, flexible backbone -- this is a real, standard simplifying
     assumption, but PK does have some secondary preference for large
     hydrophobic/aromatic residues at the cleavage position that this
     model does NOT capture. Treat cleavage-site predictions as a
     first-order approximation, not a precise enzymatic model.
  3. Consecutive cleavage sites define fragments; each fragment's mass is
     computed from standard average amino acid residue masses (the same
     constants used by tools like ExPASy's MW calculator).
  4. A lab's observed fragment masses (from SDS-PAGE or MS) are matched
     against every cached structure's predicted ladder, scoring how many
     observed fragments have a close-mass predicted counterpart.

This is a hypothesis-ranking tool, not a diagnostic. A high match score
means "this structure's predicted ladder is consistent with what you
observed" -- it does not by itself prove the sample IS that structural
class, especially since predicted cleavage-site propensity is itself an
approximation (see point 2).
"""
import sqlite3
from scipy.stats import binom, false_discovery_control

# Tien et al. 2013 theoretical MaxASA values (Å²), PLOS ONE 8(11):e80635,
# verified against the published table (not estimated).
MAX_ASA = {
    "A": 129.0, "R": 274.0, "N": 195.0, "D": 193.0, "C": 167.0,
    "E": 223.0, "Q": 225.0, "G": 104.0, "H": 224.0, "I": 197.0,
    "L": 201.0, "K": 236.0, "M": 224.0, "F": 240.0, "P": 159.0,
    "S": 155.0, "T": 172.0, "W": 285.0, "Y": 263.0, "V": 174.0,
}

# Standard average amino acid residue masses (Da) -- mass contributed by
# each residue within a peptide chain (i.e. amino acid mass minus water,
# since peptide bond formation releases one water per bond). Same
# constants used by standard protein MW calculators (e.g. ExPASy).
RESIDUE_MASS = {
    "G": 57.0519, "A": 71.0788, "S": 87.0782, "P": 97.1167, "V": 99.1326,
    "T": 101.1051, "C": 103.1388, "L": 113.1594, "I": 113.1594, "N": 114.1038,
    "D": 115.0886, "Q": 128.1307, "K": 128.1741, "E": 129.1155, "M": 131.1926,
    "H": 137.1411, "F": 147.1766, "R": 156.1875, "Y": 163.1760, "W": 186.2132,
}
WATER_MASS = 18.0153  # added once per fragment to cap the termini


def compute_rsa(sasa, amino_acid):
    """Relative Solvent Accessibility: SASA normalized by the residue's
    theoretical maximum, so residues of different sizes are comparable
    on the same 0-1 scale. Returns None for non-standard residues (already
    filtered upstream, but defensive here too)."""
    max_asa = MAX_ASA.get(amino_acid)
    if max_asa is None:
        return None
    return min(sasa / max_asa, 1.5)  # allow modest overshoot from probe geometry, cap runaway values


def predict_cleavage_sites(profile_chain, rsa_threshold=0.45, cluster_window=3):
    """Given one chain's {residue: {"sasa":..., "aa":...}} profile, return
    the sorted list of residue numbers predicted to be PK cleavage sites.
    """
    candidates = []
    for resseq in sorted(profile_chain.keys()):
        d = profile_chain[resseq]
        rsa = compute_rsa(d["sasa"], d["aa"])
        if rsa is not None and rsa >= rsa_threshold:
            candidates.append((resseq, rsa))

    if not candidates:
        return []

    # cluster adjacent candidates (within cluster_window residues of the
    # previous one) and keep only the most-exposed residue per cluster
    clusters = [[candidates[0]]]
    for resseq, rsa in candidates[1:]:
        if resseq - clusters[-1][-1][0] <= cluster_window:
            clusters[-1].append((resseq, rsa))
        else:
            clusters.append([(resseq, rsa)])

    sites = [max(cluster, key=lambda c: c[1])[0] for cluster in clusters]
    return sorted(sites)


def generate_fragment_ladder(profile_chain, cleavage_sites):
    """Break the chain into fragments at predicted cleavage sites and
    compute each fragment's average mass."""
    residues = sorted(profile_chain.keys())
    if not residues:
        return []

    cleavage_set = set(cleavage_sites)
    fragments = []
    frag_start = residues[0]
    for i, resseq in enumerate(residues):
        is_last = i == len(residues) - 1
        if resseq in cleavage_set or is_last:
            frag_end = resseq
            frag_residues = [r for r in residues if frag_start <= r <= frag_end]
            mass = sum(RESIDUE_MASS.get(profile_chain[r]["aa"], 110.0) for r in frag_residues) + WATER_MASS
            fragments.append({
                "start": frag_start, "end": frag_end,
                "length": len(frag_residues), "mass_da": round(mass, 1),
            })
            frag_start = resseq + 1

    return sorted(fragments, key=lambda f: -f["mass_da"])


def predicted_ladder_for_structure(pdb_id, mode="full-core", rsa_threshold=0.45, db_path="sg_atlas_cache.db"):
    """Load a structure's cached profile and return its predicted fragment
    ladder for its best chain."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT chain_id, residue, amino_acid, sasa FROM residues WHERE pdb_id=? AND mode=?",
        (pdb_id.upper(), mode),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None

    by_chain = {}
    for cid, resseq, aa, sasa in rows:
        by_chain.setdefault(cid, {})[resseq] = {"aa": aa, "sasa": sasa}

    best_chain = max(by_chain, key=lambda c: len(by_chain[c]))
    sites = predict_cleavage_sites(by_chain[best_chain], rsa_threshold)
    ladder = generate_fragment_ladder(by_chain[best_chain], sites)
    return {"pdb_id": pdb_id.upper(), "chain": best_chain, "cleavage_sites": sites, "fragments": ladder}


def compute_match_confidence(n_trials, n_matches, chance_probability):
    """
    Statistically grounded confidence, not just a raw match fraction.
    """
    if n_trials == 0:
        return 1.0, 0.0  # no evidence at all
    chance_probability = min(max(chance_probability, 1e-9), 1.0)
    p_value = float(binom.sf(n_matches - 1, n_trials, chance_probability))
    return p_value, 1.0 - p_value


def match_fragments_by_position(observed_fragments, pdb_id, mode="full-core", tolerance_window=2,
                                  db_path="sg_atlas_cache.db"):
    """
    The precision-matching mode: checks whether this structure's predicted 
    cleavage sites include something within tolerance_window residues. 
    """
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT chain_id, residue, amino_acid, sasa FROM residues WHERE pdb_id=? AND mode=?",
        (pdb_id.upper(), mode),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None

    by_chain = {}
    for cid, resseq, aa, sasa in rows:
        by_chain.setdefault(cid, {})[resseq] = {"aa": aa, "sasa": sasa}
    best_chain = max(by_chain, key=lambda c: len(by_chain[c]))
    profile = by_chain[best_chain]
    residues = sorted(profile.keys())
    chain_start, chain_end = residues[0], residues[-1]

    predicted_sites = predict_cleavage_sites(profile)

    trials = 0
    matches = 0
    boundary_detail = []
    for start, end in observed_fragments:
        for boundary, label, is_natural_end in [
            (start, f"start of {start}-{end}", start <= chain_start),
            (end, f"end of {start}-{end}", end >= chain_end),
        ]:
            if is_natural_end:
                continue
            trials += 1
            hit = any(abs(boundary - s) <= tolerance_window for s in predicted_sites)
            if hit:
                matches += 1
            boundary_detail.append({"boundary_residue": boundary, "fragment": label, "matched": hit})

    chain_length = chain_end - chain_start + 1
    covered_positions = set()
    for s in predicted_sites:
        for offset in range(-tolerance_window, tolerance_window + 1):
            covered_positions.add(s + offset)
    chance_probability = len(covered_positions & set(range(chain_start, chain_end + 1))) / chain_length

    p_value, confidence = compute_match_confidence(trials, matches, chance_probability)

    return {
        "pdb_id": pdb_id.upper(), "chain": best_chain,
        "trials": trials, "matches": matches,
        "chance_probability": round(chance_probability, 4),
        "p_value": round(p_value, 5), "confidence": round(confidence, 4),
        "boundary_detail": boundary_detail,
    }


def score_all_candidates(observed_fragments, tolerance_window=2, db_path="sg_atlas_cache.db", min_trials_threshold=3):
    """
    Run position-based matching against every cached structure.
    Applies Benjamini-Hochberg FDR correction to handle multiple testing across ~200 structures.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT DISTINCT pdb_id FROM structures WHERE mode='full-core'")
    all_pdb_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    results = []
    raw_p_values = []
    
    # Step 1: Compute raw p-values for each candidate structure
    for pdb_id in all_pdb_ids:
        r = match_fragments_by_position(observed_fragments, pdb_id, tolerance_window=tolerance_window, db_path=db_path)
        if r is not None and r["trials"] > 0:
            raw_p = r["p_value"]
            raw_p_values.append(raw_p)
            results.append(r)
            
    # Step 2: Apply Benjamini-Hochberg FDR Correction
    if raw_p_values:
        adjusted_p_values = false_discovery_control(raw_p_values, method='bh')
    else:
        adjusted_p_values = []
        
    # Step 3: Compute FDR-adjusted confidence scores & check power
    for i, res in enumerate(results):
        adj_p = adjusted_p_values[i]
        adj_p = max(adj_p, res["p_value"]) # Adjusted p-value cannot be lower than raw p-value
        adj_confidence = max(0.0, 1.0 - adj_p)
        
        res["adj_p"] = round(adj_p, 5)
        res["confidence"] = round(adj_confidence, 4)
        res["low_power_warning"] = res["trials"] <= min_trials_threshold

    # Sort results by FDR-adjusted confidence (descending)
    return sorted(results, key=lambda r: -r["confidence"])


def theoretical_max_fragment(profile_chain):
    """The largest possible fragment size for this chain."""
    return sum(RESIDUE_MASS.get(d["aa"], 110.0) for d in profile_chain.values()) + WATER_MASS


def match_observed_fragments(observed_masses, tolerance_pct=5.0, rsa_threshold=0.45, db_path="sg_atlas_cache.db"):
    """
    The core lab-facing feature: given a list of fragment masses a
    researcher actually observed, score every cached structure's predicted ladder.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT DISTINCT pdb_id FROM structures WHERE mode='full-core'")
    all_pdb_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    results = []
    for pdb_id in all_pdb_ids:
        ladder_info = predicted_ladder_for_structure(pdb_id, rsa_threshold=rsa_threshold, db_path=db_path)
        if ladder_info is None or not ladder_info["fragments"]:
            continue
        predicted_masses = [f["mass_da"] for f in ladder_info["fragments"]]
        max_possible = max(predicted_masses) 

        matched = 0
        evaluable = 0
        match_details = []
        for obs in observed_masses:
            if obs > max_possible * 1.05:
                match_details.append({"observed": obs, "closest_predicted": None, "pct_diff": None,
                                       "matched": False, "exceeds_max": True,
                                       "structure_max_da": round(max_possible, 1)})
                continue
            evaluable += 1
            best = min(predicted_masses, key=lambda p: abs(p - obs))
            pct_diff = abs(best - obs) / obs * 100
            is_match = pct_diff <= tolerance_pct
            if is_match:
                matched += 1
            match_details.append({"observed": obs, "closest_predicted": best, "pct_diff": round(pct_diff, 1),
                                    "matched": is_match, "exceeds_max": False})

        score = matched / evaluable if evaluable > 0 else 0.0
        results.append({
            "pdb_id": pdb_id, "score": round(score, 3),
            "matched_count": matched, "total_observed": len(observed_masses),
            "evaluable_count": evaluable,
            "details": match_details,
        })

    return sorted(results, key=lambda r: (-r["evaluable_count"], -r["score"]))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Match observed PK-digestion fragment masses against every "
                                               "cached structure's predicted ladder.")
    ap.add_argument("--observed", nargs="+", type=float, required=True,
                     help="Observed fragment masses in Da, e.g. --observed 4200 8100 12300")
    ap.add_argument("--tolerance", type=float, default=5.0, help="Match tolerance in %% (default 5.0)")
    ap.add_argument("--rsa-threshold", type=float, default=0.45,
                     help="RSA cutoff for predicted cleavage sites (default 0.2)")
    ap.add_argument("--cache-db", type=str, default="sg_atlas_cache.db")
    ap.add_argument("--top", type=int, default=10, help="Show top N ranked structures (default 10)")
    args = ap.parse_args()

    results = match_observed_fragments(args.observed, tolerance_pct=args.tolerance,
                                        rsa_threshold=args.rsa_threshold, db_path=args.cache_db)
    print(f"\nRanked matches for observed fragments {args.observed} (tolerance {args.tolerance}%):\n")
    for r in results[:args.top]:
        exceeded = [d["observed"] for d in r["details"] if d.get("exceeds_max")]
        note = f"  [{len(exceeded)} mass(es) exceed this structure's theoretical max, excluded: {exceeded}]" if exceeded else ""
        print(f"  {r['pdb_id']}: score={r['score']} ({r['matched_count']}/{r['evaluable_count']} evaluable matched, "
              f"{r['total_observed']} total observed){note}")
    if not results:
        print("  No structures found in cache -- run batch_fetch_all.py first to populate it.")