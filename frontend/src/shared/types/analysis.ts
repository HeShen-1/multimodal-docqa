export interface SummaryResult {
  documentId: string;
  summary: string;
  method: string;
  style: string;
  sourceLength: number;
  compressionRatio: number;
  fallbackUsed: boolean;
  processingTime?: number;
}

export interface KeywordItem {
  keyword: string;
  score: number;
  frequency: number;
}

export interface KeywordsResult {
  documentId: string;
  method: string;
  keywords: KeywordItem[];
  totalWords: number;
  processingTime?: number;
}

export interface CompareResult {
  documentA: { id: string; name: string };
  documentB: { id: string; name: string };
  result: Record<string, unknown>;
  processingTime?: number;
}

export interface SimilarAnalysisResult {
  sourceDocument: Record<string, unknown>;
  similarDocuments: Array<Record<string, unknown>>;
  total: number;
  processingTime?: number;
}

