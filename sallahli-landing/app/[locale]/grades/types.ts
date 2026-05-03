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

export interface SSEEvent {
  step: string;
  message: string;
  progress: number;
  step_progress?: number;
  step_completed?: number;
  step_total?: number;
  step_label?: string;
  item?: string;
  results?: Record<string, unknown>;
}
