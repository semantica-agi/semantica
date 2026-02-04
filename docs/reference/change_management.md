# Change Management

> **Enhanced change management for knowledge graphs and ontologies with persistent storage, audit trails, and data integrity verification.**

---

## 🎯 Overview

<div class="grid cards" markdown>

-   :material-source-merge:{ .lg .middle } **Version Control**

    ---
    - Enhanced version management with integrity verification
    - Automatic version numbering
    - Support for knowledge graphs and ontologies

-   :material-audit:{ .lg .middle } **Audit Trails**

    ---
    - Complete audit trails with standardized metadata structures
    - Author attribution and change tracking
    - Enterprise compliance support

-   :material-database:{ .lg .middle } **Persistent Storage**

    ---
    - SQLite and in-memory storage backends
    - ACID compliance and thread safety
    - Automatic schema management

-   :material-shield-check:{ .lg .middle } **Data Integrity**

    ---
    - SHA-256 checksum verification
    - Data validation with corruption detection
    - Integrity guarantees for sensitive data

-   :material-timeline:{ .lg .middle } **Temporal Tracking**

    ---
    - Time-aware version management
    - Temporal queries for historical analysis
    - Historical data reconstruction

-   :material-school:{ .lg .middle } **Ontology Support**

    ---
    - Specialized ontology version management
    - Schema evolution and compatibility checking
    - Structural comparison for ontology elements

</div>

!!! tip "When to Use"
    - **Production Systems**: Reliable version control for knowledge graphs
    - **Compliance Requirements**: Audit trails and regulatory compliance
    - **Team Collaboration**: Multiple users modifying the same knowledge graph
    - **Schema Evolution**: Managing ontology changes and compatibility
    - **Data Recovery**: Rolling back to previous states

---

## Main Classes

### BaseVersionManager

Abstract base class for enhanced version managers providing common functionality for version management across different data types.

**Key Methods:**
- `create_snapshot(data, version_label, author, description)` - Create a versioned snapshot
- `compare_versions(version1, version2)` - Compare two versions and return differences
- `list_versions()` - List all version snapshots
- `get_version(label)` - Retrieve specific version by label
- `verify_checksum(snapshot)` - Verify the integrity of a snapshot

---

### TemporalVersionManager

Enhanced version manager for knowledge graphs with temporal capabilities and detailed change tracking.

**Key Methods:**
- `create_snapshot(data, version_label, author, description)` - Create temporal snapshot
- `compare_versions(version1, version2)` - Compare temporal versions with detailed diffs
- `list_versions()` - List all temporal versions
- `get_version(label)` - Retrieve specific temporal version
- `verify_checksum(snapshot)` - Verify temporal snapshot integrity

**Use For:**
- Knowledge graph versioning with temporal support
- Historical analysis and time-aware queries
- Version comparison and rollback operations

---

### OntologyVersionManager

Enhanced version manager for ontology schemas with compatibility checking and structural comparison.

**Key Methods:**
- `create_version(version, ontology, changes)` - Create ontology version
- `generate_element_iri(element_name, element_type)` - Generate version-aware element IRI
- `compare_versions(version1, version2)` - Compare ontology versions
- `migrate_ontology(from_version, to_version, ontology)` - Migrate ontology between versions

**Use For:**
- Ontology schema versioning and evolution
- Compatibility checking between ontology versions
- Schema validation and structural analysis

---

### VersionManager

Alias for OntologyVersionManager for backward compatibility and ontology-focused version management.

---

### ChangeLogEntry

Standardized metadata structure for version changes with validation and RFC 5322 email validation.

**Key Features:**
- RFC 5322 email validation for authors
- ISO 8601 timestamp formatting
- Maximum 500 character description limit
- Optional change ID linking to external systems
- Related changes tracking

**Methods:**
- `create_now(author, description, change_id, related_changes)` - Create entry with current timestamp
- `validate()` - Validate all fields
- `to_dict()` - Convert to dictionary
- `from_dict(data)` - Create from dictionary

---

### OntologyVersion

Dataclass representing an ontology version with version information and metadata.

**Key Attributes:**
- Version information and metadata
- Creation and modification timestamps
- Author and change tracking
- Compatibility information

---

### VersionStorage

Abstract base class for storage implementations.

**Abstract Methods:**
- `save(snapshot)` - Save a version snapshot
- `get(label)` - Retrieve a version snapshot
- `list_all()` - List all version snapshots
- `delete(label)` - Delete a version snapshot
- `exists(label)` - Check if version exists

**Implementations:**
- **InMemoryVersionStorage**: Dictionary-based in-memory storage
- **SQLiteVersionStorage**: SQLite-based persistent storage

---

## Storage Implementations

### InMemoryVersionStorage

Fast, non-persistent storage for development and testing.

**Key Features:**
- Dictionary-based storage
- Thread-safe operations
- LRU eviction when limit reached
- Temporary version tracking

---

### SQLiteVersionStorage

SQLite-based persistent version storage implementation.

**Key Features:**
- Persistent SQLite database storage
- ACID compliance and thread safety
- Automatic schema management
- Checksum verification

---

## Usage Examples

### 🔄 Basic Version Control

```python
from semantica.change_management import TemporalVersionManager, ChangeLogEntry

# Initialize version manager
manager = TemporalVersionManager(storage_path="versions.db")

# Create snapshot with change tracking
snapshot = manager.create_snapshot(
    data=kg,
    version_label="v1.0.0",
    author="data-engineer@company.com",
    description="Initial knowledge graph creation"
)

# List all versions
versions = manager.list_versions()
print(f"Total versions: {len(versions)}")

# Retrieve specific version
version = manager.get_version("v1.0.0")
print(f"Version v1.0.0: {version['description']}")
```

### 🏢 Ontology Version Management

```python
from semantica.change_management import OntologyVersionManager

# Initialize ontology version manager
manager = OntologyVersionManager(base_uri="https://example.org/ontology/")

# Create ontology version
version = manager.create_version(
    version="1.0",
    ontology=ontology,
    changes=["Added Person class", "Updated properties"]
)

# Generate element IRI
element_iri = manager.generate_element_iri("Person", "class")
print(f"Person IRI: {element_iri}")

# Compare versions
comparison = manager.compare_versions("1.0", "2.0")
print(f"Classes added: {comparison['classes_added']}")
```

### 🔧 Storage Configuration

```python
from semantica.change_management import (
    TemporalVersionManager,
    SQLiteVersionStorage,
    InMemoryVersionStorage
)

# SQLite storage for production
sqlite_storage = SQLiteVersionStorage("production_versions.db")
production_manager = TemporalVersionManager(storage_path="production_versions.db")

# In-memory storage for testing
memory_storage = InMemoryVersionStorage()
dev_manager = TemporalVersionManager()  # Uses in-memory by default

# Direct storage path
direct_manager = TemporalVersionManager(storage_path="versions.db")
```

### 📊 Version Analysis

```python
from semantica.change_management import TemporalVersionManager

manager = TemporalVersionManager(storage_path="versions.db")

# Get version statistics
all_versions = manager.list_versions()
print(f"Total versions: {len(all_versions)}")

# Compare versions
diff = manager.compare_versions("v1.0.0", "v2.0.0")
print(f"Changes detected: {len(diff)}")

# Verify integrity
for version in all_versions:
    is_valid = manager.verify_checksum(version)
    print(f"Version {version['label']} integrity: {'✓' if is_valid else '✗'}")
```

### 📝 Change Log Entry Management

```python
from semantica.change_management import ChangeLogEntry

# Create change log entry with current timestamp
entry = ChangeLogEntry.create_now(
    author="developer@company.com",
    description="Fixed entity resolution bug in medical ontology",
    change_id="JIRA-1234",
    related_changes=["JIRA-1235", "JIRA-1236"]
)

# Validate entry
try:
    entry.validate()
    print("Change log entry is valid")
except Exception as e:
    print(f"Validation failed: {e}")

# Convert to/from dictionary
entry_dict = entry.to_dict()
restored_entry = ChangeLogEntry.from_dict(entry_dict)
```

### 🔍 Base Version Manager Usage

```python
from semantica.change_management import BaseVersionManager

# Create custom version manager (abstract base class)
class CustomVersionManager(BaseVersionManager):
    def create_snapshot(self, data, version_label, author, description, **options):
        """Custom snapshot creation logic"""
        snapshot = {
            "label": version_label,
            "data": data,
            "author": author,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            **options
        }
        self.storage.save(snapshot)
        return snapshot
    
    def compare_versions(self, version1, version2, **options):
        """Custom version comparison logic"""
        return {
            "added": [],
            "removed": [],
            "modified": [],
            "metadata_diff": {}
        }

# Initialize custom manager
custom_manager = CustomVersionManager(storage_path="custom_versions.db")
```

### 🏷️ Ontology Version Dataclass

```python
from semantica.change_management import OntologyVersion

# Create ontology version dataclass
version = OntologyVersion(
    version="1.0.0",
    base_uri="https://example.org/ontology/",
    created_at=datetime.utcnow(),
    author="ontologist@company.com",
    description="Initial ontology version",
    changes=["Added Person class", "Defined properties"]
)

# Access version information
print(f"Version: {version.version}")
print(f"Base URI: {version.base_uri}")
print(f"Changes: {version.changes}")
```

### 🗄️ Version Storage Direct Usage

```python
from semantica.change_management import (
    VersionStorage,
    InMemoryVersionStorage,
    SQLiteVersionStorage
)

# Use in-memory storage directly
memory_storage = InMemoryVersionStorage()
memory_storage.save({"label": "v1.0", "data": "test"})
retrieved = memory_storage.get("v1.0")
print(f"Retrieved: {retrieved}")

# Use SQLite storage directly
sqlite_storage = SQLiteVersionStorage("direct_versions.db")
sqlite_storage.save({"label": "v2.0", "data": "test2"})
all_versions = sqlite_storage.list_all()
print(f"All versions: {len(all_versions)}")
```

---

## Utilities

### Checksum Functions

```python
from semantica.change_management import compute_checksum, verify_checksum

# Compute checksum of data
data = {"entities": [...], "relationships": [...]}
checksum = compute_checksum(data)
print(f"Checksum: {checksum}")

# Verify data integrity
is_valid = verify_checksum(data, checksum)
if not is_valid:
    raise ValueError("Data integrity check failed")
```

---
