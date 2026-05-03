'use client';

import { useMemo } from 'react';
import { Download, FileText } from 'lucide-react';
import type { TranscriptionDocument } from '@/app/[locale]/grades/types';

export function TranscriptionDocumentPreview({ document }: { document?: TranscriptionDocument | null }) {
  const pdfUrl = useMemo(() => {
    if (!document?.pdf_base64) return null;
    return `data:${document.mime_type || 'application/pdf'};base64,${document.pdf_base64}`;
  }, [document]);

  if (!document) return null;

  return (
    <section className="bg-card border border-border rounded-xl overflow-hidden shadow-sm mb-10">
      <div className="bg-muted px-6 py-4 border-b border-border flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-primary" />
          <div>
            <h2 className="text-lg font-serif font-bold text-foreground">Document transcrit</h2>
            <p className="text-sm text-muted-foreground mt-0.5">{document.filename}</p>
          </div>
        </div>
        {pdfUrl && (
          <a
            href={pdfUrl}
            download={document.filename || 'transcribed_student_work.pdf'}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition"
          >
            <Download className="w-4 h-4" />
            Télécharger
          </a>
        )}
      </div>

      {pdfUrl ? (
        <iframe
          title="Aperçu du document transcrit"
          src={pdfUrl}
          className="w-full h-[620px] bg-background"
        />
      ) : (
        <div className="p-6">
          <div className="bg-background border border-border rounded-lg p-6 max-h-[620px] overflow-auto">
            <pre className="whitespace-pre-wrap font-mono text-sm leading-7 text-foreground">
              {document.raw_text}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}
