import graph from "./ecommerce-agent.graph.json";
import type { ArchitectureGraph } from "./types";

/** Real offline output of discovery -> analyzer -> graph. No live API. */
export const demoGraph = graph as ArchitectureGraph;
export const repositoryName = "m-peker/ecommerce-ai-agent";
export const repositoryCommit = "3d38d5ab7fa0f27bd5c28488afa354abaf2577b4";

export { initialSelection } from "./selection";
