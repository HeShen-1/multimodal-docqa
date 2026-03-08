import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { analysisApi } from "@/features/analysis/analysis-api";
import { documentsApi } from "@/features/documents/documents-api";
import { DEFAULT_LLM_MODEL, LLM_MODEL_OPTIONS } from "@/shared/config/llm-models";
import { normalizeApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

function JsonViewer({ title, value }: { title: string; value: unknown }) {
  if (!value) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-primary">{title}</p>
      <pre className="max-h-80 overflow-auto rounded-md border border-border bg-black/30 p-3 text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

export function AnalysisPage() {
  const [summaryForm, setSummaryForm] = useState({
    documentId: "",
    method: "hybrid" as "extractive" | "generative" | "hybrid",
    maxLength: 300,
    style: "简洁" as "简洁" | "详细",
    model: DEFAULT_LLM_MODEL,
  });
  const [keywordForm, setKeywordForm] = useState({
    documentId: "",
    method: "hybrid" as "tfidf" | "textrank" | "llm" | "hybrid",
    topK: 10,
    model: DEFAULT_LLM_MODEL,
  });
  const [compareForm, setCompareForm] = useState({
    documentIdA: "",
    documentIdB: "",
    topK: 10,
  });
  const [similarForm, setSimilarForm] = useState({
    documentId: "",
    limit: 5,
    minSimilarity: 0.4,
  });

  const documentsQuery = useQuery({
    queryKey: ["analysis-document-options"],
    queryFn: async () => {
      const page = await documentsApi.list({ page: 1, pageSize: 100 });
      return page.items.filter((item) => item.status.toLowerCase().includes("complete"));
    },
  });

  const summaryMutation = useMutation({
    mutationFn: () => analysisApi.summary(summaryForm),
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const keywordsMutation = useMutation({
    mutationFn: () => analysisApi.keywords(keywordForm),
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const compareMutation = useMutation({
    mutationFn: () => analysisApi.compare(compareForm),
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const similarMutation = useMutation({
    mutationFn: () =>
      analysisApi.similar(similarForm.documentId, {
        limit: similarForm.limit,
        minSimilarity: similarForm.minSimilarity,
      }),
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  const documentOptions = documentsQuery.data?.map((doc) => ({ label: doc.fileName, value: doc.id })) ?? [];
  const modelOptions = LLM_MODEL_OPTIONS.map((option) => ({ label: option.label, value: option.value }));

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>文档摘要</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Label>文档</Label>
          <Select
            value={summaryForm.documentId}
            options={[{ label: "请选择文档", value: "" }, ...documentOptions]}
            onChange={(event) => setSummaryForm((previous) => ({ ...previous, documentId: event.target.value }))}
          />
          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            <Select
              value={summaryForm.model}
              options={modelOptions}
              onChange={(event) =>
                setSummaryForm((previous) => ({ ...previous, model: event.target.value }))
              }
            />
            <Select
              value={summaryForm.method}
              options={[
                { label: "hybrid", value: "hybrid" },
                { label: "extractive", value: "extractive" },
                { label: "generative", value: "generative" },
              ]}
              onChange={(event) =>
                setSummaryForm((previous) => ({
                  ...previous,
                  method: event.target.value as typeof previous.method,
                }))
              }
            />
            <Input
              type="number"
              value={summaryForm.maxLength}
              onChange={(event) =>
                setSummaryForm((previous) => ({
                  ...previous,
                  maxLength: Number(event.target.value),
                }))
              }
            />
            <Select
              value={summaryForm.style}
              options={[
                { label: "简洁", value: "简洁" },
                { label: "详细", value: "详细" },
              ]}
              onChange={(event) =>
                setSummaryForm((previous) => ({
                  ...previous,
                  style: event.target.value as typeof previous.style,
                }))
              }
            />
          </div>
          <Button onClick={() => summaryMutation.mutate()} disabled={!summaryForm.documentId || summaryMutation.isPending}>
            生成摘要
          </Button>
          <Textarea
            value={summaryMutation.data?.summary ?? ""}
            readOnly
            placeholder="摘要结果将显示在这里"
            className="min-h-[220px]"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>关键词提取</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Label>文档</Label>
          <Select
            value={keywordForm.documentId}
            options={[{ label: "请选择文档", value: "" }, ...documentOptions]}
            onChange={(event) => setKeywordForm((previous) => ({ ...previous, documentId: event.target.value }))}
          />
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            <Select
              value={keywordForm.model}
              options={modelOptions}
              onChange={(event) =>
                setKeywordForm((previous) => ({ ...previous, model: event.target.value }))
              }
            />
            <Select
              value={keywordForm.method}
              options={[
                { label: "hybrid", value: "hybrid" },
                { label: "tfidf", value: "tfidf" },
                { label: "textrank", value: "textrank" },
                { label: "llm", value: "llm" },
              ]}
              onChange={(event) =>
                setKeywordForm((previous) => ({
                  ...previous,
                  method: event.target.value as typeof previous.method,
                }))
              }
            />
            <Input
              type="number"
              value={keywordForm.topK}
              onChange={(event) =>
                setKeywordForm((previous) => ({
                  ...previous,
                  topK: Number(event.target.value),
                }))
              }
            />
          </div>
          <Button onClick={() => keywordsMutation.mutate()} disabled={!keywordForm.documentId || keywordsMutation.isPending}>
            提取关键词
          </Button>
          <JsonViewer title="关键词结果" value={keywordsMutation.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>文档对比</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Select
              value={compareForm.documentIdA}
              options={[{ label: "文档 A", value: "" }, ...documentOptions]}
              onChange={(event) => setCompareForm((previous) => ({ ...previous, documentIdA: event.target.value }))}
            />
            <Select
              value={compareForm.documentIdB}
              options={[{ label: "文档 B", value: "" }, ...documentOptions]}
              onChange={(event) => setCompareForm((previous) => ({ ...previous, documentIdB: event.target.value }))}
            />
          </div>
          <Input
            type="number"
            value={compareForm.topK}
            onChange={(event) => setCompareForm((previous) => ({ ...previous, topK: Number(event.target.value) }))}
          />
          <Button
            onClick={() => compareMutation.mutate()}
            disabled={!compareForm.documentIdA || !compareForm.documentIdB || compareMutation.isPending}
          >
            执行对比
          </Button>
          <JsonViewer title="对比结果" value={compareMutation.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>相似文档推荐</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Select
            value={similarForm.documentId}
            options={[{ label: "请选择源文档", value: "" }, ...documentOptions]}
            onChange={(event) => setSimilarForm((previous) => ({ ...previous, documentId: event.target.value }))}
          />
          <div className="grid grid-cols-2 gap-2">
            <Input
              type="number"
              value={similarForm.limit}
              onChange={(event) =>
                setSimilarForm((previous) => ({
                  ...previous,
                  limit: Number(event.target.value),
                }))
              }
            />
            <Input
              type="number"
              step={0.1}
              value={similarForm.minSimilarity}
              onChange={(event) =>
                setSimilarForm((previous) => ({
                  ...previous,
                  minSimilarity: Number(event.target.value),
                }))
              }
            />
          </div>
          <Button onClick={() => similarMutation.mutate()} disabled={!similarForm.documentId || similarMutation.isPending}>
            获取推荐
          </Button>
          <JsonViewer title="推荐结果" value={similarMutation.data} />
        </CardContent>
      </Card>
    </div>
  );
}
