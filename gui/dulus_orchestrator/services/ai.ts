import { GoogleGenAI } from '@google/genai';
import { extractBase64Data, getMimeType } from '../utils.ts';

export const ai = new GoogleGenAI({ apiKey: process.env.API_KEY, vertexai: true });

export const generateChatStream = async (
  prompt: string,
  history: { role: string; parts: any[] }[],
  imageUrl?: string,
  systemInstruction?: string
) => {
  const parts: any[] = [];
  
  if (imageUrl) {
    parts.push({
      inlineData: {
        mimeType: getMimeType(imageUrl),
        data: extractBase64Data(imageUrl),
      },
    });
  }
  
  parts.push({ text: prompt });

  const contents = [...history, { role: 'user', parts }];

  const config: any = {
    systemInstruction: systemInstruction || "You are Dulus, an advanced autonomous AI orchestrator. You manage sub-agents, execute tools, and provide cosmic wisdom. Format responses in markdown.",
  };

  return await ai.models.generateContentStream({
    model: 'gemini-2.5-flash',
    contents,
    config,
  });
};

export const generateImage = async (prompt: string) => {
  const response = await ai.models.generateImages({
    model: 'imagen-4.0-generate-001',
    prompt: `Premium, highly detailed, masterpiece, cosmic, mystical: ${prompt}`,
    config: {
      numberOfImages: 1,
      outputMimeType: 'image/jpeg',
      aspectRatio: '16:9',
    },
  });

  const base64ImageBytes = response.generatedImages[0].image.imageBytes;
  return `data:image/jpeg;base64,${base64ImageBytes}`;
};

