import json
import logging
from core.database import Neo4jManager
from config.settings import get_settings

settings = get_settings()
db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)

def export_graph_json(output_path="graph_3d_data.json"):
    print("Exporting Neo4j knowledge graph to JSON...")
    db.connect()
    
    # Export Nodes
    nodes = []
    print("Fetching documents...")
    docs = db.execute_query("MATCH (n:Document) RETURN id(n) as id, n.title as label, n.course as course, 'document' as type")
    for doc in docs:
        nodes.append({"id": str(doc["id"]), "label": doc["label"], "course": doc["course"], "type": "document"})
        
    print("Fetching chunks...")
    chunks = db.execute_query("MATCH (d:Document)-[:HAS_CHUNK]->(n:Chunk) RETURN id(n) as id, d.course as course, 'chunk' as type")
    for chunk in chunks:
        nodes.append({"id": str(chunk["id"]), "label": "Chunk", "course": chunk["course"], "type": "chunk"})
        
    print(f"Exported {len(nodes)} nodes.")
    
    # Export Links
    links = []
    print("Fetching HAS_CHUNK links...")
    has_chunks = db.execute_query("MATCH (a)-[:HAS_CHUNK]->(b) RETURN id(a) as source, id(b) as target")
    for link in has_chunks:
        links.append({"source": str(link["source"]), "target": str(link["target"]), "type": "HAS_CHUNK"})
        
    print("Fetching SIMILAR_TO links...")
    similar_to = db.execute_query("MATCH (a)-[:SIMILAR_TO]->(b) RETURN id(a) as source, id(b) as target")
    for link in similar_to:
        links.append({"source": str(link["source"]), "target": str(link["target"]), "type": "SIMILAR_TO"})
        
    print("Fetching RELATED_TO links...")
    related_to = db.execute_query("MATCH (a)-[:RELATED_TO]->(b) RETURN id(a) as source, id(b) as target")
    for link in related_to:
        links.append({"source": str(link["source"]), "target": str(link["target"]), "type": "RELATED_TO"})
        
    # Annotate all links with c1 and c2 courses
    node_course = {n["id"]: n.get("course") for n in nodes}
    for link in links:
        link["c1"] = node_course.get(link["source"])
        link["c2"] = node_course.get(link["target"])

    print(f"Exported {len(links)} links.")
    
    data = {"nodes": nodes, "links": links}
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    print(f"Graph successfully exported to {output_path}!")
    db.close()

if __name__ == "__main__":
    export_graph_json()
