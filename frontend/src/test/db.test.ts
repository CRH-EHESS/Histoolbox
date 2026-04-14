import { describe, it, expect, beforeEach } from "vitest";
import { db, createProject, updateProject, getProjectById, getAllProjects, getProjectsByStatus } from "../db";

// Chaque test repart d'une DB vide
beforeEach(async () => {
  await db.ocr_projects.clear();
});

const sampleProject = {
  id: "task-001",
  fileName: "ludendorff.pdf",
  pdfBlob: new Blob(["fake-pdf"], { type: "application/pdf" }),
  markdownContent: "",
  status: "pending" as const,
};

describe("createProject", () => {
  it("insère un projet dans IndexedDB", async () => {
    await createProject(sampleProject);
    const p = await db.ocr_projects.get("task-001");
    expect(p).toBeDefined();
    expect(p!.fileName).toBe("ludendorff.pdf");
    expect(p!.createdAt).toBeTypeOf("number");
    expect(p!.updatedAt).toBeTypeOf("number");
  });
});

describe("updateProject", () => {
  it("met à jour les champs spécifiés", async () => {
    await createProject(sampleProject);
    await updateProject("task-001", { status: "completed", markdownContent: "# Titre" });
    const p = await getProjectById("task-001");
    expect(p!.status).toBe("completed");
    expect(p!.markdownContent).toBe("# Titre");
  });

  it("met à jour updatedAt", async () => {
    await createProject(sampleProject);
    const before = (await getProjectById("task-001"))!.updatedAt;
    // Petit délai pour que updatedAt change
    await new Promise((r) => setTimeout(r, 5));
    await updateProject("task-001", { status: "processing" });
    const after = (await getProjectById("task-001"))!.updatedAt;
    expect(after).toBeGreaterThanOrEqual(before);
  });
});

describe("getProjectById", () => {
  it("retourne undefined pour un id inexistant", async () => {
    const result = await getProjectById("inexistant");
    expect(result).toBeUndefined();
  });

  it("retourne le bon projet", async () => {
    await createProject(sampleProject);
    const p = await getProjectById("task-001");
    expect(p!.id).toBe("task-001");
  });
});

describe("getAllProjects", () => {
  it("retourne tous les projets triés par createdAt desc", async () => {
    await createProject({ ...sampleProject, id: "a" });
    await new Promise((r) => setTimeout(r, 5));
    await createProject({ ...sampleProject, id: "b" });
    const all = await getAllProjects();
    expect(all).toHaveLength(2);
    expect(all[0].id).toBe("b"); // le plus récent en premier
  });
});

describe("getProjectsByStatus", () => {
  it("filtre par statut", async () => {
    await createProject({ ...sampleProject, id: "p1", status: "pending" });
    await createProject({ ...sampleProject, id: "p2", status: "processing" });
    await createProject({ ...sampleProject, id: "p3", status: "completed" });

    const processing = await getProjectsByStatus("processing");
    expect(processing).toHaveLength(1);
    expect(processing[0].id).toBe("p2");
  });
});
