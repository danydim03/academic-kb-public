#!/usr/bin/env python3
import json
import math
import os
import time
import numpy as np
from collections import defaultdict

def compute_organic_layout(json_path):
    print(f"Loading {json_path}...")
    t0 = time.time()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    links = data.get("links", [])
    node_map = {n["id"]: n for n in nodes}

    doc_nodes = [n for n in nodes if n.get("type") == "document"]
    chunk_nodes = [n for n in nodes if n.get("type") == "chunk"]
    n_docs = len(doc_nodes)
    n_chunks = len(chunk_nodes)
    print(f"Total Nodes: {len(nodes)} ({n_docs} documents, {n_chunks} chunks)")
    print(f"Total Links: {len(links)}")

    doc_idx = {d["id"]: i for i, d in enumerate(doc_nodes)}

    # Map chunks to parent document
    chunk_parent = {}
    for l in links:
        if l.get("type") == "HAS_CHUNK":
            s = l["source"] if isinstance(l["source"], str) else l["source"]["id"]
            t = l["target"] if isinstance(l["target"], str) else l["target"]["id"]
            chunk_parent[t] = s

    # 1. Collect RELATED_TO edges between documents
    related_edges = []
    for l in links:
        if l.get("type") == "RELATED_TO":
            s = l["source"] if isinstance(l["source"], str) else l["source"]["id"]
            t = l["target"] if isinstance(l["target"], str) else l["target"]["id"]
            if s in doc_idx and t in doc_idx:
                w = float(l.get("value", 1.0))
                related_edges.append((doc_idx[s], doc_idx[t], w))
    print(f"Direct RELATED_TO document-to-document edges: {len(related_edges)}")

    # 2. Collect aggregate SIMILAR_TO affinities between documents
    doc_pair_sims = defaultdict(int)
    for l in links:
        if l.get("type") == "SIMILAR_TO":
            s = l["source"] if isinstance(l["source"], str) else l["source"]["id"]
            t = l["target"] if isinstance(l["target"], str) else l["target"]["id"]
            p1 = chunk_parent.get(s)
            p2 = chunk_parent.get(t)
            if p1 and p2 and p1 != p2 and p1 in doc_idx and p2 in doc_idx:
                i1, i2 = doc_idx[p1], doc_idx[p2]
                if i1 > i2:
                    i1, i2 = i2, i1
                doc_pair_sims[(i1, i2)] += 1

    sim_edges = [(i1, i2, min(5.0, 0.4 * math.sqrt(cnt))) for (i1, i2), cnt in doc_pair_sims.items()]
    print(f"Aggregated semantic similarity edges between documents: {len(sim_edges)}")

    # 3. Spacious Multi-Galaxy Cosmic Architecture
    # Each academic course forms its own distinct galaxy, spaced out so they NEVER fuse into one blob!
    courses = sorted(list(set(n.get("course") for n in doc_nodes if n.get("course"))))
    num_courses = len(courses)
    course_centers = {}
    R_GALAXY = 2500.0  # Centers of galaxies are widely separated

    for idx, c in enumerate(courses):
        phi = (2.0 * math.pi * idx) / num_courses
        course_centers[c] = np.array([
            R_GALAXY * math.cos(phi),
            R_GALAXY * math.sin(phi),
            math.sin(phi * 3.0) * 850.0
        ])

    np.random.seed(42)
    doc_pos = np.zeros((n_docs, 3))
    for i, d in enumerate(doc_nodes):
        c = d.get("course")
        center = course_centers.get(c, np.zeros(3))
        # Initial jitter inside the course galaxy
        jitter = np.random.normal(0, 320.0, 3)
        doc_pos[i] = center + jitter

    # 4. Physical Simulation: Force-Directed balancing inside galaxies and along cross-bridges
    k_intra = 360.0  # Generous document spacing within a galaxy
    iterations = 180
    dt = 0.08

    print("Running 3D multi-galaxy force simulation...")
    for it in range(iterations):
        forces = np.zeros_like(doc_pos)

        # Repulsion between documents
        for i in range(n_docs):
            diff = doc_pos[i] - doc_pos
            dist_sq = np.sum(diff * diff, axis=1, keepdims=True)
            dist = np.sqrt(np.maximum(dist_sq, 9.0))
            rep = (k_intra * k_intra) / np.maximum(dist_sq, 16.0)
            forces[i] += np.sum((diff / dist) * rep, axis=0)

        # Spring attraction on RELATED_TO edges
        for i, j, w in related_edges:
            diff = doc_pos[j] - doc_pos[i]
            dist = np.linalg.norm(diff)
            if dist < 1.0:
                dist = 1.0
            dir_vec = diff / dist
            att = (dist / k_intra) * (14.0 * w)
            att = min(att, 220.0)
            forces[i] += dir_vec * att
            forces[j] -= dir_vec * att

        # Gentle gravity toward the course galaxy center (prevents galaxies from dispersing into chaos)
        for i, d in enumerate(doc_nodes):
            c = d.get("course")
            if c in course_centers:
                diff_center = doc_pos[i] - course_centers[c]
                d_len = np.linalg.norm(diff_center)
                if d_len > 1.0:
                    forces[i] -= (diff_center / d_len) * (d_len * 0.04)

        cooling = 1.0 - (it / iterations) * 0.80
        step = forces * dt * cooling
        step_len = np.linalg.norm(step, axis=1, keepdims=True)
        max_step = 50.0 * cooling
        step = np.where(step_len > max_step, (step / np.maximum(step_len, 1e-6)) * max_step, step)
        doc_pos += step

    # Save document positions
    for i, d in enumerate(doc_nodes):
        d["x"] = round(float(doc_pos[i, 0]), 2)
        d["y"] = round(float(doc_pos[i, 1]), 2)
        d["z"] = round(float(doc_pos[i, 2]), 2)
        d["fx"] = d["x"]
        d["fy"] = d["y"]
        d["fz"] = d["z"]

    doc_min = doc_pos.min(axis=0)
    doc_max = doc_pos.max(axis=0)
    print(f"Documents positioned. Bounds: [{doc_min}] to [{doc_max}]")

    # 5. Position Chunks in Airy Open Constellations around each document
    chunks_by_doc = {}
    for ch in chunk_nodes:
        p_id = chunk_parent.get(ch["id"])
        if p_id and p_id in node_map:
            chunks_by_doc.setdefault(p_id, []).append(ch)
        else:
            chunks_by_doc.setdefault("__orphan__", []).append(ch)

    for ch in chunks_by_doc.get("__orphan__", []):
        ch["x"] = round(float(np.random.uniform(-1000, 1000)), 2)
        ch["y"] = round(float(np.random.uniform(-1000, 1000)), 2)
        ch["z"] = round(float(np.random.uniform(-1000, 1000)), 2)
        ch["fx"] = ch["x"]
        ch["fy"] = ch["y"]
        ch["fz"] = ch["z"]

    GOLDEN_ANGLE = 2.399963229728653

    for p_id, ch_list in chunks_by_doc.items():
        if p_id == "__orphan__":
            continue
        p_node = node_map[p_id]
        p_pos = np.array([p_node["x"], p_node["y"], p_node["z"]])
        n_ch = len(ch_list)

        # Distribute chunks in open elliptical disk / shell (radius 50 to 280)
        # Keeps them close to their parent document without colliding into neighboring documents
        base_r = 45.0
        max_r = min(320.0, base_r + math.pow(n_ch, 0.42) * 16.0)

        for i, ch in enumerate(ch_list):
            frac = (i + 1) / max(1, n_ch)
            r = base_r + math.pow(frac, 0.6) * (max_r - base_r)

            y = 1.0 - (2.0 * i) / max(1, n_ch - 1) if n_ch > 1 else 0.0
            radius_at_y = math.sqrt(max(0.0, 1.0 - y * y))
            theta = GOLDEN_ANGLE * i

            x = math.cos(theta) * radius_at_y
            z = math.sin(theta) * radius_at_y

            pos = p_pos + np.array([r * x, r * y, r * z])
            ch["x"] = round(float(pos[0]), 2)
            ch["y"] = round(float(pos[1]), 2)
            ch["z"] = round(float(pos[2]), 2)
            ch["fx"] = ch["x"]
            ch["fy"] = ch["y"]
            ch["fz"] = ch["z"]

    t1 = time.time()
    print(f"Spacious Multi-Galaxy Layout calculated in {t1 - t0:.2f}s. Saving to {json_path}...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print("Done! Distinct, clean, non-overlapping cosmic network saved.")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base_dir, "graph_3d_data.json")
    compute_organic_layout(target)
