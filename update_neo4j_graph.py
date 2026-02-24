import pandas as pd
from neo4j import GraphDatabase
import os
import sys

# Configuration - Change these or set environment variables
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

def run_query(driver, query, parameters=None):
    with driver.session() as session:
        result = session.run(query, parameters)
        return result.consume()

def import_csv_to_neo4j(driver, csv_file, query, batch_size=1000):
    if not os.path.exists(csv_file):
        print(f"File not found: {csv_file}")
        return

    print(f"Importing {csv_file}...")
    # Read CSV with proper Quotechar and potentially complex embedded newlines (like in description)
    # The user's CSV seems standard but descriptions might have newlines.
    try:
        df = pd.read_csv(csv_file)
        df = df.fillna("") # Replace NaNs with empty string
    except Exception as e:
        print(f"Error reading CSV {csv_file}: {e}")
        return

    total_rows = len(df)
    print(f"Found {total_rows} rows.")

    with driver.session() as session:
        for start in range(0, total_rows, batch_size):
            end = min(start + batch_size, total_rows)
            batch = df[start:end].to_dict('records')
            
            # Using UNWIND for batching is efficient
            # We need to adapt the query to accept a list of maps (rows)
            # But the user's cypher script has simple MERGE statements.
            # I will wrap the user's logic in UNWIND $rows AS row
            
            # The query passed to this function should be prepared to handle `row` variable which is a map.
             
            wrapped_query = f"""
            UNWIND $rows AS row
            {query}
            """
            
            try:
                session.run(wrapped_query, rows=batch)
                print(f"Processed rows {start} to {end}...")
            except Exception as e:
                print(f"Error executing batch {start}-{end}: {e}")

def main():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j.")
    except Exception as e:
        print(f"Could not connect to Neo4j: {e}")
        print("Please ensure Neo4j is running and credentials are correct.")
        sys.exit(1)

    # 1. Constraints
    print("Setting up constraints...")
    constraints = [
        "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
        "CREATE CONSTRAINT tag_id IF NOT EXISTS FOR (t:Tag) REQUIRE t.id IS UNIQUE"
    ]
    for c in constraints:
        run_query(driver, c)

    # 2. Nodes
    # Segments
    import_csv_to_neo4j(driver, "ibs_nodes_segments.csv", 
                        "MERGE (:Segment {id: row.segment_id, name: row.name})")

    # Locations
    import_csv_to_neo4j(driver, "ibs_nodes_locations.csv", 
                        "MERGE (:Location {id: row.location_id, city: row.city, region: row.region, country: row.country})")

    # Tags
    import_csv_to_neo4j(driver, "ibs_nodes_tags.csv", 
                        "MERGE (:Tag {id: row.tag_id, name: row.name})")

    # Companies
    # Note: Using MERGE on ID only, then SET properties to handle updates or re-runs safely
    company_query = """
    MERGE (c:Company {id: row.company_id})
    SET c.name = row.name,
        c.booth = row.booth,
        c.website = row.website,
        c.role = row.role,
        c.description = row.description,
        c.city = row.city,
        c.region = row.region,
        c.country = row.country,
        c.segment_name = row.segment_name
    """
    import_csv_to_neo4j(driver, "ibs_nodes_companies.csv", company_query)

    # 3. Relationships
    # In Segment
    rel_segment_query = """
    MATCH (c:Company {id: row.company_id})
    MATCH (s:Segment {id: row.segment_id})
    MERGE (c)-[:IN_SEGMENT]->(s)
    """
    import_csv_to_neo4j(driver, "ibs_rel_in_segment.csv", rel_segment_query)

    # Located In
    rel_location_query = """
    MATCH (c:Company {id: row.company_id})
    MATCH (l:Location {id: row.location_id})
    MERGE (c)-[:LOCATED_IN]->(l)
    """
    import_csv_to_neo4j(driver, "ibs_rel_located_in.csv", rel_location_query)

    # Has Tag
    rel_tag_query = """
    MATCH (c:Company {id: row.company_id})
    MATCH (t:Tag {id: row.tag_id})
    MERGE (c)-[:HAS_TAG]->(t)
    """
    import_csv_to_neo4j(driver, "ibs_rel_has_tag.csv", rel_tag_query)

    driver.close()
    print("Import completed.")

if __name__ == "__main__":
    main()
