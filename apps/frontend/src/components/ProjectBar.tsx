"use client";

import { useState } from "react";

import type { Project } from "@/types/contracts";

interface Props {
  projects: Project[];
  selectedId: string | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
  onDelete: (project: Project) => void;
}

/** Smallest project-aware flow: pick a project, create one, delete one. AOIs are saved into it. */
export function ProjectBar({ projects, selectedId, busy, onSelect, onCreate, onDelete }: Props) {
  const [name, setName] = useState("");
  const selected = projects.find((p) => p.id === selectedId) ?? null;

  return (
    <section
      aria-label="Project"
      style={{ display: "grid", gap: 6, border: "1px solid #ccd", padding: 8 }}
    >
      <label>
        Project
        <select
          aria-label="Project"
          value={selectedId ?? ""}
          onChange={(e) => onSelect(e.target.value)}
          disabled={projects.length === 0}
          style={{ width: "100%" }}
        >
          {projects.length === 0 && <option value="">No projects yet</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.aoi_count} AOI{p.aoi_count === 1 ? "" : "s"})
            </option>
          ))}
        </select>
      </label>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          aria-label="New project name"
          placeholder="New project name"
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          style={{ flex: 1 }}
        />
        <button
          type="button"
          disabled={busy || !name.trim()}
          onClick={() => {
            onCreate(name.trim());
            setName("");
          }}
        >
          Create project
        </button>
        <button
          type="button"
          disabled={busy || !selected}
          onClick={() => selected && onDelete(selected)}
        >
          Delete project
        </button>
      </div>
      {projects.length === 0 && <small>Create a project to save AOIs into.</small>}
    </section>
  );
}
