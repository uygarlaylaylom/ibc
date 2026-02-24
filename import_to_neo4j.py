import pandas as pd
from neo4j import GraphDatabase, exceptions
import os
import time
import getpass

# Configuration
NEO4J_URI_ENV = os.getenv("NEO4J_URI", "bolt://localhost:7687")

# Auto-detect if user provided only the Aura DBID (e.g. "66c5fa42")
if "://" not in NEO4J_URI_ENV and "." not in NEO4J_URI_ENV:
    URI = f"neo4j+s://{NEO4J_URI_ENV}.databases.neo4j.io"
    print(f"Detected Neo4j Aura DBID. Using URI: {URI}")
else:
    URI = NEO4J_URI_ENV

NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# If connecting to Aura and password is default, ask for it immediately
if "databases.neo4j.io" in URI and NEO4J_PASSWORD == "password":
    print(f"Connecting to Neo4j Aura but no password set in env.")
    NEO4J_PASSWORD = getpass.getpass("Enter your Neo4j password: ")

AUTH = (NEO4J_USER, NEO4J_PASSWORD)

def get_driver(uri, auth):
    """Attempt to create a driver and verify connectivity. 
       If auth fails, prompt for password and retry."""
    current_auth = auth
    while True:
        driver = GraphDatabase.driver(uri, auth=current_auth)
        try:
            driver.verify_connectivity()
            return driver
        except exceptions.AuthError:
            print(f"\nAuthentication failed for user '{current_auth[0]}'.")
            new_password = getpass.getpass("Please enter the correct Neo4j password: ")
            if not new_password:
                print("No password entered. Exiting.")
                return None
            current_auth = (current_auth[0], new_password)
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

def import_data(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    print(f"Reading {file_path}...")
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Clean data: Replace NaN with empty strings for text fields
    df = df.fillna("")
    
    # Convert DataFrame to a list of dictionaries for batch processing
    data = df.to_dict('records')
    
    print(f"Loaded {len(data)} records. Connecting to Neo4j...")

    driver = get_driver(URI, AUTH)
    if not driver:
        return

    print("Connected successfully.")

    # Cypher query using UNWIND for batching
    query = """
    UNWIND $batch AS row
    
    MERGE (c:Exhibitor {name: row.Company})
    SET c.booth = row.Booth, 
        c.ibs_website = row.ProfileURL, 
        c.website = row.CompanyWebsite,
        c.description = row.Description

    // Update with AI Enriched Data if available
    FOREACH (ignoreMe IN CASE WHEN row.Inferred_Website <> "" AND row.Inferred_Website IS NOT NULL THEN [1] ELSE [] END |
        SET c.website = row.Inferred_Website,
            c.inferred_website = row.Inferred_Website,
            c.website_source = "AI_INFERRED"
    )
    
    // Process Role
    FOREACH (ignoreMe IN CASE WHEN row.Role <> "" AND row.Role IS NOT NULL THEN [1] ELSE [] END |
        MERGE (r:Role {name: row.Role})
        MERGE (c)-[:HAS_ROLE]->(r)
    )

    // Process Segment
    FOREACH (ignoreMe IN CASE WHEN row.Segment <> "" AND row.Segment IS NOT NULL THEN [1] ELSE [] END |
        MERGE (s:Segment {name: row.Segment})
        MERGE (c)-[:IN_SEGMENT]->(s)
    )

    // Process Location (City, State/Country)
    FOREACH (ignoreMe IN CASE WHEN row.City <> "" AND row.City IS NOT NULL THEN [1] ELSE [] END |
        MERGE (city:City {name: row.City})
        MERGE (c)-[:LOCATED_IN]->(city)
        
        FOREACH (ignoreMe2 IN CASE WHEN row['State/Country'] <> "" AND row['State/Country'] IS NOT NULL THEN [1] ELSE [] END |
            MERGE (state:StateCountry {name: row['State/Country']})
            MERGE (city)-[:PART_OF]->(state)
        )
    )

    // Process Extracted Products (Split by comma)
    FOREACH (prod IN [x IN split(row.Extracted_Products, ",") | trim(x)] |
        FOREACH (ignoreMe IN CASE WHEN prod <> "" THEN [1] ELSE [] END |
            MERGE (p:Product {name: prod})
            MERGE (c)-[:OFFERS_PRODUCT]->(p)
        )
    )

    // Process Extracted Services (Split by comma)
    FOREACH (serv IN [x IN split(row.Extracted_Services, ",") | trim(x)] |
        FOREACH (ignoreMe IN CASE WHEN serv <> "" THEN [1] ELSE [] END |
            MERGE (s:Service {name: serv})
            MERGE (c)-[:PROVIDES_SERVICE]->(s)
        )
    )
    """

    batch_size = 1000
    total_imported = 0
    start_time = time.time()
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        print(f"Importing batch {i // batch_size + 1} ({len(batch)} records)...")
        try:
            # New execution pattern (Neo4j driver 5.x+)
            summary = driver.execute_query(
                query, 
                batch=batch,
                database_="neo4j"
            ).summary
            
            # Count updates from summary
            updates = summary.counters.nodes_created + summary.counters.properties_set # Just a proxy for activity
            total_imported += len(batch)
            print(f"Batch processed in {summary.result_available_after} ms.")
            
        except Exception as e:
            print(f"Error importing batch: {e}")
    
    end_time = time.time()

    driver.close()
    print(f"Finished importing {total_imported} records in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    # Prioritize enriched file, fallback to original
    enriched_file = "offline_dossier/ibs_2026_final_enriched.csv"
    original_file = "ibs_2026_all_exhibitors.csv"
    
    if os.path.exists(enriched_file):
        print(f"Using Enriched Dataset: {enriched_file}")
        import_data(enriched_file)
    else:
        print(f"Enriched dataset not found. Using Original: {original_file}")
        import_data(original_file)
