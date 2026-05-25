export interface OntologyEntry {
  uri: string;
  name: string;
  description?: string;
  format: string;
  status: "published" | "draft" | "external";
  source_url?: string;
  version?: string;
  class_count: number;
  concept_count: number;
  property_count: number;
  loaded_at: string;
  enabled: boolean;
  tags: string[];
}

export type AlignmentRelation =
  | "owl:equivalentClass"
  | "owl:equivalentProperty"
  | "skos:exactMatch"
  | "skos:closeMatch"
  | "skos:broadMatch"
  | "skos:narrowMatch"
  | "skos:relatedMatch";

export interface OntologyAlignment {
  id: string;
  source_uri: string;
  source_label: string;
  target_uri: string;
  target_label: string;
  relation: AlignmentRelation;
  predicate_uri: string;
  confidence: number;
  provenance?: string;
  source?: string;
  reviewer?: string;
  created_at: string;
  updated_at: string;
}

export interface AlignmentSuggestion {
  source_uri: string;
  source_label: string;
  target_uri: string;
  target_label: string;
  relation: AlignmentRelation;
  score: number;
  label_similarity: number;
  embedding_similarity?: number | null;
  reason: string;
}

export interface HealthDimension {
  key: string;
  label: string;
  score: number;
  status: "ok" | "warning" | "critical" | "unavailable";
  detail: string;
}

export interface HealthIssue {
  id: string;
  severity: "info" | "warning" | "critical";
  category: string;
  entity_uri?: string;
  entity_label?: string;
  message: string;
  action?: string;
}

export interface OntologyHealthResponse {
  uri: string;
  name: string;
  total_score: number;
  dimensions: HealthDimension[];
  issues: HealthIssue[];
  generated_at: string;
}

export interface ShaclShapeSummary {
  id: string;
  target_class?: string;
  constraint_count: number;
  constraints: string[];
  violation_count: number;
}

export interface ShaclViolation {
  node?: string;
  path?: string;
  severity: string;
  message: string;
  focus_node?: string;
  source_shape?: string;
}

export interface ShaclGenerateResponse {
  uri: string;
  shacl_turtle: string;
  shape_count: number;
  generated_at: string;
}

export interface ShaclShapesResponse {
  uri: string;
  shapes: ShaclShapeSummary[];
  shacl_turtle: string;
  generated_at: string;
}

export interface ShaclValidationResponse {
  uri?: string;
  conforms: boolean;
  status: "success" | "unavailable" | "error";
  message: string;
  violations: ShaclViolation[];
  report_text?: string;
}
