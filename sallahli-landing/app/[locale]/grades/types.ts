export interface AIEvaluation {
  raisonnement: string;
  score_final: number;
  justification: string;
}

export interface GradeResult {
  student_answer: string;
  ai_evaluation: AIEvaluation;
  max_score?: number;
  erreur?: string;
}

export interface BilanGlobal {
  total_points: number;
  total_max: number;
  note_sur_20: string;
  message: string;
  timestamp?: string;
}

export interface TranscriptionDocument {
  filename: string;
  mime_type: string;
  pdf_base64?: string | null;
  raw_text: string;
}

export interface GradesData {
  [key: string]: GradeResult;
}

export interface BatchSummary {
  total_files: number;
  completed: number;
  failed: number;
  average_note_sur_20: string;
  timestamp?: string;
}

export interface BatchExamResult {
  file: string;
  file_index: number;
  status: 'completed' | 'error';
  results?: Record<string, unknown>;
  error?: string;
}

export interface FileProgress {
  file: string;
  file_index: number;
  status: string;
  message: string;
  progress: number;
  stepProgress?: number;
  completed?: number;
  total?: number;
  error?: string;
  steps?: Record<string, ProcessingStepProgress>;
}

export interface ProcessingStepProgress {
  status: 'pending' | 'active' | 'done' | 'error';
  progress: number;
  message?: string;
  completed?: number;
  total?: number;
  item?: string;
}

export interface SSEEvent {
  step: string;
  message: string;
  progress: number;
  file?: string;
  file_index?: number;
  total_files?: number;
  step_progress?: number;
  step_completed?: number;
  step_total?: number;
  step_label?: string;
  item?: string;
  error?: string;
  results?: Record<string, unknown>;
}
