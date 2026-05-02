import { NextRequest, NextResponse } from 'next/server';

/**
 * POST /api/analyze
 * 
 * Proxy route that forwards FormData (handwritten_work + rubric PDFs)
 * to the external Python AI service and streams SSE progress back.
 */
export async function POST(request: NextRequest) {
  const PYTHON_API_URL = process.env.PYTHON_API_URL;

  if (!PYTHON_API_URL) {
    return NextResponse.json(
      { error: 'PYTHON_API_URL is not configured on the server.' },
      { status: 500 }
    );
  }

  try {
    // Get the FormData from the incoming request
    const formData = await request.formData();

    const handwrittenWork = formData.get('handwritten_work');
    const rubric = formData.get('rubric');

    // Validate both files are present
    if (!handwrittenWork || !(handwrittenWork instanceof File)) {
      return NextResponse.json(
        { error: 'Le fichier "Copie manuscrite" est requis.' },
        { status: 400 }
      );
    }
    if (!rubric || !(rubric instanceof File)) {
      return NextResponse.json(
        { error: 'Le fichier "Barème" est requis.' },
        { status: 400 }
      );
    }

    // Build a new FormData to send to the Python service
    const proxyFormData = new FormData();
    proxyFormData.append('handwritten_work', handwrittenWork, handwrittenWork.name);
    proxyFormData.append('rubric', rubric, rubric.name);

    // Forward to the Python service (SSE endpoint)
    const pythonResponse = await fetch(`${PYTHON_API_URL}/api/analyze`, {
      method: 'POST',
      body: proxyFormData,
      // Don't set Content-Type — fetch will set multipart boundary automatically
    });

    if (!pythonResponse.ok) {
      const errorText = await pythonResponse.text();
      return NextResponse.json(
        { error: `Erreur du service IA: ${errorText}` },
        { status: pythonResponse.status }
      );
    }

    // Stream the SSE response back to the frontend
    if (!pythonResponse.body) {
      return NextResponse.json(
        { error: 'No response body from AI service.' },
        { status: 502 }
      );
    }

    // Pass through the SSE stream
    return new Response(pythonResponse.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });

  } catch (error) {
    console.error('[API /analyze] Error:', error);
    
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: `Impossible de contacter le service IA: ${message}` },
      { status: 502 }
    );
  }
}

// Increase the body size limit for PDF uploads (default is 4MB in Next.js)
export const config = {
  api: {
    bodyParser: false,
  },
};
