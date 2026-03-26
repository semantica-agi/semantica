# Glossary

Reference of terms and concepts used throughout Semantica.

!!! tip "Finding a term"
    Use Ctrl+F to search this page.

---

## Core Concepts

### **Agent**
An autonomous AI system that can perceive its environment, reason about information, and take actions to achieve specific goals. In Semantica, agents use knowledge graphs for memory and reasoning.

### **Entity**
A distinct object or concept in the real world, such as a person, place, organization, or event. Entities are the fundamental building blocks of knowledge graphs.

### **Knowledge Graph (KG)**
A structured representation of knowledge using entities (nodes) and relationships (edges). KGs enable reasoning, querying, and semantic analysis of data.

### **Relationship**
A connection between two entities that describes how they relate to each other (e.g., "works_for", "located_in", "founded_by").

### **Semantic**
Relating to meaning in language or logic. Semantic understanding goes beyond keywords to comprehend context and intent.

---

## Data Processing

### **Ingestion**
The process of loading data from various sources (files, databases, APIs, streams) into a system for processing.

### **Normalization**
The process of standardizing data into a consistent format (e.g., converting dates to ISO format, standardizing entity names).

### **Parsing**
Extracting structured information from unstructured or semi-structured documents like PDFs, Word documents, or web pages.

### **Chunking**
Breaking down large documents into smaller, manageable pieces while preserving context and meaning.

---

## Artificial Intelligence

### **LLM (Large Language Model)**
A type of artificial intelligence model trained on vast amounts of text data, capable of understanding and generating human-like text.

### **RAG (Retrieval Augmented Generation)**
A technique that enhances LLM responses by retrieving relevant information from a knowledge base before generating an answer.

### **GraphRAG (Graph-Augmented Retrieval Augmented Generation)**
An advanced RAG approach that combines vector search with knowledge graph traversal to provide more accurate and contextually relevant information to LLMs.

### **Inference**
The process of deriving new facts or conclusions from existing knowledge using logical rules.

---

## Knowledge Graph Components

### **Node**
A vertex in a graph representing an entity or concept.

### **Edge**
A connection between two nodes representing a relationship.

### **Property**
An attribute or characteristic of an entity or relationship (e.g., name, date, confidence score).

### **Triplet**
A basic unit of knowledge in RDF, consisting of a subject, predicate, and object (e.g., `<Apple_Inc> <founded_by> <Steve_Jobs>`).

### **Temporal Graph**
A knowledge graph that tracks changes over time, allowing queries about the state of the graph at specific time points.

---

## Entity Recognition & Extraction

### **Named Entity Recognition (NER)**
The process of identifying and classifying named entities in text into predefined categories such as persons, organizations, locations, dates, and more.

### **Relationship Extraction**
The task of identifying and extracting semantic relationships between entities in text.

### **Entity Resolution**
The process of determining when two entity mentions refer to the same real-world entity, also known as entity linking or deduplication.

### **Coreference Resolution**
The task of determining when two or more expressions in text refer to the same entity (e.g., "Apple" and "the company" referring to Apple Inc.).

### **Event Detection**
The task of identifying and classifying events (e.g., acquisitions, partnerships, announcements) in text.

---

## Ontology & Schema

### **Ontology**
A formal specification of concepts, relationships, and constraints in a domain, typically expressed in OWL (Web Ontology Language).

### **Class**
In ontologies, a category or type of entity (e.g., `Person`, `Organization`, `Location`).

### **Axiom**
A statement or rule that is accepted as true without proof, used in ontologies to define logical constraints and relationships.

### **OWL (Web Ontology Language)**
A W3C standard language for defining and instantiating ontologies on the web.

### **Property**
In ontologies, a relationship or attribute that connects entities or describes their characteristics.

---

## Data Storage & Retrieval

### **Embedding**
A dense vector representation of text, images, or other data that captures semantic meaning in a continuous vector space. Used for similarity search and semantic matching.

### **Vector Store**
A database optimized for storing and searching high-dimensional vectors, used for semantic similarity search.

### **Triplet Store**
A database designed specifically for storing and querying RDF triplets.

### **Graph Database**
A database designed specifically for storing and querying graph-structured data.

### **Hybrid Search**
A search strategy that combines multiple retrieval methods, typically vector search and keyword search, to improve accuracy.

---

## Graph Analytics

### **Centrality**
A measure of the importance or influence of a node in a graph. Common centrality metrics include PageRank, betweenness centrality, and closeness centrality.

### **PageRank**
An algorithm used to measure the importance of nodes in a graph based on the structure of incoming links.

### **Community Detection**
The process of identifying groups or clusters of densely connected nodes in a graph.

### **Graph Analytics**
The application of graph algorithms (e.g., centrality, community detection) to gain insights from the structure of a knowledge graph.

---

## Query Languages

### **Cypher**
A declarative query language for graph databases, particularly Neo4j.

### **SPARQL**
A query language for RDF data, similar to SQL for relational databases.

### **RDF (Resource Description Framework)**
A W3C standard for representing information about resources in the form of subject-predicate-object triplets.

---

## Data Quality

### **Conflict Resolution**
The process of handling contradictory information from multiple sources in a knowledge graph.

### **Deduplication**
The process of identifying and removing duplicate records or entities from a dataset.

### **Data Provenance**
Information about the origin, history, and lineage of data, including sources, timestamps, and transformations.

---

## Technical Terms

### **API (Application Programming Interface)**
A set of functions and protocols that allow different software applications to communicate with each other.

### **OCR (Optical Character Recognition)**
Technology that converts images of text (e.g., scanned documents, photos) into machine-readable text.

### **Pipeline**
A sequence of data processing steps that transform raw data into a desired output format.

### **Vector**
A mathematical representation of data as an array of numbers, used in embeddings to capture semantic meaning.

### **Visualization**
The graphical representation of data, such as knowledge graphs, embeddings, or analytics.

### **Web Scraping**
The automated process of extracting data from websites.

---

## Semantica-Specific Terms

### **Semantic Layer**
An abstraction layer that provides a unified, business-friendly view of data by adding context, relationships, and meaning to raw data.

### **Semantic Network**
A knowledge representation that uses a graph structure to represent concepts and their relationships.

### **Change Management**
The process of tracking and managing changes to knowledge graphs over time, including version control and audit trails.

### **Provenance Tracking**
W3C PROV-O compliant tracking of data lineage and source attribution.

---

## See Also

- [Core Concepts](concepts.md) — deeper explanation of key ideas
- [Getting Started](getting-started.md) — first steps
- [Modules Guide](modules.md) — every module explained
- [API Reference](reference/) — technical reference
