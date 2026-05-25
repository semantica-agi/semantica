// queries.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { VocabularyScheme, ConceptNode, ImportResponse } from './types';

const fetchSchemes = async (): Promise<VocabularyScheme[]> => {
  const res = await fetch('/api/vocabulary/schemes');
  if (!res.ok) throw new Error('Failed to fetch vocabularies');
  return res.json();
};

const fetchHierarchy = async (schemeUri: string): Promise<ConceptNode[]> => {
  const res = await fetch(`/api/vocabulary/hierarchy?scheme=${encodeURIComponent(schemeUri)}`);
  if (!res.ok) throw new Error('Failed to fetch hierarchy');
  return res.json();
};

// Updated to return the ImportResponse
const importVocabulary = async (file: File): Promise<ImportResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/vocabulary/import', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to import vocabulary');
  return res.json(); 
};

export const useVocabularies = () => {
  return useQuery({ 
    queryKey: ['vocabularies'], 
    queryFn: fetchSchemes 
  });
};

export const useConceptHierarchy = (schemeUri: string | undefined) => {
  return useQuery({
    queryKey: ['hierarchy', schemeUri],
    queryFn: () => fetchHierarchy(schemeUri!),
    enabled: !!schemeUri, 
  });
};

export const useImportVocabulary = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importVocabulary,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vocabularies'] });
    },
  });
};