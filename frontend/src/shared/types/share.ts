export interface ShareLink {
  id: string;
  documentId: string;
  token: string;
  shareUrl: string;
  hasPassword: boolean;
  allowDownload: boolean;
  expiresAt: string;
  accessCount: number;
  maxAccessCount?: number | null;
  createdAt?: string;
}

export interface ShareAccessResult {
  documentId: string;
  fileName: string;
  fileSize: number;
  allowDownload: boolean;
}

