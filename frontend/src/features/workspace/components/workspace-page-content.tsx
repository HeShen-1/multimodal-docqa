import { ConversationSidebarPanel } from "@/features/workspace/components/conversation-sidebar-panel";
import { WorkspaceChatPanel } from "@/features/workspace/components/workspace-chat-panel";
import { WorkspaceInspectorPanel } from "@/features/workspace/components/workspace-inspector-panel";
import { useWorkspacePage } from "@/features/workspace/use-workspace-page";

export function WorkspacePageContent() {
  const state = useWorkspacePage();

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[280px_minmax(0,1fr)_360px]">
      <ConversationSidebarPanel state={state} />
      <WorkspaceChatPanel state={state} />
      <WorkspaceInspectorPanel state={state} />
    </div>
  );
}
