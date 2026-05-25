export interface VocabularyScheme {
  uri: string;
  label: string;
  description?: string;
}

export interface ConceptNode {
  uri: string;
  pref_label: string;
  alt_labels: string[];
  description?: string;
  notation?: string;
  scheme_uri?: string;
  parent_uri?: string;
  children?: ConceptNode[] | null;
}

export interface ImportResponse {
  status: string;
  filename?: string | null;
  nodes_added: number;
  edges_added: number;
  format?: string;
}
