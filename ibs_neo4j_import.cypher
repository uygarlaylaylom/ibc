// IBS 2026 Market Graph - minimal long-term starter
// Put the CSV files into Neo4j's import/ directory, then run this in Neo4j Browser.

CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT tag_id IF NOT EXISTS FOR (t:Tag) REQUIRE t.id IS UNIQUE;

// --- Nodes ---
LOAD CSV WITH HEADERS FROM 'file:///ibs_nodes_segments.csv' AS row
MERGE (:Segment {id: row.segment_id, name: row.name});

LOAD CSV WITH HEADERS FROM 'file:///ibs_nodes_locations.csv' AS row
MERGE (:Location {id: row.location_id, city: row.city, region: row.region, country: row.country});

LOAD CSV WITH HEADERS FROM 'file:///ibs_nodes_tags.csv' AS row
MERGE (:Tag {id: row.tag_id, name: row.name});

LOAD CSV WITH HEADERS FROM 'file:///ibs_nodes_companies.csv' AS row
MERGE (c:Company {id: row.company_id})
SET c.name = row.name,
    c.booth = row.booth,
    c.website = row.website,
    c.role = row.role,
    c.description = row.description,
    c.city = row.city,
    c.region = row.region,
    c.country = row.country,
    c.segment_name = row.segment_name;

// --- Relationships ---
LOAD CSV WITH HEADERS FROM 'file:///ibs_rel_in_segment.csv' AS row
MATCH (c:Company {id: row.company_id})
MATCH (s:Segment {id: row.segment_id})
MERGE (c)-[:IN_SEGMENT]->(s);

LOAD CSV WITH HEADERS FROM 'file:///ibs_rel_located_in.csv' AS row
MATCH (c:Company {id: row.company_id})
MATCH (l:Location {id: row.location_id})
MERGE (c)-[:LOCATED_IN]->(l);

LOAD CSV WITH HEADERS FROM 'file:///ibs_rel_has_tag.csv' AS row
MATCH (c:Company {id: row.company_id})
MATCH (t:Tag {id: row.tag_id})
MERGE (c)-[:HAS_TAG]->(t);