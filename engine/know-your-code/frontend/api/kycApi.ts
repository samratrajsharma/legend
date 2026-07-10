// Wraps the host's pre-configured axios instance (JWT interceptor + 401 redirect already set).
// Do NOT instantiate axios or manage tokens here.
import api from '../../../api/client';

export type RepoSource = 'git' | 'upload';

export interface Repo {
  id: string; name: string; source: RepoSource; source_url?: string | null;
  status: 'indexing' | 'ready' | 'failed'; stats: Record<string, any>;
  progress: Record<string, any>; created_at: string;
}
export interface FileNode { id: string; path: string; language: string; size_bytes: number; }
export interface QASource { path: string; line_start: number; line_end: number; name?: string; }
export interface QAResponse { session_id: string; question: string; answer: string; sources: QASource[]; tokens_used: number; }
export interface QATurn { id: string; question: string; answer: string; sources: QASource[]; created_at: string; }
export interface GraphNode { id: string; label: string; kind: string; language?: string; }
export interface GraphEdge { source: string; target: string; type: string; }
export interface Architecture { nodes: GraphNode[]; edges: GraphEdge[]; }
export interface TourStep { title: string; description: string; file_path?: string | null; line_range?: string | null; }
export interface Tour { id?: string; generated_at?: string; steps: TourStep[]; }

export const kycApi = {
  listRepos: () => api.get<Repo[]>('/know-your-code/repos'),
  createRepo: (data: { source: RepoSource; source_url?: string; name: string }) =>
    api.post<Repo>('/know-your-code/repos', data),
  uploadZip: (id: string, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<Repo>(`/know-your-code/repos/${id}/upload`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } });
  },
  getRepo: (id: string) => api.get<Repo>(`/know-your-code/repos/${id}`),
  deleteRepo: (id: string) => api.delete(`/know-your-code/repos/${id}`),
  listFiles: (id: string) => api.get<FileNode[]>(`/know-your-code/repos/${id}/files`),
  fileContent: (id: string, fileId: string) =>
    api.get<{ path: string; language: string; content: string }>(
      `/know-your-code/repos/${id}/files/${fileId}/content`),
  askQuestion: (id: string, question: string, session_id?: string) =>
    api.post<QAResponse>(`/know-your-code/repos/${id}/qa`, { question, session_id }),
  qaHistory: (id: string) => api.get<QATurn[]>(`/know-your-code/repos/${id}/qa-history`),
  getArchitecture: (id: string) => api.get<Architecture>(`/know-your-code/repos/${id}/architecture`),
  generateTour: (id: string) => api.post<Tour>(`/know-your-code/repos/${id}/tour`, {}),
  getTour: (id: string) => api.get<Tour>(`/know-your-code/repos/${id}/tour`),
};
