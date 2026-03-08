import { DocumentDetailPanel } from "@/features/documents/components/document-detail-panel";
import { DocumentsListPanel } from "@/features/documents/components/documents-list-panel";
import { DocumentsSharePanel } from "@/features/documents/components/documents-share-panel";
import { DocumentsTagsPanel } from "@/features/documents/components/documents-tags-panel";
import { DocumentsUploadPanel } from "@/features/documents/components/documents-upload-panel";
import { useDocumentsPage } from "@/features/documents/use-documents-page";

export function DocumentsPageContent() {
  const state = useDocumentsPage();

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(420px,1fr)]">
      <div className="space-y-4">
        <DocumentsListPanel state={state} />
        <DocumentsUploadPanel state={state} />
        <DocumentsTagsPanel state={state} />
        <DocumentsSharePanel state={state} />
      </div>
      <DocumentDetailPanel state={state} />
    </div>
  );
}
