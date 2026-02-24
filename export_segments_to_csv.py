import pandas as pd
from neo4j import GraphDatabase, exceptions
import os
import getpass

# Configuration
NEO4J_URI_ENV = os.getenv("NEO4J_URI", "bolt://localhost:7687")

# Auto-detect if user provided only the Aura DBID
if "://" not in NEO4J_URI_ENV and "." not in NEO4J_URI_ENV:
    URI = f"neo4j+s://{NEO4J_URI_ENV}.databases.neo4j.io"
    print(f"Detected Neo4j Aura DBID. Using URI: {URI}")
else:
    URI = NEO4J_URI_ENV

NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Basic auth check
if "databases.neo4j.io" in URI and NEO4J_PASSWORD == "password":
    print(f"\nConnecting to Neo4j Aura but no password set in env.")
    NEO4J_PASSWORD = getpass.getpass("Enter your Neo4j password: ")

AUTH = (NEO4J_USER, NEO4J_PASSWORD)

def get_driver(uri, auth):
    """Attempt to create a driver and verify connectivity. 
       If auth fails, prompt for password and retry."""
    current_auth = auth
    while True:
        try:
            driver = GraphDatabase.driver(uri, auth=current_auth)
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

def export_data():
    driver = get_driver(URI, AUTH)
    if not driver:
        return

    print("Connected successfully. Fetching data...")

    query = """
    MATCH (c:Exhibitor)-[:IN_SEGMENT]->(s:Segment)
    OPTIONAL MATCH (c)-[:HAS_ROLE]->(r:Role)
    OPTIONAL MATCH (c)-[:LOCATED_IN]->(city:City)
    OPTIONAL MATCH (city)-[:PART_OF]->(state:StateCountry)
    RETURN 
        s.name as Segment, 
        c.name as Company, 
        c.booth as Booth, 
        r.name as Role,
        city.name as City,
        state.name as State,
        c.website as Website,
        c.description as Description
    ORDER BY s.name, c.name
    """

    try:
        # Use simple session run for fetching all data
        # (driver.execute_query is great for writes/small reads, but pandas integration usually likes raw lists or direct execution)
        # Actually, let's use driver.execute_query as requested before for consistency
        records, summary, keys = driver.execute_query(
            query,
            database_="neo4j"
        )
        
        data = [record.data() for record in records]
        
        if not data:
            print("No data found in the graph.")
            return

        df = pd.DataFrame(data)
        
        output_file = "ibs_2026_by_segment.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
        print(f"\nExport successful!")
        print(f"Saved {len(df)} rows to {output_file}")
        
    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    export_data()
