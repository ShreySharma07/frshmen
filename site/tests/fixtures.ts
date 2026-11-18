// Sample resumes for the resume tests: real-looking shapes (a fresher with projects, an internship,
// a long bullet that wraps, a skills line), not real people.
import type { ResumeDoc } from "../src/lib/resumeDoc.ts";

export const FRESHER: ResumeDoc = {
  v: 1, from: "pdf", name: "Asha Rao",
  contact: ["asha.rao@example.com · +91 90000 00000 · github.com/asharao · Pune"],
  sections: [
    { heading: "Education", items: [
      { kind: "entry", title: "B.Tech, Computer Science (AI)", right: "2022 – 2026", sub: "Example Institute of Technology", subRight: "CGPA 8.7", bullets: [] },
    ] },
    { heading: "Experience", items: [
      { kind: "entry", title: "ML Intern", right: "May 2025 – Jul 2025", sub: "Acme Labs", subRight: "Bengaluru", bullets: [
        "Distilled a BERT classifier to 40% of its size with knowledge distillation; served it with FastAPI at 12 ms p95.",
        "Cut weekly labelling time by 30% with an active-learning queue that ranks the least certain examples first and sends them to reviewers in batches.",
      ] },
    ] },
    { heading: "Projects", items: [
      { kind: "entry", title: "Speculative decoding for a 7B LLM", right: "2025", sub: "", subRight: "", bullets: [
        "Built draft-and-verify decoding in PyTorch: 2.1x faster generation at the same quality.",
        "Wrote CUDA kernels for the verification step.",
      ] },
      { kind: "entry", title: "RAG search over 10k papers", right: "2024", sub: "", subRight: "", bullets: [
        "Built hybrid retrieval with BM25 and embeddings; answers cite their sources.",
      ] },
    ] },
    { heading: "Skills", items: [
      { kind: "text", text: "Languages: Python, C++, SQL" },
      { kind: "text", text: "ML: PyTorch, Hugging Face, vLLM, CUDA" },
    ] },
  ],
};
