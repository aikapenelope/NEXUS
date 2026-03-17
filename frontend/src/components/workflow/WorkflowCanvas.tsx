"use client";

import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type OnConnect,
  type NodeTypes,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  LayoutGrid,
  Plus,
  Download,
  Upload,
  Trash2,
} from "lucide-react";
import { AgentNode, type AgentNodeData } from "./AgentNode";
import { getLayoutedElements } from "./layout";
import type { RegistryAgent } from "@/lib/types";
import type { WorkflowStep } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────

interface WorkflowCanvasProps {
  /** Available agents for the drag palette. */
  agents: RegistryAgent[];
  /** Initial steps to render (edit mode). */
  initialSteps?: WorkflowStep[];
  /** Called when the user saves the canvas as steps. */
  onSave?: (steps: WorkflowStep[]) => void;
  /** Step statuses during execution (step index -> status). */
  executionStatus?: Record<number, "running" | "complete" | "error">;
  /** If true, canvas is read-only (execution view). */
  readOnly?: boolean;
}

// ── Helpers ─────────────────────────────────────────────────────────

let nodeIdCounter = 0;
function nextNodeId(): string {
  nodeIdCounter += 1;
  return `agent-${nodeIdCounter}`;
}

function stepsToFlow(
  steps: WorkflowStep[],
  executionStatus?: Record<number, "running" | "complete" | "error">
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = steps.map((step, i) => ({
    id: `step-${i}`,
    type: "agentNode",
    position: { x: 0, y: 0 },
    data: {
      label: step.agent_name,
      role: "agent",
      promptTemplate: step.prompt_template,
      requiresApproval: step.requires_approval ?? false,
      status: executionStatus?.[i] ?? "idle",
    } satisfies AgentNodeData,
  }));

  const edges: Edge[] = steps.slice(1).map((_, i) => ({
    id: `e-${i}-${i + 1}`,
    source: `step-${i}`,
    target: `step-${i + 1}`,
    animated: executionStatus?.[i] === "running",
    style: { stroke: "#52525b", strokeWidth: 2 },
  }));

  return getLayoutedElements(nodes, edges);
}

function flowToSteps(nodes: Node[], edges: Edge[]): WorkflowStep[] {
  // Build adjacency from edges
  const adj = new Map<string, string>();
  for (const e of edges) {
    adj.set(e.source, e.target);
  }

  // Find root nodes (no incoming edge)
  const targets = new Set(edges.map((e) => e.target));
  const roots = nodes.filter((n) => !targets.has(n.id));

  // Walk the chain from each root
  const ordered: Node[] = [];
  const visited = new Set<string>();

  function walk(nodeId: string) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);
    const node = nodes.find((n) => n.id === nodeId);
    if (node) ordered.push(node);
    const next = adj.get(nodeId);
    if (next) walk(next);
  }

  for (const root of roots) {
    walk(root.id);
  }

  // Add any unvisited nodes at the end
  for (const n of nodes) {
    if (!visited.has(n.id)) ordered.push(n);
  }

  return ordered.map((n) => {
    const d = n.data as unknown as AgentNodeData;
    return {
      agent_name: d.label,
      prompt_template: d.promptTemplate || "{input}",
      requires_approval: d.requiresApproval,
    };
  });
}

// ── Component ───────────────────────────────────────────────────────

export function WorkflowCanvas({
  agents,
  initialSteps,
  onSave,
  executionStatus,
  readOnly = false,
}: WorkflowCanvasProps) {
  const nodeTypes: NodeTypes = useMemo(
    () => ({ agentNode: AgentNode }),
    []
  );

  const initial = useMemo(() => {
    if (initialSteps && initialSteps.length > 0) {
      return stepsToFlow(initialSteps, executionStatus);
    }
    return { nodes: [] as Node[], edges: [] as Edge[] };
  }, [initialSteps, executionStatus]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [showPalette, setShowPalette] = useState(false);

  const onConnect: OnConnect = useCallback(
    (params) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            style: { stroke: "#52525b", strokeWidth: 2 },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  const addAgentNode = useCallback(
    (agent: RegistryAgent) => {
      const id = nextNodeId();
      const newNode: Node = {
        id,
        type: "agentNode",
        position: {
          x: 100 + Math.random() * 200,
          y: 100 + nodes.length * 120,
        },
        data: {
          label: agent.name,
          role: agent.role,
          promptTemplate: "{input}",
          requiresApproval: false,
          status: "idle",
        } satisfies AgentNodeData,
      };
      setNodes((nds) => [...nds, newNode]);
      setShowPalette(false);
    },
    [nodes.length, setNodes]
  );

  const handleAutoLayout = useCallback(() => {
    const { nodes: ln, edges: le } = getLayoutedElements(nodes, edges);
    setNodes(ln);
    setEdges(le);
  }, [nodes, edges, setNodes, setEdges]);

  const handleSave = useCallback(() => {
    const steps = flowToSteps(nodes, edges);
    onSave?.(steps);
  }, [nodes, edges, onSave]);

  const handleExport = useCallback(() => {
    const steps = flowToSteps(nodes, edges);
    const blob = new Blob([JSON.stringify(steps, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "workflow.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [nodes, edges]);

  const handleImport = useCallback(() => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const text = await file.text();
      try {
        const steps: WorkflowStep[] = JSON.parse(text);
        const { nodes: n, edges: ed } = stepsToFlow(steps);
        setNodes(n);
        setEdges(ed);
      } catch {
        // Invalid JSON, ignore
      }
    };
    input.click();
  }, [setNodes, setEdges]);

  const handleClear = useCallback(() => {
    setNodes([]);
    setEdges([]);
  }, [setNodes, setEdges]);

  return (
    <div className="relative w-full h-full min-h-[500px] bg-zinc-950 rounded-xl border border-zinc-800 overflow-hidden">
      {/* Toolbar */}
      {!readOnly && (
        <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5">
          <button
            onClick={() => setShowPalette(!showPalette)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Agent
          </button>
          <button
            onClick={handleAutoLayout}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            title="Auto-layout"
          >
            <LayoutGrid className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            title="Export JSON"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleImport}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            title="Import JSON"
          >
            <Upload className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleClear}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-red-400 bg-zinc-900 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            title="Clear canvas"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Save button */}
      {!readOnly && onSave && nodes.length > 0 && (
        <div className="absolute top-3 right-3 z-10">
          <button
            onClick={handleSave}
            className="px-3 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
          >
            Save Steps
          </button>
        </div>
      )}

      {/* Agent palette dropdown */}
      {showPalette && !readOnly && (
        <div className="absolute top-12 left-3 z-20 w-56 max-h-64 overflow-y-auto bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl">
          {agents.length === 0 ? (
            <div className="p-3 text-xs text-zinc-500">
              No agents available. Create agents first.
            </div>
          ) : (
            agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => addAgentNode(agent)}
                className="w-full text-left px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors border-b border-zinc-800 last:border-0"
              >
                <span className="font-medium">{agent.name}</span>
                <span className="text-zinc-500 ml-2">({agent.role})</span>
              </button>
            ))
          )}
        </div>
      )}

      {/* React Flow canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={readOnly ? undefined : onNodesChange}
        onEdgesChange={readOnly ? undefined : onEdgesChange}
        onConnect={readOnly ? undefined : onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable={!readOnly}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#27272a"
        />
        <Controls
          showInteractive={false}
          className="!bg-zinc-900 !border-zinc-700 !rounded-lg [&>button]:!bg-zinc-900 [&>button]:!border-zinc-700 [&>button]:!text-zinc-400 [&>button:hover]:!bg-zinc-800"
        />
        <MiniMap
          nodeColor="#10b981"
          maskColor="rgba(0,0,0,0.7)"
          className="!bg-zinc-900 !border-zinc-700 !rounded-lg"
        />
      </ReactFlow>

      {/* Empty state */}
      {nodes.length === 0 && !readOnly && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-zinc-600">
            <LayoutGrid className="w-8 h-8 mx-auto mb-2" />
            <p className="text-sm">
              Click &quot;Add Agent&quot; to build your workflow
            </p>
            <p className="text-xs mt-1">
              Connect nodes by dragging from handles
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
